# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-07
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Feature directory: `docs/feature/accessibility-selector-engine/`
- Status: not merge-ready

## Decision

Do not merge or release this feature yet.

Automated package checks pass for the internal selector engine, WeChat packaged
profile migration, collection extraction, selector profile override config,
multi-step selector resolution, noisy contact-row filtering, and the
smoke-driven focus hardening. The SDK examples and `open_contact` now also use
visible row actionRefs before falling back to search. Real macOS/WeChat smoke
has partially passed: `inspect_window` and `list_contacts(limit=30)` worked on a
live client, and a later smoke run listed one semantic contact before failing to
focus WeChat's search input for message reading. The remaining release gate is
live proof for conversations, contact switching, message reading, override
behavior, and stale actionRef handling. The feature changes desktop automation
behavior and cannot be considered complete from unit tests alone.

## Scenario Coverage

Implemented and covered by automated tests:

- parse and validate internal Accessibility selector profiles;
- resolve bounded selectors against normalized Accessibility query payloads;
- extract configured collections without exposing raw AX trees to callers;
- generate normalized item element references for WeChat action mapping;
- migrate WeChat contacts, conversations, visible messages, and open-contact
  internals to packaged selector profiles;
- allow application-injected selector profile overrides through
  `wechat.selector_profile_path`, with packaged-profile fallback;
- harden live WeChat operation startup by verifying the focused window after
  `open_app`, retrying `focus_app` when the window title is missing, and
  failing closed with `wechat_not_ready` when no focused AX window is
  available;
- resolve chained selector steps under the previous step result instead of
  repeatedly scanning from the same root;
- fill contact collection pages from accepted semantic items rather than raw
  candidates, so headers and special rows do not consume the caller limit;
- expose resolved `AXFrame` values to selector results so verified fallback
  behavior can use the element frame;
- support verified `AXSetFocus` execution through `accessibility_action` for
  resolved Accessibility elements;
- open visible WeChat conversation/contact rows through their selector-derived
  actionRefs before using the search-box workflow.

Passed on a live WeChat desktop:

- normalized WeChat window inspection on a live client;
- visible WeChat contact list extraction on a live client;

Still requiring real desktop proof:

- visible WeChat conversation list extraction on a live client;
- active chat message extraction on a live client;
- switching to `文件传输助手` through `open_contact`, preferably through
  `openMethod=visible_action_ref` when the row is visible;
- valid local selector profile override;
- invalid selector profile fallback;
- stale action reference precondition failure.

Blocked smoke conditions observed on 2026-07-07:

- after one successful `inspect_window` and one successful `list_contacts`
  smoke run, subsequent smoke attempts saw WeChat frontmost but with an empty
  window title and no focused AX window, even after `focus_app`;
- a later direct PyObjC probe still showed frontmost `loginwindow`, WeChat
  running but inactive, and WeChat `AXWindows` whose roles were `AXApplication`
  rather than `AXWindow`;
- lower-level diagnostics showed WeChat's `AXWindows` contained application and
  menu-bar elements, not a chat-window UI tree;
- selector-backed WeChat operations now return `wechat_not_ready` from the open
  phase instead of continuing into `accessibility_query` or returning a
  false-positive application-root result;
- after `AXSetFocus` support was added, a later live run listed one semantic
  contact but failed at `readContactMessages` with `search_not_focused`:
  safe selector click, `AXSetFocus`, `Command+F`, `Command+K`, and several
  coordinate clicks inside the resolved search-box frame all left the search
  box with `AXFocused=false`.

Recovery steps and the remaining smoke command sequence are recorded in
`live-smoke-recovery.md`.

## Public Surface Impact

Added public/semi-public config:

- `[wechat] selector_profile_path`
- `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`

Changed semi-public action behavior:

- `accessibility_action` now accepts `AXSetFocus` for a resolved Accessibility
  element path and executes it by setting `AXFocused=true`; callers should still
  verify focus after the action before typing.

No public selector protocol command was added. `resolve_selector` and
`extract_collection` remain deferred to a future API proposal.

No WeChat semantic response schema was renamed or intentionally broken:

- `wechat.contacts.v1`
- `wechat.conversations.v1`
- `wechat.messages.v1`
- `wechat.open_contact.v1`

## Package Boundary Check

Expected package boundary:

- `computer-use-macos` owns generic selector models, validation, resolver, and
  collection extraction.
- `wechat-desktop-tool` owns WeChat selector profiles, semantic mapping, and
  WeChat action references.
- `wechat-desktop-tool` may import `computer_use_macos.selectors` only through
  `wechat_desktop_tool.profiles`.

Automated package-boundary tests passed during F5 verification.

## Verification Summary

Latest targeted verification recorded in `verification.md`:

- selector tests: 26 tests passed;
- `computer-use-macos`: 80 tests passed, 1 skipped;
- WeChat tool/profile tests: 87 tests passed;
- SDK example tests: 6 tests passed;
- Python compile check: passed;
- `git diff --check`: passed.

Broader earlier F5 verification also remains recorded in `verification.md`:

- `app-control-protocol`: 54 tests passed;
- root repository tests, including release preflight and wheel-check: 101 tests
  passed;
- WeChat package-boundary tests: 5 tests passed.

Before merge, rerun the broader root/package suite once more after the
remaining live-smoke blocker is resolved.

Unavailable:

- `ruff` could not run because the local environment has no `ruff` executable.

## Release Record

Present in `CHANGELOG.md` under `Unreleased`:

- Added: `wechat.selector_profile_path` and
  `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`;
- Internal: selector engine, packaged WeChat selector profile, collection
  extraction, and selector-backed WeChat semantic migration.

## PR/MR Description

Prepared in `pr-description.md`. It should be used as the draft PR body and
updated with links to real smoke reports before requesting merge.

## Merge Blockers

1. Remaining real macOS/WeChat smoke evidence is missing for conversations,
   opening `文件传输助手`, visible messages, override loading/fallback, and stale
   actionRef preconditions.
2. Current desktop smoke environment must expose a focused WeChat AX window.
   Visible-row opening can avoid the search box when the target row is visible,
   but non-visible contact switching still needs search-focus proof.

## Recommended PR Summary

Problem:

WeChat semantic APIs relied on brittle hard-coded Accessibility tree paths and
row scans, making them difficult to adapt when WeChat UI structure changes.

Solution:

Add an internal Accessibility selector engine with validated selector profiles,
bounded resolution, collection extraction, packaged WeChat selector profiles,
and application-configurable profile overrides.

Tests:

Use the automated verification listed in `verification.md`, then attach real
WeChat smoke reports before requesting merge.

Release note:

Add internal selector profile support and selector-backed WeChat semantic
operations, plus optional `wechat.selector_profile_path` override config.
