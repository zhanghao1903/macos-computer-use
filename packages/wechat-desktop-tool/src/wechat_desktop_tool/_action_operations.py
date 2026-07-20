"""WeChat Accessibility action execution without domain workflow semantics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._action_safety import (
    _action_ref_expiry_failure,
    _action_ref_expiry_value,
    _action_ref_identity_failure,
    _execute_action_failure_kind,
    _selector_fallback_from_action_ref,
    _should_fallback_from_accessibility_action,
    _should_try_coordinate_click_after_accessibility_action,
)
from ._diagnostics import (
    _action_ref_input,
    _executed_action_method,
    _failure,
    _optional_string_from_mapping,
)
from ._query_mapping import (
    _action_ref_from_node,
    _coordinate_click_disabled,
    _node_actions,
    _node_center_coordinates,
    _node_label,
)
from ._runtime import (
    _from_app_control_failure,
    _PhaseEventCollector,
    _safe_app_control_observation,
    _safe_executed_action_result,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL


def _execute_action(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    action_ref = _action_ref_input(command)
    action_id = _optional_string_from_mapping(action_ref, "id") or "unknown"
    evidence: dict[str, JsonValue] = {}
    result = _execute_action_ref(
        runtime,
        command,
        action_ref,
        phase="execute_action",
        evidence=evidence,
        phase_events=phase_events,
    )
    if not result.success:
        if result.tool == WECHAT_TOOL:
            return result
        return _from_app_control_failure(
            command,
            _execute_action_failure_kind(result),
            result,
            evidence=evidence,
        )
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Executed WeChat action.",
        observation={
            "schema": "wechat.execute_action.v1",
            "status": "ok",
            "actionId": action_id,
            "method": _executed_action_method(action_ref, result),
            "result": _safe_executed_action_result(result),
        },
        evidence=evidence,
    )


def _click_node_phase(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    node: Mapping[str, Any],
    *,
    phase: str,
    evidence: dict[str, JsonValue],
    snapshot_id: str | None = None,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    role = str(node.get("role") or "")
    node_label = _node_label(node)
    if role == "AXRow" and node_label is None:
        return _failure(
            command,
            status=ToolStatus.FAILED,
            failure_kind="wechat_action_target_unverified",
            message="Could not verify the identity of the WeChat row target.",
            recovery_hint="Refresh the WeChat list and retry the semantic action.",
            retryable=True,
            evidence=evidence,
        )
    if role == "AXRow" and "AXPress" not in _node_actions(node):
        coordinates = _node_center_coordinates(node)
        if coordinates is not None:
            coordinate_phase = f"{phase}:coordinate"
            coordinate_result = runtime._app_control_command(
                command,
                phase=coordinate_phase,
                operation="click",
                input=runtime._target_app_input(coordinates=coordinates),
                command_metadata={
                    "coordinateSource": "accessibility_frame",
                },
                phase_events=phase_events,
            )
            evidence[coordinate_phase] = _safe_app_control_observation(
                coordinate_result
            )
            if coordinate_result.success:
                return coordinate_result
            if not _coordinate_click_disabled(coordinate_result):
                return coordinate_result
    action_ref = _action_ref_from_node(node, snapshot_id=snapshot_id)
    if action_ref is not None:
        expected_action = (
            _optional_string_from_mapping(action_ref, "action") or "AXPress"
        )
        result = _execute_action_ref(
            runtime,
            command,
            action_ref,
            phase=phase,
            evidence=evidence,
            phase_events=phase_events,
        )
        if result.success:
            return result
        if _should_try_coordinate_click_after_accessibility_action(
            result,
            expected_action=expected_action,
        ):
            coordinates = _node_center_coordinates(node)
            if coordinates is not None:
                coordinate_phase = f"{phase}:coordinate_fallback"
                coordinate_result = runtime._app_control_command(
                    command,
                    phase=coordinate_phase,
                    operation="click",
                    input=runtime._target_app_input(coordinates=coordinates),
                    command_metadata={
                        "coordinateSource": "accessibility_frame",
                    },
                    phase_events=phase_events,
                )
                evidence[coordinate_phase] = _safe_app_control_observation(
                    coordinate_result
                )
                if coordinate_result.success:
                    return coordinate_result
                if not _coordinate_click_disabled(coordinate_result):
                    return coordinate_result
        if not _should_fallback_from_accessibility_action(
            result,
            expected_action=expected_action,
        ):
            return result

    input_payload = runtime._target_app_input()
    if node_label is not None:
        input_payload["selector"] = {
            "role": role,
            "name": node_label,
        }
    else:
        input_payload["selector"] = {
            "role": role,
            "index": 1,
        }
    result = runtime._app_control_command(
        command,
        phase=phase,
        operation="click",
        input=input_payload,
        phase_events=phase_events,
    )
    evidence[phase] = _safe_app_control_observation(result)
    return result


def _execute_action_ref(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    action_ref: Mapping[str, Any],
    *,
    phase: str,
    evidence: dict[str, JsonValue],
    timeout_ms: int | None = None,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    expiry_failure = _action_ref_expiry_failure(command, action_ref)
    if expiry_failure is not None:
        evidence[phase] = {
            "failureKind": "action_ref_expired",
            "actionRefId": _optional_string_from_mapping(action_ref, "id"),
            "expiresAt": _action_ref_expiry_value(action_ref),
        }
        return expiry_failure
    identity_failure = _action_ref_identity_failure(command, action_ref)
    if identity_failure is not None:
        evidence[phase] = {
            "failureKind": "action_ref_identity_unverified",
            "actionRefId": _optional_string_from_mapping(action_ref, "id"),
        }
        return identity_failure
    input_payload = runtime._accessibility_action_input(action_ref)
    expected_action = str(input_payload["action"])
    result = runtime._app_control_command(
        command,
        phase=phase,
        operation="accessibility_action",
        input=input_payload,
        timeout_ms=timeout_ms,
        phase_events=phase_events,
    )
    evidence[phase] = _safe_app_control_observation(result)
    if result.success or not _should_fallback_from_accessibility_action(
        result,
        expected_action=expected_action,
    ):
        return result
    selector = _selector_fallback_from_action_ref(action_ref)
    if selector is None:
        return result
    fallback_result = runtime._app_control_command(
        command,
        phase=f"{phase}:selector_fallback",
        operation="click",
        input=runtime._target_app_input(selector=selector),
        timeout_ms=timeout_ms,
        phase_events=phase_events,
    )
    evidence[f"{phase}:selector_fallback"] = _safe_app_control_observation(
        fallback_result
    )
    return fallback_result
