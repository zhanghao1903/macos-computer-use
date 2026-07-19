from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app_control_protocol import ToolCommand


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
