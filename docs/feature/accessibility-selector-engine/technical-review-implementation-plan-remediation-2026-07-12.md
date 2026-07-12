# Technical Plan Review: Accessibility Selector Engine Remediation Implementation Plan

- Review date: 2026-07-12
- Reviewed artifact(s):
  - `docs/feature/accessibility-selector-engine/implementation-plan-remediation-2026-07-12.md`
  - `docs/feature/accessibility-selector-engine/design-remediation-2026-07-12.md`
  - `docs/feature/accessibility-selector-engine/technical-review-remediation-2026-07-12.md`
  - `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-07fa052.md`
- Reviewer stance: Architect handoff readiness for F4 remediation slices
- Final decision: Pass
- Decision summary: The F3 plan translates every approved F2 contract and all
  12 frozen PR findings into bounded implementation slices, exact file owners,
  named counterexample tests, numeric proof thresholds, commit boundaries, and
  rollback rules. It is ready for Slice 1 implementation without an additional
  architecture decision.

## Handoff Judgment

The plan is safe to hand to developers. A developer can identify which package
owns each change, which files may change, which failure and privacy invariants
must hold, and which command proves a slice before it is committed. The ordering
also prevents proof-v2 work from certifying behavior that has not yet landed.

The implementation must preserve the plan's scope controls: helper parity,
public selector commands, multi-element caching, broad static-type cleanup, and
release publication are not part of these slices.

## Mandatory Criteria

| Criterion | Status | Evidence | Gap / required fix |
| --- | --- | --- | --- |
| Requirement background and goals | Pass | Scope, approved design links, and the finding ledger retain the 12 review blockers and desired outcomes. | None. |
| Data structure clarity | Pass | The plan defines selector diagnostics, normalized query outcome, WeChat backend config, disambiguation details, and proof v2. | None. |
| New/changed fields highlighted | Pass | Every field has type, required state, default, owner, validation, and compatibility behavior. | None. |
| Data flow clarity | Pass | Slice dependency flow and per-slice implementation tasks define production and proof ordering. | None. |
| Core object lifecycle | Pass | The approved F2 lifecycle remains authoritative; F3 names exact owners and rollback boundaries. | Keep lifecycle behavior synchronized while implementing. |
| Flow diagram | Pass | The Mermaid dependency diagram makes slice and gate ordering explicit. | None. |
| Developer handoff readiness | Pass | Each slice defines files, tasks, named tests, commands, acceptance, rollback, commit, and push. | None. |

## Qualified Areas

- All 12 `PRR` findings map to exactly one implementation slice and named
  automated proof.
- Safety-critical WeChat changes land before proof generation and require
  command-sequence assertions, not only successful responses.
- Selector cache/failure changes precede collection changes, so paging and batch
  logic can consume one normalized backend-failure contract.
- Proof v2 has numeric minimums and maximums, exact required checks and timings,
  recursive forbidden-field validation, and source-head binding.
- The 0.2.0 package set, release source path, clean wheel install, migration,
  and rollback rules are coordinated in one slice.
- Real macOS interaction remains explicitly authorized and follows deterministic
  tests; it is not used as a substitute for regression coverage.

## Disqualified Gaps And Risks

No blocking or major gaps remain.

| Severity | Issue | Evidence | Impact | Required fix | Blocks pass |
| --- | --- | --- | --- | --- | --- |
| Minor | The shared AX depth constant file is not named. | Slice 3 says to place it in the narrowest dependency-neutral module. | A developer must choose one small internal filename. | Use `computer_use_macos/accessibility_limits.py` or an equally dependency-neutral internal module and cover both imports. | No |
| Minor | The incompatible 0.1.x dependency test source is not prescribed. | Slice 4 requires rejection but allows wheel or metadata-based proof. | Test setup could vary while preserving the same contract. | Prefer deterministic local fixture metadata or locally built baseline wheels; do not depend on network availability. | No |

## Data Structure Review

| Object / schema | Field coverage | New or changed | Type/default coverage | Validation | Compatibility / migration |
| --- | --- | --- | --- | --- | --- |
| `SelectorDiagnostics` | Complete | Two new cause fields and clarified failure/truncation fields. | Complete | Backend cause, retryability, and real truncation are explicit. | Internal additive change. |
| `NormalizedQueryOutcome` | Complete | New private normalized object. | Complete | Successful empty and backend failure cannot collapse. | No protocol change. |
| `WeChatDesktopConfig` | Complete | Add `computer_use_backend`. | `str`, default `direct`. | Helper is rejected at construction. | Existing direct constructors remain valid. |
| `ContactDisambiguationCandidate` | Complete | New bounded error detail. | Complete | No stable-id claim; actionRef only when executable. | Additive ambiguous-result evidence. |
| `WeChatSelectorEngineProofV2` | Complete | New strict release artifact. | Complete | Exact fields, numeric thresholds, head binding, and privacy rejection. | v1 cannot satisfy strict release proof. |

## Data Flow And Lifecycle Review

- Data flow: The plan orders semantic safety, selector normalization, collection
  correctness, runtime compatibility, sanitized proof, and final verification.
- Core object lifecycle: F2 defines cache, candidate, and proof lifecycles; F3
  assigns implementation files, invalidation points, and rollback units.
- Missing transitions or ownership rules: None that block implementation.

## Flow Diagram Review

- Diagram present: yes.
- Diagram adequacy: The dependency flow prevents Slice 3 from preceding query
  normalization and prevents proof v2 from preceding the behavior it certifies.
- Recommended diagram changes: none.

## Implementation Readiness

- Clear implementation path: Yes. Start with Slice 1 and Slice 2; Slice 3
  follows Slice 2; Slice 5 follows Slices 1 through 4.
- Affected modules/components: Exact package source, tests, docs, scripts,
  workflow, version, and lock files are listed.
- Open decisions developers would still need to make: Only internal naming and
  deterministic fixture mechanics; neither changes an approved contract.

## Verification Readiness

- Test strategy: Named negative tests for each review finding, package suites,
  clean wheel/install proof, exact release commands, privacy canaries, and
  authorized real desktop proof.
- Missing proof: Expected until the corresponding F4/F5 slice lands.
- Manual or smoke validation needed: Moved/resized WeChat window, unique-contact
  navigation, non-zero collections, <=3000 ms API timings, and sanitized
  source-bound proof after deterministic checks pass.

## Modification Recommendations

1. Keep each slice commit independent and update `implementation-notes.md` with
   the exact tests and findings closed.
2. Use a dependency-neutral shared AX limits module in Slice 3.
3. Use local deterministic dependency fixtures for the 0.1.x incompatibility
   check instead of relying on package indexes.
4. Do not mark any PR finding closed from the broad suite alone; preserve the
   named counterexample evidence in `verification.md`.

## Re-review Requirements

No additional review is required before Slice 1. Re-review this plan before
continuing if implementation introduces public selector protocol commands,
helper parity, raw release proof, a package version other than the coordinated
0.2.0 set, weaker fail-closed behavior, or different proof thresholds.
