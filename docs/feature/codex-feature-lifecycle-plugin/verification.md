# Codex Feature Lifecycle Plugin Verification

- Updated: 2026-07-18
- Lifecycle phase: F5 Verification and Documentation
- Branch: `codex/codex-feature-lifecycle-plugin`
- Candidate version: `0.1.0`
- Baseline implementation commit: `836d6b4`
- Verification decision: automated and non-mutating acceptance passed

## Acceptance Summary

The plugin is discoverable from the repository marketplace, installs into an
isolated Codex home, exposes all three skills, and carries its scripts, schemas,
references, tests, and SVG asset without source/cache differences. Runtime and
schema validators agree on all positive and negative contract fixtures.

The validated workflow is deliberately Codex Desktop + GitHub only. No Claude,
provider adapter, MCP service, daemon, package API, or release publisher is
present.

## Automated Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Runtime/state/skill tests | Pass | 28 tests; config permissions, idempotency, retry, cancellation, route/digest binding, base/head snapshot identity, result guards, merge policy, corrupt state, and lock recovery. |
| Contract fixtures | Pass | 6 fixtures; runtime and JSON Schema independently accept/reject each expected payload. |
| Plugin validation | Pass | `validate_plugin.py` accepted the source plugin and isolated installed cache. |
| Skill validation | Pass | `quick_validate.py` accepted Init, main, and reviewer skills. |
| JSON and whitespace | Pass | Marketplace, manifest, and both schemas parse; `git diff --check` is clean. |
| Archive parity | Pass | `diff -qr` found no difference between source plugin and installed `0.1.0` cache; 23 files were installed. |

Primary commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s plugins/codex-feature-lifecycle/tests -p 'test_*.py'

PYTHONDONTWRITEBYTECODE=1 python3 \
  plugins/codex-feature-lifecycle/scripts/validate_contracts.py \
  --schemas plugins/codex-feature-lifecycle/schemas \
  --fixtures plugins/codex-feature-lifecycle/tests/fixtures

python3 /Users/zhanghao/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-feature-lifecycle
```

## Clean Installation Proof

An isolated Codex home at
`/private/tmp/codex-feature-lifecycle-verified-install.A38OQ2` was used; the user's
normal Codex configuration was not read or changed.

```bash
CODEX_HOME=<temporary-home> codex plugin marketplace add \
  /Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use --json

CODEX_HOME=<temporary-home> codex plugin add \
  codex-feature-lifecycle@macos-computer-use --json

CODEX_HOME=<temporary-home> codex plugin list --available --json
```

Codex reported:

- marketplace: `macos-computer-use`, newly added;
- plugin ID: `codex-feature-lifecycle@macos-computer-use`;
- version: `0.1.0`;
- enabled: true;
- install policy: `AVAILABLE`;
- authorization policy: `ON_INSTALL`.

The installed cache passed plugin validation and all 28 tests. No task was
created and no GitHub action was performed during installation proof.

## Forward Scenario Evidence

Three fresh, non-root, read-only agents applied the actual skills to bounded
hypothetical scenarios:

1. Init with one missing required task capability failed closed before any
   task/config mutation.
2. Main prepared one exact request, stopped edits while pending, accepted
   request changes only through validated state, and required a new dispatch
   for the changed snapshot.
3. Reviewer returned `STALE + NOT_ATTEMPTED` for a changed head and
   `APPROVE + NOT_AUTHORIZED` for a review-only policy without attempting merge.

The first pass found ambiguous readiness wording and several state/contract
edge cases. Those findings were repaired and covered by tests, including:

- exact readiness-marker equality and conditional failure guidance;
- dispatch IDs bound to both base and head SHA;
- request digest and GitHub repository/PR URL binding;
- a non-regressing fast-reviewer delivery-confirmation race;
- explicit cancellation and rejection of late review/results;
- reviewer-prepared result state/digest requirements and idempotent retry;
- closed decision/merge-status and merge-artifact combinations;
- canonical lowercase SHA agreement between runtime and JSON Schema;
- independent runtime/schema negative-fixture execution.

Final read-only re-review reported no blocker/high issue for Init, main, or the
reviewer contract.

## External Proof Not Performed

Two actions were intentionally not performed because they create durable user
or GitHub state and require explicit authorization at smoke time:

- a live `$codex-workflow-init` run that creates/pins two user-owned tasks;
- an end-to-end approved exact-head merge of a real PR.

Their absence does not weaken the static/install evidence, but they remain the
first opt-in production smoke after installation. Init must default to
`review-only` unless durable auto-merge authorization is separately granted.

## Known Boundaries

- Codex Desktop and `github.com` repositories only.
- Both configured tasks must have access to the same repository-scoped local
  workflow state and callable Codex task-management capabilities.
- No cross-application or cross-provider protocol is included.
- Uninstall does not archive user-owned tasks or erase local dispatch history.
- Plugin version `0.1.0` has no legacy-state migration path; unsupported schema
  versions fail closed.

## Verification Decision

Proceed to F6 merge readiness and PR review. Automated behavior, packaging,
installation, and non-mutating forward scenarios pass. Live task creation and
real merge remain explicit post-install smoke actions.
