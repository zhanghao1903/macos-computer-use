# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-12
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Feature directory: `docs/feature/accessibility-selector-engine/`
- Status: `REQUEST_CHANGES`; the PR remains draft and is not merge-ready

## Decision

The feature is not ready to merge. The frozen review of head `07fa052` recorded
12 blocking findings in
[`pr-review-macos-computer-use-3-07fa052.md`](./pr-review-macos-computer-use-3-07fa052.md):
7 S1 findings covering privacy, unsafe desktop actions, incorrect-contact
reads, helper/dependency compatibility, and release workflow behavior; and 5 S2
findings covering cache validation, failure mapping, batch depth, pagination,
and strict proof validation.

The earlier 2026-07-10 merge-ready decision is superseded. Green CI for
`07fa052` did not include the reviewer's counterexamples and therefore is not
sufficient merge proof. The lifecycle returns from F6 to F2/F3 for a separately
versioned remediation design and implementation plan before any code changes.

Automated package checks pass for the internal selector engine, WeChat packaged
profile migration, collection extraction, selector profile override config,
multi-step selector resolution, noisy contact-row filtering, and the
smoke-driven focus hardening. The SDK examples and `open_contact` now also use
visible row actionRefs before falling back to search. The consolidated live
macOS/WeChat selector-engine smoke passed on 2026-07-08 through the trusted
local service, covering conversations, contact switching, message reading,
override behavior, and stale actionRef handling. The feature changes desktop
automation behavior, so the live smoke report remains part of the merge proof.

The latest targeted smoke additionally proved that the recent-messages example
opens `文件传输助手`, verifies that title, prints 30 rows, and keeps
`open_contact` and `read_visible_messages` below the three-second API target.

## Historical F6 Review Refresh (Superseded)

This section records the historical 2026-07-10 review. It checked the latest
contact-message and performance commits, package boundaries, generated
artifacts, release records, PR text, local full tests, real WeChat proof, and
GitHub CI. Its conclusion no longer describes the current head's merge status.

Review finding and remediation:

- finding: an empty result from the first mapped `0/12` collection root could
  stop lookup before the compatible `0/11` root;
- remediation: generic collection and targeted conversation lookup now continue
  until a configured root returns nodes, then use selector/search fallback only
  after mapped alternatives are exhausted;
- proof: deterministic tests cover `0/12` empty followed by `0/11` success for
  both `list_conversations` and `open_contact`;
- result: no unresolved code-review findings remain.

Repository hygiene review:

- local private smoke JSON, rawdata, tokens, build output, and the package-local
  untracked lock file are not part of the branch diff;
- only the workspace `uv.lock` is tracked as expected;
- unrelated dirty skill/docs/example changes remain outside this feature's
  commits;
- `git diff --check origin/main...HEAD` is clean after removing the trailing
  blank line in `requirements.md`.

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
- use current `0/12` and compatible `0/11` mapped roots for conversations,
  chat panels, and visible messages;
- verify the active chat title before any composed contact-message read;
- use policy-gated Quartz clicks for queried rows that do not expose a usable
  `AXPress` action;
- print a configured target contact's returned message rows from the SDK
  recent-messages example.

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
- targeted `文件传输助手` recent-message read with 30 terminal-printed rows;
- mismatched-title failure proof that returned zero messages instead of reading
  the unrelated active conversation.

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
- `open_contact` now fails closed with `contact_not_found` when the verified
  chat title differs from the requested contact.
- coordinate clicks retain the existing opt-in policy and now report additive
  `method = quartz_cg_event` metadata when executed by the native backend.

Changed example behavior:

- `examples/wechat_contacts_recent_messages_test.py` now reads one configurable
  contact using `--contact` instead of `--max-contacts` / `--stop-on-error`;
- this is an example-only migration; package API callers do not need to change.

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

- 2026-07-10 remediation CI: passed on run `29103299589` / job
  `86397377175`;
- protocol package: 54 tests passed;
- `computer-use-macos`: 112 tests passed, 1 skipped;
- `wechat-desktop-tool`: 103 tests passed;
- SDK examples: 9 tests passed;
- root repository: 109 tests passed, including wheel and release preflight;
- latest real targeted WeChat smoke: `currentChat=文件传输助手`,
  `messageCount=30`, `failedStep=null`;
- measured API timings: `openWeChat=463 ms`, `openContact=1175 ms`, and
  `readVisibleMessages=2052 ms`;
- alternate-root list/open regression tests: passed.

Historical feature verification also recorded there:

- GitHub Actions PR #3 `test` check passed on run
  `28958774968` / job `85924596643`;
- selector collection batch field extraction: `computer-use-macos` package
  tests passed with 108 tests and 1 skipped; WeChat package tests passed with
  96 tests;
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

Before merge, rely on GitHub CI for the full repository matrix if new commits
are added.

Unavailable:

- local `ruff` could not run because the command is not installed in the
  current environment.

## Release Record

Present in `CHANGELOG.md` under `Unreleased`:

- Added: `wechat.selector_profile_path` and
  `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`;
- Internal: selector engine, packaged WeChat selector profile, collection
  extraction, and selector-backed WeChat semantic migration.
- Fixed: verify requested WeChat chats before reading, support current/compatible
  mapped roots, use policy-gated Quartz row clicks, and print the configured
  target's messages from the SDK example.

## PR/MR Description

Prepared in `pr-description.md`. It includes the latest title-verification,
Quartz safety boundary, example-only migration, alternate-root remediation,
API timing, live smoke, and CI evidence, and has been synced to PR #3.

## Merge Blockers

All findings below must be remediated and independently re-reviewed on a new
head before the merge-ready status can be restored:

- `PRR-001`: prevent private WeChat observations from entering public release
  proof assets;
- `PRR-002`: fail closed when search focus cannot be verified;
- `PRR-003`: remove fixed global coordinate-first navigation;
- `PRR-004`: make same-name contact disambiguation reachable before clicking;
- `PRR-005`: provide helper AX parity or explicitly fail fast for unsupported
  selector-backed operations;
- `PRR-006`: revalidate the complete selector contract on cache hits;
- `PRR-007`: preserve Accessibility and transport failures through resolution;
- `PRR-008`: keep packaged collection batch queries within backend depth limits;
- `PRR-009`: separate normal pagination lookahead from true truncation;
- `PRR-010`: align package dependency lower bounds with required selector and
  configuration surfaces;
- `PRR-011`: repair and validate the clean release-workflow source paths;
- `PRR-012`: require non-empty, internally consistent strict selector proof.

The remediation must not add public `resolve_selector` or
`extract_collection` protocol commands; those remain deferred to a future
reviewed API proposal.

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
