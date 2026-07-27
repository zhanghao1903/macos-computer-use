# F5 Verification: Codex Engineering Lifecycle Plugin

- Date: 2026-07-27
- Branch: `codex/engineering-lifecycle-plugin`
- Implementation commit: `bde85ea`
- Phase: F5 documentation and verification

## User-facing documentation

The plugin README documents:

- prerequisites and trust boundaries;
- GitHub marketplace installation and source/ZIP download;
- feature-branch installation for pre-merge testing;
- Init and the exact three task roles;
- lifecycle and GoalRun behavior;
- review-record retention and merge gates;
- exact per-release authorization and failed-target retry;
- marketplace update/reinstall;
- plugin and optional marketplace uninstall;
- retained task/state/external-record boundaries;
- status, recovery, development validation, safety, and support.

Plugin-level `PRIVACY.md`, `TERMS.md`, `SUPPORT.md`, `CHANGELOG.md`, and the
repository-compatible MIT `LICENSE` are present. `docs/README.md` links the
plugin for repository discoverability.

## Automated verification

### Official plugin validator

Command:

```bash
uv run --isolated --with pyyaml python \
  /Users/zhanghao/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-engineering-lifecycle
```

Result: Pass.

### Official skill validators

Command:

```bash
find plugins/codex-engineering-lifecycle/skills \
  -mindepth 1 -maxdepth 1 -type d \
  -exec uv run --isolated --with pyyaml python \
  /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  {} \;
```

Result: nine of nine skills valid.

### Full plugin unit/integration tests

Command:

```bash
uv run --isolated --with pyyaml --with jsonschema python \
  -m unittest discover \
  -s plugins/codex-engineering-lifecycle/tests \
  -p 'test_*.py' -v
```

Result: 24 tests passed.

Coverage includes:

- manifest, marketplace, SVG, documentation, and placeholder checks;
- all eight contract schemas and 16 fixtures;
- runtime/Schema parity;
- role-skill composition and boundaries;
- source/packaged skill parity;
- packaged `pr-review` schema and re-review decision invariants;
- full temporary-Git lifecycle through closure.

### Strict contract gate

Command:

```bash
uv run --isolated --with jsonschema python \
  plugins/codex-engineering-lifecycle/scripts/validate_contracts.py \
  --require-jsonschema
```

Result: 16 fixtures, zero failures, `jsonschema+runtime`.

## End-to-end lifecycle proof

The temporary-Git integration test proved:

1. canonical GitHub repository binding;
2. Init with distinct Requirements/Main/Review IDs;
3. all role bootstrap acknowledgements;
4. committed confirmed requirements handoff;
5. committed technical-plan snapshot and independent Pass report;
6. initial GoalRun prepare/activate/block/resume/complete;
7. exact-head code-review request and immutable report branch;
8. passing-check and matching-policy merge proof;
9. exact two-target release authorization;
10. GitHub Release success and PyPI failure;
11. closure rejection while one target failed;
12. retry containing only the failed PyPI target;
13. cumulative all-target success and closure.

No production repository, PR, release, or package publication was mutated by
this test.

## Repository and artifact checks

- JSON parsing: Pass for manifests, schemas, examples, and fixtures.
- SVG XML parsing: Pass for icon, light logo, and dark logo.
- Source skill runtime parity: Pass; only the documented explicit-invocation
  metadata overlay differs.
- `git diff --check`: Pass for the F4 implementation snapshot.
- Project dependency/API impact: none; temporary validators use isolated
  development dependencies.
- Generated environments: no `.venv` retained.

## Known operational requirements

- Real Init requires Codex task create/read/wait/message/pin tools and Goal
  create/get/update tools.
- Real merge/release needs the user's GitHub/PyPI permissions.
- GitHub install from `main` becomes valid after merge; before merge, install
  from `codex/engineering-lifecycle-plugin`.
- Plugin uninstall intentionally retains tasks, state, review branches, PRs,
  tags, releases, and packages.
