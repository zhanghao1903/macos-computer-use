# PyPI Token Publishing Implementation Plan

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | PyPI API-token publishing mode |
| Phase | F3 implementation plan |
| Branch | `codex/release-token-publishing` |
| Design | `docs/feature/pypi-token-publishing/design.md` |
| Release target | Coordinated `0.3.0` package release |

## Implementation Slice

Implement one coherent release-infrastructure change: generate and validate a
sanitized API-token authentication report, use its generic proof result in the
strict release bundle, and configure the GitHub release workflow to consume the
encrypted `PYPI_API_TOKEN` secret.

No runtime package, public Python import, protocol schema, macOS helper, WeChat
operation, or distribution content changes in this slice.

## Files And Ownership

| File | Planned change | Boundary |
| --- | --- | --- |
| `scripts/pypi_auth_report.py` | Add fixed-schema sanitized report generator. | Release tooling |
| `scripts/release_preflight.py` | Add token report loader, generic `pypi_publish_auth` proof, exact-one-mode validation, and workflow contract checks. | Release tooling |
| `scripts/release_proof_bundle.py` | Accept exactly one auth report mode and bundle `pypi-auth.json` for token releases. | Release tooling |
| `scripts/dev_check.py` | Point strict local proof validation at `pypi-auth.json`. | Developer checks |
| `.github/workflows/release.yml` | Keep macOS validation/build separate from the Linux publish action, remove OIDC permission, require the secret, and pass token credentials only in the publish job. | GitHub release automation |
| `tests/test_release_preflight.py` | Add report, preflight, bundle, ambiguity, and workflow-contract regression coverage. | Root release tests |
| `docs/publishing.md` | Document secure secret setup, token proof generation, workflow behavior, failure recovery, and optional OIDC compatibility. | Maintainer documentation |
| `docs/release-checklist.md` | Replace the `0.3.0` Trusted Publisher steps and proof names with token-mode steps. | Release operations |
| `docs/feature/pypi-token-publishing/implementation-notes.md` | Record the completed F4 implementation and decisions. | Lifecycle record |
| `docs/feature/pypi-token-publishing/verification.md` | Record automated and external F5 evidence. | Lifecycle record |
| `CHANGELOG.md` | Add the release-infrastructure change under the `0.3.0` release record. | Release record |

`scripts/trusted_publisher_report.py` remains unchanged unless a compatibility
test exposes a defect. It remains an alternate report producer, not the active
`0.3.0` workflow mode.

## Detailed Work Plan

### 1. Sanitized Report Producer

- Define fixed constants for schema, production repository URL, owner,
  repository, workflow, secret name, and verification method.
- Require the explicit `--configured` flag and `--output` path.
- Generate `generatedAt` as an ISO 8601 UTC timestamp ending in `Z`.
- Write only the approved schema. Do not accept or inspect token material.
- Use deterministic JSON formatting and an atomic-enough single-file write
  consistent with existing report scripts.

### 2. Strict Proof Contract

- Replace `EXTERNAL_PROOFS["pypi_trusted_publisher"]` with
  `EXTERNAL_PROOFS["pypi_publish_auth"]`.
- Add a strict token report loader that validates exact keys, values, types, and
  UTC timestamp syntax.
- Map valid Trusted Publisher reports to the same generic proof key.
- Extend `run_preflight` and CLI parsing with `pypi_auth_report_path` and
  `--pypi-auth-report`.
- Reject simultaneous token and Trusted Publisher reports before loading
  either; neither can silently take precedence.
- Keep all six non-authentication external proof checks unchanged.

### 3. Proof Bundle

- Add the `pypi-auth.json` asset name.
- Make token and Trusted Publisher report paths optional individually but
  require exactly one mode.
- Validate the selected detailed report before copying it.
- Write `release-proof.json` with `pypi_publish_auth` and unchanged source SHA,
  artifact, TestPyPI, helper, TextEdit, and WeChat proof data.
- Preserve fail-closed default behavior and `--allow-incomplete` diagnostics.

### 4. Workflow Security Contract

- Remove `permissions.id-token` from token mode.
- Download and require `pypi-auth.json` instead of
  `trusted-publisher.json`.
- Pass `--pypi-auth-report` to strict preflight.
- Add a non-echoing step that fails when `${{ secrets.PYPI_API_TOKEN }}` is
  empty before the publish action begins.
- Run source tests, macOS checks, builds, and strict proof in a `macos-latest`
  build job, upload the verified distributions, and download them in a dependent
  `ubuntu-latest` publish job supported by the Docker action.
- Keep every `PYPI_API_TOKEN` reference and the publish action out of the build
  job.
- Configure `pypa/gh-action-pypi-publish@release/v1` with `user: __token__`
  and `password: ${{ secrets.PYPI_API_TOKEN }}`.
- Do not add fallback credentials, workflow inputs, or shell interpolation that
  could print the token.

### 5. Tests

Add focused tests for:

- generated report shape and absence of credential-derived fields;
- exact-schema success;
- missing/malformed JSON and invalid timestamp;
- wrong schema, source, mode, repository URL, secret name, publisher metadata,
  credential type, configured value, verification mode, and unknown fields;
- strict preflight with token mode;
- strict preflight with existing Trusted Publisher mode;
- missing auth mode and dual-mode ambiguity;
- token-mode proof bundle asset names and aggregate proof;
- incomplete bundle behavior;
- release workflow secret gate, username, password expression, proof filename,
  proof argument, absence of OIDC permission, Linux publish runner, artifact
  handoff, and build-job secret isolation;
- local script inventory and `dev_check` strict command.

Existing release tests will be updated only where the pre-release generic proof
key or active workflow mode intentionally changed.

## Verification Commands

Focused checks:

```bash
python -m unittest tests.test_release_preflight
python scripts/release_preflight.py
```

Full repository checks:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest discover -s packages/app-control-protocol/tests
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Release checks after creating the sanitized external report:

```bash
python scripts/release_preflight.py \
  --wheel-dir <exact-dist-dir> \
  --sdist-dir <exact-dist-dir> \
  --pypi-auth-report <proof-dir>/pypi-auth.json \
  --require-external \
  ...
```

GitHub CI must pass on the pull request before merge.

## External Proof Plan

1. Set `PYPI_API_TOKEN` through `gh secret set ...` stdin using the ignored
   local production-token file; disable tracing and emit no credential output.
2. Verify only secret-name metadata with `gh secret list`.
3. Generate `pypi-auth.json` with the repository script.
4. Rebuild the complete strict proof bundle from the existing exact-source
   `0.3.0` proof and TestPyPI install evidence.
5. Run strict preflight against the exact `1b2c9a5` artifacts and expected
   source SHA.
6. Attach only sanitized proof assets and exact distributions to the GitHub
   Release.
7. After publication, verify all three projects and six expected files on
   production PyPI, then install/import all three `0.3.0` packages in an
   isolated environment.

No token file, token value, token hash, shell transcript containing a token, or
private desktop cleanup artifact may be attached or committed.

## Documentation And Release Record

- `docs/publishing.md` becomes the stable maintainer guide for token mode and
  clearly labels Trusted Publisher as an alternate future mode.
- `docs/release-checklist.md` records the exact `0.3.0` operation sequence and
  proof filenames.
- F4 and F5 lifecycle documents record implementation decisions and evidence.
- `CHANGELOG.md` records the GitHub Secret authentication and sanitized proof
  change without implying package runtime behavior changed.
- F6 prepares a PR description and merge-readiness record.
- F7 updates release readiness/notes with the exact merged SHA, tag, artifacts,
  proofs, and publication result.

## Compatibility And Rollback

- Package artifacts remain byte-for-byte governed by the existing build and
  exact-asset checks; this feature can be reverted without a package migration.
- Before production publication, rollback is a workflow/script revert plus
  restoration of the Trusted Publisher proof asset and OIDC permission.
- After any production artifact is accepted, do not recreate the version or
  replace files. Complete only duplicate-safe uploads after hash comparison, or
  use the documented yank/patch-release process.
- The GitHub secret can be deleted independently after publication. Deleting it
  does not alter release assets or published distributions.
- A future OIDC migration should reuse `pypi_publish_auth`, select only the
  Trusted Publisher report, restore least-privilege OIDC permission, and remove
  the password input and token secret.

## Phase Completion Criteria

F3 is complete when this plan is committed and pushed. F4 begins only after
the worktree is clean and implementation remains within the files and behavior
defined above.
