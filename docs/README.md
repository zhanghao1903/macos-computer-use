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
- [Architecture](architecture/): package-level architecture notes for
  `computer-use-macos` and `wechat-desktop-tool`.
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

## Documentation Placement Rules

- `architecture/`: stable architecture documents only. Use it for package
  boundaries, component ownership, runtime modes, long-lived data flow, and
  cross-package responsibilities.
- `feature/`: detailed technical designs for new or proposed features. Use it
  for data structures, protocol/API proposals, selector profiles, flowcharts,
  sequence diagrams, implementation plans, migration notes, and test strategy.
- Stable public API docs belong in [api.md](api.md), package READMEs, or the
  narrowest package-specific reference after the implementation is complete.
- Migration or compatibility guidance belongs in
  [migration-notes.md](migration-notes.md).
- Release and validation process belongs in [release-checklist.md](release-checklist.md)
  and [publishing.md](publishing.md).

## New Feature Workflow

Every new feature that changes public behavior, protocol shape, package API,
desktop automation behavior, or cross-package architecture must follow this
flow:

1. Use the repository `feature-lifecycle` skill to manage the feature from
   requirement confirmation through release readiness.
2. Create or switch to a dedicated feature branch, normally
   `codex/<feature-slug>`.
3. Classify the change with the package workflow gate before implementation.
4. Add or update a design under [feature/](feature/) when the feature is
   non-trivial, cross-package, risky, or changes public contracts.
5. Define the consumer contract before coding: data structures, command or
   observation shape, failure kinds, safety boundaries, and recovery behavior.
6. Define data flow and operation flow for features that traverse macOS
   Accessibility, local service boundaries, helper transport, or semantic app
   adapters.
7. Use the repository `implementation-execution` skill for non-trivial or
   high-risk F4 work. Implement against the approved package boundary, maintain
   changed-surface/risk ledgers and adversarial evidence, then produce an
   exact-head review handoff. Generic macOS capability belongs in
   `computer-use-macos`; app semantics belong in an adapter such as
   `wechat-desktop-tool`.
8. Add targeted unit tests, SDK/example tests when public usage changes, and a
   documented manual smoke path for real desktop behavior.
9. Update stable docs after implementation, including [api.md](api.md), package
   README files, or package-specific docs as appropriate.
10. Add a `CHANGELOG.md` entry for every feature, fix, docs change, test change,
   or internal workflow change.

Each lifecycle phase must have a documentation carrier. Completing a phase
should update a feature document, stable doc, changelog, release checklist,
PR/MR description, or another tracked document. After each phase is complete,
commit and push only the files for that phase on the feature branch.
