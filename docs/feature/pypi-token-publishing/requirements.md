# PyPI Token Publishing Requirements

## Lifecycle Snapshot

| Field | Value |
| --- | --- |
| Feature | PyPI API-token publishing mode |
| Feature branch | `codex/release-token-publishing` |
| Current phase | F1 requirement confirmation |
| Release target | Coordinated `0.3.0` package release |
| Source baseline | `1b2c9a53abde68fe1373a7fff21fbb2e87950280` |
| Affected packages | Release infrastructure for all three packages |
| Public runtime API impact | None |
| Security impact | GitHub Actions receives a repository secret for PyPI upload |

## F0 Repository Hygiene

- The feature branch starts from the latest `origin/main` and the release
  worktree is clean.
- The unrelated primary worktree and its local changes are not modified.
- Local `.pypi.token` and `.testpypi.token` files are ignored, untracked, and
  restricted to the current user; token values must never enter logs, proof
  assets, commits, or command output.
- Existing exact-source `0.3.0` build and desktop proof remains external to the
  repository under `/private/tmp`.
- TestPyPI upload and isolated install proof have completed for all three
  `0.3.0` packages.
- The remaining release blocker is that the current workflow and strict proof
  contract require PyPI Trusted Publisher while the maintainer explicitly
  authorized API-token publishing.

## Lifecycle Report

- User problem / scenario: publish `0.3.0` without a PyPI browser session by
  using the maintainer-provided production PyPI API token.
- Current behavior: `.github/workflows/release.yml` supports only OIDC Trusted
  Publishing and strict preflight requires `trusted-publisher.json`.
- Desired behavior: GitHub Release publishing can use a configured GitHub
  Actions secret while retaining explicit, sanitized authentication proof and
  all existing release gates.
- Public surface impact: release process and proof schema only; no package
  imports, commands, observations, or semantic operations change.
- Required upstream artifacts: existing `0.3.0` release readiness, publishing
  documentation, proof bundle, preflight checks, workflow, and tests.
- Required implementation scope: token-auth proof generator, strict preflight
  alternative, proof bundling, release workflow secret use, docs, tests, and
  changelog.
- Required verification: focused release-script tests, full root tests,
  release preflight, exact artifact checks, GitHub CI, and post-publish PyPI
  install verification.
- Release impact: the `v0.3.0` workflow will publish with a long-lived secret
  instead of an OIDC-minted short-lived token.
- Phase commit / push plan: each F0-F7 phase updates its tracked carrier and is
  committed and pushed separately.
- Blockers / assumptions: repository secret configuration must be verified
  without exposing its value; publication must stop if the secret is absent or
  the strict proof bundle does not validate.

## Confirmed Requirements

### Goals

1. Support a production PyPI API token stored as a GitHub Actions repository
   secret for the coordinated package release.
2. Preserve the published-GitHub-Release trigger, source tests, artifact build,
   exact proof download, and strict preflight before any PyPI upload.
3. Replace the Trusted Publisher-specific release blocker with an explicit
   publishing-authentication proof that can represent the authorized API-token
   mode without claiming OIDC configuration exists.
4. Keep token values out of command output, Git history, release assets,
   generated reports, subprocess arguments where practical, and test fixtures.
5. Fail before upload when the workflow secret or matching sanitized proof is
   absent, malformed, for the wrong index, or for the wrong secret name.
6. Preserve the ability to add Trusted Publisher mode again without changing
   package runtime APIs or weakening unrelated external proof requirements.

### User Scenarios

- A maintainer with a production PyPI API token can configure one GitHub
  repository secret and publish all three coordinated packages from the
  existing release workflow.
- A reviewer can inspect a release asset and confirm the selected auth mode,
  target index, and GitHub secret name without learning the token.
- A failed or missing secret stops the publish job; the workflow does not fall
  back to a local file, plaintext repository value, or unauthenticated upload.
- A release operator can still validate exact artifacts on TestPyPI before the
  production token is used.

### Non-Goals

- Logging into PyPI, creating or rotating the maintainer's PyPI token, or
  committing any credential material.
- Changing package versions, runtime dependencies, public Python APIs, macOS
  behavior, WeChat behavior, or protocol schemas.
- Supporting password authentication, `.pypirc` publication in CI, or tokens
  passed through GitHub workflow inputs.
- Claiming the long-lived token has the security properties or attestations of
  OIDC Trusted Publishing.

### Failure And Recovery

- Missing secret: GitHub Actions fails the publish step before upload. Add the
  repository secret and rerun only while `0.3.0` is still unpublished.
- Invalid or wrong-scope token: PyPI rejects upload. Do not regenerate or reuse
  artifacts; correct the secret and rerun against the same tag and source.
- Partial publication: inspect every project/version before rerun. Never
  rebuild or replace an uploaded distribution; use repository-supported
  duplicate handling only when the artifact digest is already published.
- Suspected token exposure: stop the release, revoke the token in PyPI, replace
  the GitHub secret, inspect logs/assets, and record the incident before retry.
- Published bad release: follow the existing yank and coordinated patch-release
  process; PyPI artifacts and tags remain immutable.

## Acceptance Criteria

- A sanitized token-auth report validates only when it identifies production
  PyPI, `api-token` mode, and the exact `PYPI_API_TOKEN` secret name.
- Strict preflight accepts the token-auth report as the production publishing
  authentication proof while still requiring all six other external proofs.
- The proof bundle includes the exact token-auth report and records no secret
  value or local credential path.
- `release.yml` supplies `${{ secrets.PYPI_API_TOKEN }}` to the official PyPI
  publish action and does not request OIDC permission in token mode.
- The official Docker publish action runs in a dependent Linux job; the macOS
  test/build/proof job transfers verified distributions but cannot access the
  production token.
- Automated tests cover success, missing/malformed report, wrong index, wrong
  secret name, proof precedence, bundle output, and workflow contract.
- Documentation clearly distinguishes TestPyPI credentials, production token
  credentials, and Trusted Publisher/OIDC behavior.
