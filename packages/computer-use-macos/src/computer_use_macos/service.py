"""Local service mode for app-control protocol commands."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
import socket
import socketserver
import threading
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .models import JsonValue

if TYPE_CHECKING:
    from app_control_protocol import ToolCommand, ToolEvent, ToolObservation

SERVICE_REQUEST_SCHEMA = "app_control.service.request.v1"
SERVICE_RESPONSE_SCHEMA = "app_control.service.response.v1"
SERVICE_EVENT_SCHEMA = "app_control.service.event.v1"


class LocalServiceError(RuntimeError):
    """Raised when the local service cannot be started or handle a request."""


class AppControlServiceClient:
    """Protocol-like runtime surface expected by LocalCommandService."""

    def run_command(
        self,
        command: "ToolCommand | Mapping[str, Any]",
        *,
        observer: object | None = None,
    ) -> "ToolObservation": ...

    def run_stream(
        self,
        command: "ToolCommand | Mapping[str, Any]",
        *,
        observer: object | None = None,
    ) -> "Iterator[ToolEvent]": ...


@dataclass
class LocalCommandService:
    """Handle JSON-compatible local service requests.

    The service envelope is intentionally small:

    - `run`: execute a command and return the observation immediately.
    - `submit`: execute a command, store the observation, and return request id.
    - `poll`: retrieve a stored observation by request id.
    - `stream`: execute a command and emit JSON-lines event envelopes followed
      by the final observation response.

    Execution is synchronous in this process. The `submit`/`poll` shape gives
    non-Python callers a stable polling contract without introducing a remote
    task system.
    """

    app_control: AppControlServiceClient
    token: str | None = None
    observer: object | None = None
    _results: dict[str, dict[str, JsonValue]] = field(default_factory=dict)

    def handle_payload(self, payload: Mapping[str, Any]) -> dict[str, JsonValue]:
        try:
            self._authorize(payload)
            _validate_service_request(payload)
            action = _request_action(payload)
            if action == "run":
                return self._run(payload, store=False)
            if action == "submit":
                return self._run(payload, store=True)
            if action == "poll":
                return self._poll(payload)
            if action == "stream":
                return _service_failure(
                    "stream_requires_event_lines",
                    "stream requests must be consumed with stream_payload",
                )
            return _service_failure(
                "unsupported_action",
                f"unsupported local service action: {action}",
            )
        except (TypeError, ValueError) as exc:
            return _service_failure("invalid_request", str(exc))

    def stream_payload(
        self,
        payload: Mapping[str, Any],
    ) -> Iterator[dict[str, JsonValue]]:
        """Yield service envelopes for one request.

        Non-stream actions yield a single normal response. Stream actions yield
        one event envelope per `ToolEvent`, then a final complete response.
        """

        try:
            self._authorize(payload)
            _validate_service_request(payload)
            action = _request_action(payload)
            if action != "stream":
                yield self.handle_payload(payload)
                return
            yield from self._stream(payload)
        except (TypeError, ValueError) as exc:
            yield _service_failure("invalid_request", str(exc))

    def _authorize(self, payload: Mapping[str, Any]) -> None:
        if self.token is None:
            return
        if payload.get("token") != self.token:
            raise ValueError("invalid local service token")

    def _run(
        self,
        payload: Mapping[str, Any],
        *,
        store: bool,
    ) -> dict[str, JsonValue]:
        request_id = _request_id(payload)
        command = _command_from_payload(payload)
        observation = self.app_control.run_command(command, observer=self.observer)
        observation_payload = _observation_to_dict(observation)
        if store:
            self._results[request_id] = observation_payload
        return _service_response(
            request_id=request_id,
            status="complete",
            observation=observation_payload,
        )

    def _poll(self, payload: Mapping[str, Any]) -> dict[str, JsonValue]:
        request_id = _required_request_id(payload)
        observation = self._results.get(request_id)
        if observation is None:
            return _service_response(request_id=request_id, status="not_found")
        return _service_response(
            request_id=request_id,
            status="complete",
            observation=observation,
        )

    def _stream(self, payload: Mapping[str, Any]) -> Iterator[dict[str, JsonValue]]:
        request_id = _request_id(payload)
        command = _command_from_payload(payload)
        final_observation: dict[str, JsonValue] | None = None

        if hasattr(self.app_control, "run_stream"):
            for event in self.app_control.run_stream(command, observer=self.observer):
                event_payload = _event_to_dict(event)
                observation = _observation_from_event(event_payload)
                if observation is not None:
                    final_observation = observation
                yield _service_event(request_id=request_id, event=event_payload)
        else:
            observer = _CollectingObserver()
            observation = self.app_control.run_command(
                command,
                observer=_tee_observers(observer, self.observer),
            )
            final_observation = _observation_to_dict(observation)
            for event_payload in observer.events:
                yield _service_event(request_id=request_id, event=event_payload)

        yield _service_response(
            request_id=request_id,
            status="complete",
            observation=final_observation,
        )


class UnixSocketCommandService:
    """Serve LocalCommandService requests over a Unix domain socket."""

    def __init__(
        self,
        socket_path: str | Path,
        service: LocalCommandService,
    ) -> None:
        self._socket_path = Path(socket_path).expanduser()
        self._service = service
        self._server: _UnixSocketServer | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    def serve_forever(self) -> None:
        with self:
            assert self._server is not None
            self._server.serve_forever()

    def serve_in_thread(self) -> threading.Thread:
        self.start()
        thread = threading.Thread(target=self._serve_existing, daemon=True)
        thread.start()
        return thread

    def start(self) -> None:
        if self._server is not None:
            raise LocalServiceError("local service is already started")
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            if not self._socket_path.is_socket():
                raise LocalServiceError(
                    f"socket path exists and is not a socket: {self._socket_path}"
                )
            self._socket_path.unlink()
        try:
            server = _UnixSocketServer(str(self._socket_path), _ServiceHandler)
        except OSError as exc:
            raise LocalServiceError(f"failed to start local service: {exc}") from exc
        try:
            self._socket_path.chmod(0o600)
        except OSError as exc:
            server.server_close()
            if self._socket_path.exists():
                self._socket_path.unlink()
            raise LocalServiceError(
                f"failed to restrict local service socket permissions: {exc}"
            ) from exc
        server.service = self._service
        self._server = server

    def shutdown(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self.close()

    def close(self) -> None:
        if self._server is None:
            return
        self._server.server_close()
        self._server = None
        if self._socket_path.exists():
            self._socket_path.unlink()

    def __enter__(self) -> "UnixSocketCommandService":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _serve_existing(self) -> None:
        assert self._server is not None
        self._server.serve_forever()


@dataclass(frozen=True)
class UnixSocketServiceClient:
    """Small client for a local Unix socket app-control service."""

    socket_path: str | Path
    token: str | None = None
    timeout: float = 30.0

    def request(self, payload: Mapping[str, Any]) -> list[dict[str, JsonValue]]:
        request_payload = dict(payload)
        if self.token is not None and "token" not in request_payload:
            request_payload["token"] = self.token
        return send_service_payload(
            self.socket_path,
            request_payload,
            timeout=self.timeout,
        )

    def run_command(
        self,
        command: Mapping[str, Any],
        *,
        action: str = "run",
        request_id: str | None = None,
    ) -> list[dict[str, JsonValue]]:
        payload: dict[str, JsonValue] = {
            "schema": SERVICE_REQUEST_SCHEMA,
            "action": action,
            "command": dict(command),
        }
        if request_id is not None:
            payload["requestId"] = request_id
        return self.request(payload)

    def poll(self, request_id: str) -> dict[str, JsonValue]:
        responses = self.request(
            {
                "schema": SERVICE_REQUEST_SCHEMA,
                "action": "poll",
                "requestId": request_id,
            }
        )
        if not responses:
            raise LocalServiceError("local service returned no response")
        return responses[-1]


def send_service_payload(
    socket_path: str | Path,
    payload: Mapping[str, Any],
    *,
    timeout: float = 30.0,
) -> list[dict[str, JsonValue]]:
    """Send one service payload and return all JSON-lines responses."""

    message = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":"))
    raw_responses: list[bytes] = []
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(Path(socket_path).expanduser()))
            client.sendall(message.encode("utf-8") + b"\n")
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                raw_responses.append(chunk)
    except OSError as exc:
        raise LocalServiceError(f"local service request failed: {exc}") from exc
    return _decode_service_responses(b"".join(raw_responses))


def service_envelope_to_sse(envelope: Mapping[str, Any]) -> str:
    """Format one service envelope as a Server-Sent Events frame."""

    status = envelope.get("status", "message")
    event_name = _sse_field(status if isinstance(status, str) else "message")
    lines: list[str] = []
    request_id = envelope.get("requestId")
    if isinstance(request_id, str) and request_id.strip():
        lines.append(f"id: {_sse_field(request_id)}")
    lines.append(f"event: {event_name}")
    data = json.dumps(dict(envelope), ensure_ascii=False, separators=(",", ":"))
    for line in data.splitlines() or ("",):
        lines.append(f"data: {line}")
    lines.append("")
    return "\n".join(lines) + "\n"


def service_envelopes_to_sse(
    envelopes: Iterable[Mapping[str, Any]],
) -> Iterator[str]:
    """Format service envelopes as Server-Sent Events frames."""

    for envelope in envelopes:
        yield service_envelope_to_sse(envelope)


class _UnixSocketServer(socketserver.UnixStreamServer):
    service: LocalCommandService


class _ServiceHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw_line = self.rfile.readline()
        for response in _handle_raw_lines(
            self.server.service,  # type: ignore[attr-defined]
            raw_line,
        ):
            self.wfile.write(
                json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
                + b"\n"
            )
            self.wfile.flush()


def _handle_raw_line(
    service: LocalCommandService,
    raw_line: bytes,
) -> dict[str, JsonValue]:
    responses = list(_handle_raw_lines(service, raw_line))
    return responses[0]


def _handle_raw_lines(
    service: LocalCommandService,
    raw_line: bytes,
) -> Iterator[dict[str, JsonValue]]:
    if not raw_line:
        yield _service_failure("empty_request", "local service request is empty")
        return
    try:
        payload = json.loads(raw_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        yield _service_failure("invalid_json", str(exc))
        return
    if not isinstance(payload, Mapping):
        yield _service_failure("invalid_request", "request must be a JSON object")
        return
    yield from service.stream_payload(payload)


def _decode_service_responses(raw_payload: bytes) -> list[dict[str, JsonValue]]:
    responses: list[dict[str, JsonValue]] = []
    for raw_line in raw_payload.split(b"\n"):
        if not raw_line:
            continue
        try:
            payload = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalServiceError(f"invalid local service response: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise LocalServiceError("local service response must be a JSON object")
        responses.append(_validate_decoded_service_envelope(payload))
    if not responses:
        raise LocalServiceError("local service returned no response")
    return responses


def _validate_decoded_service_envelope(
    payload: Mapping[str, Any],
) -> dict[str, JsonValue]:
    schema = payload.get("schema")
    try:
        if schema == SERVICE_RESPONSE_SCHEMA:
            return _validate_service_response(payload)
        if schema == SERVICE_EVENT_SCHEMA:
            return _validate_service_event(payload)
    except Exception as exc:
        raise LocalServiceError(f"invalid local service response: {exc}") from exc
    raise LocalServiceError(f"unsupported local service response schema: {schema!r}")


def _request_action(payload: Mapping[str, Any]) -> str:
    action = payload.get("action", "run")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    return action.strip()


def _request_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("requestId") or payload.get("request_id")
    if value is None:
        return "req_" + uuid4().hex
    if not isinstance(value, str) or not value.strip():
        raise ValueError("requestId must be a non-empty string")
    return value.strip()


def _required_request_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("requestId") or payload.get("request_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("poll requires requestId")
    return value.strip()


def _command_from_payload(payload: Mapping[str, Any]) -> dict[str, JsonValue]:
    command = payload.get("command")
    if command is None and "commandId" in payload:
        command = payload
    if not isinstance(command, Mapping):
        raise ValueError("request command must be a JSON object")
    tool_command_cls, _ = _protocol_models()
    return tool_command_cls.from_dict(dict(command)).to_dict()


def _observation_to_dict(observation: object) -> dict[str, JsonValue]:
    if hasattr(observation, "to_dict"):
        payload = observation.to_dict()
    elif isinstance(observation, Mapping):
        payload = dict(observation)
    else:
        raise TypeError("app-control client returned an unsupported observation")
    _, tool_observation_cls = _protocol_models()
    return tool_observation_cls.from_dict(payload).to_dict()


def _event_to_dict(event: object) -> dict[str, JsonValue]:
    if hasattr(event, "to_dict"):
        payload = event.to_dict()
    elif isinstance(event, Mapping):
        payload = dict(event)
    else:
        raise TypeError("app-control client returned an unsupported event")
    tool_event_cls = _tool_event_model()
    return tool_event_cls.from_dict(payload).to_dict()


def _observation_from_event(
    event: Mapping[str, JsonValue],
) -> dict[str, JsonValue] | None:
    data = event.get("data")
    if not isinstance(data, Mapping):
        return None
    observation = data.get("observation")
    if not isinstance(observation, Mapping):
        return None
    return _observation_to_dict(observation)


class _CollectingObserver:
    def __init__(self) -> None:
        self.events: list[dict[str, JsonValue]] = []

    def on_event(self, event: object) -> None:
        self.events.append(_event_to_dict(event))


class _TeeObserver:
    def __init__(self, observers: tuple[object, ...]) -> None:
        self._observers = observers

    def on_event(self, event: object) -> None:
        for observer in self._observers:
            handler = getattr(observer, "on_event", None)
            if callable(handler):
                handler(event)


def _tee_observers(*observers: object | None) -> object | None:
    active = tuple(observer for observer in observers if observer is not None)
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    return _TeeObserver(active)


def _service_response(
    *,
    request_id: str,
    status: str,
    observation: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "schema": SERVICE_RESPONSE_SCHEMA,
        "requestId": request_id,
        "status": status,
        "success": status == "complete",
    }
    if observation is not None:
        payload["observation"] = observation
    return _validate_service_response(payload)


def _service_event(
    *,
    request_id: str,
    event: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "schema": SERVICE_EVENT_SCHEMA,
        "requestId": request_id,
        "status": "event",
        "success": True,
        "event": event,
    }
    return _validate_service_event(payload)


def _service_failure(failure_kind: str, message: str) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "schema": SERVICE_RESPONSE_SCHEMA,
        "status": "failed",
        "success": False,
        "error": {
            "failureKind": failure_kind,
            "message": message,
            "retryable": False,
        },
    }
    return _validate_service_response(payload)


def _sse_field(value: str) -> str:
    sanitized = value.replace("\r", " ").replace("\n", " ").strip()
    return sanitized or "message"


def _protocol_models() -> tuple[type[Any], type[Any]]:
    try:
        from app_control_protocol import ToolCommand, ToolObservation
    except ImportError as exc:  # pragma: no cover - environment setup failure.
        raise RuntimeError(
            "local service mode requires the app-control-protocol package. "
            "Install app-control-protocol or add packages/app-control-protocol/src "
            "to PYTHONPATH in the monorepo checkout."
        ) from exc
    return ToolCommand, ToolObservation


def _validate_service_request(payload: Mapping[str, Any]) -> dict[str, JsonValue]:
    return _validate_protocol_payload("service_request", payload)


def _validate_service_response(payload: Mapping[str, Any]) -> dict[str, JsonValue]:
    return _validate_protocol_payload("service_response", payload)


def _validate_service_event(payload: Mapping[str, Any]) -> dict[str, JsonValue]:
    return _validate_protocol_payload("service_event", payload)


def _validate_protocol_payload(
    schema_name: str,
    payload: Mapping[str, Any],
) -> dict[str, JsonValue]:
    try:
        from app_control_protocol import validate_protocol_payload
    except ImportError as exc:  # pragma: no cover - environment setup failure.
        raise RuntimeError(
            "local service schema validation requires the app-control-protocol "
            "package. Install app-control-protocol or add "
            "packages/app-control-protocol/src to PYTHONPATH in the monorepo "
            "checkout."
        ) from exc
    return validate_protocol_payload(schema_name, payload)


def _tool_event_model() -> type[Any]:
    try:
        from app_control_protocol import ToolEvent
    except ImportError as exc:  # pragma: no cover - environment setup failure.
        raise RuntimeError(
            "local service event streaming requires app-control-protocol. "
            "Install app-control-protocol or add packages/app-control-protocol/src "
            "to PYTHONPATH in the monorepo checkout."
        ) from exc
    return ToolEvent
