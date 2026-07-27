# Code Review Remediation: Codex Engineering Lifecycle Plugin

- Date: 2026-07-27
- Initial review:
  [code-review-2026-07-27.md](code-review-2026-07-27.md)
- Reviewed head: `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- Initial decision: `REQUEST_CHANGES`
- Remediation scope: `PRR-001` through `PRR-006`

## PRR-001 — Review-only merge path

Implemented a two-result, same-request transition:

1. Review returns exact-head `APPROVE`, passing checks, and `READY`.
2. Main applies it and waits at `MERGE_READY`.
3. A separately authorized human or merge owner performs the merge.
4. Review refreshes external state and returns observed `MERGED` proof for the
   same request/report.

The runtime requires the prior result to be applied, bound to the same request
and PR snapshot, `APPROVE`, passing, and exactly `READY`. Direct review-only
`MERGED` remains rejected. `merge-on-approve` retains its existing configured
method gate.

## PRR-002 — Atomic acceptance

`accept_request` now receives a role-specific transition validator and executes
it inside the same file lock before mutating dispatch status. Requirements
artifact acceptance and stage transition also happen in that transaction.

A synthetic failing transition test snapshots the state bytes, raises after
validation begins, and proves the command leaves state byte-identical.

## PRR-003 — Deterministic message retry

`record_message` now compares canonical authority, which intentionally excludes
the non-authorizing creation timestamp. An unchanged retry returns the first
stored payload and original timestamp. A same-ID authority difference fails as
`replay_conflict`.

Duplicate bootstrap, dispatch, and acceptance operations also preserve their
original status timestamps.

## PRR-004 — Successful release replay

`record-release-result` accepts `RELEASED` only as a strict replay:

- submitted target IDs must be authorized;
- each normalized submitted target must exactly match durable successful proof;
- the final publication timestamp must match;
- the cumulative stored result is returned with `duplicate: true`;
- no state mutation occurs.

Both one-shot full results and final failed-target-only retry payloads can be
replayed safely.

## PRR-005 — Exact re-review authority

Cycle 1 rejects `previousResultMessageId`. Every later plan/code cycle requires
the exact latest durable result ID. Missing, wrong, older, or unrelated IDs fail
before request creation. A stale code result is now retained as the authority
for the next cycle.

Result preparation also requires an accepted, current pending request rather
than merely a dispatched request.

## PRR-006 — Destination-bound release proof

Runtime proof validation now requires:

- canonical credential-free GitHub release and asset URLs for the authorized
  repository/tag/artifact filename;
- no URL port, query, or fragment;
- normalized Python project names;
- canonical PyPI/TestPyPI project URL for the authorized project/version;
- expected `files.pythonhosted.org` or
  `test-files.pythonhosted.org` artifact host and filename.

Integration counterexamples prove cross-repository GitHub and cross-project
PyPI URLs fail without state mutation.

## Forward-risk hardening

While reviewing remediation interactions, the runtime's state validator was
expanded to fail closed on:

- unknown feature/dispatch fields;
- malformed feature metadata, counters, artifacts, review snapshots, merge,
  release, or closure proof;
- missing stage-required authority;
- queue/stage or active Goal/status inconsistencies;
- malformed dispatch ledgers or payload-digest/routing/workflow mismatches.

The integration test injects an unknown authority field and proves `status`
rejects the corrupted state before restoring the fixture.

## Fresh-context forward-test remediation

Three isolated read-only forward tests exercised Init/Requirements,
plan-development-review, and release/closure. Their initial decisions were
FAIL. All reported paths were reproduced and remediated:

- `ELC-FWD-001` (bootstrap deadlock): every role now has a strict
  bootstrap-only `EngineeringRoleReady` exception, while runtime rejects
  feature work until all three acknowledgements are durable.
- `ELC-FWD-002` (interrupted Init duplication/config-only crash): Init now
  writes `init-pending.json` before task creation, records each role ID
  immediately, exposes pending IDs through status, and reconstructs the
  config-written/state-missing window with the same workflow identity.
- `ELC-FWD-003` (unpushed/superseded requirements): requirements now require
  the deterministic feature branch/path and the exact authoritative
  `origin` branch tip.
- `ELC-FWD-004` (Goal response-loss replay): deterministic prepare and activate
  calls reuse PREPARED/ACTIVE/BLOCKED/COMPLETE runs, preserve timestamps, and
  return `duplicate: true`; changed objectives still conflict.
- `ELC-FWD-005` (failing checks at READY): the decision/check/merge matrix now
  requires `APPROVE` plus `PASSING` for READY, MERGED, and merge FAILED, and
  binds READY/FAILED to their permitted merge modes.
- `ELC-FWD-006` (persisted release target deletion): every state load now
  canonicalizes authorization and cumulative result proof, requires exact
  authorized target equality, validates destinations/artifacts/IDs/digests,
  and binds closure targets exactly to the cumulative result.

The end-to-end test now includes incremental Init recovery, global-bootstrap
blocking, unpushed/superseded requirements rejection, plan FAIL/remediation/
re-review, Goal prepare/activate replay, code REQUEST_CHANGES/new remediation
Goal/re-review, failing READY rejection, partial release retry, missing-target
and missing-ID state corruption, and arbitrary closure-target corruption.

## Final release/state forward-test remediation

The release/closure recheck found two additional fail-closed gaps. Both were
reproduced and fixed:

- `ELC-FWD-007` (ambiguous successful subset replay): each accepted release
  result now persists the canonical last submission beside the cumulative
  result. At `RELEASED`, only an exact replay of that submission or the complete
  cumulative result is idempotent; another valid successful subset fails with
  `replay_conflict`.
- `ELC-FWD-008` (future proof under an earlier stage): state validation now
  applies inverse stage invariants. Merge, release, and closure proof cannot
  survive a declared rollback to a stage where that proof is not yet legal.

Integration coverage now rejects a non-final successful subset, accepts the
final partial submission and full cumulative result as exact replays, and
rejects `CLOSED` state rewritten to `RELEASED`,
`RELEASE_AWAITING_AUTHORIZATION`, or `MERGED` while retaining future proof.

## Final Init/Requirements and release-ledger remediation

The exact-commit re-review found three further forward risks:

- `IRR-001` (unauthorized Init persistence): `begin-init` now rejects missing
  Goal-mode authorization before resolving any state path, acquiring the lock,
  or writing pending state. The proposed pending record is fully validated
  before its first write. The integration test proves the failure leaves
  `CODEX_HOME` absent and a later authorized Init starts normally.
- `IRR-002` (shadow requirements metadata): the parser now requires the five
  authority fields exactly once, in order, contiguously, within the first
  40 lines. Duplicate Confirmed/Draft blocks are rejected before feature or
  dispatch mutation, even at the authoritative pushed branch tip.
- `FWD-REL-003` (self-authorizing `lastSubmission`): release state now stores
  ordered immutable submission history. The first entry covers all authorized
  targets; each retry covers exactly the preceding failed target set; targets
  and history digests are unique; folding the history must equal cumulative
  proof; and the final entry must equal `lastSubmission`.

New counterexamples rewrite both `lastSubmission` and its final history entry
to a different authorized successful subset, or duplicate a target while
recomputing its digest. Both states fail validation. Exact failed-result replay
returns without appending a duplicate history entry.

## Updated documentation

Role skills and user/design docs now explain:

- review-only READY followed by observed external MERGED proof;
- original-payload message retry;
- exact previous-result binding;
- cumulative partial release retry and successful replay;
- destination-bound GitHub/PyPI proof;
- blocked GoalRuns occupying the single global slot.

## Verification

Focused standard-library tests pass for:

- deterministic message retry and conflict;
- initial/re-review previous-result gates;
- atomic acceptance rollback;
- review-only direct-MERGED rejection;
- READY then observed MERGED;
- cross-destination release-proof rejection;
- partial failure and failed-target-only retry;
- successful release-result replay;
- state corruption rejection;
- final closure.

Full official/plugin/repository validation is rerun before the remediation
commit and recorded in the re-review report.
