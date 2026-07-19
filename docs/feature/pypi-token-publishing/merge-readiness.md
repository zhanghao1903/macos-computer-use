# PyPI Token Publishing Merge Readiness

## Review Snapshot

| Field | Value |
| --- | --- |
| Lifecycle phase | F6 review and merge readiness |
| Repository | `zhanghao1903/macos-computer-use` |
| Base branch | `main` |
| Base SHA | `1b2c9a53abde68fe1373a7fff21fbb2e87950280` |
| Reviewed implementation head | `d6c99cb` |
| Feature branch | `codex/release-token-publishing` |
| Merge decision | Ready for PR and CI |
| Production release decision | Not yet authorized by proof gates |

The F6 documentation commit follows the reviewed implementation head and adds
only release records and PR documentation. Any later implementation change
invalidates this readiness decision and requires focused and unified regression
checks again.

## Scenario And Behavior

The maintainer can publish the coordinated `0.3.0` package set with an existing
production PyPI API token without a PyPI browser session. The token is stored in
the encrypted GitHub repository secret `PYPI_API_TOKEN`; release assets contain
only fixed, sanitized authentication metadata.

Strict release proof now uses the implementation-neutral
`pypi_publish_auth` key. API-token and Trusted Publisher detailed reports remain
mutually exclusive. Aggregate proof alone cannot authorize a strict release.

The release workflow validates and builds on macOS, then transfers only verified
distributions to a dependent Ubuntu publish job. Production-token references
and the Docker-based PyPI action exist only in that publish job.

## Change Map

| Area | Change | Risk | Evidence |
| --- | --- | --- | --- |
| Authentication metadata | Fixed sanitized API-token report schema and CLI. | High | Exact-field and malformed-input tests. |
| Strict proof | Generic auth key, detailed-report requirement, ambiguity rejection. | High | Preflight and bundle regressions. |
| GitHub workflow | Secret gate and token inputs; no OIDC permission. | High | Workflow contract tests and local preflight. |
| Runner boundary | macOS build/proof and Ubuntu publish jobs with artifact handoff. | High | Official action compatibility review and mutation tests. |
| Runtime packages | No source/API/package metadata change. | Low | Full package suites and branch file scope. |

## Review Findings

- `PTR-001` found that the inherited macOS job could not run the official
  Docker publish action. It is resolved by the dependent Ubuntu publish job and
  enforced by preflight. See `review-remediation.md`.
- No unresolved blocking correctness, security, compatibility, or packaging
  finding remains in the locally reviewed implementation diff.

## Verification Evidence

- focused release suite: `110` passed;
- root repository suite: `147` passed;
- `app-control-protocol`: `55` passed;
- `computer-use-macos`: `168` passed, `1` restricted-socket test skipped;
- `wechat-desktop-tool`: `172` passed;
- local release preflight: passed;
- workflow YAML syntax load: passed;
- credential-signature diff scan: clean;
- `git diff --check`: passed.

The existing socket skip is unrelated to release authentication and is covered
by GitHub macOS CI.

## Public And Compatibility Impact

- No package import, public Python API, protocol schema, command, observation,
  runtime dependency, version, or desktop behavior changes.
- The pre-publication release proof key changes from
  `pypi_trusted_publisher` to `pypi_publish_auth`.
- Existing Trusted Publisher reports remain an alternate local-tool input, but
  the active workflow selects token mode.
- No package consumer migration is required.

## Documentation And Release Record

- Requirements, design, implementation plan, implementation notes,
  verification, and remediation records are present under
  `docs/feature/pypi-token-publishing/`.
- `docs/publishing.md` and `docs/release-checklist.md` match token mode.
- `CHANGELOG.md` records the authentication proof and supported-runner split in
  the `0.3.0` Packaging section.
- The `0.3.0` release notes and readiness record no longer claim Trusted
  Publishing is the active mode.

## Merge And Release Boundaries

Merge requires:

- a PR from `codex/release-token-publishing` to `main`;
- green GitHub CI at the exact PR head;
- no new blocking review finding;
- a clean branch with no token, generated proof, distributions, or private
  smoke output.

Merge does not authorize production publication. F7 still requires the GitHub
secret metadata, final-source selector proof, rebuilt strict proof bundle,
tag/release assets, successful workflow, and post-publish install verification.
