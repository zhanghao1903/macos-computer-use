# Codex Feature Lifecycle Plugin

Status: F0 scaffold

## Problem

The repository's feature lifecycle currently depends on a user manually
transferring work from a main implementation task to a separate pull-request
review and merge task. The intended plugin will let Codex carry that workflow
end to end without a manual task-to-task handoff.

## Initial Scope

- Package the workflow as an installable Codex plugin.
- Use dedicated Codex tasks for main work and pull-request review and merge.
- Provide an explicit initialization entry point that creates or binds the
  workflow tasks and stores their local routing configuration.
- Automate structured handoffs, review feedback, re-review, and merge-result
  reporting between those tasks.
- Preserve the existing feature lifecycle requirements for documentation,
  verification, release records, and traceability.

## Non-Goals

- Supporting Claude or any other external application.
- Defining a provider-neutral or cross-application protocol.
- Implementing initialization, routing, review, or merge behavior during this
  F0 scaffold phase.
- Changing the public API or behavior of the repository's Python packages.

## Repository Location

Plugin work lives under `plugins/codex-feature-lifecycle/`. The scaffold starts
with the required `.codex-plugin/plugin.json` manifest and reserves standard
plugin directories for skills, scripts, and assets as those resources become
necessary.

## Repository Hygiene

- Feature branch: `codex/codex-feature-lifecycle-plugin`.
- Branch base: `origin/main` at the start of F0.
- Pre-existing untracked smoke outputs, distribution directories, and lock
  files are unrelated to this feature and are excluded from its commits.

## Next Phase

F1 will define the initialization contract, the two Codex task roles, local
configuration ownership, lifecycle states, authorization boundaries, failure
recovery, and acceptance scenarios before implementation begins.
