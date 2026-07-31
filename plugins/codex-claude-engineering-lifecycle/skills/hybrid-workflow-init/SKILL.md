---
name: hybrid-workflow-init
description: Initialize, inspect, repair, or explain a Codex-Claude Engineering Lifecycle workflow for the current trusted GitHub repository. Use only when the user explicitly asks to run Init, create or bind the two Codex tasks and two Claude sessions, inspect hybrid workflow status, recover incomplete bootstrap or UNKNOWN delivery, or configure Goal, Claude edit/model/budget, and merge policy. Do not use for feature intake or delivery.
---

# Hybrid Workflow Init

Initialize one repository-scoped workflow with two Codex tasks and two durable
Claude Code sessions. Read
[setup-and-recovery.md](references/setup-and-recovery.md) completely before
creating identities or repairing state.

## Guardrails

- Treat explicit Init as authorization to create and pin only Requirements and
  Engineering Main Codex tasks and to create only Frontend and Review Claude
  sessions.
- Do not create a feature, branch, plan, PR, merge, tag, release, or package.
- Do not install Claude Code, start authentication, read credentials, or use
  `--dangerously-skip-permissions`.
- Stop before persistence if canonical GitHub identity, task tools, Goal tools,
  GitHub read access, Claude probe/auth, or explicit edit/Goal authorization is
  missing.
- Keep Frontend and Review session UUIDs distinct. Review never uses the
  Frontend session.
- Never hand-edit workflow or Claude JSON state.

## Preflight and choices

1. Resolve the plugin root and both helpers:
   `scripts/workflowctl.py` and `scripts/claudectl.py`.
2. Verify one trusted GitHub `origin`, Git common directory, readable default
   branch, Python 3, task tools, Goal tools, and GitHub state tools.
3. Run `workflowctl.py status --repo <root>` and
   `claudectl.py status --repo <root>`.
4. Explain the four roles, one active Goal, serialized Claude resumes,
   frontend path authority, exact review/merge gates, external Anthropic data
   boundary, local retained state, and explicit release authorization.
5. Obtain explicit choices:
   - Goal mode authorized: required;
   - Claude Frontend edits authorized: required;
   - Frontend model (propose `sonnet`);
   - Review model (propose `opus`);
   - per-role max turns and USD budgets;
   - dispatch timeout;
   - `review-only` (recommended) or `merge-on-approve` plus merge method.

Run the Claude probe before writing Init state:

```text
claudectl.py probe --claude-command <claude-or-absolute-path>
```

Only authenticated success may continue.

## Recoverable identity creation

First run `claudectl.py begin-init` with the confirmed models, limits, timeout,
and `--frontend-edit-authorized`. Record the returned Frontend and Review UUIDs
exactly; repeated matching calls reuse them.

Then run `workflowctl.py begin-init` with Goal and merge policy. Create and pin
exactly:

- `Requirements · <repository>`;
- `Engineering Main · <repository>`.

Immediately record their IDs with `record-init-task`. Record the Claude Review
UUID as the workflow `review` endpoint; do not create a third Codex task:

```text
workflowctl.py record-init-task
  --role review
  --created-task-id <claude-review-session-uuid>
```

Finalize `workflowctl.py init` with Requirements/Main task IDs and the Review
UUID in `--review-task-id`. Then finalize:

```text
claudectl.py init
  --repo <root>
  --workflow-id <workflow-uuid>
  --requirements-task-id <codex-id>
  --main-task-id <codex-id>
```

Every one of the four IDs must be distinct. Reuse pending identities after
interruption; never create replacements merely because a role is idle.

## Bootstrap

Send the two Codex tasks bootstrap messages containing workflow/repository,
both task IDs, both Claude session IDs, exact role, and required skill:

- Requirements: `$hybrid-requirements`;
- Main: `$hybrid-main`.

Require the exact `EngineeringRoleReady` JSON and record each with
`workflowctl.py ack-bootstrap`.

Bootstrap Claude roles through the bridge:

```text
claudectl.py bootstrap --repo <root> --role frontend
claudectl.py bootstrap --repo <root> --role review
```

The bridge uses the exact recorded UUID and structured acknowledgement. After
Review succeeds, record workflow role `review` acknowledgement with its session
UUID. Do not interpret prose as readiness.

## Finish

Run both status commands. Claim readiness only when:

- workflowctl requirements/main/review bootstrap flags are true;
- claudectl frontend/review bootstrap flags are true;
- Review workflow endpoint equals the Claude Review UUID;
- all four IDs remain distinct.

Report workflow ID, repository, task/session titles and IDs, models/budgets,
Goal/merge policy, state root, recovery commands, and that new features belong
in Requirements.

## Prohibitions

- Do not submit a feature during Init.
- Do not send Review work to a Codex review task.
- Do not bind Frontend and Review to the same session.
- Do not answer permission or user-input requests inside another role.
- Do not delete sessions, tasks, state, branches, or review records as recovery.
