# Codex-Claude Engineering Lifecycle Plugin — Verification

- Phase: F5 verification
- Date: 2026-07-31
- Branch: `codex/claude-hybrid-engineering-lifecycle-plugin`
- Implementation commit: `1616ab5`
- Status: Offline verification passed; real Claude smoke remains manual

## Automated results

### Full plugin suite

Command:

```bash
uv run --offline --isolated --with pyyaml --with jsonschema \
  python -m unittest discover -v \
  -s plugins/codex-claude-engineering-lifecycle/tests \
  -p 'test_*.py'
```

Result: **PASS — 37 tests**.

Covered behavior includes:

- recoverable lifecycle Init and exact workflow role binding;
- separate Claude Frontend and Review UUIDs;
- exact `--session-id` creation and same-role `--resume`;
- role-specific `acceptEdits` and `plan` permissions;
- environment credential filtering and forbidden permission flags;
- deterministic preflight `FAILED` retry;
- malformed/wrong-session/wrong-snapshot UNKNOWN behavior;
- same-message/same-session recovery and completed idempotent replay;
- explicit orphaned-RUNNING confirmation;
- routing and exact reviewed-snapshot binding;
- frontend Git proof and path-escape rejection;
- 13 contract runtime/schema pairs and 26 fixtures;
- packaged skill parity, metadata policy, prompt separation, manifest/layout,
  copied lifecycle integration, and PR-review validator behavior.

### Strict contract validation

Command:

```bash
uv run --offline --isolated --with pyyaml --with jsonschema \
  python plugins/codex-claude-engineering-lifecycle/scripts/validate_contracts.py \
  --require-jsonschema
```

Result: **PASS — 26 fixtures, 0 failures**, using both Draft 2020-12
`jsonschema` and independent runtime validation.

### Static checks

Commands:

```bash
uv run --offline --isolated --with ruff \
  ruff check \
  plugins/codex-claude-engineering-lifecycle/scripts \
  plugins/codex-claude-engineering-lifecycle/tests

uv run --offline --isolated --with mypy \
  mypy \
  plugins/codex-claude-engineering-lifecycle/scripts/workflowctl.py \
  plugins/codex-claude-engineering-lifecycle/scripts/claudectl.py \
  plugins/codex-claude-engineering-lifecycle/scripts/validate_contracts.py
```

Results:

- **Ruff PASS**.
- **mypy PASS — 3 source files, 0 issues**.

### Official scaffold validators

Results:

- plugin creator validator: **PASS**;
- `hybrid-workflow-init`: **PASS**;
- `hybrid-requirements`: **PASS**;
- `hybrid-main`: **PASS**.

## Security and recovery evidence

The offline fake executable records only sanitized argv metadata. Tests prove:

- the bridge never emits `--dangerously-skip-permissions` or
  `bypassPermissions`;
- `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` present in the parent test
  environment do not reach Claude;
- Frontend and Review never share session UUIDs;
- Review always uses the configured Review session and exact routed snapshot;
- a changed request under the same message ID is rejected;
- an uncertain response never authorizes work;
- a completed frontend claim never authorizes path escape;
- a lost Codex process cannot be recovered as orphaned without an explicit
  process-stopped confirmation.

## Manual pre-release gate

`command -v claude` returned no executable on this host. Therefore the
following real-service smoke was not run and is not claimed:

1. install/authenticate a supported Claude Code CLI manually;
2. install this plugin from the feature Git ref into a disposable repository;
3. run `$hybrid-workflow-init` with low test budgets;
4. confirm four distinct identities and both Claude bootstrap results;
5. dispatch one bounded frontend fixture and verify the resulting Git proof;
6. dispatch one plan review and one exact-head code review;
7. simulate one UNKNOWN result and recover the identical request/session;
8. inspect local state for secrets and verify uninstall retains audit state.

This smoke is required before tagging or announcing v0.1.0 as production-ready.
It is not required to review the deterministic offline implementation.

## Package/public API impact

No app-control package source, public Python API, protocol, build metadata, or
published artifact changed. Verification scope is the new repository plugin,
repository marketplace index, root plugin discovery docs, and changelog.

## Delivery decision

The implementation is ready for a draft PR and independent review. Merge and
release remain intentionally unauthorized. The real authenticated Claude smoke
is the only remaining pre-release verification gap.
