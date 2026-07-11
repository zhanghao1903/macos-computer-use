# Accessibility Selector Engine PR Description

## Current Review Status

`REQUEST_CHANGES` for reviewed head `07fa052`. The frozen review identified 12
blocking findings that are not covered by the green CI suite. The previous
merge-ready statement is superseded; PR #3 must remain draft until the findings
in the
[frozen review report](https://github.com/zhanghao1903/macos-computer-use/blob/codex/accessibility-selector-engine/docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-07fa052.md)
are remediated and a new-head review passes.

The original design remains the historical baseline. Remediation is specified
in the separate
[2026-07-12 remediation design](https://github.com/zhanghao1903/macos-computer-use/blob/codex/accessibility-selector-engine/docs/feature/accessibility-selector-engine/design-remediation-2026-07-12.md).
That proposal requires technical review and a separate implementation plan
before code changes begin.

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
`AXRow` targets that omit action names or reject `AXPress` by using the queried
AX frame with policy-gated Quartz coordinate clicks, then verifies the opened
chat title before allowing message reads to continue.

## Consumer Impact

Package consumers continue to call the existing WeChat semantic APIs:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `read_visible_messages`
- `read_contact_messages`

New optional configuration allows applications to inject a local WeChat selector
profile without rebuilding the package:

- `[wechat] selector_profile_path`
- `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`

If an override profile is missing, unreadable, invalid TOML, or fails selector
validation, the tool falls back to the packaged profile.

The SDK recent-messages example now reads one configured contact instead of
iterating over a contact page. It defaults to `文件传输助手`, accepts
`--contact` and `--message-limit`, records separate `openContact` and
`readVisibleMessages` results, and prints returned message rows.

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
- `open_contact` now fails with `contact_not_found` when the queried active chat
  title does not match the requested contact; composed message reads stop at
  that failure instead of returning another conversation's rows.
- `click_coordinate` retains its existing API and opt-in policy while reporting
  additive `method = quartz_cg_event` metadata after native execution.
- `wechat-desktop-tool` imports `computer_use_macos.selectors` only through
  `wechat_desktop_tool.profiles`, preserving the package boundary.

Example-only migration: callers of
`examples/wechat_contacts_recent_messages_test.py` should replace
`--max-contacts` / `--stop-on-error` with `--contact`. Package API callers do
not need to migrate.

## Safety And Authorization

The selector engine does not expose arbitrary raw AX data or unrestricted raw
coordinate actions as a WeChat application-facing contract. Coordinate clicks
remain disabled unless the service configuration enables
`allow_coordinate_click`; target frames come from bounded Accessibility
queries, and `open_contact` verifies the resulting chat title. WeChat APIs
continue to return semantic models and structured failures. Message submission
remains explicit and is not hidden behind selector resolution.

## Verification

Latest 2026-07-10 checks recorded in `verification.md`:

- protocol package: 54 tests passed
- `computer-use-macos`: 112 tests passed, 1 skipped
- `wechat-desktop-tool`: 103 tests passed
- SDK examples: 9 tests passed
- root repository: 109 tests passed, including wheel and release preflight
- Python compile and whitespace checks: passed
- alternate-root regression: `0/12` empty then `0/11` successful, passed for
  conversation listing and `open_contact`
- real targeted WeChat smoke: `文件传输助手` verified and 30 rows printed

Earlier feature checks also recorded there include:

- GitHub Actions PR #3 `test`: passed
- selector collection batch field extraction: package tests passed
- release-preflight source-path recovery: 3 targeted tests passed
- CI workflow WeChat dependency-path recovery: 2 targeted tests passed
- CI-equivalent `env -u PYTHONPATH python scripts/release_preflight.py`: passed
- `computer-use-macos` targeted package tests: 108 tests passed, 1 skipped
- WeChat tool/profile tests: 91 tests passed
- Python compile check: passed
- live WeChat selector-engine smoke: passed
- release preflight with the live smoke report: passed

The complete historical test and smoke evidence remains in `verification.md`.

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

The latest targeted recent-messages smoke also passed through an isolated
service using the current source:

- `currentChat = 文件传输助手`
- `messageCount = 30`
- `failedStep = null`
- `openWeChat = 463 ms`
- `openContact = 1175 ms`
- `readVisibleMessages = 2052 ms`

The private smoke JSON remained under `/private/tmp` and is not committed.

## Release Note

Add internal selector profile support and selector-backed WeChat semantic
operations, plus optional `wechat.selector_profile_path` override config;
verify requested chat titles before reading messages and use policy-gated
Quartz clicks for WeChat rows without `AXPress`.
