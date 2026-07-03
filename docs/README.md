# Documentation

This directory documents the `app-control-protocol`,
`computer-use-macos`, and `wechat-desktop-tool` package suite for application
developers.

## Start Here

- [Quickstart](quickstart.md): install the packages, run TextEdit smoke, start
  local service mode, and try the WeChat focus/draft smoke.
- [Agent Integration Guide](agent-integration-guide.md): choose direct,
  helper, or local service mode and connect the packages to an application
  runtime, confirmation flow, and audit system.
- [API Contract](api.md): public Python APIs, command builders, protocol
  envelopes, WeChat semantic APIs, statuses, and failure boundaries.

## Reference

- [Protocol](protocol.md): `ToolCommand`, `ToolObservation`, `ToolEvent`,
  service envelopes, and schema validation.
- [Permissions](permissions.md): macOS Accessibility, Screen Recording, Apple
  Events, and the recommended helper permission subject.
- [Local Service](local-service.md): Unix socket service mode for non-Python
  callers.
- [Helper Packaging](helper-packaging.md): helper app template, manifest,
  signing, notarization, transport, and doctor checks.
- [Migration Notes](migration-notes.md): import paths and migration boundaries.

## WeChat

- [WeChat Desktop Tool](wechat-desktop-tool.md): semantic WeChat operations,
  response shapes, and safety boundaries.
- [WeChat Window Data Model](wechat-window-data-model.md): normalized
  `wechat.window.v1` model.
- [WeChat Smoke](wechat-smoke.md): dry-run, focus/draft, and opt-in submit
  smoke procedures.
- [WeChat AX Query Design](wechat-ax-query-design/README.md): design notes for
  scoped Accessibility reads.

## Release And Validation

- [Manual Smoke](manual-smoke.md): real macOS smoke checks.
- [Release Checklist](release-checklist.md): local verification, proof assets,
  and GitHub Release publishing flow.
- [Publishing](publishing.md): TestPyPI/PyPI workflow and trusted publisher
  proof.

## Feature Drafts

Draft designs under [feature/](feature/) are not stable public API. Treat them
as proposals until they are implemented, tested, and documented in
[api.md](api.md) or a package README.
