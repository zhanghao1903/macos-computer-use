# Setup and Recovery

## Required capabilities

- Codex task create/read/wait/message/pin tools.
- Platform Goal create/get/terminal-update tools.
- GitHub repository, PR, checks, merge, tag, release, and artifact access.
- Local Git and Python 3.
- Authenticated Claude Code CLI supporting explicit session UUID, resume,
  print-mode JSON, JSON Schema output, model, permission, turn, budget, and
  system-prompt-file flags.

Init creates only two user-owned Codex tasks. Claude sessions are persistent
local Claude Code sessions and remain after plugin uninstall.

## State

Both helpers derive one private root from canonical GitHub origin and Git common
directory:

```text
${CODEX_HOME:-~/.codex}/codex-claude-engineering-lifecycle/projects/<key>/
├── init-pending.json
├── config.json
├── state.json
├── state.lock
├── claude-init-pending.json
├── claude-config.json
├── claude-state.json
├── claude.lock
└── messages/
    └── <message-id>.result.json
```

State stores identities, policies, stages, paths, SHAs, digests, timestamps,
structured Claude results, and sanitized errors. It excludes credentials, raw
Claude transcripts, full source, diffs, raw prompts, and command logs.

## Bootstrap acknowledgements

Codex roles return:

```json
{
  "type": "EngineeringRoleReady",
  "workflowId": "<uuid>",
  "repositoryKey": "<owner/repo>",
  "taskId": "<exact Codex task id>",
  "role": "requirements|main"
}
```

Claude roles return through the bridge schema:

```json
{
  "schemaVersion": 1,
  "type": "ClaudeRoleReady",
  "messageId": "<digest>",
  "requestDigest": "<digest>",
  "workflowId": "<uuid>",
  "repositoryKey": "<owner/repo>",
  "sessionId": "<exact UUID>",
  "role": "frontend|review",
  "status": "READY"
}
```

Do not accept prose-only readiness.

## Recovery

- Claude missing/not authenticated: install or run `claude auth login`
  manually, then rerun `probe`. Do not persist credentials in plugin state.
- interrupted Claude Init: rerun matching `begin-init`; reuse both UUIDs.
- interrupted Codex task creation: reuse every pending recorded task ID before
  creating anything.
- config-only workflow crash: rerun final workflow Init with exact recorded
  endpoints, then final Claude Init.
- missing bootstrap: rerun only that role. An UNKNOWN bootstrap resumes the
  same UUID with a recovery query.
- `session_busy`: wait for the running call. Do not resume the same session in
  another process.
- orphaned `RUNNING`: first prove the Claude process is stopped, then use
  `mark-orphaned --message-id <id> --confirm-process-stopped`; it becomes
  UNKNOWN. Never mark an active process orphaned.
- `UNKNOWN`: inspect sanitized status and Git state, then run `recover` with the
  identical request file. Do not send another message to that role first.
- `frontend_path_escape`, stale head, dirty state, or claim mismatch: preserve
  the checkout and ask the user to choose repair or explicit takeover. Never
  reset automatically.
- task/session/config mismatch: stop. Compare exact repository, common
  directory, workflow, four IDs, models, budgets, and policy.
- malformed state: preserve files and restore from a known valid backup or
  explicit migration; never hand-edit.

Repeated Init is idempotent only when repository, role IDs, command path,
models, limits, Goal policy, and merge policy match.

## Uninstall

Uninstall does not archive Codex tasks, remove Claude sessions, delete state,
delete branches/review records, close PRs, or remove releases/packages. Delete
only the exact derived state directory after the user explicitly accepts losing
recovery and audit history.
