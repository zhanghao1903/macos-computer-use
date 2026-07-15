# Accessibility Selector Engine Merge Readiness

- Updated: 2026-07-15
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Verified implementation/evidence head:
  `d85703a`
- Current review:
  [`pr-review-macos-computer-use-3-d85703a.md`](./pr-review-macos-computer-use-3-d85703a.md),
  published at `376401e`
- Current decision: `APPROVE`; no blocking findings remain for the reviewed
  `d85703a` snapshot

## Remediation Status

The `3f792e4` review requested changes for `PRR-025` and `PRR-026` after
revalidating `PRR-022` through `PRR-024`. Both new blockers are resolved:

- the strict proof contract and implementation plan were amended at
  `804348b`;
- `0b78eff` declares the emitted failure in the stable public tuple, parses
  malformed effects without raising, and validates the complete WeChat proof;
- F5 evidence is recorded at `d85703a`; clean-clone package, root, 150-outcome
  stress, preflight, compile, and wheel checks passed;
- the `d85703a` replacement review is published at `376401e` with decision
  `APPROVE` and no blocking findings.

The replacement report is the authoritative current review. This final
docs-only update makes its decision discoverable from both F6 entry points; it
does not change runtime behavior or independently change the PR draft state.

## Corrected Recovery Contract

The direct backend reports three native action effect states:

| Result | Public evidence | Higher-level recovery |
| --- | --- | --- |
| Native success | `actionAttempted=true`, `actionEffect=performed` | Continue without fallback. |
| `AXPress/-25206` or `AXSetFocus/-25205` | Registered `failureKind=accessibility_action_unsupported`, exact action/code pair, `actionAttempted=true`, `actionEffect=none` | Permit exactly one existing policy-gated fallback. |
| Any other native error, including `-25204` | `failureKind=accessibility_action_failed`, `actionAttempted=true`, `actionEffect=unknown`, `nativeErrorCode` | Stop; do not mutate again. |

The WeChat adapter requires every public, metadata, alias, and nested proof
field to have the expected type and agree. Missing action, attempted state,
effect, or native code; wrong action/code pairing; non-string or empty effects;
non-integer codes; contradictory duplicates; legacy attempted results; EOF;
timeout; malformed responses; and unknown dispatch outcomes remain
fail-closed. Once an allowed fallback is issued, its result is final.

## Verification

Clean-clone verification of implementation head `0b78eff`:

- root repository: 127 passed in 51.076 seconds;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 143 passed, 1 skipped, with `ResourceWarning` treated
  as an error;
- `wechat-desktop-tool`: 138 passed with `ResourceWarning` treated as an
  error;
- fifteen unsafe cross-package modes repeated ten times: 10/10 passes, 150
  dispatch/outcome executions, zero second mutation;
- compile, release preflight, whitespace, clean-tree, three-wheel build,
  isolated install/import/API smoke, and old dependency rejection: passed.

GitHub Actions run
[`29428052131`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29428052131)
passed against exact implementation head `0b78eff`. Run
[`29429104699`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29429104699)
passed against exact F5/review head `d85703a`.

No real Accessibility action or WeChat message was executed for this
classification remediation. Historical authorized live evidence remains
performance and integration context; deterministic SDK/error and real worker
protocol tests cover the corrected boundary.

## Finding Ledger

| Finding | State for this F6 snapshot |
| --- | --- |
| `PRR-001` through `PRR-021` | Resolved and revalidated by the prior review/test ledger. |
| `PRR-022` | Resolved; exact native unsupported/no-effect semantics and regressions are implemented and verified. |
| `PRR-023` | Resolved; tracked/platform F6 synchronization was verified by the replacement review. |
| `PRR-024` | Resolved; both stable documents publish one precedence rule. |
| `PRR-025` | Resolved; the emitted unsupported failure is declared and registered in the stable tuple. |
| `PRR-026` | Resolved; only complete, consistent native no-effect proof permits one fallback. |

Historical review reports remain immutable. The `3f792e4` report retains its
`REQUEST_CHANGES` decision for that older snapshot; the `d85703a` replacement
report supersedes it for current merge evaluation.

## Release Record

The committed `CHANGELOG.md` records the selector engine and compatibility
fallback for WeChat rows that omit or reject `AXPress`. No package version,
dependency, command, configuration key, or schema version changes in this
remediation.

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

1. Synchronize the GitHub PR body from the final tracked
   `pr-description.md`.
2. Observe exact-head GitHub CI for this docs-only status update.
3. The repository owner may then mark the PR ready and merge it under normal
   branch protection.

Signed-helper proof and actual package publication remain F7 work.
