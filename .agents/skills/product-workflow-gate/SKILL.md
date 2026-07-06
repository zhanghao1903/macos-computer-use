---
name: product-workflow-gate
description: Use before any change to the macOS computer-use package suite. Classifies package-maintenance work, checks public API and protocol impact, developer documentation, tests, release records, packaging proof, and GitHub MR hygiene before implementation or review.
---

# Computer-Use Package Workflow Gate

This repository ships Python packages for developers who integrate local macOS
computer-use capabilities into their own Agent applications. The primary user is
the package consumer, not an end-user UI operator.

Use this skill before implementation, review, release work, documentation work,
or repository-management work.

For end-to-end feature work that spans requirements, design, implementation,
review, merge, release notes, or release readiness, use `feature-lifecycle` as
the lifecycle orchestrator and this skill as the package gate inside that flow.

## Canonical Workflow

P0. Intake and repository hygiene
P1. Package consumer contract
P2. Public API, protocol, compatibility, and feature design
P3. Implementation or documentation change
P4. Examples, developer docs, and migration notes
P5. Tests, package boundaries, and smoke proof
P6. MR release record and changelog discipline
P7. Release readiness, packaging, and publishing proof

This is not a UI product workflow. Do not require UX flows, Figma screens,
frontend architecture, component specs, or visual regression unless the task
explicitly changes a UI artifact.

## Required Output Before File Edits

Package Workflow Gate Report:
- User request:
- Detected phase:
- Task type:
- Affected package(s):
- Public surface affected:
- Required upstream artifacts:
- Found artifacts:
- Missing or weak artifacts:
- Implementation allowed now: yes/no
- Prework required:
- Execution scope:
- Required docs update:
- Required tests/checks:
- Required release record:
- Risks/assumptions:

Keep the report short. The point is to prevent blind edits, not to create a
large planning document for every small fix.

## Task Types

Classify the request into one or more of these task types:

- Public API: package exports, command builders, client methods, config models,
  protocol schemas, CLI commands, observation payloads, error kinds, or typing.
- Behavior: desktop automation behavior, policy/risk behavior, helper/service
  behavior, WeChat semantic behavior, retry/timeout behavior, or failure modes.
- Documentation: README, docs under `docs/`, examples, migration notes,
  permissions docs, publishing docs, or API reference.
- Tests: unit tests, SDK example tests, package-boundary tests, release
  preflight tests, smoke tests, or proof-generation scripts.
- Packaging/release: version bumps, changelog, build metadata, wheel/sdist
  contents, PyPI/TestPyPI, release proof assets, tags, or publishing workflow.
- Repository hygiene: CI, GitHub workflow, MR policy, generated artifacts,
  ignored files, secrets, or branch/tag discipline.

## Public Surface Rules

Treat these as public or semi-public surfaces:

- Package names: `app-control-protocol`, `computer-use-macos`,
  `wechat-desktop-tool`.
- Import paths, `__all__`, `__version__`, `py.typed`, and exported dataclasses.
- Protocol schemas and payload contracts under `app_control_protocol`.
- Command builders, observation shapes, error `failureKind` values, config TOML
  fields, helper manifests, service envelopes, CLI commands, and examples.
- Developer-facing docs and smoke-test instructions.

For any public surface change:

- Prefer additive changes over breaking changes.
- If behavior changes, document the old behavior, new behavior, migration path,
  and compatibility risk.
- If a field is removed or renamed, require a deprecation or migration note
  unless the user explicitly accepts a breaking change.
- Keep package boundaries intact: `computer-use-macos` must not depend on
  `wechat-desktop-tool`; package code must not depend on product apps, Agent
  frameworks, UI frameworks, or LLM SDKs.

## Developer Documentation Rules

Because the consumer is an application developer, every meaningful feature or
behavior change must answer:

- How does a developer call it?
- What package and import path owns it?
- What command, observation, or config shape is stable?
- What can fail, and how should the caller recover?
- Which macOS permissions or helper/service setup are required?
- What is safe to automate, and what confirmation/audit remains the caller's
  responsibility?

Update the narrowest useful docs:

- `docs/api.md` for public APIs and protocol examples.
- Package README files for package-specific quick use.
- `docs/agent-integration-guide.md` for application integration guidance.
- `docs/permissions.md` for macOS permission subject changes.
- `docs/local-service.md` for socket/service/token behavior.
- `docs/wechat-desktop-tool.md` and `docs/wechat-window-data-model.md` for
  WeChat semantic APIs and window models.
- `docs/architecture/` for stable package architecture only: package
  boundaries, component ownership, runtime modes, long-lived data flow, and
  cross-package responsibilities.
- `docs/feature/` for detailed technical designs for new or proposed features:
  data structures, protocol/API proposals, flowcharts, sequence diagrams,
  implementation plans, migration notes, and test strategy.
- `docs/publishing.md` and `docs/release-checklist.md` for release workflow.
- `docs/migration-notes.md` when consumers need to change integration code.

Do not add broad docs when a focused package README or API section is enough.
Do not put detailed feature designs in `docs/architecture/`; architecture docs
must stay focused on stable long-lived structure.

For every new feature that changes public behavior, protocol shape, package
API, desktop automation behavior, or cross-package architecture, require a
feature design under `docs/feature/` before implementation unless the change is
trivially small and fully covered by an existing design. The design must define
the consumer contract, data structures, failure modes, safety boundaries, data
flow for cross-boundary behavior, tests, and migration path where applicable.

## MR Release Record Rules

Every MR must include a release record. This applies to features, bugfixes,
documentation changes, tests, packaging, CI, and internal maintenance.

The default release record location is `CHANGELOG.md`.

Required behavior:

- If `CHANGELOG.md` has an `Unreleased` section, add the entry there.
- If there is no `Unreleased` section, add one before the latest version
  section unless the task is explicitly preparing a versioned release.
- Use a category that reflects package-consumer impact: `Added`, `Changed`,
  `Fixed`, `Deprecated`, `Removed`, `Docs`, `Tests`, `Packaging`, or
  `Internal`.
- Mention affected package(s) when useful.
- For no user-facing behavior change, still add an `Internal`, `Tests`, or
  `Docs` release record so reviewers can see why the MR is safe.
- For release commits, move or copy relevant entries into the versioned section
  with the release date.

Block merge/review approval if a MR lacks a release record and the user has not
explicitly chosen to waive it for an exceptional reason.

## Required Tests And Checks

Choose the smallest check set that covers the changed surface.

Baseline package test command:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest discover -s packages/app-control-protocol/tests
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Use targeted tests for small changes, but broaden when touching shared protocol,
public API, config, packaging, release scripts, or cross-package behavior.

Additional gates:

- Public protocol/API docs or examples: run `python scripts/release_preflight.py`
  when feasible, because it validates docs examples and public surfaces.
- Wheel/sdist or packaging changes: build distributions and run
  `python scripts/release_preflight.py --wheel-dir <dist> --sdist-dir <dist>`.
- Version/tag changes: run `python scripts/release_tag_check.py --tag vX.Y.Z`.
- Release workflow changes: inspect `.github/workflows/ci.yml`,
  `.github/workflows/release.yml`, and release proof requirements.
- macOS/Desktop behavior changes: prefer unit tests plus a documented manual or
  smoke test path. Do not fake external proof and call it real.

If a check cannot run in the current environment, state exactly why and what
check remains for a macOS machine, PyPI/TestPyPI, GitHub, or a real desktop app.

## Implementation Rules

- Do not implement before classifying public surface and release impact.
- Do not invent API shapes in examples or docs without implementing and testing
  the matching package behavior.
- Do not expose raw macOS Accessibility data to application developers when a
  normalized model or semantic operation is expected.
- Do not hide risky desktop actions behind convenience APIs without clear risk,
  confirmation, and audit responsibilities.
- Do not commit tokens, local proof files, smoke output JSON, wheel/sdist
  directories, or generated lock files unless they are intentionally part of
  the repo contract.
- Keep changes scoped to the affected package boundary. Avoid unrelated
  refactors in release or bugfix MRs.
- Prefer deterministic unit tests and SDK stubs for API behavior. Use real
  smoke tests as release proof, not as the only correctness check.

## When To Block

Block implementation or review when:

- The request changes public behavior but the intended consumer contract is
  unclear.
- A breaking API change is proposed without explicit approval and migration
  notes.
- A desktop automation action can send messages, click unsafe targets, or
  mutate user data without confirmation/audit boundaries.
- Release or packaging work lacks version, changelog, build, or proof strategy.
- A MR has no release record.
- The package boundary would be violated.
- The task depends on real macOS/PyPI/GitHub state that cannot be checked and
  cannot be safely stubbed.

If the missing dependency can be safely inferred, create the smallest useful
draft artifact first and mark assumptions. If it is a major public API, release,
security, permission, or automation-safety decision, ask the user before
implementation.

## Final Response Format

At the end, return:

- Workflow phase
- Dependency status
- What changed
- Public API or docs impact
- Release record status
- Files changed
- Tests/checks run
- Remaining gaps or manual proof still needed
