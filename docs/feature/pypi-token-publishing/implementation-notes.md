# PyPI Token Publishing Implementation Notes

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | PyPI API-token publishing mode |
| Phase | F4 implementation |
| Branch | `codex/release-token-publishing` |
| Runtime package impact | None |
| Distribution content impact | None |
| External publication performed | No |

## Implemented Slice

### Sanitized Authentication Report

Added `scripts/pypi_auth_report.py` with a fixed, versioned schema for production
PyPI API-token authentication metadata. The command:

- requires the operator to pass `--configured` explicitly;
- always records the expected production upload URL, GitHub repository,
  workflow, and `PYPI_API_TOKEN` secret name;
- accepts no token value, token path, target override, secret-name override, or
  publisher override;
- writes no credential-derived value or fingerprint.

The report is an audit assertion about verified GitHub secret metadata. It is
not a credential validator and cannot authenticate an upload.

### Generic Authentication Proof

`scripts/release_preflight.py` now exposes the aggregate proof key
`pypi_publish_auth`. The implementation-specific
`pypi_trusted_publisher` key was removed before its first published release.

Strict mode resets the aggregate authentication proof to false before reading
detailed reports. Consequently, a hand-written `release-proof.json` boolean
cannot satisfy the production authentication boundary.

Strict preflight accepts exactly one detailed mode:

- `--pypi-auth-report` for API-token metadata; or
- `--trusted-publisher-report` for the existing OIDC-compatible report.

Supplying both produces an explicit source failure and leaves
`pypi_publish_auth=false`. A malformed report cannot fall back to an aggregate
boolean.

### Exact Token Report Validation

The token report loader validates:

- exact top-level, credential, and publisher key sets;
- exact schema, source, mode, production repository, secret name, credential
  kind, repository owner/name, workflow, and verification method;
- `configured` using identity with JSON boolean `true`, so integer `1` is not
  accepted;
- a syntactically valid RFC 3339 UTC `generatedAt` timestamp.

Unknown keys are rejected. This prevents a future producer from silently adding
credential values, fingerprints, or local paths to a release asset.

### Proof Bundle And Developer Check

`scripts/release_proof_bundle.py` now requires exactly one authentication report
mode. Token mode copies the detailed report as `pypi-auth.json`; Trusted
Publisher mode remains available as `trusted-publisher.json`. Both map to the
same aggregate proof key.

`scripts/dev_check.py` uses `release-proof/pypi-auth.json` for the active strict
release-proof check.

### GitHub Release Workflow

`.github/workflows/release.yml` now:

- runs tests, macOS checks, builds, and strict proof in a `macos-latest` build
  job that receives no production PyPI secret;
- uploads verified distributions and downloads them in a dependent
  `ubuntu-latest` publish job, as required by the Docker-based official action;
- omits unused `id-token: write` permission in API-token mode;
- downloads and validates `pypi-auth.json`;
- fails before the PyPI action when `PYPI_API_TOKEN` is empty;
- supplies `user: __token__` and
  `password: ${{ secrets.PYPI_API_TOKEN }}` to
  `pypa/gh-action-pypi-publish@release/v1`;
- retains the published-release trigger, source tests, tag check, builds,
  artifact checks, exact external proof download, strict preflight, and build
  artifact upload.

There is no plaintext, local-file, workflow-input, or unauthenticated fallback.

## Test Coverage Added

`tests/test_release_preflight.py` now covers:

- fixed sanitized report generation and CLI confirmation;
- valid token report integration with strict preflight;
- wrong schema, source, mode, target, secret, credential boolean type,
  publisher, and verification method;
- malformed JSON, unknown/missing fields, credential extensions, publisher
  extensions, and invalid/non-UTC timestamps;
- strict rejection of aggregate-only authentication proof;
- ambiguity rejection when token and Trusted Publisher reports are both given;
- active token-mode bundle assets and exact-one-mode bundle behavior;
- retained Trusted Publisher compatibility;
- workflow Secret gate, token action inputs, and absence of OIDC permission;
- Linux publish-runner compatibility, verified artifact handoff, and absence of
  the production secret from the build job;
- strict `dev_check` token proof asset selection.

Focused result at F4: `108` release preflight tests passed.

## Deliberate Compatibility Decisions

- Runtime imports, commands, schemas, macOS behavior, WeChat behavior, package
  metadata, and versions are unchanged.
- Trusted Publisher detailed reports remain accepted by local tooling, but the
  active `0.3.0` workflow uses API-token mode.
- Authentication reports are mutually exclusive rather than ordered by
  precedence.
- The generic proof-key migration is allowed because the proof schema has not
  yet shipped in a published version.

## Deferred To Later Phases

- F5 updates stable publishing/checklist documentation and records full test
  evidence.
- F6 adds the changelog and merge-readiness/PR record.
- F7 configures the real GitHub Secret, generates the external token-auth
  report, rebuilds strict proof, publishes, and verifies production PyPI.
- The selector-engine proof must be regenerated for the final merged/tagged
  source SHA. Existing proof tied to
  `1b2c9a53abde68fe1373a7fff21fbb2e87950280` cannot satisfy the workflow's
  `--expected-source-sha ${{ github.sha }}` check after merge.

No GitHub secret was changed and no production artifact was uploaded during F4.
