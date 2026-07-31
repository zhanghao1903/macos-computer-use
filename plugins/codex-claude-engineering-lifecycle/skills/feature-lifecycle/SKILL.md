---
name: feature-lifecycle
description: Manage a feature across its full repository lifecycle. Use when a user asks to add, implement, plan, review, merge, release, or summarize a feature; when work spans requirements, design, implementation, tests, documentation, changelog, PR/MR, or release notes; when each phase must leave a documentation record and be committed and pushed; or when preparing a version release that must clearly show what changed and which user scenarios were solved.
---

# Feature Lifecycle

Use this skill to drive feature work from requirement confirmation through
design, implementation, verification, review, merge, release, and post-release
traceability.

This skill orchestrates the lifecycle. It does not replace package-specific
workflow gates. For this repository, use `product-workflow-gate` before package
implementation, review, release, documentation, or repository-management work.

## Lifecycle Phases

F0. Intake and repository hygiene
F1. Requirement confirmation
F2. Consumer contract and feature design
F3. Implementation plan
F4. Implementation
F5. Verification, examples, and documentation
F6. Review, merge readiness, and release record
F7. Release preparation and publishing proof
F8. Post-release summary and traceability

## Non-Negotiable Rules

- Work on one feature per branch. Create or switch to a dedicated feature branch
  before changing feature artifacts. Prefer `codex/<feature-slug>` unless the
  user names another branch.
- Every lifecycle phase must have a documentation carrier. Completing a phase
  should change a document or a clearly identified section of a document. If no
  file change is appropriate, record the reason in the phase summary before
  proceeding.
- Commit and push after each completed phase. The commit must include only the
  files for that phase. If unrelated dirty files prevent a clean phase commit,
  stop and ask how to isolate the work.
- Report the branch name, phase document, commit id, and push status at the end
  of each phase.

## Phase Documentation Contract

Each phase has a required documentation responsibility:

| Phase | Required documentation carrier |
| --- | --- |
| F0 | Feature branch and repository hygiene note in the feature doc, issue, PR/MR draft, or phase summary. |
| F1 | Requirement/scenario section in `docs/feature/<feature>.md` or equivalent tracked feature document. |
| F2 | Consumer contract and design in `docs/feature/<feature>.md`. |
| F3 | Implementation plan section with files, tests, docs, smoke proof, and rollback notes. |
| F4 | Implementation notes in the feature doc or stable docs describing what changed and why. |
| F5 | Verification section listing automated checks, examples, manual smoke, and any skipped proof. |
| F6 | Review/merge readiness section plus `CHANGELOG.md` entry and PR/MR description when applicable. |
| F7 | Release notes, release checklist/proof assets, and version/tag plan when releasing. |
| F8 | Post-release summary linking commits, PR/MR, tag/release, scenarios solved, and follow-ups. |

## Required Feature Lifecycle Report

Before implementation, produce a short report:

- Feature:
- Feature branch:
- Current phase:
- User problem / scenario:
- Current behavior:
- Desired behavior:
- Affected package(s):
- Public surface impact:
- Safety / authorization impact:
- Required phase document:
- Required implementation scope:
- Required tests:
- Required docs:
- Required changelog entry:
- Release impact:
- Phase commit / push plan:
- Blockers / assumptions:

Keep this report concise. It should clarify scope and prevent hidden contract
changes, not become a replacement for the feature design.

## F0. Intake And Repository Hygiene

- Check current branch and worktree state before editing.
- Identify unrelated dirty files and do not revert them.
- Create or switch to a dedicated feature branch before changing feature files.
- Locate existing docs, tests, examples, and release notes for the affected
  package.
- Use `rg` and targeted file reads before changing code.
- Create or update the first documentation carrier for this feature, even if it
  is only an intake section in `docs/feature/<feature>.md`.
- Commit and push the F0 documentation and branch setup before starting F1.
- If the user asks for a release or merge, verify repository state and remote
  status before proceeding.

## F1. Requirement Confirmation

Clarify the feature in package-consumer terms:

- Which user or developer scenario is solved?
- What can the caller do after this feature that they cannot do now?
- What is explicitly out of scope?
- What is the expected recovery path when the feature fails?
- Does the feature read data, change focus, mutate desktop state, send content,
  publish artifacts, or affect release automation?

Ask only for missing decisions that cannot be safely inferred. For small
features, infer conservative defaults and continue.

Record confirmed requirements, assumptions, non-goals, and user scenarios in
the feature document. Commit and push that F1 update before moving to design.

## F2. Consumer Contract And Feature Design

For non-trivial, risky, cross-package, public API, protocol, desktop automation,
or release-affecting features, create or update a design under `docs/feature/`
before implementation.

The design should define:

- problem and goals;
- non-goals;
- affected package boundaries;
- data structures and schemas;
- public API or command shape;
- observation/result shape;
- failure kinds and caller recovery;
- safety, confirmation, and audit boundaries;
- data flow and operation flow diagrams when crossing package, helper, service,
  or Accessibility boundaries;
- compatibility and migration notes;
- implementation plan;
- test strategy;
- release-note impact.

Do not put detailed feature designs in `docs/architecture/`. Architecture docs
are for stable long-lived structure.

Commit and push the completed design document before starting implementation
planning. The commit should make the consumer contract reviewable on its own.

## F3. Implementation Plan

Before code changes, define the smallest coherent implementation slice:

- files/modules to touch;
- package boundary for each change;
- test files to add or update;
- examples or smoke scripts needed;
- docs that must be updated when the feature lands;
- manual proof required for real macOS or external services;
- rollback or compatibility strategy.

Prefer additive API changes. If a breaking change is unavoidable, require
explicit approval and migration notes.

Write the implementation plan into the feature document or a linked tracked
plan. Commit and push the F3 plan before code implementation begins.

## F4. Implementation

- Keep edits scoped to the approved package boundary.
- Preserve existing public behavior unless the feature explicitly changes it.
- Avoid broad refactors unrelated to the feature.
- Use structured parsers and existing helper APIs where available.
- Do not expose raw macOS Accessibility data to application developers when a
  normalized model or semantic operation is expected.
- Do not hide risky desktop actions behind convenience APIs without explicit
  risk, confirmation, and audit boundaries.

Update the feature document or stable docs with implementation notes that
explain the completed slice. Commit and push the F4 code and documentation
together after tests for that slice pass or are explicitly deferred.

## F5. Verification, Examples, And Documentation

Choose checks based on blast radius:

- Unit tests for parsing, protocol shape, failure handling, and package logic.
- SDK/example tests for public caller workflows.
- Package-boundary tests when imports or dependencies change.
- Release preflight when public docs, APIs, schemas, packaging, or examples
  change.
- Manual smoke proof for real macOS, helper, WeChat, PyPI, GitHub, or other
  external systems.

Update docs in the narrowest useful place:

- `docs/api.md` for stable public API and protocol examples.
- package README files for quick usage;
- `docs/feature/` for design drafts;
- `docs/architecture/` only for stable architecture;
- package-specific docs for semantic behavior;
- `docs/migration-notes.md` for compatibility changes;
- release docs for publishing workflow changes.

Record verification evidence in the feature document or release checklist:
commands run, results, skipped checks, and required manual proof. Commit and
push the F5 verification and documentation update.

## F6. Review, Merge Readiness, And Release Record

Before declaring the feature complete:

- Confirm tests/checks run and note anything not run.
- Confirm examples or smoke paths exist for package consumers.
- Confirm docs match implemented behavior.
- Confirm `CHANGELOG.md` has an entry under the correct category.
- Confirm each completed phase has a pushed commit on the feature branch.
- Confirm no generated local proof files, tokens, build outputs, or private
  smoke artifacts are accidentally included.
- Summarize user scenarios solved, not only files changed.

When using GitHub or another MR system, the PR/MR description should include:

- problem/scenario;
- solution summary;
- public API or behavior impact;
- tests and manual proof;
- docs and changelog;
- release-note text;
- migration notes if needed.

Commit and push the F6 review, changelog, and PR/MR description updates before
requesting merge.

## F7. Release Preparation And Publishing Proof

For a version release:

- Gather all merged changelog entries since the previous version.
- Group changes by user/developer scenario, not only by commit.
- Identify new features, fixes, docs, tests, packaging, and internal changes.
- Confirm version, tag, build artifacts, release checklist, and publishing proof
  requirements.
- Run or verify release preflight checks appropriate to the package suite.
- Prepare release notes that answer:
  - what changed;
  - what problems or scenarios are solved;
  - who needs to migrate;
  - what remains experimental;
  - what proof was run.

Do not publish a release without explicit user direction and required external
proof for real publishing targets.

Commit and push release-note, checklist, proof-reference, version, or tag-plan
updates before publishing or asking for final release approval.

## F8. Post-Release Summary And Traceability

After merge or release, return a concise lifecycle summary:

- feature name;
- scenario solved;
- package/API impact;
- files changed;
- tests and proof;
- changelog/release-note status;
- commit, PR/MR, tag, or release link when available;
- remaining follow-up work.

The goal is that a future maintainer can read the release notes and understand
what changed, why it changed, and how it was verified.

Commit and push the final post-release summary or follow-up tracking update
when it changes repository files.

## Blocking Conditions

Block or ask before proceeding when:

- feature work is not on a dedicated feature branch;
- a phase lacks a documentation carrier or a documented reason for no file
  change;
- a completed phase has not been committed and pushed;
- the consumer contract is unclear and cannot be inferred safely;
- public API or protocol changes lack a design;
- desktop automation can send content, pay, delete, install, or mutate user data
  without clear confirmation and audit boundaries;
- a breaking change lacks explicit approval and migration notes;
- release work lacks changelog, version, tag, build, or proof strategy;
- package boundaries would be violated;
- requested merge or publish action depends on external state that cannot be
  verified.

## Final Response Shape

End feature work with:

- Lifecycle phase:
- Feature status:
- Scenario solved:
- What changed:
- Public API/docs impact:
- Phase document:
- Branch:
- Commit / push status:
- Tests/checks run:
- Release record:
- Merge/release status:
- Remaining gaps:
