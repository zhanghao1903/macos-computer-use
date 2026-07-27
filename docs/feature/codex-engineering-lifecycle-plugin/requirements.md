# Codex Engineering Lifecycle Plugin

## Status

- Feature: `codex-engineering-lifecycle`
- Lifecycle phase: F1 — requirements confirmed
- Branch: `codex/engineering-lifecycle-plugin`
- Base: `origin/main` at `1935b33`
- Date: 2026-07-27

## F0 intake and repository hygiene

The feature adds a new, heavier Codex workflow plugin alongside the existing
lightweight lifecycle work. It packages the repository's engineering workflow
skills and coordinates three durable Codex tasks:

1. Requirements;
2. Main Work;
3. Review.

The feature is being developed in an isolated Git worktree because the user's
original worktree contains unrelated, untracked WeChat smoke outputs, build
artifacts, and a lock file. Those files are outside this feature and must remain
untouched.

The implementation scope is limited to:

- `plugins/codex-engineering-lifecycle/`;
- `.agents/plugins/marketplace.json`;
- this feature document set;
- focused plugin and workflow tests;
- the repository changelog and PR/release records.

The change does not alter the public Python APIs, package dependencies, macOS
automation behavior, protocol package, or package release versions.

## Phase plan

- F1: confirm workflow requirements, scenarios, non-goals, and safety gates.
- F2: define the three-task state machine, contracts, and role boundaries.
- F3: define files, tests, documentation, recovery, and rollout.
- F4: implement the plugin, role skills, Init, schemas, and deterministic state
  helper.
- F5: validate skills, plugin structure, state transitions, documentation, and
  installation flow.
- F6: perform independent review, remediation, changelog, and merge readiness.
- F7: prepare an explicit release plan and proof.
- F8: record merge/release/closure traceability when external actions complete.

## Confirmed user problem

The repository has five strong but independent engineering skills:

- `feature-lifecycle`;
- `product-workflow-gate`;
- `technical-plan-write`;
- `technical-plan-review`;
- `pr-review`.

They do not currently provide an installable, initialized multi-task workflow
that automatically hands a confirmed feature through requirements, technical
design, plan review, Goal-mode implementation, code review, merge, release, and
closure.

The requested plugin must provide that workflow without replacing or changing
the existing source skills.

## Required user scenarios

### S1 — initialize once

From a trusted GitHub checkout, a user invokes the plugin's Init skill. Init
must validate the repository and required Codex/GitHub/task capabilities, then
create or bind exactly three project-scoped, pinned Codex tasks:

1. `Requirements · <repository>`;
2. `Engineering Main · <repository>`;
3. `Engineering Review · <repository>`.

Repeated Init must reuse a healthy workflow and repair only safely recoverable
missing bindings. It must not silently overwrite a conflicting workflow.

### S2 — collect and confirm requirements

The Requirements task turns a natural-language feature request into a tracked
requirements document. It must not design or implement the feature. It may
dispatch work only after the user explicitly confirms an immutable requirements
snapshot.

### S3 — write and review the technical plan

Main Work accepts a validated confirmed requirements handoff, uses
`technical-plan-write`, and commits and pushes the requirements, design, and
implementation plan before dispatching an immutable technical-plan review
request.

Engineering Review uses `technical-plan-review` and writes a persistent review
report. A rejected plan returns actionable findings to Main Work. Main Work
must revise, commit, push, and request re-review. Development cannot start
until Review approves the exact plan snapshot.

### S4 — notify and implement with Goal mode

Init must disclose that approved features use Goal mode and obtain explicit
workflow-level authorization for that behavior. After exact-snapshot technical
approval, Main Work notifies the user and immediately creates a Goal for the
approved implementation. Goal completion must mean implementation,
verification, documentation, release record, and PR preparation are complete;
nearing a budget or ending a turn is not completion.

### S5 — independently review the code

After Main Work opens or updates the PR, it dispatches an immutable exact-head
review request. Engineering Review uses `pr-review`, writes Markdown and JSON
review artifacts, and returns either approval or actionable findings.

Main Work owns finding remediation and re-review dispatch. It may not approve
or merge its own changes. Engineering Review may not edit the feature branch.

### S6 — merge safely

Engineering Review may merge only the exact approved PR head when the PR is not
draft, all required checks pass, no blocking finding remains, and repository
policy permits the configured merge method. Administrative bypass is forbidden.
The merge result must be returned to Main Work with immutable evidence.

### S7 — publish a release

After merge, Main Work prepares release notes and publishing proof using
`feature-lifecycle` and `product-workflow-gate`. The default policy is manual:
the exact version, tag, target, artifacts, and publishing action require
explicit user authorization. Init must not enable silent release publishing.

### S8 — close the feature

The feature may close only after release publication is proven and a
post-release summary records the requirements snapshot, plan approval, PR,
merge commit, tag/release, scenarios solved, and follow-ups. Failed or deferred
release work leaves the feature open with a recoverable state.

## Required role composition

| Task | Bundled workflow responsibilities |
| --- | --- |
| Requirements | Requirements intake, confirmation, immutable handoff |
| Engineering Main | `feature-lifecycle`, `product-workflow-gate`, `technical-plan-write`, plan remediation, Goal-mode implementation, PR preparation, release, closure |
| Engineering Review | `technical-plan-review`, `pr-review`, exact-head merge decision |

All five repository source skills must be packaged in the new plugin as
independent reusable skills in addition to the three role wrappers and Init.

## Required durable contracts

The plugin must validate versioned JSON contracts for:

- confirmed requirements handoff;
- technical-plan review request and result;
- code-review request and result;
- merge result;
- release authorization and release result;
- feature closure record.

Every authorizing message must bind to the canonical GitHub repository, feature
identifier, task roles, exact commit or PR head, document path, content digest,
schema version, and UTC timestamp. Unknown fields and malformed or stale
authority must fail closed.

Workflow configuration and state must be stored outside the target repository
under the user's Codex data directory. It must not store credentials, raw task
transcripts, source diffs, or unredacted user content.

## Failure and recovery requirements

- Dispatches must use deterministic IDs so retries cannot duplicate feature
  starts, review cycles, merges, releases, or closure.
- Invalid, stale, mismatched, or unconfirmed handoffs must not advance state.
- A missing task-management, Goal, GitHub, or repository capability must stop
  Init with a clear recovery action.
- Review rejection and check failure must return control to the owning role
  without destroying prior evidence.
- Restarting a task must resume from durable state rather than infer authority
  from conversation history.
- Manual edits to task IDs, schema versions, or workflow state are unsupported.

## Safety and authorization boundaries

- Requirements never writes a technical plan or implementation.
- Main Work never approves its own plan or code.
- Review never edits the feature branch.
- Plan approval is valid only for the reviewed immutable snapshot.
- Code approval is valid only for the reviewed exact PR head.
- Merge cannot use an administrative bypass.
- Goal mode is enabled only through explicit Init authorization.
- Release publication always requires an exact, explicit authorization.
- Feature closure requires verified release evidence.

## Compatibility and distribution

- Codex-only; cross-application or Claude routing is out of scope.
- GitHub repositories only; other forges are out of scope.
- The new plugin coexists with the lightweight
  `codex-feature-lifecycle` plugin and uses a distinct plugin name, skill
  namespace, state root, and task titles.
- The plugin is repository-distributed through the repo-local marketplace and
  must include install, update, uninstall, initialization, recovery, and data
  cleanup documentation.
- Version `0.1.0` is the first release of the new plugin.

## Acceptance criteria

1. Plugin and every bundled skill pass the canonical validators.
2. Init creates or reuses exactly three role-correct tasks and persists their
   bindings.
3. Invalid or out-of-order contracts fail closed without advancing state.
4. Plan rejection loops back to Main Work; exact-snapshot approval starts the
   authorized Goal flow.
5. Goal completion dispatches an exact-head PR review; findings loop through
   remediation and re-review.
6. Only Review can merge, only at the approved head and with passing checks.
7. Release and closure cannot occur without exact authorization and proof.
8. Positive end-to-end and negative safety scenarios are covered by automated
   tests and documented manual task-dispatch proof.
9. Installation, update, uninstall, Init, recovery, and local-data behavior are
   documented for another user.

## Non-goals

- Cross-application task routing.
- Non-GitHub repository providers.
- Automatic administrative merge or check bypass.
- Silent or unattended release publication.
- Changes to the package suite's public APIs or versions.
- Migrating an existing lightweight workflow into the new plugin.
