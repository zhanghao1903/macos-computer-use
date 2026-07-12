# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-12
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Reviewed head: `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`
- Status: `REQUEST_CHANGES`; not merge-ready
- Current review:
  [`pr-review-macos-computer-use-3-eb0e793.md`](./pr-review-macos-computer-use-3-eb0e793.md)

## Decision

PR #3 remains draft and must not be merged at the reviewed head. The F6 review
closed the 12 findings from the historical `07fa052` snapshot, but identified
four new blocking findings while tracing public compatibility and desktop
action paths:

- `PRR-013`: `focus_contact` and `send_message` still use the obsolete
  hotkey/coarse-observe implementation and fail on the authorized live client;
- `PRR-014`: target-app-only Accessibility requests can select the wrong
  frontmost process when no bundle id is supplied;
- `PRR-015`: conversation-row actionRefs omit semantic identity preconditions
  and can press a different contact after row reordering;
- `PRR-016`: visible-window list methods return continuation tokens that do not
  advance and repeat the first page.

The review decision is `REQUEST_CHANGES`. Remediation must retain these IDs,
add deterministic regression coverage, and receive a fresh head-bound F6
review before this document can return to `APPROVE`.

## Completed Scope

The implementation currently provides:

- internal selector profile models, parsing, validation, matching, confidence,
  relations, fallbacks, cache, and collection extraction;
- bounded Accessibility queries with a warm worker, indexed/attribute root
  resolution, safe attribute filtering, query budgets, and step timing;
- generic verified `AXPress` and `AXSetFocus` actions plus policy-gated,
  current-frame coordinate fallback;
- packaged WeChat selector profile and control map for navigation, contacts,
  conversations, chat panels, and visible messages;
- semantic `inspect_window`, list, `open_contact`, message read, and actionRef
  execution results;
- application-injected `wechat.selector_profile_path` with packaged fallback;
- coordinated package version/dependency floor `0.2.0`;
- privacy-safe, source-bound selector release proof v2 and strict preflight.

No public `resolve_selector` or `extract_collection` protocol command was
added. Those remain a future feature.

## Previous Findings

The current review retains and marks these historical findings resolved:

| Finding | Current status | Closure |
|---|---|---|
| `PRR-001` | Resolved | Whitelist-only public proof v2 and recursive privacy rejection. |
| `PRR-002` | Resolved | Unknown search focus stops before text or Return. |
| `PRR-003` | Resolved | Current in-window frame only; selected-state postcondition. |
| `PRR-004` | Resolved | Two-candidate ambiguity checked before action. |
| `PRR-005` | Resolved | Unsupported selector-backed helper mode fails at construction. |
| `PRR-006` | Resolved | Full cache predicate and signature revalidation. |
| `PRR-007` | Resolved | Backend query causes preserved as failures. |
| `PRR-008` | Resolved | Shared maximum query depth and bounded batch plan. |
| `PRR-009` | Resolved | Completed N+1 lookahead separated from truncation. |
| `PRR-010` | Resolved | Coordinated `0.2.0` dependency set and clean wheel proof. |
| `PRR-011` | Resolved | Correct release source paths protected by preflight. |
| `PRR-012` | Resolved | Non-zero, consistent, exact-head strict proof requirements. |

The historical report remains immutable at
[`pr-review-macos-computer-use-3-07fa052.md`](./pr-review-macos-computer-use-3-07fa052.md).

## Current Verification

Reviewed head `eb0e793b...`:

- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 125 tests passed;
- `wechat-desktop-tool`: 122 tests passed;
- `git diff --check origin/main...HEAD`: passed;
- GitHub Actions `test`: passed, run `29196700910`, job `86660857594`;
- PR metadata: draft and GitHub reports `MERGEABLE`, but review policy blocks
  merge while findings remain.

Exact code head `6a74c1d...` proof, before the F5 documentation-only commit:

- all 10 selector smoke checks passed;
- 11 contacts, 14 conversations, and 30 visible messages were proven;
- `openWeChat=251 ms`, `inspectWindow=330 ms`,
  `listConversations=336 ms`, `openContact=829 ms`,
  `readVisibleMessages=1095 ms`, and `listContacts=1446 ms`;
- offscreen verified-search `openContact=2457 ms` and
  `readVisibleMessages=1282 ms`;
- no raw observation and no message submission;
- strict source-bound preflight passed.

F6 compatibility counterexamples on `eb0e793b...`:

- packaged `Command+F` `focus_contact`: failed safely with
  `search_not_focused` in 1781 ms;
- prior `Command+K` override: same failure in 1278 ms;
- both stopped before drafting or submitting;
- generated AXRow actionRef contained a target label but no `labelIn`
  precondition.

The exact selector proof must be regenerated after remediation because its
source SHA must equal the final reviewed head.

## Public Impact

The intended public behavior remains:

- existing WeChat semantic method names and response schema names stay stable;
- selector internals and raw AX structures are not the primary application
  contract;
- message drafting/submission remains explicit and target-verified;
- coordinate fallback remains policy-gated and frame-derived;
- selector profile overrides do not require repackaging the application.

The current head does not yet satisfy that contract for `focus_contact`,
`send_message`, target-app-only AX requests, row actionRefs, or pagination.

## Required Remediation

1. `PRR-013`: route public focus/send through the verified `open_contact`
   implementation, add call-sequence tests, and run the user-authorized live
   focus/send smoke to `文件传输助手`.
2. `PRR-014`: resolve or verify target app identity before AX query/action;
   add wrong-frontmost and bundle mismatch tests.
3. `PRR-015`: revalidate row semantic identity or stop publishing row
   actionRefs; add same-path changed-label tests.
4. `PRR-016`: keep continuation null/reject unsupported page tokens, or
   implement real disjoint continuation with two-call tests.
5. Re-run package/root suites, wheel/preflight checks, authorized live proof,
   current-head CI, and a new F6 PR review.

## Repository Hygiene

- Private smoke JSON, tokens, raw data, distribution output, package-local lock
  files, and unrelated dirty skill/docs/example changes are not part of the
  feature commits.
- Current review artifacts contain only bounded, sanitized evidence.
- `CHANGELOG.md`, API docs, migration notes, release checklist, and PR text must
  be refreshed again only after the four blockers are resolved.
