# Accessibility Selector Engine Live Smoke Recovery

- Date: 2026-07-07
- Branch: `codex/accessibility-selector-engine`
- Status: live smoke blocked by desktop WeChat window state

## Current Blocker

The implementation and automated checks are in place, but the remaining live
WeChat smoke cannot complete until macOS exposes a real focused WeChat
`AXWindow`.

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

After manual recovery, run this read-only probe. It must show at least one
window with role `AXWindow`.

```bash
.venv/bin/python - <<'PY'
from AppKit import NSWorkspace
from ApplicationServices import AXUIElementCreateApplication, AXUIElementCopyAttributeValue

def ax_get(element, attr):
    try:
        err, value = AXUIElementCopyAttributeValue(element, attr, None)
        return None if err else value
    except Exception as exc:
        return f"<error {exc!r}>"

workspace = NSWorkspace.sharedWorkspace()
frontmost = workspace.frontmostApplication()
print("frontmost", frontmost.localizedName(), frontmost.bundleIdentifier(), frontmost.processIdentifier())
apps = [app for app in workspace.runningApplications() if str(app.bundleIdentifier()) == "com.tencent.xinWeChat"]
for app in apps:
    ax_app = AXUIElementCreateApplication(app.processIdentifier())
    focused = ax_get(ax_app, "AXFocusedWindow")
    print("focused_window_role", ax_get(focused, "AXRole") if focused else None)
    print("focused_window_title", ax_get(focused, "AXTitle") if focused else None)
    windows = ax_get(ax_app, "AXWindows") or []
    print("windows_count", len(windows))
    for idx, window in enumerate(windows):
        print("window", idx, "role", ax_get(window, "AXRole"), "title", ax_get(window, "AXTitle"))
PY
```

Expected success signal:

```text
focused_window_role AXWindow
```

or:

```text
window 0 role AXWindow title ...
```

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
.venv/bin/python examples/wechat_selector_engine_smoke_test.py \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-selector-engine-smoke.json \
  --contact "文件传输助手" \
  --conversation-limit 30 \
  --contact-limit 30 \
  --message-limit 30
```

That report covers the remaining merge-gate scenarios in one artifact:
conversation listing, opening `文件传输助手`, visible message reading, valid
profile override loading, invalid override fallback, and expired actionRef
fail-closed behavior. It does not draft or submit a message.

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
.venv/bin/python examples/wechat_file_transfer_send_test.py \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-file-transfer-send.json \
  --contact "文件传输助手" \
  --message "selector engine smoke"
```

```bash
.venv/bin/python examples/wechat_contacts_recent_messages_test.py \
  --socket-path /private/tmp/app-control-selector-live.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-recent-messages.json \
  --max-contacts 3 \
  --message-limit 30
```

## Merge Gate

The feature remains not merge-ready until `verification.md` records passing
proof for:

- conversation listing;
- opening `文件传输助手`;
- visible message reading;
- valid selector profile override loading;
- invalid selector profile fallback;
- stale actionRef precondition failure.
