---
name: engineering-workflow-init
description: Initialize, inspect, repair, or explain a Codex Engineering Lifecycle workflow for the current trusted GitHub repository. Use when a user explicitly asks to run Init, create or bind the three Requirements/Main/Review tasks, inspect workflow status, recover incomplete bootstrap, or configure Goal and merge policy. Do not use for feature intake, plan writing, implementation, review, merge, release, or uninitialized repositories without explicit Init intent.
---

# Engineering Workflow Init

Initialize one repository-scoped workflow with exactly three durable Codex
tasks. Read [setup-and-recovery.md](references/setup-and-recovery.md) before
creating tasks or repairing state.

## Guardrails

- Treat the user's explicit Init request as authorization to create and pin the
  three named tasks only.
- Do not create feature branches, requirements, plans, PRs, merges, tags, or
  releases.
- Use task-management tools, Goal tools, and the GitHub connector or
  authenticated `gh`; discover deferred tools before declaring them missing.
- Stop before persistence when repository identity, task tooling, Goal
  tooling, GitHub read access, or explicit Goal authorization is missing.
- Keep release policy fixed at `explicit-per-release`.
- Never reuse task IDs from another canonical repository or plugin state root.
- Never hand-edit config/state JSON.

## Preflight

1. Resolve the plugin root two directories above this skill and locate
   `scripts/workflowctl.py`.
2. Verify the current directory is a trusted Git checkout with one canonical
   GitHub `origin`, a resolvable Git common directory, and a readable default
   branch.
3. Discover tools for:
   - create/read/wait/message tasks;
   - pin tasks;
   - create/get/update Goal state;
   - inspect GitHub repository and PR/check/release state.
4. Run `workflowctl.py status --repo <root>`. An absent workflow is expected on
   first Init; malformed or conflicting state is not.
5. Explain the three roles, single-active-Goal queue, immutable review-record
   branches, exact-head merge gate, explicit release gate, and retained local
   state.

## Required user choices

Obtain explicit confirmation that approved work may use Goal mode. Without it,
Init must stop.

Obtain merge policy:

- `review-only` (recommended); or
- `merge-on-approve`, plus `squash`, `merge`, or `rebase`.

Require green checks and exact head in every policy. Default branch deletion to
false unless the user explicitly chooses it. Review-record branches are never
deleted by this policy.

## Create or bind tasks

Use the repository name in exact titles:

- `Requirements · <repository>`;
- `Engineering Main · <repository>`;
- `Engineering Review · <repository>`.

Before creating the first task, persist the recoverable Init ledger:

```text
workflowctl.py begin-init
  --repo <repository-root>
  --goal-mode-authorized
  --merge-mode <review-only|merge-on-approve>
  --merge-method <squash|merge|rebase>
  [--delete-branch]
```

On first Init, create exactly those three project-scoped tasks, pin them, and
immediately record each returned ID:

```text
workflowctl.py record-init-task
  --repo <repository-root>
  --role <requirements|main|review>
  --created-task-id <id>
```

On repeated or interrupted Init, inspect `status` first and reuse every task ID
already present in the pending ledger. Never recreate a recorded role. If task
creation returned but its ledger write did not, list/read exact-title tasks,
verify their repository/bootstrap message, and record that existing ID before
creating anything. Do not create replacements merely because a task is idle.
If one task is missing, repair only after proving the other bindings and
repository identity match.

Task creation is asynchronous. Wait for task availability without answering
approval or user-input requests on another task's behalf.

## Persist configuration

Run:

```text
python <plugin-root>/scripts/workflowctl.py init
  --repo <repository-root>
  --requirements-task-id <id>
  --main-task-id <id>
  --review-task-id <id>
  --goal-mode-authorized
  --merge-mode <review-only|merge-on-approve>
  --merge-method <squash|merge|rebase>
  [--delete-branch]
```

Copy the returned `workflowId` and canonical repository key exactly.
Finalization must use exactly the three IDs and policy in the pending ledger.
The helper repairs the recoverable `config.json`-written/`state.json`-missing
crash window and reports `recovered: true`.

## Bootstrap roles

Send each task a short bootstrap message containing:

- workflow ID and repository key;
- all three task IDs;
- that task's exact role;
- the required role skill:
  - Requirements: `$engineering-requirements`;
  - Main: `$engineering-main`;
  - Review: `$engineering-review`;
- instruction to read durable status before acting;
- instruction to acknowledge without beginning feature work.

Each role skill has a bootstrap-only exception that permits this acknowledgement
before global readiness; it permits no feature work. Require an acknowledgement
that names the same workflow, task ID, and role.
Record each with:

```text
workflowctl.py ack-bootstrap --repo <root> --role <role> --task-id <id>
```

Retry only missing acknowledgements. Reject a role/task mismatch.

## Finish

Run `workflowctl.py status --repo <root>` and report:

- workflow ID and repository;
- three task titles/IDs and readiness;
- Goal and merge policy;
- state location;
- that new feature requests belong in Requirements;
- recovery command and uninstall/state-retention boundary.

Do not claim success until all three acknowledgements are durable.
