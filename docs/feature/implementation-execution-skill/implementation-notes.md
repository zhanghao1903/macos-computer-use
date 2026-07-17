# Implementation Notes: Implementation Execution Skill

## S1 Core Skill

- Status: implemented; verification pending F5 consolidation
- Scope:
  - `.agents/skills/implementation-execution/SKILL.md`
  - `.agents/skills/implementation-execution/agents/openai.yaml`
  - `.agents/skills/implementation-execution/references/rejection-patterns.md`

### Behavior Implemented

The skill now owns implementation execution between an approved plan and an
independent PR review. It requires:

- frozen branch/base/head and approved inputs;
- a pre-edit implementation gate report;
- changed-file and risk-surface ledgers;
- vertical slices with counterexamples defined before code;
- contract-execution parity and complete public contract propagation;
- explicit mutation no-replay, target, bounded-query, cache/pagination,
  privacy, configuration, compatibility, and package gates;
- exact-head slice evidence and phase/slice commit/push;
- a fresh full-diff forward-risk pass;
- a review handoff that can say only `ready_for_review` or `blocked`.

The detailed reference groups recurring findings from `PRR-001` through
`PRR-036` into eleven reusable implementation patterns and three compact
adversarial matrices. The core skill links to that reference only for matching
risk surfaces.

### Design Decisions

- No implementation-record schema or validator is added in version one. The
  evidence is semantic, and keyword validation would recreate the vacuous-proof
  problem the skill is intended to prevent.
- No README, example placeholder, script, asset, or tool dependency is included.
- The skill never approves its own implementation or authorizes live mutation,
  merge, publish, or release.
- UI metadata uses the same narrow ownership and explicitly invokes
  `$implementation-execution` in its default prompt.

### Counterexamples Addressed

- A new failure kind cannot be considered complete without registry/export,
  consumer, packaging, and dependency-floor evidence.
- A timeout or malformed action result cannot authorize replay without exact
  safe dispatch/effect proof.
- Truncated selector candidates cannot be used as targets or cached decisions.
- Half-valid configuration cannot activate split components.
- Private canaries must be checked across results, errors, events, logs, and
  release artifacts.
- Passing old finding tests does not skip remediation-induced risk review.

### Rollback

Revert the S1 commit. No package, protocol, configuration, or runtime migration
is required.

## S2 Lifecycle Integration

- Status: implemented; verification pending F5 consolidation
- Scope:
  - `.agents/skills/feature-lifecycle/SKILL.md`
  - `docs/README.md`

### Behavior Implemented

`feature-lifecycle` now invokes `implementation-execution` during F4 for
non-trivial, cross-package, public-contract, desktop-mutation, retry/fallback,
cache/pagination, privacy, packaging, and review-remediation work. It keeps
phase-transition ownership and requires blocked implementation to return to
F1-F3 rather than inventing missing decisions in code.

Small isolated changes may scale down the ledger, but still require frozen
scope, changed-path classification, proportional counterexamples, and
exact-head evidence. Leaving F4 requires a review handoff and cannot claim PR
approval.

The repository documentation now exposes this workflow alongside
`feature-lifecycle` and the package workflow gate.

### Ownership Check

- `feature-lifecycle`: branch, phase, documentation carrier, commit/push cadence.
- `implementation-execution`: F4 slices, risk gates, implementation evidence,
  and `ready_for_review` handoff.
- formal review: independent decision after F4/F5 evidence exists.

No circular phase ownership or package dependency is introduced.

### Rollback

Revert the S2 commit. The standalone implementation skill remains usable, and
the lifecycle returns to its prior generic F4 rules.
