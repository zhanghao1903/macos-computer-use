# Review Contract

## Completion Definition

A review is complete only when it:

- fixes the exact base/head snapshot;
- maps the changed surface and critical behavior paths;
- examines implementation, tests, docs, changelog, and operational impact;
- records commands/checks and limitations;
- produces a justified decision;
- validates merge gates immediately before any merge;
- prepares and delivers a schema-valid ReviewResult.

## Risk Priority

Review in this order when applicable:

1. authorization, confirmation, and unsafe external writes;
2. data loss, destructive behavior, secrets, and privacy;
3. correctness of state transitions, idempotency, retries, and concurrency;
4. validation/parsing at trust boundaries and prompt-injection exposure;
5. public API/protocol/config compatibility and migration;
6. packaging, CI, release, and generated artifact integrity;
7. tests, docs, examples, diagnostics, and maintainability.

## Finding Quality

Every finding must include:

- stable ID such as `FINDING-001`;
- severity: `blocker`, `high`, `medium`, or `low`;
- concise summary;
- repository-relative file and tight line when applicable;
- concrete user/system impact;
- evidence or reproducible reasoning;
- actionable required change.

Do not report:

- unsupported speculation;
- pure style preference without material impact;
- vague whole-file or whole-directory locations;
- missing tests without identifying the unprotected behavior;
- duplicates split into multiple findings.

Severity meaning:

- `blocker`: unsafe or invalid to merge under any normal condition.
- `high`: likely correctness/security/data/compatibility failure that blocks
  merge.
- `medium`: real non-blocking defect or material maintainability/diagnostic gap.
- `low`: small concrete improvement that does not block the reviewed behavior.

## Decision Rules

### REQUEST_CHANGES

Use when at least one confirmed finding requires a new commit before merge.
Blocker/high findings always require changes.

### COMMENT

Use when review is complete but feedback is non-blocking, or limitations prevent
a strong approval without proving a defect.

### APPROVE

Use only when:

- no blocker/high finding remains;
- the reviewed snapshot is current;
- critical behavior paths are covered by evidence;
- docs/changelog match implementation;
- limitations do not undermine merge safety.

Approval is scoped only to the recorded base/head. Any head change invalidates
it immediately.

### STALE

Use when GitHub base/head differs from ReviewRequest. Do not continue review on
the new head under the old dispatch.

### FAILED

Use when repository access, GitHub auth, required diff/check data, or another
hard dependency prevents a defensible review.

Use merge status `NOT_ATTEMPTED` for `COMMENT`, `REQUEST_CHANGES`, `STALE`, and
review-level `FAILED`. `APPROVE` must use `NOT_AUTHORIZED`, `DEFERRED`, `MERGED`,
or merge-command `FAILED`. Do not attach merge URL/SHA/error fields unless the
selected status requires them.

## Re-Review

For every prior finding, record one state:

- `fixed`: evidence proves the required behavior now holds;
- `open`: defect remains;
- `regressed`: attempted repair worsened or reintroduced it;
- `superseded`: design changed and evidence proves the old finding no longer
  applies.

Then independently inspect all commits since the reviewed old head. Do not let
finding closure substitute for reviewing induced risk. A new head always needs
a new ReviewRequest/dispatch ID.

## Verification Evidence

Prefer direct evidence:

- full diff and surrounding code reads;
- targeted unit/contract/integration tests;
- repository-required lint/type/build/package checks;
- GitHub check rollup and exact head/base;
- manifest/schema validators;
- manual proof only when genuinely run.

Record commands and outcomes. Never claim checks, coverage, smoke, or external
state not observed.

## Merge Rules

Merge only an approved exact head. Required gates:

- durable local authorization;
- matching request policy;
- open non-draft PR;
- exact base/head;
- green required checks with none pending;
- mergeable state;
- no blocker/high findings;
- guarded merge command using configured method;
- no admin bypass and no deferred auto-merge.

After the command, query GitHub again and record merged state, PR URL, and merge
SHA. If post-merge proof is unavailable, report failure/uncertainty rather than
claiming success.

## Result Finding Shape

```json
{
  "id": "FINDING-001",
  "severity": "high",
  "summary": "Short defect title",
  "file": "path/to/file.py",
  "line": 42,
  "impact": "What can fail and for whom.",
  "evidence": "Observed behavior or code path proving the issue.",
  "requiredAction": "Specific change needed before closure."
}
```

Omit `line` only when no single line can represent the issue. Keep findings
free of secrets and large source excerpts.

## Review Summary

Return a compact human summary alongside ReviewResult:

- decision;
- exact snapshot;
- critical paths reviewed;
- findings by severity;
- checks and limitations;
- re-review closure when applicable;
- merge gate/outcome;
- result delivery status.
