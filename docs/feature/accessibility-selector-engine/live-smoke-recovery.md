# Accessibility Selector Engine Live Smoke Recovery

- Date: 2026-07-12
- Branch: `codex/accessibility-selector-engine`
- Status: historical recovery evidence retained; current exact-head proof v2
  awaits explicit desktop authorization and a trusted local service

## Current Blocker

The observations in this section describe the 2026-07-07/08 recovery attempts.
Current deterministic remediation checks pass, but a fresh live proof still
requires macOS to expose a real focused WeChat `AXWindow`. As of 2026-07-12,
`/tmp/app-control.sock` is absent, so the trusted service must also be restarted
from the exact feature checkout before rerunning the smoke.

Observed current desktop state:

```text
frontmost loginwindow com.apple.loginwindow 398
wechat_apps [('微信', 'com.tencent.xinWeChat', 60088, False, False)]
focused_window_role AXApplication
focused_window_title 微信
windows_count 3
window 0 role AXApplication title 微信 children 5
window 1 role AXApplication title 微信 children 5
window 2 role AXApplication title 微信 children 5
```

This means WeChat is running, but Accessibility is not exposing a chat-window
UI tree. The available AX nodes are application/menu-bar structures, not
selectors that can produce contacts, conversations, messages, or action
references.

The package now fails closed in this state:

- `open_app` succeeds;
- `observe` sees WeChat as the target app but with empty `windowTitle`;
- `focus_app` succeeds;
- the second `observe` still has empty `windowTitle`;
- WeChat semantic operations return `wechat_not_ready`;
- selector `accessibility_query` is not run after the open phase proves no
  focused window is available.

## Latest Retry

On 2026-07-08, a read-only `frontmostApp` root probe was attempted from the
Codex-hosted Python process:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -c '... accessibility_query(root={"kind": "frontmostApp"}) ...'
```

Result:

```text
status=not_ready
success=false
failureKind=not_available
readiness.status=missing_accessibility
accessibility_trusted=false
summary=macOS Accessibility query is unavailable until readiness is ready.
```

This did not reach WeChat or the selector backend. It only proves that the
current Codex-spawned Python process is not Accessibility-trusted. Live smoke
must be run from a trusted Terminal/Python host or after granting
Accessibility permission to the host process.

After the listed-contact actionRef and visible-row `open_contact` updates,
`examples/wechat_contacts_recent_messages_test.py --max-contacts 1` was rerun
against the current feature checkout and wrote:

```text
/private/tmp/selector-live-recent-messages-actionref.json
```

Result:

```text
success=false
failedStep=openWeChat
system_open_wechat=true
readiness=true
open_wechat status=not_ready
open_wechat summary=WeChat is frontmost but no focused window is available.
verify_wechat_accessibility_window failureKind=accessibility_query_no_focused_window
```

A direct PyObjC probe in the same desktop session still reported:

```text
frontmost loginwindow com.apple.loginwindow 398
wechat_apps [('微信', 'com.tencent.xinWeChat', 60088, False, False)]
focused_window_role AXApplication
focused_window_title 微信
windows_count 3
window 0 role AXApplication title 微信 children 5
window 1 role AXApplication title 微信 children 5
window 2 role AXApplication title 微信 children 5
```

This retry did not exercise contact listing, actionRef opening, or message
reading. It stopped at the same desktop-window prerequisite as earlier reruns.

On 2026-07-08, the consolidated selector-engine smoke was run twice against
the existing local app-control service:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_selector_engine_smoke_test.py \
    --skip-system-open \
    --socket-path /tmp/app-control.sock \
    --token-file ./app-control.token \
    --output /private/tmp/selector-live-selector-engine-smoke-20260708.json \
    --contact "文件传输助手"
```

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_selector_engine_smoke_test.py \
    --socket-path /tmp/app-control.sock \
    --token-file ./app-control.token \
    --output /private/tmp/selector-live-selector-engine-smoke-system-open-20260708.json \
    --contact "文件传输助手"
```

Results:

```text
readiness=true
accessibility_trusted=true
profile override checks=true
open_app WeChat=true
focus_app WeChat=true
system open and AppleScript activate=true in the second run
openWeChat=false
failedStep=openWeChat
failureKind=wechat_not_ready
before focus frontmostBundleId=com.openai.codex
after focus frontmostBundleId=com.openai.codex
```

These runs prove the local service and Accessibility permission are usable, and
the profile override/fallback checks pass. They still do not produce merge
proof because macOS keeps Codex frontmost even after WeChat open/focus and
AppleScript activation report success.

On the continuation run on 2026-07-08, the new read-only prerequisite probe was
run from the Codex-hosted Python process:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_live_prereq_probe.py \
  --output /private/tmp/selector-live-prereq-probe-continuation-20260708.json
```

Result:

```text
success=false
readyForSmoke=false
failureKind=accessibility_not_trusted
accessibilityTrusted=false
wechatRunning=false
frontmostWeChat=false
wechatAxWindow=false
```

That result applies only to the Codex-spawned Python process. The local
app-control service was then used as the authoritative smoke host because its
readiness check has Accessibility permission.

The consolidated selector-engine smoke was rerun through the existing trusted
local service:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_selector_engine_smoke_test.py \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-selector-engine-smoke-continuation-20260708.json \
  --contact "文件传输助手" \
  --conversation-limit 30 \
  --contact-limit 30 \
  --message-limit 30
```

Result:

```text
systemOpenWeChat=true
readiness=true
accessibility_trusted=true
validProfileOverride=true
invalidProfileFallback=true
openWeChat=false
failedStep=openWeChat
failureKind=wechat_not_ready
open_app WeChat=true
focus_app WeChat=true
system open and AppleScript activate=true
before focus frontmostBundleId=com.openai.codex
after focus frontmostBundleId=com.openai.codex
```

This repeats the same trusted-service desktop blocker: automation can request
WeChat open/focus successfully, but macOS keeps Codex as the frontmost app, so
the WeChat adapter fails closed before selector queries, contact switching, or
message reading run.

## Required Manual Recovery

Before rerunning the remaining smoke tests, restore a real WeChat main window
in the desktop session:

1. Unlock or switch to the interactive macOS desktop session if the system is
   at loginwindow.
2. Open WeChat from Dock, Spotlight, Launchpad, or Finder.
3. Make the main WeChat chat window visible and frontmost.
4. Confirm the window title is visible as `微信 (聊天)` or an equivalent WeChat
   chat window title.
5. Leave WeChat logged in and unlocked.

The following automatic attempts did not restore the window in the current
state and should not be treated as sufficient proof:

- `open -b com.tencent.xinWeChat`;
- AppleScript `activate`;
- AppleScript `reopen`;
- `focus_app`;
- menu item clicks under `窗口` and `文件`.

## Verification Probe

After manual recovery, run this read-only probe. It must report
`readyForSmoke=true` and show at least one WeChat window with role `AXWindow`.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_live_prereq_probe.py \
  --output /private/tmp/selector-live-prereq-probe.json
```

Expected success signal:

```json
{
  "success": true,
  "readyForSmoke": true,
  "failureKind": null,
  "checks": {
    "accessibilityTrusted": true,
    "wechatRunning": true,
    "frontmostWeChat": true,
    "wechatAxWindow": true
  }
}
```

The probe is intentionally read-only. It does not open WeChat, focus WeChat,
click, type, draft messages, or call the WeChat semantic API. If it returns
`frontmost_not_wechat`, manually bring the WeChat chat window to the foreground
and rerun the probe. If it returns `wechat_ax_window_missing`, restore the main
chat window until macOS exposes an `AXWindow`.

The full report is written to `/private/tmp/selector-live-prereq-probe.json`
and includes `frontmost`, `wechat.apps[*].focusedWindow`, and
`wechat.apps[*].windows` for diagnosing the desktop state without exposing raw
Accessibility trees to package consumers.

## Remaining Smoke Commands

Start the local service from the feature checkout:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m computer_use_macos serve \
  --config ./app-control.toml \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token
```

Run the consolidated selector-engine smoke checklist first:

```bash
HEAD_SHA="$(git rev-parse HEAD)"
.venv/bin/python examples/wechat_selector_engine_smoke_test.py \
  --head-sha "$HEAD_SHA" \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-selector-engine-proof-v2.json \
  --private-debug-output /private/tmp/selector-live-selector-engine-private.json \
  --contact "文件传输助手" \
  --conversation-limit 30 \
  --contact-limit 30 \
  --message-limit 30
```

That report covers the remaining merge-gate scenarios in one artifact:
conversation listing, opening `文件传输助手`, visible message reading, valid
profile override loading, invalid override fallback, and expired actionRef
fail-closed behavior. The public output is whitelist-only proof v2. The private
diagnostic file must remain outside the repository and release bundle. The run
does not draft or submit a message.

Validate the public proof against the exact source commit:

```bash
.venv/bin/python scripts/release_preflight.py \
  --wechat-smoke-report /private/tmp/selector-live-selector-engine-proof-v2.json \
  --expected-source-sha "$(git rev-parse HEAD)"
```

If the consolidated checklist fails, run the narrower probes below to isolate
the failing phase:

```bash
.venv/bin/python examples/wechat_window_sdk_test.py \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-inspect.json
```

```bash
.venv/bin/python examples/wechat_contacts_list_test.py \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-contacts.json \
  --limit 30
```

```bash
.venv/bin/python examples/wechat_contacts_recent_messages_test.py \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-recent-messages.json \
  --contact "文件传输助手" \
  --message-limit 30
```

Do not use `wechat_file_transfer_send_test.py` as a fallback for this gate. The
required proof is read/focus-only and must not draft or send content.

## Merge Gate

The feature remains not merge-ready until `verification.md` records passing
proof for:

- conversation listing;
- opening `文件传输助手`;
- visible message reading;
- valid selector profile override loading;
- invalid selector profile fallback;
- expired actionRef rejection before backend execution;
- moved/resized-window frame-derived navigation;
- at least one contact, one conversation, and 1 to 30 visible messages;
- every measured semantic API at or below 3000 ms;
- exact-head proof v2 accepted by strict preflight with no sensitive fields.
