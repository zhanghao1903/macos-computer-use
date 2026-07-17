---
name: implementation-execution
description: Execute approved implementation plans and PR-remediation work with changed-surface mapping, risk-ledger, vertical-slice, adversarial-test, exact-head evidence, and review-handoff gates. Use when Codex is asked to implement a non-trivial feature, fix review findings, change public APIs/protocols/configuration/failure behavior, or modify desktop automation, mutation/retry/fallback, target selection, cache/pagination, privacy, packaging, or cross-package behavior. Do not use this skill to approve a design or PR, merge, publish, or release.
---

# Implementation Execution

Turn an approved plan into review-ready implementation without treating tests
or author confidence as approval. Own implementation quality and evidence;
leave lifecycle transitions to `feature-lifecycle`, design decisions to the
technical-plan workflow, and merge decisions to an independent review.

## Required Inputs

Before editing, identify:

- feature and user/developer scenario;
- dedicated branch, frozen base SHA, and starting head SHA;
- approved requirements, design/review, and implementation plan;
- acceptance criteria and explicit non-goals;
- affected package/module boundaries;
- authorization limits for mutation, private data, external services, merge,
  and release;
- unresolved decisions and unrelated dirty files.

For small isolated fixes, use a compact record. For public contracts,
cross-package work, desktop mutation, retries/fallbacks, concurrency, privacy,
packaging, or review remediation, require the full workflow.

## Implementation Gate Report

Emit this short report before file edits:

- Feature / branch / base / starting head:
- Approved inputs:
- Scenario and acceptance criteria:
- Scope and package boundaries:
- Public contract impact:
- Mutation, privacy, compatibility, and release impact:
- Anticipated changed paths:
- Risk surfaces and counterexamples:
- Planned slices:
- Required tests, docs, packaging, and smoke proof:
- Authorization limits:
- Blockers / assumptions:

Do not use the report to hide missing decisions. Stop and return to the owning
requirements/design/plan phase when a correctness, security, privacy,
compatibility, mutation, or release decision cannot be inferred safely.

## Workflow

### 1. Freeze Context And Scope

1. Confirm one feature per branch and isolate unrelated changes.
2. Record full base and starting-head SHAs.
3. Read approved artifacts and relevant architecture, APIs, callers, tests,
   configs, packaging, and release checks before coding.
4. Convert acceptance criteria into observable behavior and failure outcomes.
5. Mark assumptions. Verify every locally decidable, decision-critical one.

If implementation needs behavior absent from the approved plan, update the
plan and its review before continuing. Do not silently invent the contract.

### 2. Build Changed-Surface And Risk Ledgers

List anticipated files and map each to at least one behavior/risk surface.
For each surface record:

| Field | Required content |
| --- | --- |
| Surface | Behavior or contract boundary |
| Triggers | Public contract, trust boundary, mutation, state, privacy, concurrency, deployment, test adequacy |
| Paths | Expected files/modules |
| Behavior path | Input through producer, normalization/state, consumer, failure, output |
| Invariants | What must remain true |
| Counterexamples | Negative cases defined before implementation |
| Checks | Tests, build, inspection, smoke, or package proof |
| Status | `planned`, `implemented`, `verified`, or `blocked` |

Classify newly discovered files immediately. An unclassified changed path
blocks `ready_for_review`.

Load [references/rejection-patterns.md](references/rejection-patterns.md) when
the change touches public contracts, mutation/recovery, targets, selectors,
cache/pagination, privacy, configuration, failures, dependencies, packaging,
CI, or review remediation.

### 3. Plan Vertical Slices And Counterexamples

Make each slice deliver one coherent scenario with code, tests, docs,
diagnostics, compatibility, and rollback together. Record:

- scenario and expected behavior;
- files and contracts;
- risk surfaces;
- positive and adversarial cases;
- target tests and exact operation/state assertions;
- docs and changelog impact;
- rollback/disable path.

Define discriminating counterexamples before coding. Scale them by risk:

- missing, empty, wrong type, malformed, duplicate, and contradictory values;
- zero, one, minimum, maximum, exact limit, limit plus one, timeout, and
  truncation;
- stale cache/ref, reorder, ambiguity, multiple instances, and wrong target;
- transport loss before dispatch, after dispatch, and unknown outcome;
- partial config, older dependency, producer/consumer version skew;
- private canaries beyond semantic output limits.

For side effects, assert count and order. A status-only assertion does not prove
no replay or idempotency.

### 4. Implement Contract And Execution Together

- Follow existing package/module patterns and preserve unrelated behavior.
- Keep parser/config acceptance equal to runtime execution. Implement accepted
  semantics fully or reject them before side effects.
- Prefer structured parsers, typed values, stable registries, and one source of
  truth over duplicated interpretation.
- Fail closed when target identity, preconditions, completeness, or mutation
  outcome is uncertain.
- Bound time, depth, nodes, batches, retries, memory, and pagination work.
- Treat cache entries and action references as hints requiring current-state
  validation before use.
- Activate related configuration components atomically.
- Keep normal evidence/logs semantic and allowlisted; make raw/private output
  explicit and authorized.

For every public or semi-public field, enum, failure kind, config value, or
serialized shape, trace:

```text
producer -> normalization -> registry/export -> serialization/schema
         -> docs -> consumer/recovery -> contract/package/wheel test
```

Mark a stage `N/A` with a reason. An applicable `UNKNOWN` stage blocks slice
completion.

### 5. Apply Mutation And Recovery Gates

For retry, fallback, timeout, cancellation, or any possible second side effect:

1. Distinguish not dispatched, dispatched, performed, definite no-effect, and
   unknown outcome.
2. Treat unknown or contradictory outcome as no-replay.
3. Validate every supported evidence container with presence and type
   sensitivity; do not trust truthiness or one preferred copy.
4. Bind evidence to the exact requested action and target.
5. Let structured failure/effect values override free-text messages.
6. Permit a fallback only when the reviewed contract proves it safe.
7. Test all shared callers and assert operation count/order.

Do not generalize a compatibility exception beyond its exact producer,
action, error/effect tuple, and version contract.

### 6. Verify Each Slice

Run the smallest discriminating checks first, then broaden by blast radius:

- focused unit and regression tests;
- cross-layer/contract tests using production producers and normalizers;
- package-boundary, clean-install, dependency-floor, and wheel tests;
- compile/type/lint/format checks configured by the repository;
- release preflight for public docs, APIs, schemas, packaging, or examples;
- authorized real smoke only when deterministic tests cannot prove the
  environment-specific behavior.

Reject vacuous proof. A smoke that accepts zero results, a fixture that bypasses
the real producer, or a test that never reaches the risky branch does not count.

Record exact command, environment, head SHA, exit status, result, and skipped
proof. Never reuse passing evidence from another head as exact-head evidence.

### 7. Record, Commit, And Push The Slice

Update the feature's implementation record with:

- behavior implemented and non-goals preserved;
- changed files and risk-surface status;
- contract propagation and compatibility decisions;
- counterexamples and validation results;
- deferred/manual proof and residual limitations;
- rollback notes.

Commit code, tests, and implementation documentation together after required
slice checks pass. Push the slice before starting the next one when the
lifecycle requires phase/slice traceability. Do not stage unrelated dirty
files, tokens, raw observations, smoke outputs, build artifacts, or local locks.

### 8. Run Review Preflight On The Final Head

After all slices:

1. Freeze the candidate head.
2. Reconcile every commit and changed file from base to head.
3. Verify every changed path belongs to a risk surface or has an explicit
   exclusion reason.
4. Perform a fresh forward-risk pass over the raw diff and surrounding callers.
   Do not seed it only with expected prior findings.
5. Recheck trust boundaries, mutation recovery, public propagation, privacy,
   compatibility, generated code, packaging, and lifecycle evidence.
6. Use a fresh agent/context when available. Otherwise restart from raw
   artifacts and disclose same-agent second-pass limits.
7. Run required broad checks on the exact candidate head in a clean or
   demonstrably isolated tree.
8. Re-run if the head changes.

The implementation preflight may conclude `ready_for_review` or `blocked`. It
must not conclude `APPROVE`, `mergeable`, or release-ready.

## Review Remediation Mode

When fixing review findings:

1. Freeze the prior report, finding IDs, previous head, current base, and
   verification criteria.
2. Build one slice per coherent root cause, not necessarily one per comment.
3. Reproduce each finding before the fix when safe and deterministic.
4. Prove prior-finding closure on the new head.
5. Treat every remediation edit as untrusted new content and run the full
   forward-risk workflow.
6. Preserve public compatibility and finding intent; do not replace the user
   requirement with a safer but different behavior.
7. Update implementation and verification artifacts, commit/push, then hand
   the exact head to independent re-review.

Passing old regression tests does not prove the remediation introduced no new
risk.

## Review Handoff

Return this concise implementation dossier:

- Feature / branch:
- Base SHA / exact head SHA:
- Scenario solved and behavior changed:
- Commits and complete changed-file list:
- Risk surfaces and final statuses:
- Public contract propagation:
- Mutation/privacy/compatibility decisions:
- Exact validation commands and results:
- Checks not run and reasons:
- Residual risks / assumptions:
- Highest-risk paths for reviewer focus:
- Status: `ready_for_review` or `blocked`

If the report itself must be committed, do not confuse the report commit with
approval of the new head. Formal review must bind its decision to the final
immutable snapshot.

## Stop Conditions

Stop and report `blocked` when any of these remains:

- decision-critical requirement, design, or authorization is unclear;
- accepted configuration/runtime behavior diverges;
- mutation may replay after an unknown or contradictory result;
- target identity or stale-reference preconditions are insufficient;
- bounded work or semantic completeness cannot be proven;
- private/raw data can enter normal logs, reports, or release assets;
- a public contract has an unknown propagation stage;
- changed paths remain unclassified;
- required tests fail, pass vacuously, or belong to another head;
- the requested action requires unapproved live mutation, merge, publish, or
  release.
