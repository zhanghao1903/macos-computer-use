"""Typed models for WeChat Desktop semantic operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from app_control_protocol import AppControlConfig

WeChatOperation = Literal[
    "open_wechat",
    "focus_contact",
    "observe_current_chat",
    "read_visible_messages",
    "draft_message",
    "submit_draft",
    "send_message",
]


@dataclass(frozen=True)
class WeChatDesktopConfig:
    app_name: str = "WeChat"
    bundle_id: str | None = "com.tencent.xinWeChat"
    app_control_tool: str = "macos.computer_use"
    search_hotkey: tuple[str, ...] = ("Command", "F")
    search_clear_hotkey: tuple[str, ...] = ("Command", "A")
    clear_key: str = "Delete"
    submit_key: str = "Return"
    default_timeout_ms: int = 30_000
    max_message_chars: int = 2_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_name", _non_empty(self.app_name, "app_name"))
        if self.bundle_id is not None:
            object.__setattr__(
                self,
                "bundle_id",
                _non_empty(self.bundle_id, "bundle_id"),
            )
        object.__setattr__(
            self,
            "app_control_tool",
            _non_empty(self.app_control_tool, "app_control_tool"),
        )
        object.__setattr__(
            self,
            "search_hotkey",
            _string_tuple(self.search_hotkey, "search_hotkey"),
        )
        object.__setattr__(
            self,
            "search_clear_hotkey",
            _string_tuple(self.search_clear_hotkey, "search_clear_hotkey"),
        )
        object.__setattr__(
            self,
            "clear_key",
            _non_empty(self.clear_key, "clear_key"),
        )
        object.__setattr__(
            self,
            "submit_key",
            _non_empty(self.submit_key, "submit_key"),
        )
        if self.default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms must be positive")
        if self.max_message_chars <= 0:
            raise ValueError("max_message_chars must be positive")

    @classmethod
    def from_app_control_config(
        cls,
        config: "AppControlConfig | Mapping[str, Any] | str | Path | None" = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> "WeChatDesktopConfig":
        app_config = _load_app_control_config(config, env=env)
        wechat = app_config.wechat
        return cls(
            app_name=wechat.app_name,
            bundle_id=wechat.bundle_id,
            app_control_tool=wechat.app_control_tool,
            search_hotkey=wechat.search_hotkey,
            search_clear_hotkey=wechat.search_clear_hotkey,
            clear_key=wechat.clear_key,
            submit_key=wechat.submit_key,
            default_timeout_ms=wechat.default_timeout_ms,
            max_message_chars=wechat.max_message_chars,
        )


@dataclass(frozen=True)
class WeChatVisibleMessage:
    text: str
    direction: str = "unknown"
    visible_timestamp: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _non_empty(self.text, "text"))
        object.__setattr__(
            self,
            "direction",
            _non_empty(self.direction, "direction"),
        )

    def to_dict(self) -> dict[str, str]:
        payload = {
            "direction": self.direction,
            "text": self.text,
        }
        if self.visible_timestamp is not None:
            payload["visibleTimestamp"] = self.visible_timestamp
        return payload


def wechat_message_hash(message: str) -> str:
    return "sha256:" + sha256(message.encode("utf-8")).hexdigest()


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple | list):
        raise TypeError(f"{field_name} must be a string sequence")
    items = tuple(_non_empty(item, field_name) for item in value)
    if not items:
        raise ValueError(f"{field_name} must not be empty")
    return items


def _load_app_control_config(
    config: "AppControlConfig | Mapping[str, Any] | str | Path | None",
    *,
    env: Mapping[str, str] | None,
) -> "AppControlConfig":
    from app_control_protocol import AppControlConfig, load_app_control_config

    if config is None or isinstance(config, str | Path):
        return load_app_control_config(config, env=env)
    if isinstance(config, AppControlConfig):
        return config
    if isinstance(config, Mapping):
        return AppControlConfig.from_dict(config)
    raise TypeError("config must be an AppControlConfig, mapping, path, or None")
