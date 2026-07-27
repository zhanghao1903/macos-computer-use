# PR: Add the Codex Engineering Lifecycle Plugin

## Summary

- Add the GitHub-distributed `codex-engineering-lifecycle` plugin.
- Package the repository's `feature-lifecycle`, `product-workflow-gate`,
  `technical-plan-write`, `technical-plan-review`, and `pr-review` skills.
- Add role skills and Init for exactly three Codex tasks: Requirements,
  Engineering Main, and Engineering Review.
- Add a durable, fail-closed workflow runtime for confirmed requirements,
  independent plan review, Goal-mode development/remediation, exact-head code
  review, merge evidence, explicit release authorization, and feature closure.

## Lifecycle

Requirements intake and confirmation → technical plan writing → independent
plan review → user notification → serialized Goal-mode development → exact-head
code review and report → authorized merge → exact per-release authorization →
verified publication → closure.

## Safety and recovery

- Init persists each created task ID before creating the next task and can
  recover interrupted or config-only initialization.
- Cross-task messages and Goal transitions are deterministic and replay-safe.
- Review-only mode separates approval from external merge authority.
- Release proof is bound to the exact repository, version, tag, artifacts, and
  targets; partial retries preserve prior success.
- Successful release replay must match the exact last submission or complete
  cumulative result, and state rejects proof from future lifecycle stages.
- Merge and release remain externally authorized operations.

## Verification

- 28 plugin unit/integration tests passed.
- 16 contract fixtures passed strict JSON Schema/runtime parity.
- Official plugin validator passed.
- All nine packaged skills passed the official skill validator.
- Ruff check and format gates passed.
- Strict mypy passed for both workflow runtime scripts.
- Repository release preflight passed, with only pre-existing environment and
  external-proof warnings documented in the verification record.

## Distribution

The plugin is distributed from this GitHub repository marketplace. Installation,
update, uninstall, pre-merge testing, privacy, support, and retained-state
behavior are documented in the plugin README.

## Authorization boundary

This PR does not authorize merge, GitHub Release creation, package publication,
or marketplace installation in another repository.
