# Verification: Implementation Execution Skill

- Date: 2026-07-17
- Tested implementation head: `51371fa`
- Worktree: `/private/tmp/macos-computer-use-implementation-execution-skill`
- Scope: repository skills and workflow documentation only
- Live mutation or external publication: none

## Automated Checks

| Check | Command | Result |
| --- | --- | --- |
| New skill structure/frontmatter | `/opt/anaconda3/bin/python3 /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/implementation-execution` | `Skill is valid!` |
| Updated lifecycle skill | Same validator against `.agents/skills/feature-lifecycle` | `Skill is valid!` |
| Core/reference size | `wc -l .../SKILL.md .../references/rejection-patterns.md` | Core 268 lines; reference 342 lines; core remains below 500 lines. |
| Placeholder scan | `rg -n "TODO|\\[TODO" ...` | No placeholders found. |
| Lifecycle integration | `rg -n "implementation-execution|ready_for_review|return to F1-F3" ...` | F4 invocation, blocked return path, and non-approval handoff are present. |
| Repository preflight | `/opt/anaconda3/bin/python3 scripts/release_preflight.py` | Passed. One expected sandbox Unix-socket warning and six unavailable external-proof warnings; no errors. |
| Whitespace | `git diff --check` before each implementation commit | Passed. |

The skill folder contains only `SKILL.md`, `agents/openai.yaml`, and the one
referenced pattern document. It has no README, placeholder example, script,
asset, or unused resource directory.

## Scenario Dry Runs

These walkthroughs applied the final skill to raw implementation requests. They
evaluate the decisions and evidence the skill requires, not only whether a
keyword exists. No code or external state was changed.

### Scenario 1: Add A Public Worker Failure

**Raw request:** "Add `accessibility_query_worker_crashed` when the warm worker
dies and expose it through the SDK."

**Gate output:**

- Classifies public API/contract, failure routing, package, dependency, and CI
  surfaces before edits.
- Requires anticipated paths for producer, normalizer, error constants,
  registry, package export, docs, consumer/recovery, package tests, wheel checks,
  and dependency floors.
- Defines worker crash, empty response, malformed frame, timeout before/after
  dispatch, duplicate registry value, old dependency, and public wheel import
  counterexamples.
- Blocks a producer-only implementation because registry/export, consumer,
  packaging, and compatibility stages remain `UNKNOWN`.

**Result:** Pass. The workflow would catch the root classes behind `PRR-005`,
`PRR-010`, `PRR-011`, `PRR-025`, and `PRR-036` before review.

### Scenario 2: Fallback After An Accessibility Action

**Raw request:** "When AXPress fails, click the element coordinates as a
fallback so opening a contact still works."

**Gate output:**

- Classifies mutation recovery, target identity, stale reference, coordinate
  authorization, and privacy surfaces.
- Refuses a generic "fails" condition. Requires separate not-dispatched,
  dispatched/performed, dispatched/definite-no-effect, dispatched/unknown,
  timeout, EOF, malformed, duplicate, and contradictory outcomes.
- Requires evidence to match the requested action and current frontmost target.
- Requires operation-count/order assertions for every caller: one AX action and
  zero fallback for unknown/conflict, or at most one fallback for an exact
  reviewed safe tuple.
- Blocks raw coordinate fallback unless policy, current bounds/identity, stale
  path checks, and explicit authorization are present.

**Result:** Pass. The workflow would catch the root classes behind `PRR-002`,
`PRR-003`, `PRR-014`, `PRR-015`, and `PRR-018` through `PRR-026`.

### Scenario 3: Return Thirty Contacts

**Raw request:** "Implement `list_contacts(limit=30)` from the WeChat AX
collection and cache the contacts root."

**Gate output:**

- Classifies selector/config execution parity, query bounds, semantic
  pagination, cache validity, latency, structured failures, and privacy.
- Requires unsupported selector steps/policies to execute fully or fail profile
  validation before a query.
- Distinguishes raw AX rows from accepted contacts and requires one accepted
  lookahead for `hasMore` within depth/node/time/batch limits.
- Rejects candidate-present truncation as a cache or action decision and
  requires cache predicate/signature revalidation.
- Defines empty, exact 30, 31 accepted, noisy rejected rows, stale cache,
  duplicate contacts, permission/timeout/transport/truncation, maximum batch,
  and private-canary cases.
- Requires latency/operation evidence if a three-second API contract is claimed.

**Result:** Pass. The workflow would catch the root classes behind `PRR-004`,
`PRR-006` through `PRR-009`, `PRR-012`, `PRR-016`, `PRR-017`, `PRR-028` through
`PRR-031`, `PRR-033`, `PRR-034`, and `PRR-035`.

### Scenario 4: Fix A Reopened Review Finding

**Raw request:** "Fix PRR-021 by adding `actionAttempted` validation, then
prepare the branch for re-review."

**Gate output:**

- Freezes the prior report, finding, verification criteria, previous head, and
  current base.
- Requires deterministic reproduction and a coherent root-cause slice rather
  than a one-field patch.
- Checks all known metadata/observation/diagnostics/transport/error evidence
  containers, malformed values, contradictions, request binding, and every
  shared fallback caller.
- Separately treats the remediation diff as untrusted and classifies every
  changed path for induced public-contract, privacy, mutation, and evidence
  risk.
- Requires exact-head broad verification and a `ready_for_review` dossier; it
  does not self-approve the fix.

**Result:** Pass. The workflow addresses the repeated reopenings of
`PRR-018`, `PRR-021`, `PRR-022`, and `PRR-026`, plus the evidence failure in
`PRR-027`.

## Acceptance Criteria Check

| Criterion | Status | Evidence |
| --- | --- | --- |
| Precise implementation/remediation trigger | Pass | Frontmatter covers non-trivial implementation, review fixes, public contracts, desktop state, privacy, packaging, and cross-package behavior. |
| Clear ownership boundary | Pass | Core skill and lifecycle integration prohibit design/PR self-approval, merge, publish, and release. |
| Reusable review lessons | Pass | Eleven pattern sections generalize `PRR-001` through `PRR-036`; WeChat details remain examples, not universal rules. |
| Explicit stop conditions | Pass | Missing decisions, replay risk, execution mismatch, unclassified paths, vacuous tests, wrong-head evidence, and unauthorized actions block handoff. |
| Exact review handoff | Pass | Base/head, commits/files, risk surfaces, propagation, validation, limitations, and reviewer focus are required. |
| Official skill validation | Pass | Both affected skill folders are valid. |
| Three or more realistic dry runs | Pass | Four scenario walkthroughs above. |

## Checks Not Run

- Fresh-agent forward test: no subagent/fresh-agent execution capability was
  available in this task. The same agent restarted each walkthrough from the
  raw request and disclosed that limitation.
- Package unit suites: no package source, protocol, schema, dependency, or
  executable example changed. Repository release preflight and CI are the
  proportional gates.
- Live macOS/WeChat smoke: not relevant to a repository guidance-only feature
  and not authorized by this task.
- Package build/publication: no package artifact or version changed.

## Residual Risks

- A process skill reduces foreseeable omissions but cannot replace independent
  engineering review or guarantee zero findings.
- The first version relies on semantic records rather than a machine schema;
  consistency depends on disciplined lifecycle use and future real-task
  feedback.
- Trigger overlap with lifecycle and review skills requires agents to preserve
  the ownership boundaries stated in the skill metadata and body.

## F5 Status

`ready_for_review` for the repository-skill feature after this verification
record is committed and pushed. Formal PR approval remains external.
