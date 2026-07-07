# Accessibility Selector Engine Verification

- Verification date: 2026-07-07
- Branch: `codex/accessibility-selector-engine`
- Scope: automated F5 verification snapshot after Slice 5C
- Status: automated checks passed; real WeChat smoke partially passed and
  remains incomplete

## Automated Checks

| Area | Command | Result |
| --- | --- | --- |
| `app-control-protocol` tests | `PYTHONPATH=packages/app-control-protocol/src python -m unittest discover -s packages/app-control-protocol/tests` | Passed: 54 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 75 tests, 1 skipped |
| `wechat-desktop-tool` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 88 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| WeChat package-boundary tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_package_boundary.py` | Passed: 5 tests |
| Root repository tests and release preflight | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 101 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile ...` | Passed |
| Whitespace/conflict check | `git diff --check` | Passed |

## Additional Verification: Multi-Step Selector Resolution

Date: 2026-07-07.

This verification covers a corrective selector-engine slice that makes
`SelectorResolver` execute selector steps as a chain instead of querying every
step from the same root.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 25 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 76 tests, 1 skipped |

New coverage:

- a two-step selector first resolves an `AXGroup` landmark from the focused
  window;
- the second step is queried under that landmark's AX path;
- the final `SelectorResult` returns the second-step `AXTable` element rather
  than the intermediate landmark;
- query evidence confirms no full-window second-step scan is used.

## Additional Verification: Action Definition Safe Defaults

Date: 2026-07-07.

This verification covers the contract-synchronization slice for
`ActionDefinition.enabled_by_default`. Profile actions now default to disabled,
read/focus actions may opt in, and mutating actions fail closed if a profile
tries to enable them by default.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 30 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 84 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/models.py packages/computer-use-macos/src/computer_use_macos/selectors/profile.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/models.py packages/computer-use-macos/src/computer_use_macos/selectors/profile.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- omitted `enabled_by_default` parses to `False`;
- `changes_focus` actions can explicitly opt into
  `enabled_by_default = true`;
- `submits_text` and other mutating actions cannot be enabled by default;
- non-boolean `enabled_by_default` values are rejected during profile parsing.

## Additional Verification: Profile Policy Validation Hardening

Date: 2026-07-07.

This verification covers additional field-matrix enforcement for profile
policies that were represented in the dataclasses but not fully fail-closed in
validation.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 34 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 88 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- `PaginationPolicy.mode = "cursor"` is rejected during the internal MVP;
- `RelationRule.relation = "near"` requires a positive `max_distance`;
- relation distances cannot be zero or negative;
- `pick = "best"` requires at least one non-zero confidence scoring weight;
- non-best pick strategies may still use zero scoring weights when they do not
  depend on best-candidate scoring.

## Additional Verification: Selector Cache TTL Enforcement

Date: 2026-07-07.

This verification covers the selector cache lifecycle rule that cache entries
expire by TTL and must not be treated as stable element identity.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 35 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 89 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- expired selector cache entries are deleted and refreshed from the selector
  root instead of validating the old AX path;
- expired refreshes report `cache_status = "stale"` and only count the fresh
  query;
- stale signature validation still validates the cached AX path once before
  falling back to a fresh query;
- cache validation query counts are no longer double-counted.

## Additional Verification: WeChat Search Hotkey Recovery

Date: 2026-07-07.

This verification covers the live-smoke hardening slice that makes
`Command+F` the default WeChat search hotkey and recovers open-phase window
readiness from a bounded Accessibility query when `observe` omits the window
title.

| Area | Command | Result |
| --- | --- | --- |
| `app-control-protocol` config tests | `PYTHONPATH=packages/app-control-protocol/src python -m unittest packages/app-control-protocol/tests/test_config.py` | Passed: 7 tests |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 84 tests |

New coverage:

- default `[wechat].search_hotkey` is `["Command", "F"]`;
- explicit config and environment overrides can still set another hotkey such
  as `["Command", "K"]`;
- live `--allow-focus-select` no longer rejects `Command+F` before running;
- the open phase succeeds when `observe` has no title but
  `accessibility_query` returns an `AXWindow` title;
- the open phase still fails closed with `wechat_not_ready` when neither
  observation nor Accessibility can prove a focused WeChat window.

## Additional Verification: Contact Collection Fill And Search Focus Fallbacks

Date: 2026-07-07.

This verification covers the corrective slice for noisy WeChat contact rows,
frame-backed selector results, role-specific Accessibility selector click, and
verified `AXSetFocus` support.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 26 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 80 tests, 1 skipped |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 86 tests |

New coverage:

- collection extraction continues past invalid candidates until it accepts the
  caller's requested number of valid semantic items or exhausts bounded visible
  candidates;
- WeChat contact listing skips special/header rows before filling the caller
  limit;
- selector resolver queries include `AXFrame`, allowing resolved element frames
  to drive verified fallback behavior;
- Accessibility selector click preserves `AXTextArea` and matches by
  `description` inside role-specific System Events collections;
- `accessibility_action` accepts verified `AXSetFocus` for resolved AX paths;
- `open_contact` attempts safe selector click, `AXSetFocus`, configured
  hotkey, and config-gated coordinate fallback before returning
  `search_not_focused`.

## Additional Verification: Listed Contact ActionRef Recent Messages

Date: 2026-07-07.

This verification covers the SDK example path for reading recent messages from
contacts that were already returned by `list_contacts`. The example now uses
the contact row `actionRef` when present, then reads visible messages from the
opened chat. It falls back to `read_contact_messages(contact)` only when the
contact item does not include an actionRef.

| Area | Command | Result |
| --- | --- | --- |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile examples/wechat_contacts_recent_messages_test.py tests/test_sdk_examples.py` | Passed |

New coverage:

- `examples/wechat_contacts_recent_messages_test.py` opens listed contacts with
  `execute_action(actionRef)` before reading messages;
- the recent-messages fake-service fixture uses realistic contact row heights,
  so rows are not filtered as section/header rows;
- the SDK test asserts the listed-contact path does not issue `type_text` for
  the contact name;
- existing `read_contact_messages(contact)` search behavior remains the
  fallback when a contact item lacks an actionRef.

## Additional Verification: Visible Row OpenContact ActionRef

Date: 2026-07-07.

This verification covers the WeChat semantic `open_contact(contact)` path. The
tool now tries visible row actionRefs under the selector-resolved main content
region before entering the search-box workflow. The search path remains the
fallback for contacts that are not currently visible.

| Area | Command | Result |
| --- | --- | --- |
| Open-contact focused tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k open_contact` | Passed: 5 tests |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 87 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py` | Passed |

New coverage:

- `open_contact("文件传输助手")` opens a visible conversation row by executing
  that row's actionRef before search;
- the visible actionRef path returns `openMethod=visible_action_ref`;
- the visible actionRef path does not issue `type_text`, search hotkeys, or raw
  coordinate clicks;
- no-match visible rows still fall back to the existing search-box flow;
- SDK send-message fixtures now cover opening File Transfer through the visible
  row actionRef before drafting and submitting.

## Additional Verification: ActionRef Precondition Failure Mapping

Date: 2026-07-07.

This verification covers the WeChat semantic `execute_action(actionRef)` failure
path for stale or invalid action references.

| Area | Command | Result |
| --- | --- | --- |
| Execute-action focused tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k execute_action` | Passed: 3 tests |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 88 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- backend `precondition_failed` results are mapped to
  `wechat_action_precondition_failed`;
- stale actionRefs that fail role, label, action, or enabled checks do not use
  selector-click fallback;
- unsupported-backend responses still use selector fallback when one is
  available;
- backend failure details remain in the action evidence for caller diagnostics.

## Unavailable Checks

`uv run ruff check ...` was attempted, but the local environment does not have a
`ruff` executable available:

```text
error: Failed to spawn: `ruff`
Caused by: No such file or directory (os error 2)
```

This is an environment/tooling gap, not a reported lint failure.

## Fixture And Unit Coverage

Covered by automated tests:

- selector profile parsing, validation, defaults, transforms, cache policy, and
  collection extraction;
- normalized collection `elementRef` generation and fail-closed validation;
- packaged WeChat selector profile loading and override fallback;
- selector-backed WeChat contacts, conversations, visible messages, and
  open-contact flows;
- WeChat selector profile override config propagation from `AppControlConfig`;
- package boundary rule that only `wechat_desktop_tool.profiles` imports
  `computer_use_macos.selectors`;
- root release preflight allows the explicit selector-profile dependency while
  continuing to block broad WeChat-to-backend imports;
- SDK example fake-service fixtures cover selector-backed contact listing and
  recent-message reads after collection extraction;
- SDK example fake-service fixtures cover listed-contact actionRef execution
  before reading visible messages;
- WeChat tool and SDK example fixtures cover `open_contact` and File Transfer
  send flows that consume visible row actionRefs before using search.

## Real WeChat Smoke Evidence

Partial smoke was run on 2026-07-07 against a local app-control service using
the current checkout as `PYTHONPATH`.

The current no-focused-window desktop blocker and recovery steps are recorded
in `live-smoke-recovery.md`.

Passed evidence:

- `inspect_window` wrote `/private/tmp/accessibility-selector-inspect-fixed.json`
  and returned `success=true`, schema `wechat.window.v1`, title `微信 (聊天)`,
  active section `chats`, navigation labels `chats`, `contacts`, and
  `favorites`, regions `mainContent` and `searchBox`, `actionableCount=4`, and
  `availableActionCount=5`.
- `list_contacts(limit=30)` wrote
  `/private/tmp/accessibility-selector-contacts-list.json` and returned
  `success=true`, `listedContactCount=29`.

Incomplete evidence:

- `/private/tmp/accessibility-selector-conversations-open-read.json` could not
  complete `list_conversations`, `open_contact`, or `read_visible_messages`.
- `/private/tmp/accessibility-selector-inspect-after-focus.json` shows WeChat
  was frontmost, but `windowTitle` was empty and `accessibility_query` failed
  with `accessibility_query_no_focused_window` even after `focus_app`.
- `/private/tmp/accessibility-selector-contacts-list-rerun.json` failed for the
  same no-focused-window desktop state after the successful contacts run.
- `/private/tmp/selector-live-inspect-open-phase-fail.json` confirms the
  no-focused-window state now fails in the WeChat open phase with
  `status=not_ready` and `failureKind=wechat_not_ready`, before any selector
  `accessibility_query` runs.
- A direct PyObjC probe on 2026-07-07 still showed frontmost `loginwindow`,
  WeChat running but inactive, and WeChat `AXWindows` whose roles were
  `AXApplication` rather than `AXWindow`.
- `/private/tmp/selector-live-recent-messages-after-axsetfocus.json` listed one
  semantic contact but failed at `readContactMessages` with
  `search_not_focused`. Evidence shows `AXSetFocus` returned
  `AXUIElementSetAttributeValue` success for search box `0/12/0`, but a
  follow-up query still reported `AXFocused=false`. `Command+F`, `Command+K`,
  safe selector click, and several coordinate clicks inside the resolved
  search-box frame also failed to focus that live WeChat search input.
- `/private/tmp/selector-live-recent-messages-actionref.json` was rerun after
  the listed-contact actionRef and visible-row `open_contact` updates. The
  smoke did not reach `list_contacts`: `system_open_wechat` and readiness
  passed, but `open_wechat` returned `status=not_ready` with summary
  `WeChat is frontmost but no focused window is available.` The nested
  `verify_wechat_accessibility_window` failed with
  `accessibility_query_no_focused_window`.
- A direct PyObjC probe during that rerun showed frontmost `loginwindow`,
  WeChat running but inactive, `AXFocusedWindow` role `AXApplication`, and
  three WeChat `AXWindows` entries whose roles were all `AXApplication`, not
  `AXWindow`.

This is not enough for merge readiness. It proves that the selector-backed
window model and contacts collection work on a live client, and it also proves
that the backend and WeChat semantic layer now fail closed when no focused AX
window is available.

After manually restoring a real WeChat `AXWindow`, rerun
`examples/wechat_contacts_recent_messages_test.py --max-contacts 1` on the live
desktop. That rerun should prove whether the already-listed contact row can be
opened through `execute_action(actionRef)` and read through
`read_visible_messages` without relying on the WeChat search box.

After the visible-row `open_contact` update, rerun
`examples/wechat_file_transfer_send_test.py` on the live desktop. If
`文件传输助手` is visible in the conversation list, the smoke should open it
through `openMethod=visible_action_ref` before drafting and submitting.

## Remaining Real WeChat Smoke Checklist

These checks require a real macOS desktop, Accessibility permission, running
WeChat, and the local app-control service. Remaining checks are required before
merge or release readiness:

1. `list_conversations(limit=30)` returns visible conversations and action refs.
2. `open_contact("文件传输助手")` switches the active chat, preferably through
   visible row `openMethod=visible_action_ref` when File Transfer is visible.
3. `examples/wechat_contacts_recent_messages_test.py --max-contacts 1` opens a
   listed contact through actionRef and reads visible message rows.
4. `read_visible_messages(limit=30)` returns visible message rows after a
   manually or actionRef-opened chat.
5. `[wechat] selector_profile_path` loads a valid local override without
   rebuilding the package.
6. Invalid `selector_profile_path` falls back to the packaged profile.
7. Stale or invalid action refs fail preconditions instead of raw-coordinate
   clicking.

Recommended smoke setup:

```bash
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

Then run the existing SDK/example scripts against that service. For release
review, save JSON reports under a reviewed location or link the local proof
paths from this file.

## Release Readiness Gate

The feature is not release-ready until the remaining real WeChat smoke evidence
is added to this file or linked from it. Public selector protocol commands
remain deferred; this feature currently ships only the internal selector
engine, WeChat packaged profile migration, and profile override configuration.
