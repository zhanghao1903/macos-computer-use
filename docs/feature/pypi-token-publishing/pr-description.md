# PR: Use API-token authentication for the PyPI release

## Problem

The `0.3.0` release workflow required PyPI Trusted Publisher configuration, but
the maintainer authorized the existing production PyPI API token instead. The
old proof contract could not represent that decision without falsely claiming
OIDC setup. The inherited workflow also placed the Docker-based official PyPI
action in a macOS job, which is unsupported.

## Solution

- Add a fixed-schema `pypi_auth_report.py` generator that records only sanitized
  GitHub Secret metadata.
- Replace the aggregate proof key with `pypi_publish_auth` and require one
  detailed auth report in strict mode.
- Reject malformed reports, unknown fields, wrong target/secret/repository,
  aggregate-only proof, and token/OIDC report ambiguity.
- Extend proof bundling and developer checks for `pypi-auth.json` while
  retaining Trusted Publisher as an alternate tooling mode.
- Store the production credential only in `PYPI_API_TOKEN`; fail before upload
  when it is empty and pass it directly to the official action.
- Run tests/build/proof on macOS, transfer verified distributions as an Actions
  artifact, and run the Docker publish action in a dependent Ubuntu job that is
  the only job allowed to reference the production token.

## Package Impact

No runtime package API, protocol, dependency, version, macOS behavior, WeChat
behavior, or distribution content changes. The release proof schema changes
before its first published use; package consumers do not need to migrate.

## Verification

- `python -m unittest tests.test_release_preflight`: `110` passed.
- `python scripts/dev_check.py`:
  - root: `147` passed;
  - protocol: `55` passed;
  - computer-use: `168` passed, `1` restricted-socket skip;
  - WeChat: `172` passed;
  - release preflight: passed.
- Workflow YAML syntax and `git diff --check`: passed.
- Local review blocker `PTR-001` (unsupported macOS publish runner): resolved.

## Documentation And Release Record

- Added requirements, design, plan, implementation, verification, remediation,
  and merge-readiness records.
- Updated publishing and release-checklist guidance.
- Updated `0.3.0` release notes/readiness and added a Packaging changelog entry.

## Release Boundary

This PR does not configure the real GitHub Secret or publish to PyPI. After
merge, F7 must regenerate source-bound selector proof for the final SHA, build
the complete strict proof bundle, configure/verify the secret metadata, publish
`v0.3.0`, and validate all three production packages from a clean environment.
