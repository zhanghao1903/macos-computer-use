"""Command builders and execution seam for macOS integrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import subprocess
from uuid import uuid4
from typing import Protocol

from app_control_protocol import ToolCommand
from app_control_protocol.json_types import JsonValue, to_json_value

from .models import ComputerUseOperation

COMPUTER_USE_TOOL = "macos.computer_use"


def computer_use_command(
    operation: ComputerUseOperation | str,
    input: Mapping[str, JsonValue] | None = None,
    *,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    """Build a macOS computer-use command envelope without executing it."""

    return ToolCommand(
        command_id=command_id or f"computer-use-{uuid4().hex}",
        tool=COMPUTER_USE_TOOL,
        operation=_operation_value(operation),
        input=dict(input or {}),
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=dict(metadata or {}),
    )


def readiness_command(
    *,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return computer_use_command(
        ComputerUseOperation.READINESS,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def observe_command(
    *,
    target_app: str | None = None,
    bundle_id: str | None = None,
    include_visible_text: bool | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {}
    if target_app is not None:
        payload["targetApp"] = target_app
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    if include_visible_text is not None:
        payload["includeVisibleText"] = include_visible_text
    return computer_use_command(
        ComputerUseOperation.OBSERVE,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def open_app_command(
    app: str,
    *,
    bundle_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {"app": app}
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    return computer_use_command(
        ComputerUseOperation.OPEN_APP,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def focus_app_command(
    app: str,
    *,
    bundle_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {"app": app}
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    return computer_use_command(
        ComputerUseOperation.FOCUS_APP,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def click_command(
    target: str | None = None,
    *,
    target_app: str | None = None,
    bundle_id: str | None = None,
    selector: Mapping[str, JsonValue] | None = None,
    coordinates: Sequence[int] | Mapping[str, JsonValue] | None = None,
    snapshot_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {}
    if target is not None:
        payload["target"] = target
    if target_app is not None:
        payload["targetApp"] = target_app
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    if selector is not None:
        selector_value = to_json_value(selector)
        if not isinstance(selector_value, dict):
            raise TypeError("selector must be a JSON object")
        payload["selector"] = selector_value
    if coordinates is not None:
        coordinate_value = to_json_value(coordinates)
        if not isinstance(coordinate_value, list | dict):
            raise TypeError("coordinates must be a JSON list or object")
        payload["coordinates"] = coordinate_value
    if snapshot_id is not None:
        payload["snapshotId"] = snapshot_id
    return computer_use_command(
        ComputerUseOperation.CLICK,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def click_accessibility_command(
    selector: Mapping[str, JsonValue],
    *,
    target_app: str,
    bundle_id: str | None = None,
    snapshot_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return click_command(
        target_app=target_app,
        bundle_id=bundle_id,
        selector=selector,
        snapshot_id=snapshot_id,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def click_coordinate_command(
    x: int,
    y: int,
    *,
    target_app: str | None = None,
    bundle_id: str | None = None,
    snapshot_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return click_command(
        target_app=target_app,
        bundle_id=bundle_id,
        coordinates=[x, y],
        snapshot_id=snapshot_id,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def type_text_command(
    text: str,
    *,
    target_app: str | None = None,
    bundle_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {"text": text}
    if target_app is not None:
        payload["targetApp"] = target_app
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    return computer_use_command(
        ComputerUseOperation.TYPE_TEXT,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def press_key_command(
    key: str,
    *,
    target_app: str | None = None,
    bundle_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {"key": key}
    if target_app is not None:
        payload["targetApp"] = target_app
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    return computer_use_command(
        ComputerUseOperation.PRESS_KEY,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def hotkey_command(
    keys: Sequence[str],
    *,
    target_app: str | None = None,
    bundle_id: str | None = None,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    payload: dict[str, JsonValue] = {"keys": list(keys)}
    if target_app is not None:
        payload["targetApp"] = target_app
    if bundle_id is not None:
        payload["bundleId"] = bundle_id
    return computer_use_command(
        ComputerUseOperation.HOTKEY,
        payload,
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def wait_command(
    *,
    seconds: float = 1.0,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return computer_use_command(
        ComputerUseOperation.WAIT,
        {"seconds": seconds},
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def _operation_value(operation: ComputerUseOperation | str) -> str:
    if isinstance(operation, ComputerUseOperation):
        return operation.value
    return str(operation)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CommandRunner(Protocol):
    def run(self, args: Sequence[str], *, timeout: float) -> CommandResult:
        """Run a command and return sanitized stdout/stderr."""


class SubprocessCommandRunner:
    def run(self, args: Sequence[str], *, timeout: float) -> CommandResult:
        try:
            completed = subprocess.run(
                list(args),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                returncode=124,
                stdout=_timeout_output(exc.stdout),
                stderr=_timeout_output(exc.stderr),
                timed_out=True,
            )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
