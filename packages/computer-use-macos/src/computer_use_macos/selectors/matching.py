"""Candidate matching and scoring for internal selector resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import re
from typing import Any

from .models import (
    AttributeMatcher,
    Frame,
    JsonValue,
    MatchRule,
    RelationRule,
    SelectorConstraint,
    SelectorEvidence,
    SelectorStep,
)


ATTRIBUTE_ALIASES = {
    "AXRole": "role",
    "AXTitle": "title",
    "AXValue": "value",
    "AXDescription": "description",
    "AXPlaceholderValue": "placeholderValue",
    "AXHelp": "help",
}


def node_role(node: Mapping[str, Any]) -> str:
    return str(node.get("role") or node.get("AXRole") or "")


def node_actions(node: Mapping[str, Any]) -> tuple[str, ...]:
    actions = node.get("actions") or ()
    if not isinstance(actions, list | tuple):
        return ()
    return tuple(str(action) for action in actions)


def node_ax_path(node: Mapping[str, Any]) -> str | None:
    path = node.get("axPath") or node.get("path")
    return str(path) if path is not None and str(path).strip() else None


def node_frame(node: Mapping[str, Any]) -> Frame | None:
    frame = node.get("frame")
    if not isinstance(frame, Mapping):
        return None
    try:
        return Frame(
            x=float(frame["x"]),
            y=float(frame["y"]),
            width=float(frame["width"]),
            height=float(frame["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def node_visible(node: Mapping[str, Any]) -> bool | None:
    visible = node.get("visible")
    if isinstance(visible, bool):
        return visible
    hidden = node.get("hidden")
    if hidden is None:
        hidden = node.get("AXHidden")
    if isinstance(hidden, bool):
        return not hidden
    if "raw" in node and isinstance(node["raw"], Mapping):
        raw_hidden = node["raw"].get("AXHidden")
        if isinstance(raw_hidden, bool):
            return not raw_hidden
    frame = node_frame(node)
    if frame is not None:
        return frame.width > 0 and frame.height > 0
    return None


def node_enabled(node: Mapping[str, Any]) -> bool | None:
    enabled = node.get("enabled")
    if isinstance(enabled, bool):
        return enabled
    ax_enabled = node.get("AXEnabled")
    if isinstance(ax_enabled, bool):
        return ax_enabled
    if "raw" in node and isinstance(node["raw"], Mapping):
        raw_enabled = node["raw"].get("AXEnabled")
        if isinstance(raw_enabled, bool):
            return raw_enabled
    return None


def node_attribute(node: Mapping[str, Any], attribute: str) -> JsonValue | None:
    key = ATTRIBUTE_ALIASES.get(attribute, attribute)
    value = node.get(key)
    if value is None and "raw" in node and isinstance(node["raw"], Mapping):
        value = node["raw"].get(attribute)
    return _json_value(value)


def node_label(node: Mapping[str, Any]) -> str | None:
    for attribute in ("AXDescription", "AXTitle", "AXValue", "AXPlaceholderValue"):
        value = node_attribute(node, attribute)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def match_node(
    node: Mapping[str, Any],
    match: MatchRule,
    locale_aliases: Mapping[str, tuple[str, ...]],
) -> tuple[bool, SelectorEvidence]:
    matched_attributes: dict[str, JsonValue] = {}
    score_breakdown: dict[str, float] = {}
    role = node_role(node)
    allowed_roles = tuple(match.role_in)
    if match.role is not None and role != match.role:
        return False, SelectorEvidence()
    if allowed_roles and role not in allowed_roles:
        return False, SelectorEvidence()
    if match.actions_include:
        actions = node_actions(node)
        if not all(action in actions for action in match.actions_include):
            return False, SelectorEvidence()
    if match.enabled is not None:
        enabled = node_enabled(node)
        if enabled is None or enabled != match.enabled:
            return False, SelectorEvidence()
    if match.visible is not None:
        visible = node_visible(node)
        if visible is None or visible != match.visible:
            return False, SelectorEvidence()

    attribute_matches = 0
    for attribute, matcher in match.attributes.items():
        value = node_attribute(node, attribute)
        if not attribute_matches_rule(value, matcher, locale_aliases):
            return False, SelectorEvidence()
        matched_attributes[attribute] = value
        attribute_matches += 1

    if match.attributes:
        score_breakdown["attributes"] = attribute_matches / len(match.attributes)
    if match.actions_include:
        score_breakdown["actions"] = 1.0
    if match.role or match.role_in:
        score_breakdown["role"] = 1.0
    if match.enabled is not None:
        score_breakdown["enabled"] = 1.0
    if match.visible is not None:
        score_breakdown["visible"] = 1.0
    return True, SelectorEvidence(
        matched_attributes=matched_attributes,
        matched_actions=match.actions_include,
        score_breakdown=score_breakdown,
    )


def effective_step_match(step: SelectorStep) -> MatchRule:
    """Return the match rule including step-level role filters."""

    if step.role_in and not step.match.role_in:
        return replace(step.match, role_in=step.role_in)
    return step.match


def attribute_matches_rule(
    value: JsonValue | None,
    matcher: AttributeMatcher,
    locale_aliases: Mapping[str, tuple[str, ...]],
) -> bool:
    if matcher.exists is True and value is None:
        return False
    if matcher.exists is False and value is not None:
        return False
    if matcher.alias_ref is not None:
        aliases = locale_aliases.get(matcher.alias_ref, ())
        if value not in aliases:
            return False
    if matcher.equals is not None and value != matcher.equals:
        return False
    if matcher.any_of is not None and value not in matcher.any_of:
        return False
    if matcher.contains is not None:
        if not isinstance(value, str) or matcher.contains not in value:
            return False
    if matcher.regex is not None:
        if not isinstance(value, str) or re.search(matcher.regex, value) is None:
            return False
    return True


def constraints_match(
    node: Mapping[str, Any],
    constraints: tuple[SelectorConstraint, ...],
) -> tuple[bool, tuple[str, ...], float]:
    matched: list[str] = []
    score = 0.0
    for constraint in constraints:
        passed = _constraint_passes(node, constraint)
        if not passed and constraint.required:
            return False, tuple(matched), score
        if passed:
            matched.append(constraint.kind)
            score += constraint.weight
    return True, tuple(matched), score


def relation_match(
    candidate_frame: Frame | None,
    anchor_frames: tuple[Frame, ...],
    relation: RelationRule,
) -> bool:
    if candidate_frame is None or not anchor_frames:
        return False
    return any(
        _frame_relation_match(candidate_frame, anchor_frame, relation)
        for anchor_frame in anchor_frames
    )


def confidence_score(
    evidence: SelectorEvidence,
    *,
    constraint_score: float,
) -> float:
    if not evidence.score_breakdown and constraint_score == 0:
        return 1.0
    score = 0.0
    if evidence.score_breakdown:
        score += sum(evidence.score_breakdown.values()) / len(evidence.score_breakdown)
    score += min(constraint_score, 1.0)
    divisor = 2 if constraint_score else 1
    return min(score / divisor, 1.0)


def _constraint_passes(
    node: Mapping[str, Any],
    constraint: SelectorConstraint,
) -> bool:
    if constraint.kind == "minChildren":
        try:
            return int(node.get("childrenCount", 0)) >= int(constraint.value)
        except (TypeError, ValueError):
            return False
    if constraint.kind == "selected":
        return bool(node.get("selected")) == bool(constraint.value)
    if constraint.kind in {"hasChildRole", "hasDescendantRole"}:
        roles = node.get("childRoles") or node.get("descendantRoles") or ()
        return isinstance(roles, list | tuple) and str(constraint.value) in roles
    if constraint.kind == "frameWithin":
        candidate = node_frame(node)
        bounds = _frame_constraint_value(constraint.value)
        if candidate is None or bounds is None:
            return False
        return _frame_inside(candidate, bounds)
    if constraint.kind == "rightOf":
        candidate = node_frame(node)
        anchor = _frame_constraint_value(constraint.value)
        if candidate is None or anchor is None:
            return False
        return _frame_right_of(candidate, anchor)
    if constraint.kind == "below":
        candidate = node_frame(node)
        anchor = _frame_constraint_value(constraint.value)
        if candidate is None or anchor is None:
            return False
        return _frame_below(candidate, anchor)
    return False


def _frame_relation_match(
    candidate: Frame,
    anchor: Frame,
    relation: RelationRule,
) -> bool:
    candidate_right = candidate.x + candidate.width
    candidate_bottom = candidate.y + candidate.height
    anchor_right = anchor.x + anchor.width
    anchor_bottom = anchor.y + anchor.height

    distance: float
    if relation.relation == "rightOf":
        if candidate.x < anchor_right or not _ranges_overlap(
            candidate.y,
            candidate_bottom,
            anchor.y,
            anchor_bottom,
        ):
            return False
        distance = candidate.x - anchor_right
    elif relation.relation == "leftOf":
        if candidate_right > anchor.x or not _ranges_overlap(
            candidate.y,
            candidate_bottom,
            anchor.y,
            anchor_bottom,
        ):
            return False
        distance = anchor.x - candidate_right
    elif relation.relation == "below":
        if candidate.y < anchor_bottom or not _ranges_overlap(
            candidate.x,
            candidate_right,
            anchor.x,
            anchor_right,
        ):
            return False
        distance = candidate.y - anchor_bottom
    elif relation.relation == "above":
        if candidate_bottom > anchor.y or not _ranges_overlap(
            candidate.x,
            candidate_right,
            anchor.x,
            anchor_right,
        ):
            return False
        distance = anchor.y - candidate_bottom
    elif relation.relation == "inside":
        if (
            candidate.x < anchor.x
            or candidate.y < anchor.y
            or candidate_right > anchor_right
            or candidate_bottom > anchor_bottom
        ):
            return False
        distance = 0.0
    else:
        candidate_center_x = candidate.x + candidate.width / 2
        candidate_center_y = candidate.y + candidate.height / 2
        anchor_center_x = anchor.x + anchor.width / 2
        anchor_center_y = anchor.y + anchor.height / 2
        distance = (
            (candidate_center_x - anchor_center_x) ** 2
            + (candidate_center_y - anchor_center_y) ** 2
        ) ** 0.5

    return relation.max_distance is None or distance <= relation.max_distance


def _frame_constraint_value(value: JsonValue) -> Frame | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return Frame(
            x=float(value["x"]),
            y=float(value["y"]),
            width=float(value["width"]),
            height=float(value["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _frame_inside(candidate: Frame, bounds: Frame) -> bool:
    return (
        candidate.x >= bounds.x
        and candidate.y >= bounds.y
        and candidate.x + candidate.width <= bounds.x + bounds.width
        and candidate.y + candidate.height <= bounds.y + bounds.height
    )


def _frame_right_of(candidate: Frame, anchor: Frame) -> bool:
    return candidate.x >= anchor.x + anchor.width and _ranges_overlap(
        candidate.y,
        candidate.y + candidate.height,
        anchor.y,
        anchor.y + anchor.height,
    )


def _frame_below(candidate: Frame, anchor: Frame) -> bool:
    return candidate.y >= anchor.y + anchor.height and _ranges_overlap(
        candidate.x,
        candidate.x + candidate.width,
        anchor.x,
        anchor.x + anchor.width,
    )


def _ranges_overlap(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> bool:
    return first_start < second_end and second_start < first_end


def _json_value(value: Any) -> JsonValue | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)
