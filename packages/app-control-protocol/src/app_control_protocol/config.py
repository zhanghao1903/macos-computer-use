"""Developer-editable configuration models for app-control tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import os
from pathlib import Path
import tomllib
from typing import Any


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "info"
    redact_text: bool = True
    json: bool = False
    event_sink: str = "stderr"
    raw_data_log_path: str | None = None

    def __post_init__(self) -> None:
        level = self.level.strip().lower()
        if level not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError(f"unsupported logging level: {self.level}")
        object.__setattr__(self, "level", level)
        object.__setattr__(
            self,
            "event_sink",
            _non_empty(self.event_sink, "event_sink"),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LoggingConfig":
        return cls(
            level=_string(payload.get("level"), default="info"),
            redact_text=_bool(payload.get("redact_text"), default=True),
            json=_bool(payload.get("json"), default=False),
            event_sink=_string(payload.get("event_sink"), default="stderr"),
            raw_data_log_path=_optional_string(payload.get("raw_data_log_path")),
        )


@dataclass(frozen=True)
class ComputerUseConfig:
    backend: str = "direct"
    allowed_apps: tuple[str, ...] = ()
    allowed_app_bundle_ids: Mapping[str, str] = field(default_factory=dict)
    allow_coordinate_click: bool = False
    screen_recording_required: bool = False
    timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend", _non_empty(self.backend, "backend"))
        object.__setattr__(
            self,
            "allowed_apps",
            tuple(app.strip() for app in self.allowed_apps if app.strip()),
        )
        object.__setattr__(
            self,
            "allowed_app_bundle_ids",
            _string_mapping(self.allowed_app_bundle_ids),
        )
        if self.timeout_ms <= 0:
            raise ValueError("computer_use.timeout_ms must be positive")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComputerUseConfig":
        return cls(
            backend=_string(payload.get("backend"), default="direct"),
            allowed_apps=_string_tuple(payload.get("allowed_apps")),
            allowed_app_bundle_ids=_string_mapping(
                payload.get("allowed_app_bundle_ids")
            ),
            allow_coordinate_click=_bool(
                payload.get("allow_coordinate_click"),
                default=False,
            ),
            screen_recording_required=_bool(
                payload.get("screen_recording_required"),
                default=False,
            ),
            timeout_ms=_int(payload.get("timeout_ms"), default=10_000),
        )

    def allowed_app_identities(self) -> dict[str, str | None]:
        identities: dict[str, str | None] = {
            app: None for app in self.allowed_apps
        }
        identities.update(self.allowed_app_bundle_ids)
        return identities


@dataclass(frozen=True)
class HelperConfig:
    transport: str = "unix_socket"
    helper_app_path: str | None = None
    bundle_id: str | None = None
    manifest_path: str | None = None
    endpoint: str | None = None
    token: str | None = None
    allowed_apps: tuple[str, ...] = ()
    auto_launch: bool = False
    launch_timeout_ms: int = 90_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "transport", _non_empty(self.transport, "transport"))
        object.__setattr__(
            self,
            "allowed_apps",
            _string_tuple(self.allowed_apps),
        )
        if self.launch_timeout_ms <= 0:
            raise ValueError("helper.launch_timeout_ms must be positive")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HelperConfig":
        return cls(
            transport=_string(payload.get("transport"), default="unix_socket"),
            helper_app_path=_optional_string(payload.get("helper_app_path")),
            bundle_id=_optional_string(payload.get("bundle_id")),
            manifest_path=_optional_string(payload.get("manifest_path")),
            endpoint=_optional_string(payload.get("endpoint")),
            token=_optional_string(payload.get("token")),
            allowed_apps=_string_tuple(payload.get("allowed_apps")),
            auto_launch=_bool(payload.get("auto_launch"), default=False),
            launch_timeout_ms=_int(payload.get("launch_timeout_ms"), default=90_000),
        )


@dataclass(frozen=True)
class WeChatConfig:
    app_name: str = "WeChat"
    bundle_id: str | None = "com.tencent.xinWeChat"
    app_control_tool: str = "macos.computer_use"
    search_hotkey: tuple[str, ...] = ("Command", "K")
    search_clear_hotkey: tuple[str, ...] = ("Command", "A")
    clear_key: str = "Delete"
    submit_key: str = "Return"
    max_message_chars: int = 2_000
    default_timeout_ms: int = 30_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_name", _non_empty(self.app_name, "app_name"))
        object.__setattr__(
            self,
            "app_control_tool",
            _non_empty(self.app_control_tool, "app_control_tool"),
        )
        object.__setattr__(
            self,
            "search_hotkey",
            _string_tuple(self.search_hotkey),
        )
        object.__setattr__(
            self,
            "search_clear_hotkey",
            _string_tuple(self.search_clear_hotkey),
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
        if self.max_message_chars <= 0:
            raise ValueError("wechat.max_message_chars must be positive")
        if self.default_timeout_ms <= 0:
            raise ValueError("wechat.default_timeout_ms must be positive")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WeChatConfig":
        return cls(
            app_name=_string(payload.get("app_name"), default="WeChat"),
            bundle_id=_optional_string(
                payload.get("bundle_id"),
                default="com.tencent.xinWeChat",
            ),
            app_control_tool=_string(
                payload.get("app_control_tool"),
                default="macos.computer_use",
            ),
            search_hotkey=_string_tuple(payload.get("search_hotkey", ("Command", "K"))),
            search_clear_hotkey=_string_tuple(
                payload.get("search_clear_hotkey", ("Command", "A"))
            ),
            clear_key=_string(payload.get("clear_key"), default="Delete"),
            submit_key=_string(payload.get("submit_key"), default="Return"),
            max_message_chars=_int(payload.get("max_message_chars"), default=2_000),
            default_timeout_ms=_int(payload.get("default_timeout_ms"), default=30_000),
        )


@dataclass(frozen=True)
class AppControlConfig:
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    computer_use: ComputerUseConfig = field(default_factory=ComputerUseConfig)
    helper: HelperConfig = field(default_factory=HelperConfig)
    wechat: WeChatConfig = field(default_factory=WeChatConfig)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AppControlConfig":
        return cls(
            logging=LoggingConfig.from_dict(_section(payload, "logging")),
            computer_use=ComputerUseConfig.from_dict(_section(payload, "computer_use")),
            helper=HelperConfig.from_dict(_section(payload, "helper")),
            wechat=WeChatConfig.from_dict(_section(payload, "wechat")),
        )

    @classmethod
    def from_toml(cls, path: str | Path) -> "AppControlConfig":
        with Path(path).expanduser().open("rb") as config_file:
            return cls.from_dict(tomllib.load(config_file))

    def to_dict(self) -> dict[str, Any]:
        return {
            "logging": {
                "level": self.logging.level,
                "redact_text": self.logging.redact_text,
                "json": self.logging.json,
                "event_sink": self.logging.event_sink,
                "raw_data_log_path": self.logging.raw_data_log_path,
            },
            "computer_use": {
                "backend": self.computer_use.backend,
                "allowed_apps": list(self.computer_use.allowed_apps),
                "allowed_app_bundle_ids": dict(
                    self.computer_use.allowed_app_bundle_ids
                ),
                "allow_coordinate_click": self.computer_use.allow_coordinate_click,
                "screen_recording_required": (
                    self.computer_use.screen_recording_required
                ),
                "timeout_ms": self.computer_use.timeout_ms,
            },
            "helper": {
                "transport": self.helper.transport,
                "helper_app_path": self.helper.helper_app_path,
                "bundle_id": self.helper.bundle_id,
                "manifest_path": self.helper.manifest_path,
                "endpoint": self.helper.endpoint,
                "token": self.helper.token,
                "allowed_apps": list(self.helper.allowed_apps),
                "auto_launch": self.helper.auto_launch,
                "launch_timeout_ms": self.helper.launch_timeout_ms,
            },
            "wechat": {
                "app_name": self.wechat.app_name,
                "bundle_id": self.wechat.bundle_id,
                "app_control_tool": self.wechat.app_control_tool,
                "search_hotkey": list(self.wechat.search_hotkey),
                "search_clear_hotkey": list(self.wechat.search_clear_hotkey),
                "clear_key": self.wechat.clear_key,
                "submit_key": self.wechat.submit_key,
                "max_message_chars": self.wechat.max_message_chars,
                "default_timeout_ms": self.wechat.default_timeout_ms,
            },
        }


def load_app_control_config(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> AppControlConfig:
    """Load config from TOML and apply environment overrides."""

    config = (
        AppControlConfig.from_toml(path) if path is not None else AppControlConfig()
    )
    environment = env if env is not None else os.environ
    return _apply_env_overrides(config, environment)


def _apply_env_overrides(
    config: AppControlConfig,
    env: Mapping[str, str],
) -> AppControlConfig:
    payload = config.to_dict()
    if "APP_CONTROL_LOG_LEVEL" in env:
        payload["logging"]["level"] = env["APP_CONTROL_LOG_LEVEL"]
    if "APP_CONTROL_LOG_REDACT_TEXT" in env:
        payload["logging"]["redact_text"] = _bool(env["APP_CONTROL_LOG_REDACT_TEXT"])
    if "APP_CONTROL_LOG_JSON" in env:
        payload["logging"]["json"] = _bool(env["APP_CONTROL_LOG_JSON"])
    if "APP_CONTROL_LOG_EVENT_SINK" in env:
        payload["logging"]["event_sink"] = env["APP_CONTROL_LOG_EVENT_SINK"]
    if "APP_CONTROL_LOG_RAW_DATA_PATH" in env:
        payload["logging"]["raw_data_log_path"] = env[
            "APP_CONTROL_LOG_RAW_DATA_PATH"
        ]
    if "APP_CONTROL_COMPUTER_USE_BACKEND" in env:
        payload["computer_use"]["backend"] = env["APP_CONTROL_COMPUTER_USE_BACKEND"]
    if "APP_CONTROL_ALLOWED_APPS" in env:
        payload["computer_use"]["allowed_apps"] = _string_tuple(
            env["APP_CONTROL_ALLOWED_APPS"]
        )
    if "APP_CONTROL_COMPUTER_USE_ALLOWED_APPS" in env:
        payload["computer_use"]["allowed_apps"] = _string_tuple(
            env["APP_CONTROL_COMPUTER_USE_ALLOWED_APPS"]
        )
    if "APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS" in env:
        payload["computer_use"]["allowed_app_bundle_ids"] = _string_pair_mapping(
            env["APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS"],
            "APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS",
        )
    if "APP_CONTROL_COMPUTER_USE_ALLOW_COORDINATE_CLICK" in env:
        payload["computer_use"]["allow_coordinate_click"] = _bool(
            env["APP_CONTROL_COMPUTER_USE_ALLOW_COORDINATE_CLICK"]
        )
    if "APP_CONTROL_COMPUTER_USE_SCREEN_RECORDING_REQUIRED" in env:
        payload["computer_use"]["screen_recording_required"] = _bool(
            env["APP_CONTROL_COMPUTER_USE_SCREEN_RECORDING_REQUIRED"]
        )
    if "APP_CONTROL_COMPUTER_USE_TIMEOUT_MS" in env:
        payload["computer_use"]["timeout_ms"] = _int_string(
            env["APP_CONTROL_COMPUTER_USE_TIMEOUT_MS"],
            "APP_CONTROL_COMPUTER_USE_TIMEOUT_MS",
        )
    if "APP_CONTROL_HELPER_TRANSPORT" in env:
        payload["helper"]["transport"] = env["APP_CONTROL_HELPER_TRANSPORT"]
    if "APP_CONTROL_HELPER_MANIFEST" in env:
        payload["helper"]["manifest_path"] = env["APP_CONTROL_HELPER_MANIFEST"]
    if "APP_CONTROL_HELPER_APP_PATH" in env:
        payload["helper"]["helper_app_path"] = env["APP_CONTROL_HELPER_APP_PATH"]
    if "APP_CONTROL_HELPER_BUNDLE_ID" in env:
        payload["helper"]["bundle_id"] = env["APP_CONTROL_HELPER_BUNDLE_ID"]
    if "APP_CONTROL_HELPER_ENDPOINT" in env:
        payload["helper"]["endpoint"] = env["APP_CONTROL_HELPER_ENDPOINT"]
    if "APP_CONTROL_HELPER_TOKEN" in env:
        payload["helper"]["token"] = env["APP_CONTROL_HELPER_TOKEN"]
    if "APP_CONTROL_HELPER_ALLOWED_APPS" in env:
        payload["helper"]["allowed_apps"] = _string_tuple(
            env["APP_CONTROL_HELPER_ALLOWED_APPS"]
        )
    if "APP_CONTROL_HELPER_AUTO_LAUNCH" in env:
        payload["helper"]["auto_launch"] = _bool(env["APP_CONTROL_HELPER_AUTO_LAUNCH"])
    if "APP_CONTROL_HELPER_LAUNCH_TIMEOUT_MS" in env:
        payload["helper"]["launch_timeout_ms"] = _int_string(
            env["APP_CONTROL_HELPER_LAUNCH_TIMEOUT_MS"],
            "APP_CONTROL_HELPER_LAUNCH_TIMEOUT_MS",
        )
    if "APP_CONTROL_WECHAT_APP_NAME" in env:
        payload["wechat"]["app_name"] = env["APP_CONTROL_WECHAT_APP_NAME"]
    if "APP_CONTROL_WECHAT_BUNDLE_ID" in env:
        payload["wechat"]["bundle_id"] = env["APP_CONTROL_WECHAT_BUNDLE_ID"]
    if "APP_CONTROL_WECHAT_APP_CONTROL_TOOL" in env:
        payload["wechat"]["app_control_tool"] = env[
            "APP_CONTROL_WECHAT_APP_CONTROL_TOOL"
        ]
    if "APP_CONTROL_WECHAT_SEARCH_HOTKEY" in env:
        payload["wechat"]["search_hotkey"] = _string_tuple(
            env["APP_CONTROL_WECHAT_SEARCH_HOTKEY"]
        )
    if "APP_CONTROL_WECHAT_SEARCH_CLEAR_HOTKEY" in env:
        payload["wechat"]["search_clear_hotkey"] = _string_tuple(
            env["APP_CONTROL_WECHAT_SEARCH_CLEAR_HOTKEY"]
        )
    if "APP_CONTROL_WECHAT_CLEAR_KEY" in env:
        payload["wechat"]["clear_key"] = env["APP_CONTROL_WECHAT_CLEAR_KEY"]
    if "APP_CONTROL_WECHAT_SUBMIT_KEY" in env:
        payload["wechat"]["submit_key"] = env["APP_CONTROL_WECHAT_SUBMIT_KEY"]
    if "APP_CONTROL_WECHAT_MAX_MESSAGE_CHARS" in env:
        payload["wechat"]["max_message_chars"] = _int_string(
            env["APP_CONTROL_WECHAT_MAX_MESSAGE_CHARS"],
            "APP_CONTROL_WECHAT_MAX_MESSAGE_CHARS",
        )
    if "APP_CONTROL_WECHAT_DEFAULT_TIMEOUT_MS" in env:
        payload["wechat"]["default_timeout_ms"] = _int_string(
            env["APP_CONTROL_WECHAT_DEFAULT_TIMEOUT_MS"],
            "APP_CONTROL_WECHAT_DEFAULT_TIMEOUT_MS",
        )
    return AppControlConfig.from_dict(payload)


def _section(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be a mapping")
    return value


def _non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string(value: Any, *, default: str) -> str:
    if value is None:
        return default
    return _non_empty(value, "string")


def _optional_string(value: Any, *, default: str | None = None) -> str | None:
    if value is None:
        return default
    return _non_empty(value, "optional string")


def _bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise TypeError(f"expected boolean value, got {value!r}")


def _int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"expected integer value, got {value!r}")
    return value


def _int_string(value: str, field_name: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, list | tuple):
        return tuple(_non_empty(item, "string tuple item") for item in value)
    raise TypeError(f"expected string sequence, got {value!r}")


def _string_mapping(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"expected string mapping, got {value!r}")
    return {
        _non_empty(key, "mapping key"): _non_empty(item, "mapping value")
        for key, item in value.items()
    }


def _string_pair_mapping(value: str, field_name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"{field_name} entries must use APP=bundle.id")
        key, bundle_id = item.split("=", 1)
        result[_non_empty(key, "mapping key")] = _non_empty(
            bundle_id,
            "mapping value",
        )
    return result
