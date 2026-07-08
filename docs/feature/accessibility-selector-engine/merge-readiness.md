# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-09
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Feature directory: `docs/feature/accessibility-selector-engine/`
- Status: merge-ready for PR review after branch CI is green

## Decision

The feature is ready for PR review after the branch CI checks pass.

Automated package checks pass for the internal selector engine, WeChat packaged
profile migration, collection extraction, selector profile override config,
multi-step selector resolution, noisy contact-row filtering, and the
smoke-driven focus hardening. The SDK examples and `open_contact` now also use
visible row actionRefs before falling back to search. The consolidated live
macOS/WeChat selector-engine smoke passed on 2026-07-08 through the trusted
local service, covering conversations, contact switching, message reading,
override behavior, and stale actionRef handling. The feature changes desktop
automation behavior, so the live smoke report remains part of the merge proof.

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
- visible WeChat conversation list extraction with 30 rows and action refs;
- switching to `文件传输助手` through `open_contact`;
- active chat message extraction with 30 visible messages after opening the
  target chat;
- valid local selector profile override loading;
- invalid selector profile fallback to the packaged profile;
- expired actionRef rejection before backend execution.

Final live proof:

- report path:
  `/private/tmp/selector-live-selector-engine-smoke-return-20260708.json`;
- command: `examples/wechat_selector_engine_smoke_test.py --contact
  "文件传输助手" --conversation-limit 30 --contact-limit 30 --message-limit 30`;
- result: `success=true`, `conversationCount=30`, `contactCount=30`,
  `messageCount=30`, and `failedStep=null`;
- release preflight accepted the report with
  `external-proof:wechat_selector_engine_smoke` verified.

Earlier blocked smoke conditions and recovery steps remain recorded in
`live-smoke-recovery.md` for troubleshooting future desktop environments. The
authoritative merge proof is the passing consolidated report recorded in
`verification.md`.

The release proof gate now recognizes that report as
`wechat_selector_engine_smoke` when it is attached or passed as
`wechat-selector-engine-smoke.json`. The report must keep the selector-engine
schema, a successful summary, all required checklist booleans, protocol-shaped
WeChat observations, profile override/fallback success, and an expired
actionRef failure kind of `wechat_action_ref_expired`.

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

- release preflight source-path recovery: 3 targeted tests passed;
- CI workflow WeChat package dependency-path recovery: 2 targeted tests passed;
- CI-equivalent `env -u PYTHONPATH python scripts/release_preflight.py`:
  passed, including WeChat module-entrypoint, dry-run smoke, and workflow
  source-path checks;
- `computer-use-macos` targeted package tests: 108 tests passed, 1 skipped;
- WeChat tool/profile tests: 91 tests passed;
- Python compile check: passed;
- real WeChat selector-engine smoke: passed with 30 conversations, 30 contacts,
  and 30 visible messages;
- release preflight accepted the live smoke report.

Broader earlier F5 verification also remains recorded in `verification.md`:

- `app-control-protocol`: 54 tests passed;
- root repository tests, including release preflight and wheel-check: 101 tests
  passed;
- WeChat package-boundary tests: 5 tests passed.

Before merge, rely on GitHub CI for the full repository matrix and rerun local
checks only if CI reports a failure.

Unavailable:

- local `ruff` could not run because the command is not installed in the
  current environment.

## Release Record

Present in `CHANGELOG.md` under `Unreleased`:

- Added: `wechat.selector_profile_path` and
  `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`;
- Internal: selector engine, packaged WeChat selector profile, collection
  extraction, and selector-backed WeChat semantic migration.

## PR/MR Description

Prepared in `pr-description.md`. It now includes the passing live smoke proof
and should be used as the PR body before requesting review.

## Merge Blockers

1. Branch CI must pass on GitHub before merge.
2. The draft PR body should be refreshed from `pr-description.md` after the CI
   source-path fix lands.
3. Do not add public `resolve_selector` or `extract_collection` protocol
   commands in this PR; those remain deferred to a future reviewed API proposal.

## Recommended PR Summary

Problem:

WeChat semantic APIs relied on brittle hard-coded Accessibility tree paths and
row scans, making them difficult to adapt when WeChat UI structure changes.

Solution:

Add an internal Accessibility selector engine with validated selector profiles,
bounded resolution, collection extraction, packaged WeChat selector profiles,
and application-configurable profile overrides.

Tests:

Use the automated verification and passing live WeChat smoke proof listed in
`verification.md`.

Release note:

Add internal selector profile support and selector-backed WeChat semantic
operations, plus optional `wechat.selector_profile_path` override config.
