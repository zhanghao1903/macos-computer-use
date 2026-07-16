"""Profile parsing helpers for internal Accessibility selectors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import (
    AccessibilitySelectorProfile,
    ActionDefinition,
    ActionPrecondition,
    AppIdentity,
    AttributeMatcher,
    CachePolicy,
    CollectionDefinition,
    CollectionDiagnosticsPolicy,
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
from .validation import validate_selector_profile


PROFILE_SCHEMA_VERSION = "app-control.selector-profile.v1"


def parse_selector_profile(
    data: Mapping[str, Any],
    *,
    validate: bool = True,
) -> AccessibilitySelectorProfile:
    """Parse a profile mapping into internal dataclasses.

    The input shape is intentionally dictionary-based so callers can load TOML,
    JSON, or package data without binding the selector MVP to one config format.
    """

    app_data = _mapping(data.get("app"), "app")
    profile = AccessibilitySelectorProfile(
        schema_version=_string(data.get("schema_version"), "schema_version"),
        profile_id=_string(data.get("profile_id"), "profile_id"),
        profile_version=_string(data.get("profile_version"), "profile_version"),
        app=AppIdentity(
            app_id=_string(app_data.get("app_id"), "app.app_id"),
            bundle_ids=_strings(app_data.get("bundle_ids", ()), "app.bundle_ids"),
            app_names=_strings(app_data.get("app_names", ()), "app.app_names"),
            supported_locales=_strings(
                app_data.get("supported_locales", ()),
                "app.supported_locales",
            ),
            window_title_patterns=_strings(
                app_data.get("window_title_patterns", ()),
                "app.window_title_patterns",
            ),
        ),
        locale_aliases={
            key: _strings(value, f"locale_aliases.{key}")
            for key, value in _mapping(
                data.get("locale_aliases", {}),
                "locale_aliases",
            ).items()
        },
        selectors={
            selector_id: _parse_selector(selector_id, selector_data)
            for selector_id, selector_data in _flatten_sections(
                _mapping(data.get("selectors", {}), "selectors")
            ).items()
        },
        collections={
            collection_id: _parse_collection(collection_id, collection_data)
            for collection_id, collection_data in _flatten_sections(
                _mapping(data.get("collections", {}), "collections")
            ).items()
        },
        actions={
            action_id: _parse_action(action_id, action_data)
            for action_id, action_data in _flatten_sections(
                _mapping(data.get("actions", {}), "actions")
            ).items()
        },
    )
    if validate:
        validate_selector_profile(profile)
    return profile


def _parse_selector(
    selector_id: str,
    data: Mapping[str, Any],
    *,
    default_root: SelectorRoot | None = None,
    default_pick: str = "best",
    default_cache_mode: str = "readWrite",
) -> SelectorDefinition:
    root_data = data.get("root")
    root = _parse_root(_mapping(root_data, f"{selector_id}.root")) if root_data else (
        default_root or SelectorRoot(kind="focusedWindow")
    )
    return SelectorDefinition(
        selector_id=_string(data.get("selector_id", selector_id), "selector_id"),
        description=_optional_string(data.get("description"), "description"),
        root=root,
        steps=tuple(
            _parse_step(step, f"{selector_id}.steps[{index}]")
            for index, step in enumerate(_sequence(data.get("steps", ()), "steps"))
        ),
        constraints=tuple(
            _parse_constraint(item, f"{selector_id}.constraints[{index}]")
            for index, item in enumerate(
                _sequence(data.get("constraints", ()), "constraints")
            )
        ),
        pick=_string(data.get("pick", default_pick), "pick"),  # type: ignore[arg-type]
        confidence=_parse_confidence(
            _mapping(data.get("confidence", {}), "confidence")
        ),
        fallbacks=_strings(data.get("fallbacks", ()), "fallbacks"),
        cache=_parse_cache(
            _mapping(data.get("cache", {}), "cache"),
            default_mode=default_cache_mode,
        ),
    )


def _parse_root(data: Mapping[str, Any]) -> SelectorRoot:
    return SelectorRoot(
        kind=_string(data.get("kind"), "root.kind"),  # type: ignore[arg-type]
        selector_id=_optional_string(data.get("selector_id"), "root.selector_id"),
        ax_path=_optional_string(data.get("ax_path"), "root.ax_path"),
    )


def _parse_step(data: Any, field_name: str) -> SelectorStep:
    step = _mapping(data, field_name)
    match_data = dict(_mapping(step.get("match", {}), f"{field_name}.match"))
    for key in ("role", "role_in", "actions_include", "enabled", "visible"):
        if key in step and key not in match_data:
            match_data[key] = step[key]
    return SelectorStep(
        scope=_string(step.get("scope"), f"{field_name}.scope"),  # type: ignore[arg-type]
        max_depth=_integer(step.get("max_depth"), f"{field_name}.max_depth"),
        limit=_integer(step.get("limit"), f"{field_name}.limit"),
        time_budget_ms=_integer(
            step.get("time_budget_ms"),
            f"{field_name}.time_budget_ms",
        ),
        role_in=_strings(step.get("role_in", ()), f"{field_name}.role_in"),
        match=_parse_match(match_data),
        relation=(
            _parse_relation(_mapping(step["relation"], f"{field_name}.relation"))
            if "relation" in step
            else None
        ),
    )


def _parse_match(data: Mapping[str, Any]) -> MatchRule:
    attributes = _mapping(data.get("attributes", {}), "match.attributes")
    return MatchRule(
        role=_optional_string(data.get("role"), "match.role"),
        role_in=_strings(data.get("role_in", ()), "match.role_in"),
        attributes={
            key: _parse_attribute_matcher(value, f"match.attributes.{key}")
            for key, value in attributes.items()
        },
        actions_include=_strings(
            data.get("actions_include", ()),
            "match.actions_include",
        ),
        enabled=_optional_bool(data.get("enabled"), "match.enabled"),
        visible=_optional_bool(data.get("visible"), "match.visible"),
    )


def _parse_attribute_matcher(data: Any, field_name: str) -> AttributeMatcher:
    matcher = _mapping(data, field_name)
    any_of = matcher.get("any_of")
    return AttributeMatcher(
        equals=matcher.get("equals"),
        any_of=tuple(_sequence(any_of, f"{field_name}.any_of")) if any_of else None,
        contains=_optional_string(matcher.get("contains"), f"{field_name}.contains"),
        regex=_optional_string(matcher.get("regex"), f"{field_name}.regex"),
        exists=_optional_bool(matcher.get("exists"), f"{field_name}.exists"),
        alias_ref=_optional_string(
            matcher.get("alias_ref"),
            f"{field_name}.alias_ref",
        ),
    )


def _parse_relation(data: Mapping[str, Any]) -> RelationRule:
    return RelationRule(
        anchor_selector_id=_string(
            data.get("anchor_selector_id"),
            "relation.anchor_selector_id",
        ),
        relation=_string(data.get("relation"), "relation.relation"),  # type: ignore[arg-type]
        max_distance=_optional_float(data.get("max_distance"), "relation.max_distance"),
    )


def _parse_constraint(data: Any, field_name: str) -> SelectorConstraint:
    constraint = _mapping(data, field_name)
    return SelectorConstraint(
        kind=_string(constraint.get("kind"), f"{field_name}.kind"),  # type: ignore[arg-type]
        value=constraint.get("value"),
        weight=_float(constraint.get("weight", 1.0), f"{field_name}.weight"),
        required=_bool(constraint.get("required", False), f"{field_name}.required"),
    )


def _parse_confidence(data: Mapping[str, Any]) -> ConfidencePolicy:
    return ConfidencePolicy(
        minimum=_float(data.get("minimum", 0.85), "confidence.minimum"),
        attribute_weight=_float(
            data.get("attribute_weight", 0.4),
            "confidence.attribute_weight",
        ),
        action_weight=_float(
            data.get("action_weight", 0.2),
            "confidence.action_weight",
        ),
        structure_weight=_float(
            data.get("structure_weight", 0.25),
            "confidence.structure_weight",
        ),
        geometry_weight=_float(
            data.get("geometry_weight", 0.1),
            "confidence.geometry_weight",
        ),
        cache_weight=_float(data.get("cache_weight", 0.05), "confidence.cache_weight"),
    )


def _parse_cache(
    data: Mapping[str, Any],
    *,
    default_mode: str = "readWrite",
) -> CachePolicy:
    return CachePolicy(
        mode=_string(data.get("mode", default_mode), "cache.mode"),  # type: ignore[arg-type]
        ttl_seconds=(
            _integer(data["ttl_seconds"], "cache.ttl_seconds")
            if "ttl_seconds" in data
            else 60
        ),
        validate_signature=_bool(
            data.get("validate_signature", True),
            "cache.validate_signature",
        ),
        key_attributes=_strings(data.get("key_attributes", ()), "cache.key_attributes"),
    )


def _parse_collection(
    collection_id: str,
    data: Mapping[str, Any],
) -> CollectionDefinition:
    root_selector_id = _string(data.get("root_selector_id"), "root_selector_id")
    item_data = _mapping(data.get("item_selector", data.get("item")), "item_selector")
    item_selector = _parse_selector(
        f"{collection_id}.item",
        item_data,
        default_root=SelectorRoot(kind="selector", selector_id=root_selector_id),
        default_pick="all",
        default_cache_mode="disabled",
    )
    fields = _mapping(data.get("fields", {}), "fields")
    return CollectionDefinition(
        collection_id=_string(data.get("collection_id", collection_id), "collection_id"),
        root_selector_id=root_selector_id,
        item_selector=item_selector,
        fields={
            key: _parse_field(value, f"fields.{key}")
            for key, value in fields.items()
        },
        pagination=_parse_pagination(
            _mapping(data.get("pagination", {}), "pagination")
        ),
        diagnostics=_parse_collection_diagnostics(
            _mapping(data.get("diagnostics", {}), "diagnostics")
        ),
    )


def _parse_field(data: Any, field_name: str) -> FieldDefinition:
    field = _mapping(data, field_name)
    selector_data = field.get("selector")
    selector = (
        _parse_selector(
            f"{field_name}.selector",
            _mapping(selector_data, f"{field_name}.selector"),
            default_pick="first",
            default_cache_mode="disabled",
        )
        if selector_data is not None
        else None
    )
    return FieldDefinition(
        source=_string(field.get("source"), f"{field_name}.source"),  # type: ignore[arg-type]
        selector=selector,
        attribute=_optional_string(field.get("attribute"), f"{field_name}.attribute"),
        required=_bool(field.get("required", False), f"{field_name}.required"),
        transform=_optional_string(field.get("transform"), f"{field_name}.transform"),
    )


def _parse_pagination(data: Mapping[str, Any]) -> PaginationPolicy:
    return PaginationPolicy(
        mode=_string(data.get("mode", "visibleWindow"), "pagination.mode"),  # type: ignore[arg-type]
        default_limit=_integer(
            data.get("default_limit", 30),
            "pagination.default_limit",
        ),
        max_limit=_integer(data.get("max_limit", 100), "pagination.max_limit"),
    )


def _parse_collection_diagnostics(
    data: Mapping[str, Any],
) -> CollectionDiagnosticsPolicy:
    return CollectionDiagnosticsPolicy(
        include_skipped_count=_bool(
            data.get("include_skipped_count", True),
            "diagnostics.include_skipped_count",
        ),
        include_field_failures=_bool(
            data.get("include_field_failures", True),
            "diagnostics.include_field_failures",
        ),
        include_candidate_counts=_bool(
            data.get("include_candidate_counts", True),
            "diagnostics.include_candidate_counts",
        ),
    )


def _parse_action(action_id: str, data: Mapping[str, Any]) -> ActionDefinition:
    return ActionDefinition(
        action_id=_string(data.get("action_id", action_id), "action_id"),
        selector_id=_string(data.get("selector_id"), "selector_id"),
        ax_action=_string(data.get("ax_action", data.get("action")), "ax_action"),
        risk=_string(data.get("risk"), "risk"),  # type: ignore[arg-type]
        preconditions=tuple(
            _parse_precondition(item, f"preconditions[{index}]")
            for index, item in enumerate(
                _sequence(data.get("preconditions", ()), "preconditions")
            )
        ),
        enabled_by_default=(
            _bool(data["enabled_by_default"], "enabled_by_default")
            if "enabled_by_default" in data
            else False
        ),
        description=_optional_string(data.get("description"), "description"),
    )


def _parse_precondition(data: Any, field_name: str) -> ActionPrecondition:
    precondition = _mapping(data, field_name)
    return ActionPrecondition(
        kind=_string(precondition.get("kind"), f"{field_name}.kind"),  # type: ignore[arg-type]
        value=precondition.get("value"),
    )


def _flatten_sections(data: Mapping[str, Any], prefix: str = "") -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for key, value in data.items():
        section_id = f"{prefix}.{key}" if prefix else str(key)
        mapping = _mapping(value, section_id)
        if _is_definition(mapping):
            output[section_id] = mapping
        else:
            output.update(_flatten_sections(mapping, section_id))
    return output


def _is_definition(data: Mapping[str, Any]) -> bool:
    return any(
        key in data
        for key in (
            "root",
            "steps",
            "root_selector_id",
            "item",
            "item_selector",
            "selector_id",
            "ax_action",
            "action",
            "risk",
        )
    )


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _sequence(value: Any, field_name: str) -> tuple[Any, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list")
    return tuple(value)


def _strings(value: Any, field_name: str) -> tuple[str, ...]:
    return tuple(_string(item, f"{field_name}[]") for item in _sequence(value, field_name))


def _string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _string(value, field_name)


def _integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _float(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _optional_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    return _float(value, field_name)


def _optional_bool(value: Any, field_name: str) -> bool | None:
    if value is None:
        return None
    return _bool(value, field_name)


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value
