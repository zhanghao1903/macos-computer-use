# Implementation Plan: Codex Feature Lifecycle Plugin

- Feature directory: `docs/feature/codex-feature-lifecycle-plugin/`
- Plugin directory: `plugins/codex-feature-lifecycle/`
- Branch: `codex/codex-feature-lifecycle-plugin`
- Design document: [design.md](design.md)
- Current phase: F3 implementation planning

## Scope

### In Scope

- A skills-only Codex plugin for Codex Desktop and GitHub.
- Explicit idempotent initialization of two long-lived Codex tasks.
- Main-work lifecycle guidance from intake through post-merge traceability.
- Independent PR review, re-review, merge gates, and result delivery.
- User-local configuration and atomic dispatch state.
- Versioned ReviewRequest and ReviewResult schemas.
- Repository marketplace entry, plugin metadata, icon, tests, install proof,
  usage documentation, changelog, and merge-readiness artifacts.

### Out Of Scope

- Claude or other external applications.
- Provider abstraction or a shared cross-application protocol.
- Non-GitHub merge requests.
- MCP servers, background daemons, or hosted state.
- Package API/version changes.
- Automatic release publication.

## Implementation Slices

| Slice | Files/modules | Behavior | Tests | Docs | Rollback |
| --- | --- | --- | --- | --- | --- |
| 1. Contracts and state | `schemas/*.json`, `scripts/workflowctl.py`, `scripts/validate_contracts.py` | Resolve repo identity, persist config/state, validate payloads, enforce dispatch transitions and idempotency. | Unit and contract tests for positive/negative schemas, permissions, atomic writes, duplicates, stale results, and locks. | Update design only if implementation requires a contract correction. | Remove scripts/schemas; no external state is created by tests. |
| 2. Init skill | `skills/codex-workflow-init/**` | Capability preflight, existing-config reuse, explicit merge authorization, create/bind/title/pin/wait for two tasks, persist only after readiness. | Skill validation and static scenario assertions. | Usage and troubleshooting sections. | Disable/remove skill; existing tasks/config remain user-owned. |
| 3. Main skill | `skills/codex-feature-main/**` | F0-F8 main responsibility, PR readiness gate, exact-head dispatch, finding remediation, result acceptance, traceability. | Skill validation and handoff fixture scenarios. | Lifecycle phase reference and user guide. | Revert skill; repository feature artifacts remain. |
| 4. Reviewer skill | `skills/codex-pr-review-merge/**` | Validate immutable request, risk-based review, stale-head refusal, re-review, deterministic merge gate, result delivery. | Skill validation, negative merge scenarios, structured finding fixtures. | Review contract and safety guide. | Revert skill; no branch edits are performed by reviewer. |
| 5. Package and marketplace | Manifest, icon, `.agents/plugins/marketplace.json` | Accurate install metadata and repo-local discovery. | Plugin validator, JSON validation, marketplace install in temporary Codex home. | Installation/update/uninstall instructions. | Remove marketplace entry and plugin directory. |
| 6. Verification and release record | Plugin tests, `verification.md`, `merge-readiness.md`, `CHANGELOG.md` | Record automated evidence, skipped live proof, limitations, and PR-ready summary. | Full plugin test suite, validators, clean-install/cache inspection, non-mutating forward tests. | Verification, PR description, release note. | Revert documentation-only record if implementation is rolled back. |

## Detailed File Plan

### Plugin Manifest And Marketplace

- `plugins/codex-feature-lifecycle/.codex-plugin/plugin.json`
  - add author contact, repository, homepage, license, keywords;
  - replace the scaffold prompt with at most three short starter prompts;
  - declare the implemented Interactive/Write capabilities;
  - reference only assets that exist.
- `.agents/plugins/marketplace.json`
  - create a repo marketplace catalog;
  - point `codex-feature-lifecycle` at
    `./plugins/codex-feature-lifecycle`;
  - use `AVAILABLE`, `ON_INSTALL`, and `Productivity`.
- `plugins/codex-feature-lifecycle/assets/codex-feature-lifecycle.svg`
  - provide a simple source-controlled vector mark suitable for the plugin UI.

### Runtime Contracts

- `plugins/codex-feature-lifecycle/schemas/review-request.schema.json`
  - JSON Schema Draft 2020-12;
  - closed objects with explicit required fields;
  - SHA, dispatch ID, URL, UUID, decision, and enum constraints.
- `plugins/codex-feature-lifecycle/schemas/review-result.schema.json`
  - closed result/finding/merge objects;
  - stable finding ID and severity constraints;
  - decision-to-merge semantic checks implemented by `workflowctl.py` where
    JSON Schema alone cannot express them.
- `plugins/codex-feature-lifecycle/scripts/validate_contracts.py`
  - validate schemas and fixtures using the available `jsonschema` library when
    present;
  - provide a dependency-free structural fallback for runtime payload checks;
  - emit machine-readable validation results.

### Workflow State

- `plugins/codex-feature-lifecycle/scripts/workflowctl.py`
  - use only Python standard-library modules at runtime;
  - implement `locate`, `init`, `show`, `validate`, `prepare-review`,
    `mark-dispatched`, `mark-delivery-failed`, `accept-review`,
    `prepare-result`, and `accept-result`;
  - sanitize remotes before storage;
  - use deterministic repo and dispatch keys;
  - use owner-only directories/files and atomic replacement;
  - serialize writes with a bounded lock file;
  - never persist source, diffs, prompts, findings, tokens, or credentials;
  - return JSON on stdout and safe diagnostics on stderr.

### Init Skill

- `skills/codex-workflow-init/SKILL.md`
  - explicit-only trigger;
  - resolve and validate current git repository;
  - check all required Codex task capabilities and a GitHub surface;
  - inspect existing config before mutation;
  - obtain explicit merge policy and method;
  - use exact project matching;
  - create or bind, title, pin, and wait for both tasks;
  - persist final routes only after readiness;
  - report config path, workflow ID, tasks, policy, and recovery.
- `skills/codex-workflow-init/agents/openai.yaml`
  - set accurate UI text and `allow_implicit_invocation: false`.

### Main Skill

- `skills/codex-feature-main/SKILL.md`
  - describe the main role and F0-F8 ownership;
  - load repository-specific `AGENTS.md` and local skills/gates;
  - require feature branch and phase documentation/commit/push discipline;
  - define PR readiness and immutable head gates;
  - use `workflowctl.py` before and after task message delivery;
  - accept only a validated ReviewResult from the configured reviewer;
  - loop on findings and new head; finish traceability on merge.
- `skills/codex-feature-main/references/lifecycle-phases.md`
  - move detailed phase checklists out of SKILL.md.
- `skills/codex-feature-main/agents/openai.yaml`
  - allow implicit invocation for feature requests.

### Reviewer Skill

- `skills/codex-pr-review-merge/SKILL.md`
  - explicit invocation from ReviewRequest messages;
  - validate route and state before inspecting the PR;
  - fix base/head snapshot and review risk-first;
  - preserve stable finding IDs in re-review;
  - never edit/fix feature code;
  - enforce exact-head, checks, authorization, and merge-method gates;
  - prepare, persist, and deliver ReviewResult.
- `skills/codex-pr-review-merge/references/review-contract.md`
  - finding quality, decisions, re-review, merge, and report requirements.
- `skills/codex-pr-review-merge/agents/openai.yaml`
  - disable implicit invocation so ordinary review prompts do not accidentally
    enter the automated merge workflow.

### Tests And Fixtures

- `tests/test_workflowctl.py`
  - temporary Codex state roots;
  - repo/remote normalization;
  - config initialization, replacement, permissions, and validation;
  - dispatch preparation and transition matrix;
  - duplicate and stale input handling;
  - result semantic constraints;
  - lock acquisition and stale-lock recovery.
- `tests/test_contracts.py`
  - compile both schemas;
  - validate representative positive payloads;
  - reject malformed routes, SHA, UUID, finding, merge, and extra fields.
- `tests/fixtures/`
  - positive ReviewRequest and ReviewResult;
  - stale and request-changes results;
  - negative payloads for submission testing.
- `tests/test_skill_contracts.py`
  - assert required capability names, safety gates, message commands, and
    explicit invocation policies remain present.

## Task Bootstrap Prompts

Init generates bounded prompts rather than copying conversation history.

Main task prompt responsibilities:

- invoke `$codex-feature-main`;
- bind to the exact repository path;
- report `MAIN_READY` and remain idle;
- accept feature work only from the user or validated reviewer results.

Reviewer task prompt responsibilities:

- invoke `$codex-pr-review-merge`;
- bind to the exact repository path;
- report `REVIEW_READY` and remain idle;
- accept only validated ReviewRequest payloads;
- never edit the feature branch.

## Package Boundaries

- `app-control-protocol`: unchanged.
- `computer-use-macos`: unchanged.
- `wechat-desktop-tool`: unchanged.
- Repository `.agents/skills`: unchanged except the new marketplace catalog is
  stored alongside existing agent configuration under `.agents/plugins/`.
- Plugin runtime: self-contained under `plugins/codex-feature-lifecycle/`.

## Verification

### Automated Checks

```bash
python3 -m unittest discover \
  -s plugins/codex-feature-lifecycle/tests -p 'test_*.py'

python3 plugins/codex-feature-lifecycle/scripts/validate_contracts.py \
  --schemas plugins/codex-feature-lifecycle/schemas \
  --fixtures plugins/codex-feature-lifecycle/tests/fixtures

python3 /path/to/skill-creator/scripts/quick_validate.py \
  plugins/codex-feature-lifecycle/skills/codex-workflow-init
python3 /path/to/skill-creator/scripts/quick_validate.py \
  plugins/codex-feature-lifecycle/skills/codex-feature-main
python3 /path/to/skill-creator/scripts/quick_validate.py \
  plugins/codex-feature-lifecycle/skills/codex-pr-review-merge

python3 /path/to/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-feature-lifecycle

python3 -m json.tool .agents/plugins/marketplace.json
git diff --check
```

### Clean Installation Proof

Use a task-specific temporary Codex home and local marketplace snapshot so the
test does not alter the user's installed plugins:

1. create a temporary Codex state directory;
2. add the repository marketplace;
3. install `codex-feature-lifecycle`;
4. list installed plugins;
5. inspect the cached manifest, skills, scripts, schemas, and assets;
6. start no real tasks during this proof.

### Forward Tests

Use fresh non-root agents with the installed/raw plugin artifact and bounded
hypothetical scenarios:

- initialize when capabilities are missing;
- process a PR-ready main handoff without sending it;
- reject an unauthorized or stale merge;
- handle request changes and a new head.

Forward tests must not create Codex app tasks, mutate GitHub, or edit the
feature branch.

### Manual Smoke

A real Init creates user-owned Codex tasks, and an end-to-end merge mutates
GitHub. These actions require explicit user authorization at smoke time. Until
then, record them as external proof rather than silently performing them.

## Documentation Updates

- `docs/feature/codex-feature-lifecycle-plugin/implementation-notes.md`
- `docs/feature/codex-feature-lifecycle-plugin/verification.md`
- `docs/feature/codex-feature-lifecycle-plugin/merge-readiness.md`
- `docs/feature/codex-feature-lifecycle-plugin/pr-description.md`
- `docs/feature/README.md`
- `CHANGELOG.md`

The plugin skill/reference files themselves carry installation, operation,
authorization, local-data, troubleshooting, and uninstall guidance so those
instructions ship with the plugin.

## Rollout And Rollback

- Rollout: repository marketplace → temporary-home install → local opt-in
  install → public submission preparation.
- Rollback: uninstall or remove the plugin marketplace entry and revert plugin
  commits. Do not delete tasks or local config automatically.
- Compatibility: unsupported schema versions fail closed; v0.1.0 has no legacy
  state migration.

## Commit And Push Plan

- F3: this implementation plan only.
- F4: runtime schemas/scripts, skills, metadata, marketplace, tests, and
  implementation notes after implementation checks pass.
- F5: verification evidence and user/developer documentation.
- F6: merge readiness, PR description, final changelog wording, and review
  record.

Each commit stages only feature-scoped files and is pushed before the next
phase. Pre-existing untracked smoke files and package lock files remain
excluded.

## Open Decisions

No implementation-blocking decision remains. A real two-task/PR smoke and
public marketplace submission are external-state operations that require
separate explicit authorization; the plugin can be implemented and validated
without performing them.
