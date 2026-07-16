# API Contract

This document is the stable public API reference for the package suite:

| Package | Import | Responsibility |
|---|---|---|
| `app-control-protocol` | `app_control_protocol` | Shared command, observation, event, error, config, service envelope, and schema contracts. |
| `computer-use-macos` | `computer_use_macos` | macOS readiness, app focus/open, scoped Accessibility reads, keyboard/text/click primitives, helper transport, local service, and CLI. |
| `wechat-desktop-tool` | `wechat_desktop_tool` | WeChat-specific normalized window, contact, conversation, message, and send/draft operations on top of an injected app-control client. |

The packages expose deterministic primitives and semantic desktop-tool APIs.
They do not include an LLM action interpreter, planner, confirmation store,
remote task queue, UI, or product-specific authorization layer.

## Stability And Ownership

Treat these as public or semi-public API:

- import paths, exported symbols, command builders, config models, and CLI
  commands;
- `ToolCommand`, `ToolObservation`, `ToolEvent`, `ToolError`, and local service
  envelope JSON shapes;
- protocol operation names and package-owned `failureKind` values;
- `computer-use-macos` operation payloads and `observation` fields;
- `wechat-desktop-tool` semantic response schemas such as `wechat.window.v1`,
  `wechat.contacts.v1`, `wechat.conversations.v1`, and `wechat.messages.v1`.

Raw macOS Accessibility data is an implementation detail unless a method
explicitly documents it as debug output. Application callers should use
normalized models, visible information lists, command builders, and stable
action/failure metadata instead of depending on raw AX tree shape.

Only operations listed in this document should be treated as stable. Drafts
under [feature/](feature/) describe candidate APIs such as
`accessibility_action`; they are not stable package-consumer contracts until
the implementation, tests, and this API reference all agree.

## Choosing An Entry Point

- Use direct `ComputerUseClient(...)` for local development and smoke tests.
- Use `ComputerUseClient.from_config("app-control.toml")` when the caller owns
  a shared app-control configuration.
- Use helper mode when a signed helper app should be the stable macOS
  permission subject.
- Use `computer-use-macos serve` and `UnixSocketServiceClient` when the caller
  is not Python or needs a separate local process boundary.
- Use `WeChatDesktopTool` only for WeChat domain operations; keep generic macOS
  automation in `computer-use-macos`.

The caller remains responsible for business authorization, user confirmation,
durable audit, retry policy, and any LLM/planner loop.

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
| `accessibility_query(target_app=None, bundle_id=None, root=None, query=None)` | Return scoped macOS Accessibility nodes for a target app/window. | No |
| `accessibility_action(target_app=None, bundle_id=None, target=..., action="AXPress")` | Execute a verified Accessibility action such as `AXPress`. | Yes |
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

For new UI-model APIs, prefer `accessibility_query` over
`observe(includeAccessibilityTree=true)`. `accessibility_query` reads only the
requested subtree and attributes, returns normalized `nodes`, and avoids
exposing raw `attributeNames` to application callers.

The query `root.kind` can be `focusedWindow`, `frontmostApp`, or `axPath`.
`focusedWindow` is the default window-rooted query. `frontmostApp` reads from
the target application's AX root and can still return app-level nodes when no
focused AX window is available. `axPath` accepts either focused-window paths
such as `0/12/0` or app-root paths such as `app/0`; app-root paths are intended
for scoped reads and are not valid `accessibility_action` targets.

Example protocol command:

```python
from computer_use_macos import accessibility_query_command

result = client.run_command(
    accessibility_query_command(
        target_app="WeChat",
        bundle_id="com.tencent.xinWeChat",
        root={"kind": "focusedWindow"},
        query={
            "scope": "children",
            "maxDepth": 1,
            "limit": 80,
            "attributes": [
                "AXRole",
                "AXDescription",
                "AXValue",
                "AXPosition",
                "AXSize",
            ],
            "actions": True,
            "includeChildRoles": True,
            "includeDescendantRoles": True,
        },
    )
)
```

`includeChildRoles` and `includeDescendantRoles` return bounded role-name
summaries for structural matching. They are intended for selector engines and
semantic adapters that need to verify UI shape without returning full child
subtrees.

Use `accessibility_action` for elements that expose stable AX actions such as
`AXPress`. The direct backend validates the target app allowlist, resolves the
snapshot-local `axPath`, checks preconditions, and then calls
`AXUIElementPerformAction`.

On the direct backend, bounded Accessibility queries and actions use separate
prewarmed worker processes. Successful payloads expose
`diagnostics.transport.mode` as `worker` or `subprocess`. A worker protocol
failure may fall back once for a read-only query. Actions are never replayed
after a worker request: worker timeout or protocol failure is returned directly
because the action may already have been attempted. The original action
subprocess remains the fallback only when no action worker is available before
dispatch. Helper behavior is unchanged.

Successful worker-backed actions expose
`diagnostics.transport.requestDispatched`; timeout observations expose the same
field at
`observation.metadata.accessibility_action_transport.requestDispatched`. A
value of `false` means the request deadline expired before any worker write and
the timeout is safe to retry. A value of `true` means dispatch was attempted;
if its result is unknown, the timeout is not retryable. When dispatch state is
unavailable, action timeouts are conservatively not retryable. The top-level
observation and nested `ToolError` always carry the same `retryable` value.

Higher-level adapters must preserve this no-replay boundary. The packaged
WeChat adapter permits one alternative mutation only when the result explicitly
proves `requestDispatched=false` and `retryable=true`, or when the backend
explicitly reports an unsupported Accessibility action without reporting that
the action was attempted. The direct backend additionally normalizes Apple's
definite no-effect results as `failureKind=accessibility_action_unsupported`:
`AXPress` with `kAXErrorActionUnsupported` (`-25206`) and `AXSetFocus` with
`kAXErrorAttributeUnsupported` (`-25205`). These results carry the exact
requested `action`, `actionAttempted=true`, `actionEffect=none`, and
`nativeErrorCode`; the native call was issued, but the requested action or
attribute was not supported and was not performed. That explicit no-effect
result may override dispatched and non-retryable transport evidence for
exactly one policy-gated fallback only when the proof is complete. The failure
kind must be
`accessibility_action_unsupported`, the action must be `AXPress` with `-25206`
or `AXSetFocus` with `-25205`, `actionAttempted` must be `true`, and
`actionEffect` must be `none`. Every present public, metadata, snake-case, and
nested copy must have the expected type and agree with the others. The proof
action must also equal the action in the outbound request; an internally valid
proof for a different action is rejected.

Attempt and dispatch evidence is parsed without truthiness coercion. A field is
either absent, a consistent Boolean `true`, a consistent Boolean `false`, or
invalid. Any present non-Boolean value, malformed metadata/action/diagnostics/
transport container, or contradictory alias invalidates recovery. The client
promotes `actionAttempted` to normalized metadata only when the raw value is an
actual Boolean and retains the raw action payload for downstream validation.

All other attempted native failures carry `actionEffect=unknown`, including
`kAXErrorCannotComplete` (`-25204`), and remain fail-closed.
`actionAttempted=true`, `requestDispatched=true`, `retryable=false`,
missing action/effect/native-code proof, malformed or empty values,
contradictory duplicates, and missing dispatch evidence stop recovery unless
the complete result is the definite unsupported/no-effect case above. They
cannot be followed by a coordinate click, selector click, Return keypress, or
next mutating strategy.

```python
from computer_use_macos import accessibility_action_command

result = client.run_command(
    accessibility_action_command(
        target_app="WeChat",
        bundle_id="com.tencent.xinWeChat",
        ax_path="0/2",
        action="AXPress",
        preconditions={
            "roleIn": ["AXRadioButton"],
            "labelIn": ["通讯录", "Contacts"],
            "actionIn": ["AXPress"],
        },
    )
)
```

The successful observation stores the query result at
`observation.accessibilityQuery`:

```json
{
  "schema": "macos.accessibility.query.v1",
  "available": true,
  "snapshotId": "frontmost:WeChat:微信 (聊天)",
  "app": {
    "name": "WeChat",
    "bundleId": "com.tencent.xinWeChat"
  },
  "window": {
    "title": "微信 (聊天)",
    "role": "AXWindow"
  },
  "root": {
    "kind": "focusedWindow",
    "axPath": "0"
  },
  "nodes": [
    {
      "axPath": "0/2",
      "role": "AXRadioButton",
      "description": "通讯录",
      "value": 0,
      "frame": {"x": 268, "y": 207, "width": 62, "height": 34},
      "actions": ["AXPress"]
    }
  ],
  "diagnostics": {
    "returnedNodes": 1,
    "truncated": false
  }
}
```

Supported `root.kind` values are:

- `focusedWindow`: query the focused window for the target app.
- `axPath`: query a node path returned by a previous query.

Supported `query.scope` values are `self`, `children`, and `descendants`.
Callers should set `limit`, `maxDepth`, and `timeBudgetMs` to keep reads
bounded. `match` can filter by role, role list, description, title/value text,
enabled state, or focused state.

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
- `accessibility_query`
- `open_app`
- `focus_app`
- `click`
- `type_text`
- `press_key`
- `hotkey`
- `wait`

Unsupported operations return a structured failed `ToolObservation`.

### `computer-use-macos` Command Builders

Use these helpers when constructing protocol commands in application code,
queues, or non-UI tests:

| Builder | Operation | Required Input | Notes |
|---|---|---|---|
| `readiness_command()` | `readiness` | none | Permission and platform readiness. |
| `observe_command(...)` | `observe` | optional target app/bundle | Bounded foreground/window observation. |
| `accessibility_query_command(...)` | `accessibility_query` | root/query | Scoped AX node reads for models and semantic tools. |
| `open_app_command(app, ...)` | `open_app` | app name | App must be allowlisted. |
| `focus_app_command(app, ...)` | `focus_app` | app name | Activates an allowlisted running app. |
| `click_command(...)` | `click` | semantic target, selector, or coordinates | Coordinate click requires explicit enablement. |
| `click_accessibility_command(selector, ...)` | `click` | selector + target app | Bounded selector click convenience wrapper. |
| `click_coordinate_command(x, y, ...)` | `click` | coordinates | Disabled unless `allow_coordinate_click=True`. |
| `type_text_command(text, ...)` | `type_text` | text | Does not submit and rejects newline text. |
| `press_key_command(key, ...)` | `press_key` | key | Single key press. |
| `hotkey_command(keys, ...)` | `hotkey` | modifier tuple/list | One key plus modifiers. |
| `wait_command(seconds=...)` | `wait` | seconds | Bounded pacing only. |

All builders accept `command_id`, `timeout_ms`, `idempotency_key`, and
`metadata` keyword arguments when the caller needs stable task/audit identity.

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

## WeChat Desktop APIs

`wechat-desktop-tool` exposes semantic WeChat operations on top of any
app-control client that implements:

```python
run_command(command, *, observer=None) -> ToolObservation
```

Typical initialization:

```python
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import WeChatDesktopTool

app_control = ComputerUseClient.from_config("app-control.toml")
wechat = WeChatDesktopTool.from_config(app_control, "app-control.toml")
```

Public operations:

| Operation | Python API | Purpose | Mutates Desktop |
|---|---|---|---:|
| `open_wechat` | `wechat.open_wechat()` | Open/focus WeChat and verify foreground identity. | Yes |
| `inspect_window` | `wechat.inspect_window(include_raw=False, include_actionables=True)` | Return the normalized `wechat.window.v1` model. | Opens/focuses app |
| `list_contacts` | `wechat.list_contacts(limit=30, page_token=None)` | Switch to contacts and return visible contact rows. | Changes selected tab |
| `list_conversations` | `wechat.list_conversations(limit=30, page_token=None)` | Return visible chat/conversation rows. | May change selected tab |
| `open_contact` | `wechat.open_contact(contact)` | Search and open one contact/conversation. | Yes |
| `execute_action` | `wechat.execute_action(action_ref)` | Execute an action returned by `inspect_window` or list APIs. | Depends |
| `read_visible_messages` | `wechat.read_visible_messages(limit=20)` | Return visible loaded message rows in current chat. | Opens/focuses app |
| `read_contact_messages` | `wechat.read_contact_messages(contact, limit=30)` | Compose `open_contact` and `read_visible_messages`. | Yes |
| `focus_contact` | `wechat.focus_contact(contact)` | Compatibility wrapper over verified `open_contact`, used by send-message. | Yes |
| `observe_current_chat` | `wechat.observe_current_chat()` | Legacy observe-backed current chat summary. | No |
| `draft_message` | `wechat.draft_message(message)` | Type bounded text into the focused chat input. | Yes |
| `submit_draft` | `wechat.submit_draft()` | Press the configured submit key. | Yes |
| `send_message` | `wechat.send_message(contact=..., message=...)` | Convenience focus/draft/submit flow. | Yes |

Command builders are exported for protocol-first callers:

```python
from wechat_desktop_tool import (
    execute_action_command,
    inspect_window_command,
    list_contacts_command,
    list_conversations_command,
    open_contact_command,
    read_contact_messages_command,
    read_visible_messages_command,
)

result = wechat.run_command(list_contacts_command(limit=30))
```

| Builder | Operation | Required Input | Notes |
|---|---|---|---|
| `open_wechat_command()` | `open_wechat` | none | Open/focus WeChat and verify foreground identity. |
| `inspect_window_command(...)` | `inspect_window` | optional flags | Returns `wechat.window.v1`. |
| `list_contacts_command(...)` | `list_contacts` | optional limit | Visible contacts only; non-null page tokens are rejected. |
| `list_conversations_command(...)` | `list_conversations` | optional limit | Visible conversations only; non-null page tokens are rejected. |
| `open_contact_command(contact)` | `open_contact` | contact text | May return `needs_disambiguation`. |
| `execute_action_command(action_ref)` | `execute_action` | `actionRef` returned by a read-model API | Executes `accessibility_action` first, then allowed fallback. |
| `read_visible_messages_command(...)` | `read_visible_messages` | optional limit | Visible loaded messages only. |
| `read_contact_messages_command(contact, ...)` | `read_contact_messages` | contact text | Opens contact, then reads visible messages. |
| `draft_message_command(message)` | `draft_message` | message text | Types but does not submit. |
| `submit_draft_command()` | `submit_draft` | none | Presses configured submit key. |
| `send_message_command(contact=..., message=...)` | `send_message` | contact + message | Convenience flow; caller owns authorization. |

The read-model APIs use `macos.computer_use/accessibility_query` internally.
Normal responses expose WeChat concepts such as navigation items, contact rows,
conversation rows, messages, and available semantic actions. They do not expose
raw `attributeNames` or full AX trees.

`inspect_window` returns:

```json
{
  "schema": "wechat.window.v1",
  "window": {
    "appName": "WeChat",
    "bundleId": "com.tencent.xinWeChat",
    "title": "微信 (聊天)",
    "snapshotId": "frontmost:WeChat:微信 (聊天)",
    "activeSection": "chats",
    "navigation": [
      {
        "id": "nav.contacts",
        "label": "contacts",
        "selected": false,
        "element": {"axPath": "0/2", "role": "AXRadioButton"}
      }
    ],
    "regions": {
      "mainContent": {"available": true},
      "searchBox": {"available": true}
    },
    "actionables": [
      {
        "id": "nav.contacts.press",
        "kind": "navigation_item",
        "actionRef": {
          "schema": "wechat.action_ref.v1",
          "id": "nav.contacts.press",
          "preferredMethod": "accessibility_action",
          "target": {"axPath": "0/2", "role": "AXRadioButton"},
          "action": "AXPress",
          "createdAt": "2026-07-08T10:00:00Z",
          "expiresAt": "2026-07-08T10:05:00Z"
        }
      }
    ],
    "availableActions": [
      {"id": "wechat.list_contacts", "status": "available"},
      {"id": "wechat.open_contact", "status": "needs_input"},
      {"id": "wechat.read_visible_messages", "status": "available"}
    ]
  },
  "includeRaw": false,
  "includeActionables": true,
  "normalization": {
    "status": "normalized",
    "reason": "accessibility_query_normalized",
    "queryMode": "scoped"
  }
}
```

When macOS Accessibility data is unavailable, `inspect_window` still returns a
structured observation when possible. Check `normalization.reason` and
diagnostic `availableActions` such as
`diagnostic.accessibility_query_missing`.

List APIs return visible rows only:

```json
{
  "schema": "wechat.conversations.v1",
  "section": "chats",
  "items": [
    {
      "id": "chats.visible.0",
      "displayName": "文件传输助手",
      "preview": "hello",
      "timestamp": "09:00",
      "badges": ["置顶"],
      "pinned": true,
      "muted": false,
      "actionId": "chats.visible.0.open",
      "element": {"axPath": "0/11/1/0/0", "role": "AXRow"},
      "actionRef": {
        "schema": "wechat.action_ref.v1",
        "id": "chats.visible.0.open",
        "kind": "chats.open",
        "preferredMethod": "accessibility_action",
        "target": {
          "axPath": "0/11/1/0/0",
          "role": "AXRow",
          "label": "文件传输助手,hello,09:00,置顶"
        },
        "action": "AXPress",
        "preconditions": {
          "roleIn": ["AXRow"],
          "labelIn": ["文件传输助手,hello,09:00,置顶"],
          "actionIn": ["AXPress"]
        },
        "createdAt": "2026-07-08T10:00:00Z",
        "expiresAt": "2026-07-08T10:05:00Z"
      }
    }
  ],
  "pagination": {
    "mode": "visibleWindow",
    "limit": 30,
    "pageToken": null,
    "hasMore": false,
    "nextPageToken": null
  }
}
```

List APIs do not scroll or implement cursor continuation in `0.2.0`.
`nextPageToken` is always `null`; passing a non-null `pageToken` returns
`failureKind="pagination_not_supported"` instead of replaying the first page.

WeChat `actionRef` values are short-lived recommendations. Generated refs
include `createdAt` and `expiresAt`; `execute_action` rejects expired or
malformed refs with `wechat_action_ref_expired` before calling macOS
Accessibility or selector fallback. Re-run `inspect_window`, `list_contacts`,
or `list_conversations` to obtain a fresh ref when this happens.

`read_visible_messages` returns normalized visible messages:

```json
{
  "schema": "wechat.messages.v1",
  "chat": {"title": "Ada"},
  "messages": [
    {
      "id": "message.visible.0",
      "direction": "unknown",
      "text": "hello",
      "visible": true,
      "element": {"axPath": "0/11/4/0/0/0", "role": "AXRow"}
    }
  ],
  "pagination": {
    "limit": 20,
    "canReadOlder": false,
    "olderPageToken": null
  },
  "truncated": false
}
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
`accessibility_action_unsupported`, `wechat_action_ref_expired`,
`draft_failed`, and `submit_unknown`. The named macOS constant is available as
`computer_use_macos.errors.ACCESSIBILITY_ACTION_UNSUPPORTED`. A tool may still
propagate a lower-level `failureKind` from another compatible app-control
client in nested evidence.

Warm accessibility worker process failures are also stable public constants:

- `ACCESSIBILITY_QUERY_WORKER_FAILED`
- `ACCESSIBILITY_QUERY_WORKER_EMPTY_RESPONSE`
- `ACCESSIBILITY_ACTION_WORKER_FAILED`
- `ACCESSIBILITY_ACTION_WORKER_EMPTY_RESPONSE`

All four are exported from `computer_use_macos` and included exactly once in
`COMPUTER_USE_FAILURE_KINDS`.

Accessibility query, action, and legacy tree workers operate only on the
current usable frontmost application. A bundle-id or app-name mismatch,
terminated app, hidden app, or unavailable frontmost app fails before an AX
application element is created. The workers do not select a background process
with the requested bundle identifier.

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
