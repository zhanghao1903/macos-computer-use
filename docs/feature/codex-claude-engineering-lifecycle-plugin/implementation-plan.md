# Implementation Plan: Codex-Claude Engineering Lifecycle Plugin

- Feature directory:
  `docs/feature/codex-claude-engineering-lifecycle-plugin/`
- Branch: `codex/claude-hybrid-engineering-lifecycle-plugin`
- Design: `design.md`
- Current phase: F3

## Scope

### In scope

- One sibling `codex-claude-engineering-lifecycle` plugin.
- Two Codex tasks: Requirements and Engineering Main.
- Two persistent Claude Code sessions: Frontend and Review.
- Claude CLI probe/bootstrap/resume bridge with strict state and result
  contracts.
- Frontend Git/path verification, unknown-outcome recovery, and audit proof.
- Existing GoalRun, review snapshot, merge, release, and closure state machine.
- Repo marketplace registration, install/update/uninstall/recovery docs, tests,
  and Unreleased changelog entry.

### Out of scope

- Claude Desktop UI automation.
- Shared provider protocol or support for additional model vendors.
- Automatic installation/authentication or credential storage.
- Importing existing Codex-only workflow state.
- Python package/API/version changes.
- Publishing the plugin to `my-skills` in this implementation branch.

## Implementation slices

| Slice | Files/modules | Behavior | Tests | Docs | Rollback |
| --- | --- | --- | --- | --- | --- |
| 1. Scaffold | `plugins/codex-claude-engineering-lifecycle/.codex-plugin/plugin.json`, `assets/`, repo marketplace | Create valid independent plugin identity and marketplace entry | Plugin validator; manifest/path tests | Root/plugin README skeleton | Remove only new entry/directory |
| 2. Lifecycle core | copied `scripts/workflowctl.py`, existing schemas/fixtures/tests | Preserve lifecycle state while changing state root and Review endpoint documentation | Full copied workflow and contract suite | Design implementation note | Delete sibling copy; source plugin unchanged |
| 3. Bridge contracts | five new schemas, positive/negative fixtures | Define bootstrap, frontend request/result, plan review, and code review outputs | JSON Schema parity and unknown-field tests | Contract table cross-check | Remove additive schemas |
| 4. Claude bridge runtime | `scripts/claudectl.py` | Probe/auth, recoverable Init, session UUIDs, safe argv, lock/atomic state, dispatch/recovery ledger | Focused unit and fake-executable integration tests | Status/recovery reference | Stop dispatch; state remains readable |
| 5. Git authority | bridge Git helpers and tests | Verify clean/pushed exact start, ancestry, end head, commit/path equality, allowed prefixes | Temporary Git repository tests for pass/stale/dirty/path escape/rewrite | Frontend ownership reference | Block feature; never auto-reset |
| 6. Role skills | `hybrid-workflow-init`, `hybrid-requirements`, `hybrid-main` plus metadata/references | Orchestrate two Codex tasks and two Claude sessions through full lifecycle | Skill contract tests and official quick validation | Role lifecycle/recovery references | Uninstall new plugin |
| 7. Claude prompts | `prompts/claude-frontend.md`, `prompts/claude-review.md` | Enforce role identity, untrusted-data boundary, exact request/digest, concise structured output | Prompt invariant tests | Privacy disclosure | Replace prompts without state migration |
| 8. Distribution/docs | plugin README, privacy/support/terms/changelog, root CHANGELOG, marketplace | Install, prerequisite, Init, status, recovery, update, uninstall, external-data boundary | Link/path/no-placeholder/secret scans | User-facing complete docs | Revert distribution commit |
| 9. Verification | feature verification and implementation notes | Record commands, results, deferred real Claude proof, compatibility evidence | Full plugin suite, validator, skill validators, diff/secret scans | F4/F5 records | No runtime rollback needed |

## Exact implementation surfaces

### New plugin root

```text
plugins/codex-claude-engineering-lifecycle/
```

Create it with the official plugin scaffold. Reuse copied assets, lifecycle
schemas, workflow runtime, fixtures, and composition skills from
`plugins/codex-engineering-lifecycle/`; then edit only the sibling copy.

### New role skills

Initialize each new skill with the official skill initializer before replacing
the generated content:

- `hybrid-workflow-init`
  - explicit-only;
  - creates/binds Requirements and Main Codex tasks;
  - creates/binds Frontend and Review Claude UUIDs;
  - probes Claude and bootstraps all roles;
  - owns status and recovery.
- `hybrid-requirements`
  - implicit;
  - retains confirmed-requirements behavior;
  - routes only to configured Main Codex task.
- `hybrid-main`
  - implicit;
  - owns plan, backend/integration Goal work, Claude dispatch, review-record
    persistence, merge mechanics, release, and closure;
  - forbids direct frontend edits absent explicit takeover.

No Codex Review role skill is created. Claude Review behavior lives in a
versioned prompt loaded on every resume.

### Composition skills

Package exact explicit-only copies of:

- `feature-lifecycle`
- `product-workflow-gate`
- `technical-plan-write`
- `technical-plan-review`
- `pr-review`

Their skill names stay unchanged inside the plugin namespace. Tests must prove
their resources match the source skills and implicit invocation remains false.

### `workflowctl.py`

- Change module/product wording to the hybrid plugin.
- Change the local project state namespace to
  `codex-claude-engineering-lifecycle`.
- Preserve routed schema version and state schema version.
- Preserve existing command behavior and all regression tests.
- Treat configured Review ID as a transport endpoint UUID; update errors/docs
  where practical without a broad internal rename.
- Do not add Claude subprocess behavior to this file.

### `claudectl.py`

Implement with standard-library Python only:

- repository identity and project-root derivation compatible with
  `workflowctl.py`;
- `WorkflowError`-style sanitized JSON errors and deterministic exit codes;
- canonical JSON/SHA-256 helpers;
- strict object/key/type/path/UUID/SHA/digest validation;
- advisory file lock with stale-lock recovery rules matching the lifecycle
  runtime;
- mode `0700` directories, mode `0600` files, atomic fsync/replace writes;
- commands:
  - `probe`
  - `begin-init`
  - `init`
  - `status`
  - `bootstrap`
  - `dispatch`
  - `recover`
  - `verify-frontend`
- no shell execution, no credential reads, no raw transcript persistence;
- subprocess timeout and output-size caps;
- exact wrapper/session/structured-output validation;
- message ledger state machine from the design;
- Git verification implemented with fixed argv calls;
- result paths confined to the exact project `messages/` directory.

### Schemas

Add strict draft-2020-12 schemas:

- `claude-bootstrap-output.schema.json`
- `frontend-work-request.schema.json`
- `claude-frontend-output.schema.json`
- `claude-plan-review-output.schema.json`
- `claude-code-review-output.schema.json`

Use `additionalProperties: false`, bounded arrays/strings, lowercase SHA/digest
patterns, safe repository-relative path patterns, and explicit enums. Avoid
unsupported structured-output schema features; keep response schemas shallow.

### Fake Claude executable

Add a test-only executable fixture that:

- parses the supported argv subset;
- records sanitized argv and prompt metadata in a temporary test directory;
- returns a JSON result wrapper with configured `session_id` and
  `structured_output`;
- can simulate missing auth, non-zero exit, timeout, malformed JSON, wrong
  session, invalid structured output, and recovery;
- never uses network access.

It is automated proof of bridge behavior, not evidence that real Claude is
installed or authenticated.

## Implementation ordering

1. Scaffold plugin and three skills.
2. Copy lifecycle core and composition resources.
3. Make plugin identity/state-root changes; restore copied regression tests.
4. Add bridge schemas and fixtures.
5. Implement bridge state/probe/Init.
6. Add dispatch/recovery and fake-Claude tests.
7. Add frontend Git verification and temporary-repository tests.
8. Write role skills, prompts, and runtime references.
9. Complete plugin and repository documentation.
10. Run focused tests, then full gates.
11. Record F4/F5/F6 evidence in separate commits.

## Test matrix

### Bridge unit tests

- canonical request and schema digest stability;
- executable resolution rejects relative path tricks and non-executables;
- repository identity/state paths do not collide with the Codex-only plugin;
- four role IDs are pairwise distinct;
- invalid model, permission mode, budget, turn, timeout, path, UUID, SHA, and
  digest values fail closed;
- locks serialize one Claude session and stale lock recovery does not permit
  concurrent resume;
- atomic writes retain last valid state after injected failure.

### Fake-Claude integration

- probe success/auth failure;
- bootstrap creates exact configured UUID and role;
- dispatch uses `--resume`, never `--continue`;
- Frontend and Review select separate model/permission/schema/prompt files;
- argv contains no shell wrapper or dangerous permission flag;
- output wrapper session and request digest must match;
- identical completed retry returns saved result without a second invocation;
- conflicting message ID is rejected;
- timeout, non-zero exit, malformed JSON, wrong session, and invalid schema
  become UNKNOWN;
- recovery addresses the same UUID/message and accepts only a matching result;
- simultaneous dispatch to one session is rejected.

### Git integration

- clean exact pushed start and in-prefix commits pass;
- dirty pre-dispatch state fails;
- stale branch/head and unpushed start fail;
- end head must descend from start and equal current HEAD;
- changed path outside a prefix fails;
- returned paths/commits must equal derived Git sets;
- empty COMPLETED change, merge to another branch, and history rewrite fail;
- verification never invokes reset, checkout restore, clean, or deletion.

### Lifecycle regression

- copied 28-test suite remains green after state-root/wording changes;
- Review UUID passes role routing and remains distinct from Codex task IDs;
- plan/code request/result, GoalRun, merge, release, retry, migration, and
  closure invariants remain unchanged;
- all existing 16 lifecycle fixtures preserve parity.

### Skill/plugin/distribution

- official plugin validator;
- official skill validator for all role and composition skills;
- manifest assets and marketplace source paths exist;
- only role skills intended for direct work allow implicit invocation;
- prompts contain role/authority/untrusted-data prohibitions;
- README commands use the new plugin/skill/marketplace names;
- secret scan and generated-artifact scan have no findings;
- `git diff --check`.

## Verification commands

```bash
python3 -m unittest discover \
  -s plugins/codex-claude-engineering-lifecycle/tests \
  -p 'test_*.py'

python3 plugins/codex-claude-engineering-lifecycle/scripts/validate_contracts.py \
  --require-jsonschema

python3 /Users/zhanghao/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-claude-engineering-lifecycle

find plugins/codex-claude-engineering-lifecycle/skills \
  -mindepth 1 -maxdepth 1 -type d \
  -exec python3 /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/quick_validate.py '{}' \;

git diff --check
```

Use an isolated environment with `pyyaml` and `jsonschema` for strict gates.
Run the original `codex-engineering-lifecycle` suite as a non-regression check
because the new plugin must not modify it.

## Documentation updates

- New plugin `README.md`: prerequisites, install, Init choices, four roles,
  lifecycle, status/recovery, update, uninstall, privacy.
- New plugin `PRIVACY.md`: Anthropic external processing boundary and retained
  structured result/state.
- New plugin `SUPPORT.md` and `TERMS.md`: safe diagnostic/reporting boundary.
- New plugin `CHANGELOG.md`: v0.1.0 initial capability.
- Root `CHANGELOG.md`: Unreleased/Added entry.
- Repo marketplace: append new plugin entry; preserve existing entry and order.
- Feature docs: implementation notes, verification, and PR description.

## Rollout and rollback

- Rollout from the feature ref into a disposable GitHub repository first.
- Require a new Codex task after plugin installation.
- Init must complete real Claude probe/bootstrap before feature intake.
- Do not claim real cross-application smoke on this development machine because
  `claude` is absent.
- On runtime failure, stop dispatch and preserve bridge/workflow state.
- Uninstall removes only discovery; tasks, Claude sessions, state, branches,
  review records, PRs, releases, and packages remain.
- Rollback to the Codex-only plugin requires a new workflow Init; no state
  conversion is implied.

## Compatibility

- Additive sibling plugin; no existing package or plugin behavior changes.
- No routed schema migration for the copied lifecycle core.
- New bridge state begins at schema version 1.
- State roots are disjoint, so downgrade/uninstall cannot corrupt the old
  plugin.

## Open decisions

No implementation-blocking decision remains. Real Claude smoke and eventual
publication to `my-skills` require a later environment/user action.
