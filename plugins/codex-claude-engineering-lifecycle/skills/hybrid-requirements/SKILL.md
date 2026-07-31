---
name: hybrid-requirements
description: Run the Requirements Codex role of an initialized Codex-Claude Engineering Lifecycle workflow. Use when this task is the configured Requirements task and the user supplies a natural-language feature request, revises requirements, explicitly confirms or rejects a requirements snapshot, or retries a confirmed handoff to Engineering Main. Do not use for design, implementation, Claude dispatch, review, merge, release, closure, or another role.
---

# Hybrid Requirements

Turn a feature request into a confirmed, committed, immutable handoff. Read
[requirements-contract.md](references/requirements-contract.md) before
preparing or retrying it. Use
[requirements-template.md](assets/requirements-template.md) for new documents.

## Role gate

Run both:

```text
workflowctl.py status --repo <root> --task-id <current-task-id>
claudectl.py status --repo <root>
```

Continue only as configured workflow role `requirements` when both runtimes are
ready. Otherwise direct the user to `$hybrid-workflow-init`.

Bootstrap has one narrow exception. When workflow status proves this task is
bound to `requirements`, its bootstrap flag is false, and the message requests
acknowledgement, return only:

```json
{"type":"EngineeringRoleReady","workflowId":"<exact>","repositoryKey":"<exact>","taskId":"<exact>","role":"requirements"}
```

Do not begin feature work, acknowledge yourself, or claim global readiness.

## Intake and confirmation

- Ask only for product, API, safety, compatibility, frontend ownership, or
  release decisions that cannot be inferred conservatively.
- Record problem, scenarios, goals, non-goals, acceptance criteria,
  failure/recovery, public/safety/privacy impact, assumptions, open questions,
  and whether a frontend implementation slice is expected.
- Create `docs/feature/<slug>/requirements.md` on `codex/<slug>`.
- Keep status Draft until explicit user confirmation.
- Do not write the technical plan, classify final frontend paths, implement,
  review, merge, release, or close.

Show the whole snapshot for confirmation. Any revision invalidates prior
confirmation. On confirmation, fill the exact metadata, validate, commit only
requirements, push, and prove canonical `origin` has the same lowercase commit
SHA. This pushed commit is the authoritative requirements snapshot. Never
route a working-tree-only or unpushed document.

## Handoff

Run `workflowctl.py prepare-requirements` with exact feature, branch, document,
commit, and confirmation evidence. Send the returned JSON unchanged to the
configured Main Codex task using the task message tool.

After host-confirmed delivery, call `mark-dispatched`. On failure call
`mark-delivery-failed` with a sanitized reason. Reuse identical returned
payloads for retry; never reconstruct their timestamp or authority.

## Boundaries

- Route design, backend/frontend implementation, remediation, release, and
  closure to Main.
- Do not message either Claude session directly.
- Do not route review to a Codex task; Main owns the bridge to Claude Review.
- End with requirements path/commit, confirmation state, message ID, and
  delivery state.
