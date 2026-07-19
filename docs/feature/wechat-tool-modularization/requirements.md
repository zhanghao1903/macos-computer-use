# WeChat Tool Modularization Requirements

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | WeChat Tool Internal Modularization |
| Branch | `codex/wechat-tool-modularization` |
| Current phase | F4 implementation (I2 query mapping extraction) |
| Baseline | `23d293d01245f3c46c67c5be6a6553a989d14e0a` (`origin/main`) |
| Affected package | `wechat-desktop-tool` |
| Public surface | No planned change |
| Release impact | Internal maintenance entry in the next changelog |

## F0 Intake

The package's `tool.py` has accumulated operation dispatch, workflow
orchestration, Accessibility query mapping, action execution and fallback,
failure translation, event evidence, timing, and redaction. The file is now a
material maintenance risk even though its behavior is protected by substantial
tests.

The requested outcome is an internal modularization that improves ownership,
reviewability, and test locality without changing software behavior.

## Repository Hygiene

- The user's primary checkout is on another feature branch and contains
  unrelated untracked files. Those files are not part of this feature and will
  not be modified, staged, or removed.
- This feature uses the isolated worktree
  `/private/tmp/macos-computer-use-wechat-tool-modularization`.
- The feature branch was created from the latest fetched `origin/main`.
- The feature worktree was clean before this document was added.
- Generated smoke output, tokens, build directories, local lock files, and raw
  Accessibility data are out of scope for commits.

## Baseline Evidence

At the baseline:

- `tool.py` contains 6979 lines and approximately 238 KB of source;
- it accounts for 63.5 percent of the package's Python production source;
- `WeChatDesktopTool` contains 62 methods;
- the module contains 161 top-level functions and 228 total functions/methods;
- `tests/test_tool.py` contains 7246 lines and 138 test methods;
- the public package exports `WeChatDesktopTool`, while the module's helper
  functions and support classes remain private implementation details.

These measurements establish a maintainability problem; they are not a claim
that line count alone proves incorrect behavior.

## F0 Scope Decision

The work proceeds as behavior-preserving internal maintenance. Requirements,
module contracts, safety invariants, implementation slices, and verification
evidence will be completed in later lifecycle phases before implementation.

## Feature Lifecycle Report

- Feature: WeChat Tool Internal Modularization.
- Feature branch: `codex/wechat-tool-modularization`.
- Current phase: F1 requirement confirmation.
- User problem / scenario: `tool.py` is too large to review and maintain safely.
- Current behavior: one module owns most semantic workflows, query mapping,
  action safety, diagnostics, and redaction.
- Desired behavior: the same public and desktop behavior implemented through
  cohesive internal modules with local tests.
- Affected package: `wechat-desktop-tool` only.
- Public surface impact: none.
- Safety / authorization impact: none is allowed; all current mutation gates
  and caller authorization boundaries remain mandatory.
- Required phase documents: this requirements document, followed by
  `design.md`, `implementation-plan.md`, implementation notes, verification,
  and merge-readiness records.
- Required implementation scope: internal module extraction, facade
  composition, and matching test reorganization.
- Required tests: all existing package tests, package-boundary tests, root
  contracts, type/lint checks, release preflight, and the existing live smoke
  performance contract when release proof is refreshed.
- Required docs: feature design plus the stable package architecture component
  map after implementation stabilizes.
- Required changelog entry: `Unreleased / Internal`.
- Release impact: include in the next coordinated package release; no immediate
  version publication is requested.
- Phase commit / push plan: one scoped commit and push after each completed
  lifecycle phase or coherent F4 implementation slice.
- Blockers / assumptions: no product decision is missing; behavior preservation
  is the controlling requirement.

## Problem Statement

The current module can still be tested and released, but unrelated concerns
share one import and review boundary. A change to contact discovery requires a
reviewer to navigate action replay rules, message submission, query parsing,
redaction, and failure conversion in the same file. The mirrored test module
has the same problem. This increases change blast radius and makes future
safety reviews slower and less reliable.

The maintenance problem is architectural. Runtime speed is not expected to
improve solely because code moves between modules, and this work must not claim
such an improvement without measurement.

## Developer Scenarios

1. A maintainer can change contact matching without editing the module that
   owns message submission or action dispatch proof.
2. A reviewer can inspect action replay and fallback rules in one bounded
   module with focused tests.
3. A maintainer can change observation normalization or redaction without
   navigating desktop mutation workflows.
4. An application developer upgrades to the refactored package without
   changing imports, commands, configuration, error handling, or Agent logic.
5. A release maintainer can run the same smoke and performance gates and obtain
   semantically equivalent proof.

## Functional Requirements

### R1. Public API Compatibility

- `wechat_desktop_tool.WeChatDesktopTool` and
  `wechat_desktop_tool.tool.WeChatDesktopTool` remain importable.
- Every public constructor, method signature, command builder, recipe, CLI
  entry point, dataclass, constant, and `__all__` export remains unchanged.
- No protocol schema, operation name, configuration field, default, package
  dependency, or Python version requirement changes.

### R2. Observation Compatibility

- Given the same `AppControlClient` responses, each operation returns the same
  `ToolObservation` status, success value, summary, observation/evidence
  structure, failure kind, retryability, risk metadata, and timing semantics.
- Normalized WeChat schemas, action references, pagination values, message
  hashes, and diagnostic field names remain unchanged.
- Raw Accessibility data remains excluded from public results except through
  the existing explicit debug behavior.

### R3. Command And Event Compatibility

- App-control operation sequences, command inputs, command-id suffixes,
  metadata phases, timeouts, and target-app identity remain unchanged.
- `run_stream` and observer callbacks emit the same event types, ordering,
  sequence numbers, summaries, and redaction behavior.
- Refactoring must not add a desktop query, click, key press, text insertion,
  or submit action to an existing successful or failed path.

### R4. Safety Compatibility

- A dispatched or possibly dispatched mutating action is never replayed.
- Coordinate fallback remains limited to coordinates derived from a current,
  validated Accessibility frame and the existing policy gate.
- Action-reference expiration, identity, preconditions, and fallback rules are
  unchanged.
- Ambiguous contacts remain non-actionable until disambiguated.
- `submit_unknown`, `send_unverified`, response-loss, truncation, and
  contradictory evidence remain fail-closed with their existing recovery
  instructions.
- Message content and other sensitive inputs remain redacted from events and
  safe diagnostics.

### R5. Performance Compatibility

- No query becomes unbounded and all existing timeout budgets remain intact.
- Common semantic APIs retain the existing release requirement of completing
  within 3000 ms in the supported live WeChat environment.
- The refactor must not introduce additional process, socket, or Accessibility
  round trips on equivalent paths.

### R6. Package Boundaries

- Generic macOS execution remains owned by `computer-use-macos` and protocol
  contracts remain owned by `app-control-protocol`.
- New modules stay private to `wechat-desktop-tool` and must not import product
  applications, Agent frameworks, or backend implementation modules.
- Internal module imports are acyclic. Shared low-level modules must not import
  operation orchestrators or the public facade.

### R7. Maintainability Outcome

- `tool.py` becomes a facade and dispatcher rather than a multi-domain
  implementation module.
- Each extracted module has one documented responsibility and avoids a generic
  `utils.py` catch-all.
- `tool.py` should be below 1000 lines and no new internal implementation
  module should exceed 1500 lines without a documented exception.
- The monolithic test module is split along the same ownership boundaries; no
  new test module should exceed 2500 lines without a documented exception.
- Extracted pure logic is directly testable without constructing the public
  facade or a live macOS client.

## Non-Goals

- Adding or removing WeChat operations.
- Changing selector profiles, control-map paths, matching heuristics, fallback
  decisions, error wording, or performance budgets.
- Generalizing WeChat-specific semantics into `computer-use-macos`.
- Redesigning `ToolCommand`, `ToolObservation`, or service transport.
- Replacing unittest, changing CLI syntax, or changing the packaged Agent
  skill.
- Large-scale style rewrites, renaming public concepts, or opportunistic bug
  fixes unrelated to extraction.

## Assumptions And Recovery

- Private helpers may move and be renamed inside the package; they are not part
  of the supported consumer contract. Tests that intentionally exercise those
  helpers will import them from their new owning module.
- Existing deterministic tests are the primary behavior oracle. When a test
  and an intended invariant disagree, implementation stops and the discrepancy
  is documented rather than silently changing behavior.
- Each extraction slice remains revertible as a standalone commit. A failed
  slice is rolled back without reverting earlier validated slices.

## Acceptance Evidence

- Baseline package suite: 172 tests passed on 2026-07-19 before code changes.
- All pre-existing package tests pass after every implementation slice.
- Public API and package-boundary contract tests pass from source and built
  distributions.
- Root repository tests, strict mypy/ruff checks configured by the repository,
  `git diff --check`, and source release preflight pass before merge readiness.
- Test inventory and module-size evidence prove the maintainability targets.
- Live smoke is not required for pure movement in every slice, but the next
  release proof must show unchanged safety checks and the 3000 ms API limits.

## Phase Commit Plan

Each completed lifecycle phase will update a tracked feature document, be
committed independently, and be pushed to the dedicated feature branch before
the next phase starts.
