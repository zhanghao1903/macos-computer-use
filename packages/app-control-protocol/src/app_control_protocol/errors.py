"""Structured error model for app-control protocol results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .json_types import JsonValue, ensure_json_mapping, require_non_empty_string


class ProtocolValidationError(ValueError):
    """Raised when a protocol payload cannot be validated."""


@dataclass(frozen=True)
class ToolError:
    """A structured tool error that can be embedded in observations."""

    failure_kind: str
    message: str
    recovery_hint: str | None = None
    retryable: bool = False
    phase: str | None = None
    operation: str | None = None
    evidence: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "failure_kind",
            require_non_empty_string(self.failure_kind, "failure_kind"),
        )
        object.__setattr__(
            self,
            "message",
            require_non_empty_string(self.message, "message"),
        )
        if self.recovery_hint is not None:
            object.__setattr__(
                self,
                "recovery_hint",
                require_non_empty_string(self.recovery_hint, "recovery_hint"),
            )
        if self.phase is not None:
            object.__setattr__(
                self,
                "phase",
                require_non_empty_string(self.phase, "phase"),
            )
        if self.operation is not None:
            object.__setattr__(
                self,
                "operation",
                require_non_empty_string(self.operation, "operation"),
            )
        object.__setattr__(
            self,
            "evidence",
            ensure_json_mapping(self.evidence, "evidence"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "failureKind": self.failure_kind,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.recovery_hint is not None:
            payload["recoveryHint"] = self.recovery_hint
        if self.phase is not None:
            payload["phase"] = self.phase
        if self.operation is not None:
            payload["operation"] = self.operation
        if self.evidence:
            payload["evidence"] = self.evidence
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolError":
        return cls(
            failure_kind=require_non_empty_string(
                _field(payload, "failureKind", "failure_kind"),
                "failureKind",
            ),
            message=require_non_empty_string(payload.get("message"), "message"),
            recovery_hint=_optional_string(
                _field(payload, "recoveryHint", "recovery_hint")
            ),
            retryable=_bool(payload.get("retryable", False), "retryable"),
            phase=_optional_string(payload.get("phase")),
            operation=_optional_string(payload.get("operation")),
            evidence=ensure_json_mapping(payload.get("evidence", {}), "evidence"),
        )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return require_non_empty_string(value, "optional string")


def _field(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value
