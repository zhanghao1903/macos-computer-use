"""Observation helper models for WeChat Desktop semantic operations."""

from __future__ import annotations

from app_control_protocol import ToolObservation

from .models import WeChatVisibleMessage, wechat_message_hash

__all__ = [
    "ToolObservation",
    "WeChatVisibleMessage",
    "wechat_message_hash",
]
