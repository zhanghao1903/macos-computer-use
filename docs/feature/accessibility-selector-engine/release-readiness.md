# Accessibility Selector Engine 0.2.0 Release Readiness

- Updated: 2026-07-18
- Lifecycle phase: F7 Release Preparation
- Release branch: `codex/release-0.2.0`
- Target version/tag: `0.2.0` / `v0.2.0`
- Target packages: `app-control-protocol`, `computer-use-macos`,
  `wechat-desktop-tool`
- Source baseline: `main` at `44e90e817d4db51e0a7fcab71927ad85dc1b7646`
- Publication state: not published
- Release decision: proceed with maintainer-accepted known issues

## Release Scope

Version `0.2.0` publishes the coordinated package set required by the internal
Accessibility selector engine and selector-backed WeChat semantic operations.
All package versions and dependency floors are already aligned at `0.2.0`.
Public `resolve_selector` and `extract_collection` protocol commands remain
deferred and are not part of this release.

## Accepted Known Issues

The maintainer explicitly directed the release to proceed with `PRR-039`,
`PRR-042`, `PRR-043`, and `PRR-044` open. The authoritative evidence is
[`pr-review-macos-computer-use-3-31404a9.md`](./pr-review-macos-computer-use-3-31404a9.md).
These findings remain release notes and follow-up work, not resolved findings.

Release consumers must apply these boundaries:

- use only trusted, application-owned selector profile overrides;
- use the coordinated first-party package set rather than foreign query
  envelope producers;
- keep application-level confirmation and audit around message submission;
- avoid unattended send for partial, duplicate, or ambiguous contact names;
- stop automation when query completeness or provenance is inconsistent.

## Release Gates

| Gate | Required evidence | Status |
| --- | --- | --- |
| Version and dependency alignment | All three package metadata files and tag check report `0.2.0`. | Ready for exact-head validation. |
| Changelog and release notes | Versioned changelog plus `release-notes-0.2.0.md`. | Prepared on release branch. |
| Source tests and CI | Root and three package suites; release-branch and final-main CI. | Pending release commit. |
| Build and package contents | Three wheels and sdists; isolated import/API and dependency rejection. | Pending release commit. |
| Helper doctor | `helper-doctor.json`. | Pending exact release source. |
| TextEdit real smoke | `textedit-smoke.json`. | Pending exact release source. |
| WeChat focus/draft and submit | Two sanitized smoke reports; submit requires explicit one-shot authorization. | Pending exact release source. |
| Selector-engine live proof | Source-bound proof v2 with all APIs at or below 3000 ms. | Pending final `main` SHA. |
| TestPyPI coordinated install | Strict isolated `testpypi-install.json`. | Pending uploaded release artifacts. |
| PyPI Trusted Publisher | Manual project/workflow verification in `trusted-publisher.json`. | Pending manual verification. |
| Strict proof bundle | Eight exact-name GitHub Release assets accepted with `--require-external`. | Pending all external proof. |
| GitHub Release and PyPI | Publish `v0.2.0`; release workflow publishes all three distributions. | Pending proof gates. |

## Publication Sequence

1. Validate and merge the release-preparation PR into `main`.
2. Freeze the resulting `main` commit as the release source candidate.
3. Run tests, tag check, build, wheel/sdist checks, and isolated API smoke.
4. Generate real desktop proof against that exact source commit.
5. Upload the coordinated distributions to TestPyPI and generate the isolated
   install report.
6. Manually verify Trusted Publisher configuration for all three PyPI
   projects.
7. Build and strictly validate the release proof bundle.
8. Create draft GitHub Release `v0.2.0`, attach all eight proof files, and
   publish it to trigger `.github/workflows/release.yml`.
9. Verify PyPI versions and installed public APIs, then write
   `post-release-summary.md` in a separate F8 commit.

## Rollback

PyPI artifacts are immutable. If publication exposes a release-blocking
regression, stop the workflow before publish when possible. After publication,
yank affected `0.2.0` artifacts, document the reason, direct consumers to pin
`0.1.1`, and prepare a coordinated `0.2.1` fix. Do not overwrite an existing
version or reuse a tag.
