# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-13
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Reviewed implementation head:
  `5a010dab632eda2d3d9b39205f4f867c1fed0097`
- Status: `APPROVE`; implementation is merge-ready
- Current review:
  [`pr-review-macos-computer-use-3-5a010da.md`](./pr-review-macos-computer-use-3-5a010da.md)

## Decision

`PRR-001` through `PRR-017` are resolved. No open blocking finding remains for
the reviewed implementation head.

The final two gates now have direct evidence:

1. one authorized public `send_message` to `文件传输助手` returned
   `success=true`, `submitted=true` in `2461 ms`, below the `<=3000 ms`
   contract;
2. GitHub Actions run `29217691709`, job `86797719880`, passed all test,
   preflight, package, wheel, and distribution checks against the exact
   implementation head.

The public send began with Chats already selected. A separate non-submit probe
started in Contacts and measured `open_contact("文件传输助手")` at `1272 ms`.
Its Chats `AXPress` took `58 ms` wall time with
`diagnostics.transport.mode=worker`, `fallback=false`, and verified
preconditions, compared with `1042 ms` before remediation. These are two
separate live measurements and are not represented as one run.

Post-send read-back was not requested, so the evidence proves API submission
rather than delivery confirmation. That limitation does not block this
feature's approved contract.

## Completed Scope

The implementation provides:

- internal selector profile models, validation, matching, confidence,
  relations, bounded fallbacks, cache, and collection extraction;
- bounded Accessibility queries with indexed/attribute root resolution, safe
  attributes, budgets, timing diagnostics, and a warm query worker;
- verified AX actions with a separate warm action worker and no replay after
  uncertain action dispatch;
- policy-gated current-frame coordinate fallback and semantic postconditions;
- packaged WeChat selector/control maps for navigation, contacts,
  conversations, chat panels, search, and visible messages;
- semantic inspect, list, open, focus, read, actionRef, draft, and send paths;
- application-injected `wechat.selector_profile_path` with packaged fallback;
- coordinated package version/dependency floor `0.2.0`;
- privacy-safe, source-bound selector release proof v2 and strict preflight.

No public `resolve_selector` or `extract_collection` protocol command was
added. Helper-side selector parity and cursor/scroll pagination remain future
features.

## Finding Ledger

| Finding | Status | Closure |
|---|---|---|
| `PRR-001` | Resolved | Whitelist-only public proof v2 and recursive privacy rejection. |
| `PRR-002` | Resolved | Unknown search focus stops before text or Return. |
| `PRR-003` | Resolved | Current in-window frame only, with semantic postcondition. |
| `PRR-004` | Resolved | Two-candidate ambiguity checked before action. |
| `PRR-005` | Resolved | Unsupported selector-backed helper mode fails at construction. |
| `PRR-006` | Resolved | Full cache predicate and signature revalidation. |
| `PRR-007` | Resolved | Backend query causes remain failures, not not-found. |
| `PRR-008` | Resolved | Shared maximum query depth and bounded batch plan. |
| `PRR-009` | Resolved | N+1 lookahead separated from truncation. |
| `PRR-010` | Resolved | Coordinated `0.2.0` dependencies and clean wheel proof. |
| `PRR-011` | Resolved | Correct release source paths protected by preflight. |
| `PRR-012` | Resolved | Exact-head, non-zero, consistent, private-safe proof requirements. |
| `PRR-013` | Resolved | Public focus/send delegates to verified `open_contact`; live target title proved. |
| `PRR-014` | Resolved | Explicit AX targets are allowlisted and bundle/name identity is proven. |
| `PRR-015` | Resolved | Row refs carry exact labels; unlabeled rows emit no action or coordinate click. |
| `PRR-016` | Resolved | Visible-window lists return null continuation and reject non-null tokens. |
| `PRR-017` | Resolved | Public send `2461 ms`; warm Chats action `58 ms`; real Contacts-origin open `1272 ms`. |

Historical reports remain immutable. The authoritative current review is the
`5a010da` report linked above.

## Verification

Deterministic checks on implementation head `5a010da...`:

- root repository: 127 tests passed;
- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 132 tests passed, 1 skipped;
- `wechat-desktop-tool`: 123 tests passed;
- compile, wheel/build/install compatibility, release preflight, and diff
  checks passed;
- worker failure and timeout tests prove action requests are not replayed.

Live macOS and WeChat proof:

- one authorized public send ran exactly once and returned in `2461 ms`;
- exact target title, clipboard draft, and Return submission succeeded;
- a separate no-submit Contacts-origin `open_contact` returned in `1272 ms`;
- warm Chats `AXPress` returned in `58 ms`, worker transport `44 ms`, with no
  fallback and verified preconditions;
- no private raw payload is included in tracked proof.

Remote proof:

- repository visibility is public;
- PR #3 is open, draft, and GitHub reports it mergeable;
- run `29217691709` passed against exact implementation head `5a010da...`.

Ruff remains unavailable. Strict mypy reports the existing broad baseline and
is not a passing gate for this feature.

## Public Contract

- `focus_contact` is a compatibility wrapper over verified `open_contact`;
  `send_message` uses that target switch before drafting;
- target-app-only AX query/action requests fail closed unless process identity
  is proven;
- executable AXRow actionRefs require exact identity in
  `preconditions.labelIn`;
- contact and conversation lists are visible-window-only, return
  `nextPageToken=null`, and reject non-null continuation input;
- action worker timeout/protocol failure is non-retryable after dispatch;
- message submission remains explicit, with unknown submit outcomes marked
  non-retryable until manual inspection.

## Remaining Non-Blocking Work

- The PR is still draft; changing it to ready and merging are repository-owner
  actions, not part of this read-only review decision.
- Signed-helper proof and actual release publication remain F7 work.
- Delivery read-back was not requested for the one-shot send.
- A future performance suite may collect repeated samples and percentiles; the
  approved feature gate uses bounded representative live samples.

## Repository Hygiene

- The committed `CHANGELOG.md` already contains the selector-engine feature and
  performance entries; unrelated local changelog edits are not part of this
  phase.
- Private smoke JSON, tokens, raw data, distribution output, package-local lock
  files, and unrelated dirty skill/docs/example changes remain excluded.
- Review artifacts contain bounded semantic evidence only.
