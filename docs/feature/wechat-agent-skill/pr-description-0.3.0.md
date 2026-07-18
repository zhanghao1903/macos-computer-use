# Prepare coordinated 0.3.0 release

## Release Scope

Prepare `app-control-protocol`, `computer-use-macos`, and
`wechat-desktop-tool` for coordinated version `0.3.0`.

PyPI currently exposes `0.1.1` as the latest package set. The repository's
`0.2.0` selector milestone was not tagged or published, so `0.3.0` is the next
published release and includes all selector-backed runtime changes plus the
new packaged `wechat-use` Agent skill.

## Changes

- Set all three package metadata and runtime `__version__` values to `0.3.0`.
- Raise internal package dependency floors to `>=0.3.0`.
- Update the generated helper bundle version.
- Update release preflight, wheel checks, fixtures, package-boundary tests, and
  selector proof version expectations.
- Move the Unreleased entries into the `0.3.0` changelog section.
- Add versioned release notes, migration guidance, and F7 readiness records.
- Remove one unused WeChat window-model import found by the release lint gate.

## Consumer Impact

Applications should upgrade the coordinated package set together. Existing
semantic WeChat method signatures remain compatible; no protocol schema or
stored-data migration is required.

The `wechat-use` skill is opt-in. Loading or exporting it performs no desktop,
network, token, permission, registration, or message-send operation.

## Local Verification

- `scripts/release_tag_check.py --tag v0.3.0`: passed.
- Root suite: 132 passed.
- `app-control-protocol`: 55 passed.
- `computer-use-macos`: 168 passed, 1 environment-dependent socket skip.
- `wechat-desktop-tool`: 171 passed.
- Unified `scripts/dev_check.py`: passed.
- Ruff on changed Python files: passed.
- Three wheels and three sdists built successfully.
- Combined wheel/sdist release preflight: passed.
- Clean wheelhouse installation and installed public API smoke: passed.
- Mixed-version smoke rejected WeChat `0.3.0` with only `0.1.1` dependencies.

The existing setuptools `project.license` TOML-table deprecation warning remains
non-blocking and is outside this release's scope.

## External Publishing Gates

The PR does not publish packages. After merge, the exact `main` SHA must still
produce and pass:

- helper doctor proof;
- TextEdit real smoke;
- WeChat focus/draft and explicitly authorized submit reports;
- source-bound selector-engine proof v2;
- coordinated TestPyPI install report;
- PyPI Trusted Publisher report;
- strict eight-file release proof bundle.

Only after those assets validate will draft GitHub Release `v0.3.0` be
published to trigger the PyPI Trusted Publishing workflow.

## Known Issues

The maintainer-accepted selector findings `PRR-039`, `PRR-042`, `PRR-043`, and
`PRR-044` remain open and documented. Applications must retain recipient
confirmation, trusted selector-profile ownership, audit, and no automatic
replay after an unknown send result.
