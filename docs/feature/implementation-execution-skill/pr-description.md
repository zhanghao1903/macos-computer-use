# PR: Add Implementation Execution Skill

## Problem

Approved plans were implemented without a dedicated execution gate between
technical design and formal PR review. The Accessibility Selector Engine review
history repeatedly found avoidable cross-layer gaps only after implementation:
mutation replay, wrong targets, truncated decisions, semantic pagination,
configuration/runtime mismatch, privacy leakage, incomplete failure
propagation, clean-package failures, vacuous tests, and wrong-head evidence.

## Solution

Add a repository `implementation-execution` skill that:

- freezes approved inputs, branch, base, head, and authorization boundaries;
- maps anticipated files to behavior/risk surfaces before code;
- implements vertical slices with positive and adversarial cases;
- enforces contract-execution parity and producer-to-wheel propagation;
- applies mutation no-replay, target, bounded-query, cache/pagination, privacy,
  atomic configuration, compatibility, and exact-head gates;
- commits/pushes each verified slice with its implementation record;
- performs a fresh full-diff forward-risk pass;
- produces `ready_for_review` or `blocked`, never self-approval.

Integrate the skill into `feature-lifecycle` F4 while preserving lifecycle phase
ownership. Add a progressive-disclosure reference that generalizes recurring
`PRR-001` through `PRR-036` failure patterns.

## Public API And Compatibility

- No Python package, protocol, schema, config, dependency, CLI, or version
  change.
- Existing repository skills remain compatible.
- The change is additive; rollback is a normal commit revert.

## Verification

- Official skill validation passes for `implementation-execution` and the
  updated `feature-lifecycle`.
- Repository release preflight passes with expected sandbox/external-proof
  warnings only.
- No placeholders or unused resource files.
- Core skill remains below 500 lines.
- Four raw-request walkthroughs verify public failure propagation, mutation
  fallback, selector collection, and review-remediation gates.
- `git diff --check` passes.

## Documentation And Release Record

- Full lifecycle artifacts are under
  `docs/feature/implementation-execution-skill/`.
- `docs/README.md` documents F4 usage.
- `CHANGELOG.md` includes an `Unreleased / Internal` entry.

## Limitations

- Same-agent scenario walkthroughs were used because no fresh-agent execution
  capability was available.
- Formal PR review and exact-head CI are still required.
- The skill reduces foreseeable omissions; it does not guarantee zero future
  findings.

## Review Focus

- Trigger and ownership boundaries.
- Whether the mandatory gates are actionable rather than ceremonial.
- Generalization and non-duplication of rejection patterns.
- F4 lifecycle integration and exact-head handoff semantics.
