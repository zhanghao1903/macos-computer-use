# Technical Plan Review: Accessibility Selector Engine Review Remediation Design

- Review date: 2026-07-12
- Reviewed artifact(s):
  - `docs/feature/accessibility-selector-engine/design-remediation-2026-07-12.md`
  - `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-07fa052.md`
  - `docs/feature/accessibility-selector-engine/design.md`
  - `docs/feature/accessibility-selector-engine/implementation-plan.md`
  - `docs/feature/accessibility-selector-engine/verification.md`
- Reviewer stance: Architect handoff readiness for an F2 remediation design
- Final decision: Pass
- Decision summary: The remediation design is clear enough to approve as the
  revised F2 design for the 12 frozen PR review blockers. It is not, by its own
  gate, a direct code-start artifact; F3 still requires a separately versioned
  implementation plan before any remediation slice begins.

## Handoff Judgment

I would be comfortable handing this document to an implementation-plan owner and
expecting them to produce the F3 slice plan without rediscovering the
architecture. The document explains the safety, privacy, compatibility,
collection, cache, backend-failure, release-proof, and helper-mode decisions
with concrete contracts, diagrams, lifecycles, and acceptance proof.

I would not treat this review as permission to start code immediately. The
reviewed document explicitly says a separate implementation plan and new-head
technical review are required before code work and merge readiness. That
constraint is coherent and should remain a hard gate.

## Mandatory Criteria

| Criterion | Status | Evidence | Gap / required fix |
| --- | --- | --- | --- |
| Requirement background and goals | Pass | `Problem`, `Goals`, `Non-Goals`, and `Consumer Scenarios` define the unsafe states, user-facing recovery needs, privacy risk, compatibility target, and scoped exclusions. | None for F2. |
| Data structure clarity | Pass | `SelectorDiagnostics`, `NormalizedQueryOutcome`, `ContactDisambiguationCandidate`, and `WeChatSelectorEngineProofV2` define the relevant remediation objects and fields. | F3 plan should preserve these as implementation tables with exact module/file owners. |
| New/changed fields highlighted | Pass | `SelectorDiagnostics` marks new and clarified fields; the new outcome, candidate, and proof-v2 objects define field-level type, required status, validation, and privacy rules. | Add explicit default/owner/compatibility columns when converting to the F3 implementation plan. |
| Data flow clarity | Pass | Three Mermaid diagrams cover safe `open_contact`, selector/cache resolution, and privacy-safe proof publication. | None for F2. |
| Core object lifecycle | Pass | Cache entry, contact candidate, and release proof lifecycles define creation, validation, expiry/deletion, and persistence boundaries. | ActionRef lifecycle is referenced through existing policy; F3 should point to the exact implementation owner. |
| Flow diagram | Pass | The document includes sequence and flowchart diagrams for the critical runtime and release-proof paths. | None. |
| Developer handoff readiness | Pass | Package ownership, failure/recovery contract, test strategy, and six implementation handoff slices define the implementation path. | Code must not start until the separate F3 implementation plan supplies exact file/module tasks and command-level verification. |

## Qualified Areas

- The design directly maps all 12 frozen PR findings to revised contracts and
  planned proof, which makes closure traceable.
- The highest-risk user-safety paths now fail closed: unknown search focus,
  same-name ambiguity, stale/missing frame evidence, stale cache hits, backend
  query failures, and unsafe helper mode.
- The release-proof redesign is appropriately privacy-first: proof v2 is
  whitelist based, source-head bound, schema validated, and rejects raw
  observations plus sensitive fields.
- The design keeps package boundaries clean: generic selector behavior remains
  in `computer-use-macos`, WeChat semantics remain in `wechat-desktop-tool`,
  and no public selector protocol command is introduced.
- The verification strategy includes deterministic negative tests, clean
  package install proof, release workflow proof, and explicitly authorized real
  macOS proof.

## Disqualified Gaps And Risks

No blocking gaps remain for F2 design approval.

| Severity | Issue | Evidence | Impact | Required fix | Blocks pass |
| --- | --- | --- | --- | --- | --- |
| Major | The document is not a direct code-start plan by design. | It says a separate implementation plan and new-head review are required before code work; the handoff slices also require the implementation plan before any code slice begins. | A developer could otherwise skip file-level decomposition and verification commands. | Create the F3 implementation plan before code work. | No |
| Minor | Field tables should become stricter in F3. | Some new objects are clearly defined but do not all carry explicit default, owner, and compatibility columns. | Implementation reviewers may need to infer defaults or field ownership if the F3 plan copies these tables unchanged. | Add default, owner, validation, and compatibility/migration columns for every field in the F3 plan. | No |
| Minor | Release proof minimums should be made numeric in the F3 plan. | Proof v2 requires operation-specific minimum counts and real proof reads non-zero samples. | Tests are clear in direction, but exact thresholds should be machine-checkable. | State exact minimum counts for contacts, conversations, and visible messages in the implementation plan and validator tests. | No |

## Data Structure Review

| Object / schema | Field coverage | New or changed | Type coverage | Required/default coverage | Validation coverage | Compatibility / migration note |
| --- | --- | --- | --- | --- | --- | --- |
| `SelectorDiagnostics` | Complete for remediation fields. | New `cause_failure_kind`, `retryable`; clarified `failure_kind`, `message`, `truncated`, `truncation_reason`. | Present. | Required status present; defaults should be restated in F3. | Failure cause and truncation semantics are clear. | Supports preserving backend causes without changing public protocol commands. |
| `NormalizedQueryOutcome` | Complete for backend availability and failure normalization. | New internal normalization contract. | Present. | Required status present; defaults/legacy behavior described for `available`. | Clear distinction between backend failure and empty successful query. | Internal to `computer-use-macos`; F3 should name exact modules. |
| `ContactDisambiguationCandidate` | Complete for ambiguous contact summaries. | New semantic object inside `contact_ambiguous`. | Present. | Required status present. | Privacy and non-durable identity rules are clear. | Does not create a stable contact id or new top-level API method. |
| `WeChatSelectorEngineProofV2` | Complete for sanitized release proof. | New proof schema version. | Present. | Required status present; `failedStep` must be null. | Schema, head SHA, count consistency, forbidden keys, and sensitive scans are defined. | Supersedes proof v1 for strict/bundleable release proof. |

## Data Flow And Lifecycle Review

- Data flow: The plan describes application calls into WeChat semantic methods,
  bounded AX query/action behavior, cache validation, backend failure mapping,
  and release proof sanitization from raw in-memory observations to validated
  public assets.
- Core object lifecycle: Cache entries, contact candidates, and release proofs
  have creation, validation, invalidation, expiry/deletion, persistence, and
  publication rules.
- Missing transitions or ownership rules: No F2 blocker. F3 should assign exact
  implementation files and tests for ActionRef expiration and proof validator
  ownership.

## Flow Diagram Review

- Diagram present: yes.
- Diagram adequacy: Adequate for F2. The diagrams cover the critical unsafe
  execution paths and the release-proof data path.
- Recommended diagram changes: None required. The F3 implementation plan may
  add a slice-level dependency diagram if multiple owners work in parallel.

## Implementation Readiness

- Clear implementation path: Yes for F2 to F3 handoff. The six slices are
  correctly grouped by risk and package boundary.
- Affected modules/components: Package/component owners are clear:
  `app-control-protocol`, `computer-use-macos`, `wechat-desktop-tool`,
  `examples/`, `scripts/`, and `.github/workflows/`.
- Open decisions developers would still need to make: No architecture decision
  remains open for F2. Developers still need the F3 plan to translate slices
  into exact files, tests, commit order, and verification commands.

## Verification Readiness

- Test strategy: Strong. It includes deterministic tests for every PRR finding,
  clean-environment install proof, release command proof, proof schema tests,
  and authorized real macOS proof.
- Missing proof: No proof is expected at F2. F3 must define exact commands and
  CI/preflight entry points.
- Manual or smoke validation needed: Real macOS proof remains mandatory before
  merge/release readiness, but it is correctly sequenced after deterministic
  tests and explicit desktop authorization.

## Modification Recommendations

1. Write `implementation-plan-remediation-2026-07-12.md` before code work,
   preserving the six slices and adding exact file/module tasks, targeted test
   commands, and commit boundaries.
2. Expand the F3 field matrix with explicit default, owner, validation, and
   compatibility/migration columns for every new or changed field.
3. Make proof-v2 minimum evidence thresholds numeric and machine-checkable.
4. Keep helper parity, multi-element cache, candidate-selection API, and broad
   type-checking cleanup as follow-up features unless a design update is
   reviewed.

## Re-review Requirements

No F2 re-review is required before writing the remediation implementation plan.
Re-review is required if the implementation plan changes any approved
architecture decision, introduces public selector protocol commands, weakens
fail-closed safety, publishes raw proof data, changes the coordinated package
version strategy, or starts helper parity in this remediation scope.
