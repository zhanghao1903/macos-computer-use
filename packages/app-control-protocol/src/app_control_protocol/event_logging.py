"""Default logging observer for app-control stream events."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
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
        raw_payload = event.to_dict()
        self._write_raw_data_log(raw_payload)
        payload = raw_payload
        if self.config.redact_text:
            payload = _redact_payload(payload)
        line = _json_line(payload) if self.config.json else _text_line(payload)
        if self.stream is not None:
            self.stream.write(line + "\n")
            self.stream.flush()
            return
        assert self.logger is not None
        self.logger.log(_level_number(self.config.level), line)

    def _write_raw_data_log(self, payload: dict[str, JsonValue]) -> None:
        if not self.config.raw_data_log_path:
            return
        raw_observation = _raw_event_observation(payload)
        if raw_observation is None:
            return
        record: dict[str, JsonValue] = {
            "commandId": payload.get("commandId"),
            "type": payload.get("type"),
            "phase": payload.get("phase"),
            "status": payload.get("status"),
            "summary": payload.get("summary"),
            "rawObservation": raw_observation,
        }
        path = Path(self.config.raw_data_log_path).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as log_file:
                log_file.write(
                    json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                )
        except OSError as exc:
            assert self.logger is not None
            self.logger.warning("failed to write raw data log %s: %s", path, exc)


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
    observation = _event_observation(payload)
    if observation:
        parts.append(
            "observation="
            + json.dumps(observation, ensure_ascii=False, sort_keys=True)
        )
    raw_observation = _raw_event_observation(payload)
    if raw_observation:
        parts.append(
            "rawObservation="
            + json.dumps(raw_observation, ensure_ascii=False, sort_keys=True)
        )
    return " | ".join(parts)


def _event_observation(payload: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    raw_observation = _raw_event_observation(payload)
    if raw_observation is None:
        return None
    observation = raw_observation.get("observation")
    return observation if isinstance(observation, dict) else None


def _raw_event_observation(
    payload: dict[str, JsonValue],
) -> dict[str, JsonValue] | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    for key in ("observation", "appControlObservation"):
        envelope = data.get(key)
        if isinstance(envelope, dict):
            return envelope
    return None


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
