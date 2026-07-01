# API Contract

`computer-use-macos` exposes deterministic primitives. It does not expose an
LLM action interpreter.

## Client

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient(
    allowed_apps=("TextEdit",),
    enabled=True,
    allow_coordinate_click=False,
)
```

Or build from shared app-control configuration:

```python
client = ComputerUseClient.from_config("app-control.toml")
```

For direct backends this returns the macOS direct client. For helper backends it
discovers the helper manifest and returns a helper transport client with the
same `run_command(command)` and `run_stream(command)` protocol surface:

```toml
[computer_use]
backend = "helper"
timeout_ms = 10000

[helper]
manifest_path = "./helper_config.json"
bundle_id = "com.example.computer-use-helper"
```

When the helper app path is known, the client also discovers the generated
manifest at `Contents/Resources/helper_config.json`:

```toml
[computer_use]
backend = "helper"
allowed_apps = ["TextEdit"]

[helper]
helper_app_path = "/Applications/Example Computer Use Helper.app"
bundle_id = "com.example.computer-use-helper"
allowed_apps = ["TextEdit"]
```

The helper backend can also be configured without a manifest when the local
socket endpoint is already known:

```toml
[computer_use]
backend = "helper"

[helper]
transport = "unix_socket"
bundle_id = "com.example.computer-use-helper"
endpoint = "/tmp/example-computer-use-helper.sock"
token = "optional-local-token"
```

The distribution exposes the `ComputerUseClient` factory, shared
`AppControlConfig`, and helper config/model constructors:

```python
from computer_use_macos import ComputerUseClient, HelperConfig

client = ComputerUseClient(
    HelperConfig(
        helper_app_path="/Applications/Example Computer Use Helper.app",
        bundle_id="com.example.computer-use-helper",
        allowed_apps=("TextEdit",),
    )
)
```

## Methods

| Method | Purpose | Mutates Desktop |
|---|---|---:|
| `run_command(command)` | Run a protocol command envelope. | Depends |
| `run_stream(command)` | Run a command and yield protocol events. | Depends |
| `readiness()` | Report platform and permission state. | No |
| `observe(target_app=None, bundle_id=None)` | Return bounded frontmost-app/window summary. | No |
| `open_app(app, bundle_id=None)` | Open an allowlisted app. | Yes |
| `focus_app(app, bundle_id=None)` | Activate an allowlisted app. | Yes |
| `click(target, target_app=..., bundle_id=None)` | Click a low-risk semantic target. | Yes |
| `click_accessibility(selector, target_app=..., bundle_id=None)` | Click a bounded Accessibility selector. | Yes |
| `click_coordinate(x, y, target_app=None, bundle_id=None)` | Click enabled screen coordinates. | Yes |
| `type_text(text, target_app=None, bundle_id=None)` | Type bounded text into focused input. | Yes |
| `press_key(key, target_app=None, bundle_id=None)` | Press one key in the focused target. | Yes |
| `hotkey(keys, target_app=None, bundle_id=None)` | Press one key with modifiers. | Yes |
| `wait(seconds=1.0)` | Sleep for bounded workflow pacing. | No |

Direct backend convenience methods return `ComputerUseResult` for compatibility
with the original package. Helper-backed convenience methods returned by
`ComputerUseClient.from_helper_manifest(...)` or helper `from_config(...)`
return `ToolObservation`, matching the helper command/observation boundary.

`readiness().to_dict()` includes a structured `permissions` object,
structured `helper` object, and `enabledOperations` list in addition to the
legacy flat dataclass fields. Screen Recording readiness is a best-effort
non-prompting preflight value and may be `null` when the host cannot probe it.
Apple Events readiness may also be `null` because macOS Automation permission
is target-app specific.

Keyboard and text primitives include structured action facts. Direct SDK
results keep these in `ComputerUseResult.metadata`. Protocol observations also
promote stable JSON fields to `observation`: `type_text` returns `chars`,
`submitted=false`, and `actionAttempted=true`; `press_key` returns the
normalized `key`; and `hotkey` returns `keys`, `key`, and `modifiers`. When
`target_app` is supplied and the target observation succeeds, protocol
observations also include `targetSummary`, `targetSnapshotId`, `frontmostApp`,
and `windowTitle`. When `bundle_id` is supplied, direct macOS execution uses it
for app open/focus and protocol observations include `bundleId` plus
`frontmostBundleId` when available. The nested `observation.metadata` object is
kept for compatibility with the direct SDK metadata names.

`observe` accepts two Accessibility opt-ins through protocol input:
`includeAccessibility` returns a bounded focused-element/text-field summary,
while `includeAccessibilityTree` asks the backend for the focused window's raw
Accessibility tree under `observation.accessibility.focusedWindow`. The tree
can contain contact names, visible message text, and other private UI data, so
callers should request it only when they are about to normalize it into a
domain model such as `wechat.window.v1` or write it to an explicit raw-data
debug log.

## Protocol Entry

`run_command` accepts either a `ToolCommand` from `app-control-protocol` or a
command payload mapping. It returns a `ToolObservation`. Observations emitted by
the SDK include `timing.startedAt` and `timing.durationMs`.

```python
from app_control_protocol import ToolCommand
from computer_use_macos import ComputerUseClient

client = ComputerUseClient(allowed_apps=("TextEdit",))
result = client.run_command(
    ToolCommand(
        command_id="cmd_1",
        tool="macos.computer_use",
        operation="open_app",
        input={"app": "TextEdit"},
        timeout_ms=10_000,
    )
)
```

For bundle-id-specific allowlists, pass a mapping or set
`computer_use.allowed_app_bundle_ids` in `AppControlConfig`:

```python
client = ComputerUseClient(
    allowed_apps={"TextEdit": "com.apple.TextEdit"},
)
```

`computer-use-macos` also exports command builders so callers do not have to
hand-write the envelope:

```python
from computer_use_macos import ComputerUseClient, open_app_command

client = ComputerUseClient.from_config("app-control.toml")
result = client.run_command(open_app_command("TextEdit", timeout_ms=10_000))
```

Coordinate click is disabled by default. A caller must construct the client
with `allow_coordinate_click=True`, and protocol callers must send explicit
coordinates:

```python
client = ComputerUseClient(
    allowed_apps=("TextEdit",),
    allow_coordinate_click=True,
)
result = client.run_command(
    ToolCommand(
        command_id="cmd_click_1",
        tool="macos.computer_use",
        operation="click",
        input={"coordinates": {"x": 120, "y": 240}},
    )
)
```

Accessibility selector click is available through the same `click` operation.
It requires `targetApp` and a bounded selector object:

```python
result = client.run_command(
    ToolCommand(
        command_id="cmd_click_selector_1",
        tool="macos.computer_use",
        operation="click",
        input={
            "targetApp": "TextEdit",
            "selector": {"role": "button", "name": "OK"},
        },
    )
)
```

Callers that need progress routing can use an observer callback or iterate the
stream:

```python
from app_control_protocol import build_logging_observer

observer = build_logging_observer()
client.run_command(command, observer=observer)

for event in client.run_stream(command):
    print(event.to_dict())
```

Supported protocol operations in this migration entrypoint:

- `readiness`
- `observe`
- `open_app`
- `focus_app`
- `click`
- `type_text`
- `press_key`
- `hotkey`
- `wait`

Unsupported operations return a structured failed `ToolObservation`.

## Local Service

Non-Python callers can send the same command envelopes over a local Unix domain
socket:

```bash
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

If `[helper] endpoint` and optional `token` are set in `app-control.toml`, the
serve command can use them directly and explicit CLI values still take
precedence.

The service supports `run`, `submit`, `poll`, and `stream` request actions.
Stream requests return `app_control.service.event.v1` JSON lines followed by a
final `app_control.service.response.v1` envelope. HTTP wrappers can reuse
`service_envelopes_to_sse(...)` to format those envelopes as SSE frames. See
[local-service.md](local-service.md) for the wire format.

The package also provides a small socket client and CLI for local smoke checks:

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness
```

`computer-use-macos request --config ./app-control.toml --operation readiness`
uses `[helper] endpoint`, optional `token`, and `computer_use.timeout_ms` from
the shared config when the matching CLI argument is omitted.

```python
from computer_use_macos import UnixSocketServiceClient

client = UnixSocketServiceClient("/tmp/app-control.sock", token="local-token")
responses = client.run_command(
    {
        "commandId": "cmd_readiness",
        "tool": "macos.computer_use",
        "operation": "readiness",
    }
)
```

## Statuses

Protocol callers receive `ToolObservation.status` from the shared
`app-control-protocol` status set:

| Protocol Status | Meaning |
|---|---|
| `ok` | Operation completed and the observation is successful. |
| `not_found` | The requested app, window, contact, or target was verified missing. |
| `not_ready` | The backend, app, focus, login, or helper is not ready. |
| `permission_missing` | A required macOS permission is missing. |
| `timeout` | Command execution exceeded the configured timeout. |
| `failed` | Operation failed or was refused with structured diagnostics. |
| `unknown` | The tool cannot prove whether a side-effecting action succeeded. |

Direct primitive methods return `ComputerUseResult.status`, which is a local
backend status. `run_command(...)` maps that status into the protocol set and
preserves the original value in `observation.metadata.legacyStatus`.

| Direct `ComputerUseResult.status` | Protocol `ToolObservation.status` |
|---|---|
| `ok` | `ok` |
| `blocked` | `failed` |
| `needs_user` | `not_ready` |
| `not_available` | `not_ready` |
| `timeout` | `timeout` |
| `failed` | `failed` |

## Confirmation Boundary

The package does not create or store confirmations. For high-risk operations it
returns a direct `ComputerUseResult` with `status="blocked"` and risk metadata:

```json
{
  "status": "blocked",
  "risk": {
    "level": "high",
    "requires_confirmation": true,
    "risk_label": "high_risk_click"
  },
  "metadata": {
    "confirmation_required": true,
    "confirmation_title": "Confirm desktop action"
  }
}
```

Protocol callers receive `ToolObservation.status="failed"` with the same
refusal represented as `failureKind`, nested `error`, and structured
observation metadata.

## Failure Kinds

Tool-specific packages expose stable failure kind tuples for callers that want
to route errors without hard-coding strings:

```python
from computer_use_macos import COMPUTER_USE_FAILURE_KINDS
from wechat_desktop_tool import WECHAT_FAILURE_KINDS
```

These constants cover package-owned failures such as `invalid_input`,
`coordinate_click_disabled`, `app_not_allowlisted`, `contact_not_found`,
`draft_failed`, and `submit_unknown`. A tool may still propagate a lower-level
`failureKind` from another compatible app-control client in nested evidence.

The caller must own:

- user-facing confirmation UI;
- durable confirmation storage;
- action authorization;
- audit/evidence records;
- retry behavior after confirmation resolves.

## Package Boundary

This package must remain independent from:

- Plato / Taskweavn;
- LLM providers;
- Agent frameworks;
- UI frameworks;
- remote task networking.
