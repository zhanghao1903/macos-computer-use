"""Candidate matching and scoring for internal selector resolution."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .models import (
    AttributeMatcher,
    Frame,
    JsonValue,
    MatchRule,
    SelectorConstraint,
    SelectorEvidence,
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
    if match.enabled is not None and bool(node.get("enabled")) != match.enabled:
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
    return True, SelectorEvidence(
        matched_attributes=matched_attributes,
        matched_actions=match.actions_include,
        score_breakdown=score_breakdown,
    )


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
    return True


def _json_value(value: Any) -> JsonValue | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)
