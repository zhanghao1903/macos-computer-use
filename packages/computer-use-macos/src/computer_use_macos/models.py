"""Public dataclass models for macOS computer-use operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ComputerUseOperation(str, Enum):
    READINESS = "readiness"
    OBSERVE = "observe"
    ACCESSIBILITY_QUERY = "accessibility_query"
    OPEN_APP = "open_app"
    FOCUS_APP = "focus_app"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"
    WAIT = "wait"


class ComputerUseStatus(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"
    NEEDS_USER = "needs_user"
    NOT_AVAILABLE = "not_available"
    TIMEOUT = "timeout"
    FAILED = "failed"


class ComputerUseReadinessStatus(str, Enum):
    READY = "ready"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    BACKEND_DISABLED = "backend_disabled"
    MISSING_ACCESSIBILITY = "missing_accessibility"
    MISSING_SCREEN_RECORDING = "missing_screen_recording"
    NEEDS_MANUAL_SETUP = "needs_manual_setup"
    ERROR = "error"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _jsonify(value: Any) -> JsonValue:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonify(item) for item in value]
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


@dataclass(frozen=True)
class RiskDecision:
    level: RiskLevel
    requires_confirmation: bool
    reason: str
    risk_label: str | None = None
    action_fingerprint: str | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        return _jsonify(asdict(self))  # type: ignore[return-value]


@dataclass(frozen=True)
class ComputerUseReadiness:
    status: ComputerUseReadinessStatus
    platform: str
    accessibility_trusted: bool
    screen_recording_available: bool | None = None
    screen_recording_required: bool = False
    apple_events_available: bool | None = None
    helper_installed: bool = False
    helper_running: bool = False
    helper_bundle_id: str | None = None
    enabled_operations: tuple[ComputerUseOperation, ...] = ()
    setup_hint: str | None = None
    diagnostics: dict[str, str] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.status == ComputerUseReadinessStatus.READY

    def to_dict(self) -> dict[str, JsonValue]:
        payload = _jsonify(asdict(self))
        assert isinstance(payload, dict)
        payload["permissions"] = {
            "accessibility": self.accessibility_trusted,
            "screenRecording": self.screen_recording_available,
            "appleEvents": self.apple_events_available,
        }
        helper: dict[str, JsonValue] = {
            "installed": self.helper_installed,
            "running": self.helper_running,
        }
        if self.helper_bundle_id is not None:
            helper["bundleId"] = self.helper_bundle_id
        payload["helper"] = helper
        payload["enabledOperations"] = [
            operation.value for operation in self.enabled_operations
        ]
        return payload


@dataclass(frozen=True)
class ComputerUseResult:
    operation: ComputerUseOperation
    status: ComputerUseStatus
    success: bool
    summary: str
    text_extract: str | None = None
    snapshot_id: str | None = None
    risk: RiskDecision | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return _jsonify(asdict(self))  # type: ignore[return-value]

    @classmethod
    def ok(
        cls,
        operation: ComputerUseOperation,
        summary: str,
        *,
        text_extract: str | None = None,
        snapshot_id: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ComputerUseResult":
        return cls(
            operation=operation,
            status=ComputerUseStatus.OK,
            success=True,
            summary=summary,
            text_extract=text_extract,
            snapshot_id=snapshot_id,
            metadata=metadata or {},
        )

    @classmethod
    def not_available(
        cls,
        operation: ComputerUseOperation,
        summary: str,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ComputerUseResult":
        return cls(
            operation=operation,
            status=ComputerUseStatus.NOT_AVAILABLE,
            success=False,
            summary=summary,
            metadata=metadata or {},
        )

    @classmethod
    def blocked(
        cls,
        operation: ComputerUseOperation,
        summary: str,
        *,
        risk: RiskDecision | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ComputerUseResult":
        return cls(
            operation=operation,
            status=ComputerUseStatus.BLOCKED,
            success=False,
            summary=summary,
            risk=risk,
            metadata=metadata or {},
        )

    @classmethod
    def needs_user(
        cls,
        operation: ComputerUseOperation,
        summary: str,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ComputerUseResult":
        return cls(
            operation=operation,
            status=ComputerUseStatus.NEEDS_USER,
            success=False,
            summary=summary,
            metadata=metadata or {},
        )

    @classmethod
    def failed(
        cls,
        operation: ComputerUseOperation,
        summary: str,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ComputerUseResult":
        return cls(
            operation=operation,
            status=ComputerUseStatus.FAILED,
            success=False,
            summary=summary,
            metadata=metadata or {},
        )

    @classmethod
    def timed_out(
        cls,
        operation: ComputerUseOperation,
        summary: str,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ComputerUseResult":
        return cls(
            operation=operation,
            status=ComputerUseStatus.TIMEOUT,
            success=False,
            summary=summary,
            metadata=metadata or {},
        )
