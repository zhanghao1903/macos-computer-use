# Setup and Recovery

## Required capabilities

Discover rather than assume:

- task create, read, wait, message, and pin;
- Goal create, get, and terminal update;
- GitHub repository, PR, checks, merge, tag, release, and artifact access;
- local Git and Python 3.

Use `create_thread` only after the user explicitly runs Init. The created tasks
are user-owned and remain in the sidebar after plugin uninstall.

## State

The helper derives:

```text
${CODEX_HOME:-~/.codex}/engineering-lifecycle/projects/<repository-key>/
├── init-pending.json  # only while Init is incomplete
├── config.json
├── state.json
└── state.lock
```

The repository key derives from the canonical GitHub origin and Git common
directory. Worktrees of one repository share one workflow.

State contains IDs, policies, stages, paths, SHAs, digests, timestamps, and
sanitized errors. It excludes credentials, raw prompts, transcripts, source
content, diffs, findings text, and command logs.

## Bootstrap acknowledgement format

Each role must reply with:

```json
{
  "type": "EngineeringRoleReady",
  "workflowId": "<uuid>",
  "repositoryKey": "<owner/repo>",
  "taskId": "<exact id>",
  "role": "requirements|main|review"
}
```

Do not accept prose-only acknowledgement.

The role task does not call `ack-bootstrap`. It returns the JSON to the Init
task, which validates the exact values and records the acknowledgement. Global
readiness remains false until all three acknowledgements are recorded.

## Recovery

- `workflow_not_initialized`: rerun Init from the exact repository.
- `init_not_started`: run `begin-init` before creating any tasks.
- interrupted task creation: read `status`, reuse every task ID in the pending
  ledger, and record only a proven existing missing role before creating one.
- `init_recovery_required`: use the recorded IDs and policy to rerun final
  `init`; a config-only crash window reconstructs empty state with the same
  workflow ID.
- `bootstrap_incomplete`: inspect status and resend only missing role bootstrap.
- `task_role_mismatch`: stop; do not rewrite IDs silently.
- `config_conflict`: compare canonical origin, common directory, policies, and
  task IDs; require explicit reconfiguration.
- missing task: prove it is unavailable, then ask before replacing it.
- corrupt state: preserve the files, report the validator error, and restore
  from a known backup or reconstruct through an explicit migration.

Repeated Init is idempotent only when repository identity, task IDs, and policy
match.

## Uninstall and cleanup

Plugin uninstall does not archive tasks or remove state. Archive tasks
separately. Delete only the exact derived project state directory after the user
confirms loss of retry, policy, and audit history. Never delete Git branches,
PRs, review records, tags, releases, or packages as part of state cleanup.
