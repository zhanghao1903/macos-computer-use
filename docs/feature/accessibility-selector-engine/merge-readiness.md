# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-07
- Branch: `codex/accessibility-selector-engine`
- Feature directory: `docs/feature/accessibility-selector-engine/`
- Status: not merge-ready

## Decision

Do not merge or release this feature yet.

Automated package checks pass for the internal selector engine, WeChat packaged
profile migration, collection extraction, and selector profile override config.
The remaining release gate is real macOS/WeChat smoke evidence. The feature
changes desktop automation behavior and cannot be considered complete from unit
tests alone.

## Scenario Coverage

Implemented and covered by automated tests:

- parse and validate internal Accessibility selector profiles;
- resolve bounded selectors against normalized Accessibility query payloads;
- extract configured collections without exposing raw AX trees to callers;
- generate normalized item element references for WeChat action mapping;
- migrate WeChat contacts, conversations, visible messages, and open-contact
  internals to packaged selector profiles;
- allow application-injected selector profile overrides through
  `wechat.selector_profile_path`, with packaged-profile fallback.

Still requiring real desktop proof:

- visible WeChat contact list extraction on a live client;
- visible WeChat conversation list extraction on a live client;
- active chat message extraction on a live client;
- switching to `文件传输助手` through `open_contact`;
- valid local selector profile override;
- invalid selector profile fallback;
- stale action reference precondition failure.

## Public Surface Impact

Added public/semi-public config:

- `[wechat] selector_profile_path`
- `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`

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

Recorded in `verification.md`:

- `app-control-protocol`: 54 tests passed;
- `computer-use-macos`: 74 tests passed, 1 skipped;
- `wechat-desktop-tool`: 86 tests passed;
- root repository tests, including release preflight and wheel-check: 101 tests
  passed;
- WeChat package-boundary tests: 5 tests passed;
- Python compile check: passed;
- `git diff --check`: passed.

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

1. Real macOS/WeChat smoke evidence is missing.

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
