# Merge Readiness: Implementation Execution Skill

- Date: 2026-07-17
- Branch: `codex/implementation-execution-skill`
- Base: `origin/main` at `fed652343ec73734247955d44dc8e60293a7b373`
- Status: `ready_for_review`
- Self-approval: prohibited
- Package/version impact: none

## Scenario Solved

Implementation previously moved directly from an approved plan into code and
tests, leaving cross-layer risk discovery to formal PR review. Repeated review
cycles found avoidable gaps in mutation safety, target identity, query bounds,
configuration/runtime parity, privacy, public contract propagation, clean
packaging, test adequacy, and exact-head evidence.

The new skill makes those concerns part of F4 execution. An implementer must
maintain changed-surface and risk ledgers, define adversarial cases before code,
deliver vertical slices with tests/docs/evidence, run a fresh full-diff pass,
and hand an exact head to independent review.

## Lifecycle Evidence

| Phase | Artifact | Commit | Push |
| --- | --- | --- | --- |
| F0 intake/hygiene | `requirements.md` intake section | `ac7bfdc` | pushed |
| F1 requirements | `requirements.md` confirmed requirements | `6c5e50c` | pushed |
| F2 design/review | `design.md`, `technical-review-2026-07-17.md` | `43e3173` | pushed |
| F3 plan | `implementation-plan.md` | `3ec56d2` | pushed |
| F4 S1 core skill | skill files and `implementation-notes.md` | `61be748` | pushed |
| F4 S2 lifecycle integration | lifecycle/docs integration and notes | `51371fa` | pushed |
| F5 verification | `verification.md` | `01b521c` | pushed |
| F6 readiness/release record | this document, PR description, changelog | this phase commit | pending until committed |

## Changed Surfaces

### Repository Skill

- `.agents/skills/implementation-execution/SKILL.md`
- `.agents/skills/implementation-execution/agents/openai.yaml`
- `.agents/skills/implementation-execution/references/rejection-patterns.md`

The core is 268 lines and uses one one-level progressive-disclosure reference.
It contains no unused scripts, assets, README, or placeholders.

### Lifecycle Integration

- `.agents/skills/feature-lifecycle/SKILL.md`
- `docs/README.md`

F4 now invokes the new skill for non-trivial/risky implementation. Lifecycle
retains phase ownership; implementation execution may return work to F1-F3 or
produce `ready_for_review`, but cannot approve a PR.

### Feature And Release Records

- `docs/feature/implementation-execution-skill/`
- `CHANGELOG.md`

## Verification Summary

- Official `quick_validate.py`: both affected skills valid.
- Core skill: 268 lines, under the 500-line target.
- Placeholder scan: clean.
- Repository release preflight: passed with expected sandbox/external-proof
  warnings only.
- `git diff --check`: passed before every phase/slice commit.
- Four scenario dry runs: public failure propagation, action fallback,
  selector collection paging, and review remediation all exercised the intended
  gates and stop conditions.
- No package source/API/schema/dependency/example changed, so package unit and
  live desktop smoke were not required for this repository-guidance feature.

## Review Focus

An independent reviewer should prioritize:

1. whether the frontmatter triggers implementation but avoids design/review
   ownership conflicts;
2. whether core mandatory gates are concrete enough to change implementation
   behavior rather than produce ceremonial checklists;
3. whether the rejection reference generalizes historical findings without
   duplicating or contradicting the core skill;
4. whether F4 integration preserves feature lifecycle ownership and commit/push
   rules;
5. whether same-agent scenario walkthroughs are sufficient for merge or need a
   fresh-agent forward test.

## Limitations And Residual Risk

- A process skill can reduce foreseeable review failures but cannot guarantee
  a PR will pass on the first review.
- No fresh-agent forward test was available in this task; the same agent used
  raw prompts and disclosed the limitation.
- Version one has no machine implementation-record schema. Add one only after
  real records demonstrate stable semantics that can be validated without
  encouraging keyword-only proof.
- Formal PR approval, merge, and release remain separate authorized actions.

## Merge Checklist

- [x] Dedicated feature branch and isolated worktree.
- [x] Requirements, design, technical review, and implementation plan.
- [x] Core skill and UI metadata validated.
- [x] Rejection patterns derived from the full review chain.
- [x] `feature-lifecycle` F4 integration documented and validated.
- [x] Scenario dry runs and limitations recorded.
- [x] Internal changelog entry.
- [x] No package or runtime migration.
- [ ] Independent PR review.
- [ ] Exact-head CI after the F6 commit.

## Decision

Implementation status is `ready_for_review`. This document does not claim
`APPROVE`, mergeability, or release readiness.
