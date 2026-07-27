# Technical Plan Review: Codex Engineering Lifecycle Plugin

- Review date: 2026-07-27
- Reviewed artifacts:
  - `requirements.md` at `5fc521c`
  - `design.md` at `fa5c69b`
  - `implementation-plan.md` at `25f924d`
- Reviewer stance: Architect handoff readiness
- Final decision: **Fail**
- Decision summary: The plan is strong in topology, immutable evidence, and
  role ownership, but three authority/lifecycle gaps would force developers to
  invent behavior during implementation. Goal remediation, source-skill
  invocation policy, and release-target proof must be made deterministic before
  development.

## Handoff judgment

An architect should not hand this plan to implementation yet. The normal happy
path is clear, but the first code-review remediation would encounter an
unrepresentable Goal transition, task-role isolation depends on unmodified
implicit skill behavior, and the release contract cannot prove all authorized
publishing targets succeeded before closure.

## Mandatory criteria

| Criterion | Status | Evidence | Gap / required fix |
| --- | --- | --- | --- |
| Requirement background and goals | Pass | `requirements.md` defines eight scenarios, non-goals, and acceptance criteria | None |
| Data structure clarity | Fail | `design.md` defines config, state, feature, evidence, and contracts | `FeatureRecord.goal` cannot represent remediation Goal runs; release targets are untyped |
| New/changed fields highlighted | Fail | Field matrices cover most objects | Missing `GoalRun` collection and typed release target/result fields |
| Data flow clarity | Fail | Topology and sequence diagrams cover the happy path | Code-review remediation says “resume” without a valid post-completion Goal operation |
| Core object lifecycle | Fail | Feature state machine is present | Completed Goal to remediation Goal creation/update ownership is undefined |
| Flow diagram | Pass | Flowchart, state diagram, and sequence diagrams are present | Update the state/sequence flow after the Goal model changes |
| Developer handoff readiness | Fail | File slices, commands, tests, and rollback are specified | Findings TR-1 through TR-3 require design decisions |

## Qualified areas

- Exactly three task roles and pairwise-distinct task IDs are explicit.
- Requirements, plan, code, merge, release, and closure authority bind to
  immutable artifacts rather than conversation history.
- Review-record branches preserve reviewer independence from the feature
  branch.
- Single-active-Goal queueing correctly recognizes the Main task's concurrency
  limit.
- Persistence, locking, atomic writes, replay handling, origin validation, and
  sanitized error boundaries are implementation-ready.
- The implementation slices, validators, tests, manual proof, and rollback plan
  are appropriately scoped for a plugin-only repository change.

## Disqualified gaps and risks

| ID | Severity | Issue | Evidence | Impact | Required fix | Blocks pass |
| --- | --- | --- | --- | --- | --- | --- |
| TR-1 | Blocker | A completed implementation Goal cannot be resumed for code-review remediation | `FeatureRecord` has singular `goal`; transition is `CODE_CHANGES_REQUESTED -> DEVELOPMENT_ACTIVE`; Main slice says use the same or resumed Goal | Runtime cannot truthfully represent or operate the first remediation cycle because platform Goal state is terminal | Replace singular `goal` with ordered `goalRuns[]`; define `INITIAL_IMPLEMENTATION` and `CODE_REMEDIATION` runs, creation IDs, active-run invariant, terminal handling, and transitions | yes |
| TR-2 | Blocker | Packaged source skills remain implicitly invocable in every role task | Slice 3 requires digest-identical copies, while all five source `agents/openai.yaml` files remain implicitly invocable | Requirements or Main could invoke review/plan behavior outside the intended wrapper; state transitions may still fail closed but repository mutations can occur before rejection | Add a documented metadata overlay that sets `policy.allow_implicit_invocation: false` for the five composition skills; validate all other runtime content against source and require explicit wrapper invocation | yes |
| TR-3 | Blocker | Release targets and proof are not machine-verifiable | `ReleaseAuthorization.targets` is `string[]`; artifact digests are optional; `ReleaseResult` exposes one release URL | A feature could close after only one destination succeeds even when the user authorized GitHub Release plus PyPI, or after evidence cannot be tied to an artifact | Define typed `ReleaseTarget` and per-target `ReleaseTargetResult`, required artifact digests, success/failure conditions, exact target matching, and “all authorized targets succeeded” closure invariant | yes |
| TR-4 | Major | Review-record branch retry/conflict semantics are incomplete | Design defines deterministic branch names and says no force-push, but not behavior when a branch already exists | Delivery retries could duplicate commits or accept a branch created from a different snapshot | Define create-if-absent, verify exact base/report commit on retry, reject conflicts, and persist the report commit before delivery | yes |

## Data structure review

| Object / schema | Field | Status | Required change |
| --- | --- | --- | --- |
| `FeatureRecord` | `goal` | Disqualified | Replace with ordered `goalRuns[]` and active run reference |
| `GoalRun` | all | Missing | Define run ID, purpose, review cycle, objective digest, thread, status, timestamps, and terminal evidence |
| Source-skill metadata | `policy.allow_implicit_invocation` | Missing | Set false in packaged composition copies and document the only permitted parity difference |
| `ReleaseAuthorization` | `targets` | Disqualified | Replace strings with typed exact target descriptors |
| `ReleaseResult` | target evidence | Missing | Add one result per authorized target and require digest-bound success |
| Review dispatch state | report branch retry fields | Partial | Record requested base, branch, report commit, and delivery state |

## Data flow and lifecycle review

- Requirements through plan approval: qualified.
- Plan approval through initial Goal: qualified once Goal authorization is
  present.
- Code-review remediation: disqualified because the existing Goal is already
  complete.
- Release and closure: disqualified because multi-target success is not
  representable.
- Review record delivery: partially qualified; deterministic names are good,
  but retries need an exact existing-branch verification rule.

## Flow diagram review

- Diagram present: yes.
- Diagram adequacy: adequate for the initial happy path.
- Required changes:
  - show a new remediation Goal run after `REQUEST_CHANGES`;
  - show one release result per authorized target;
  - show closure guarded by the conjunction of all target successes.

## Implementation readiness

- Clear implementation path: mostly, but blocked by the four findings.
- Affected modules/components: correctly identified.
- Open decisions developers would still need to make:
  - Goal run identity and terminal semantics;
  - source-skill metadata overlay and parity test rules;
  - supported release target types and evidence;
  - idempotent review-record branch retry behavior.

## Verification readiness

The proposed test matrix is broad enough, but it must add:

- multiple Goal-run lifecycle and remediation tests;
- source-skill parity with an explicit metadata-policy exception;
- mixed GitHub Release and PyPI target result tests;
- partial multi-target release failure and pre-closure rejection;
- existing identical review-record branch retry and conflicting branch
  rejection.

## Modification recommendations

1. Replace the single Goal record with ordered, immutable Goal runs and one
   active-run pointer.
2. Make the five composition skills explicit-only through packaged metadata
   overlays while preserving their SKILL/resources content.
3. Model GitHub Release and PyPI as typed release targets with per-target
   digest-bound results and require all targets to succeed before closure.
4. Specify exact retry behavior for review-record branches and report commits.

## Re-review requirements

Revise `design.md` and `implementation-plan.md` to resolve TR-1 through TR-4,
update diagrams and tests, commit and push the remediation, then review the new
exact plan snapshot. No plugin implementation should begin before a Pass.
