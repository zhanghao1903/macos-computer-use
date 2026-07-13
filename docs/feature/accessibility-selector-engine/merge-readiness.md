# Accessibility Selector Engine Merge Readiness

- Review date: 2026-07-13
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Reviewed head: `a49c57ef26a471b0e28f89223554895de3bcf8fd`
- Status: `INCOMPLETE`; not yet merge-ready
- Current review:
  [`pr-review-macos-computer-use-3-a49c57e.md`](./pr-review-macos-computer-use-3-a49c57e.md)

## Decision

No open code finding remains on the reviewed source. `PRR-001` through
`PRR-016` have implementation and named deterministic closure evidence.

Merge readiness remains incomplete for two external evidence gates:

1. the authorized public `send_message` smoke to `文件传输助手` executed once
   but failed closed because Codex remained frontmost after bounded focus
   recovery;
2. current GitHub Actions failed before any job step because of the repository
   account's Billing/spending-limit state.

The live attempt did not query or click a contact, draft text, submit, or send a
message, and it was not retried. GitHub's failure is external to the code and
workflow. This document must not change to merge-ready until a successful live
send and a green current CI run are observed.

## Completed Scope

The implementation now provides:

- internal selector profile models, validation, matching, confidence,
  relations, bounded fallbacks, cache, and collection extraction;
- warm bounded Accessibility queries with indexed/attribute root resolution,
  safe attributes, budgets, and timing diagnostics;
- verified AX actions plus policy-gated current-frame coordinate fallback;
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
| `PRR-009` | Resolved | Completed N+1 lookahead separated from truncation. |
| `PRR-010` | Resolved | Coordinated `0.2.0` dependencies and clean wheel proof. |
| `PRR-011` | Resolved | Correct release source paths protected by preflight. |
| `PRR-012` | Resolved | Exact-head, non-zero, consistent, private-safe proof requirements. |
| `PRR-013` | Resolved in code; live gate pending | Public focus/send delegates to verified `open_contact`; no legacy global-search hotkey in the tested sequence. |
| `PRR-014` | Resolved | Explicit AX targets are allowlisted and bundle/name identity is proven. |
| `PRR-015` | Resolved | Row refs carry exact label preconditions; unlabeled rows emit no action or coordinate click. |
| `PRR-016` | Resolved | Visible-window lists return null continuation and reject non-null tokens. |

Historical reports remain immutable:

- [`pr-review-macos-computer-use-3-07fa052.md`](./pr-review-macos-computer-use-3-07fa052.md)
- [`pr-review-macos-computer-use-3-eb0e793.md`](./pr-review-macos-computer-use-3-eb0e793.md)
- [`pr-review-macos-computer-use-3-feb937d.md`](./pr-review-macos-computer-use-3-feb937d.md)

## Verification

Latest code head `ca6d4a8...`, followed only by verification documentation:

- root repository: 127 tests passed;
- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 128 tests passed, 1 skipped;
- `wechat-desktop-tool`: 123 tests passed;
- package wheel build/install/rejection checks passed through the root suite;
- compile and diff checks passed.

Exact review head `a49c57e...`:

- release preflight passed public API, docs, config, command-builder,
  dry-run-smoke, packaging metadata, and workflow checks;
- current external proofs remain warnings;
- the one-shot public send stopped at target-app identity with zero contact or
  message side effects;
- workflow run `29200626621` failed before any step because of GitHub Billing,
  not a code or workflow error.

Historical exact-code selector proof remains valid for the shared semantic
read/open implementation: 11 contacts, 14 conversations, 30 visible messages,
all measured APIs below 3000 ms, target-title postcondition passed, and no raw
observation or message submission. It does not prove the newly unified public
send wrapper.

Ruff is unavailable. Strict mypy reports the existing broad baseline of 184
errors in 15 files and is not treated as a passing gate.

## Public Contract

- `focus_contact` is now a compatibility wrapper over verified
  `open_contact`; `send_message` uses that same target switch before drafting;
- target-app-only AX query/action requests fail closed unless process identity
  is proven;
- executable AXRow actionRefs require exact identity in
  `preconditions.labelIn`;
- contact and conversation lists are visible-window-only, always return
  `nextPageToken=null`, and reject non-null continuation input;
- legacy search-hotkey config remains parseable but does not drive normal
  contact switching;
- message submission remains explicit, with unknown submit outcomes marked
  non-retryable until manual inspection.

## Remaining Evidence

1. Correct the GitHub account Billing/spending-limit condition.
2. Rerun the existing workflow without changing it and require green current
   checks for the pushed head.
3. Run the public send smoke in an environment where WeChat can remain
   frontmost, restricted to target `文件传输助手`.
4. If submission returns `unknown`, inspect WeChat manually and do not retry.
5. Record the target postcondition, submit result, and elapsed public API time.
6. Refresh this file and the F6 report decision to `APPROVE` only after both
   evidence gates pass.

## Repository Hygiene

- Private smoke JSON, tokens, raw data, distribution output, package-local lock
  files, and unrelated dirty skill/docs/example changes are excluded.
- Review artifacts contain bounded semantic evidence only.
- The feature changelog entry must be staged independently from unrelated local
  changelog edits.
