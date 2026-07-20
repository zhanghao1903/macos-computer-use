"""WeChat control-map navigation and bounded collection access."""

from __future__ import annotations

from typing import Any

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._action_operations import _execute_action_ref
from ._action_safety import (
    _should_try_coordinate_click_after_accessibility_action,
)
from ._diagnostics import _failure, _optional_string_from_mapping
from ._query_mapping import (
    _action_ref_from_node,
    _contact_target_query_issue,
    _coordinate_click_disabled,
    _first_concrete_label,
    _mapped_control_node_matches,
    _node_actions,
    _node_center_coordinates,
    _node_frame_within_query_window,
    _node_selected,
    _query_matches_target_app_window,
    _query_nodes,
    _query_payload,
    _query_snapshot_id,
    _window_title_matches_navigation,
)
from ._row_parsing import _conversation_rows_from_cells
from ._runtime import (
    _PhaseEventCollector,
    _safe_app_control_observation,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL
from .control_map import WeChatMappedCollection, WeChatMappedControl


_MAPPED_NAVIGATION_ACTION_TIMEOUT_MS = 2_000

_MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS = 800

_MAPPED_NAVIGATION_CLICK_TIMEOUT_MS = 1_200

_MAPPED_CONVERSATION_TARGET_QUERY_TIMEOUT_MS = 450


def _press_mapped_navigation(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    navigation_key: str,
    *,
    active_window_title: str | None = None,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    control = runtime.control_map.navigation.get(navigation_key)
    if control is None:
        return None
    if _window_title_matches_navigation(active_window_title, control):
        phase = f"control_map_switch_{navigation_key}_skipped"
        skipped = ToolObservation.ok(
            command_id=f"{command.command_id}:{phase}",
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary=f"WeChat is already on {navigation_key}.",
            observation={
                "schema": "wechat.control_map.navigation.v1",
                "status": "already_selected",
                "navigation": navigation_key,
                "control": control.control_id,
                "source": {
                    "mode": "control_map",
                    "mapId": runtime.control_map.map_id,
                    "mapVersion": runtime.control_map.map_version,
                },
            },
        )
        evidence[phase] = _safe_app_control_observation(skipped)
        return skipped
    return _execute_mapped_control(
        runtime,
        command,
        control,
        action_id=f"nav.{navigation_key}.press",
        target_summary=f"Switch to {navigation_key}",
        phase=f"control_map_switch_{navigation_key}",
        evidence=evidence,
        phase_events=phase_events,
    )


def _execute_mapped_control(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    control: WeChatMappedControl,
    *,
    action_id: str,
    target_summary: str,
    phase: str,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    for index, ax_path in enumerate(control.ax_paths):
        query_phase = f"{phase}:target_{index}"
        target_query = runtime._app_control_command(
            command,
            phase=query_phase,
            operation="accessibility_query",
            input=runtime._accessibility_query_input(
                root={"kind": "axPath", "axPath": ax_path},
                query={
                    "scope": "self",
                    "maxDepth": 0,
                    "limit": 1,
                    "timeBudgetMs": _MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
                    "attributes": [
                        "AXRole",
                        "AXDescription",
                        "AXTitle",
                        "AXValue",
                        "AXEnabled",
                        "AXSelected",
                        "AXFrame",
                        "AXPosition",
                        "AXSize",
                    ],
                    "actions": True,
                    "includeChildrenCount": False,
                    "match": {"roleIn": [control.role]},
                },
            ),
            timeout_ms=_MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
            phase_events=phase_events,
        )
        evidence[query_phase] = _safe_app_control_observation(target_query)
        if not target_query.success:
            continue
        if not _query_matches_target_app_window(target_query, runtime.config):
            continue
        nodes = _query_nodes(target_query)
        if not nodes:
            continue
        target_node = nodes[0]
        if not _mapped_control_node_matches(target_node, control):
            continue
        if not _node_frame_within_query_window(target_node, target_query):
            continue
        if _node_selected(target_node):
            selected_phase = f"{phase}:already_selected_{index}"
            selected = ToolObservation.ok(
                command_id=f"{command.command_id}:{selected_phase}",
                tool=WECHAT_TOOL,
                operation=command.operation,
                summary=(
                    f"WeChat navigation control {control.control_id} "
                    "is already selected."
                ),
                observation={
                    "schema": "wechat.control_map.navigation.v1",
                    "status": "already_selected",
                    "control": control.control_id,
                    "axPath": ax_path,
                },
            )
            evidence[selected_phase] = _safe_app_control_observation(selected)
            return selected

        if control.action in _node_actions(target_node):
            action_ref = _action_ref_from_node(
                target_node,
                action_id=action_id,
                kind=control.kind,
                risk=control.risk,
                target_summary=target_summary,
                snapshot_id=_query_snapshot_id(_query_payload(target_query)),
            )
            if action_ref is not None:
                action_result = _execute_action_ref(
                    runtime,
                    command,
                    action_ref,
                    phase=f"{phase}:action_{index}",
                    evidence=evidence,
                    timeout_ms=_MAPPED_NAVIGATION_ACTION_TIMEOUT_MS,
                    phase_events=phase_events,
                )
                if action_result.success:
                    return _verify_mapped_navigation_postcondition(
                        runtime,
                        command,
                        control,
                        ax_path=ax_path,
                        phase=f"{phase}:verify_{index}",
                        evidence=evidence,
                        phase_events=phase_events,
                    )
                if not _should_try_coordinate_click_after_accessibility_action(
                    action_result,
                    expected_action=(
                        _optional_string_from_mapping(action_ref, "action")
                        or control.action
                    ),
                ):
                    return action_result

        coordinates = _node_center_coordinates(target_node)
        if coordinates is None:
            continue
        coordinate_phase = f"{phase}:coordinate_{index}"
        coordinate_result = runtime._app_control_command(
            command,
            phase=coordinate_phase,
            operation="click",
            input=runtime._target_app_input(coordinates=coordinates),
            timeout_ms=_MAPPED_NAVIGATION_CLICK_TIMEOUT_MS,
            command_metadata={
                "coordinateSource": "accessibility_frame",
            },
            phase_events=phase_events,
        )
        evidence[coordinate_phase] = _safe_app_control_observation(coordinate_result)
        if coordinate_result.success:
            return _verify_mapped_navigation_postcondition(
                runtime,
                command,
                control,
                ax_path=ax_path,
                phase=f"{phase}:verify_{index}",
                evidence=evidence,
                phase_events=phase_events,
            )
        if not _coordinate_click_disabled(coordinate_result):
            return coordinate_result

    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_navigation_target_unverified",
        message=(
            "Could not verify a current Accessibility target for "
            f"WeChat navigation control {control.control_id}."
        ),
        recovery_hint="Refresh the WeChat window and retry navigation.",
        retryable=True,
        evidence=evidence,
    )


def _verify_mapped_navigation_postcondition(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    control: WeChatMappedControl,
    *,
    ax_path: str,
    phase: str,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    verification = runtime._app_control_command(
        command,
        phase=phase,
        operation="accessibility_query",
        input=runtime._accessibility_query_input(
            root={"kind": "axPath", "axPath": ax_path},
            query={
                "scope": "self",
                "maxDepth": 0,
                "limit": 1,
                "timeBudgetMs": _MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
                "attributes": [
                    "AXRole",
                    "AXDescription",
                    "AXTitle",
                    "AXValue",
                    "AXEnabled",
                    "AXSelected",
                ],
                "actions": False,
                "includeChildrenCount": False,
                "match": {"roleIn": [control.role]},
            },
        ),
        timeout_ms=_MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
        phase_events=phase_events,
    )
    evidence[phase] = _safe_app_control_observation(verification)
    nodes = _query_nodes(verification) if verification.success else []
    if (
        _query_matches_target_app_window(
            verification,
            runtime.config,
        )
        and nodes
        and _mapped_control_node_matches(
            nodes[0],
            control,
        )
        and _node_selected(nodes[0])
    ):
        return ToolObservation.ok(
            command_id=f"{command.command_id}:{phase}",
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary=f"Selected WeChat navigation control {control.control_id}.",
            observation={
                "schema": "wechat.control_map.navigation.v1",
                "status": "selected",
                "control": control.control_id,
                "axPath": ax_path,
            },
            evidence=evidence,
        )
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_navigation_postcondition_failed",
        message=(
            f"WeChat navigation control {control.control_id} is not "
            "selected after the action."
        ),
        recovery_hint="Restore the expected WeChat view and retry.",
        retryable=True,
        evidence=evidence,
    )


def _query_mapped_collection(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    collection_id: str,
    *,
    semantic_limit: int,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> tuple[ToolObservation, WeChatMappedCollection, list[dict[str, Any]]] | None:
    collection = runtime.control_map.collections.get(collection_id)
    if collection is None:
        return None
    query_limit = max(
        collection.minimum_limit,
        semantic_limit * collection.limit_multiplier,
    )
    for index, root_ax_path in enumerate(collection.root_ax_paths):
        result = runtime._query_accessibility_nodes(
            command,
            root_node={"axPath": root_ax_path},
            phase=f"control_map_{collection_id}_{index}",
            scope="descendants",
            max_depth=collection.max_depth,
            role_in=list(collection.roles),
            limit=query_limit,
            time_budget_ms=collection.time_budget_ms,
            attributes=list(collection.attributes) or None,
            actions=collection.actions,
            root_resolver=collection.root_resolvers.get(root_ax_path),
            prefer_visible_rows=collection.prefer_visible_rows,
            evidence=evidence,
            phase_events=phase_events,
        )
        if not result.success:
            continue
        nodes = _query_nodes(result)
        if nodes:
            return result, collection, nodes
    return None


def _query_mapped_conversation_target(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    contact: str,
    *,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> tuple[ToolObservation, WeChatMappedCollection, list[dict[str, Any]]] | None:
    collection = runtime.control_map.collections.get("conversations")
    if collection is None:
        return None
    successful_query: (
        tuple[
            ToolObservation,
            WeChatMappedCollection,
            list[dict[str, Any]],
        ]
        | None
    ) = None
    for index, root_ax_path in enumerate(collection.root_ax_paths):
        result = runtime._query_accessibility_nodes(
            command,
            root_node={"axPath": root_ax_path},
            phase=f"control_map_conversation_target_{index}",
            scope="descendants",
            max_depth=2,
            role_in=["AXCell"],
            limit=2,
            time_budget_ms=min(
                collection.time_budget_ms,
                _MAPPED_CONVERSATION_TARGET_QUERY_TIMEOUT_MS,
            ),
            attributes=[
                "AXRole",
                "AXDescription",
                "AXPosition",
                "AXSize",
                "AXFrame",
            ],
            actions=False,
            match={"descriptionContains": f"{contact},"},
            prefer_visible_rows=True,
            evidence=evidence,
            phase_events=phase_events,
        )
        query_issue = _contact_target_query_issue(result)
        if (
            query_issue is not None
            and query_issue[0] == "failed"
            and result.failure_kind == "accessibility_query_root_not_found"
        ):
            continue
        if query_issue is not None:
            return result, collection, []
        rows = _conversation_rows_from_cells(_query_nodes(result))
        if rows:
            return result, collection, rows
        successful_query = (result, collection, [])
    return successful_query


def _mapped_region_node(
    runtime: WeChatToolRuntime,
    region_id: str,
    *,
    reference_ax_path: str | None = None,
) -> dict[str, Any] | None:
    region = runtime.control_map.regions.get(region_id)
    if region is None or not region.ax_paths:
        return None
    ax_path = region.ax_paths[0]
    if reference_ax_path is not None:
        reference_root = "/".join(reference_ax_path.split("/")[:2])
        ax_path = next(
            (
                candidate
                for candidate in region.ax_paths
                if "/".join(candidate.split("/")[:2]) == reference_root
            ),
            ax_path,
        )
    node: dict[str, Any] = {
        "axPath": ax_path,
        "role": region.role,
    }
    label = _first_concrete_label(region.labels)
    if label is not None:
        node["label"] = label
    return node
