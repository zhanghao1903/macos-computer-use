# Review Lifecycle

## Request classes

`TechnicalPlanReviewRequest` binds one plan commit/composite digest.
`CodeReviewRequest` binds one PR number, base SHA, and head SHA. Accept only the
configured Main-to-Review route and latest expected cycle.

## Review-record branch

Names are supplied by the validated request:

```text
codex/review-records/<feature-id>/plan-<cycle>-<sha12>
codex/review-records/<feature-id>/code-<cycle>-<sha12>
```

Create a temporary worktree from the exact snapshot. Never use an unresolved
environment variable, glob, or current feature checkout as a destructive
target.

Before creating a branch, query local and remote refs. If absent, create/push
normally. If present, call workflow status:

- reuse only when state already records the same request, base, report commit,
  paths, and digests;
- otherwise stop with `review_record_conflict`;
- never reset, delete, or force-push the branch.

Persist prepared result proof before cross-task delivery.

## Plan decision

Follow `$technical-plan-review`:

- PASS only when mandatory criteria are complete and blocker/major counts are
  zero;
- FAIL returns actionable findings and re-review requirements;
- never edit plan content in Review.

## Code decision

Follow `$pr-review` and its re-review gates. Reports must name exact base/head,
commands/evidence, findings, limitations, and merge decision.

Immediately before merge, refresh live:

- PR head and draft state;
- required checks;
- mergeability;
- unresolved blocker evidence;
- configured merge mode/method.

Any changed head invalidates approval.

For `review-only`, deliver and apply `APPROVE` plus `READY` first. Review does
not execute the merge. If a separately authorized merge owner later merges the
exact head, re-read the live PR and return an observed `MERGED` result using the
same request and report proof. Do not create a new review cycle merely to
record that merge. Direct `MERGED` before READY fails closed.

## Result delivery

Return JSON produced by `workflowctl` unchanged. The report proof binds:

- deterministic branch;
- report path and optional JSON path;
- report commit SHA;
- SHA-256 for every report.

Mark host-confirmed delivery. A retry reuses the same message/result proof.
Re-preparing unchanged authority returns the originally stored payload and
timestamp. Every cycle after the first must bind
`previousResultMessageId` to the exact latest result; missing, stale, or
unrelated IDs are rejected.
