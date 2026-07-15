# Accessibility Selector Engine Merge Readiness

- Updated: 2026-07-15
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Verified implementation/evidence head:
  `916ac1d`
- Current review input:
  [`pr-review-macos-computer-use-3-d2dadd0.md`](./pr-review-macos-computer-use-3-d2dadd0.md)
- Current decision: `PENDING_REVIEW`; do not merge until a replacement review
  evaluates this remediation and the synchronized F6 surfaces

## Remediation Status

The `d2dadd0` review requested changes for `PRR-022` and `PRR-023` and recorded
`PRR-024` as a documentation contradiction.

- `PRR-022` is remediated at `3fd41ce`. Native Accessibility results now
  distinguish a definite unsupported/no-effect result from an uncertain
  attempted outcome.
- F5 evidence is recorded at `916ac1d`; clean-clone package, root, stress,
  preflight, compile, and wheel checks passed.
- `PRR-023` is being remediated by this merge-readiness update, the matching
  tracked PR description, and the GitHub PR body synchronization performed
  after this commit is pushed.
- `PRR-024` is remediated in `docs/api.md` and
  `docs/wechat-desktop-tool.md`; both now define the same recovery precedence.

These items remain `remediated, pending re-review` until a replacement review
binds its finding ledger to the resulting F6 snapshot.

## Corrected Recovery Contract

The direct backend reports three native action effect states:

| Result | Public evidence | Higher-level recovery |
| --- | --- | --- |
| Native success | `actionAttempted=true`, `actionEffect=performed` | Continue without fallback. |
| `AXPress/-25206` or `AXSetFocus/-25205` | `failureKind=accessibility_action_unsupported`, `actionAttempted=true`, `actionEffect=none`, `nativeErrorCode` | Permit exactly one existing policy-gated fallback. |
| Any other native error, including `-25204` | `failureKind=accessibility_action_failed`, `actionAttempted=true`, `actionEffect=unknown`, `nativeErrorCode` | Stop; do not mutate again. |

The WeChat adapter requires the new failure kind and consistent `none` effect
evidence before applying the exception. Missing or contradictory effect data,
legacy unsupported results with positive attempt evidence, EOF, timeout,
malformed responses, and unknown dispatch outcomes remain fail-closed. Once an
allowed fallback is issued, its result is final.

## Verification

Clean-clone verification of implementation head `3fd41ce`:

- root repository: 127 passed in 44.070 seconds;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 142 passed, 1 skipped, with `ResourceWarning` treated
  as an error;
- `wechat-desktop-tool`: 137 passed with `ResourceWarning` treated as an
  error;
- seven unsafe cross-package modes repeated ten times: 10/10 passes, 70
  dispatch/outcome executions, zero second mutation;
- compile, release preflight, whitespace, clean-tree, three-wheel build,
  isolated install/import/API smoke, and old dependency rejection: passed.

GitHub Actions run
[`29396951638`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29396951638),
job `87292520782`, passed in 2 minutes 23 seconds against exact F5 head
`916ac1d`.

No real Accessibility action or WeChat message was executed for this
classification remediation. Historical authorized live evidence remains
performance and integration context; deterministic SDK/error and real worker
protocol tests cover the corrected boundary.

## Finding Ledger

| Finding | State for this F6 snapshot |
| --- | --- |
| `PRR-001` through `PRR-021` | Resolved and revalidated by the prior review/test ledger. |
| `PRR-022` | Remediated; exact native unsupported/no-effect semantics and regressions are implemented and verified. |
| `PRR-023` | Remediated by tracked/platform F6 synchronization; replacement review still required. |
| `PRR-024` | Remediated; both stable documents publish one precedence rule. |

Historical review reports remain immutable. The `d2dadd0` report remains the
latest completed review decision until the replacement report is committed;
this document does not reinterpret its `REQUEST_CHANGES` decision as approval.

## Release Record

The committed `CHANGELOG.md` already records the selector engine, warm bounded
AX execution, no-replay behavior, and the compatibility requirement for
WeChat rows that omit or reject `AXPress`. No package version, dependency,
command, configuration key, or schema version changes in this remediation.

The release note should retain the existing selector-engine summary and name
the dispatch/attempt-aware no-replay boundary plus the definite unsupported
single-fallback exception.

## Repository Hygiene

- Private smoke JSON, tokens, raw AX observations, distribution directories,
  and package-local lock files are excluded.
- Unrelated dirty skill, README, changelog, and example changes in the primary
  worktree are not part of this phase.
- F5 validation used a clean clone and left it clean.

## Remaining Gates

1. Push this F6 tracked-document update.
2. Synchronize the GitHub PR body from `pr-description.md`.
3. Observe exact-head GitHub CI.
4. Produce a replacement review for the resulting snapshot.
5. If approved, make a final docs-only status synchronization before changing
   the PR from draft to ready.

Signed-helper proof and actual package publication remain F7 work.
