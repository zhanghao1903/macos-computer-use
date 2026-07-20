"""Pure Accessibility query and WeChat element normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, cast

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._diagnostics import _contains_any, _failure, _number_value, _string_value
from .control_map import WeChatMappedControl, WeChatRootResolver
from .models import WeChatDesktopConfig


_MAPPED_NAVIGATION_FRAME_EDGE_TOLERANCE_POINTS = 1.0


_SELECTOR_PERMISSION_FAILURES = frozenset(
    {
        "missing_accessibility",
        "accessibility_not_trusted",
        "accessibility_permission_missing",
        "accessibility_query_permission_missing",
    }
)


_SELECTOR_TIMEOUT_FAILURES = frozenset(
    {
        "timeout",
        "accessibility_query_timeout",
        "accessibility_snapshot_timeout",
        "accessibility_tree_snapshot_timeout",
    }
)


_SELECTOR_TRANSPORT_FAILURES = frozenset(
    {
        "helper_transport_failed",
        "app_control_transport_failed",
        "local_service_failed",
        "local_service_unavailable",
        "socket_unavailable",
        "connection_failed",
        "accessibility_query_worker_failed",
        "accessibility_query_worker_empty_response",
        "accessibility_query_invalid_json",
        "accessibility_query_invalid_payload",
    }
)


_SELECTOR_TRUNCATION_FAILURES = frozenset(
    {
        "selector_query_truncated",
        "accessibility_query_truncated",
        "query_limit_reached",
        "query_time_budget_reached",
    }
)


_ACTION_REF_TTL_SECONDS = 300


_NAV_QUERY_LABELS: dict[str, tuple[str, ...]] = {
    "chats": ("聊天", "__EN_CHATS_PLACEHOLDER__"),
    "contacts": ("通讯录", "__EN_CONTACTS_PLACEHOLDER__"),
    "favorites": ("收藏", "__EN_FAVORITES_PLACEHOLDER__"),
}


_SEARCH_QUERY_LABELS = ("搜索", "search", "__EN_SEARCH_PLACEHOLDER__")


def _root_resolver_payload(resolver: WeChatRootResolver) -> dict[str, JsonValue]:
    steps: list[JsonValue] = []
    for step in resolver.steps:
        step_payload: dict[str, JsonValue] = {
            "attribute": step.attribute,
            "index": step.index,
        }
        if step.path_index is not None:
            step_payload["pathIndex"] = step.path_index
        steps.append(step_payload)
    return {
        "strategy": resolver.strategy,
        "steps": steps,
    }


def _node_from_selector_element(element: Any) -> dict[str, Any]:
    element_ref = element.element_ref
    node: dict[str, Any] = {
        "axPath": element_ref.ax_path,
        "role": element.role,
        "actions": list(element.actions),
    }
    if element.label is not None:
        node["description"] = element.label
    if element.frame is not None:
        node["frame"] = {
            "x": element.frame.x,
            "y": element.frame.y,
            "width": element.frame.width,
            "height": element.frame.height,
        }
    return node


def _selector_element_selected(element: Any) -> bool:
    value = element.evidence.matched_attributes.get("AXValue")
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "selected"}
    return False


def _failure_from_selector_result(
    command: ToolCommand,
    result: Any,
    *,
    failure_kind: str,
    message: str,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    if result.diagnostics.failure_kind in {
        "selector_query_failed",
        "selector_query_truncated",
    }:
        return _failure_from_selector_query(
            command,
            result.diagnostics,
            message=message,
            observation_key="selector",
            semantic_payload={
                "id": result.selector_id,
                "status": result.status,
                "profileId": result.profile_id,
                "profileVersion": result.profile_version,
                "diagnostics": _selector_diagnostics_payload(result.diagnostics),
            },
            evidence=evidence,
        )
    status = (
        ToolStatus.NOT_FOUND
        if result.status in {"not_found", "failed"}
        else ToolStatus.FAILED
    )
    return _failure(
        command,
        status=status,
        failure_kind=failure_kind,
        message=message,
        retryable=True,
        observation={
            "selector": {
                "id": result.selector_id,
                "status": result.status,
                "profileId": result.profile_id,
                "profileVersion": result.profile_version,
                "diagnostics": _selector_diagnostics_payload(result.diagnostics),
            }
        },
        evidence=evidence,
    )


def _failure_from_collection_result(
    command: ToolCommand,
    result: Any,
    *,
    failure_kind: str,
    message: str,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    if result.diagnostics.failure_kind in {
        "selector_query_failed",
        "selector_query_truncated",
    }:
        return _failure_from_selector_query(
            command,
            result.diagnostics,
            message=message,
            observation_key="collection",
            semantic_payload={
                "id": result.collection_id,
                "status": result.status,
                "profileId": result.profile_id,
                "profileVersion": result.profile_version,
                "diagnostics": _selector_diagnostics_payload(result.diagnostics),
            },
            evidence=evidence,
        )
    return _failure(
        command,
        status=ToolStatus.NOT_FOUND,
        failure_kind=failure_kind,
        message=message,
        retryable=True,
        observation={
            "collection": {
                "id": result.collection_id,
                "status": result.status,
                "profileId": result.profile_id,
                "profileVersion": result.profile_version,
                "diagnostics": _selector_diagnostics_payload(result.diagnostics),
            }
        },
        evidence=evidence,
    )


def _failure_from_selector_query(
    command: ToolCommand,
    diagnostics: Any,
    *,
    message: str,
    observation_key: str,
    semantic_payload: dict[str, JsonValue],
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    diagnostic_kind = diagnostics.failure_kind or "selector_query_failed"
    cause = diagnostics.cause_failure_kind
    cause_text = cause.casefold() if isinstance(cause, str) else ""
    diagnostic_kind_text = diagnostic_kind.casefold()
    diagnostic_message = diagnostics.message or message
    category: str | None = None
    if (
        diagnostic_kind_text in _SELECTOR_TRUNCATION_FAILURES
        or cause_text in _SELECTOR_TRUNCATION_FAILURES
    ):
        category = "truncation"
    elif cause_text in _SELECTOR_PERMISSION_FAILURES:
        category = "permission"
    elif cause_text in _SELECTOR_TIMEOUT_FAILURES:
        category = "timeout"
    elif cause_text in _SELECTOR_TRANSPORT_FAILURES:
        category = "transport"

    if category is None:
        context = f"{cause_text} {diagnostic_message.casefold()}"
        if any(
            token in context for token in ("permission", "accessibility_not_trusted")
        ):
            category = "permission"
        elif "timeout" in context or "timed_out" in context:
            category = "timeout"
        elif any(
            token in context
            for token in (
                "transport",
                "socket",
                "connection",
                "local_service",
                "helper",
            )
        ):
            category = "transport"
        else:
            category = "query"

    if category == "permission":
        status = ToolStatus.NOT_READY
        mapped_failure_kind = "missing_accessibility"
        default_retryable = False
        recovery_hint = (
            "Grant Accessibility permission to the process or helper that runs "
            "app-control, then retry."
        )
    elif category == "timeout":
        status = ToolStatus.FAILED
        mapped_failure_kind = "accessibility_query_timeout"
        default_retryable = True
        recovery_hint = "Retry the bounded Accessibility query after app state settles."
    elif category == "transport":
        status = ToolStatus.NOT_READY
        mapped_failure_kind = "app_control_transport_failed"
        default_retryable = True
        recovery_hint = "Restore the configured app-control transport, then retry."
    elif category == "truncation":
        status = ToolStatus.FAILED
        mapped_failure_kind = "wechat_query_truncated"
        default_retryable = True
        recovery_hint = (
            "Retry with a narrower selector or smaller page after app state settles."
        )
    else:
        status = ToolStatus.FAILED
        mapped_failure_kind = "accessibility_query_failed"
        default_retryable = True
        recovery_hint = "Restore Accessibility query readiness and retry."
    return _failure(
        command,
        status=status,
        failure_kind=mapped_failure_kind,
        message=diagnostic_message,
        recovery_hint=recovery_hint,
        retryable=(
            diagnostics.retryable
            if diagnostics.retryable is not None
            else default_retryable
        ),
        observation={observation_key: semantic_payload},
        evidence=evidence,
    )


def _selector_diagnostics_payload(diagnostics: Any) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "triedSelectors": list(diagnostics.tried_selectors),
        "queryCount": diagnostics.query_count,
        "nodeCount": diagnostics.node_count,
        "truncated": diagnostics.truncated,
        "cacheStatus": diagnostics.cache_status,
    }
    if diagnostics.truncation_reason is not None:
        payload["truncationReason"] = diagnostics.truncation_reason
    if diagnostics.failure_kind is not None:
        payload["failureKind"] = diagnostics.failure_kind
    if diagnostics.cause_failure_kind is not None:
        payload["causeFailureKind"] = diagnostics.cause_failure_kind
    if diagnostics.retryable is not None:
        payload["retryable"] = diagnostics.retryable
    if diagnostics.message is not None:
        payload["message"] = diagnostics.message
    return payload


def _query_payload(observation: ToolObservation) -> dict[str, Any]:
    payload = observation.observation.get("accessibilityQuery")
    if isinstance(payload, Mapping):
        return dict(payload)
    if observation.observation.get("schema") == "macos.accessibility.query.v1":
        return dict(observation.observation)
    return {}


def _query_nodes(observation: ToolObservation) -> list[dict[str, Any]]:
    payload = _query_payload(observation)
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [dict(item) for item in nodes if isinstance(item, Mapping)]


def _query_snapshot_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("snapshotId") or payload.get("snapshot_id")
    return value if isinstance(value, str) and value.strip() else None


def _navigation_from_query_nodes(
    nodes: list[dict[str, Any]],
    *,
    snapshot_id: str | None = None,
) -> list[dict[str, JsonValue]]:
    items: list[dict[str, JsonValue]] = []
    for node in nodes:
        if node.get("role") != "AXRadioButton":
            continue
        description = str(node.get("description") or "").casefold()
        semantic = None
        for key, labels in _NAV_QUERY_LABELS.items():
            if description in {label.casefold() for label in labels}:
                semantic = key
                break
        if semantic is None:
            continue
        element = _element_from_query_node(node)
        items.append(
            {
                "id": f"nav.{semantic}",
                "label": semantic,
                "selected": _node_selected(node),
                "element": element,
                "actionRef": _action_ref_from_node(
                    node,
                    action_id=f"nav.{semantic}.press",
                    kind="navigation.switch",
                    risk="low",
                    target_summary=f"Switch to {semantic}",
                    snapshot_id=snapshot_id,
                ),
            }
        )
    return items


def _main_content_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [node for node in nodes if node.get("role") == "AXSplitGroup"]
    if not candidates:
        return None
    return max(candidates, key=lambda node: _frame_area(node))


def _search_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    for node in nodes:
        if node.get("role") not in {"AXTextArea", "AXTextField"}:
            continue
        label = _node_label(node)
        if label and _contains_any(label, _SEARCH_QUERY_LABELS):
            return node
    for node in nodes:
        if node.get("role") in {"AXTextArea", "AXTextField"}:
            return node
    return None


def _window_from_query(
    config: WeChatDesktopConfig,
    query: Mapping[str, Any],
    *,
    navigation: list[dict[str, JsonValue]],
    main_content: Mapping[str, Any] | None,
    main_nodes: list[dict[str, Any]],
    include_actionables: bool,
) -> dict[str, JsonValue]:
    app = (
        cast(Mapping[str, Any], query.get("app"))
        if isinstance(query.get("app"), Mapping)
        else {}
    )
    window = (
        cast(Mapping[str, Any], query.get("window"))
        if isinstance(query.get("window"), Mapping)
        else {}
    )
    title = _string_value(window.get("title")) or config.app_name
    element: dict[str, JsonValue] = {
        "axPath": "0",
        "role": _string_value(window.get("role")) or "AXWindow",
        "label": title,
    }
    search = _search_node(main_nodes)
    regions: dict[str, JsonValue] = {}
    if main_content is not None:
        regions["mainContent"] = {
            "id": "main-content",
            "available": True,
            "element": _element_from_query_node(main_content, label="main-content"),
        }
    if search is not None:
        regions["searchBox"] = {
            "id": "search.focus",
            "available": True,
            "element": _element_from_query_node(search, label="search"),
        }
    actionables = []
    if include_actionables:
        for item in navigation:
            nav_element = item.get("element")
            if isinstance(nav_element, Mapping):
                actionables.append(
                    {
                        "id": f"nav.{item['label']}.press",
                        "kind": "navigation_item",
                        "label": item["label"],
                        "element": dict(nav_element),
                        "confidence": 1.0,
                        "actionRef": item.get("actionRef"),
                    }
                )
        if search is not None:
            actionables.append(
                {
                    "id": "search.focus",
                    "kind": "search_box",
                    "label": "search",
                    "element": _element_from_query_node(search, label="search"),
                    "confidence": 0.9,
                }
            )
    available_actions: list[dict[str, JsonValue]] = [
        {
            "id": "wechat.inspect_window.refresh",
            "kind": "wechat_operation",
            "status": "available",
            "operation": "inspect_window",
        },
        {
            "id": "wechat.list_contacts",
            "kind": "wechat_operation",
            "status": "available",
            "operation": "list_contacts",
        },
        {
            "id": "wechat.list_conversations",
            "kind": "wechat_operation",
            "status": "available",
            "operation": "list_conversations",
        },
        {
            "id": "wechat.open_contact",
            "kind": "wechat_operation",
            "status": "needs_input",
            "operation": "open_contact",
        },
        {
            "id": "wechat.read_visible_messages",
            "kind": "wechat_operation",
            "status": "available",
            "operation": "read_visible_messages",
        },
    ]
    return {
        "appName": _string_value(app.get("name")) or config.app_name,
        "bundleId": _string_value(app.get("bundleId")) or config.bundle_id,
        "title": title,
        "snapshotId": _query_snapshot_id(query),
        "element": element,
        "activeSection": next(
            (str(item["label"]) for item in navigation if item.get("selected") is True),
            None,
        ),
        "navigation": cast(JsonValue, navigation),
        "regions": regions,
        "actionables": cast(JsonValue, actionables),
        "availableActions": cast(JsonValue, available_actions),
    }


def _query_normalization_reason(
    query: Mapping[str, Any],
    *,
    top_nodes: list[dict[str, Any]],
    main_content: Mapping[str, Any] | None,
) -> str:
    if query.get("available") is False:
        return "accessibility_query_missing"
    if not top_nodes:
        return "accessibility_query_empty"
    if main_content is None:
        return "main_content_missing"
    return "accessibility_query_normalized"


def _wechat_environment_from_query(
    config: WeChatDesktopConfig,
    query: Mapping[str, Any],
) -> dict[str, JsonValue]:
    app = (
        cast(Mapping[str, Any], query.get("app"))
        if isinstance(query.get("app"), Mapping)
        else {}
    )
    window = (
        cast(Mapping[str, Any], query.get("window"))
        if isinstance(query.get("window"), Mapping)
        else {}
    )
    return {
        "configuredAppName": config.app_name,
        "configuredBundleId": config.bundle_id,
        "frontmostApp": _string_value(app.get("name")) or config.app_name,
        "frontmostBundleId": _string_value(app.get("bundleId")) or config.bundle_id,
        "windowTitle": _string_value(window.get("title")),
    }


def _element_from_query_node(
    node: Mapping[str, Any],
    *,
    label: str | None = None,
) -> dict[str, JsonValue]:
    element: dict[str, JsonValue] = {
        "axPath": str(node.get("axPath") or "0"),
        "role": str(node.get("role") or "AXUnknown"),
    }
    frame = node.get("frame")
    frame_values = _frame_numbers(frame)
    if frame_values is not None:
        x, y, width, height = frame_values
        element["frame"] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
    node_label = label or _node_label(node)
    if node_label:
        element["label"] = node_label
    if "value" in node:
        value = node.get("value")
        if isinstance(value, str | int | float | bool) or value is None:
            element["value"] = value
    actions = node.get("actions")
    if isinstance(actions, list):
        element["actions"] = [str(item) for item in actions]
    for key in ("enabled", "focused"):
        if isinstance(node.get(key), bool):
            element[key] = node[key]
    return element


def _node_ax_path(node: Mapping[str, Any]) -> str | None:
    value = node.get("axPath") or node.get("path")
    return value if isinstance(value, str) and value.strip() else None


def _utc_now_datetime() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _action_ref_time_bounds() -> tuple[str, str]:
    created_at = _utc_now_datetime()
    expires_at = created_at + timedelta(seconds=_ACTION_REF_TTL_SECONDS)
    return _isoformat_utc(created_at), _isoformat_utc(expires_at)


def _action_ref_from_node(
    node: Mapping[str, Any],
    *,
    action_id: str | None = None,
    kind: str = "ui.press",
    risk: str = "low",
    target_summary: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, JsonValue] | None:
    ax_path = _node_ax_path(node)
    role = str(node.get("role") or "AXUnknown")
    if ax_path is None:
        return None
    if "AXPress" not in _node_actions(node):
        return None
    label = _node_label(node)
    if role == "AXRow" and label is None:
        return None
    target: dict[str, JsonValue] = {
        "axPath": ax_path,
        "role": role,
        "actions": ["AXPress"],
    }
    if label is not None:
        target["label"] = label
    preconditions: dict[str, JsonValue] = {
        "roleIn": [role],
        "actionIn": ["AXPress"],
    }
    if label is not None:
        preconditions["labelIn"] = _label_precondition_values(label)
    if isinstance(node.get("enabled"), bool):
        preconditions["enabled"] = bool(node["enabled"])
    created_at, expires_at = _action_ref_time_bounds()
    action_ref: dict[str, JsonValue] = {
        "schema": "wechat.action_ref.v1",
        "id": action_id or f"ui.{_stable_id(label or ax_path, 0)}.press",
        "kind": kind,
        "preferredMethod": "accessibility_action",
        "target": target,
        "action": "AXPress",
        "preconditions": preconditions,
        "risk": risk,
        "targetSummary": target_summary or f"Press {label or ax_path}",
        "createdAt": created_at,
        "expiresAt": expires_at,
    }
    if snapshot_id is not None:
        action_ref["snapshotId"] = snapshot_id
    selector = _selector_from_node(node)
    if selector is not None:
        action_ref["fallbacks"] = [
            {"method": "selector_click", "selector": selector},
        ]
    return action_ref


def _first_concrete_label(labels: tuple[str, ...]) -> str | None:
    for label in labels:
        if label and not label.startswith("__"):
            return label
    return None


def _window_title_matches_navigation(
    window_title: str | None,
    control: WeChatMappedControl,
) -> bool:
    if window_title is None:
        return False
    expected = {
        label.casefold()
        for label in control.labels
        if label and not label.startswith("__")
    }
    if not expected:
        return False
    normalized_title = window_title.casefold()
    return any(label in normalized_title for label in expected)


def _mapped_control_node_matches(
    node: Mapping[str, Any],
    control: WeChatMappedControl,
) -> bool:
    if str(node.get("role") or "") != control.role:
        return False
    if node.get("enabled") is not True:
        return False
    concrete_labels = {
        label.casefold()
        for label in control.labels
        if label and not label.startswith("__")
    }
    if not concrete_labels:
        return True
    label = _node_label(node)
    return label is not None and label.casefold() in concrete_labels


def _node_center_coordinates(node: Mapping[str, Any]) -> dict[str, JsonValue] | None:
    frame = node.get("frame")
    if not isinstance(frame, Mapping):
        return None
    x = _number_value(frame.get("x"))
    y = _number_value(frame.get("y"))
    width = _number_value(frame.get("width"))
    height = _number_value(frame.get("height"))
    if x is None or y is None or width is None or height is None:
        return None
    if not all(math.isfinite(item) for item in (x, y, width, height)):
        return None
    if width <= 0 or height <= 0:
        return None
    return {
        "x": int(round(x + width / 2)),
        "y": int(round(y + height / 2)),
    }


def _node_frame_within_query_window(
    node: Mapping[str, Any],
    query: ToolObservation,
) -> bool:
    node_frame = _frame_numbers(node.get("frame"))
    payload = _query_payload(query)
    window = payload.get("window")
    window_frame = (
        _frame_numbers(window.get("frame")) if isinstance(window, Mapping) else None
    )
    if node_frame is None or window_frame is None:
        return False
    node_x, node_y, node_width, node_height = node_frame
    window_x, window_y, window_width, window_height = window_frame
    node_right = node_x + node_width
    node_bottom = node_y + node_height
    window_right = window_x + window_width
    window_bottom = window_y + window_height
    node_center_x = node_x + node_width / 2
    node_center_y = node_y + node_height / 2
    tolerance = _MAPPED_NAVIGATION_FRAME_EDGE_TOLERANCE_POINTS
    return (
        window_x < node_center_x < window_right
        and window_y < node_center_y < window_bottom
        and node_x >= window_x - tolerance
        and node_y >= window_y - tolerance
        and node_right <= window_right + tolerance
        and node_bottom <= window_bottom + tolerance
    )


def _query_matches_target_app_window(
    query: ToolObservation,
    config: WeChatDesktopConfig,
) -> bool:
    payload = _query_payload(query)
    if payload.get("available") is not True:
        return False
    app = payload.get("app")
    if not isinstance(app, Mapping):
        return False
    observed_bundle_id = _string_value(app.get("bundleId"))
    observed_name = _string_value(app.get("name"))
    if config.bundle_id is not None:
        if observed_bundle_id != config.bundle_id:
            return False
    elif (
        observed_name is None or observed_name.casefold() != config.app_name.casefold()
    ):
        return False
    window = payload.get("window")
    if not isinstance(window, Mapping):
        return False
    if _string_value(window.get("role")) != "AXWindow":
        return False
    return _frame_numbers(window.get("frame")) is not None


def _frame_numbers(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, Mapping):
        return None
    raw_values = tuple(value.get(key) for key in ("x", "y", "width", "height"))
    if any(
        isinstance(item, bool) or not isinstance(item, int | float)
        for item in raw_values
    ):
        return None
    numeric_values = cast(
        tuple[int | float, int | float, int | float, int | float],
        raw_values,
    )
    x, y, width, height = (float(item) for item in numeric_values)
    if not all(math.isfinite(item) for item in (x, y, width, height)):
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _coordinate_click_disabled(result: ToolObservation) -> bool:
    return result.failure_kind == "coordinate_click_disabled"


def _selector_from_node(node: Mapping[str, Any]) -> dict[str, JsonValue] | None:
    label = _node_label(node)
    role = str(node.get("role") or "")
    if not label or not role:
        return None
    return {"role": role, "name": label}


def _node_actions(node: Mapping[str, Any]) -> set[str]:
    actions = node.get("actions")
    if not isinstance(actions, list):
        return set()
    return {str(item) for item in actions}


def _label_precondition_values(label: str) -> list[JsonValue]:
    values: list[JsonValue] = [label]
    for key, labels in _NAV_QUERY_LABELS.items():
        if label in labels:
            values.extend(item for item in labels if item not in values)
            values.append(key)
            break
    return values


def _stable_id(label: str, fallback_index: int) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "-", label.strip().lower()).strip("-")
    return normalized or f"item-{fallback_index}"


def _node_label(node: Mapping[str, Any]) -> str | None:
    for key in ("description", "title", "placeholder", "value", "label"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _node_selected(node: Mapping[str, Any]) -> bool:
    selected = node.get("selected")
    if isinstance(selected, bool):
        return selected
    value = node.get("value")
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return False


def _frame_area(node: Mapping[str, Any]) -> float:
    frame = node.get("frame")
    if not isinstance(frame, Mapping):
        return 0.0
    width = _number_value(frame.get("width")) or 0.0
    height = _number_value(frame.get("height")) or 0.0
    return width * height


def _selector_element_center_coordinates(element: Any) -> dict[str, JsonValue] | None:
    frame = getattr(element, "frame", None)
    if frame is None:
        return None
    x = getattr(frame, "x", None)
    y = getattr(frame, "y", None)
    width = getattr(frame, "width", None)
    height = getattr(frame, "height", None)
    if (
        not isinstance(x, int | float)
        or not isinstance(y, int | float)
        or not isinstance(width, int | float)
        or not isinstance(height, int | float)
    ):
        return None
    return {
        "x": int(round(float(x) + float(width) / 2)),
        "y": int(round(float(y) + float(height) / 2)),
    }


def _node_from_collection_element(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    ax_path = value.get("axPath")
    if not isinstance(ax_path, str) or not ax_path.strip():
        return None
    role = value.get("role")
    node: dict[str, Any] = {
        "axPath": ax_path.strip(),
        "role": role if isinstance(role, str) and role.strip() else "AXUnknown",
    }
    label = value.get("label")
    if isinstance(label, str) and label.strip():
        node["label"] = label.strip()
    frame = value.get("frame")
    if isinstance(frame, Mapping):
        node["frame"] = {
            "x": _number_value(frame.get("x")) or 0,
            "y": _number_value(frame.get("y")) or 0,
            "width": _number_value(frame.get("width")) or 0,
            "height": _number_value(frame.get("height")) or 0,
        }
    actions = value.get("actions")
    if isinstance(actions, list):
        node["actions"] = [str(action) for action in actions]
    for key in ("enabled", "focused"):
        if isinstance(value.get(key), bool):
            node[key] = value[key]
    return node


def _query_truncated(observation: ToolObservation) -> bool:
    diagnostics = _query_payload(observation).get("diagnostics")
    return bool(isinstance(diagnostics, Mapping) and diagnostics.get("truncated"))


def _public_accessibility_element(
    element: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    for key in (
        "role",
        "roleDescription",
        "name",
        "description",
        "title",
        "focused",
        "frame",
    ):
        value = element.get(key)
        if isinstance(value, str | bool | dict):
            payload[key] = value
    index = element.get("index")
    if isinstance(index, int) and not isinstance(index, bool):
        payload["index"] = index
    return payload


def _is_text_like_accessibility_element(element: dict[str, JsonValue]) -> bool:
    text = _accessibility_element_text(element)
    return any(
        marker in text
        for marker in (
            "text",
            "edit",
            "search",
            "axtextfield",
            "axtextarea",
            "axsearchfield",
            "文本",
            "输入",
            "搜索",
        )
    )


def _accessibility_element_contains(
    element: dict[str, JsonValue],
    markers: tuple[str, ...],
) -> bool:
    text = _accessibility_element_text(element)
    return any(marker.casefold() in text for marker in markers)


def _accessibility_element_text(element: dict[str, JsonValue]) -> str:
    parts: list[str] = []
    for key in ("role", "roleDescription", "name", "description", "title", "value"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts).casefold()


def _focused_text_field_position(
    focused: dict[str, JsonValue],
    accessibility: dict[str, JsonValue],
) -> str | None:
    focused_y = _element_frame_int(focused, "y")
    if focused_y is None:
        return None
    raw_fields = accessibility.get("textFields")
    if not isinstance(raw_fields, list):
        return None
    y_values = [
        y
        for item in raw_fields
        if isinstance(item, dict)
        for y in [_element_frame_int(item, "y")]
        if y is not None
    ]
    if len(y_values) < 2:
        return None
    top = min(y_values)
    bottom = max(y_values)
    if bottom <= top:
        return None
    threshold = max(20, int(round((bottom - top) * 0.25)))
    if focused_y <= top + threshold:
        return "top"
    if focused_y >= bottom - threshold:
        return "bottom"
    return None


def _element_frame_int(element: Mapping[str, JsonValue], key: str) -> int | None:
    frame = element.get("frame")
    if not isinstance(frame, dict):
        return None
    value = frame.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _contact_target_query_issue(
    observation: ToolObservation,
) -> tuple[str, str | None] | None:
    if not observation.success:
        return "failed", None
    payload = _query_payload(observation)
    invalid_reason = _contact_target_query_invalid_reason(payload)
    if invalid_reason is not None:
        return "invalid", invalid_reason
    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, Mapping)
    if diagnostics["truncated"] is True:
        return "truncated", None
    return None


def _contact_target_query_invalid_reason(
    payload: Mapping[str, Any],
) -> str | None:
    if payload.get("schema") != "macos.accessibility.query.v1":
        return "schema_invalid"
    if payload.get("available") is not True:
        return "available_invalid"
    if "status" in payload and payload.get("status") != "ok":
        return "status_invalid"
    if any(key in payload for key in ("failureKind", "failure_kind", "error")):
        return "failure_evidence_conflict"
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return "nodes_invalid"
    if any(not isinstance(node, Mapping) for node in nodes):
        return "node_member_invalid"
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return "diagnostics_invalid"
    if "truncated" not in diagnostics or not isinstance(
        diagnostics.get("truncated"),
        bool,
    ):
        return "truncation_invalid"
    if any(key in diagnostics for key in ("failureKind", "failure_kind")):
        return "diagnostics_failure_conflict"
    if "returnedNodes" in diagnostics:
        returned_nodes = diagnostics.get("returnedNodes")
        if (
            not isinstance(returned_nodes, int)
            or isinstance(returned_nodes, bool)
            or returned_nodes != len(nodes)
        ):
            return "returned_nodes_invalid"
    return None
