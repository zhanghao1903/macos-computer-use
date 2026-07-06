"""Command, observation, and event protocol models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import ToolError
from .json_types import JsonValue, ensure_json_mapping, require_non_empty_string

COMMAND_SCHEMA = "app_control.command.v1"
OBSERVATION_SCHEMA = "app_control.observation.v1"
EVENT_SCHEMA = "app_control.event.v1"
SERVICE_REQUEST_SCHEMA = "app_control.service.request.v1"
SERVICE_RESPONSE_SCHEMA = "app_control.service.response.v1"
SERVICE_EVENT_SCHEMA = "app_control.service.event.v1"
HELPER_REQUEST_SCHEMA = "app_control.helper.request.v1"
HELPER_RESPONSE_SCHEMA = "app_control.helper.response.v1"


class ToolStatus(str, Enum):
    """Stable status values used by tool observations and events."""

    OK = "ok"
    NOT_FOUND = "not_found"
    NOT_READY = "not_ready"
    PERMISSION_MISSING = "permission_missing"
    TIMEOUT = "timeout"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ToolEventType(str, Enum):
    """Stream event kinds emitted while a command is running."""

    STARTED = "started"
    PROGRESS = "progress"
    OBSERVATION = "observation"
    WARNING = "warning"
    ERROR = "error"


class ServiceAction(str, Enum):
    """Local service request actions."""

    RUN = "run"
    SUBMIT = "submit"
    POLL = "poll"
    STREAM = "stream"


class ServiceResponseStatus(str, Enum):
    """Local service response statuses."""

    COMPLETE = "complete"
    NOT_FOUND = "not_found"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolCommand:
    """A protocol command envelope.

    The command expresses what to run. The caller owns authorization and
    policy decisions before constructing or submitting the command.
    """

    command_id: str
    tool: str
    operation: str
    input: dict[str, JsonValue] = field(default_factory=dict)
    timeout_ms: int | None = None
    idempotency_key: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    schema: str = COMMAND_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema",
            require_non_empty_string(self.schema, "schema"),
        )
        if self.schema != COMMAND_SCHEMA:
            raise ValueError(f"unsupported command schema: {self.schema}")
        object.__setattr__(
            self,
            "command_id",
            require_non_empty_string(self.command_id, "command_id"),
        )
        object.__setattr__(
            self,
            "tool",
            require_non_empty_string(self.tool, "tool"),
        )
        object.__setattr__(
            self,
            "operation",
            require_non_empty_string(self.operation, "operation"),
        )
        object.__setattr__(self, "input", ensure_json_mapping(self.input, "input"))
        object.__setattr__(
            self,
            "metadata",
            ensure_json_mapping(self.metadata, "metadata"),
        )
        if self.timeout_ms is not None and self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if self.idempotency_key is not None:
            object.__setattr__(
                self,
                "idempotency_key",
                require_non_empty_string(self.idempotency_key, "idempotency_key"),
            )

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema": self.schema,
            "commandId": self.command_id,
            "tool": self.tool,
            "operation": self.operation,
            "input": self.input,
        }
        if self.timeout_ms is not None:
            payload["timeoutMs"] = self.timeout_ms
        if self.idempotency_key is not None:
            payload["idempotencyKey"] = self.idempotency_key
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolCommand":
        return cls(
            schema=require_non_empty_string(
                payload.get("schema", COMMAND_SCHEMA),
                "schema",
            ),
            command_id=require_non_empty_string(
                _field(payload, "commandId", "command_id"),
                "commandId",
            ),
            tool=require_non_empty_string(payload.get("tool"), "tool"),
            operation=require_non_empty_string(
                payload.get("operation"),
                "operation",
            ),
            input=ensure_json_mapping(payload.get("input", {}), "input"),
            timeout_ms=_optional_positive_int(
                _field(payload, "timeoutMs", "timeout_ms"),
                "timeoutMs",
            ),
            idempotency_key=_optional_string(
                _field(payload, "idempotencyKey", "idempotency_key")
            ),
            metadata=ensure_json_mapping(payload.get("metadata", {}), "metadata"),
        )


@dataclass(frozen=True)
class ToolObservation:
    """A factual protocol result for one command."""

    command_id: str
    tool: str
    operation: str
    status: ToolStatus | str
    success: bool
    summary: str
    observation: dict[str, JsonValue] = field(default_factory=dict)
    evidence: dict[str, JsonValue] = field(default_factory=dict)
    timing: dict[str, JsonValue] = field(default_factory=dict)
    failure_kind: str | None = None
    message: str | None = None
    recovery_hint: str | None = None
    retryable: bool | None = None
    error: ToolError | Mapping[str, Any] | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    schema: str = OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema",
            require_non_empty_string(self.schema, "schema"),
        )
        if self.schema != OBSERVATION_SCHEMA:
            raise ValueError(f"unsupported observation schema: {self.schema}")
        object.__setattr__(
            self,
            "command_id",
            require_non_empty_string(self.command_id, "command_id"),
        )
        object.__setattr__(
            self,
            "tool",
            require_non_empty_string(self.tool, "tool"),
        )
        object.__setattr__(
            self,
            "operation",
            require_non_empty_string(self.operation, "operation"),
        )
        object.__setattr__(self, "status", _coerce_status(self.status))
        object.__setattr__(
            self,
            "summary",
            require_non_empty_string(self.summary, "summary"),
        )
        object.__setattr__(
            self,
            "observation",
            ensure_json_mapping(self.observation, "observation"),
        )
        object.__setattr__(
            self,
            "evidence",
            ensure_json_mapping(self.evidence, "evidence"),
        )
        object.__setattr__(
            self,
            "timing",
            ensure_json_mapping(self.timing, "timing"),
        )
        object.__setattr__(
            self,
            "metadata",
            ensure_json_mapping(self.metadata, "metadata"),
        )
        if self.success != (self.status == ToolStatus.OK):
            raise ValueError("success must match status == ok")
        if self.error is not None:
            error = _coerce_tool_error(self.error)
            if self.success:
                raise ValueError("successful observations cannot include error")
            object.__setattr__(self, "error", error)
            _ensure_error_field_matches(
                "failure_kind",
                self.failure_kind,
                error.failure_kind,
            )
            _ensure_error_field_matches("message", self.message, error.message)
            _ensure_error_field_matches(
                "recovery_hint",
                self.recovery_hint,
                error.recovery_hint,
            )
            _ensure_error_field_matches("retryable", self.retryable, error.retryable)
            if self.failure_kind is None:
                object.__setattr__(self, "failure_kind", error.failure_kind)
            if self.message is None:
                object.__setattr__(self, "message", error.message)
            if self.recovery_hint is None:
                object.__setattr__(self, "recovery_hint", error.recovery_hint)
            if self.retryable is None:
                object.__setattr__(self, "retryable", error.retryable)
        if self.failure_kind is not None:
            object.__setattr__(
                self,
                "failure_kind",
                require_non_empty_string(self.failure_kind, "failure_kind"),
            )
        if self.message is not None:
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

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema": self.schema,
            "commandId": self.command_id,
            "tool": self.tool,
            "operation": self.operation,
            "status": self.status.value,
            "success": self.success,
            "summary": self.summary,
            "observation": self.observation,
        }
        if self.evidence:
            payload["evidence"] = self.evidence
        if self.timing:
            payload["timing"] = self.timing
        if self.failure_kind is not None:
            payload["failureKind"] = self.failure_kind
        if self.message is not None:
            payload["message"] = self.message
        if self.recovery_hint is not None:
            payload["recoveryHint"] = self.recovery_hint
        if self.retryable is not None:
            payload["retryable"] = self.retryable
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def ok(
        cls,
        *,
        command_id: str,
        tool: str,
        operation: str,
        summary: str,
        observation: dict[str, JsonValue] | None = None,
        evidence: dict[str, JsonValue] | None = None,
        timing: dict[str, JsonValue] | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ToolObservation":
        return cls(
            command_id=command_id,
            tool=tool,
            operation=operation,
            status=ToolStatus.OK,
            success=True,
            summary=summary,
            observation=observation or {},
            evidence=evidence or {},
            timing=timing or {},
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        *,
        command_id: str,
        tool: str,
        operation: str,
        status: ToolStatus | str,
        error: ToolError,
        summary: str | None = None,
        observation: dict[str, JsonValue] | None = None,
        timing: dict[str, JsonValue] | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> "ToolObservation":
        coerced = _coerce_status(status)
        if coerced == ToolStatus.OK:
            raise ValueError("failure status cannot be ok")
        return cls(
            command_id=command_id,
            tool=tool,
            operation=operation,
            status=coerced,
            success=False,
            summary=summary or error.message,
            observation=observation or {},
            evidence=error.evidence,
            timing=timing or {},
            failure_kind=error.failure_kind,
            message=error.message,
            recovery_hint=error.recovery_hint,
            retryable=error.retryable,
            error=error,
            metadata=metadata or {},
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolObservation":
        return cls(
            schema=require_non_empty_string(
                payload.get("schema", OBSERVATION_SCHEMA),
                "schema",
            ),
            command_id=require_non_empty_string(
                _field(payload, "commandId", "command_id"),
                "commandId",
            ),
            tool=require_non_empty_string(payload.get("tool"), "tool"),
            operation=require_non_empty_string(
                payload.get("operation"),
                "operation",
            ),
            status=_coerce_status(payload.get("status")),
            success=_required_bool(payload.get("success"), "success"),
            summary=require_non_empty_string(payload.get("summary"), "summary"),
            observation=ensure_json_mapping(
                payload.get("observation", {}),
                "observation",
            ),
            evidence=ensure_json_mapping(payload.get("evidence", {}), "evidence"),
            timing=ensure_json_mapping(payload.get("timing", {}), "timing"),
            failure_kind=_optional_string(
                _field(payload, "failureKind", "failure_kind")
            ),
            message=_optional_string(payload.get("message")),
            recovery_hint=_optional_string(
                _field(payload, "recoveryHint", "recovery_hint")
            ),
            retryable=(
                None
                if "retryable" not in payload
                else _required_bool(payload["retryable"], "retryable")
            ),
            error=_optional_tool_error(payload.get("error")),
            metadata=ensure_json_mapping(payload.get("metadata", {}), "metadata"),
        )


@dataclass(frozen=True)
class ToolEvent:
    """A stream event emitted during command execution."""

    command_id: str
    seq: int
    event_type: ToolEventType | str
    phase: str | None = None
    status: ToolStatus | str | None = None
    summary: str | None = None
    data: dict[str, JsonValue] = field(default_factory=dict)
    schema: str = EVENT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema",
            require_non_empty_string(self.schema, "schema"),
        )
        if self.schema != EVENT_SCHEMA:
            raise ValueError(f"unsupported event schema: {self.schema}")
        object.__setattr__(
            self,
            "command_id",
            require_non_empty_string(self.command_id, "command_id"),
        )
        if self.seq < 0:
            raise ValueError("seq must be non-negative")
        object.__setattr__(
            self,
            "event_type",
            _coerce_event_type(self.event_type),
        )
        if self.phase is not None:
            object.__setattr__(
                self,
                "phase",
                require_non_empty_string(self.phase, "phase"),
            )
        if self.status is not None:
            object.__setattr__(self, "status", _coerce_status(self.status))
        if self.summary is not None:
            object.__setattr__(
                self,
                "summary",
                require_non_empty_string(self.summary, "summary"),
            )
        object.__setattr__(self, "data", ensure_json_mapping(self.data, "data"))

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema": self.schema,
            "commandId": self.command_id,
            "seq": self.seq,
            "type": self.event_type.value,
        }
        if self.phase is not None:
            payload["phase"] = self.phase
        if self.status is not None:
            payload["status"] = self.status.value
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.data:
            payload["data"] = self.data
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolEvent":
        return cls(
            schema=require_non_empty_string(
                payload.get("schema", EVENT_SCHEMA),
                "schema",
            ),
            command_id=require_non_empty_string(
                _field(payload, "commandId", "command_id"),
                "commandId",
            ),
            seq=_required_non_negative_int(payload.get("seq"), "seq"),
            event_type=_coerce_event_type(_field(payload, "type", "event_type")),
            phase=_optional_string(payload.get("phase")),
            status=(
                None
                if payload.get("status") is None
                else _coerce_status(payload["status"])
            ),
            summary=_optional_string(payload.get("summary")),
            data=ensure_json_mapping(payload.get("data", {}), "data"),
        )


@dataclass(frozen=True)
class ServiceRequest:
    """A local service request envelope around an optional tool command."""

    action: ServiceAction | str
    command: ToolCommand | Mapping[str, Any] | None = None
    request_id: str | None = None
    token: str | None = None
    schema: str = SERVICE_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema",
            require_non_empty_string(self.schema, "schema"),
        )
        if self.schema != SERVICE_REQUEST_SCHEMA:
            raise ValueError(f"unsupported service request schema: {self.schema}")
        object.__setattr__(
            self,
            "action",
            _coerce_service_action(self.action),
        )
        if self.command is not None:
            object.__setattr__(
                self,
                "command",
                _coerce_tool_command(self.command),
            )
        if self.request_id is not None:
            object.__setattr__(
                self,
                "request_id",
                require_non_empty_string(self.request_id, "request_id"),
            )
        if self.token is not None:
            object.__setattr__(
                self,
                "token",
                require_non_empty_string(self.token, "token"),
            )
        if self.action in {
            ServiceAction.RUN,
            ServiceAction.SUBMIT,
            ServiceAction.STREAM,
        } and self.command is None:
            raise ValueError(f"{self.action.value} service requests require command")
        if self.action == ServiceAction.POLL and self.request_id is None:
            raise ValueError("poll service requests require request_id")

    @classmethod
    def run(
        cls,
        command: ToolCommand | Mapping[str, Any],
        *,
        token: str | None = None,
    ) -> "ServiceRequest":
        return cls(action=ServiceAction.RUN, command=command, token=token)

    @classmethod
    def submit(
        cls,
        command: ToolCommand | Mapping[str, Any],
        *,
        request_id: str | None = None,
        token: str | None = None,
    ) -> "ServiceRequest":
        return cls(
            action=ServiceAction.SUBMIT,
            command=command,
            request_id=request_id,
            token=token,
        )

    @classmethod
    def poll(
        cls,
        request_id: str,
        *,
        token: str | None = None,
    ) -> "ServiceRequest":
        return cls(action=ServiceAction.POLL, request_id=request_id, token=token)

    @classmethod
    def stream(
        cls,
        command: ToolCommand | Mapping[str, Any],
        *,
        token: str | None = None,
    ) -> "ServiceRequest":
        return cls(action=ServiceAction.STREAM, command=command, token=token)

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema": self.schema,
            "action": self.action.value,
        }
        if self.request_id is not None:
            payload["requestId"] = self.request_id
        if self.token is not None:
            payload["token"] = self.token
        if self.command is not None:
            payload["command"] = _tool_command_payload(self.command)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ServiceRequest":
        return cls(
            schema=require_non_empty_string(
                payload.get("schema", SERVICE_REQUEST_SCHEMA),
                "schema",
            ),
            action=_coerce_service_action(payload.get("action")),
            command=_optional_tool_command(payload.get("command")),
            request_id=_optional_string(_field(payload, "requestId", "request_id")),
            token=_optional_string(payload.get("token")),
        )


@dataclass(frozen=True)
class ServiceResponse:
    """A local service response envelope."""

    status: ServiceResponseStatus | str
    success: bool
    request_id: str | None = None
    observation: ToolObservation | Mapping[str, Any] | None = None
    error: ToolError | Mapping[str, Any] | None = None
    schema: str = SERVICE_RESPONSE_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema",
            require_non_empty_string(self.schema, "schema"),
        )
        if self.schema != SERVICE_RESPONSE_SCHEMA:
            raise ValueError(f"unsupported service response schema: {self.schema}")
        object.__setattr__(
            self,
            "status",
            _coerce_service_response_status(self.status),
        )
        object.__setattr__(
            self,
            "success",
            _required_bool(self.success, "success"),
        )
        if self.success != (self.status == ServiceResponseStatus.COMPLETE):
            raise ValueError("success must match status == complete")
        if self.request_id is not None:
            object.__setattr__(
                self,
                "request_id",
                require_non_empty_string(self.request_id, "request_id"),
            )
        if self.observation is not None:
            object.__setattr__(
                self,
                "observation",
                _observation_payload(self.observation),
            )
        if self.error is not None:
            object.__setattr__(
                self,
                "error",
                _coerce_tool_error(self.error),
            )
        if self.status == ServiceResponseStatus.FAILED and self.error is None:
            raise ValueError("failed service responses require error")

    @classmethod
    def complete(
        cls,
        observation: ToolObservation | Mapping[str, Any],
        *,
        request_id: str | None = None,
    ) -> "ServiceResponse":
        return cls(
            status=ServiceResponseStatus.COMPLETE,
            success=True,
            request_id=request_id,
            observation=observation,
        )

    @classmethod
    def not_found(
        cls,
        *,
        request_id: str | None = None,
    ) -> "ServiceResponse":
        return cls(
            status=ServiceResponseStatus.NOT_FOUND,
            success=False,
            request_id=request_id,
        )

    @classmethod
    def failed(
        cls,
        error: ToolError | Mapping[str, Any],
        *,
        request_id: str | None = None,
    ) -> "ServiceResponse":
        return cls(
            status=ServiceResponseStatus.FAILED,
            success=False,
            request_id=request_id,
            error=error,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema": self.schema,
            "status": self.status.value,
            "success": self.success,
        }
        if self.request_id is not None:
            payload["requestId"] = self.request_id
        if self.observation is not None:
            payload["observation"] = self.observation
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ServiceResponse":
        return cls(
            schema=require_non_empty_string(
                payload.get("schema", SERVICE_RESPONSE_SCHEMA),
                "schema",
            ),
            status=_coerce_service_response_status(payload.get("status")),
            success=_required_bool(payload.get("success"), "success"),
            request_id=_optional_string(_field(payload, "requestId", "request_id")),
            observation=(
                None
                if "observation" not in payload
                else ensure_json_mapping(payload["observation"], "observation")
            ),
            error=_optional_tool_error(payload.get("error")),
        )


@dataclass(frozen=True)
class ServiceEventEnvelope:
    """A local service stream envelope around one tool event."""

    request_id: str
    event: ToolEvent | Mapping[str, Any]
    status: str = "event"
    success: bool = True
    schema: str = SERVICE_EVENT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema",
            require_non_empty_string(self.schema, "schema"),
        )
        if self.schema != SERVICE_EVENT_SCHEMA:
            raise ValueError(f"unsupported service event schema: {self.schema}")
        object.__setattr__(
            self,
            "request_id",
            require_non_empty_string(self.request_id, "request_id"),
        )
        if self.status != "event":
            raise ValueError("service event status must be event")
        object.__setattr__(
            self,
            "success",
            _required_bool(self.success, "success"),
        )
        if not self.success:
            raise ValueError("service events must be successful")
        object.__setattr__(self, "event", _coerce_tool_event(self.event))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schema": self.schema,
            "requestId": self.request_id,
            "status": self.status,
            "success": self.success,
            "event": self.event.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ServiceEventEnvelope":
        return cls(
            schema=require_non_empty_string(
                payload.get("schema", SERVICE_EVENT_SCHEMA),
                "schema",
            ),
            request_id=require_non_empty_string(
                _field(payload, "requestId", "request_id"),
                "requestId",
            ),
            status=require_non_empty_string(payload.get("status"), "status"),
            success=_required_bool(payload.get("success"), "success"),
            event=_coerce_tool_event(payload.get("event")),
        )


def _coerce_status(value: ToolStatus | str | Any) -> ToolStatus:
    if isinstance(value, ToolStatus):
        return value
    try:
        return ToolStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"unsupported tool status: {value}") from exc


def _coerce_event_type(value: ToolEventType | str | Any) -> ToolEventType:
    if isinstance(value, ToolEventType):
        return value
    try:
        return ToolEventType(str(value))
    except ValueError as exc:
        raise ValueError(f"unsupported event type: {value}") from exc


def _coerce_service_action(value: ServiceAction | str | Any) -> ServiceAction:
    if isinstance(value, ServiceAction):
        return value
    try:
        return ServiceAction(str(value))
    except ValueError as exc:
        raise ValueError(f"unsupported service action: {value}") from exc


def _coerce_service_response_status(
    value: ServiceResponseStatus | str | Any,
) -> ServiceResponseStatus:
    if isinstance(value, ServiceResponseStatus):
        return value
    try:
        return ServiceResponseStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"unsupported service response status: {value}") from exc


def _coerce_tool_command(value: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(value, ToolCommand):
        return value
    if isinstance(value, Mapping):
        return ToolCommand.from_dict(dict(value))
    raise TypeError("command must be a ToolCommand or mapping")


def _optional_tool_command(value: Any) -> ToolCommand | None:
    if value is None:
        return None
    return _coerce_tool_command(value)


def _tool_command_payload(value: ToolCommand | Mapping[str, Any]) -> dict[str, JsonValue]:
    return _coerce_tool_command(value).to_dict()


def _observation_payload(
    value: ToolObservation | Mapping[str, Any],
) -> dict[str, JsonValue]:
    if isinstance(value, ToolObservation):
        return value.to_dict()
    if isinstance(value, Mapping):
        return ensure_json_mapping(value, "observation")
    raise TypeError("observation must be a ToolObservation or mapping")


def _coerce_tool_error(value: ToolError | Mapping[str, Any]) -> ToolError:
    if isinstance(value, ToolError):
        return value
    if isinstance(value, Mapping):
        return ToolError.from_dict(dict(value))
    raise TypeError("error must be a ToolError or mapping")


def _optional_tool_error(value: Any) -> ToolError | None:
    if value is None:
        return None
    return _coerce_tool_error(value)


def _ensure_error_field_matches(
    field_name: str,
    current_value: Any,
    error_value: Any,
) -> None:
    if current_value is None:
        return
    if current_value != error_value:
        raise ValueError(f"{field_name} does not match nested error")


def _coerce_tool_event(value: ToolEvent | Mapping[str, Any] | Any) -> ToolEvent:
    if isinstance(value, ToolEvent):
        return value
    if isinstance(value, Mapping):
        return ToolEvent.from_dict(dict(value))
    raise TypeError("event must be a ToolEvent or mapping")


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return require_non_empty_string(value, "optional string")


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _required_non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _field(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None
