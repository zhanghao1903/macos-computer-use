# Codex Feature Lifecycle Plugin

Status: F1 requirements confirmed

## Feature Lifecycle Report

- Feature: Codex Feature Lifecycle plugin
- Feature branch: `codex/codex-feature-lifecycle-plugin`
- Current phase: F1 requirement confirmation
- User problem: a user must manually transfer a completed implementation from
  a main Codex task to a separate review-and-merge task.
- Desired behavior: one explicit initialization command establishes two Codex
  tasks that automatically exchange review requests and results.
- Affected package(s): standalone plugin only; no Python package changes.
- Public surface impact: new plugin skills, local workflow configuration, and
  structured task messages.
- Safety / authorization impact: task creation, background task messaging, and
  optional GitHub pull-request merge.
- Required tests: schema, configuration/state, skill, plugin, marketplace, and
  scenario validation plus non-mutating forward tests.
- Release impact: initial plugin version `0.1.0`; no package version change.
- Blockers / assumptions: Codex Desktop task tools and a usable GitHub surface
  are required for the complete workflow.

## Problem

The repository's feature lifecycle currently depends on a user manually
transferring work from a main implementation task to a separate pull-request
review and merge task. The intended plugin will let Codex carry that workflow
end to end without a manual task-to-task handoff.

## Goals

- Package the workflow as an installable Codex plugin.
- Use dedicated Codex tasks for main work and pull-request review and merge.
- Provide an explicit initialization entry point that creates or binds the
  workflow tasks and stores their local routing configuration.
- Automate structured handoffs, review feedback, re-review, and merge-result
  reporting between those tasks.
- Preserve the existing feature lifecycle requirements for documentation,
  verification, release records, and traceability.

## Users And Scenarios

The primary user is a developer who installs the plugin in Codex Desktop and
wants Codex to carry a GitHub-backed feature from intake through merge without
manually relaying messages between tasks.

### Scenario A: Initialize A Repository

The user explicitly invokes `$codex-workflow-init` in a trusted Git repository.
The skill verifies required capabilities, asks whether approved pull requests
may be merged automatically, creates or binds the main and reviewer tasks,
stores local routing configuration, and proves both tasks are reachable.

### Scenario B: Implement And Dispatch

The user sends a feature request to the main task. The main task completes the
required feature phases, pushes a reviewable branch, opens or updates a pull
request, fixes the reviewed head SHA, and sends one structured review request
to the configured reviewer task.

### Scenario C: Request Changes And Re-Review

The reviewer reports blocking findings to the main task. The main task fixes
them, verifies and pushes a new head, and dispatches a new review request. The
new head invalidates every earlier approval and requires a complete re-review.

### Scenario D: Approve And Merge

The reviewer finds no blockers, verifies the exact reviewed head and required
checks, and merges only when durable merge authorization was recorded during
initialization. It reports the merge result to the main task, which completes
post-merge traceability and any explicitly requested release preparation.

## Functional Requirements

### R1. Supported Surface

- Support Codex Desktop only for version `0.1.0`.
- Require callable project discovery, task creation, task discovery/read,
  background task messaging, task wait, title, and pin capabilities.
- Fail closed with a precise capability report when the host cannot provide the
  required task tools.

### R2. Explicit And Idempotent Initialization

- Expose `$codex-workflow-init` as the single initialization entry point.
- Treat explicit invocation as authorization to create the two workflow tasks,
  but ask separately before recording automatic merge authorization.
- Create one main task and one review-and-merge task for the current repository,
  or bind existing tasks selected by the user.
- Name, pin, bootstrap, and wait for both tasks to report readiness.
- Re-running initialization must reuse a healthy configuration and must not
  create duplicate tasks.
- A partial initialization must be reported as incomplete and must not be
  presented as operational.

### R3. Local Configuration

- Store routing configuration outside the repository under the user's Codex
  state directory, keyed by a deterministic fingerprint of the canonical
  repository root and sanitized origin remote.
- Store schema version, repository identity, project ID, host ID, both task IDs,
  merge policy, creation time, and update time.
- Store workflow dispatch state separately from static configuration.
- Use owner-only file permissions where supported and never store tokens,
  credentials, transcripts, source code, diffs, or review content.
- Validate the configured repository and both task routes before every dispatch.

### R4. Main Task Lifecycle

- The main task owns intake, requirements, design, implementation planning,
  implementation, verification, documentation, pull-request preparation,
  finding remediation, and post-merge traceability.
- Preserve one feature per branch and phase-level documentation, commit, and
  push discipline when the repository requires it.
- Do not dispatch before the branch is pushed, a pull request exists, tests and
  docs are recorded, and the intended head SHA is stable.
- Do not modify the feature branch after dispatch without invalidating the
  pending review and producing a new dispatch.

### R5. Review-And-Merge Task Lifecycle

- Review an immutable base/head snapshot independently from the main task.
- Produce evidence-backed findings with stable IDs, severity, file/line where
  applicable, impact, evidence, and an actionable fix.
- Treat any head change as stale review input and refuse approval or merge.
- Re-review both prior finding closure and newly introduced risk after fixes.
- Merge only when the current PR head equals the reviewed head, required checks
  are green, no blocking findings remain, and merge authorization is enabled.
- Never publish a release; release publication remains an explicit user action.

### R6. Structured Task Handoffs

- Define versioned `ReviewRequest` and `ReviewResult` JSON contracts.
- Every request must identify the workflow, repository, pull request, base SHA,
  head SHA, feature branch, evidence locations, checks, known limitations,
  source task, destination task, merge authorization, and dispatch ID.
- Every result must identify the dispatch, reviewed snapshot, decision,
  findings, verification, limitations, merge outcome, and destination task.
- Messages must contain a short instruction to invoke the intended plugin skill
  plus the machine-readable JSON payload.

### R7. Idempotency And State

- Derive a stable dispatch ID from repository identity, pull request number,
  head SHA, and reviewer task ID.
- Do not send the same pending or completed dispatch twice.
- Persist dispatch and result state atomically.
- Allow retry after a failed delivery without treating an unconfirmed send as a
  completed dispatch.
- Reject results whose dispatch, repository, pull request, or head does not
  match local state.

### R8. Installation And Distribution

- Package all required skills, scripts, schemas, templates, and UI metadata in
  the plugin directory.
- Provide a repository marketplace entry for installation and local testing.
- Validate the plugin and every bundled skill with the official validators.
- Document installation, initialization, capability requirements, local data,
  authorization, update, troubleshooting, and uninstall behavior.

## Acceptance Criteria

1. A clean installation exposes the Init, main-work, and review-and-merge
   skills with accurate UI metadata.
2. Init creates or binds exactly two reachable Codex tasks and writes a valid
   repository-scoped local configuration.
3. A second Init invocation detects the healthy workflow and creates no tasks.
4. A PR-ready main task emits exactly one review request for a given head SHA.
5. A blocking review result returns to the main task and a fixed head produces
   a new dispatch ID.
6. A stale review cannot approve or merge a changed head.
7. An approved exact head merges only when durable authorization and all merge
   gates are satisfied.
8. Missing Codex task tools, missing GitHub access, malformed configuration, or
   unreachable tasks produce actionable failure output without claiming the
   workflow is ready.
9. Local configuration and state contain no repository content or credentials.
10. Plugin, skill, schema, script, and marketplace validation pass from a clean
    checkout.

## Non-Goals

- Supporting Claude or any other external application.
- Defining a provider-neutral or cross-application protocol.
- Supporting GitLab, Bitbucket, or non-GitHub merge requests in version `0.1.0`.
- Supporting Codex CLI, IDE extension, ChatGPT Work mode, or mobile as complete
  orchestration surfaces in version `0.1.0`.
- Running main and reviewer edits concurrently in the same checkout.
- Changing the public API or behavior of the repository's Python packages.
- Publishing releases without a separate explicit user request.

## Failure And Recovery Expectations

- Missing capability: stop before task creation and list the missing tools.
- One task fails to initialize: mark configuration incomplete; archive only
  tasks created by the failed Init attempt when safe and report recovery steps.
- Stale or deleted task: stop dispatch, let Init repair or rebind the route.
- GitHub unavailable: preserve implementation state and report the exact auth or
  tool prerequisite; do not fabricate a PR or merge result.
- Message delivery uncertain: leave the dispatch retryable until the host
  confirms delivery.
- Reviewer crash or interruption: retain the pending dispatch and allow an
  explicit retry against the same immutable head.
- Head changed: mark the old dispatch stale and require a new request.

## Authorization And Privacy

- Initialization may create and pin tasks because the user invoked Init
  explicitly.
- Automatic merge is disabled until the user explicitly authorizes it during
  Init; the durable choice is visible and can be changed by re-running Init.
- Review comments, approvals, merge, release, and other external writes remain
  bounded by the original user request and configured policy.
- Task prompts and local state must not contain secrets. GitHub authentication
  remains owned by the GitHub connector or `gh`.

## Repository Location

Plugin work lives under `plugins/codex-feature-lifecycle/`. The plugin is a
Codex-specific product and intentionally contains no provider adapter layer.

## Repository Hygiene

- Feature branch: `codex/codex-feature-lifecycle-plugin`.
- Branch base: `origin/main` at the start of F0.
- Pre-existing untracked smoke outputs, distribution directories, and lock
  files are unrelated to this feature and are excluded from its commits.

## Decisions

- Version `0.1.0` is Codex Desktop and GitHub only.
- The workflow uses two long-lived, repository-scoped Codex tasks.
- User-local configuration lives outside the repository.
- Main and reviewer exchange versioned JSON payloads inside task messages.
- Automatic merge requires durable explicit authorization and deterministic
  gates; model prose alone never authorizes merge.
- Cross-application reuse is intentionally excluded rather than deferred.

## Next Phase

F2 will specify configuration and state schemas, message fields, task and
dispatch state machines, tool flows, safety gates, and failure recovery before
implementation planning begins.
