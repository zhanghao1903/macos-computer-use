"""Validation for internal Accessibility selector profiles."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from ..accessibility_limits import (
    MAX_ACCESSIBILITY_QUERY_DEPTH,
    MAX_ACCESSIBILITY_QUERY_LIMIT,
)
from .models import (
    AccessibilitySelectorProfile,
    ActionDefinition,
    ActionPrecondition,
    AttributeMatcher,
    CachePolicy,
    CollectionDefinition,
    ConfidencePolicy,
    FieldDefinition,
    MatchRule,
    PaginationPolicy,
    RelationRule,
    SelectorConstraint,
    SelectorDefinition,
    SelectorRoot,
    SelectorStep,
)


SUPPORTED_SCHEMA_VERSIONS = {"app-control.selector-profile.v1"}
PICK_STRATEGIES = {"first", "best", "largestArea", "all", "nearestToAnchor"}
CACHE_MODES = {"disabled", "read", "readWrite"}
ROOT_KINDS = {"focusedWindow", "frontmostApp", "selector", "axPath"}
STEP_SCOPES = {"self", "children", "descendants"}
RELATION_KINDS = {"rightOf", "leftOf", "above", "below", "inside", "near"}
CONSTRAINT_KINDS = {
    "hasChildRole",
    "hasDescendantRole",
    "minChildren",
    "frameWithin",
    "rightOf",
    "below",
    "selected",
}
FIELD_SOURCES = {"self", "descendant", "attribute", "computed"}
PAGINATION_MODES = {"none", "visibleWindow", "cursor"}
ACTION_RISKS = {
    "read_only",
    "changes_focus",
    "changes_current_chat",
    "submits_text",
}
ACTION_PRECONDITIONS = {
    "appFrontmost",
    "windowTitleMatches",
    "signatureMatches",
    "selectorStillMatches",
}
ALLOWED_TRANSFORMS = {"strip", "firstText", "joinText", "toBool"}
COMPUTED_FIELD_ATTRIBUTES = {"summary", "elementRef"}


class SelectorProfileValidationError(ValueError):
    """Raised when a selector profile is invalid."""


def validate_selector_profile(profile: AccessibilitySelectorProfile) -> None:
    """Validate a parsed selector profile or raise fail-closed errors."""

    if profile.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SelectorProfileValidationError(
            f"unsupported selector profile schema: {profile.schema_version}"
        )
    _require_non_empty(profile.profile_id, "profile_id")
    _require_non_empty(profile.profile_version, "profile_version")
    _require_non_empty(profile.app.app_id, "app.app_id")
    if not profile.app.bundle_ids:
        raise SelectorProfileValidationError("app.bundle_ids must be non-empty")
    for pattern in profile.app.window_title_patterns:
        _compile_regex(pattern, "app.window_title_patterns")
    for alias, values in profile.locale_aliases.items():
        _require_non_empty(alias, "locale alias")
        if not values:
            raise SelectorProfileValidationError(
                f"locale alias {alias!r} must be non-empty"
            )
        for value in values:
            _require_non_empty(value, f"locale alias {alias}")
    if not profile.selectors:
        raise SelectorProfileValidationError("selectors must be non-empty")

    selector_ids = set(profile.selectors)
    collection_ids = set(profile.collections)
    action_ids = set(profile.actions)
    _validate_unique_keys(selector_ids, profile.selectors, "selector")
    _validate_unique_keys(collection_ids, profile.collections, "collection")
    _validate_unique_keys(action_ids, profile.actions, "action")

    for selector_id, selector in profile.selectors.items():
        if selector.selector_id != selector_id:
            raise SelectorProfileValidationError(
                f"selector key {selector_id!r} must match selector_id "
                f"{selector.selector_id!r}"
            )
        _validate_selector(
            selector,
            selector_ids,
            profile.locale_aliases,
            f"selectors.{selector_id}",
        )
    _validate_fallback_cycles(profile.selectors)

    for collection_id, collection in profile.collections.items():
        if collection.collection_id != collection_id:
            raise SelectorProfileValidationError(
                f"collection key {collection_id!r} must match collection_id "
                f"{collection.collection_id!r}"
            )
        _validate_collection(
            collection,
            selector_ids,
            profile.locale_aliases,
            f"collections.{collection_id}",
        )

    for action_id, action in profile.actions.items():
        if action.action_id != action_id:
            raise SelectorProfileValidationError(
                f"action key {action_id!r} must match action_id {action.action_id!r}"
            )
        _validate_action(action, selector_ids, f"actions.{action_id}")


def _validate_selector(
    selector: SelectorDefinition,
    selector_ids: set[str],
    locale_aliases: dict[str, tuple[str, ...]],
    field_name: str,
) -> None:
    _require_non_empty(selector.selector_id, f"{field_name}.selector_id")
    _validate_root(selector.root, selector_ids, f"{field_name}.root")
    if not selector.steps:
        raise SelectorProfileValidationError(f"{field_name}.steps must be non-empty")
    for index, step in enumerate(selector.steps):
        _validate_step(step, selector_ids, locale_aliases, f"{field_name}.steps[{index}]")
    for index, constraint in enumerate(selector.constraints):
        _validate_constraint(constraint, f"{field_name}.constraints[{index}]")
    if selector.pick not in PICK_STRATEGIES:
        raise SelectorProfileValidationError(f"{field_name}.pick is invalid")
    if selector.pick == "nearestToAnchor" and selector.steps[-1].relation is None:
        raise SelectorProfileValidationError(
            f"{field_name}.pick nearestToAnchor requires a final-step relation"
        )
    _validate_confidence(
        selector.confidence,
        f"{field_name}.confidence",
        pick=selector.pick,
    )
    _validate_cache(selector.cache, f"{field_name}.cache")
    for fallback in selector.fallbacks:
        if fallback not in selector_ids:
            raise SelectorProfileValidationError(
                f"{field_name}.fallbacks references unknown selector {fallback!r}"
            )


def _validate_root(
    root: SelectorRoot,
    selector_ids: set[str],
    field_name: str,
) -> None:
    if root.kind not in ROOT_KINDS:
        raise SelectorProfileValidationError(f"{field_name}.kind is invalid")
    if root.kind == "selector":
        if root.selector_id not in selector_ids:
            raise SelectorProfileValidationError(
                f"{field_name}.selector_id references unknown selector "
                f"{root.selector_id!r}"
            )
    elif root.selector_id is not None:
        raise SelectorProfileValidationError(
            f"{field_name}.selector_id is only valid for selector roots"
        )
    if root.kind == "axPath":
        _require_non_empty(root.ax_path, f"{field_name}.ax_path")


def _validate_step(
    step: SelectorStep,
    selector_ids: set[str],
    locale_aliases: dict[str, tuple[str, ...]],
    field_name: str,
) -> None:
    if step.scope not in STEP_SCOPES:
        raise SelectorProfileValidationError(f"{field_name}.scope is invalid")
    if not 0 <= step.max_depth <= MAX_ACCESSIBILITY_QUERY_DEPTH:
        raise SelectorProfileValidationError(
            f"{field_name}.max_depth must be between 0 and "
            f"{MAX_ACCESSIBILITY_QUERY_DEPTH}"
        )
    if step.limit <= 0:
        raise SelectorProfileValidationError(f"{field_name}.limit must be > 0")
    if step.limit > MAX_ACCESSIBILITY_QUERY_LIMIT:
        raise SelectorProfileValidationError(
            f"{field_name}.limit must be <= {MAX_ACCESSIBILITY_QUERY_LIMIT}"
        )
    if step.time_budget_ms <= 0:
        raise SelectorProfileValidationError(
            f"{field_name}.time_budget_ms must be > 0"
        )
    _validate_match(step.match, locale_aliases, f"{field_name}.match")
    if step.relation is not None:
        _validate_relation(step.relation, selector_ids, f"{field_name}.relation")


def _validate_match(
    match: MatchRule,
    locale_aliases: dict[str, tuple[str, ...]],
    field_name: str,
) -> None:
    if match.role and match.role_in and match.role not in match.role_in:
        raise SelectorProfileValidationError(
            f"{field_name}.role must not conflict with role_in"
        )
    for attr, matcher in match.attributes.items():
        _require_non_empty(attr, f"{field_name}.attributes key")
        _validate_attribute_matcher(
            matcher,
            locale_aliases,
            f"{field_name}.attributes.{attr}",
        )


def _validate_attribute_matcher(
    matcher: AttributeMatcher,
    locale_aliases: dict[str, tuple[str, ...]],
    field_name: str,
) -> None:
    if matcher.regex is not None:
        _compile_regex(matcher.regex, f"{field_name}.regex")
    if matcher.alias_ref is not None and matcher.alias_ref not in locale_aliases:
        raise SelectorProfileValidationError(
            f"{field_name}.alias_ref references unknown alias {matcher.alias_ref!r}"
        )
    if matcher.any_of is not None and not matcher.any_of:
        raise SelectorProfileValidationError(f"{field_name}.any_of must be non-empty")


def _validate_relation(
    relation: RelationRule,
    selector_ids: set[str],
    field_name: str,
) -> None:
    if relation.anchor_selector_id not in selector_ids:
        raise SelectorProfileValidationError(
            f"{field_name}.anchor_selector_id references unknown selector "
            f"{relation.anchor_selector_id!r}"
        )
    if relation.relation not in RELATION_KINDS:
        raise SelectorProfileValidationError(f"{field_name}.relation is invalid")
    if relation.max_distance is not None:
        _require_finite_number(relation.max_distance, f"{field_name}.max_distance")
    if relation.max_distance is not None and relation.max_distance <= 0:
        raise SelectorProfileValidationError(
            f"{field_name}.max_distance must be > 0"
        )
    if relation.relation == "near" and relation.max_distance is None:
        raise SelectorProfileValidationError(
            f"{field_name}.max_distance is required for near relations"
        )


def _validate_constraint(
    constraint: SelectorConstraint,
    field_name: str,
) -> None:
    if constraint.kind not in CONSTRAINT_KINDS:
        raise SelectorProfileValidationError(f"{field_name}.kind is invalid")
    _require_finite_number(constraint.weight, f"{field_name}.weight")
    if constraint.weight < 0:
        raise SelectorProfileValidationError(f"{field_name}.weight must be >= 0")
    if constraint.kind == "minChildren":
        if (
            not isinstance(constraint.value, int)
            or isinstance(constraint.value, bool)
            or constraint.value < 0
        ):
            raise SelectorProfileValidationError(
                f"{field_name}.value must be a non-negative integer"
            )
    elif constraint.kind == "selected":
        if not isinstance(constraint.value, bool):
            raise SelectorProfileValidationError(
                f"{field_name}.value must be a boolean"
            )
    elif constraint.kind in {"hasChildRole", "hasDescendantRole"}:
        if not isinstance(constraint.value, str) or not constraint.value:
            raise SelectorProfileValidationError(
                f"{field_name}.value must be a non-empty role string"
            )
    elif constraint.kind in {"frameWithin", "rightOf", "below"}:
        _validate_frame_value(constraint.value, f"{field_name}.value")


def _validate_confidence(
    confidence: ConfidencePolicy,
    field_name: str,
    *,
    pick: str,
) -> None:
    _require_finite_number(confidence.minimum, f"{field_name}.minimum")
    if not 0 <= confidence.minimum <= 1:
        raise SelectorProfileValidationError(f"{field_name}.minimum must be 0..1")
    weights = (
        confidence.attribute_weight,
        confidence.action_weight,
        confidence.structure_weight,
        confidence.geometry_weight,
        confidence.cache_weight,
    )
    for index, weight in enumerate(weights):
        _require_finite_number(weight, f"{field_name}.weights[{index}]")
    if any(weight < 0 for weight in weights):
        raise SelectorProfileValidationError(f"{field_name} weights must be >= 0")
    if pick == "best" and all(weight == 0 for weight in weights):
        raise SelectorProfileValidationError(
            f"{field_name} must have at least one non-zero weight for best pick"
        )


def _validate_frame_value(value: object, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise SelectorProfileValidationError(f"{field_name} must be a frame object")
    for key in ("x", "y", "width", "height"):
        field_value = value.get(key)
        if not isinstance(field_value, (int, float)) or isinstance(field_value, bool):
            raise SelectorProfileValidationError(
                f"{field_name}.{key} must be a number"
            )
        _require_finite_number(field_value, f"{field_name}.{key}")
    if value["width"] < 0 or value["height"] < 0:
        raise SelectorProfileValidationError(
            f"{field_name}.width and height must be >= 0"
        )


def _require_finite_number(value: int | float, field_name: str) -> None:
    if not math.isfinite(float(value)):
        raise SelectorProfileValidationError(f"{field_name} must be finite")


def _validate_cache(cache: CachePolicy, field_name: str) -> None:
    if cache.mode not in CACHE_MODES:
        raise SelectorProfileValidationError(f"{field_name}.mode is invalid")
    if cache.ttl_seconds is not None and cache.ttl_seconds <= 0:
        raise SelectorProfileValidationError(f"{field_name}.ttl_seconds must be > 0")
    if cache.mode != "disabled" and not cache.validate_signature:
        raise SelectorProfileValidationError(
            f"{field_name}.validate_signature must be true when cache is enabled"
        )


def _validate_collection(
    collection: CollectionDefinition,
    selector_ids: set[str],
    locale_aliases: dict[str, tuple[str, ...]],
    field_name: str,
) -> None:
    if collection.root_selector_id not in selector_ids:
        raise SelectorProfileValidationError(
            f"{field_name}.root_selector_id references unknown selector "
            f"{collection.root_selector_id!r}"
        )
    _validate_selector(
        collection.item_selector,
        selector_ids,
        locale_aliases,
        f"{field_name}.item_selector",
    )
    _validate_collection_item_selector(
        collection.item_selector,
        collection.root_selector_id,
        f"{field_name}.item_selector",
    )
    if not collection.fields:
        raise SelectorProfileValidationError(f"{field_name}.fields must be non-empty")
    for name, field in collection.fields.items():
        _require_non_empty(name, f"{field_name}.fields key")
        _validate_field(field, selector_ids, locale_aliases, f"{field_name}.{name}")
    _validate_pagination(collection.pagination, f"{field_name}.pagination")


def _validate_field(
    field: FieldDefinition,
    selector_ids: set[str],
    locale_aliases: dict[str, tuple[str, ...]],
    field_name: str,
) -> None:
    if field.source not in FIELD_SOURCES:
        raise SelectorProfileValidationError(f"{field_name}.source is invalid")
    if field.source == "descendant" and field.selector is None:
        raise SelectorProfileValidationError(
            f"{field_name}.selector is required for descendant fields"
        )
    if field.source != "descendant" and field.selector is not None:
        raise SelectorProfileValidationError(
            f"{field_name}.selector is only supported for descendant fields"
        )
    if field.source == "attribute" and field.attribute is None:
        raise SelectorProfileValidationError(
            f"{field_name}.attribute is required for {field.source} fields"
        )
    if (
        field.source == "computed"
        and field.attribute is not None
        and field.attribute not in COMPUTED_FIELD_ATTRIBUTES
    ):
        raise SelectorProfileValidationError(
            f"{field_name}.attribute is not an allowlisted computed field: "
            f"{field.attribute!r}"
        )
    if field.source == "computed" and field.attribute == "elementRef":
        if field.selector is not None:
            raise SelectorProfileValidationError(
                f"{field_name}.selector is not valid for computed elementRef"
            )
        if field.transform is not None:
            raise SelectorProfileValidationError(
                f"{field_name}.transform is not valid for computed elementRef"
            )
    if field.selector is not None:
        _validate_selector(
            field.selector,
            selector_ids,
            locale_aliases,
            f"{field_name}.selector",
        )
        _validate_collection_field_selector(
            field.selector,
            f"{field_name}.selector",
        )
    if field.transform is not None and field.transform not in ALLOWED_TRANSFORMS:
        raise SelectorProfileValidationError(
            f"{field_name}.transform is not allowlisted: {field.transform!r}"
        )


def _validate_collection_item_selector(
    selector: SelectorDefinition,
    root_selector_id: str,
    field_name: str,
) -> None:
    if len(selector.steps) != 1:
        raise SelectorProfileValidationError(
            f"{field_name}.steps must contain exactly one executable step"
        )
    if (
        selector.root.kind != "selector"
        or selector.root.selector_id != root_selector_id
    ):
        raise SelectorProfileValidationError(
            f"{field_name}.root must reference collection root selector "
            f"{root_selector_id!r}"
        )
    _validate_collection_selector_policy(
        selector,
        expected_pick="all",
        field_name=field_name,
    )


def _validate_collection_field_selector(
    selector: SelectorDefinition,
    field_name: str,
) -> None:
    if len(selector.steps) != 1:
        raise SelectorProfileValidationError(
            f"{field_name}.steps must contain exactly one executable step"
        )
    if selector.root != SelectorRoot(kind="focusedWindow"):
        raise SelectorProfileValidationError(
            f"{field_name}.root must use the contextual focusedWindow root"
        )
    _validate_collection_selector_policy(
        selector,
        expected_pick="first",
        field_name=field_name,
    )


def _validate_collection_selector_policy(
    selector: SelectorDefinition,
    *,
    expected_pick: str,
    field_name: str,
) -> None:
    if selector.pick != expected_pick:
        raise SelectorProfileValidationError(
            f"{field_name}.pick must be {expected_pick!r}"
        )
    if selector.cache.mode != "disabled":
        raise SelectorProfileValidationError(
            f"{field_name}.cache.mode must be 'disabled'"
        )
    if selector.fallbacks:
        raise SelectorProfileValidationError(
            f"{field_name}.fallbacks are not supported"
        )
    if selector.confidence != ConfidencePolicy():
        raise SelectorProfileValidationError(
            f"{field_name}.confidence customization is not supported"
        )
    if selector.steps[0].relation is not None:
        raise SelectorProfileValidationError(
            f"{field_name}.steps[0].relation is not supported"
        )


def _validate_pagination(
    pagination: PaginationPolicy,
    field_name: str,
) -> None:
    if pagination.mode not in PAGINATION_MODES:
        raise SelectorProfileValidationError(f"{field_name}.mode is invalid")
    if pagination.mode == "cursor":
        raise SelectorProfileValidationError(
            f"{field_name}.mode cursor is not supported in the internal MVP"
        )
    if pagination.default_limit <= 0:
        raise SelectorProfileValidationError(
            f"{field_name}.default_limit must be > 0"
        )
    if pagination.max_limit < pagination.default_limit:
        raise SelectorProfileValidationError(
            f"{field_name}.max_limit must be >= default_limit"
        )


def _validate_action(
    action: ActionDefinition,
    selector_ids: set[str],
    field_name: str,
) -> None:
    if action.selector_id not in selector_ids:
        raise SelectorProfileValidationError(
            f"{field_name}.selector_id references unknown selector "
            f"{action.selector_id!r}"
        )
    _require_non_empty(action.ax_action, f"{field_name}.ax_action")
    if action.risk not in ACTION_RISKS:
        raise SelectorProfileValidationError(f"{field_name}.risk is invalid")
    if (
        action.enabled_by_default
        and action.risk not in {"read_only", "changes_focus"}
    ):
        raise SelectorProfileValidationError(
            f"{field_name}.enabled_by_default is only allowed for read or focus actions"
        )
    for index, precondition in enumerate(action.preconditions):
        _validate_precondition(precondition, f"{field_name}.preconditions[{index}]")


def _validate_precondition(
    precondition: ActionPrecondition,
    field_name: str,
) -> None:
    if precondition.kind not in ACTION_PRECONDITIONS:
        raise SelectorProfileValidationError(f"{field_name}.kind is invalid")


def _validate_fallback_cycles(
    selectors: dict[str, SelectorDefinition],
) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(selector_id: str) -> None:
        if selector_id in visited:
            return
        if selector_id in visiting:
            raise SelectorProfileValidationError(
                f"selector fallback cycle includes {selector_id!r}"
            )
        visiting.add(selector_id)
        for fallback in selectors[selector_id].fallbacks:
            visit(fallback)
        visiting.remove(selector_id)
        visited.add(selector_id)

    for selector_id in selectors:
        visit(selector_id)


def _validate_unique_keys(
    keys: set[str],
    values: dict[str, object],
    field_name: str,
) -> None:
    if len(keys) != len(values):
        raise SelectorProfileValidationError(f"duplicate {field_name} ids")


def _compile_regex(pattern: str, field_name: str) -> None:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise SelectorProfileValidationError(
            f"{field_name} must be a valid regex: {exc}"
        ) from exc


def _require_non_empty(value: str | None, field_name: str) -> None:
    if value is None or not value.strip():
        raise SelectorProfileValidationError(f"{field_name} must be non-empty")
