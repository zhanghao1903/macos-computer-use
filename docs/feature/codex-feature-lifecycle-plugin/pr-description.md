## Summary

Add `codex-feature-lifecycle` version `0.1.0`, a Codex Desktop + GitHub plugin
that coordinates two durable tasks for a complete feature workflow:

- main task: requirements, design, implementation, verification, PR readiness,
  automated review dispatch, finding fixes, and post-merge traceability;
- reviewer task: exact-snapshot independent review, re-review, strict merge
  gates, and structured result delivery;
- Init: explicit, idempotent creation/binding/readiness verification and local
  route/policy persistence.

## User Scenario

After one explicit Init, the user sends feature work to main. When a PR is
ready, main automatically sends a versioned immutable ReviewRequest to the
configured reviewer. Reviewer returns a validated ReviewResult and merges only
if exact-head, checks, findings, mergeability, and durable authorization all
pass. Routine handoff prompts no longer require manual relay.

## Scope And Boundaries

- Codex Desktop and `github.com` only.
- No Claude/cross-application adapter or shared provider protocol.
- No MCP server, daemon, hosted state, release publisher, or non-GitHub MR path.
- No Python package/public API/version changes.
- Real task creation and real PR merge remain explicit external-state smoke.

## Implementation

- Add three packaged skills with explicit role and mutation boundaries.
- Add `workflowctl.py` for private config, atomic state, stable dispatches,
  cancellation, idempotent retry, and closed transition validation.
- Add ReviewRequest/ReviewResult JSON Schemas plus independent runtime/schema
  fixture validation.
- Add repository marketplace metadata, complete plugin manifest, and SVG asset.
- Ship installation, update, local-data, recovery, and uninstall guidance.

## Safety

- Review-only is the default; auto-merge requires a separate durable grant.
- Dispatch identity binds repository, PR, base, head, workflow, and reviewer.
- Reviewer never edits the feature branch and never uses admin/auto merge.
- Guarded merge uses the reviewed head and rejects stale base/head or failing
  checks, remaining blocker/high findings, or policy mismatch.
- Config sanitizes origin credentials and stores no code, diff, prompts,
  transcripts, findings, or tokens.

## Verification

- 28 source tests: pass.
- 6 runtime + JSON Schema fixtures: both validators agree, pass.
- Three skill validators: pass.
- Plugin validator on source, local cache, and Git-downloaded cache: pass.
- Local isolated marketplace install and 23-file source/cache parity: pass.
- GitHub branch marketplace download/install and cached 28-test run: pass.
- Three independent non-mutating forward tests and repaired-gap re-review: no
  blocker/high issue.
- After synchronizing current `main`: root 132 tests, protocol 55 tests,
  computer-use 168 tests (1 skipped), and WeChat 171 tests all pass.
- `git diff --check` and JSON parsing: pass.

## Documentation And Release Record

- Requirements, design, implementation plan, implementation notes,
  verification, merge readiness, and this PR description are recorded under
  `docs/feature/codex-feature-lifecycle-plugin/`.
- `CHANGELOG.md` records the plugin under Unreleased.
- Plugin release version is `0.1.0`; no package distribution is published.

## Known Limitations

- Requires Codex task-management capabilities and shared repository-scoped
  local state for the configured tasks.
- Live two-task Init and an actual merge smoke were not run without explicit
  authorization; both are post-install opt-in proof.
- Unsupported future schema versions fail closed; v0.1.0 has no migration from
  foreign/legacy state.

## Rollback

Remove/revert the marketplace entry and plugin directory or uninstall through
Codex. Do not automatically delete user-owned tasks or local workflow history.
