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

Initial F5 result: 24 tests passed.

Post-review and forward-test remediation result: 28 tests passed, including
recoverable incremental Init, bootstrap blocking, deterministic message/Goal
replay, exact re-review authority, atomic acceptance rollback, pushed-current
requirements, unauthorized pre-persistence Init rejection, shadow metadata
rejection, plan/code remediation loops, review-only
READY/observed-MERGED, destination-bound full-target release proof, successful
last-submission/cumulative-result release replay, arbitrary-subset rejection,
ordered submission-history reconstruction, inverse stage invariants, and
corrupt-state rejection.

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

### Python static and format gates

Commands:

```bash
uv run --isolated --with ruff ruff check \
  plugins/codex-engineering-lifecycle/scripts \
  plugins/codex-engineering-lifecycle/tests

uv run --isolated --with ruff ruff format --check \
  plugins/codex-engineering-lifecycle/scripts \
  plugins/codex-engineering-lifecycle/tests
```

Result: Pass; all checks passed and all eight Python files were already
formatted on the final check.

Strict type command:

```bash
uv run --isolated --with mypy --with jsonschema --with types-PyYAML mypy \
  plugins/codex-engineering-lifecycle/scripts/workflowctl.py \
  plugins/codex-engineering-lifecycle/scripts/validate_contracts.py
```

Result: Pass; no issues in both runtime scripts.

## End-to-end lifecycle proof

The temporary-Git integration test proved:

1. canonical GitHub repository binding and recoverable incremental Init;
2. pre-persistence rejection without Goal authorization;
3. distinct Requirements/Main/Review IDs and config-only crash recovery;
4. bootstrap-only acknowledgements and pre-ready feature-work rejection;
5. deterministic, pushed, current, unique-metadata confirmed requirements
   handoff;
6. technical-plan Fail, remediation, exact previous-result re-review, and Pass;
7. initial GoalRun prepare/activate replay, block/resume, and completion;
8. code REQUEST_CHANGES, new remediation GoalRun, exact new-head re-review;
9. failing-check READY and review-only direct-MERGED rejection;
10. applied READY, then observed external
   matching-policy merge proof;
11. exact two-target release authorization;
12. GitHub Release success and PyPI failure;
13. closure rejection while one target failed;
14. retry containing only the failed PyPI target;
15. cumulative all-target success reconstructed from two immutable submission
    entries;
16. exact final-submission and cumulative-result replay, with arbitrary
    successful subset rejection;
17. rewritten/duplicate submission history, missing authorized result
    target/ID, arbitrary closure target, and
    future-proof/earlier-stage state corruption rejection;
18. final closure.

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
- Repository `scripts/release_preflight.py`: Pass. The sandbox prevented its
  local Unix-socket smoke, and the existing opt-in external application and
  TestPyPI/PyPI proofs remain explicitly unverified; this plugin does not
  change those package surfaces.

## Known operational requirements

- Real Init requires Codex task create/read/wait/message/pin tools and Goal
  create/get/update tools.
- Real merge/release needs the user's GitHub/PyPI permissions.
- GitHub install from `main` becomes valid after merge; before merge, install
  from `codex/engineering-lifecycle-plugin`.
- Plugin uninstall intentionally retains tasks, state, review branches, PRs,
  tags, releases, and packages.
