# wechat-desktop-tool

Protocol-first WeChat Desktop semantic operations.

This package knows the WeChat Desktop workflow shape, but delegates all desktop
actions to a compatible app-control client. It does not own macOS permission
subjects, business authorization, task lifecycle, UI projection, confirmation
storage, or caller audit systems.

## Quick Start

```python
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import build_wechat_tool, send_message

app_control = ComputerUseClient.from_config("app-control.toml")
wechat = build_wechat_tool(app_control)

result = wechat.focus_contact("File Transfer")
print(result.to_dict())
```

After the caller has completed its own authorization and confirmation policy,
the convenience flow is also available:

```python
result = send_message(
    wechat,
    contact="File Transfer",
    message="hello",
)
```

The lower-level protocol entry is also available through command builders:

```python
from wechat_desktop_tool import draft_message_command, list_contacts_command

result = wechat.run_command(draft_message_command("hello"))
contacts = wechat.run_command(list_contacts_command(limit=30))
```

Use `wechat_command(...)` when you need to construct a custom command envelope
while keeping the stable `wechat.desktop` tool name.
`run_command(..., observer=...)` and `run_stream(...)` use the shared
`app_control_protocol.ToolObserver` event surface.

## Operations

- `open_wechat`: open or focus WeChat Desktop, then verify the foreground
  window with `observe`; a reported non-WeChat foreground identity returns
  `wechat_not_ready`. Successful observations include `wechatEnvironment`
  diagnostics with configured and observed app identity plus `appVersion` when
  the backend reports it.
- `inspect_window`: open/focus WeChat and use scoped
  `accessibility_query` calls to return the normalized `wechat.window.v1`
  model with navigation, regions, actionables, and available semantic actions.
- `list_contacts`: switch to the contacts tab and return visible contact rows
  with stable `actionId`, element reference, and visible-window pagination
  metadata. Continuation tokens are not supported.
- `list_conversations`: return visible chat rows with display name, preview,
  timestamp, badges, pinned/muted flags, and row open actions.
- `open_contact`: first resolve a visible conversation row, then use the
  verified selector-backed search flow when the target is not visible. It
  opens exactly one match and verifies the resulting chat title. Multiple
  matches return `contact_ambiguous` instead of selecting implicitly.
- `focus_contact`: compatibility API that delegates to `open_contact` and
  returns its verified target result. It no longer depends on a global search
  hotkey or coarse focused-window observation.
- `observe_current_chat`: ask the app-control backend for the current chat
  state and map visible messages into semantic chat fields after checking any
  reported foreground app identity.
- `read_visible_messages`: use scoped Accessibility queries to return visible
  loaded message rows as `wechat.messages.v1`. This is not a full chat-history
  export API.
- `read_contact_messages`: compose `open_contact` and `read_visible_messages`
  for a target contact.
- `draft_message`: type bounded message text without submitting.
- `submit_draft`: press the configured submit key.
- `send_message`: convenience flow for focus, draft, and submit. Set
  `verifyAfterSubmit` to read visible messages after submission and return
  `send_unverified` if the text is not observed in `wechat.messages.v1`.

## CLI Examples

Inspect the current WeChat window and write the normalized window model to a
file:

```bash
wechat-desktop-tool examples inspect-window \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --output ./wechat-window-inspect.json
```

Dry-run the app-control commands without touching the desktop:

```bash
wechat-desktop-tool examples send-message \
  --contact "File Transfer" \
  --message "hello" \
  --dry-run
```

Run against a local app-control service. Without `--submit`, the example only
focuses the contact and drafts the message:

```bash
wechat-desktop-tool examples send-message \
  --contact "File Transfer" \
  --message "hello" \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

Submitting is explicit:

```bash
wechat-desktop-tool examples send-message \
  --contact "File Transfer" \
  --message "hello" \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --submit
```

The CLI example does not provide business authorization. The caller must only
run it for contacts and messages they are allowed to control.

## Manual Smoke

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_DRY_RUN=1 \
python -m wechat_desktop_tool.examples.wechat_smoke
```

For a real focus/draft smoke, open the target chat manually, start
`computer-use-macos serve`, and provide `WECHAT_TOOL_SOCKET_PATH`. The smoke
does not press Return to select a searched contact. If the WeChat window title
does not identify the current chat, set `WECHAT_TOOL_ASSUME_CURRENT_CHAT=1`
after manually verifying the target chat. It submits only when
`WECHAT_TOOL_ALLOW_SEND=1` is set. `WECHAT_TOOL_ALLOW_SUBMIT=1` is accepted as a
compatibility alias. Automated contact switching requires
`WECHAT_TOOL_ALLOW_FOCUS_SELECT=1`; it uses the selector-backed
`open_contact` flow and verifies the target chat before drafting or submitting.

To run the read-only window inspection example:

```bash
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_OUTPUT=./wechat-window-inspect.json \
python -m wechat_desktop_tool.examples.wechat_window_inspect
```

## Configuration

The package consumes the shared `AppControlConfig` `wechat` section:

```toml
[wechat]
app_name = "WeChat"
bundle_id = "com.tencent.xinWeChat"
app_control_tool = "macos.computer_use"
# Optional custom selector profile. Invalid files fall back to the packaged
# WeChat selector profile.
# selector_profile_path = "./profiles/wechat-local.toml"
# Accepted for compatibility with older integrations. Normal contact switching
# uses selector-backed open_contact and does not depend on these fields.
search_hotkey = ["Command", "F"]
search_clear_hotkey = ["Command", "A"]
clear_key = "Delete"
submit_key = "Return"
max_message_chars = 2000
default_timeout_ms = 30000
```

## Failure Kinds

Import `WECHAT_FAILURE_KINDS` when callers need stable routing for
package-owned semantic failures such as `contact_not_found`, `draft_failed`,
`input_not_focused`, `pagination_not_supported`,
`wechat_action_precondition_failed`, `wechat_action_ref_expired`,
`wechat_action_target_unverified`, `submit_failed`, `submit_unknown`, and
`send_unverified`.

Selector-backed reads classify backend query failures into stable top-level
kinds: `missing_accessibility`, `accessibility_query_timeout`,
`app_control_transport_failed`, and `accessibility_query_failed`. The exact
backend cause remains available as `diagnostics.causeFailureKind`; use the
top-level kind for routing and the nested cause for diagnostics.

## Package Boundary

`wechat-desktop-tool` depends on `app-control-protocol` and a client that
implements `run_command(command) -> ToolObservation`. It must not import
`macos_computer_use`, Plato, Taskweavn, or any LLM provider SDK.

Developer-facing module entrypoints are available as `commands`,
`observations`, `errors`, `adapter`, and `recipes`.
