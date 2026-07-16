# Accessibility Selector Engine Merge Readiness

- Updated: 2026-07-16
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Verified implementation/evidence head:
  `f19cbd9`
- Current review:
  [`pr-review-macos-computer-use-3-f19cbd9.md`](./pr-review-macos-computer-use-3-f19cbd9.md),
  published at `412a2d3`
- Current decision: `APPROVE`; no blocking findings remain for the reviewed
  `f19cbd9` snapshot

## Remediation Status

The `1e56b00` review reopened `PRR-021`, `PRR-022`, and `PRR-026` after
exercising the real producer-to-consumer path and malformed evidence. All three
blockers are now resolved, and `PRR-025` remains resolved:

- `b4026ee` amends the end-to-end proof contract: the native producer owns the
  requested action, the consumer binds proof to its outbound action, and
  attempted/dispatch evidence is presence-sensitive;
- `da4e011` records the file-level remediation and verification plan;
- `65f8855` implements the producer, normalizer, recovery parser, caller, and
  adversarial test changes;
- F5 evidence at `f19cbd9` records clean-clone package/root verification, 350
  unsafe stress outcomes with zero second mutation, 20 valid production-pair
  fallbacks, preflight, compile, and wheel checks;
- exact-head GitHub Actions run `29463591047` passed;
- the `f19cbd9` replacement review is published at `412a2d3` with decision
  `APPROVE` and no blocking findings.

The replacement report is the authoritative implementation review. This final
docs-only update makes its decision discoverable from both F6 entry points; it
does not change runtime behavior or independently change the PR draft state.

## Corrected Recovery Contract

The direct backend reports three native action effect states:

| Result | Public evidence | Higher-level recovery |
| --- | --- | --- |
| Native success | `actionAttempted=true`, `actionEffect=performed` | Continue without fallback. |
| `AXPress/-25206` or `AXSetFocus/-25205` | Registered `failureKind=accessibility_action_unsupported`, exact requested action/code pair, `actionAttempted=true`, `actionEffect=none` | Permit exactly one existing policy-gated fallback. |
| Any other native error, including `-25204` | `failureKind=accessibility_action_failed`, `actionAttempted=true`, `actionEffect=unknown`, `nativeErrorCode` | Stop; do not mutate again. |

The generated native failure includes the validated requested action.
`ComputerUseClient` promotes attempted evidence only when its raw value is an
actual Boolean. The WeChat adapter requires every public, metadata, alias, and
nested proof field to have the expected type, agree, and match the outbound
request action.

Attempt and dispatch evidence is represented as absent, valid true, valid
false, or invalid. Non-Boolean truthy/falsey values, malformed containers,
conflicting aliases, missing proof, wrong action/code or request/response
pairing, EOF, timeout, and unknown dispatch outcomes remain fail-closed. Once
an allowed fallback is issued, its result is final.

## Verification

Clean-clone verification of implementation head `65f8855`, with exact-head
decision tests and CI at `f19cbd9`:

- root repository: 127 passed in 42.752 seconds;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 144 passed, 1 skipped, with `ResourceWarning` treated
  as an error;
- `wechat-desktop-tool`: 140 passed with `ResourceWarning` treated as an
  error;
- six decision-focused methods repeated ten times: 10/10 passes, 350 unsafe
  subcases with zero second mutation and 20 valid production-generated pairs
  with one fallback each;
- compile, release preflight, whitespace, clean-tree, three-wheel build,
  isolated install/import/API smoke, and old dependency rejection: passed.

GitHub Actions run
[`29463591047`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29463591047)
passed against exact F5/review head `f19cbd9`.

No real Accessibility action or WeChat message was executed for this
classification remediation. Historical authorized live evidence remains
performance and integration context; deterministic SDK/error and real worker
protocol tests cover the corrected boundary.

## Finding Ledger

| Finding | State for this F6 snapshot |
| --- | --- |
| `PRR-001` through `PRR-020` | Resolved and revalidated by the prior review/test ledger. |
| `PRR-021` | Resolved; malformed or contradictory attempted/dispatch evidence cannot authorize fallback. |
| `PRR-022` | Resolved; the production-generated native result carries action and both valid pairs retain one fallback. |
| `PRR-023` | Resolved; tracked/platform F6 synchronization was verified by the replacement review. |
| `PRR-024` | Resolved; both stable documents publish one precedence rule. |
| `PRR-025` | Resolved; the emitted unsupported failure is declared and registered in the stable tuple. |
| `PRR-026` | Resolved; only complete proof matching the outbound request action permits one fallback. |

Historical review reports remain immutable. The `1e56b00` report retains its
`REQUEST_CHANGES` decision for that older snapshot; the `f19cbd9` replacement
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

1. Synchronize the GitHub PR body from this tracked `pr-description.md`.
2. Observe exact-head GitHub CI for this report/status-only delta.
3. Renew the final review over the report/status-only delta.
4. The repository owner may then mark the PR ready and merge it under normal
   branch protection.

Signed-helper proof and actual package publication remain F7 work.
