# Accessibility Selector Engine PR Description

## Problem

WeChat semantic APIs previously depended on brittle hard-coded Accessibility
paths and row scans. When WeChat changes layout, locale labels, or row
structure, package consumers have little room to recover without rebuilding the
tool package or changing application code.

## Solution

This feature adds an internal Accessibility selector engine owned by
`computer-use-macos` and migrates WeChat semantic reads/actions to packaged
selector profiles owned by `wechat-desktop-tool`.

The implementation keeps selector resolution internal for this PR. It does not
add public `resolve_selector` or `extract_collection` protocol commands.

## Consumer Impact

Package consumers continue to call the existing WeChat semantic APIs:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `read_visible_messages`

New optional configuration allows applications to inject a local WeChat selector
profile without rebuilding the package:

- `[wechat] selector_profile_path`
- `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`

If an override profile is missing, unreadable, invalid TOML, or fails selector
validation, the tool falls back to the packaged profile.

## Public API And Compatibility

- Existing WeChat semantic schemas remain compatible:
  - `wechat.contacts.v1`
  - `wechat.conversations.v1`
  - `wechat.messages.v1`
  - `wechat.open_contact.v1`
- No public selector command or generic selector protocol is exposed in this
  feature.
- `wechat-desktop-tool` imports `computer_use_macos.selectors` only through
  `wechat_desktop_tool.profiles`, preserving the package boundary.

## Safety And Authorization

The selector engine does not make arbitrary raw AX data or raw coordinate
clicks part of the application-facing contract. WeChat APIs continue to return
semantic models and structured failures. Message submission remains explicit
and is not hidden behind selector resolution.

## Verification

Automated checks recorded in `verification.md`:

- `app-control-protocol`: 54 tests passed
- `computer-use-macos`: 75 tests passed, 1 skipped
- `wechat-desktop-tool`: 88 tests passed
- SDK example tests: 6 tests passed
- root repository tests, including release preflight and wheel-check: 101 tests
  passed
- WeChat package-boundary tests: 5 tests passed
- Python compile check: passed
- `git diff --check`: passed

## Manual Proof Status

Partial real macOS/WeChat smoke evidence is recorded in `verification.md`:

- `inspect_window` returned a normalized WeChat window model
- `list_contacts(limit=30)` returned 29 visible contacts

This PR must remain blocked until the remaining real smoke evidence is attached
or linked from `verification.md`:

- `list_conversations(limit=30)` returns visible conversations and action refs
- `open_contact("文件传输助手")` switches the active chat
- `read_visible_messages(limit=30)` returns visible message rows
- valid `selector_profile_path` override loads without rebuilding the package
- invalid `selector_profile_path` falls back to the packaged profile
- stale or invalid action refs fail preconditions instead of raw-coordinate
  clicking

The current desktop blocker and rerun commands are documented in
`live-smoke-recovery.md`.

## Release Note

Add internal selector profile support and selector-backed WeChat semantic
operations, plus optional `wechat.selector_profile_path` override config.
