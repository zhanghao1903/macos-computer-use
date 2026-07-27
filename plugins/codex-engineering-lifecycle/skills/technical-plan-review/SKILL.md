---
name: technical-plan-review
description: Architect-level technical plan review. Use when a user asks Codex to review, inspect, approve, reject, or give pass/fail feedback on a technical design, detailed implementation plan, ADR, feature design, architecture proposal, API/data-model proposal, migration plan, or design document before development. Produces a persistent review document with qualified areas, disqualified gaps, required fixes, recommendations, a pass/fail decision, and a review-scoped git commit when safe.
---

# Technical Plan Review

Use this skill to review a technical plan from an architect's perspective:
Would you feel comfortable handing this design to developers and expecting them
to understand the requirement, solution, data model, data flow, implementation
path, risks, and verification work without hidden context?

This is a design-readiness review, not a code review. Judge whether the plan is
clear, complete, consistent, and implementable before development starts.

## Required Behavior

- Always create or update a persistent review document for each review.
- Match the user's language in the review document unless the repository has an
  established language for the target docs.
- Make a clear final decision: `Pass` or `Fail`.
- Fail the plan when mandatory design information is missing, even if the
  reviewer can infer a plausible answer.
- Do not silently fill missing design content into the plan and then approve it.
  Put inferred or proposed content under recommendations.
- When reviewing within a feature lifecycle, treat a failed review as a blocker
  before implementation unless the user explicitly overrides it.
- After the review report and directly related docs are written, create one git
  commit containing only review-scoped changes unless the user explicitly says
  not to commit or the repository cannot be committed safely.

## Review Document Location

Prefer the narrowest useful location:

- If reviewing an existing repository feature design inside
  `docs/feature/<feature-slug>/`, write the review in the same feature
  directory as `technical-review-YYYY-MM-DD.md`.
- If the feature has no directory yet, create
  `docs/feature/<feature-slug>/` and write
  `docs/feature/<feature-slug>/technical-review-YYYY-MM-DD.md`.
- If reviewing a legacy single-file design under `docs/feature/`, create a new
  feature directory derived from the plan slug and write the review there. Do
  not create new global review files under `docs/feature/reviews/`.
- If reviewing a pasted plan with no source file, create a feature directory
  using a descriptive slug derived from the feature or plan title, then write
  the review document inside it.
- Do not overwrite earlier review reports. If a same-day report exists, append a
  short suffix such as `-2`.

The final response must include the feature directory, review document path, and
final decision.

## Review Workflow

1. Identify the reviewed artifact(s): pasted content, docs, ADR, PRD, issue,
   implementation plan, diagrams, API schemas, or linked files.
2. Read surrounding context needed to judge the design: related feature docs,
   architecture docs, API docs, schemas, tests, and previous review reports.
3. Determine the intended developer handoff: who will implement it, what they
   need to change, which packages/modules/components are touched, and what
   success looks like.
4. Evaluate mandatory criteria first. A missing mandatory item usually makes the
   plan fail.
5. Evaluate supplemental architecture criteria based on risk and blast radius.
6. Write the persistent review report with evidence, gaps, fixes, and a
   pass/fail decision.
7. If the plan fails, state the smallest set of changes needed before it should
   be reviewed again.
8. Commit the review-scoped changes according to the commit rules below.

## Review Commit Rules

At the end of each completed review, make one git commit for the review work.

- Stage only files that belong to the review scope: the feature directory,
  review report, migrated design document, directly related docs index updates,
  and required changelog entry.
- Do not stage unrelated dirty files, generated smoke outputs, local proof
  files, tokens, build artifacts, wheel/sdist directories, or lock files unless
  they are explicitly part of the reviewed artifact.
- If unrelated dirty files exist, leave them uncommitted and mention them in the
  final response only when relevant.
- If a file needed for the review commit already contains unrelated user
  changes that cannot be safely separated, stop before committing and report the
  conflict.
- Run `git diff --check` when feasible before committing.
- Use a concise commit message such as
  `docs: review <feature-slug> technical plan`.
- Do not push unless the user or a lifecycle skill explicitly asks for push.
- If a commit cannot be created because the repository is not a git checkout,
  git identity is missing, validation failed, or the worktree cannot be safely
  isolated, leave the files uncommitted and report the exact reason.

## Mandatory Criteria

A plan must satisfy these criteria to pass:

1. Requirement background and goals
   - Explain the user/business/developer problem.
   - State the concrete goals and expected outcomes.
   - Identify non-goals or out-of-scope behavior when relevant.

2. Data structure clarity
   - Define all relevant objects, tables, schemas, protocol payloads, config
     fields, request/response shapes, or persisted state.
   - Highlight every new field and changed field.
   - For each new or changed field, define type, required/optional status,
     default, owner, validation, compatibility, and migration impact where
     applicable.

3. Data flow clarity
   - Explain where data originates, how it moves, how it is transformed, where
     it is stored, and which component consumes it.
   - Identify cross-boundary calls, async behavior, retries, idempotency, and
     failure handling where applicable.

4. Core object lifecycle
   - For each new core object, define creation, state transitions, persistence,
     update rules, ownership, deletion/expiration, and observable states.
   - If no new core object exists, the plan must explicitly say so.

5. Flow diagram
   - Include a flowchart, sequence diagram, state diagram, or equivalent diagram
     that makes the execution/data path clear.
   - Mermaid diagrams are preferred for repository Markdown docs.
   - If the source plan lacks a diagram, mark this as a gap. A reviewer-proposed
     diagram can be included as a recommendation, but it does not make the
     original plan complete.

6. Developer handoff readiness
   - Define affected modules/files/components or package boundaries.
   - Describe the implementation path in enough detail for a developer to start
     without rediscovering the architecture.
   - Define acceptance criteria and verification strategy.

## Supplemental Architecture Criteria

Apply these according to risk. Missing high-risk items can make the plan fail:

- Public API, protocol, schema, and compatibility impact.
- Migration, backfill, rollback, and downgrade behavior.
- Error states, failure kinds, caller recovery, retries, and timeout behavior.
- Security, permissions, privacy, safety, audit, and authorization boundaries.
- Performance, capacity, concurrency, ordering, and consistency assumptions.
- Observability: logs, metrics, traces, debug artifacts, and operational proof.
- Dependency changes, external service assumptions, and environment constraints.
- Test strategy: unit, integration, contract, migration, smoke, and manual proof.
- Rollout strategy, feature flags, staged release, and kill switch where needed.
- Ownership and maintenance: responsible package/team/module and long-term docs.

## Severity And Decision Rules

Use these severities:

- `Blocker`: Developers cannot implement safely or correctly; mandatory design
  criteria are missing; data structures or data flow are unclear; public
  contracts are ambiguous; safety/compatibility risk is unresolved.
- `Major`: The plan is implementable only with significant assumptions, likely
  rework, or hidden decisions.
- `Minor`: The plan is mostly clear but needs localized clarification,
  examples, naming cleanup, or stronger verification detail.

Decision:

- `Fail` if there is any blocker, any missing mandatory criterion, or the
  architect would not confidently hand the plan to developers.
- `Pass` only when mandatory criteria are complete and remaining issues are
  minor enough to track during implementation.

Avoid vague conclusions such as "looks good overall" without an explicit pass
or fail decision.

## Review Report Template

Use this structure for the persistent review document:

```markdown
# Technical Plan Review: <plan title>

- Review date: <YYYY-MM-DD>
- Reviewed artifact(s): <files, links, or pasted-plan summary>
- Reviewer stance: Architect handoff readiness
- Final decision: <Pass|Fail>
- Decision summary: <1-3 sentences>

## Handoff Judgment

<Would an architect feel comfortable giving this plan to developers? Why or why not?>

## Mandatory Criteria

| Criterion | Status | Evidence | Gap / required fix |
| --- | --- | --- | --- |
| Requirement background and goals | <Pass|Fail> |  |  |
| Data structure clarity | <Pass|Fail> |  |  |
| New/changed fields highlighted | <Pass|Fail> |  |  |
| Data flow clarity | <Pass|Fail> |  |  |
| Core object lifecycle | <Pass|Fail|N/A> |  |  |
| Flow diagram | <Pass|Fail> |  |  |
| Developer handoff readiness | <Pass|Fail> |  |  |

## Qualified Areas

- <What is clear, complete, or well constrained.>

## Disqualified Gaps And Risks

| Severity | Issue | Evidence | Impact | Required fix | Blocks pass |
| --- | --- | --- | --- | --- | --- |
| <Blocker|Major|Minor> |  |  |  |  | <yes|no> |

## Data Structure Review

| Object / schema | Field | New or changed | Type | Required | Default | Validation | Compatibility / migration note |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Data Flow And Lifecycle Review

- Data flow:
- Core object lifecycle:
- Missing transitions or ownership rules:

## Flow Diagram Review

- Diagram present: <yes|no>
- Diagram adequacy:
- Recommended diagram changes:

## Implementation Readiness

- Clear implementation path:
- Affected modules/components:
- Open decisions developers would still need to make:

## Verification Readiness

- Test strategy:
- Missing proof:
- Manual or smoke validation needed:

## Modification Recommendations

1. <Highest priority required fix.>
2. <Next recommendation.>

## Re-review Requirements

<If failed, list the minimum changes needed before the plan should be reviewed again.>
```

Remove empty rows or sections that do not apply, but keep the mandatory
criteria table.

## Final Response Format

After writing the review document, respond with:

- Review decision: `Pass` or `Fail`
- Feature directory: path
- Review document: path
- Review commit: commit id, or reason no commit was created
- Blocking gaps: count and short summary
- Key recommendations: shortest useful list
