# Implementation Rejection Patterns

Load the sections relevant to the current risk ledger. Use the patterns to
design implementation and counterexamples before code; do not copy every check
into low-risk work.

## Contents

1. Public contract propagation
2. Mutation outcome and replay
3. Target identity and stale references
4. Query bounds, cache, pagination, and performance
5. Contract-execution parity and atomic configuration
6. Failure routing and retryability
7. Privacy and observability
8. Dependencies, packaging, CI, and release environments
9. Vacuous or synthetic-only proof
10. Exact-head evidence integrity
11. Remediation-induced risk
12. Adversarial matrices

## 1. Public Contract Propagation

### Signals

- New field, enum, failure kind, config value, operation, or serialized shape.
- A producer changes while registry, exports, docs, consumers, or dependency
  floors remain untouched.
- Tests import source directly but do not inspect built packages.

### Implementation Response

Trace the exact value through producer, normalization, stable registry/export,
serialization/schema, docs, consumer/recovery, package boundary, wheel, and old
dependency behavior. Mark each stage pass or `N/A` with a reason.

### Required Evidence

- Producer-to-consumer contract test using the real producer shape.
- Registry uniqueness and public import check.
- Clean wheel/install test when the value is package-visible.
- Minimum dependency rejection or compatibility proof.

### Derived Findings

`PRR-005`, `PRR-010`, `PRR-011`, `PRR-025`, `PRR-036`.

## 2. Mutation Outcome And Replay

### Signals

- Retry, fallback, timeout, worker recovery, keypress/click after another
  action, or any branch that can issue a second side effect.
- Evidence duplicated across metadata, observation, diagnostics, transport, or
  error payloads.

### Implementation Response

Model dispatch and effect separately. Permit a second mutation only for a
reviewed pre-dispatch or exact definite-no-effect case. Treat missing,
malformed, contradictory, timeout-after-dispatch, transport loss, and unknown
effect as no-replay. Bind every evidence copy to the requested action/target.

### Required Evidence

- Positive valid tuple plus missing, wrong-type, malformed, duplicate-agree,
  duplicate-conflict, cross-field contradiction, timeout, EOF, and version-skew
  cases.
- Operation count and order for every shared caller.
- Real worker/protocol normalization when hand-built fixtures could mask gaps.

### Derived Findings

`PRR-018`, `PRR-019`, `PRR-020`, `PRR-021`, `PRR-022`, `PRR-026`.

## 3. Target Identity And Stale References

### Signals

- App name/bundle targeting, keyboard input, coordinates, cached AX paths,
  action references, contact rows, focus, or reordered lists.

### Implementation Response

Require evidence appropriate to the action risk: current frontmost identity,
focused target, signature/preconditions, fresh snapshot, and unambiguous
semantic match. Treat coordinates as an explicitly enabled fallback with
current bounds/identity checks, never the preferred unverified target.

### Required Evidence

- Wrong-frontmost, hidden, terminated, multiple-instance, stale snapshot,
  reordered list, ambiguous match, and focus-unknown cases.
- Zero side effects for mismatch and unknown state.

### Derived Findings

`PRR-002`, `PRR-003`, `PRR-014`, `PRR-015`, `PRR-032`.

## 4. Query Bounds, Cache, Pagination, And Performance

### Signals

- Limit, depth, time budget, batch, lookahead, cursor, cache, page size, or
  latency target.
- Raw rows are filtered into semantic items.
- Partial/truncated results may influence a target decision.

### Implementation Response

- Bound all resource dimensions consistently across callers and transports.
- Fail closed before pick/cache/mutation on decision-critical truncation unless
  a reviewed partial-result policy proves safety.
- Revalidate cached predicates and signatures.
- Count accepted semantic records, not raw rows; find one accepted lookahead
  for `hasMore` within explicit work bounds.
- Distinguish normal limit-plus-one lookahead from backend truncation.

### Required Evidence

- Empty, exact limit, limit plus one, maximum, noisy leading/middle rows,
  visible exhaustion, time/limit truncation, stale cache, hidden better or
  duplicate candidates, and real normalizer bounds.
- Latency/operation budget evidence for declared performance contracts.

### Derived Findings

`PRR-004`, `PRR-006`, `PRR-008`, `PRR-009`, `PRR-016`, `PRR-017`,
`PRR-028`, `PRR-031`, `PRR-034`.

## 5. Contract-Execution Parity And Atomic Configuration

### Signals

- Parser accepts steps/fields/policies runtime does not execute.
- Multiple components load related configuration independently.
- Optional override can be half valid.

### Implementation Response

Implement every accepted semantic or reject it during validation before any
query/action. Parse related configuration once, validate all components, then
publish one immutable pair/version. Fall back or fail as one transaction.

### Required Evidence

- Unsupported extra steps, roots, pick/cache/fallback/confidence/relation, and
  wrong-container decoys fail before work.
- Both half-valid override directions, invalid syntax, missing sections, valid
  pair identity, and reload/construction behavior.

### Derived Findings

`PRR-029`, `PRR-030`.

## 6. Failure Routing And Retryability

### Signals

- Generic exception mapping, message keyword heuristics, nested causes, timeout
  labels, or new transport/worker failures.

### Implementation Response

Preserve the most specific structured failure and cause. Derive retryability
from dispatch/effect and recovery semantics, not only the category name. Use
free text only when structured cause is absent or explicitly unknown. Keep
not-found distinct from permission, timeout, transport, and truncation.

### Required Evidence

- Known structured cause plus adversarial message containing another category.
- Unknown/missing cause fallback.
- Registry/export coverage for every emitted public value.
- Caller-visible status, retryability, hint, and nested diagnostics.

### Derived Findings

`PRR-007`, `PRR-020`, `PRR-025`, `PRR-035`, `PRR-036`.

## 7. Privacy And Observability

### Signals

- Accessibility nodes, message/contact text, window titles, raw payloads,
  screenshots, logs, events, evidence, smoke proof, or public release assets.

### Implementation Response

Define semantic output separately from operational diagnostics. Allowlist
normal evidence/log fields. Make raw/private output explicit and authorized;
keep it out of normal results, logs, CI artifacts, release proof, and public
uploads. Apply privacy review to progress and error paths, not only success.

### Required Evidence

- Private canaries before, within, and beyond semantic limits.
- Result, error, progress/final event, redacted logger, raw-disabled inspection,
  and release bundle assertions.
- Explicit raw/debug positive behavior tested separately.

### Derived Findings

`PRR-001`, `PRR-033`.

## 8. Dependencies, Packaging, CI, And Release Environments

### Signals

- New cross-package symbol or behavior, dependency floor, build backend,
  editable-only success, workflow source path, or release proof.

### Implementation Response

Test from a clean environment with declared dependency floors. Build and
inspect wheels/sdists, install them together, import public symbols, run API
smoke, and reject incompatible old dependency sets. Reproduce CI/release path
construction rather than assuming workspace imports.

### Required Evidence

- Clean checkout or isolated build/install.
- Wheel content/metadata/no-bytecode and public import checks.
- Minimum dependency and workflow path tests.
- No private/live data in public artifacts.

### Derived Findings

`PRR-005`, `PRR-010`, `PRR-011`.

## 9. Vacuous Or Synthetic-Only Proof

### Signals

- Smoke succeeds with zero records, optional assertion, or broad exception.
- Test constructs the consumer payload by hand instead of invoking the changed
  producer/normalizer.
- Test checks success status but not target, data, or side effects.

### Implementation Response

Make the test fail when the critical path is absent. Assert non-empty or exact
semantic output where required. Use production-generated scripts/payloads for
cross-layer contracts and keep hand-shaped fixtures only for isolated parser
cases.

### Required Evidence

- Mutation test proving the test fails for an unregistered value, replay, wrong
  target, zero result, or bypassed producer.
- Explicit assertions for operation count/order, output identity, and negative
  path reachability.

### Derived Findings

`PRR-012`, plus repeated reopenings of `PRR-021`, `PRR-022`, and `PRR-026`.

## 10. Exact-Head Evidence Integrity

### Signals

- Validation runs on a parent commit, report commit changes head, stale hashes,
  three-dot versus two-dot range, or changed files absent from risk coverage.

### Implementation Response

Bind each run to a full head SHA and record the exact command/environment.
Reconcile previous-head-to-current-head and base-to-current-head ranges. Do not
claim another head's broad test as current-head proof. Treat a report commit as
a new head requiring renewal.

### Required Evidence

- Full SHA, exact two-dot ranges, complete changed-file classification, clean
  tree, current-head CI, valid predecessor hashes, and machine validator output
  where applicable.

### Derived Findings

`PRR-023`, `PRR-027`.

## 11. Remediation-Induced Risk

### Signals

- A finding fix widens fallback, changes protocol values, adds caching, changes
  failure routing, or updates lifecycle evidence.
- Old regression passes but surrounding behavior changed.

### Implementation Response

Run two tracks:

1. prove each prior finding's verification criteria on the current head;
2. treat the remediation diff as new untrusted content and inspect every
   changed path, caller, trust boundary, contract, and negative case.

Use a fresh context when possible. Do not provide the second pass only the
expected answer.

### Required Evidence

- Prior finding ledger with current-head proof.
- Forward-risk surfaces covering every remediation path.
- New/changed contract propagation and adversarial cases.
- Exact-head broad tests and independent review handoff.

### Derived Findings

Repeated reopening and expansion from `PRR-018` through `PRR-036`.

## 12. Adversarial Matrices

### Mutation Matrix

| Dispatch | Effect | Evidence | Allowed follow-up |
| --- | --- | --- | --- |
| false | none | complete and consistent | reviewed fallback may run once |
| true | definite no-effect | exact allowlisted producer/action/code tuple | reviewed compatibility fallback may run once |
| true | performed | any | none |
| true | unknown | any | none |
| unknown | any | missing/malformed/transport loss | none |
| any | any | contradictory copies | none |

### Query Decision Matrix

| Query state | Use for read output | Use for target decision/cache/mutation |
| --- | --- | --- |
| complete and unambiguous | yes | yes after preconditions |
| partial under explicit semantic policy | policy-dependent | no unless design proves safety |
| truncated with candidate present | diagnostic/partial only | no |
| stale cache/ref | no until revalidated | no |
| permission/timeout/transport failure | no | no; preserve structured cause |

### Configuration Matrix

| Generic component | Adapter component | Activation |
| --- | --- | --- |
| valid | valid | activate one versioned pair |
| valid | invalid | reject/fallback both |
| invalid | valid | reject/fallback both |
| invalid | invalid | reject/fallback both |
