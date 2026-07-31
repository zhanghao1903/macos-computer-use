---
name: technical-plan-write
description: Draft or complete technical plans before implementation. Use when a user asks Codex to write, create, draft, fill in, complete, refine, or update a technical design, detailed implementation plan, ADR, feature design, architecture proposal, API/data-model proposal, migration plan, or design document. Produces or updates per-feature requirements, design, and implementation-plan documents with data structures, changed fields, data flow, object lifecycle, diagrams, risks, tests, rollout, and a writer-scoped git commit when safe. Does not approve or reject the plan.
---

# Technical Plan Write

Use this skill as the plan author's workflow for turning requirements and
repository context into an implementation-ready technical plan. The goal is to
make the plan clear enough that a developer can implement it and a reviewer can
judge it without hidden context.

This skill writes and improves plans. It does not approve, reject, or produce a
pass/fail decision. Use `technical-plan-review` after writing when the user asks
for review or when the lifecycle requires architect review.

## Required Behavior

- Create or update a per-feature directory, preferably
  `docs/feature/<feature-slug>/`.
- Prefer separate files over one large document:
  - `requirements.md` for background, goals, scenarios, non-goals, assumptions,
    and open questions.
  - `design.md` for the technical design and consumer contract.
  - `implementation-plan.md` for implementation slices, files/modules, tests,
    docs, rollout, rollback, and proof.
- Preserve existing plan content unless it is wrong or superseded; update it
  deliberately instead of rewriting from scratch without need.
- Distinguish implemented behavior from proposed behavior.
- Mark assumptions and open decisions explicitly. Do not bury unresolved design
  choices in prose.
- Do not create a `Pass` or `Fail` decision. Leave approval to
  `technical-plan-review`.
- After writing or materially updating the plan, create one git commit
  containing only writer-scoped changes unless the user explicitly says not to
  commit or the repository cannot be committed safely.

## Workflow

1. Identify the feature, feature slug, branch, requested artifact, and affected
   package/module boundaries.
2. Read repository context before writing: existing feature docs, architecture
   docs, API docs, tests, examples, and current implementation surfaces.
3. Create or update the feature directory.
4. Write or update requirements first when the problem, goals, non-goals, or
   scenarios are unclear.
5. Write or update `design.md` using the design contract below.
6. Write or update `implementation-plan.md` when developers need concrete
   execution slices before coding.
7. Add a changelog entry when repository policy requires one for workflow/docs
   changes.
8. Run lightweight validation such as `git diff --check` when feasible.
9. Commit the writer-scoped changes according to the commit rules below.

Ask for user input only when a major product, API, safety, compatibility,
security, or release decision cannot be safely inferred. Otherwise make
conservative assumptions and record them.

## Design Contract

A strong technical plan should include these sections where applicable:

- Background and problem statement.
- Goals, non-goals, and user/developer scenarios.
- Current behavior and desired behavior.
- Affected packages, modules, ownership boundaries, and stable docs.
- Public API, protocol, command, observation, config, or schema impact.
- Data structures with a field matrix:
  - object/schema name;
  - field name;
  - new or changed;
  - type;
  - required/optional;
  - default;
  - owner;
  - validation;
  - compatibility or migration note.
- Data flow with a Mermaid flowchart, sequence diagram, or state diagram.
- Core object lifecycle:
  - creation;
  - state transitions;
  - persistence;
  - update rules;
  - ownership;
  - expiration/deletion;
  - observable states.
- Failure modes, failure kinds, caller recovery, retries, timeouts, and
  idempotency.
- Safety, privacy, permissions, authorization, confirmation, and audit
  boundaries.
- Performance, concurrency, ordering, capacity, and consistency assumptions.
- Observability: logs, metrics, traces, debug artifacts, diagnostics, and proof.
- Migration, rollout, rollback, downgrade, feature flags, and compatibility.
- Test strategy: unit, integration, contract, migration, smoke, manual proof,
  and skipped checks.
- Implementation plan with files/modules, slices, dependencies, docs updates,
  and verification commands.
- Open questions with owners and decision timing.

If the feature has no new core object, say that explicitly. If no public
contract changes, say that explicitly.

## Required Diagrams

Use Mermaid diagrams in Markdown when the plan describes behavior, data flow, or
state:

- Use `flowchart` for data movement, component boundaries, or processing paths.
- Use `sequenceDiagram` for cross-package, helper, service, API, or user
  interaction flows.
- Use a state diagram or table for lifecycle-heavy objects.

Do not let diagrams replace field definitions or lifecycle text. Diagrams should
make the plan easier to review, not hide decisions.

## Writing Standards

- Be concrete about package boundaries. For this repository, keep generic macOS
  capability in `computer-use-macos`, protocol contracts in
  `app-control-protocol`, and app-specific semantics in adapter packages such as
  `wechat-desktop-tool`.
- Prefer additive contracts. If a breaking change is proposed, call it out and
  include migration notes.
- Do not invent API examples that conflict with implemented package behavior.
  Mark speculative APIs as proposed.
- Do not expose raw macOS Accessibility data as the application developer
  contract when normalized semantic models are expected.
- Do not hide risky desktop actions behind convenience APIs without explicit
  confirmation, risk, and audit boundaries.
- Keep plan text scoped to the feature. Put stable long-lived architecture in
  `docs/architecture/` only after the feature stabilizes.

## Implementation Plan Template

Use or adapt this structure for `implementation-plan.md`:

```markdown
# Implementation Plan: <feature>

- Feature directory:
- Branch:
- Design document:
- Current phase:

## Scope

- In scope:
- Out of scope:

## Implementation Slices

| Slice | Files/modules | Behavior | Tests | Docs | Rollback |
| --- | --- | --- | --- | --- | --- |

## Package Boundaries

- `app-control-protocol`:
- `computer-use-macos`:
- `wechat-desktop-tool`:
- Other:

## Verification

- Automated checks:
- Fixtures or examples:
- Manual smoke:
- Checks intentionally deferred:

## Rollout And Rollback

- Rollout:
- Rollback:
- Compatibility:

## Open Decisions

| Decision | Owner | Needed by | Default assumption |
| --- | --- | --- | --- |
```

## Writer Commit Rules

At the end of a completed write/update pass, make one git commit for the plan
writing work.

- Stage only writer-scoped files: the feature directory, requirements/design/
  implementation-plan files, directly related docs index updates, and required
  changelog entry.
- Do not stage unrelated dirty files, generated smoke outputs, local proof
  files, tokens, build artifacts, wheel/sdist directories, or lock files unless
  the user explicitly made them part of the plan artifact.
- If unrelated dirty files exist, leave them uncommitted and mention them only
  when relevant.
- If a file needed for the writer commit already contains unrelated user changes
  that cannot be safely separated, stop before committing and report the
  conflict.
- Run `git diff --check` when feasible before committing.
- Use a concise commit message such as
  `docs: write <feature-slug> technical plan`.
- Do not push unless the user or a lifecycle skill explicitly asks for push.
- If a commit cannot be created because the repository is not a git checkout,
  git identity is missing, validation failed, or the worktree cannot be safely
  isolated, leave the files uncommitted and report the exact reason.

## Final Response Format

After writing or updating the plan, respond with:

- Feature directory: path
- Documents written: paths
- Writer commit: commit id, or reason no commit was created
- Open decisions: shortest useful list
- Recommended next step: usually `technical-plan-review` for non-trivial plans
