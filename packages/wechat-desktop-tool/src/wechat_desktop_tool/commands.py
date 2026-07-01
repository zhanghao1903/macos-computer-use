"""Command builders for WeChat Desktop protocol operations."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from app_control_protocol import ToolCommand
from app_control_protocol.json_types import JsonValue

from .models import WeChatOperation

WECHAT_TOOL = "wechat.desktop"


def wechat_command(
    operation: WeChatOperation,
    input: Mapping[str, JsonValue] | None = None,
    *,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    """Build a WeChat command envelope without executing it."""

    return ToolCommand(
        command_id=command_id or f"wechat-{uuid4().hex}",
        tool=WECHAT_TOOL,
        operation=operation,
        input=dict(input or {}),
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=dict(metadata or {}),
    )


def open_wechat_command(
    *,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "open_wechat",
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def inspect_window_command(
    *,
    include_raw: bool = False,
    include_actionables: bool = True,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "inspect_window",
        {
            "includeRaw": include_raw,
            "includeActionables": include_actionables,
        },
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def focus_contact_command(
    contact: str,
    *,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "focus_contact",
        {"contact": contact},
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def observe_current_chat_command(
    *,
    include_visible_messages: bool = True,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "observe_current_chat",
        {"includeVisibleMessages": include_visible_messages},
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def read_visible_messages_command(
    *,
    limit: int = 20,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "read_visible_messages",
        {"limit": limit},
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def draft_message_command(
    message: str,
    *,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "draft_message",
        {"message": message},
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def submit_draft_command(
    *,
    method: str = "keyboard_return",
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "submit_draft",
        {"method": method},
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def send_message_command(
    *,
    contact: str,
    message: str,
    verify_after_submit: bool = False,
    verify_limit: int = 20,
    command_id: str | None = None,
    timeout_ms: int | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
) -> ToolCommand:
    return wechat_command(
        "send_message",
        {
            "contact": contact,
            "message": message,
            "verifyAfterSubmit": verify_after_submit,
            "verifyLimit": verify_limit,
        },
        command_id=command_id,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )
