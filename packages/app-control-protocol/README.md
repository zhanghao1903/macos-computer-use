# app-control-protocol

Shared protocol models for app-control tools.

This package defines the stable public contract used by `computer-use-macos`,
`wechat-desktop-tool`, and third-party callers:

- `ToolCommand`
- `ToolObservation`
- `ToolEvent`
- `ToolError`
- `ServiceRequest`
- `ServiceResponse`
- `ServiceEventEnvelope`
- `AppControlClient`
- `AppControlConfig`
- `LoggingToolObserver`
- packaged JSON Schema files for command, observation, event, error, and
  local service envelopes

It has no runtime dependencies and does not import product-specific modules,
LLM SDKs, UI frameworks, or app-control backend implementations.

Observation status values are stable: `ok`, `not_found`, `not_ready`,
`permission_missing`, `timeout`, `failed`, and `unknown`.

## Example

```python
from app_control_protocol import ToolCommand

command = ToolCommand(
    command_id="cmd_1",
    tool="macos.computer_use",
    operation="open_app",
    input={"app": "TextEdit"},
    timeout_ms=10_000,
)

payload = command.to_dict()
round_tripped = ToolCommand.from_dict(payload)
assert round_tripped == command
```

## JSON Schemas

Schema assets are included in the wheel for non-Python callers:

```text
app_control_protocol/schemas/command.schema.json
app_control_protocol/schemas/observation.schema.json
app_control_protocol/schemas/event.schema.json
app_control_protocol/schemas/error.schema.json
app_control_protocol/schemas/service-request.schema.json
app_control_protocol/schemas/service-response.schema.json
app_control_protocol/schemas/service-event.schema.json
app_control_protocol/schemas/helper-request.schema.json
app_control_protocol/schemas/helper-response.schema.json
```

Python callers can load the same packaged files:

```python
from app_control_protocol import ProtocolValidationError, load_protocol_schema
from app_control_protocol import validate_protocol_payload

command_schema = load_protocol_schema("command")

try:
    validate_protocol_payload("command", payload)
except ProtocolValidationError as exc:
    print(exc)
```

## Client Protocol

```python
from app_control_protocol import AppControlClient

def use_client(client: AppControlClient) -> None:
    observation = client.run_command(command)
    print(observation.to_dict())
```

`AppControlClient`, `StreamingAppControlClient`, and `ToolObserver` are
`runtime_checkable` protocols, so integrations can do a lightweight structural
check before wiring tools together:

```python
from app_control_protocol import AppControlClient

if not isinstance(client, AppControlClient):
    raise TypeError("app-control client must expose run_command(...)")
```

This checks the presence of protocol methods. Payload correctness is still
validated with `validate_protocol_payload(...)`.

## Errors

Failed observations can embed a complete `ToolError` while keeping top-level
failure fields for simpler callers:

```python
from app_control_protocol import ToolError, ToolObservation

error = ToolError(
    failure_kind="not_ready",
    message="Helper is not running.",
    retryable=True,
    phase="readiness",
    operation="readiness",
)

failure = ToolObservation.failure(
    command_id="cmd_1",
    tool="macos.computer_use",
    operation="readiness",
    status="not_ready",
    error=error,
)
```

## Local Service Envelopes

Use the service envelope models when submitting commands to a local
`computer-use-macos` service:

```python
from app_control_protocol import ServiceRequest, ToolCommand

command = ToolCommand(
    command_id="cmd_1",
    tool="macos.computer_use",
    operation="readiness",
)

request_payload = ServiceRequest.run(command, token="local-token").to_dict()
poll_payload = ServiceRequest.poll("req_1").to_dict()
```

## Event Logging

```python
from app_control_protocol import build_logging_observer

observer = build_logging_observer()
client.run_command(command, observer=observer)
```

## Configuration

The repository includes a complete editable template at
`examples/app-control.toml`.

```toml
[logging]
level = "info"
redact_text = true

[computer_use]
backend = "direct"
allowed_apps = ["TextEdit", "WeChat"]

[computer_use.allowed_app_bundle_ids]
TextEdit = "com.apple.TextEdit"
WeChat = "com.tencent.xinWeChat"

[wechat]
app_name = "WeChat"
bundle_id = "com.tencent.xinWeChat"
app_control_tool = "macos.computer_use"
search_hotkey = ["Command", "K"]
search_clear_hotkey = ["Command", "A"]
clear_key = "Delete"
submit_key = "Return"
max_message_chars = 2000
default_timeout_ms = 30000
```

Smoke tests and CI can override runtime values with environment variables such
as `APP_CONTROL_COMPUTER_USE_BACKEND`,
`APP_CONTROL_COMPUTER_USE_ALLOWED_APPS`,
`APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS`,
`APP_CONTROL_HELPER_ENDPOINT`,
`APP_CONTROL_HELPER_TOKEN`, `APP_CONTROL_WECHAT_BUNDLE_ID`,
`APP_CONTROL_WECHAT_MAX_MESSAGE_CHARS`, and `APP_CONTROL_WECHAT_DEFAULT_TIMEOUT_MS`.
