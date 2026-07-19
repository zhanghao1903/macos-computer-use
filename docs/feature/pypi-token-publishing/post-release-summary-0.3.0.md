# 0.3.0 Post-Release Summary

## Lifecycle Status

| Field | Value |
| --- | --- |
| Lifecycle phase | F8 post-release summary and traceability |
| Release date | 2026-07-19 |
| Source commit | `9923d64b74763586f284156bb1baa60c9bcf4802` |
| Tag | [`v0.3.0`](https://github.com/zhanghao1903/macos-computer-use/releases/tag/v0.3.0) |
| Release workflow | [Run 29667048852](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29667048852), attempt 2 passed |
| F8 branch | `codex/release-0.3.0-post-release` |
| Publication state | Complete |

## Scenario Solved

Application developers can install a coordinated package set that exposes the
selector-backed macOS operations, semantic WeChat APIs, and packaged
`wechat-use` Agent skill. Repository maintainers can publish that set through
the reviewed GitHub Release workflow with a production PyPI API token that is
available only to the Linux publish job.

The release includes all source changes since `0.1.1`. The intermediate
`0.2.0` source milestone was not published.

## Package And API Impact

| Package | Published version | Dependency contract |
| --- | --- | --- |
| [`app-control-protocol`](https://pypi.org/project/app-control-protocol/0.3.0/) | `0.3.0` | None |
| [`computer-use-macos`](https://pypi.org/project/computer-use-macos/0.3.0/) | `0.3.0` | `app-control-protocol>=0.3.0` |
| [`wechat-desktop-tool`](https://pypi.org/project/wechat-desktop-tool/0.3.0/) | `0.3.0` | `app-control-protocol>=0.3.0`, `computer-use-macos>=0.3.0` |

The release adds the packaged, framework-neutral `wechat-use` skill and ships
the selector-backed semantic WeChat operation set. Existing callers that do
not load the skill do not need a protocol or stored-data migration. Consumers
must install the coordinated `0.3.0` dependency set.

## Merged Change Record

- [PR #5](https://github.com/zhanghao1903/macos-computer-use/pull/5)
  added the packaged WeChat Agent skill.
- [PR #7](https://github.com/zhanghao1903/macos-computer-use/pull/7)
  aligned versions, dependencies, release notes, and package checks for
  `0.3.0`.
- [PR #8](https://github.com/zhanghao1903/macos-computer-use/pull/8)
  fixed configured WeChat conversation-root fallback before release.
- [PR #9](https://github.com/zhanghao1903/macos-computer-use/pull/9)
  selected API-token publishing and separated macOS build/proof from the Linux
  publish job. Its squash merge commit is the tagged release source.

## Release Proof

The published GitHub Release contains the eight allowlisted JSON proof assets:

- `helper-doctor.json`;
- `textedit-smoke.json`;
- `wechat-focus-draft-smoke.json`;
- `wechat-submit-smoke.json`;
- `wechat-selector-engine-smoke.json`;
- `testpypi-install.json`;
- `pypi-auth.json`;
- `release-proof.json`.

Strict preflight accepted all detailed reports, all six distributions, and the
aggregate proof. The selector proof is bound to the tagged source commit and
contains no raw Accessibility observations, contact names, message text,
window titles, token values, or local paths.

The live selector proof reported 11 contacts, 14 conversations, and 30 visible
messages. Every measured semantic API remained below the 3000 ms release
limit:

| Operation | Duration |
| --- | ---: |
| `openWeChat` | 718 ms |
| `inspectWindow` | 450 ms |
| `listConversations` | 413 ms |
| `openContact` | 1110 ms |
| `readVisibleMessages` | 1250 ms |
| `listContacts` | 691 ms |

The smoke opened WeChat, selected the configured File Transfer contact, read
visible data, and verified safety checks. It did not send another message.
The separately authorized submit proof was reused and accepted by strict
preflight.

## Workflow And PyPI Verification

The release workflow's macOS `build` job passed source tests, source preflight,
tag validation, distribution builds, wheel checks, proof download, strict
external preflight, and artifact upload. The dependent Ubuntu `publish` job
downloaded only the verified distributions and published them with the
repository secret.

The first publish attempt failed before uploading its first file because the
configured secret was not valid PyPI authentication. The secret was replaced
through protected input, and rerunning the failed job succeeded. No token value
or fingerprint was written to a report, log summary, release asset, or commit.

Production PyPI metadata reports exactly one wheel and one sdist per project.
Their SHA-256 digests match those printed by the successful workflow:

| File | SHA-256 |
| --- | --- |
| `app_control_protocol-0.3.0-py3-none-any.whl` | `856f0817fbbd89c9ae52afc662e48943a0bb532812acd91c8718c8edaf597580` |
| `app_control_protocol-0.3.0.tar.gz` | `259b3c3a049da61cf9c478532fdef3f1dba3fd4d32a62ca9d3c91be4658b8c5c` |
| `computer_use_macos-0.3.0-py3-none-any.whl` | `5b9da857103ead3f72bec5ca4b03e346d6bb2e69879183dd76ea066dbc20ecd1` |
| `computer_use_macos-0.3.0.tar.gz` | `7918f27f8b6290abe5e08e9ecbd8ffb5ed59bed12b41db315f0d6f2b918f48da` |
| `wechat_desktop_tool-0.3.0-py3-none-any.whl` | `a7345978e3ed8728d52677db3a885730c61eeb255c77cf420a5e5e32a0941a90` |
| `wechat_desktop_tool-0.3.0.tar.gz` | `9b4f0ef49c7cdb47ebf41ddbc32c3c95b8fcd7b53953e104397382d79c4160c7` |

A new isolated virtual environment then installed all three exact versions
from `https://pypi.org/simple/` with no cache. Installed-package public API
smoke passed for protocol schemas and envelopes, macOS command builders and
helper APIs, and WeChat commands plus the packaged Agent skill.

## Remaining Follow-Ups

- Preserve the accepted selector-engine risks `PRR-039`, `PRR-042`, `PRR-043`,
  and `PRR-044`; do not infer unattended-send safety from this release.
- Update GitHub actions that still target the deprecated Node.js 20 runtime.
- Replace the deprecated TOML table form of `project.license` before the
  setuptools 2027 enforcement date.
- Signed and notarized helper distribution remains separate from this package
  publication proof.
- Rotate or revoke `PYPI_API_TOKEN` through repository-secret controls when
  repository ownership or maintainer access changes.

Published PyPI files and `v0.3.0` are immutable. A release defect must be
handled by yanking affected files when necessary and publishing a coordinated
patch version; artifacts and tags must not be replaced.
