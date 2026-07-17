"""WeChat-specific Accessibility control map loading."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


CONTROL_MAP_SCHEMA_VERSION = "wechat.control-map.v1"


@dataclass(frozen=True)
class WeChatMappedControl:
    control_id: str
    ax_paths: tuple[str, ...]
    role: str
    labels: tuple[str, ...] = ()
    screen_coordinates: tuple[tuple[int, int], ...] = ()
    action: str = "AXPress"
    kind: str = "ui.press"
    risk: str = "changes_focus"


@dataclass(frozen=True)
class WeChatRootResolverStep:
    attribute: str
    index: int
    path_index: int | None = None


@dataclass(frozen=True)
class WeChatRootResolver:
    strategy: str
    steps: tuple[WeChatRootResolverStep, ...]


@dataclass(frozen=True)
class WeChatMappedCollection:
    collection_id: str
    root_ax_paths: tuple[str, ...]
    roles: tuple[str, ...]
    root_resolvers: dict[str, WeChatRootResolver] = field(default_factory=dict)
    attributes: tuple[str, ...] = ()
    actions: bool = True
    max_depth: int = 3
    minimum_limit: int = 80
    limit_multiplier: int = 4
    time_budget_ms: int = 2_200
    prefer_visible_rows: bool = False


@dataclass(frozen=True)
class WeChatControlMap:
    schema_version: str
    map_id: str
    map_version: str
    navigation: dict[str, WeChatMappedControl]
    regions: dict[str, WeChatMappedControl]
    collections: dict[str, WeChatMappedCollection]


def load_control_map(
    selector_profile_path: str | Path | None = None,
) -> WeChatControlMap:
    """Load the WeChat control map from an override or the packaged profile."""

    from .profiles import load_selector_assets

    return load_selector_assets(selector_profile_path).control_map


def load_packaged_control_map() -> WeChatControlMap:
    """Load the default packaged WeChat control map."""

    from .profiles import load_packaged_selector_assets

    return load_packaged_selector_assets().control_map


def parse_control_map(data: Mapping[str, Any]) -> WeChatControlMap:
    """Parse a WeChat private control map section."""

    map_data = _mapping(data.get("control_map"), "control_map")
    schema_version = _string(
        map_data.get("schema_version"),
        "control_map.schema_version",
    )
    if schema_version != CONTROL_MAP_SCHEMA_VERSION:
        raise ValueError(f"unsupported WeChat control map schema: {schema_version}")
    navigation = {
        control_id: _parse_control(control_id, control_data)
        for control_id, control_data in _mapping(
            map_data.get("navigation", {}),
            "control_map.navigation",
        ).items()
    }
    regions = {
        region_id: _parse_control(region_id, region_data, default_risk="read_only")
        for region_id, region_data in _mapping(
            map_data.get("regions", {}),
            "control_map.regions",
        ).items()
    }
    collections = {
        collection_id: _parse_collection(collection_id, collection_data)
        for collection_id, collection_data in _mapping(
            map_data.get("collections", {}),
            "control_map.collections",
        ).items()
    }
    if not navigation:
        raise ValueError("control_map.navigation must be non-empty")
    if not collections:
        raise ValueError("control_map.collections must be non-empty")
    return WeChatControlMap(
        schema_version=schema_version,
        map_id=_string(map_data.get("map_id"), "control_map.map_id"),
        map_version=_string(map_data.get("map_version"), "control_map.map_version"),
        navigation=navigation,
        regions=regions,
        collections=collections,
    )


def _parse_control(
    control_id: str,
    data: Any,
    *,
    default_risk: str = "changes_focus",
) -> WeChatMappedControl:
    payload = _mapping(data, f"control_map.{control_id}")
    return WeChatMappedControl(
        control_id=control_id,
        ax_paths=_strings(payload.get("ax_paths"), f"{control_id}.ax_paths"),
        role=_string(payload.get("role"), f"{control_id}.role"),
        labels=_strings(payload.get("labels", ()), f"{control_id}.labels"),
        screen_coordinates=_coordinate_pairs(
            payload.get("screen_coordinates", ()),
            f"{control_id}.screen_coordinates",
        ),
        action=_string(payload.get("action", "AXPress"), f"{control_id}.action"),
        kind=_string(payload.get("kind", "ui.press"), f"{control_id}.kind"),
        risk=_string(payload.get("risk", default_risk), f"{control_id}.risk"),
    )


def _parse_collection(
    collection_id: str,
    data: Any,
) -> WeChatMappedCollection:
    payload = _mapping(data, f"control_map.collections.{collection_id}")
    return WeChatMappedCollection(
        collection_id=collection_id,
        root_ax_paths=_strings(
            payload.get("root_ax_paths"),
            f"{collection_id}.root_ax_paths",
        ),
        roles=_strings(payload.get("roles"), f"{collection_id}.roles"),
        root_resolvers=_parse_root_resolvers(
            payload.get("root_resolvers", {}),
            collection_id,
        ),
        attributes=_strings(
            payload.get("attributes", ()),
            f"{collection_id}.attributes",
            allow_empty=True,
        ),
        actions=_bool(payload.get("actions", True), f"{collection_id}.actions"),
        max_depth=_positive_int(
            payload.get("max_depth", 3),
            f"{collection_id}.max_depth",
        ),
        minimum_limit=_positive_int(
            payload.get("minimum_limit", 80),
            f"{collection_id}.minimum_limit",
        ),
        limit_multiplier=_positive_int(
            payload.get("limit_multiplier", 4),
            f"{collection_id}.limit_multiplier",
        ),
        time_budget_ms=_positive_int(
            payload.get("time_budget_ms", 2_200),
            f"{collection_id}.time_budget_ms",
        ),
        prefer_visible_rows=_bool(
            payload.get("prefer_visible_rows", False),
            f"{collection_id}.prefer_visible_rows",
        ),
    )


def _parse_root_resolvers(
    value: Any,
    collection_id: str,
) -> dict[str, WeChatRootResolver]:
    if value in (None, {}, ()):
        return {}
    payload = _mapping(
        value,
        f"control_map.collections.{collection_id}.root_resolvers",
    )
    resolvers: dict[str, WeChatRootResolver] = {}
    for ax_path, resolver_data in payload.items():
        path = _string(ax_path, f"{collection_id}.root_resolvers path")
        resolver_payload = _mapping(
            resolver_data,
            f"{collection_id}.root_resolvers.{path}",
        )
        strategy = _string(
            resolver_payload.get("strategy", "attributePath"),
            f"{collection_id}.root_resolvers.{path}.strategy",
        )
        if strategy != "attributePath":
            raise ValueError(
                f"{collection_id}.root_resolvers.{path}.strategy must be "
                "attributePath"
            )
        raw_steps = resolver_payload.get("steps")
        if not isinstance(raw_steps, list | tuple) or not raw_steps:
            raise ValueError(
                f"{collection_id}.root_resolvers.{path}.steps must be non-empty"
            )
        steps = tuple(
            _parse_root_resolver_step(step, collection_id, path, index)
            for index, step in enumerate(raw_steps)
        )
        resolvers[path] = WeChatRootResolver(strategy=strategy, steps=steps)
    return resolvers


def _parse_root_resolver_step(
    value: Any,
    collection_id: str,
    ax_path: str,
    index: int,
) -> WeChatRootResolverStep:
    payload = _mapping(
        value,
        f"{collection_id}.root_resolvers.{ax_path}.steps[{index}]",
    )
    field_name = f"{collection_id}.root_resolvers.{ax_path}.steps[{index}]"
    path_index = payload.get("path_index", payload.get("pathIndex"))
    return WeChatRootResolverStep(
        attribute=_string(payload.get("attribute"), f"{field_name}.attribute"),
        index=_non_negative_int(payload.get("index"), f"{field_name}.index"),
        path_index=(
            None
            if path_index is None
            else _non_negative_int(path_index, f"{field_name}.path_index")
        ),
    )


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a table")
    return value


def _string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _strings(
    value: Any,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_name} must be a string list")
    items = tuple(_string(item, field_name) for item in value)
    if not items and not allow_empty:
        raise ValueError(f"{field_name} must be non-empty")
    return items


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _coordinate_pairs(value: Any, field_name: str) -> tuple[tuple[int, int], ...]:
    if value in (None, (), []):
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_name} must be a list of coordinate objects")
    coordinates: list[tuple[int, int]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a table")
        x = _non_negative_int(item.get("x"), f"{field_name}[{index}].x")
        y = _non_negative_int(item.get("y"), f"{field_name}[{index}].y")
        coordinates.append((x, y))
    return tuple(coordinates)


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return int(value)


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return int(value)


__all__ = [
    "CONTROL_MAP_SCHEMA_VERSION",
    "WeChatControlMap",
    "WeChatMappedCollection",
    "WeChatMappedControl",
    "WeChatRootResolver",
    "WeChatRootResolverStep",
    "load_control_map",
    "load_packaged_control_map",
    "parse_control_map",
]
