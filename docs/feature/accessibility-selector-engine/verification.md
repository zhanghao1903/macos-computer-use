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
  recent-message reads after collection extraction.

## Real WeChat Smoke Evidence

Partial smoke was run on 2026-07-07 against a local app-control service using
the current checkout as `PYTHONPATH`.

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

This is not enough for merge readiness. It proves that the selector-backed
window model and contacts collection work on a live client, and it also proves
that the backend and WeChat semantic layer now fail closed when no focused AX
window is available.

## Remaining Real WeChat Smoke Checklist

These checks require a real macOS desktop, Accessibility permission, running
WeChat, and the local app-control service. Remaining checks are required before
merge or release readiness:

1. `list_conversations(limit=30)` returns visible conversations and action refs.
2. `open_contact("文件传输助手")` switches the active chat.
3. `read_visible_messages(limit=30)` returns visible message rows.
4. `[wechat] selector_profile_path` loads a valid local override without
   rebuilding the package.
5. Invalid `selector_profile_path` falls back to the packaged profile.
6. Stale or invalid action refs fail preconditions instead of raw-coordinate
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
