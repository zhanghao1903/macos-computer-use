# Codex Feature Lifecycle Plugin Implementation Notes

- Updated: 2026-07-18
- Lifecycle phase: F4 Implementation
- Branch: `codex/codex-feature-lifecycle-plugin`
- Plugin version: `0.1.0`
- Product boundary: Codex Desktop + GitHub, no cross-application adapter

## Implemented Outcome

The repository now contains an installable skills-only Codex plugin that
coordinates two durable user-owned Codex tasks:

- `codex-feature-main` owns requirements through PR preparation, sends an
  immutable review request, consumes findings, and records post-merge
  traceability;
- `codex-pr-review-merge` independently reviews the exact PR head, never edits
  the feature branch, and merges only through explicit policy and safety gates;
- `codex-workflow-init` explicitly creates or binds the two tasks, verifies
  their readiness, and persists their routes only after both are healthy.

The implementation intentionally contains no Claude/provider abstraction, MCP
server, daemon, or non-GitHub merge-request path.

## Runtime And State

`scripts/workflowctl.py` is dependency-free at runtime and implements local
configuration, atomic dispatch state, schema/runtime validation, and safe
transitions for the complete request/result round trip. It:

- derives a stable repository key from canonical path and sanitized origin;
- strips credentials, query strings, and fragments from remotes before storage;
- writes owner-only state through atomic replacement and a bounded lock;
- creates stable dispatch IDs for exact repository, PR, base, and head inputs;
- rejects wrong routes, wrong workflow/repository, stale snapshots, duplicate
  terminal results, and unauthorized merge claims;
- stores no code, diff, prompt, transcript, finding text, or credential.

Configuration and state live below
`${CODEX_HOME:-~/.codex}/feature-lifecycle/projects/<repo-key>/`, not in the
source repository.

## Message Contracts

`ReviewRequest` and `ReviewResult` use closed JSON Schema Draft 2020-12
contracts at schema version 1. Runtime validation adds semantic constraints
that JSON Schema alone cannot reliably express, including:

- exact source/destination route reversal on results;
- approval cannot contain blocker findings;
- `MERGED` requires a URL and full merge SHA;
- a review-only workflow cannot accept a merged result;
- result snapshot and dispatch ID must match pending local state.

The reviewer uses GitHub's exact-head merge guard and is explicitly forbidden
from `--admin` and `--auto` bypasses.

## Packaging

The plugin manifest includes discoverability metadata, three bounded starter
prompts, declared Interactive/Write capabilities, and a source-controlled SVG
asset. The repository marketplace exposes the plugin as `AVAILABLE` with
installation-time authorization.

Installation, update, local-data, partial-recovery, and uninstall behavior ship
inside the Init skill reference so users receive operational guidance with the
plugin.

## Implementation Verification

The F4 implementation checks cover:

- runtime/contract unit tests, including permissions, retry, idempotency,
  stale-lock recovery, and merge authorization;
- static skill contract tests for required Codex capabilities, role isolation,
  exact-head enforcement, invocation policy, manifest assets, and marketplace
  wiring;
- all three skill package validators;
- plugin manifest/archive validation;
- Python syntax compilation and whitespace validation.

Clean installation, non-mutating forward scenarios, and consolidated evidence
are recorded separately in `verification.md` during F5.

## Public API And Package Impact

No Python package, public protocol, package version, or distribution artifact is
changed. This is a repository plugin deliverable with version `0.1.0`; the root
package suite remains at its existing release versions.

## Rollback

Reverting the plugin directory and marketplace entry removes discovery and
future execution. Existing Codex tasks and user-local workflow state remain
user-owned and are not deleted automatically. Their exact removal or archival
must be an explicit user action.
