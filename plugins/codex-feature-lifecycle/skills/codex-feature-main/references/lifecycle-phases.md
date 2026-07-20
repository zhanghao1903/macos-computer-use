# Main-Work Lifecycle Phases

Use one feature per branch and keep every phase independently reviewable.

## F0. Intake And Repository Hygiene

- Inspect current branch, worktree, remote, default branch, open PRs, and
  repository instructions before editing.
- Preserve unrelated user changes and generated/local files.
- Create or switch to a dedicated feature branch.
- Locate existing docs, tests, examples, changelog, release policy, and any
  package/product workflow gate.
- Create the first feature documentation carrier.

## F1. Requirements

Record:

- user/developer scenario and current pain;
- desired behavior and observable success;
- non-goals;
- failure recovery;
- public API/protocol/config impact;
- safety, permissions, authorization, and external writes;
- assumptions and decisions that still require the user.

Do not implement a major public, safety, compatibility, or release decision
that remains ambiguous.

## F2. Design

For non-trivial or risky work, define before implementation:

- components and ownership boundaries;
- data structures and changed fields;
- API, protocol, command, config, and error contracts;
- data flow and object/state lifecycle;
- failure, retry, timeout, idempotency, and concurrency behavior;
- privacy, permissions, confirmation, and audit boundaries;
- compatibility, migration, rollout, and rollback;
- test and proof strategy.

Use diagrams when they materially clarify multi-component flow or lifecycle.
Keep proposed behavior distinct from implemented behavior.

## F3. Implementation Plan

Specify coherent slices with:

- exact files/modules and package boundaries;
- behavior and data-flow changes;
- unit, integration, contract, package, and smoke checks;
- docs, examples, changelog, and release impact;
- rollout, rollback, and deferred external proof.

Prefer additive changes. Breaking behavior requires explicit approval and
migration guidance.

## F4. Implementation

- Keep edits inside the approved scope.
- Preserve existing public behavior unless the feature changes it explicitly.
- Avoid unrelated refactors.
- Use existing parsers/helpers/contracts where available.
- Add deterministic tests with the implementation.
- Update implementation notes and stable docs together with code.

Do not include tokens, local proof, personal config, build output, or unrelated
dirty files in commits.

## F5. Verification, Examples, And Documentation

Choose evidence by blast radius:

- unit tests for logic, parsing, state, and failure handling;
- contract tests for public schemas and messages;
- package-boundary/build checks for dependency or packaging changes;
- examples for caller-visible workflows;
- release preflight for public docs/API/packaging changes;
- real external smoke only when authorized and available.

Record commands, results, skipped checks, reasons, limitations, and remaining
manual proof. Documentation must match implemented behavior.

## F6. PR And Review Readiness

- Add the repository-required changelog/release record.
- Ensure every intended phase commit is pushed.
- Create/update the PR with problem, solution, impact, tests, proof, docs,
  changelog, migration, release note, limitations, and rollback.
- Remove accidental generated/private artifacts from the PR.
- Fix the exact base/head snapshot from GitHub.
- Apply the readiness gate in the main skill and dispatch once.

F6 remains incomplete while review is pending or blocking findings exist.

## F7. Release Preparation

Run only when the user requests a release or the repository requires release
readiness for merge. Confirm version/tag/build/publishing proof, group release
notes by user scenario, and identify migration or experimental behavior.

Never publish without explicit user direction and required external proof.

## F8. Post-Merge Traceability

After proving merge, record or report:

- feature and scenario solved;
- public behavior/API/package impact;
- files/components changed;
- tests and external proof;
- docs/changelog/release status;
- commits, PR, reviewed head, merge SHA, tag/release when applicable;
- remaining follow-ups.

Use the narrowest durable carrier. Do not manufacture a post-merge repository
change when PR/task history already satisfies repository policy.

## Phase Completion Report

For every completed phase return:

- Phase
- Status and scenario
- Documentation carrier
- Branch and commit
- Push status
- Tests/checks
- Release record impact
- Blockers/assumptions
- Next phase
