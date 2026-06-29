"""Local helper transport client for protocol commands."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
import socket
from typing import Any, Protocol, TYPE_CHECKING

from app_control_protocol import (
    HELPER_REQUEST_SCHEMA,
    HELPER_RESPONSE_SCHEMA,
    validate_protocol_payload,
)
from app_control_protocol.errors import ProtocolValidationError

from ..commands import (
    click_accessibility_command,
    click_command,
    click_coordinate_command,
    focus_app_command,
    hotkey_command,
    observe_command,
    open_app_command,
    press_key_command,
    readiness_command,
    type_text_command,
    wait_command,
)
from ..models import JsonValue

from .manifest import HelperManifest

if TYPE_CHECKING:
    from app_control_protocol import ToolObservation, ToolObserver


class RoundTrip(Protocol):
    def __call__(
        self,
        socket_path: Path,
        payload: Mapping[str, Any],
        *,
        timeout: float,
    ) -> dict[str, Any]: ...


class HelperTransportError(RuntimeError):
    """Raised when a helper transport cannot complete a request."""


@dataclass(frozen=True)
class HelperTransportRequest:
    command: dict[str, JsonValue]
    token: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema": HELPER_REQUEST_SCHEMA,
            "command": self.command,
        }
        if self.token is not None:
            payload["token"] = self.token
        if self.metadata:
            payload["metadata"] = self.metadata
        _validate_helper_payload("helper_request", payload)
        return payload


class HelperTransportClient:
    """Send app-control protocol commands to a local helper process."""

    def __init__(
        self,
        manifest: HelperManifest,
        *,
        timeout: float = 10.0,
        round_trip: RoundTrip | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._manifest = manifest
        self._timeout = timeout
        self._round_trip = round_trip or _unix_socket_round_trip

    @property
    def manifest(self) -> HelperManifest:
        return self._manifest

    def readiness(
        self,
        *,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Run the helper readiness command."""

        return self.run_command(
            readiness_command(
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def open_app(
        self,
        app: str,
        *,
        bundle_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Open or focus an app through the helper protocol."""

        return self.run_command(
            open_app_command(
                app,
                bundle_id=bundle_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def focus_app(
        self,
        app: str,
        *,
        bundle_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Focus an app through the helper protocol."""

        return self.run_command(
            focus_app_command(
                app,
                bundle_id=bundle_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def observe(
        self,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        include_visible_text: bool | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Observe the current desktop state through the helper protocol."""

        return self.run_command(
            observe_command(
                target_app=target_app,
                bundle_id=bundle_id,
                include_visible_text=include_visible_text,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def type_text(
        self,
        text: str,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Type text through the helper protocol without submitting it."""

        return self.run_command(
            type_text_command(
                text,
                target_app=target_app,
                bundle_id=bundle_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def press_key(
        self,
        key: str,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Press one key through the helper protocol."""

        return self.run_command(
            press_key_command(
                key,
                target_app=target_app,
                bundle_id=bundle_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def hotkey(
        self,
        keys: tuple[str, ...] | list[str],
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Press a modifier hotkey through the helper protocol."""

        return self.run_command(
            hotkey_command(
                keys,
                target_app=target_app,
                bundle_id=bundle_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def click(
        self,
        target: str | None = None,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        selector: Mapping[str, JsonValue] | None = None,
        coordinates: list[int] | tuple[int, int] | Mapping[str, JsonValue] | None = None,
        snapshot_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Click a semantic, selector, or coordinate target through the helper."""

        return self.run_command(
            click_command(
                target,
                target_app=target_app,
                bundle_id=bundle_id,
                selector=selector,
                coordinates=coordinates,
                snapshot_id=snapshot_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def click_accessibility(
        self,
        selector: Mapping[str, JsonValue],
        *,
        target_app: str,
        bundle_id: str | None = None,
        snapshot_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Click an Accessibility selector through the helper protocol."""

        return self.run_command(
            click_accessibility_command(
                selector,
                target_app=target_app,
                bundle_id=bundle_id,
                snapshot_id=snapshot_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def click_coordinate(
        self,
        x: int,
        y: int,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        snapshot_id: str | None = None,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Click screen coordinates through the helper protocol."""

        return self.run_command(
            click_coordinate_command(
                x,
                y,
                target_app=target_app,
                bundle_id=bundle_id,
                snapshot_id=snapshot_id,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def wait(
        self,
        *,
        seconds: float = 1.0,
        command_id: str | None = None,
        timeout: float | None = None,
        timeout_ms: int | None = None,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Wait through the helper protocol."""

        return self.run_command(
            wait_command(
                seconds=seconds,
                command_id=command_id,
                timeout_ms=_command_timeout_ms(timeout, timeout_ms),
            ),
            observer=observer,
        )

    def run_command(
        self,
        command: object,
        *,
        observer: object | None = None,
    ) -> object:
        (
            tool_command_cls,
            tool_observation_cls,
            tool_event_cls,
            tool_event_type_cls,
        ) = _protocol_models()
        tool_command = _coerce_command(command, tool_command_cls)
        started = _started_event(
            tool_command,
            tool_event_cls=tool_event_cls,
            tool_event_type_cls=tool_event_type_cls,
        )
        _emit_observer(observer, started)
        payload = self._send_request(tool_command.to_dict())
        observation = tool_observation_cls.from_dict(_observation_payload(payload))
        _emit_observer(
            observer,
            _observation_event(
                tool_command,
                observation,
                tool_event_cls=tool_event_cls,
                tool_event_type_cls=tool_event_type_cls,
            ),
        )
        return observation

    def run_stream(
        self,
        command: object,
        *,
        observer: object | None = None,
    ) -> Iterator[object]:
        (
            tool_command_cls,
            tool_observation_cls,
            tool_event_cls,
            tool_event_type_cls,
        ) = _protocol_models()
        tool_command = _coerce_command(command, tool_command_cls)
        started = _started_event(
            tool_command,
            tool_event_cls=tool_event_cls,
            tool_event_type_cls=tool_event_type_cls,
        )
        _emit_observer(observer, started)
        yield started
        payload = self._send_request(tool_command.to_dict())
        observation = tool_observation_cls.from_dict(_observation_payload(payload))
        final_event = _observation_event(
            tool_command,
            observation,
            tool_event_cls=tool_event_cls,
            tool_event_type_cls=tool_event_type_cls,
        )
        _emit_observer(observer, final_event)
        yield final_event

    def _send_request(self, command: dict[str, JsonValue]) -> dict[str, Any]:
        if self._manifest.transport != "unix_socket":
            raise HelperTransportError(
                "unsupported helper transport: " + self._manifest.transport
            )
        if not self._manifest.socket_path:
            raise HelperTransportError("helper manifest does not include socketPath")
        request = HelperTransportRequest(
            command=command,
            token=self._manifest.read_token(),
            metadata={
                "bundleId": self._manifest.bundle_id,
                "apiVersion": self._manifest.api_version,
            },
        )
        return self._round_trip(
            Path(self._manifest.socket_path).expanduser(),
            request.to_dict(),
            timeout=self._timeout,
        )


def helper_transport_from_manifest(
    manifest: HelperManifest,
    *,
    timeout: float = 10.0,
) -> HelperTransportClient:
    return HelperTransportClient(manifest, timeout=timeout)


def _command_timeout_ms(
    timeout: float | None,
    timeout_ms: int | None,
) -> int | None:
    if timeout is not None and timeout_ms is not None:
        raise ValueError("pass either timeout or timeout_ms, not both")
    if timeout is None:
        return timeout_ms
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    return max(1, int(round(timeout * 1000)))


def _unix_socket_round_trip(
    socket_path: Path,
    payload: Mapping[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    message = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(socket_path))
            client.sendall(message.encode("utf-8"))
            raw_response = _read_line(client)
    except OSError as exc:
        raise HelperTransportError(f"helper transport failed: {exc}") from exc
    try:
        response = json.loads(raw_response.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HelperTransportError("helper response is not valid JSON") from exc
    if not isinstance(response, dict):
        raise HelperTransportError("helper response must be a JSON object")
    return response


def _read_line(client: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    data = b"".join(chunks)
    line, _, _ = data.partition(b"\n")
    if not line:
        raise HelperTransportError("helper closed connection without a response")
    return line


def _observation_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema") == HELPER_RESPONSE_SCHEMA:
        response = _validate_helper_payload("helper_response", payload)
        observation = response.get("observation")
        if observation is None and response.get("error") is not None:
            raise HelperTransportError(_helper_error_message(response["error"]))
    else:
        observation = payload.get("observation", payload)
    if not isinstance(observation, dict):
        raise HelperTransportError("helper response does not contain an observation")
    return dict(observation)


def _validate_helper_payload(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return dict(validate_protocol_payload(name, payload))
    except ProtocolValidationError as exc:
        readable_name = name.replace("_", " ")
        raise HelperTransportError(f"{readable_name} is invalid: {exc}") from exc


def _helper_error_message(error: Any) -> str:
    if not isinstance(error, Mapping):
        return "helper returned an error"
    message = error.get("message")
    if isinstance(message, str) and message:
        return f"helper returned an error: {message}"
    failure_kind = error.get("failureKind")
    if isinstance(failure_kind, str) and failure_kind:
        return f"helper returned an error: {failure_kind}"
    return "helper returned an error"


def _coerce_command(command: object, tool_command_cls: type[Any]) -> Any:
    if isinstance(command, Mapping):
        return tool_command_cls.from_dict(dict(command))
    if isinstance(command, tool_command_cls):
        return command
    raise TypeError("command must be a ToolCommand or mapping")


def _started_event(
    command: Any,
    *,
    tool_event_cls: type[Any],
    tool_event_type_cls: type[Any],
) -> Any:
    return tool_event_cls(
        command_id=command.command_id,
        seq=0,
        event_type=tool_event_type_cls.STARTED,
        phase=command.operation,
        summary=f"Started helper command: {command.operation}",
    )


def _observation_event(
    command: Any,
    observation: Any,
    *,
    tool_event_cls: type[Any],
    tool_event_type_cls: type[Any],
) -> Any:
    return tool_event_cls(
        command_id=command.command_id,
        seq=1,
        event_type=tool_event_type_cls.OBSERVATION,
        phase=command.operation,
        status=observation.status,
        summary=observation.summary,
        data={"observation": observation.to_dict()},
    )


def _emit_observer(observer: object | None, event: object) -> None:
    if observer is not None:
        observer.on_event(event)  # type: ignore[attr-defined]


def _protocol_models() -> tuple[type[Any], type[Any], type[Any], type[Any]]:
    try:
        from app_control_protocol import (
            ToolCommand,
            ToolEvent,
            ToolEventType,
            ToolObservation,
        )
    except ImportError as exc:  # pragma: no cover - environment setup failure.
        raise RuntimeError(
            "helper transport requires the app-control-protocol package. "
            "Install app-control-protocol or add packages/app-control-protocol/src "
            "to PYTHONPATH in the monorepo checkout."
        ) from exc
    return ToolCommand, ToolObservation, ToolEvent, ToolEventType
