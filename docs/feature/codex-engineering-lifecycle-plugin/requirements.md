# Codex Engineering Lifecycle Plugin

## Status

- Feature: `codex-engineering-lifecycle`
- Lifecycle phase: F0 — intake and repository hygiene
- Branch: `codex/engineering-lifecycle-plugin`
- Base: `origin/main` at `1935b33`
- Date: 2026-07-27

## F0 intake and repository hygiene

The feature adds a new, heavier Codex workflow plugin alongside the existing
lightweight lifecycle work. It packages the repository's engineering workflow
skills and coordinates three durable Codex tasks:

1. Requirements;
2. Main Work;
3. Review.

The feature is being developed in an isolated Git worktree because the user's
original worktree contains unrelated, untracked WeChat smoke outputs, build
artifacts, and a lock file. Those files are outside this feature and must remain
untouched.

The implementation scope is limited to:

- `plugins/codex-engineering-lifecycle/`;
- `.agents/plugins/marketplace.json`;
- this feature document set;
- focused plugin and workflow tests;
- the repository changelog and PR/release records.

The change does not alter the public Python APIs, package dependencies, macOS
automation behavior, protocol package, or package release versions.

## Phase plan

- F1: confirm workflow requirements, scenarios, non-goals, and safety gates.
- F2: define the three-task state machine, contracts, and role boundaries.
- F3: define files, tests, documentation, recovery, and rollout.
- F4: implement the plugin, role skills, Init, schemas, and deterministic state
  helper.
- F5: validate skills, plugin structure, state transitions, documentation, and
  installation flow.
- F6: perform independent review, remediation, changelog, and merge readiness.
- F7: prepare an explicit release plan and proof.
- F8: record merge/release/closure traceability when external actions complete.
