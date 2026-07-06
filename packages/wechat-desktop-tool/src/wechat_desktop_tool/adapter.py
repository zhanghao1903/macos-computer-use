"""Adapter entrypoints for compatible app-control clients."""

from __future__ import annotations

from app_control_protocol import AppControlClient

from .models import WeChatDesktopConfig
from .tool import WeChatDesktopTool


def build_wechat_tool(
    app_control: AppControlClient,
    config: WeChatDesktopConfig | None = None,
) -> WeChatDesktopTool:
    """Build a WeChatDesktopTool from any compatible app-control client."""

    return WeChatDesktopTool(app_control=app_control, config=config)


__all__ = [
    "AppControlClient",
    "WeChatDesktopConfig",
    "WeChatDesktopTool",
    "build_wechat_tool",
]
