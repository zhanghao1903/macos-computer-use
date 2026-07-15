# WeChat Desktop Tool

`wechat-desktop-tool` is the first semantic package above the shared
app-control protocol. It translates WeChat operations into app-control commands
such as `open_app`, `accessibility_query`, `hotkey`, `type_text`, `press_key`,
and `observe`.

## Boundary

The package owns:

- WeChat operation names and typed inputs.
- WeChat-specific configuration such as app name, bundle id, selector profile,
  submit key, legacy search fields, message length limit, and default timeout.
- Mapping app-control observations into WeChat `ToolObservation` results.

The package does not own:

- macOS permissions or helper app lifecycle.
- User confirmation and business authorization.
- Durable task state, audit records, or UI projection.
- LLM provider integrations.

The normalized WeChat window model used for Accessibility snapshots is
documented in [wechat-window-data-model.md](wechat-window-data-model.md).

## Initialization

```python
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import build_wechat_tool, send_message

app_control = ComputerUseClient.from_config("app-control.toml")
wechat = build_wechat_tool(app_control)
```

After the caller has completed its own authorization and confirmation policy,
the convenience flow is:

```python
result = send_message(
    wechat,
    contact="File Transfer",
    message="hello",
)
```

Any compatible app-control client can be used as long as it exposes:

```python
run_command(command, *, observer=None) -> ToolObservation
```

In code, that surface is represented by
`app_control_protocol.AppControlClient`.

## Supported Runtime Modes In 0.2.0

The selector-backed WeChat APIs support these runtime modes:

- direct mode through `ComputerUseClient` with
  `[computer_use] backend = "direct"`;
- a local service whose server executes the direct backend, adapted through
  `UnixSocketServiceClient` or another compatible `AppControlClient`.

They do not support `[computer_use] backend = "helper"` in version `0.2.0`.
`WeChatDesktopTool.from_config(...)` copies the backend from the shared config
and raises `ValueError` during construction before it sends any app-control
command. Change the service to a direct backend or defer WeChat selector use;
do not catch the error and continue as though helper parity exists.

Constructing `WeChatDesktopTool(app_control)` without shared config cannot
identify the transport behind an arbitrary protocol client. In that advanced
injection form, the application is responsible for supplying a direct or
direct-backed local-service client.

## Protocol Example

```python
from wechat_desktop_tool import focus_contact_command

observation = wechat.run_command(
    focus_contact_command(
        "File Transfer",
        command_id="cmd_wechat_focus_1",
        timeout_ms=30000,
    )
)
```

For generic cases, `wechat_command(...)` builds a raw WeChat command envelope
without executing it.

## Inspect Window API

`inspect_window` is the read-only API for getting the current WeChat window as
the normalized `wechat.window.v1` model documented in
[wechat-window-data-model.md](wechat-window-data-model.md).

Python convenience API:

```python
result = wechat.inspect_window(
    include_raw=False,
    include_actionables=True,
)
window = result.observation["window"]
```

Protocol command builder:

```python
from wechat_desktop_tool import inspect_window_command

result = wechat.run_command(
    inspect_window_command(
        include_raw=False,
        include_actionables=True,
        command_id="cmd_wechat_inspect_window_1",
    )
)
```

The command emits this app-control sequence:

1. `open_app` with the configured WeChat app name.
2. `accessibility_query` for focused-window children. This discovers stable
   second-level controls such as `AXDescription="聊天"`,
   `AXDescription="通讯录"`, `AXDescription="收藏"`, and the main content
   `AXSplitGroup`.
3. `accessibility_query` for main-content children when the main content region
   is available.

Runnable example:

```bash
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_OUTPUT=./wechat-window-inspect.json \
python -m wechat_desktop_tool.examples.wechat_window_inspect
```

The equivalent CLI form is:

```bash
wechat-desktop-tool examples inspect-window \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --output ./wechat-window-inspect.json
```

Root-level SDK test stub:

```bash
/opt/anaconda3/bin/python examples/wechat_window_sdk_test.py \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --output ./wechat-window-sdk-test.json
```

This script imports `app_control_protocol`, `computer_use_macos`, and
`wechat_desktop_tool` as installed SDK packages, uses
`computer_use_macos.UnixSocketServiceClient` to call the local service, and then
calls `WeChatDesktopTool.inspect_window()` directly.

If this returns `normalization.reason = "accessibility_query_missing"`, check
`result.evidence.inspect_window.observation.accessibilityQuery`. A common cause
is starting `computer-use-macos serve` from a different Python environment than
the one where `packages/computer-use-macos[accessibility]` was installed.

The public result shape is:

```json
{
  "schema": "wechat.window.v1",
  "window": {
    "appName": "WeChat",
    "bundleId": "com.tencent.xinWeChat",
    "title": "WeChat window title",
    "snapshotId": "snapshot id",
    "element": {
      "axPath": "0",
      "role": "AXWindow"
    },
    "navigation": [],
    "regions": {
      "mainContent": {},
      "searchBox": {}
    },
    "actionables": [],
    "availableActions": []
  },
  "includeRaw": false,
  "includeActionables": true,
  "normalization": {
    "status": "normalized",
    "reason": "accessibility_query_normalized",
    "actionableCount": 0,
    "availableActionCount": 0,
    "queryMode": "scoped"
  }
}
```

If the lower app-control backend cannot return Accessibility query data, the
command still succeeds when WeChat can be opened, but
`normalization.reason` reports a diagnostic such as
`accessibility_query_missing`, `window.actionables` is empty, and
`window.availableActions` contains diagnostic recovery actions. A useful model
must have at least one non-diagnostic action whose `status` is not `blocked`.

By default, raw Accessibility data is not returned because it can contain
contact names and message text. Set `include_raw=True` only for debugging; then
the scoped low-level query payloads are included as `rawQueries`.

## Read Model APIs

These APIs expose clean WeChat information lists for Agent applications. The
caller should use these semantic lists instead of interpreting raw macOS AX
trees.

### `list_contacts`

Python API:

```python
result = wechat.list_contacts(limit=30, page_token=None)
contacts = result.observation["items"]
```

Protocol command builder:

```python
from wechat_desktop_tool import list_contacts_command

result = wechat.run_command(list_contacts_command(limit=30))
```

Behavior:

1. Open/focus WeChat.
2. Resolve the mapped `contacts` navigation path and query that element again
   from the current window.
3. Validate its role, localized label, enabled state, finite positive frame,
   and containment within the current window. Prefer its advertised `AXPress`;
   otherwise use the center of that current frame when coordinate clicking is
   enabled.
4. Verify that the navigation element is selected after the action.
5. Query visible row descendants under the main content region.

Response shape:

```json
{
  "schema": "wechat.contacts.v1",
  "section": "contacts",
  "items": [
    {
      "id": "contacts.visible.0",
      "kind": "contact",
      "displayName": "Ada",
      "actionId": "contacts.visible.0.open",
      "element": {"axPath": "0/11/1/0/0", "role": "AXRow"},
      "confidence": 0.88
    }
  ],
  "pagination": {
    "mode": "visibleWindow",
    "limit": 30,
    "pageToken": null,
    "hasMore": false,
    "nextPageToken": null
  },
  "availableActions": [
    {"id": "wechat.open_contact", "status": "needs_input"}
  ]
}
```

The current implementation returns visible rows only and does not scroll.
`nextPageToken` is always null. Passing a non-null page token returns
`pagination_not_supported` instead of replaying the first visible page.

An item includes `actionRef` only when its current AX node advertises an
executable `AXPress`. Rows without `AXPress` remain readable but do not publish
an actionRef that the backend cannot execute. Executable row refs also include
the exact current row label in `preconditions.labelIn`; execution rejects a row
ref whose identity cannot be verified.

### `list_conversations`

Python API:

```python
result = wechat.list_conversations(limit=30)
rows = result.observation["items"]
```

The flow is the same as `list_contacts`, but it targets the `chats` navigation
item and normalizes row labels into `displayName`, `preview`, `timestamp`,
`badges`, `pinned`, and `muted`.

Response shape:

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
      "confidence": 0.88
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

### `open_contact`

Python API:

```python
result = wechat.open_contact("Ada")
```

Protocol command builder:

```python
from wechat_desktop_tool import open_contact_command

result = wechat.run_command(open_contact_command("Ada"))
```

Behavior:

1. Open/focus WeChat.
2. Query top-level and main-content regions.
3. Locate the search box by AX role plus search-like description, preferring
   `AXDescription="搜索"`.
4. Click the search box, type the contact text, query search result rows, then
   click the only matching result.
5. Query static text in the chat panel to report the opened chat title.

If multiple candidates match, the operation returns `not_found` with
`failureKind="contact_ambiguous"`, `status="needs_disambiguation"`, and a
bounded semantic `candidates` list instead of selecting one implicitly. No
candidate action is attempted before the caller supplies a more specific
contact name.

Response shape:

```json
{
  "schema": "wechat.open_contact.v1",
  "target": "Ada",
  "status": "opened",
  "currentChat": {"title": "Ada"},
  "availableActions": [
    {"id": "wechat.read_visible_messages", "status": "available"},
    {"id": "wechat.draft_message", "status": "needs_input"}
  ]
}
```

### `read_visible_messages`

Python API:

```python
result = wechat.read_visible_messages(limit=20)
messages = result.observation["messages"]
```

Behavior:

1. Open/focus WeChat.
2. Query top-level controls and locate the main content region.
3. Query visible message descendants under main content.
4. Normalize visible rows into message objects.

Response shape:

```json
{
  "schema": "wechat.messages.v1",
  "chat": {"title": "Ada"},
  "messages": [
    {
      "id": "message.visible.0",
      "direction": "unknown",
      "text": "hello",
      "timestamp": null,
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

This reads only currently loaded/visible rows exposed by macOS Accessibility.
It is not a full chat-history export API.

### `read_contact_messages`

Python API:

```python
result = wechat.read_contact_messages("Ada", limit=30)
```

This composes `open_contact(contact)` and `read_visible_messages(limit)`.
The response schema is `wechat.contact_messages.v1` and includes both nested
semantic observations:

```json
{
  "schema": "wechat.contact_messages.v1",
  "target": "Ada",
  "openContact": {},
  "messages": {}
}
```

`focus_contact` delegates to `open_contact`. The common fast path emits:

1. `open_app` with the configured WeChat app name.
2. `observe` to verify the foreground WeChat window.
3. `accessibility_query` for a visible conversation matching the requested
   contact.
4. `accessibility_action` or a policy-allowed current-frame click for that
   verified row.
5. `accessibility_query` for the current chat title postcondition.

When the conversation is not visible, `open_contact` resolves the known WeChat
search box, verifies exact-element focus, replaces the current query, resolves
one result, and applies the same chat-title postcondition. Unknown focus or
multiple semantic matches fail before opening a row or drafting a message.

Mutating recovery is fail-closed across mapped navigation, visible-contact
opening, search focus, and search-result selection. A failed
`accessibility_action` can use one configured fallback only when the lower
result explicitly proves that no worker request was dispatched and marks the
result retryable, or explicitly reports that the action is unsupported without
reporting an attempted action. It can also use one fallback for
`accessibility_action_unsupported` only when the complete proof reports
`AXPress/-25206` or `AXSetFocus/-25205`, `actionAttempted=true`, and
`actionEffect=none`. Every public, metadata, alias, and nested occurrence of
the failure kind, action, attempted state, effect, and native error code must
have the expected type and agree. This direct-backend definite no-effect result
intentionally takes precedence over `requestDispatched=true` and
`retryable=false` because the native operation was rejected as unsupported
rather than applied.

All other dispatched, attempted, non-retryable, contradictory, or unknown
outcomes return immediately. Missing proof, wrong action/code pairing,
non-string or empty effects, non-integer codes, contradictory duplicates,
`actionEffect=unknown`, and `-25204` never permit another mutation. The tool
does not follow those results with a coordinate click, selector click, Return
keypress, or another open strategy. If an allowed fallback itself fails, that
failure is final for the semantic operation.

When callers use `run_stream(...)` or pass an observer to `run_command(...)`,
each app-control step is also emitted as a `progress` `ToolEvent`. The event
uses the top-level WeChat command id, stores the app-control operation and
observation in `data`, and uses nested phase names such as
`open_contact.open_wechat` inside `focus_contact` and `send_message`.
If a lower app-control backend echoes command input, WeChat progress events and
evidence redact nested `input.text` / `input.message` values before returning
them; semantic outputs expose message hashes, counts, and requested visible
message reads instead of draft input text.

`open_wechat` also verifies the foreground WeChat window with `observe` after
launch/focus. Its observation includes `frontmostApp`, `windowTitle`,
`currentChatTitle`, `windowReady`, and a `wechatEnvironment` diagnostics object
when the backend can report them.
`wechatEnvironment` includes the configured app name/bundle id, observed
foreground app/bundle id, window title, and `appVersion` when the backend
reports a version field such as `frontmostVersion`, `appVersion`, or `version`.
This is a troubleshooting signal for WeChat version or UI changes; it is not an
authorization or send-policy decision.
If the backend reports `frontmostBundleId` or `frontmostApp` and it clearly
does not match the configured WeChat identity, the tool returns `not_ready`
with `failureKind="wechat_not_ready"` instead of treating the window as ready.
If the backend reports `loggedIn=false`, `loginRequired=true`, or an equivalent
login status while observing WeChat, the tool returns `not_ready` with
`failureKind="wechat_not_logged_in"` and a recovery hint to log in manually.

When `focus_contact` verifies a current chat title that clearly does not match
the requested contact, it returns `not_found` with
`failureKind="contact_not_found"` instead of reporting a low-confidence success.
If the selector flow cannot verify a chat title, it fails instead of reporting a
best-effort focus. Multiple matching rows return `contact_ambiguous` before any
candidate is opened.

Selector-backed list, open, and read operations distinguish backend query
failure from a successful empty result. Their stable top-level failure kinds
are `missing_accessibility`, `accessibility_query_timeout`,
`app_control_transport_failed`, and `accessibility_query_failed`. The selector
or collection diagnostics retain `failureKind="selector_query_failed"`, the
exact backend `causeFailureKind`, and backend retryability. A successful query
with no match continues to use the operation-specific not-found failure.

When `draft_message` cannot type because the chat input is not focused, and the
backend reports `failureKind="input_not_focused"` or an explicit diagnostic
such as `inputFocused=false`, the tool returns `not_ready` with
`failureKind="input_not_focused"` and a recovery hint to refocus the chat input
or rerun `focus_contact`.

`observe_current_chat` asks the backend to include visible text by default and
maps common app-control fields into WeChat-specific fields such as
`frontmostApp`, `windowTitle`, `currentChatTitle`, `wechatEnvironment`,
`visibleMessages`, and `messageCount`.
The same foreground identity check is applied before mapping visible chat data.

`read_visible_messages` now uses scoped Accessibility queries and returns
`wechat.messages.v1`. `observe_current_chat` remains available for legacy
observe-backed chat summaries and still maps structured `messages` or
`textExtract` when a lower backend supplies them.

`send_message` can request bounded post-submit verification with
`verifyAfterSubmit=true`. Verification reads visible messages after the submit
attempt and returns `unknown` with `send_unverified` when the submitted text is
not visible in normalized `wechat.messages.v1` output.
If `submit_draft` cannot verify the low-level Return key result, it returns
`unknown` with `submit_unknown`, `sendAttempted=true`, and `retryable=false` so
callers can require manual review before any retry. Both `submit_unknown` and
`send_unverified` include the recovery hint `Check WeChat manually before
retrying.`
When this happens inside `send_message`, the convenience operation preserves the
nested `sendAttempted` fact and adds `failedPhase="submit_draft"` to its
observation.

## CLI Example

The package exposes a developer example without importing a concrete macOS
backend. It can either dry-run the app-control commands or connect to a local
app-control service socket:

```bash
wechat-desktop-tool examples send-message \
  --contact "File Transfer" \
  --message "hello" \
  --dry-run
```

```bash
wechat-desktop-tool examples send-message \
  --contact "File Transfer" \
  --message "hello" \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

If `--config` points to an app-control TOML with `[helper] endpoint` and
optional `token`, the CLI uses those connection values when `--socket-path`,
`--token`, or `--token-file` are not supplied. For WeChat selector APIs in
version `0.2.0`, that service must still run the direct backend and the same
config must keep `[computer_use] backend = "direct"`:

```bash
wechat-desktop-tool examples send-message \
  --config ./app-control.toml \
  --contact "File Transfer" \
  --message "hello"
```

The local service response and nested `ToolObservation` are validated against
the shared protocol schemas before the CLI returns them.

For live runs, the example verifies that the current chat already matches the
contact and then drafts the message. Use `--assume-current-chat` only when the
user has manually verified the current chat but the WeChat window title is too
generic to prove it. Live `--allow-focus-select` uses the verified
selector-backed `open_contact` flow and proves the target chat before drafting.
Add `--submit` only when the caller has already completed its own authorization
and confirmation policy.

## Current Limitations

- Helper-backed WeChat selector execution is not supported in `0.2.0` and
  fails during `WeChatDesktopTool.from_config(...)` construction. Generic
  `computer-use-macos` helper operations remain a separate supported backend
  capability.
- `list_contacts`, `list_conversations`, and `read_visible_messages` return
  visible or currently loaded rows exposed by macOS Accessibility. They do not
  export the full WeChat contact database or complete chat history.
- Contact and conversation lists do not implement cursor continuation in
  `0.2.0`; callers must refresh after scrolling the WeChat UI.
- `observe_current_chat` remains a legacy observe-backed summary API. When a
  lower backend supplies `observation.messages` or `textExtract`, its parsing is
  still best-effort.
- `submit_draft` and verified `send_message` still use bounded verification.
  A successful submit means the keyboard action completed; a verified send means
  matching text was visible afterward through `read_visible_messages`.
- `open_contact` can return `needs_disambiguation` when multiple search results
  match. The caller must choose how to resolve that ambiguity.
