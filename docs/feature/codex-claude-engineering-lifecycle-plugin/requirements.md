# Codex-Claude Engineering Lifecycle Requirements

## F0 — Intake and repository hygiene

- Feature: add a separate `codex-claude-engineering-lifecycle` plugin.
- Base: `codex/engineering-lifecycle-plugin` at
  `c8fa2770bc35aac428b5aaf22b1c5fb79ca0f222`.
- Feature branch: `codex/claude-hybrid-engineering-lifecycle-plugin`.
- Isolation: development runs in
  `/private/tmp/macos-computer-use-claude-hybrid-lifecycle`; unrelated
  untracked smoke and release artifacts in the primary worktree are excluded.
- Existing behavior: `codex-engineering-lifecycle` uses three Codex tasks for
  Requirements, Main, and Review.
- Requested behavior: keep requirements and primary engineering in Codex while
  delegating frontend implementation and independent review to durable Claude
  sessions.
- Packaging boundary: add one sibling repo-marketplace plugin. Do not change
  package APIs, desktop automation behavior, or the existing lifecycle plugin.
- External dependency: Claude Code CLI must be installed and authenticated by
  the user. The plugin must probe it and fail closed; Init must not install or
  authenticate Claude automatically.
- Phase records: this directory carries requirements, design, implementation
  plan, implementation notes, verification, and merge-readiness evidence.
- Release impact: plugin-only Unreleased entry; no Python package version bump
  or package publishing.

## F0 assumptions

- “Claude session” means a persistent Claude Code session addressable by an
  explicit UUID and resumed programmatically from the repository.
- Claude Frontend and Claude Review are different session IDs.
- This feature may build on the unmerged engineering-lifecycle source branch;
  its eventual pull request must declare that dependency.

## F1 — Confirmed requirements

### User scenarios

1. A repository owner installs one plugin and runs Init once. Init creates two
   durable Codex tasks (Requirements and Engineering Main), creates two durable
   Claude Code sessions (Frontend and Review), binds all four identities to the
   canonical GitHub repository, and verifies every role before accepting work.
2. The Requirements task turns a natural-language request into a versioned,
   explicitly confirmed handoff and sends it to Engineering Main.
3. Engineering Main writes the complete technical plan. Claude Review examines
   the exact plan snapshot and returns a structured PASS/FAIL result before
   development can begin.
4. Engineering Main owns backend, infrastructure, integration, release, and
   closure work. Every frontend slice and frontend remediation slice is sent to
   Claude Frontend with an exact starting commit and explicit allowed paths.
5. Claude Frontend edits and tests only the authorized frontend slice. Main
   rejects the result if the branch, starting commit, or changed paths differ
   from the request.
6. After implementation and integration proof, Claude Review examines the
   exact PR base/head snapshot and produces a durable report and structured
   APPROVE/REQUEST_CHANGES/STALE result.
7. Findings return to their owning executor: frontend findings go to Claude
   Frontend; all other findings go to Engineering Main. Every remediation
   invalidates the previous approval and requires exact-head re-review.
8. Merge, release, and closure retain the existing lifecycle’s exact-snapshot,
   required-check, explicit-release-authorization, proof, and replay gates.

### Role and independence requirements

- Requirements and Engineering Main must be separate Codex task IDs.
- Claude Frontend and Claude Review must be separate Claude session UUIDs.
- No identity may own more than one of the four roles.
- Claude Review must not modify the feature branch or implement findings.
- Claude Frontend must not issue review decisions, merge, publish, or close a
  feature.
- Engineering Main must not directly implement files classified by the
  accepted technical plan as frontend-owned, except for an explicitly recorded
  emergency takeover authorized by the user.
- Review content must originate from Claude Review. Codex may perform only
  deterministic transport, schema validation, audit-record persistence, and
  policy-gated merge mechanics around that decision.

### Cross-application communication requirements

- Use Claude Code’s explicit `--session-id` and `--resume` session addressing;
  never rely on “most recent session”.
- Use non-interactive print mode and JSON Schema structured output for every
  bootstrap, frontend, plan-review, code-review, and re-review response.
- Invoke Claude through an argument vector without a shell and never interpolate
  request content into shell commands.
- Every request must carry a unique message ID, workflow ID, feature ID, cycle,
  source/destination role, repository key, exact authority snapshot, and
  SHA-256 digest.
- Persist a private, repository-scoped delivery ledger before dispatch. An
  identical retry must be idempotent; a conflicting reuse of a message ID must
  fail closed.
- Persist structured results and proof metadata, not credentials, raw Claude
  transcripts, full source files, or diffs.
- Dispatch must be serialized per Claude session. A session cannot be resumed
  concurrently because interleaved messages would corrupt role history.

### Init and configuration requirements

- Probe the configured Claude executable and `claude auth status` before
  creating workflow state.
- Default to the `claude` executable on `PATH`, while allowing an explicit
  absolute executable path.
- Let the user select or accept defaults for the Frontend and Review models.
- Require explicit authorization before granting Claude Frontend edit
  permission. Never use `--dangerously-skip-permissions` or
  `bypassPermissions`.
- Restrict Claude Review to the review worktree and audit-record paths. It may
  run read-oriented inspection and tests but may not edit the feature branch.
- Init must not install Claude Code, start an authentication flow, read API
  keys, or persist authentication material.
- Repeated Init must reuse the same recorded task/session IDs when repository,
  models, policies, and roles match; conflicting Init must stop with recovery
  instructions.

### Frontend ownership and integration requirements

- The accepted plan must classify frontend-owned path prefixes and frontend
  acceptance criteria. An empty classification means no frontend dispatch.
- A FrontendWorkRequest must bind the branch name, starting head SHA, allowed
  path prefixes, plan snapshot, objective, acceptance criteria, and requested
  verification commands.
- Before dispatch the repository must be clean and the requested starting head
  must be current and pushed.
- After dispatch, verify the actual Git diff from start to end. Reject unclean
  state, history rewrites, changes outside allowed paths, missing commits, or
  an end head not reachable from the start head.
- Main remains responsible for whole-repository integration tests and may send
  a new frontend remediation request; it must not silently repair Claude-owned
  files.

### Review, merge, and release requirements

- Plan review must bind the requirements, design, and implementation-plan
  commit/digests.
- Code review must bind the canonical PR URL, repository, base SHA, head SHA,
  changed-file set, and required-check policy.
- Claude Review must write Markdown and compact JSON evidence on deterministic
  `codex/review-records/...` branches. Review branches may contain only audit
  artifacts on top of the reviewed snapshot.
- `review-only` returns READY without merging. `merge-on-approve` permits
  Engineering Main—not Claude—to perform the configured merge method only
  after independently refreshing the live PR head, draft status, checks, and
  mergeability.
- Release always requires a fresh, exact proposal and explicit user
  authorization. Claude sessions receive no release credentials or publishing
  authority.

### Failure and recovery requirements

- Missing executable, unauthenticated Claude, unsupported CLI flags, non-zero
  exit, timeout, malformed JSON, schema mismatch, session mismatch, or request
  digest mismatch must produce a typed non-authorizing failure.
- If transport outcome is unknown, mark the dispatch `UNKNOWN`; do not blindly
  replay work. Resume the same session with a recovery query for the same
  message ID, then accept only a matching structured result.
- Preserve state and review records on failure. Provide status and recovery
  commands; never instruct users to delete state as the first recovery step.
- A blocked Frontend session must not consume the Review identity, and a
  blocked Review session must not grant merge authority.

### Non-goals

- Supporting Claude Desktop UI automation, browser tab automation, or arbitrary
  chat products in v0.1.
- Installing or authenticating Claude Code.
- Running Codex and Claude mutations concurrently in one worktree.
- Sharing a generic cross-vendor protocol with future plugins.
- Replacing GitHub as the canonical repository/PR/merge authority.
- Allowing Claude Review to self-review work produced by the same Claude
  session.

### Acceptance criteria

- A fake Claude executable proves bootstrap, resume, structured frontend
  execution, structured plan/code review, idempotent retry, unknown-outcome
  recovery, and fail-closed malformed output without network access.
- Contract fixtures cover valid and invalid frontend and Claude result
  messages.
- Tests prove role IDs are distinct, frontend path escape is rejected, stale
  snapshots cannot authorize review or merge, and review sessions cannot be
  configured as frontend sessions.
- Plugin and every packaged skill pass the official validators.
- Documentation includes install, Init, Claude prerequisite, status, recovery,
  update, and uninstall instructions.
- A real Claude smoke remains explicitly pending on machines where the CLI is
  absent; automated validation must not pretend the stub is real external
  proof.
