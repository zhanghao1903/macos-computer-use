# Implementation Plan: Implementation Execution Skill

- Feature directory: `docs/feature/implementation-execution-skill/`
- Branch: `codex/implementation-execution-skill`
- Design: `design.md`
- Technical review: `technical-review-2026-07-17.md` (`Pass`)
- Current phase: F3

## Scope

### In Scope

- Add the repository `implementation-execution` skill.
- Add UI metadata generated through the official skill tooling.
- Add a progressive-disclosure reference containing reusable rejection
  patterns derived from the Accessibility Selector Engine review chain.
- Integrate the skill into `feature-lifecycle` F4.
- Update repository workflow documentation.
- Validate the skill and record realistic scenario dry runs.
- Add lifecycle, changelog, and merge-readiness records.

### Out Of Scope

- Package source, public Python APIs, protocol schemas, examples, dependencies,
  package versions, releases, or live desktop operations.
- Formal PR approval or automatic merge.
- A machine-readable implementation evidence schema in version one.

## Implementation Slices

| Slice | Files/modules | Behavior | Tests | Docs | Rollback |
| --- | --- | --- | --- | --- | --- |
| S1: Core skill | `.agents/skills/implementation-execution/SKILL.md`, `agents/openai.yaml`, `references/rejection-patterns.md`, `implementation-notes.md` | Freeze implementation context, maintain risk/slice ledgers, execute mandatory gates, stop unsafe work, and produce a review handoff. | Official `quick_validate.py`; frontmatter/UI metadata inspection; line/reference inventory; scenario walkthroughs for contract propagation and mutation recovery. | Skill body, rejection reference, implementation notes. | Revert S1 commit; no runtime migration. |
| S2: Lifecycle integration | `.agents/skills/feature-lifecycle/SKILL.md`, `docs/README.md`, `implementation-notes.md` | F4 invokes the new skill for non-trivial/risky implementation while lifecycle retains phase ownership. | Trigger wording inspection; no circular ownership; scenario walkthroughs for selector collections and review remediation; `git diff --check`. | Repository workflow docs and implementation notes. | Revert S2 commit; feature lifecycle returns to previous F4 wording. |
| S3: Verification | `verification.md` | Record exact commands, outputs, dry-run results, skipped checks, and branch isolation. | Repeat official validator; release preflight when feasible; clean-tree checks. | Verification record. | Documentation-only revert. |
| S4: Review readiness | `CHANGELOG.md`, `merge-readiness.md`, `pr-description.md` | Publish internal release record and review handoff without claiming self-approval. | Full changed-file reconciliation, phase commit audit, `git diff --check`, remote branch parity. | Changelog and F6 artifacts. | Revert F6 documentation commit. |

## S1 Core Skill Contract

### Frontmatter Trigger

The description must trigger for implementation of approved plans, review
remediation, public contract/config/failure changes, risky desktop mutation,
retry/fallback/cache/pagination/privacy work, and review-ready implementation
handoff. It must not claim design or PR approval ownership.

### Core Workflow

1. Freeze inputs and branch.
2. Produce the implementation gate report.
3. Build anticipated changed-file and risk-surface coverage.
4. Define bounded vertical slices and counterexamples.
5. Implement code, tests, docs, diagnostics, and compatibility together.
6. Verify and commit/push each slice.
7. Reconcile full diff and run a fresh forward-risk pass.
8. Run exact-head broad checks and produce `ready_for_review` handoff.

### Required Specialized Gates

- Contract-execution parity.
- Producer-to-consumer public contract propagation.
- Mutation no-replay and operation count/order.
- Current target identity and stale-reference preconditions.
- Query bounds, truncation, cache, pagination, timeout, and concurrency.
- Privacy-safe output, logging, debug, and release artifacts.
- Atomic configuration and clean-environment compatibility.
- Exact-head evidence and complete changed-path classification.

## S2 Lifecycle Integration Contract

- `feature-lifecycle` remains the phase orchestrator.
- F4 uses `implementation-execution` for non-trivial, risky, cross-package,
  public-contract, desktop-automation, or review-remediation work.
- Small changes may scale the ledger down, but cannot skip scope, tests,
  documentation, or exact-head evidence.
- A blocked implementation returns to F1-F3 with a documented missing
  decision; it does not silently modify the approved plan.
- `ready_for_review` is a handoff state, not `APPROVE`.

## Rejection Pattern Reference Structure

Group prior findings by reusable root cause:

1. incomplete behavior-path and contract propagation;
2. unsafe mutation recovery and timeout/retry semantics;
3. target identity, focus, coordinates, and stale references;
4. query bounds, truncation, cache, semantic pagination, and performance;
5. accepted configuration/runtime execution mismatch and atomic activation;
6. privacy leakage through evidence, logs, and release proof;
7. structured failure routing and public failure registries;
8. dependency floors, clean installs, wheel/CI/release environments;
9. tests that pass vacuously or bypass production producers;
10. exact-head and immutable review evidence integrity;
11. remediation-induced risk not covered by old finding tests.

Each pattern must define signals, implementation response, required evidence,
and representative historical finding IDs.

## Verification Matrix

| Scenario | Expected skill behavior | Historical classes covered |
| --- | --- | --- |
| Add a worker failure kind | Trace producer, normalizer, registry/export, serialization, docs, consumer, wheel, old dependency; block unknown stages. | `PRR-005`, `PRR-010`, `PRR-011`, `PRR-025`, `PRR-036` |
| Add fallback after an Accessibility action | Define pre/post-dispatch, malformed, contradictory, unsupported, timeout, and unknown-result cases; assert one action and zero/one permitted fallback in order. | `PRR-018`-`PRR-022`, `PRR-026` |
| Implement selector collection paging | Reject unsupported profile semantics, fail closed on decision truncation, count semantic items, bound batch depth/limit, validate stale cache, inject privacy canaries. | `PRR-004`, `PRR-006`-`PRR-009`, `PRR-028`, `PRR-029`, `PRR-031`, `PRR-033`, `PRR-034` |
| Remediate a failed review | Preserve finding intent, inspect induced risk across all changed files, rerun exact-head tests, and hand off without self-approval. | `PRR-023`, `PRR-027`, repeated reopened findings |

## Verification Commands

```bash
python /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/implementation-execution
git diff --check
git status --short --branch
python scripts/release_preflight.py
```

Additional deterministic inspection:

- verify `SKILL.md` frontmatter contains only `name` and `description`;
- verify the skill folder contains no README or unused placeholder files;
- verify `SKILL.md` is below 500 lines;
- verify all links from `SKILL.md` resolve one level deep;
- compare `agents/openai.yaml` with the final skill purpose;
- walk each scenario using raw requirements and record which gate blocks or
  permits implementation.

## Documentation Updates

- `implementation-notes.md`: one section per implementation slice.
- `verification.md`: exact validation and dry-run evidence.
- `docs/README.md`: repository feature workflow invokes the implementation
  skill during F4.
- `CHANGELOG.md`: `Unreleased / Internal` entry.
- `merge-readiness.md` and `pr-description.md`: review handoff.

## Rollout And Rollback

- Rollout: additive repository skill and explicit lifecycle reference.
- Rollback: revert S2 then S1; no package or runtime state needs migration.
- Compatibility: existing skills remain valid; the new skill narrows F4
  implementation behavior without changing their public metadata.

## Open Decisions

None. A structured implementation-audit schema is deferred until real usage
shows stable fields and a deterministic validator would add value.
