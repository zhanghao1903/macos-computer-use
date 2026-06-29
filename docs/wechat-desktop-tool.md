# WeChat Desktop Tool

`wechat-desktop-tool` is the first semantic package above the shared
app-control protocol. It translates WeChat operations into app-control commands
such as `open_app`, `hotkey`, `type_text`, `press_key`, and `observe`.

## Boundary

The package owns:

- WeChat operation names and typed inputs.
- WeChat-specific configuration such as app name, bundle id, search hotkey,
  submit key, search clear keys, message length limit, and default timeout.
- Mapping app-control observations into WeChat `ToolObservation` results.

The package does not own:

- macOS permissions or helper app lifecycle.
- User confirmation and business authorization.
- Durable task state, audit records, or UI projection.
- LLM provider integrations.

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

`focus_contact` emits this app-control sequence:

1. `open_app` with the configured WeChat app name.
2. `observe` to verify the foreground WeChat window before sending search keys.
3. `hotkey` with the configured search hotkey.
4. `hotkey` with the configured search clear hotkey.
5. `press_key` with the configured clear key.
6. `type_text` with the contact name.
7. `press_key` with the configured submit key.
8. `observe` with visible text enabled to verify the selected chat window.

When callers use `run_stream(...)` or pass an observer to `run_command(...)`,
each app-control step is also emitted as a `progress` `ToolEvent`. The event
uses the top-level WeChat command id, stores the app-control operation and
observation in `data`, and uses nested phase names such as
`focus_contact.open_wechat` inside `send_message`.
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
If the backend cannot report a chat title, the operation remains best-effort and
exposes that uncertainty through the returned confidence value.
If a backend can report unresolved search candidates through fields such as
`contactMatches`, `candidateContacts`, or `searchResults`, and more than one
candidate is present, `focus_contact` returns `not_found` with
`failureKind="contact_ambiguous"` instead of selecting one implicitly.

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

`read_visible_messages` prefers structured `observation.messages`. When the
backend only returns `textExtract`, it splits non-empty visible-text lines into
message observations and best-effort parses simple prefixes such as
`incoming:`, `outgoing:`, and `[14:32] incoming:`.
The `truncated` flag is set only when the tool sees more valid messages than
the requested `limit`; a response with exactly `limit` messages is not
considered truncated.

`send_message` can request bounded post-submit verification with
`verifyAfterSubmit=true`. Verification reads visible messages after the submit
attempt and returns `unknown` with `send_unverified` when the submitted text is
not visible in normalized `messages` or `textExtract`.
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
optional `token`, the CLI uses those values when `--socket-path`, `--token`, or
`--token-file` are not supplied:

```bash
wechat-desktop-tool examples send-message \
  --config ./app-control.toml \
  --contact "File Transfer" \
  --message "hello"
```

The local service response and nested `ToolObservation` are validated against
the shared protocol schemas before the CLI returns them.

The example focuses the contact and drafts the message by default. Add
`--submit` only when the caller has already completed its own authorization and
confirmation policy.

## Current Limitations

- Visible message extraction depends on the lower app-control backend returning
  either `observation.messages` or `textExtract`; `textExtract` direction and
  timestamp parsing is intentionally best-effort.
- `submit_draft` and verified `send_message` still use bounded observation.
  A successful submit means the keyboard action completed; a verified send means
  matching text was visible afterward.
- Contact disambiguation remains a future protocol extension, not hidden
  behavior in this package.
