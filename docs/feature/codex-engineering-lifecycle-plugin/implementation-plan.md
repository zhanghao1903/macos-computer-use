# Implementation Plan: Codex Engineering Lifecycle Plugin

- Feature directory: `docs/feature/codex-engineering-lifecycle-plugin/`
- Branch: `codex/engineering-lifecycle-plugin`
- Requirements: [requirements.md](requirements.md)
- Design: [design.md](design.md)
- Current phase: F5

## Scope

### In scope

- A new repo-marketplace plugin named `codex-engineering-lifecycle`.
- Four new role/orchestration skills: Init, Requirements, Main, and Review.
- Packaged copies of the five existing repository engineering skills.
- Deterministic workflow config, state, contract validation, message replay
  protection, Goal queueing, release authorization, and closure.
- User, policy, support, installation, update, uninstall, and recovery docs.
- Automated unit, schema, plugin, skill-contract, and integration tests.
- Independent technical-plan review, code review, and forward-test evidence.

### Out of scope

- Changes to Python package code, versions, dependencies, or public APIs.
- Cross-application routing and non-GitHub forges.
- Automatic release publication without per-release authorization.
- Migrating or replacing the lightweight plugin.
- Publishing a production release before merge approval and external proof.

## Implementation slices

| Slice | Files/modules | Behavior | Tests | Docs | Rollback |
| --- | --- | --- | --- | --- | --- |
| 1. Scaffold | `plugins/codex-engineering-lifecycle/`, `.agents/plugins/marketplace.json` | Valid plugin manifest, repo marketplace entry, assets/resources directories | Plugin validator and JSON parsing | Manifest metadata | Remove new plugin and marketplace entry |
| 2. Role skills | Four `skills/engineering-*` directories | Init and three role boundaries, task bootstrap, handoff procedures | Quick validator, cross-skill assertions | Skill references for lifecycle and recovery | Remove role skills; no state migration |
| 3. Source skill packaging | Five copied skill directories | Preserve repository skill instructions/resources; add explicit-only packaged metadata overlay | Source/copy parity with one allowed policy difference, quick validators, pr-review validator tests | Plugin README composition table | Regenerate copies and overlay from source |
| 4. Contracts | `schemas/*.schema.json`, `scripts/validate_contracts.py`, fixtures | Exact-key versioned routed contracts and release/closure authority | Positive/negative schema and runtime parity | Contract reference | Reject unsupported schema; remove plugin |
| 5. State runtime | `scripts/workflowctl.py` | Config/state persistence, transitions, deterministic IDs, artifact proof, Goal queue, review/release/closure guards | Unit and temporary-Git integration tests | Runtime/recovery reference | State remains intact; reinstall prior plugin version |
| 6. User docs and policy | README, CHANGELOG, LICENSE, PRIVACY, TERMS, SUPPORT | Install/update/uninstall/Init/recovery/data cleanup and safety boundaries | Link/path/manifest checks | User-facing plugin docs | Docs-only revert |
| 7. Repository lifecycle record | Feature docs, root `CHANGELOG.md`, PR materials | Verification, review, release readiness, traceability | Diff/secret/artifact scans, release preflight | F4–F8 records | Revert feature branch before merge |

## Slice 1 — scaffold and marketplace

Run the canonical plugin scaffold from the system `plugin-creator` skill:

```bash
python3 /Users/zhanghao/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py \
  codex-engineering-lifecycle \
  --path /private/tmp/macos-computer-use-engineering-lifecycle/plugins \
  --marketplace-path /private/tmp/macos-computer-use-engineering-lifecycle/.agents/plugins/marketplace.json \
  --marketplace-name macos-computer-use \
  --with-skills \
  --with-scripts \
  --with-assets \
  --with-marketplace
```

Then update `.codex-plugin/plugin.json` to version `0.1.0`, GitHub URLs,
Productivity metadata, at most three starter prompts, and real SVG asset paths.
The repository marketplace entry remains `AVAILABLE` with `ON_INSTALL`
authentication.

## Slice 2 — role and orchestration skills

Initialize each new skill with the canonical `skill-creator` helper before
customization:

```text
engineering-workflow-init
engineering-requirements
engineering-main
engineering-review
```

Each receives a generated `agents/openai.yaml` whose default prompt explicitly
mentions the skill name. Add only required `references/` or `assets/`.

### Init responsibilities

- Resolve a trusted GitHub checkout and canonical repository identity.
- Discover task-management, Goal, and GitHub capabilities.
- Explain Goal, merge, review-record, release, and cleanup policies.
- Obtain explicit Goal-mode and merge-policy choices.
- Call `begin-init`, create or bind exactly three pinned tasks, and call
  `record-init-task` immediately after each returned ID.
- Resume interrupted Init from the pending ledger, then call final `init`.
- Send role bootstrap messages and require acknowledgements.
- Report config/state location and recovery command.

### Requirements responsibilities

- Own natural-language intake and requirements revisions.
- Write the tracked requirements document and expose confirmation metadata.
- Wait for explicit user confirmation.
- Commit and push the immutable snapshot; require its deterministic branch/path
  and exact authoritative remote branch tip.
- Call `prepare-requirements`, deliver it to Main, and record delivery.
- Refuse design, implementation, review, merge, release, and closure work.

### Main responsibilities

- Validate and accept the requirements handoff before doing work.
- Load `feature-lifecycle`, `product-workflow-gate`, and
  `technical-plan-write`.
- Write and push design and implementation plan.
- Dispatch plan review and remediate failed review results.
- On exact PASS, notify the user, obtain the Goal slot, and call `create_goal`.
- Persist immutable GoalRun state, continue until genuine completion, and
  prepare the PR.
- Dispatch exact-head code review; remediate findings in a new
  `CODE_REMEDIATION` GoalRun because a completed Goal is never reopened.
- Accept merge proof, prepare an exact release proposal, require per-release
  authorization, publish, record proof, and close.
- Never approve its own plan or code.

### Review responsibilities

- Validate and accept only routed plan/code requests.
- Load `technical-plan-review` for plan requests and `pr-review` for code.
- Create a fresh immutable review-record branch per request.
- On delivery retry, reuse only the exact state-recorded branch/report proof;
  reject an existing wrong-base, unexpected-tip, or unrecorded branch and
  never force-push.
- Produce Markdown and JSON report proof and push only that branch.
- Never edit the feature branch.
- Merge only an approved exact head with green checks and matching policy.
- Return deterministic results and merge proof to Main.

## Slice 3 — package source skills

Copy these source directories mechanically into the plugin:

```text
.agents/skills/feature-lifecycle
.agents/skills/product-workflow-gate
.agents/skills/technical-plan-write
.agents/skills/technical-plan-review
.agents/skills/pr-review
```

Include every runtime resource referenced by `SKILL.md`:

- `agents/openai.yaml`;
- `references/`;
- `scripts/`;
- `schemas/`;
- `templates/`;
- examples required for procedure understanding.

Do not package the source skill's own unit tests inside the runtime skill
directory. Copy the pr-review validator tests into the plugin test suite where
they can run without becoming skill runtime content.

Keep every packaged `SKILL.md` and runtime resource byte-identical to source.
Apply one intentional semantic overlay to each packaged
`agents/openai.yaml`:

```yaml
policy:
  allow_implicit_invocation: false
```

Add a parity test that hashes all unchanged files, parses source and packaged
agent metadata, and proves the only semantic difference is the explicit-only
policy. Role wrappers remain implicitly invocable and call composition skills
explicitly.

## Slice 4 — schemas and contract validation

Create strict Draft 2020-12 schemas:

```text
requirements-handoff.schema.json
technical-plan-review-request.schema.json
technical-plan-review-result.schema.json
code-review-request.schema.json
code-review-result.schema.json
release-authorization.schema.json
release-result.schema.json
closure-record.schema.json
```

Use:

- `additionalProperties: false` for every authority-bearing object;
- strict lowercase SHA/digest patterns;
- canonical repo-relative paths;
- bounded text and arrays;
- strict RFC3339 UTC `Z` timestamps;
- enumerated stages, decisions, check states, merge states, and release modes;
- conditional requirements for PASS/FAIL, APPROVE/CHANGES, MERGED/FAILED,
  typed `GITHUB_RELEASE`/`PYPI` targets, per-target PUBLISHED/FAILED evidence,
  and all-target release success.

`validate_contracts.py` validates one file or all fixtures. It must:

- fail closed when `--require-jsonschema` is used but the dependency is absent;
- report the schema engine and one sanitized failure per fixture;
- compare expected validity declared by the fixture filename;
- exit nonzero on any mismatch.

`workflowctl.py` owns an independent exact-key runtime validator. Contract tests
must prove schema/runtime parity for all fixtures.

## Slice 5 — deterministic state runtime

Implement `workflowctl.py` with standard-library runtime dependencies. It makes
no direct HTTP calls; `prepare-requirements` uses read-only `git ls-remote` to
prove the already-pushed authoritative branch tip.

### Commands

```text
begin-init
record-init-task
init
status
ack-bootstrap
prepare-requirements
mark-dispatched
mark-delivery-failed
accept-requirements
prepare-plan-review
accept-plan-review
prepare-plan-result
apply-plan-result
start-development
block-development
resume-development
complete-development
prepare-code-review
accept-code-review
prepare-code-result
apply-code-result
record-release-authorization
record-release-result
close-feature
```

All mutating commands:

1. resolve canonical repository and state root;
2. acquire the project lock;
3. validate full config and state;
4. validate command input and referenced Git artifacts;
5. check the exact current transition;
6. apply an idempotent mutation;
7. atomically persist and return JSON.

### Internal modules/functions

The first version stays in one script to keep plugin installation simple, but
organizes helpers by section:

- canonical repository and path validation;
- timestamps, SHA/digest, semver, URL, and exact-key validators;
- JSON loading, locking, atomic writes, and sanitized errors;
- config/state/object validators;
- routed contract validators and deterministic ID builders;
- artifact snapshot verification through `git show`;
- state-transition commands;
- CLI parser and stable JSON output.

Split the script only if it exceeds the repository's maintainability threshold
or tests show a clear module boundary. A future split must not change the CLI.

### State invariants

- Config and state workflow IDs match.
- Pending Init persists before task creation, records each task exactly once,
  and repairs the config-only crash window without changing workflow identity.
- Missing Goal-mode authorization is rejected before state-root/lock/pending
  persistence.
- Task IDs are pairwise distinct.
- Every feature map key equals `featureId`.
- Every feature stage has exactly the artifacts required by that stage.
- `developmentQueue` contains unique approved/remediation feature entries.
- `activeGoal` is null or identifies the only ACTIVE/BLOCKED GoalRun occupying
  the global slot.
- GoalRun IDs are deterministic; completed runs are immutable; remediation
  uses a new run bound to the requesting code-review result; identical prepare
  and activate replays preserve the existing run/timestamps.
- Result cycles and request IDs match the latest pending request.
- Merge proof matches the reviewed PR head and configured policy.
- Release proof matches the exact authorization, merge commit, and typed target
  set; a successful replay must equal the last accepted submission or the
  complete cumulative result.
- Ordered release submission history starts with all targets, retries exactly
  the preceding failed set, has unique target/digest entries, reconstructs the
  cumulative result, and binds `lastSubmission` to its final entry.
- Every state load re-normalizes release authorization/result identity,
  destinations, targets, and artifact evidence.
- Future-stage merge, release, and closure proof is rejected when the declared
  stage is earlier than that proof.
- Closure references a release result where every authorized target is
  PUBLISHED.
- Duplicate IDs have identical canonical payloads.

## Slice 6 — user documentation and policy

Create plugin-level files:

- `README.md`: overview, prerequisites, GitHub installation, update, uninstall,
  Init, normal lifecycle, task roles, manual release, troubleshooting, state,
  cleanup, and safety.
- `CHANGELOG.md`: `0.1.0` feature summary.
- `SUPPORT.md`: issue template data and non-secret diagnostics.
- `PRIVACY.md`: exact local state and excluded data.
- `TERMS.md`: user responsibility and external-action boundaries.
- `LICENSE`: repository-compatible MIT text.

Create role references:

- Init setup/recovery;
- requirements confirmation/handoff;
- Main lifecycle/Goal/release;
- Review request/result and review-record branches.

No skill directory receives a README or changelog.

## Slice 7 — repository lifecycle records

Update:

- `docs/feature/codex-engineering-lifecycle-plugin/implementation-notes.md`;
- `verification.md`;
- `technical-review-*.md`;
- `merge-readiness.md`;
- `pr-description.md`;
- `release-readiness.md`;
- post-release summary when publication occurs;
- root `CHANGELOG.md` under `Unreleased / Added`.

## Verification matrix

### Focused automated checks

```bash
python -m unittest discover \
  -s plugins/codex-engineering-lifecycle/tests \
  -p 'test_*.py'

python plugins/codex-engineering-lifecycle/scripts/validate_contracts.py \
  --fixtures plugins/codex-engineering-lifecycle/tests/fixtures \
  --require-jsonschema
```

Run the plugin validator:

```bash
python3 /Users/zhanghao/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-engineering-lifecycle
```

Run the canonical skill validator for all nine skills:

```bash
python3 /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  <skill-directory>
```

### Repository checks

```bash
python scripts/release_preflight.py
git diff --check
```

Also run:

- JSON parsing for every manifest/schema/fixture;
- YAML parsing for all `agents/openai.yaml`;
- XML parsing for SVG assets;
- secret-pattern scan;
- generated artifact and cache scan;
- source/packaged skill parity with only the explicit-only metadata overlay;
- clean-worktree check before review.

### Manual forward-test

Use fresh, isolated subagents only after the plugin is complete:

1. invoke Init against a disposable local GitHub-shaped fixture;
2. send a feature request to Requirements and inspect the confirmed handoff;
3. feed a plan request to Review and inspect PASS/FAIL evidence;
4. simulate initial and code-remediation GoalRun authorization and queue
   behavior in Main;
5. feed a PR review request to Review and inspect exact-head behavior;
6. verify typed multi-target release authorization, partial failure, and
   pre-release closure rejection;
7. verify an identical review-record retry reuses proof and a conflicting
   existing branch fails closed.

Forward-tests must not push, merge, publish, or modify production repositories.

## Rollout

1. Land the plugin and repo marketplace entry on the feature branch.
2. Validate locally.
3. Install the repo marketplace in a disposable Codex environment.
4. Reinstall the plugin and start a new task.
5. Run manual Init proof in a disposable repository.
6. Merge only after independent plan/code review.
7. Publish version `0.1.0` only with explicit user approval and release proof.

## Rollback and downgrade

- Before merge: delete/revert the feature branch only.
- After merge but before install: remove the marketplace entry and plugin
  directory in a normal revert PR.
- After install: uninstall the plugin. Preserve state/tasks for diagnosis.
- After initialization: archive tasks and delete only the exact derived state
  directory after explicit confirmation.
- Never auto-delete Git branches, PRs, review records, tags, releases, or state.
- Schema v1 has no downgrade migration; an older plugin must refuse newer state.

## Compatibility

- No Python package API or dependency change.
- No state, task-title, or namespace overlap with the lightweight plugin.
- GitHub and Codex Desktop task/Goal capabilities are required.
- Plugin runtime supports Python 3 and does not require `jsonschema`; strict
  schema validation in development/CI does require it.

## Open decisions

No blocking decision remains. If implementation exposes a platform limitation
in Goal creation, task pinning, or task messaging, stop and revise the design
instead of weakening the workflow silently.
