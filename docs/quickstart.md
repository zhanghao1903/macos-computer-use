# Quickstart

This path is the developer-preview entrypoint for the app-control package
suite. It is written for a new developer on macOS who wants to verify the
protocol, the macOS backend, and the WeChat semantic package without adopting a
product-specific runtime.

## Prerequisites

1. macOS with Python 3.11 or newer.
2. WeChat Desktop installed and logged in for the WeChat smoke.
3. A contact controlled by the developer, for example File Transfer.
4. Accessibility permission for the terminal, IDE, agent host, or helper app
   that runs the desktop automation.

For production-style permission stability, use a signed helper app as the
macOS permission subject. Direct mode is acceptable for local development and
TextEdit smoke tests.

## Install From Checkout

From the repository root:

```bash
python -m pip install -e packages/app-control-protocol
python -m pip install -e packages/computer-use-macos
python -m pip install -e packages/wechat-desktop-tool
cp examples/app-control.toml app-control.toml
```

The root compatibility package can also be installed when validating migration
behavior:

```bash
python -m pip install -e .
```

## 30 Minute TextEdit Smoke

First verify the package entrypoint and protocol command sequence without
touching the desktop:

```bash
COMPUTER_USE_DRY_RUN=1 \
python -m computer_use_macos.examples.textedit_smoke
```

Then grant Accessibility permission and run the real TextEdit smoke:

```bash
python -m computer_use_macos.examples.textedit_smoke
```

Expected result:

- `readiness` returns a ready or actionable not-ready observation.
- TextEdit opens or is focused.
- `observe` reports TextEdit as the foreground app.
- `type_text` writes smoke text into the focused document.

If readiness reports missing Accessibility permission, follow
[permissions.md](permissions.md), restart the terminal or host process, and run
the smoke again.

## Local Service

Start the app-control Unix socket service when another package or process needs
to call the macOS backend through the protocol:

```bash
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

After you set `[helper] endpoint` and optional `token` in `app-control.toml`,
the same command can be shortened to `computer-use-macos serve --config
./app-control.toml`.

In another terminal, verify the service:

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness
```

`computer-use-macos request --config ./app-control.toml --operation readiness`
uses the configured endpoint, token, and timeout when the CLI values are not
provided.

The service transport still uses `ToolCommand` input and `ToolObservation`
output. Long-running callers can use `run_stream` or the service stream action
to receive `ToolEvent` updates.

## 60 Minute WeChat Focus/Draft Smoke

The Python entrypoint uses any compatible app-control client:

```python
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import build_wechat_tool

app_control = ComputerUseClient.from_config("app-control.toml")
wechat = build_wechat_tool(app_control)

wechat.focus_contact("File Transfer")
wechat.draft_message("hello from wechat-desktop-tool smoke")
```

Dry-run the semantic WeChat package first. This validates the command sequence
without touching WeChat:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_DRY_RUN=1 \
python -m wechat_desktop_tool.examples.wechat_smoke
```

Then open the target chat in WeChat and run the real focus/draft smoke through
the local service:

```bash
WECHAT_TOOL_CONTACT="File Transfer" \
WECHAT_TOOL_MESSAGE="hello from wechat-desktop-tool smoke" \
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_ASSUME_CURRENT_CHAT=1 \
python -m wechat_desktop_tool.examples.wechat_smoke \
  > ./wechat-focus-draft-smoke.json
```

If your `app-control.toml` has `[helper] endpoint` and optional `token`, set
`WECHAT_TOOL_CONFIG=./app-control.toml` instead of the socket and token-file
environment variables.

Expected result:

- WeChat opens or is focused.
- The current chat already matches the controlled contact.
- The message appears as a draft.
- The report has `submitted` set to `false`.

The real smoke does not press Return to select a searched contact by default.
That prevents a misfocused search shortcut from sending text in the current
chat. `WECHAT_TOOL_ASSUME_CURRENT_CHAT=1` means you manually verified that the
currently open chat is the requested contact. Live automated contact switching
requires `WECHAT_TOOL_ALLOW_FOCUS_SELECT=1` and
`wechat.search_hotkey = ["Command", "K"]`; the known-unsafe `Command+F`
setting is rejected before any keyboard action is sent.

Submitting is intentionally outside the quickstart. Run submit smoke only after
the caller has completed its own authorization policy and set
`WECHAT_TOOL_ALLOW_SEND=1`. `WECHAT_TOOL_ALLOW_SUBMIT=1` is accepted as a
compatibility alias. See [wechat-smoke.md](wechat-smoke.md) for the opt-in
submit flow.

## Helper App Path

Use the helper template when preparing a developer preview or production
integration where the permission subject must be stable:

```bash
python -m computer_use_macos helper init ./computer-use-helper \
  --name "Example Computer Use Helper" \
  --bundle-id com.example.computer-use-helper
python -m computer_use_macos helper build ./computer-use-helper
python -m computer_use_macos doctor \
  --manifest ./computer-use-helper/helper_config.json \
  --json
```

The generated manifest should keep `allowedApps` and
`allowedAppBundleIds` aligned with the caller's `app-control.toml` policy. See
[helper-packaging.md](helper-packaging.md) for signing, notarization, and helper
transport details.

## Before Publishing

Before publishing a developer preview, run:

```bash
python scripts/dev_check.py
```

For targeted failures, the unified check expands to:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest discover -s packages/app-control-protocol/tests
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
python scripts/release_preflight.py
```

Strict PyPI release proof additionally requires a signed and notarized helper
doctor report, a real `textedit-smoke.json` report, real WeChat focus/draft and
opt-in submit reports, a clean TestPyPI install report, and a
`Trusted Publisher report` for PyPI. The complete release flow is in
[release-checklist.md](release-checklist.md).

After preparing the `./release-proof/` assets, the same strict local gate is
available through:

```bash
python scripts/dev_check.py --check release-proof-preflight
```
