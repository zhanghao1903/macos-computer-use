# Manual WeChat Smoke

This smoke verifies `wechat-desktop-tool` on a real macOS desktop through a
local app-control service. It is intentionally opt-in because focusing contacts,
drafting text, and submitting messages can have user-visible side effects.

## Prerequisites

1. WeChat Desktop is installed and logged in.
2. The contact is controlled by the developer, for example File Transfer.
3. The app-control service is running:

   ```bash
   computer-use-macos serve \
     --config ./app-control.toml \
     --socket-path /tmp/app-control.sock \
     --token-file ./app-control.token
   ```

4. The process hosting the service has macOS Accessibility permission.

## Dry Run

Dry-run mode prints the app-control commands without touching the desktop:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_DRY_RUN=1 \
python -m wechat_desktop_tool.examples.wechat_smoke
```

Expected:

- output is JSON;
- `submitted` is `false`;
- the app-control command list includes `open_app`, search `hotkey`, search
  clear `hotkey`, `press_key`, contact `type_text`, contact `press_key`, and
  final draft `type_text`.

## Focus And Draft Smoke

This verifies the current WeChat chat and drafts text, but does not submit.
Open the target chat manually before running it. By default the smoke does not
press Return to select a searched contact, because if WeChat search is not
focused that key can submit text in the current chat input.
If your WeChat window title is generic, for example `微信 (聊天)`, set
`WECHAT_TOOL_ASSUME_CURRENT_CHAT=1` after manually confirming the current chat
is the requested contact.

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_ASSUME_CURRENT_CHAT=1 \
python -m wechat_desktop_tool.examples.wechat_smoke \
  > ./wechat-focus-draft-smoke.json
```

If `./app-control.toml` already contains `[helper] endpoint` and optional
`token`, use `WECHAT_TOOL_CONFIG=./app-control.toml` instead of
`WECHAT_TOOL_SOCKET_PATH` / `WECHAT_TOOL_TOKEN_FILE`.

Expected:

- WeChat is focused;
- the current chat already matches the requested contact;
- the message appears as a draft;
- `submitted` is `false`.
- the JSON report can be passed to release preflight with
  `--wechat-smoke-report`.

To inspect the automated contact search and selection flow without touching
WeChat, use dry-run mode:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_DRY_RUN=1 \
WECHAT_TOOL_ALLOW_FOCUS_SELECT=1 \
python -m wechat_desktop_tool.examples.wechat_smoke
```

Live automated contact selection requires `WECHAT_TOOL_ALLOW_FOCUS_SELECT=1`.
The default search hotkey is `wechat.search_hotkey = ["Command", "F"]`, and the
tool verifies that WeChat search is focused before typing the contact.

## Submit Smoke

Run this only for a contact and message the caller is authorized to send:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_ALLOW_SEND=1 \
python -m wechat_desktop_tool.examples.wechat_smoke \
  > ./wechat-submit-smoke.json
```

`WECHAT_TOOL_CONFIG=./app-control.toml` can also provide the local service
endpoint and token for the submit smoke.

The submit smoke submits only when the current chat already matches
`WECHAT_TOOL_CONTACT`, or when `WECHAT_TOOL_ASSUME_CURRENT_CHAT=1` explicitly
records that the user manually verified the current chat:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_ASSUME_CURRENT_CHAT=1 \
WECHAT_TOOL_ALLOW_SEND=1 \
python -m wechat_desktop_tool.examples.wechat_smoke \
  > ./wechat-submit-smoke.json
```

To switch to the specified contact before sending, explicitly opt into both
contact selection and sending. The tool uses `wechat.search_hotkey`, defaulting
to `["Command", "F"]`, and verifies that WeChat search is focused before any
contact text is typed:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_ALLOW_FOCUS_SELECT=1 \
WECHAT_TOOL_ALLOW_SEND=1 \
python -m wechat_desktop_tool.examples.wechat_smoke \
  > ./wechat-submit-smoke.json
```

Optional visible-message verification:

```bash
WECHAT_TOOL_VERIFY_AFTER_SUBMIT=1
```

The package does not make the authorization decision. Setting
`WECHAT_TOOL_ALLOW_SEND=1` means the caller has already completed its own
authorization and confirmation policy. `WECHAT_TOOL_ALLOW_SUBMIT=1` is accepted
as a compatibility alias.

## Selector Engine Release Proof

This read-only smoke opens WeChat, lists visible conversations and contacts,
opens one configured contact, reads visible messages, checks profile override
fallback, and verifies expired actionRef rejection. It does not draft or submit
content.

Run it from the exact commit that will be released:

```bash
HEAD_SHA="$(git rev-parse HEAD)"
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
python examples/wechat_selector_engine_smoke_test.py \
  --head-sha "$HEAD_SHA" \
  --contact "File Transfer" \
  --contact-limit 30 \
  --conversation-limit 30 \
  --message-limit 30 \
  --output ./wechat-selector-engine-smoke.json
```

The default output is
`macos_computer_use.release.wechat_selector_engine_proof.v2`. It contains only
source/version metadata, structural check booleans, counts, bounded timings,
and safety evidence. It does not contain contact names, message text, window
titles, command ids, service/config paths, tokens, AX paths, or raw operation
observations. A valid release proof requires at least one contact, one
conversation, and one visible message; every measured semantic operation must
complete within 3000 ms.

Raw diagnostics are available only through an explicit private path:

```bash
python examples/wechat_selector_engine_smoke_test.py \
  --head-sha "$HEAD_SHA" \
  --private-debug-output /private/tmp/wechat-selector-engine-private-debug.json \
  --output ./wechat-selector-engine-smoke.json
```

The private debug file can contain contact names, message content, local paths,
and raw observations. Keep it outside the repository, do not pass it to
`release_proof_bundle.py`, and never attach it to a GitHub Release.

Dry-run JSON is intentionally not accepted as release proof. Use the saved
focus/draft and submit JSON reports with:

```bash
python scripts/release_preflight.py \
  --wechat-smoke-report ./wechat-focus-draft-smoke.json \
  --wechat-smoke-report ./wechat-submit-smoke.json \
  --wechat-smoke-report ./wechat-selector-engine-smoke.json \
  --expected-source-sha "$(git rev-parse HEAD)" \
  --require-external
```

Use the complete command in [publishing.md](publishing.md) when assembling all
required external release proofs.
