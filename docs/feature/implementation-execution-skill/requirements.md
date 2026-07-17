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
