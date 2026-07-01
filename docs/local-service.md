# Local Service Mode

`computer-use-macos` can expose the app-control protocol over a local Unix
domain socket. This is for non-Python callers on the same machine.

It is not a remote control protocol, task queue, audit store, or authorization
system. Callers must still decide whether a command is allowed before sending
it.

## Start

```bash
cp examples/app-control.toml app-control.toml
.venv/bin/computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

Use the entrypoint from the same environment where the editable packages were
installed. For example, if installation used `uv pip install --python
.venv/bin/python ...`, start `.venv/bin/computer-use-macos`; a globally
installed `computer-use-macos` may run a different Python and miss PyObjC
modules such as `ApplicationServices`.

When `app-control.toml` contains `[helper] endpoint` and optional `token`, the
same service can be started from the shared config alone:

```bash
.venv/bin/computer-use-macos serve \
  --config ./app-control.toml
```

The service builds its backend and event observer from the shared
`AppControlConfig`, so app allowlists, helper backend selection, timeout
settings, and `[logging]` event routing stay in one place.

`computer-use-macos serve` requires `--token`, `--token-file`, or `helper.token`
in `--config` by default. Explicit CLI values take precedence over config.
`--allow-unauthenticated` is available only for isolated local tests where the
socket path and process environment are already controlled.

On start, the server refuses to replace an existing non-socket file at
`--socket-path`. A newly bound Unix socket is restricted to `0600` filesystem
permissions.

## Request

Send one JSON object terminated by a newline:

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

Requests are validated against the packaged `app_control.service.request.v1`
schema, and service responses/events are validated before being returned.
Include `schema` and `action` in every request envelope.

Supported actions:

- `run`: execute the command and return the observation immediately.
- `submit`: execute the command, store the observation, and return `requestId`.
- `poll`: return the stored observation for a previous `requestId`.
- `stream`: execute the command and return JSON-lines service event envelopes,
  followed by a final service response.

Execution is synchronous in the local process. The `submit`/`poll` shape gives
non-Python callers a stable polling contract without turning the package into a
durable task system.

`stream` is still local and synchronous, but it lets non-Python callers consume
the same `ToolEvent` progress surface exposed by `run_stream(command)`.

## Response

```json
{
  "schema": "app_control.service.response.v1",
  "requestId": "req_1",
  "status": "complete",
  "success": true,
  "observation": {
    "schema": "app_control.observation.v1",
    "commandId": "cmd_1",
    "tool": "macos.computer_use",
    "operation": "readiness",
    "status": "ok",
    "success": true,
    "summary": "ready",
    "observation": {}
  }
}
```

Polling a missing request returns `status: "not_found"` and `success: false`.
Invalid JSON, unsupported actions, and bad local tokens return a service-level
failure envelope.

## Event Stream

For `action: "stream"`, the Unix socket response contains multiple newline
terminated JSON objects. Event lines use `app_control.service.event.v1`:

```json
{
  "schema": "app_control.service.event.v1",
  "requestId": "req_1",
  "status": "event",
  "success": true,
  "event": {
    "schema": "app_control.event.v1",
    "commandId": "cmd_1",
    "seq": 0,
    "type": "started",
    "phase": "readiness"
  }
}
```

The final line is a normal `app_control.service.response.v1` envelope with
`status: "complete"` and the final observation. Callers should read until they
receive a line whose `status` is not `event`.

## CLI Client

The package also includes a small socket client for smoke checks and non-Python
integration debugging:

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness \
  --command-id cmd_readiness
```

For full command envelopes:

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --command-json '{"commandId":"cmd_1","tool":"macos.computer_use","operation":"observe","input":{"targetApp":"TextEdit"}}'
```

`request --config ./app-control.toml` also reads `[helper] endpoint`, optional
`token`, and `computer_use.timeout_ms` when the matching CLI argument is not
supplied.

For event streams, the CLI prints JSON-lines by default and can also format
frames as SSE:

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --action stream \
  --operation readiness \
  --sse
```

## SSE Formatting

The package does not start an HTTP server. Applications that expose their own
HTTP endpoint can format local service envelopes as Server-Sent Events:

```python
from computer_use_macos.service import service_envelopes_to_sse

frames = service_envelopes_to_sse(service.stream_payload(payload))
```

Each frame uses the envelope `requestId` as the SSE `id`, the envelope `status`
as the SSE `event`, and the complete service envelope as JSON `data`.

## Python Embedding

```python
from computer_use_macos import ComputerUseClient
from computer_use_macos.service import (
    LocalCommandService,
    UnixSocketCommandService,
    UnixSocketServiceClient,
)

app_control = ComputerUseClient.from_config("app-control.toml")
service = LocalCommandService(app_control, token="local-token")
server = UnixSocketCommandService("/tmp/app-control.sock", service)
server.serve_forever()
```

Clients embedded in Python can use the same socket protocol:

```python
client = UnixSocketServiceClient("/tmp/app-control.sock", token="local-token")
responses = client.run_command(
    {
        "commandId": "cmd_readiness",
        "tool": "macos.computer_use",
        "operation": "readiness",
    }
)
```
