# Implementation Execution Skill Requirements

## F0 Intake And Repository Hygiene

- Feature: `implementation-execution` repository skill
- Branch: `codex/implementation-execution-skill`
- Base: `origin/main` at `fed652343ec73734247955d44dc8e60293a7b373`
- Worktree: isolated from the dirty Accessibility Selector Engine worktree
- Affected surface: repository Agent workflow only
- Package API/protocol impact: none
- Feature directory: `docs/feature/implementation-execution-skill/`

### Request

Create an implementation-stage skill that turns approved requirements and
technical plans into review-ready code with fewer avoidable review rejections.
Base its controls on the repeated findings from the Accessibility Selector
Engine review history.

### Source Evidence

The source review chain contains repeated failures in these areas:

- mutation replay after unknown or contradictory outcomes;
- background-app and unverified-coordinate targeting;
- raw/private Accessibility data escaping through evidence and logs;
- truncated or stale query data being used for decisions;
- parser/config contracts accepting semantics the runtime ignores;
- pagination, limits, cache, and timeout behavior differing across layers;
- non-atomic configuration activation;
- public failure values missing producer-to-consumer propagation;
- clean-environment dependency, wheel, and CI gaps;
- tests that pass without proving the critical behavior;
- review and lifecycle evidence bound to the wrong commit.

### Hygiene Decision

Implement this as a new repository skill under `.agents/skills/`. Do not modify
the existing dirty primary worktree, package code, protocol schemas, examples,
or generated smoke output. Use phase-scoped commits and push each completed
phase before continuing.

### Initial Non-Goals

- Replace `feature-lifecycle`, `technical-plan-write`, `technical-plan-review`,
  or `pr-review`.
- Guarantee that a PR cannot receive new findings.
- Run live desktop mutations, publish packages, merge a PR, or release code.
- Encode package-specific implementation details directly in the core skill.

### F0 Exit Evidence

- Dedicated branch and clean worktree exist.
- Feature scope and source review evidence are recorded.
- No package or public API change is proposed.

## F1 Confirmed Requirements

### Primary User

The skill is for a coding agent implementing an approved feature, remediation,
or cross-package change before formal PR review. The human consumer is the
maintainer who needs implementation commits and evidence that are easier to
review and less likely to miss known risk classes.

### Trigger Scenarios

Use the skill when a request asks to:

1. implement an approved requirements/design/implementation plan;
2. fix one or more review findings and prepare a re-reviewable head;
3. change public APIs, protocols, failure kinds, configuration, packaging, or
   cross-package behavior;
4. implement desktop automation, retries, fallbacks, caching, pagination,
   privacy-sensitive observations, or other high-risk state transitions;
5. prepare implementation evidence before asking for PR review.

Do not trigger it for design-only discussion, read-only code explanation, or a
formal PR decision. Those belong to technical planning or `pr-review`.

### Required Outcomes

The skill must make the implementing agent:

- freeze the approved requirement, design, plan, branch, and base SHA;
- convert the plan into small vertical implementation slices;
- build a changed-surface and risk ledger before editing code;
- define positive, negative, malformed, contradictory, boundary, and
  compatibility cases before implementation when the risk warrants them;
- trace public contract changes from producer through export/registry,
  serialization/docs, consumer, tests, packaging, and release checks;
- prove mutation/retry/fallback behavior with operation count and order;
- reject or explicitly bound semantics the implementation cannot execute;
- keep privacy, target identity, truncation, cache, pagination, timeout, and
  configuration atomicity as first-class gates;
- update the feature implementation record during each slice;
- run exact-head verification in an isolated or demonstrably clean tree;
- perform a second forward-risk pass over the complete diff before handoff;
- classify every changed file and disclose every skipped check or limitation;
- commit and push each completed implementation slice with its documentation.

### Acceptance Criteria

1. The skill has a concise `SKILL.md` with a trigger description that covers
   implementation, review-remediation, risky desktop behavior, and public
   contract changes.
2. The skill separates implementation execution from lifecycle orchestration,
   technical design, formal review, merge, and release decisions.
3. The skill includes reusable rejection-pattern guidance derived from the
   review chain without hard-coding WeChat-only behavior into every task.
4. The workflow contains explicit stop conditions for unclear requirements,
   missing design decisions, unsafe mutation semantics, unclassified diff
   paths, failing required checks, and non-exact-head evidence.
5. The workflow requires a review-ready handoff record containing exact SHAs,
   changed paths, risk surfaces, contract propagation, tests, limitations, and
   remaining actions.
6. The official skill validator passes and UI metadata matches the skill.
7. At least three realistic dry-run scenarios demonstrate that the skill would
   catch prior rejection classes before formal review.

### Safety And Authorization

- Planning and deterministic tests do not authorize live side effects.
- A skill invocation must preserve the caller's existing confirmation,
  allowlist, privacy, and release boundaries.
- Unknown mutation outcome means no replay unless a reviewed contract proves
  both no dispatch or a definite no-effect result.
- Raw private observations are evidence only when explicitly authorized and
  must not enter normal logs, reports, release assets, or public artifacts.

### Recovery Behavior

- If requirements or design are ambiguous on a correctness, compatibility,
  privacy, security, or mutation boundary, stop implementation and return to
  the owning lifecycle phase.
- If a slice exposes a new contract or risk not covered by the plan, update the
  risk ledger and implementation plan before continuing.
- If required validation fails, keep the slice incomplete; do not document it
  as verified or request review.
- If the head changes after validation, rerun every approval-critical check on
  the new exact head.

### Release Impact

This is an internal repository workflow feature. Add an `Internal` changelog
entry. It does not change package versions or require package publication.
