"""Default logging observer for app-control stream events."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import sys
from typing import Any, TextIO

from .config import AppControlConfig, LoggingConfig
from .json_types import JsonValue
from .models import ToolEvent

_REDACTED = "[redacted]"
_SENSITIVE_KEY_PARTS = (
    "text",
    "message",
    "password",
    "secret",
    "token",
    "credential",
)


@dataclass
class LoggingToolObserver:
    """Route app-control events to a standard logger or text stream."""

    config: LoggingConfig = field(default_factory=LoggingConfig)
    logger: logging.Logger | None = None
    stream: TextIO | None = None

    def __post_init__(self) -> None:
        if self.logger is None:
            self.logger = logging.getLogger("app_control")

    @classmethod
    def from_config(
        cls,
        config: AppControlConfig | LoggingConfig | None = None,
        *,
        logger: logging.Logger | None = None,
        stream: TextIO | None = None,
    ) -> "LoggingToolObserver":
        if config is None:
            logging_config = LoggingConfig()
        elif isinstance(config, AppControlConfig):
            logging_config = config.logging
        else:
            logging_config = config
        return cls(config=logging_config, logger=logger, stream=stream)

    def on_event(self, event: ToolEvent) -> None:
        payload = event.to_dict()
        if self.config.redact_text:
            payload = _redact_payload(payload)
        line = _json_line(payload) if self.config.json else _text_line(payload)
        if self.stream is not None:
            self.stream.write(line + "\n")
            self.stream.flush()
            return
        assert self.logger is not None
        self.logger.log(_level_number(self.config.level), line)


def build_logging_observer(
    config: AppControlConfig | LoggingConfig | None = None,
    *,
    stream: TextIO | None = None,
    logger: logging.Logger | None = None,
) -> LoggingToolObserver:
    """Build the default event observer from app-control logging config."""

    effective_stream = stream
    logging_config: LoggingConfig
    if config is None:
        logging_config = LoggingConfig()
    elif isinstance(config, AppControlConfig):
        logging_config = config.logging
    else:
        logging_config = config
    if effective_stream is None:
        if logging_config.event_sink == "stdout":
            effective_stream = sys.stdout
        elif logging_config.event_sink == "stderr":
            effective_stream = sys.stderr
        elif logging_config.event_sink != "logger":
            raise ValueError(
                "logging.event_sink must be one of stdout, stderr, or logger"
            )
    return LoggingToolObserver.from_config(
        logging_config,
        logger=logger,
        stream=effective_stream,
    )


def _json_line(payload: dict[str, JsonValue]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _text_line(payload: dict[str, JsonValue]) -> str:
    event_type = payload.get("type", "event")
    command_id = payload.get("commandId", "unknown-command")
    phase = payload.get("phase", "unknown-phase")
    status = payload.get("status")
    summary = payload.get("summary", "")
    parts = [str(event_type), str(command_id), str(phase)]
    if status:
        parts.append(str(status))
    if summary:
        parts.append(str(summary))
    return " | ".join(parts)


def _redact_payload(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        key: _redact_value(key, value)
        for key, value in payload.items()
    }


def _redact_value(key: str, value: JsonValue) -> JsonValue:
    if _is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, dict):
        return {
            child_key: _redact_value(child_key, child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_list_value(item) for item in value]
    return value


def _redact_list_value(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: _redact_value(key, item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_list_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("_", "").replace("-", "").lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _level_number(level: str) -> int:
    return {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }[level]
