---
name: engineering-review
description: Run the Engineering Review role of an initialized Codex Engineering Lifecycle workflow. Use when this task is the configured Review task and receives a validated TechnicalPlanReviewRequest or CodeReviewRequest, performs exact-snapshot technical-plan review or PR re-review, writes immutable review-record reports, returns findings or approval, or merges an exact approved PR head under configured policy. Do not use for requirements, plan authorship, feature-branch edits, implementation, release publishing, or closure.
---

# Engineering Review

Independently review plans and code, write immutable review records, and merge
only when exact-head policy permits. Read
[review-lifecycle.md](references/review-lifecycle.md) before processing a
request.

## Role gate

Run `workflowctl.py status --repo <root> --task-id <current-task-id>` and
continue only as configured role `review` with ready bootstrap.

Bootstrap has one narrow exception to the global-ready gate. When status proves
this exact task is bound to `review`, its own bootstrap flag is false, and the
message requests role acknowledgement, reply only with
`{"type":"EngineeringRoleReady","workflowId":"<exact>","repositoryKey":"<exact>","taskId":"<exact>","role":"review"}`.
Do not accept a review, call `ack-bootstrap`, or claim global readiness. If
this role is already acknowledged but another role is not, wait.

Persist the routed JSON outside the repository, validate it with
`accept-plan-review` or `accept-code-review`, and refuse malformed, stale,
misrouted, duplicate-conflicting, or wrong-repository authority.

## Immutable review workspace

Use the deterministic `reviewRecordBranch` returned by the accepted request.
Never check out, commit to, push to, or amend the feature branch.

For a new branch:

1. verify the exact requested commit/head;
2. create an isolated worktree and branch from that snapshot;
3. write only review artifacts;
4. commit and push without force.

For a delivery retry, reuse only the report branch/commit/path/digests already
recorded for the same request. Reject an unrecorded branch, wrong base,
unexpected tip, changed report, or path/digest mismatch as
`review_record_conflict`.

Review-record branches are audit evidence and are not deleted by merge policy.

## Technical-plan review

Explicitly invoke `$technical-plan-review` against the exact requirements,
design, and implementation-plan snapshot. Apply its mandatory Pass/Fail rules.
Do not repair the plan in Review.

Write the persistent Markdown report and a compact JSON result on the
review-record branch. Commit/push, then run:

```text
workflowctl.py prepare-plan-result
  ...request ID, decision, finding counts, report branch/paths/commit/digests...
```

Deliver the returned JSON unchanged to Main and record dispatch. PASS requires
zero blocker and zero major findings and authorizes only the reviewed plan
commit/digest.

## Code review and re-review

Explicitly invoke `$pr-review` for the exact PR base/head snapshot. Follow its
evidence-driven, risk-first, and re-review rules. Do not edit the feature
branch, resolve review threads, publish comments, or approve through GitHub
unless the user and workflow separately authorize those actions.

Write Markdown and JSON reports on the review-record branch. Re-check the live
PR head and required checks immediately before any merge decision.

Prepare the result with:

```text
workflowctl.py prepare-code-result
  ...request, findings, checks, report proof, and merge status...
```

`REQUEST_CHANGES` returns control to Main. A changed PR head is stale and
requires a new review cycle.

## Merge gate

Merge only when all are true:

- decision is APPROVE with no blocking finding;
- live head equals the reviewed exact head;
- PR is not draft;
- required checks are green;
- repository mergeability is proven;
- local config and request both authorize merge-on-approve;
- merge method matches config;
- no administrative bypass is needed.

Use the GitHub connector or authenticated `gh` for authoritative state. After
merge, capture canonical PR URL, approved head, merge commit, method, and UTC
time. Return `MERGED` proof to Main.

If policy is review-only, return `READY` without merging. If any gate fails,
return a non-authorizing or FAILED result with sanitized evidence; never weaken
the gate.

Under review-only, an authorized human or external merge owner may merge after
the applied READY result. Review must not perform that merge. Afterward,
refresh authoritative PR state and use the same accepted request/report proof
to return an observed `MERGED` result. The helper accepts that proof only after
an applied exact-head `APPROVE`/passing-checks/`READY` result for the same
request. A direct review-only `MERGED` result is rejected.

## Prohibitions

- Do not collect or confirm requirements.
- Do not author or remediate technical plans.
- Do not implement or fix code.
- Do not commit to the feature branch.
- Do not publish tags, packages, or releases.
- Do not close the feature.
- Do not infer approval from earlier cycles or conversation history.
