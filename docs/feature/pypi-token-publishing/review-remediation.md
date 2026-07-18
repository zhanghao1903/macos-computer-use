# PyPI Token Publishing Review Remediation

## Review Status

| Field | Value |
| --- | --- |
| Lifecycle phase | F6 pre-merge technical self-review |
| Review date | 2026-07-19 |
| Scope | `origin/main...codex/release-token-publishing` |
| Initial decision | Blocked by unsupported publish runner |
| Remediated decision | Locally ready for PR/CI |

## Finding PTR-001: Publish Action On Unsupported Runner

**Severity:** Blocker

The inherited release workflow combined macOS tests/build/proof and
`pypa/gh-action-pypi-publish@release/v1` in one `macos-latest` job. The official
action documentation states that the action is Docker-based and can only run on
GNU/Linux GitHub-hosted runners:

- <https://github.com/pypa/gh-action-pypi-publish#non-goals>

The same documentation recommends separating build machinery from the publish
job and transferring distributions through GitHub Actions artifacts. Without
remediation, all local tests could pass while the production publish step still
failed before contacting PyPI.

## Remediation

The release workflow now has two dependent jobs:

1. `build` runs on `macos-latest`, executes all source/package tests, release
   preflight, tag validation, distribution builds, content checks, release proof
   download, and strict proof validation. It uploads the verified `dist`
   directory as a GitHub Actions artifact.
2. `publish` runs on `ubuntu-latest`, downloads only that verified artifact,
   verifies that `PYPI_API_TOKEN` is non-empty, and invokes the official action.

The production secret and publish action appear only in the Ubuntu job. Build
dependencies, package tests, and proof processing cannot read the production
token.

## Regression Gates

`release_preflight._check_workflows` now fails unless:

- the macOS build and Ubuntu publish jobs are distinct;
- `publish` depends on `build`;
- upload/download artifact actions form the handoff;
- the publish action is in the publish job;
- no `PYPI_API_TOKEN` reference occurs in the build job.

Regression tests mutate the publish runner back to macOS and inject the secret
into the build job; both changes are rejected.

## Verification

- focused release suite: `110` passed;
- root suite: `147` passed;
- `app-control-protocol`: `55` passed;
- `computer-use-macos`: `168` passed, `1` restricted-socket test skipped;
- `wechat-desktop-tool`: `172` passed;
- local release preflight: passed;
- workflow YAML syntax load: passed;
- `git diff --check`: passed.

## Remaining Review Boundaries

- GitHub Actions must validate the real runner/action integration on the PR.
- The production secret is not configured as part of review remediation.
- Final-source desktop proof and strict external proof remain F7 gates.

No other merge-blocking finding was identified in the local branch diff after
this remediation.
