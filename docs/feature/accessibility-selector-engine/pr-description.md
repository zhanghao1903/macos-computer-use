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
It also hardens WeChat live operation paths by validating focused windows,
resolving chained selectors under prior step results, filtering noisy contact
rows before filling caller limits, opening visible rows through selector-derived
actionRefs, and verifying focus after safe selector click, `AXSetFocus`,
hotkey, or configured coordinate fallback attempts. It also handles live WeChat
`AXRow` targets that omit action names or reject `AXPress` by using bounded
actionRefs and a selected-search-result `Return` fallback instead of raw
coordinates.

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
- `open_contact` may return additive `openMethod` detail such as
  `visible_action_ref` or `search`.
- `accessibility_action` now permits `AXSetFocus` on a resolved Accessibility
  element path by setting `AXFocused=true`. Callers still need a follow-up focus
  verification before typing.
- `wechat-desktop-tool` imports `computer_use_macos.selectors` only through
  `wechat_desktop_tool.profiles`, preserving the package boundary.

## Safety And Authorization

The selector engine does not make arbitrary raw AX data or raw coordinate
clicks part of the application-facing contract. WeChat APIs continue to return
semantic models and structured failures. Message submission remains explicit
and is not hidden behind selector resolution.

## Verification

Latest targeted checks recorded in `verification.md`:

- `computer-use-macos` targeted package tests: 108 tests passed, 1 skipped
- WeChat tool/profile tests: 91 tests passed
- Python compile check: passed
- live WeChat selector-engine smoke: passed
- release preflight with the live smoke report: passed

Broader earlier F5 checks are also recorded there:

- `app-control-protocol`: 54 tests passed
- root repository tests, including release preflight and wheel-check: 101 tests
  passed
- WeChat package-boundary tests: 5 tests passed

## Manual Proof Status

The consolidated real macOS/WeChat smoke checklist passed on 2026-07-08 through
the trusted local socket service:

- report path:
  `/private/tmp/selector-live-selector-engine-smoke-return-20260708.json`
- `inspect_window`: passed
- `list_conversations(limit=30)`: passed with 30 rows and action refs
- `open_contact("文件传输助手")`: passed
- `read_visible_messages(limit=30)`: passed with 30 message rows
- `list_contacts(limit=30)`: passed with 30 contacts
- valid `selector_profile_path` override: passed
- invalid selector profile fallback: passed
- expired actionRef rejection: passed with `wechat_action_ref_expired`

`scripts/release_preflight.py --wechat-smoke-report
/private/tmp/selector-live-selector-engine-smoke-return-20260708.json` accepted
the report and verified `external-proof:wechat_selector_engine_smoke`.

Earlier desktop blockers and rerun commands remain documented in
`live-smoke-recovery.md` for troubleshooting. They are no longer merge blockers
for this branch because the consolidated smoke proof has passed.

## Release Note

Add internal selector profile support and selector-backed WeChat semantic
operations, plus optional `wechat.selector_profile_path` override config.
