# PyPI Token Publishing Requirements

## Lifecycle Snapshot

| Field | Value |
| --- | --- |
| Feature | PyPI API-token publishing mode |
| Feature branch | `codex/release-token-publishing` |
| Current phase | F0 intake and repository hygiene |
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
