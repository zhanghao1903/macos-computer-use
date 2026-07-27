# Code Re-review: Codex Engineering Lifecycle Plugin

## Review metadata

- Repository: `zhanghao1903/macos-computer-use`
- Target: `origin/main...origin/codex/engineering-lifecycle-plugin`
- Base SHA: `1935b33e29586757ec41cc1df4b99aa1ae074a8f`
- Reviewed head: `c8fa2770bc35aac428b5aaf22b1c5fb79ca0f222`
- Review-record branch:
  `codex/review-records/codex-engineering-lifecycle-plugin/code-c8fa277`
- Reviewed at: 2026-07-27 (Asia/Shanghai)
- Review type: `RE_REVIEW`
- Previous report:
  `docs/feature/codex-engineering-lifecycle-plugin/code-review-2026-07-27.md`
- Previous decision: `REQUEST_CHANGES`
- Previous reviewed head: `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- This report supersedes the previous decision for the exact reviewed head.

## Decision

- Decision: `APPROVE`
- Mergeable from code-review perspective: true
- Open blocking findings: 0
- Rationale: all six initial findings and every forward/induced finding were
  reproduced, remediated, tested, and independently re-reviewed. Exact-head
  validation passed for plugin layout, skills, contracts, runtime behavior,
  types, formatting, repository release preflight, and corruption/replay
  counterexamples.

This decision does not authorize merge, release publication, package upload, or
deletion. Live GitHub required checks and mergeability must still be refreshed
for the PR head.

## Re-review scope

Track A verified closure of all prior findings. Track B reviewed the complete
`origin/main...c8fa2770` change and all remediation deltas for induced risks,
with emphasis on:

- three-task Init authority and crash recovery;
- confirmed requirements parsing and pushed-current snapshot binding;
- exact previous-result plan/code re-review;
- Goal single-slot, blocked-state, and retry behavior;
- review-only READY followed by observed external merge;
- release authorization, destination proof, partial retry, replay, closure;
- state corruption, history reconstruction, and v1-to-v2 migration.

Packaged source skills were compared through parity tests. Copied `pr-review`
fixtures/schema/validator were exercised by their packaged tests. Assets and
policy documents were checked by plugin layout and official validators.

## Track A — finding closure

| Finding | Status | Re-review evidence |
| --- | --- | --- |
| `PRR-001` review-only merge dead end | Resolved | Direct review-only `MERGED` is rejected; exact-head `APPROVE/PASSING/READY` must first be applied, then Review may record observed external merge proof for the same request/head. |
| `PRR-002` non-atomic request acceptance | Resolved | Role transition validation and acceptance are one locked mutation; a synthetic transition failure leaves state byte-identical. |
| `PRR-003` message retry timestamp conflict | Resolved | Canonical authority excludes creation time; identical retry returns the original payload/timestamp, while changed authority conflicts. |
| `PRR-004` successful release replay | Resolved | Failed response-loss replay, final partial submission replay, and full cumulative replay are idempotent; another successful subset conflicts. |
| `PRR-005` missing previous-result authority | Resolved | Cycle 1 forbids a prior result; every later plan/code cycle requires the exact latest durable result ID. |
| `PRR-006` unbound release proof URLs | Resolved | GitHub repository/tag/artifact and PyPI/TestPyPI project/version/host/file destinations are canonical and authorization-bound. |
| `ELC-FWD-001` bootstrap acknowledgement deadlock | Resolved | Strict bootstrap-only role acknowledgements are allowed; all feature work remains blocked until all three are durable. |
| `ELC-FWD-002` interrupted Init task duplication | Resolved | Pending Init is written before task creation, each role ID is recorded immediately, and config-only recovery preserves workflow identity. |
| `ELC-FWD-003` unpushed/superseded requirements | Resolved | Deterministic branch/path and exact canonical `origin` tip are required. |
| `ELC-FWD-004` Goal prepare/activate replay | Resolved | Same objective/run is idempotent across PREPARED/ACTIVE/BLOCKED/COMPLETE; changed authority conflicts. |
| `ELC-FWD-005` failing checks at READY | Resolved | READY/MERGED require `APPROVE` and `PASSING`; invalid decision/check/merge combinations fail closed. |
| `ELC-FWD-006` persisted release target deletion | Resolved | Authorization, cumulative result, closure targets, identities, destinations, and digests are revalidated on every load. |
| `ELC-FWD-007` ambiguous successful subset replay | Resolved | Only the exact final submission or complete cumulative result can replay at RELEASED. |
| `ELC-FWD-008` future proof under earlier stage | Resolved | Merge, release, and closure proof are rejected outside their legal stage ranges. |
| `CEL-FWD-001` strict mypy failure | Resolved | Strict mypy reports no issues in both runtime scripts. |
| `IRR-001` unauthorized Init persistence | Resolved | Missing Goal authorization fails before state-root, lock, or pending creation; later authorized Init starts normally. |
| `IRR-002` shadow requirements metadata | Resolved | Five ordered contiguous top metadata fields must each occur exactly once; duplicate/conflicting/reordered/separated blocks fail without mutation. |
| `FWD-REL-001` non-final subset replay | Resolved | Final partial and cumulative replay succeed; arbitrary GH-only subset returns `replay_conflict`. |
| `FWD-REL-002` contradictory stage/proof state | Resolved | CLOSED proof retained under RELEASED, RELEASE_AWAITING_AUTHORIZATION, or MERGED is rejected without mutation. |
| `FWD-REL-003` self-authorizing `lastSubmission` | Resolved | Ordered unique submission history starts with all targets, retries the exact failed set, folds to cumulative proof, and binds its tail to `lastSubmission`. |
| `CEL-FWD-002` state-v1 compatibility regression | Resolved | Locked validation-first migration reconstructs legacy release history and atomically persists state v2; RELEASE_FAILED/RELEASED/CLOSED remain resumable. |

## Track B — forward-risk review

No new finding remains open.

The remediation introduced three sensitive mechanisms:

1. Recoverable Init persistence. Re-review proved missing authorization creates
   no local state, incremental role recording is idempotent, and config-only
   recovery uses the original workflow/task/policy identity.
2. Release submission history. Re-review replaced the history tail with another
   authorized subset, duplicated a target, duplicated a history entry, and
   recomputed local digests. Every corrupted v2 state failed validation.
3. State v1-to-v2 migration. Re-review exercised legacy RELEASE_FAILED,
   RELEASED, and CLOSED shapes. Migration runs under the state lock, constructs
   a candidate, validates full v2 invariants, then atomically writes. Malformed
   v1, missing-history v2, and future v3 state fail without changing bytes.

The version boundary remains explicit:

- config and routed contracts: schema v1;
- local workflow state: schema v2;
- new workflows start at v2;
- state v1 migrates once; no downgrade is attempted.

## Validation evidence

- Full plugin tests:
  `uv run --isolated --with pyyaml --with jsonschema python -m unittest discover -s plugins/codex-engineering-lifecycle/tests -p 'test_*.py' -v`
  — 28/28 passed.
- Strict contract gate:
  `uv run --isolated --with jsonschema python plugins/codex-engineering-lifecycle/scripts/validate_contracts.py --require-jsonschema`
  — 16 fixtures, zero failures, `jsonschema+runtime`.
- Strict types:
  `uv run --isolated --with mypy --with jsonschema --with types-PyYAML mypy plugins/codex-engineering-lifecycle/scripts/workflowctl.py plugins/codex-engineering-lifecycle/scripts/validate_contracts.py`
  — no issues in two source files.
- Ruff check and format — passed; eight Python files formatted.
- Official plugin validator — passed.
- Official skill validator — nine of nine passed.
- Repository `scripts/release_preflight.py` — exit 0; only documented sandbox
  socket and pre-existing external-proof warnings.
- `git diff --check origin/main...c8fa2770` — passed.
- Credential-pattern scan — no matches.
- Three independent scoped exact-head re-reviews — PASS for
  Init/Requirements, plan/Goal/code review, and release/closure/migration.

## Limitations and external gates

- No production Codex tasks were created or messaged during disposable runtime
  tests.
- No real GitHub merge, GitHub Release, TestPyPI, or PyPI publication occurred.
- Live PR checks and GitHub mergeability were not available before PR creation
  and must be refreshed afterward.
- Repository preflight reports existing external proof as unverified; this
  plugin does not modify the package surfaces governed by those proofs.
- Process-kill fault injection was not performed; byte-identical failure checks
  plus lock → validate → atomic-write ordering provide local persistence
  evidence.

## Machine-readable summary

```json
{
  "schemaVersion": "review-summary.v1",
  "reviewType": "RE_REVIEW",
  "baseSha": "1935b33e29586757ec41cc1df4b99aa1ae074a8f",
  "headSha": "c8fa2770bc35aac428b5aaf22b1c5fb79ca0f222",
  "previousHeadSha": "a1dd2b865e8ac407cad29d82706ff5acb12f13ea",
  "previousDecision": "REQUEST_CHANGES",
  "decision": "APPROVE",
  "mergeable": true,
  "blockingFindingIds": [],
  "supersedes": "docs/feature/codex-engineering-lifecycle-plugin/code-review-2026-07-27.md"
}
```
