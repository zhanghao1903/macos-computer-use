# WeChat Agent Skill 0.3.0 Release Readiness

## Release Identity

| Field | Value |
| --- | --- |
| Lifecycle phase | F7 release preparation and publishing proof |
| Release branch | `codex/release-0.3.0` |
| Release-blocker branch | `codex/release-0.3.0-control-map-fallback` |
| Publishing branch | `codex/release-token-publishing` |
| Source baseline | latest merged release head `1b2c9a5` |
| Target version | `0.3.0` for all three packages |
| Target tag | `v0.3.0` |
| Last PyPI version | `0.1.1` |
| Publication state | Not published |
| Release workflow | `.github/workflows/release.yml` on published GitHub Release |

The repository prepared a `0.2.0` source milestone but did not create its tag,
GitHub Release, or PyPI distributions. Version `0.3.0` is therefore the next
published package set and includes all changes since `0.1.1`, including the
selector-backed runtime and the packaged WeChat Agent skill.

## Consumer Scenarios

Version `0.3.0` enables application developers to:

- use the coordinated selector-backed macOS and WeChat semantic operation set;
- keep common contact, conversation, message, and contact-open paths bounded;
- load the versioned `wechat-use` skill into an in-memory Agent registry;
- export the validated skill for filesystem-based Agent runtimes;
- teach an Agent to inspect WeChat, list/open contacts, read visible messages,
  draft text, and send authorized text through semantic operations;
- preserve manual-verification recovery when a send result is unknown.

Existing applications that do not load the skill retain the existing semantic
operation behavior. No protocol schema migration or stored-data migration is
required.

## Coordinated Version Contract

| Package | Version | Runtime dependency floor |
| --- | --- | --- |
| `app-control-protocol` | `0.3.0` | None |
| `computer-use-macos` | `0.3.0` | `app-control-protocol>=0.3.0` |
| `wechat-desktop-tool` | `0.3.0` | `app-control-protocol>=0.3.0`, `computer-use-macos>=0.3.0` |

`wheel_check.py` must prove that the coordinated wheel set installs and that a
`wechat-desktop-tool 0.3.0` wheel cannot resolve against only the published
`0.1.1` dependency set.

## Release Gates

| Gate | Required evidence | Status |
| --- | --- | --- |
| Version and dependency alignment | Source metadata, imports, helper template, preflight constants, and tag check agree on `0.3.0`. | Passed on release branch |
| Changelog and release notes | Versioned changelog and `release-notes-0.3.0.md`. | Prepared on release branch |
| Source tests | Root and all three package suites. | Passed: 132 + 55 + 168 (1 skipped) + 171 |
| Distribution contents | Three wheels and three sdists plus clean install/API smoke. | Passed on release branch |
| Helper doctor | Exact-head `helper-doctor.json`. | Pending |
| TextEdit real smoke | Exact-head `textedit-smoke.json`. | Pending |
| WeChat focus/draft smoke | Exact-head sanitized report. | Pending |
| WeChat submit smoke | Exact-head sanitized report with explicit one-shot authorization. | Pending |
| Selector-engine live proof | Exact-head v2 report, non-empty collections, all timings at most 3000 ms. | Pending |
| TestPyPI coordinated install | Strict isolated `testpypi-install.json` for all `0.3.0` packages. | Pending |
| PyPI publish authentication | `PYPI_API_TOKEN` GitHub secret metadata and sanitized `pypi-auth.json`. | Pending final configuration |
| Strict proof bundle | Eight exact-name assets accepted with `--require-external`. | Pending |
| Release PR and CI | Release commit merged and final `main` CI green. | Pending |
| GitHub Release and PyPI | Published `v0.3.0` workflow succeeds and PyPI reports all packages. | Pending |

No gate may be marked complete from an old source SHA or from a manually
invented success report. The selector proof must bind to the exact release
source commit. Detailed reports override manual proof booleans.

## Live Proof Blocker Remediation

Exact-head WeChat submit proof on 2026-07-18 exposed a deterministic fallback
defect before any row action, message draft, or submit occurred. The packaged
control map listed both `0/12/1/0` and `0/11/1/0` conversation roots. The live
window exposed the second root, but `open_contact` returned immediately when
the first candidate produced `accessibility_query_root_not_found`.

The release-blocker fix treats only that explicit missing-root result as a
candidate miss and continues to the next configured path. Timeout, transport,
permission, malformed, contradictory, and truncated target-query evidence
remains fail-closed. Regression proof must cover the missing-first-root success
path and retain the existing failed/truncated query safety tests. After merge,
all exact-head desktop and distribution proofs must be regenerated against the
new `main` SHA before tagging.

## Local Candidate Evidence

The release branch completed these non-external checks on 2026-07-18:

- `scripts/release_tag_check.py --tag v0.3.0`;
- unified `scripts/dev_check.py`;
- root repository suite: 132 passed;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 168 passed, 1 Unix-socket environment skip;
- `wechat-desktop-tool`: 171 passed;
- source release preflight;
- three wheel and three sdist builds in an external temporary directory;
- combined wheel/sdist content and metadata preflight;
- clean local wheelhouse install and installed public API smoke;
- rejection of `wechat-desktop-tool 0.3.0` with only local `0.1.1`
  dependencies;
- Ruff checks for changed Python files;
- whitespace and scope checks.

Builds emit the existing setuptools warning that the TOML table form of
`project.license` becomes unsupported in 2027. It does not affect this release
candidate and remains a separate packaging-maintenance item.

## Accepted Existing Risks

The maintainer previously accepted `PRR-039`, `PRR-042`, `PRR-043`, and
`PRR-044` for the selector-engine release. They remain known issues rather than
resolved findings. Release consumers must:

- load only trusted, application-owned selector profile overrides;
- use the coordinated first-party package set;
- keep recipient confirmation and audit around message submission;
- avoid unattended send for partial, duplicate, or ambiguous contact names;
- stop when query completeness, identity, or provenance is inconsistent.

The Agent skill adds an additional guardrail: `submit_unknown`,
`send_unverified`, `status=unknown`, or response loss after a possible submit
must never trigger an automatic replay.

## Publication Sequence

1. Complete version, docs, source tests, distribution builds, and local
   preflight on the release branch.
2. Commit and push the F7 preparation record, open the release PR, and require
   green CI before merge.
3. Freeze the merged `main` SHA as the release source and run exact-head desktop
   proof.
4. Upload all six distributions to TestPyPI and generate the isolated install
   report.
5. Configure the production `PYPI_API_TOKEN` GitHub repository secret and
   generate sanitized `pypi-auth.json` metadata.
6. Generate and strictly validate the eight-file release proof bundle.
7. Create tag `v0.3.0`, create a draft GitHub Release, and attach every proof
   asset.
8. Publish the GitHub Release to trigger the macOS build/proof job followed by
   the token-authenticated Ubuntu publish job.
9. Verify the workflow, PyPI versions, installed public API, and skill bundle.
10. Record F8 post-release traceability in a separate commit and PR.

## Rollback

Before PyPI upload, stop the workflow and delete only the unpublished draft
release/tag as appropriate. After publication, artifacts are immutable: yank
the affected `0.3.0` files, document the reason, direct consumers to pin
`0.1.1`, and prepare a coordinated `0.3.1` fix. Never replace an existing
artifact or reuse a published tag.
