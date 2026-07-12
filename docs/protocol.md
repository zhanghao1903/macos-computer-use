# App Control Protocol

The app-control protocol exposes local automation as explicit commands and
factual observations.

Core flow:

```text
ToolCommand -> ToolObservation
ToolCommand -> ToolEvent* -> ToolObservation
```

The protocol package owns:

- command envelopes;
- observation envelopes;
- stream events;
- structured tool errors;
- packaged JSON Schema documents;
- app-control client protocols;
- developer-editable configuration models.

The protocol package does not own:

- LLM decisions;
- user authorization;
- task lifecycle;
- product UI;
- audit persistence;
- helper app implementation;
- app-specific automation logic.

## Command

The package ships JSON Schema documents for non-Python callers:

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

Python callers can load the same packaged assets:

```python
from app_control_protocol import load_protocol_schema, validate_protocol_payload

command_schema = load_protocol_schema("command")
validate_protocol_payload("command", payload)
```

```json
{
  "schema": "app_control.command.v1",
  "commandId": "cmd_123",
  "tool": "macos.computer_use",
  "operation": "open_app",
  "input": {"app": "TextEdit"},
  "timeoutMs": 10000,
  "metadata": {"caller": "example-app"}
}
```

`macos.computer_use` currently supports these protocol operations:

- `readiness`
- `observe`
- `open_app`
- `focus_app`
- `click`
- `type_text`
- `press_key`
- `hotkey`
- `wait`

`click` accepts either a semantic target:

```json
{"target": "OK", "targetApp": "TextEdit"}
```

or a bounded Accessibility selector in the target app's front window:

```json
{
  "targetApp": "TextEdit",
  "selector": {"role": "button", "name": "OK"}
}
```

or explicit screen coordinates:

```json
{"coordinates": {"x": 120, "y": 240}}
```

Selector clicks require `targetApp`. The first selector surface intentionally
allows only a small role set such as `button`, `checkbox`, `menu_item`,
`radio_button`, `pop_up_button`, and `text_field`, addressed by
`name`/`title`/`label`/`description` or a 1-based `index`.

Coordinate click is disabled unless the backend is configured with
`allow_coordinate_click = true`.

`readiness` observations include both backward-compatible flat fields and the
structured shape expected by app-control callers:

```json
{
  "status": "ready",
  "platform": "Darwin",
  "permissions": {
    "accessibility": true,
    "screenRecording": null,
    "appleEvents": null
  },
  "helper": {
    "installed": false,
    "running": false
  },
  "enabledOperations": [
    "observe",
    "open_app",
    "focus_app",
    "click",
    "type_text",
    "press_key",
    "hotkey",
    "wait"
  ]
}
```

`screenRecording` and `appleEvents` are nullable because some hosts cannot
preflight Screen Recording, and Apple Events permission is target-app specific.

## Observation

```json
{
  "schema": "app_control.observation.v1",
  "commandId": "cmd_123",
  "tool": "macos.computer_use",
  "operation": "open_app",
  "status": "ok",
  "success": true,
  "summary": "Opened app.",
  "observation": {"app": "TextEdit"},
  "timing": {
    "startedAt": "2026-06-28T12:00:00Z",
    "durationMs": 42
  }
}
```

SDK implementations populate `timing.startedAt` and `timing.durationMs` for
observations produced by `run_command` and final `run_stream` events.

`status` is intentionally small and stable:

- `ok`
- `not_found`
- `not_ready`
- `permission_missing`
- `timeout`
- `failed`
- `unknown`

`success` must be `true` only when `status` is `ok`.

Failure observations keep simple top-level error fields and may also carry the
complete nested `ToolError` object:

```json
{
  "schema": "app_control.observation.v1",
  "commandId": "cmd_124",
  "tool": "macos.computer_use",
  "operation": "open_app",
  "status": "failed",
  "success": false,
  "summary": "App is not allowlisted.",
  "failureKind": "app_not_allowlisted",
  "message": "App is not allowlisted.",
  "recoveryHint": "Add the app to allowed_apps.",
  "retryable": false,
  "observation": {},
  "evidence": {"app": "Messages"},
  "error": {
    "failureKind": "app_not_allowlisted",
    "message": "App is not allowlisted.",
    "recoveryHint": "Add the app to allowed_apps.",
    "retryable": false,
    "phase": "policy",
    "operation": "open_app",
    "evidence": {"app": "Messages"}
  }
}
```

## Event

```json
{
  "schema": "app_control.event.v1",
  "commandId": "cmd_123",
  "seq": 1,
  "type": "progress",
  "phase": "open_app",
  "status": "ok",
  "summary": "App launch requested."
}
```

Python callers may consume events as a stream or through a callback object:

```python
class Observer:
    def on_event(self, event):
        print(event.to_dict())

client.run_command(command, observer=Observer())
```

The protocol package also ships a default logging observer:

```python
from app_control_protocol import build_logging_observer

observer = build_logging_observer(config)
client.run_command(command, observer=observer)
```

The package exports the client interface consumed by higher-level tools:

```python
from app_control_protocol import AppControlClient

def run_backend(client: AppControlClient, command):
    return client.run_command(command)
```

The Python client and observer protocols are runtime-checkable structural
interfaces:

```python
from app_control_protocol import AppControlClient, ToolObserver

assert isinstance(client, AppControlClient)
assert isinstance(observer, ToolObserver)
```

Runtime protocol checks verify method presence only. Command, observation,
event, and service payloads should still be validated against the packaged JSON
schemas.

## Local Service Envelope

`computer-use-macos` can expose the same command envelope through a local Unix
domain socket for non-Python callers. The service envelope wraps the command and
optionally carries a local token:

```json
{
  "schema": "app_control.service.request.v1",
  "action": "run",
  "token": "local-token",
  "command": {
    "schema": "app_control.command.v1",
    "commandId": "cmd_1",
    "tool": "macos.computer_use",
    "operation": "readiness",
    "input": {}
  }
}
```

Responses use `app_control.service.response.v1` and include a
`ToolObservation` when the request reaches `complete`.

Python callers can build the same envelopes without hand-writing the wire
payload:

```python
from app_control_protocol import (
    ServiceEventEnvelope,
    ServiceRequest,
    ServiceResponse,
    ToolCommand,
    ToolEvent,
    ToolObservation,
)

command = ToolCommand(
    command_id="cmd_1",
    tool="macos.computer_use",
    operation="readiness",
)
request = ServiceRequest.run(command, token="local-token")

observation = ToolObservation.ok(
    command_id="cmd_1",
    tool="macos.computer_use",
    operation="readiness",
    summary="ready",
)
response = ServiceResponse.complete(observation, request_id="req_1")
event = ServiceEventEnvelope(
    request_id="req_1",
    event=ToolEvent(command_id="cmd_1", seq=0, event_type="started"),
)

request_payload = request.to_dict()
response_payload = response.to_dict()
event_payload = event.to_dict()
```

## Configuration

The shared configuration model is intentionally small and developer-editable.
Concrete packages may extend it with package-local options while preserving the
same top-level shape:

Use `examples/app-control.toml` as a complete editable starting point.

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

[helper]
transport = "unix_socket"
auto_launch = true

[wechat]
app_name = "WeChat"
bundle_id = "com.tencent.xinWeChat"
app_control_tool = "macos.computer_use"
# Optional custom selector profile. Invalid files fall back to the packaged
# WeChat selector profile.
# selector_profile_path = "./profiles/wechat-local.toml"
# Legacy compatibility fields. Selector-backed open_contact owns normal contact
# switching in 0.2.0.
search_hotkey = ["Command", "F"]
search_clear_hotkey = ["Command", "A"]
clear_key = "Delete"
submit_key = "Return"
max_message_chars = 2000
default_timeout_ms = 30000
```

Common environment overrides are also supported for smoke tests and CI:

| Environment Variable | Config Field |
|---|---|
| `APP_CONTROL_LOG_LEVEL` | `logging.level` |
| `APP_CONTROL_LOG_JSON` | `logging.json` |
| `APP_CONTROL_COMPUTER_USE_BACKEND` | `computer_use.backend` |
| `APP_CONTROL_COMPUTER_USE_ALLOWED_APPS` | `computer_use.allowed_apps` |
| `APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS` | `computer_use.allowed_app_bundle_ids` as `App=bundle.id,Other=com.example.Other` |
| `APP_CONTROL_COMPUTER_USE_TIMEOUT_MS` | `computer_use.timeout_ms` |
| `APP_CONTROL_HELPER_APP_PATH` | `helper.helper_app_path` |
| `APP_CONTROL_HELPER_BUNDLE_ID` | `helper.bundle_id` |
| `APP_CONTROL_HELPER_ENDPOINT` | `helper.endpoint` |
| `APP_CONTROL_HELPER_TOKEN` | `helper.token` |
| `APP_CONTROL_WECHAT_APP_NAME` | `wechat.app_name` |
| `APP_CONTROL_WECHAT_BUNDLE_ID` | `wechat.bundle_id` |
| `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH` | `wechat.selector_profile_path` |
| `APP_CONTROL_WECHAT_MAX_MESSAGE_CHARS` | `wechat.max_message_chars` |
| `APP_CONTROL_WECHAT_DEFAULT_TIMEOUT_MS` | `wechat.default_timeout_ms` |
