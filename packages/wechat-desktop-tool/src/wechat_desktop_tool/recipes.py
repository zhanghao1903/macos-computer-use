"""Convenience recipes built from WeChatDesktopTool primitives."""

from __future__ import annotations

from app_control_protocol import ToolObservation

from .tool import WeChatDesktopTool


def send_message(
    tool: WeChatDesktopTool,
    *,
    contact: str,
    message: str,
    verify_after_submit: bool = False,
    verify_limit: int = 20,
) -> ToolObservation:
    """Run the package-owned send-message convenience flow."""

    return tool.send_message(
        contact=contact,
        message=message,
        verify_after_submit=verify_after_submit,
        verify_limit=verify_limit,
    )


__all__ = [
    "send_message",
]
