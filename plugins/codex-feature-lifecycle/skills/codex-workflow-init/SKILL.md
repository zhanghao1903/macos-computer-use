---
name: codex-workflow-init
description: Initialize, inspect, repair, or reconfigure the Codex Feature Lifecycle workflow for a GitHub repository. Use only when the user explicitly asks to initialize the workflow, create or bind its main and review tasks, change its merge policy, repair stale task routes, or show workflow configuration/status. Requires Codex Desktop task-management capabilities; do not use for ordinary feature implementation or standalone PR review.
---

# Codex Workflow Init

Establish one repository-scoped main task and one review-and-merge task. Make
initialization idempotent, prove both routes before declaring success, and
store only local routing and policy state.

Read [setup and recovery](references/setup-and-recovery.md) when the user asks
how to install, update, uninstall, locate local state, or recover a partial
initialization.

## Product Boundary

- Support Codex Desktop and GitHub only.
- Do not add provider adapters or external-application fields.
- Do not create tasks unless the user explicitly invoked this skill.
- Do not infer authorization for automatic merge. Obtain it separately.
- Do not change source code, feature branches, GitHub PRs, or releases.

## Resolve Bundled Resources

Resolve `<plugin-root>` as two directories above this skill directory. Use:

```text
<plugin-root>/scripts/workflowctl.py
```

Run it with `python3`. If Python is unavailable and Codex exposes bundled
workspace dependencies, resolve and use the bundled Python runtime. Do not
install a runtime or dependency during Init.

## Required Capability Preflight

Before creating, renaming, pinning, or messaging a task, verify callable Codex
capabilities equivalent to:

- `list_projects`
- `create_thread`
- `list_threads`
- `read_thread`
- `send_message_to_thread`
- `wait_threads`
- `set_thread_title`
- `set_thread_pinned`
- `set_thread_archived` for recoverable partial cleanup

Tool names may be host-qualified. Treat the current callable capability as
authoritative. If any required non-cleanup capability is unavailable, stop and
report every missing capability. Do not write a configuration.

Also verify all of:

- current directory is inside a trusted git repository;
- `origin` exists and resolves to GitHub;
- either a connected GitHub tool or authenticated `gh` can read PR state;
- the repository appears in `list_projects` with an exact canonical-path match.

Do not create a projectless task for a repository workflow.

## Inspect Before Mutating

1. Resolve the canonical repository root and sanitized origin.
2. Run `workflowctl.py locate --repo-root <root>`.
3. Run `workflowctl.py show --repo-root <root>`.
4. If valid config exists, call `read_thread` for both configured task IDs.
5. When both routes are reachable and the user did not request a policy or
   route change, reuse the workflow and create no tasks.
6. When config is stale, do not overwrite it silently. Discover exact-title
   task candidates. Bind a single unambiguous healthy pair; otherwise ask the
   user which pair to use or whether replacements should be created.

Config-not-found is the expected path for first initialization, not an error to
hide. Invalid schema, repository mismatch, or unreachable configured tasks must
be reported before repair.

## Obtain Policy

Before first initialization or explicit reconfiguration, obtain these choices:

1. May the reviewer automatically merge an approved exact head after all gates
   pass? Default to `review-only` unless the user explicitly answers yes.
2. If merge is authorized, choose `squash`, `merge`, or `rebase`. Recommend
   `squash` when repository policy does not choose. For `review-only`, persist
   `squash` as the inert default so configuration is deterministic.
3. Whether to delete the branch after merge. Default to false.

Explain that durable authorization applies only to exact-head, green-check,
no-blocker merges and never authorizes release publication or admin bypass.

## Create Or Bind The Tasks

Prefer binding healthy existing tasks when the user selected them. Otherwise:

1. Call `list_projects` and select the exact current repository.
2. Create both tasks in that project's `local` environment. Omit model and
   reasoning overrides so user defaults apply.
3. Track the IDs created by this Init attempt in memory until configuration is
   committed.
4. Title and pin the tasks:
   - `Feature Main · <repository-name>`
   - `PR Review & Merge · <repository-name>`
5. Use these bounded bootstrap prompts.

Main prompt:

```text
Use $codex-feature-main as the durable main-work role for <repository-root>.
Do not start feature work yet. Confirm the canonical repository and reply with
exactly MAIN_READY when the role is loaded and the checkout is accessible.
```

Reviewer prompt:

```text
Use $codex-pr-review-merge as the durable review-and-merge role for
<repository-root>. Do not inspect or edit feature code yet. Accept only a
validated ReviewRequest and never edit the feature branch. Reply with exactly
REVIEW_READY when the role is loaded and the checkout is accessible.
```

6. Wait for both tasks. After trimming surrounding whitespace, the entire final
   response must equal the expected marker (`MAIN_READY` or `REVIEW_READY`) and
   contain no other text. Substring matches such as `NOT_MAIN_READY` fail.
7. If either task fails, do not write ready config. Archive only tasks created
   by this failed attempt when the host supports recoverable archive and the
   target is exact. Otherwise report their IDs for manual recovery.

Whenever this skill creates, archives, renames, pins, or reconfigures tasks,
announce that action in commentary immediately before taking it.

## Persist Only After Readiness

After both tasks are proven reachable, run:

```text
workflowctl.py init
  --repo-root <root>
  --origin <origin>
  --project-id <project-id>
  [--host-id <host-id>]
  --main-thread-id <main-id>
  --review-thread-id <review-id>
  --merge-policy <review-only|merge-on-approve>
  --merge-method <squash|merge|rebase>
  [--delete-branch]
  [--replace]
```

Use `--replace` only after explicit reconfiguration/repair and after proving the
new routes. If writing the user-local Codex state requires sandbox escalation,
request the narrow approval and retry; do not fall back to a tracked repository
file.

Then run `workflowctl.py validate --repo-root <root>` and read both tasks once
more. Initialization succeeds only when script validation and task reachability
both pass.

## Idempotency

- A healthy repeated Init creates no tasks and does not rewrite config.
- Never select tasks by title alone when multiple candidates match.
- Never overwrite a different config without explicit repair/reconfiguration.
- Never report a partial task pair as ready.
- Never store tokens, prompts, transcripts, code, diffs, or findings in config.

## Final Response

Return:

- Initialization: created, bound, reused, repaired, or failed
- Repository and workflow ID
- Main task ID and reachability
- Reviewer task ID and reachability
- Merge policy, method, and branch deletion policy
- Config path and validation result
- GitHub capability used
- Any partial resources or recovery action
- Next action: on success, send the feature request to the main task; on
  failure, resolve the reported preflight/recovery issue and rerun Init
