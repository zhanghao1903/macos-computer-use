from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app_control_protocol import (
    ToolCommand,
    ToolError,
    ToolObservation,
    ToolStatus,
)


def failed_accessibility_action_response() -> ToolObservation:
    transport = {
        "mode": "worker",
        "fallback": False,
        "requestDispatched": True,
    }
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="accessibility_action_failed",
            message="AXUIElementPerformAction returned error: -25204",
            retryable=False,
        ),
        summary="AXUIElementPerformAction returned error: -25204",
        observation={
            "actionAttempted": True,
            "actionEffect": "unknown",
            "nativeErrorCode": -25204,
            "metadata": {
                "action_attempted": True,
                "action_effect": "unknown",
                "native_error_code": -25204,
                "accessibility_action_transport": transport,
            },
            "accessibilityAction": {
                "failureKind": "accessibility_action_failed",
                "message": "AXUIElementPerformAction returned error: -25204",
                "actionAttempted": True,
                "actionEffect": "unknown",
                "nativeErrorCode": -25204,
                "diagnostics": {"transport": transport},
            },
        },
    )


def definite_unsupported_accessibility_action_response(
    *,
    action: str = "AXPress",
) -> ToolObservation:
    native_error_code = -25205 if action == "AXSetFocus" else -25206
    method = (
        "AXUIElementSetAttributeValue"
        if action == "AXSetFocus"
        else "AXUIElementPerformAction"
    )
    transport = {
        "mode": "worker",
        "fallback": False,
        "requestDispatched": True,
    }
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="accessibility_action_unsupported",
            message=f"{method} returned unsupported error: {native_error_code}",
            retryable=False,
        ),
        summary=f"{method} returned unsupported error: {native_error_code}",
        observation={
            "actionAttempted": True,
            "actionEffect": "none",
            "nativeErrorCode": native_error_code,
            "metadata": {
                "action_attempted": True,
                "action_effect": "none",
                "native_error_code": native_error_code,
                "accessibility_action_transport": transport,
            },
            "accessibilityAction": {
                "failureKind": "accessibility_action_unsupported",
                "message": (
                    f"{method} returned unsupported error: {native_error_code}"
                ),
                "action": action,
                "actionAttempted": True,
                "actionEffect": "none",
                "nativeErrorCode": native_error_code,
                "diagnostics": {"transport": transport},
            },
        },
    )


def predispatch_accessibility_action_response() -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.TIMEOUT,
        error=ToolError(
            failure_kind="accessibility_action_timeout",
            message="Timed out before dispatch.",
            retryable=True,
        ),
        summary="Timed out before dispatch.",
        observation={
            "metadata": {
                "accessibility_action_transport": {
                    "mode": "worker",
                    "fallback": False,
                    "requestDispatched": False,
                }
            }
        },
    )


def accessibility_action_failure_with_observation(
    observation: dict[str, Any],
    *,
    failure_kind: str = "unsupported_operation",
    retryable: bool = False,
    status: ToolStatus = ToolStatus.FAILED,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=status,
        error=ToolError(
            failure_kind=failure_kind,
            message=failure_kind,
            retryable=retryable,
        ),
        summary=failure_kind,
        observation=observation,
    )


def contradictory_predispatch_action_response() -> ToolObservation:
    return accessibility_action_failure_with_observation(
        {
            "actionAttempted": False,
            "actionEffect": "performed",
            "nativeErrorCode": -25204,
            "metadata": {
                "accessibility_action_transport": {
                    "requestDispatched": False,
                }
            },
        },
        failure_kind="accessibility_action_timeout",
        retryable=True,
        status=ToolStatus.TIMEOUT,
    )


def command_trace(commands: Sequence[ToolCommand]) -> list[dict[str, Any]]:
    """Return the behavior-bearing fields of child commands in dispatch order."""

    return [
        {
            "commandId": command.command_id,
            "tool": command.tool,
            "operation": command.operation,
            "input": dict(command.input),
            "timeoutMs": command.timeout_ms,
            "metadata": dict(command.metadata),
        }
        for command in commands
    ]


def canonicalize_timing(value: Any) -> Any:
    """Normalize only wall-clock values while retaining the complete shape."""

    if isinstance(value, Mapping):
        normalized = {
            str(key): canonicalize_timing(item) for key, item in value.items()
        }
        timing = normalized.get("timing")
        if isinstance(timing, Mapping):
            normalized["timing"] = {
                "startedAt": "<startedAt>",
                "durationMs": "<durationMs>",
            }
        return normalized
    if isinstance(value, list):
        return [canonicalize_timing(item) for item in value]
    return value
