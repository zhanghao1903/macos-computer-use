# Re-review and Approval Renewal Gates

Use this reference whenever a PR already has a review report, a finding is
being revalidated, or the reviewed base/head changed. Execute the gates in
order; do not treat a re-review as a test-only confirmation of old findings.

## Contents

1. Invalidate and freeze
2. Reconcile both diffs
3. Run the two review tracks
4. Apply propagation and adversarial gates
5. Resolve decision-critical assumptions
6. Renew approval

## 1. Invalidate and freeze

1. Starting a re-review supersedes the previous decision for the current
   workflow even when the SHAs are unchanged; never inherit an old approval.
2. When either reviewed base SHA or head SHA changes, additionally mark the
   previous report `STALE`.
3. Freeze the current base/head SHAs and record the previous report, decision,
   base/head SHAs, and blocking finding IDs.
4. Do not carry `mergeable=true` or an approval link into the new decision.

## 2. Reconcile both diffs

Inspect and classify both views:

- previous head to current head: every new commit and changed file;
- current base to current head: the complete effective PR diff.

Record all delta commits/files and any unclassified change. An unclassified
change prohibits `APPROVE`. For a large PR, partition by behavior/risk area and
give every partition an explicit reviewed or excluded status; a decision-
relevant unreviewed partition requires `INCOMPLETE`.

## 3. Run the two review tracks

### Track A: prior-finding closure

- Preserve each finding ID.
- Mark `resolved` only with current-head code evidence and the finding's
  verification criteria.
- Mark `false-positive` only with concrete counter-evidence.
- Mark `accepted-risk` only with an explicitly authorized accepter, rationale,
  and time. The reviewer cannot invent risk acceptance or silently use it to
  clear a blocker.

### Track B: forward-risk review

Treat every remediation commit as new, untrusted PR content. Independently
inspect its surrounding code, callers, consumers, tests, documentation, and
affected behavior paths. Passing Track A never permits skipping Track B.

Create an induced-risk entry for each new or widened contract, trust boundary,
side effect, recovery rule, state transition, dependency, configuration, or
deployment behavior. Record the paths and discriminating checks for each entry.

## 4. Apply propagation and adversarial gates

For a new or changed public field, enum, error/failure kind, protocol value, or
serialized shape, trace and verify:

`producer -> normalization -> registry/enum -> export -> serialization -> docs -> consumer -> executable contract test`

Do not rely only on source-text regexes when runtime generation can emit values.
Exercise representative real observations and prove that every emitted public
value is declared and consumable. If a test claims exhaustive registration,
demonstrate that it fails for an intentionally unregistered representative
value. Mark an inapplicable propagation stage `N/A` with a reason; any
applicable `UNKNOWN` stage prohibits `APPROVE`.

For retry, fallback, fail-open/fail-closed, or any gate that can authorize a
second mutation, test the valid positive tuple plus these negative classes:

- missing and empty evidence;
- wrong types and malformed values;
- duplicate values that agree and conflict;
- cross-field contradictions;
- unknown, partial-failure, timeout, and transport-loss outcomes;
- version-skewed or compatible custom producer shapes.

Assert side-effect count and order, not only the returned status. If malformed
or contradictory evidence can authorize mutation or replay, treat it as a
correctness/safety finding rather than optional hardening.

## 5. Resolve decision-critical assumptions

Verify every locally decidable assumption that can change the decision. If a
decision-critical assumption is unverified or cannot be verified with the
available context, do not approve; use `INCOMPLETE` unless an independently
proven blocker already requires `REQUEST_CHANGES`.

## 6. Renew approval

Issue a new `APPROVE` only when all are true:

- every prior blocker is revalidated at the current head;
- every delta commit/file is classified and the full PR diff is reconciled;
- Track B and all induced-risk checks are complete without a failing result;
- decision-critical assumptions are verified;
- required validation and CI belong to the current head;
- no open blocker or decision-blocking limitation remains;
- the report explicitly supersedes the previous report.

When independent agents are available, use a fresh-context pass for S0-S2
remediation or changes to public contracts, trust boundaries, or mutation
recovery. Give it frozen raw artifacts, not the expected findings. Otherwise,
perform a separate second pass and disclose the limitation.

Do not commit the report to the reviewed branch before freezing the final
decision: that commit changes the head and invalidates its own snapshot. If a
repository requires tracked review reports on the PR branch, classify and
review the report-only delta, wait for exact-head checks, and issue a final
replacement report bound to that head.

If base or head changes again, restart at Gate 1.
