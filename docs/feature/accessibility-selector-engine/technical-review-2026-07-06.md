# Technical Plan Review: Accessibility Selector Engine Technical Design

- Review date: 2026-07-06
- Reviewed artifact(s):
  - `docs/feature/accessibility-selector-engine/design.md`
  - `docs/architecture/computer-use-macos.md`
  - `docs/architecture/wechat-desktop-tool.md`
  - `docs/api.md`
- Reviewer stance: Architect handoff readiness
- Final decision: Fail
- Decision summary: The design has a strong architecture direction and enough
  diagrams to explain the intended selector flow. It is not yet safe to hand to
  developers as an implementation-ready plan because field-level contracts,
  lifecycle rules, and several boundary decisions remain unresolved.

## Handoff Judgment

I would not hand this plan to developers yet without a revision. The proposal
clearly explains why selector resolution belongs in `computer-use-macos`, how
WeChat should consume selector profiles, and how bounded queries should avoid
raw tree contracts. However, the design still leaves developers to infer
several implementation-critical details: exact field ownership and validation,
which proposed fields are new or changed public contracts, lifecycle rules for
profiles/results/action references/cache entries, and open architectural choices
that affect package boundaries and protocol stability.

## Mandatory Criteria

| Criterion | Status | Evidence | Gap / required fix |
| --- | --- | --- | --- |
| Requirement background and goals | Pass | The problem, goals, non-goals, and ownership boundaries are stated in `design.md` lines 31-75. | None blocking. |
| Data structure clarity | Fail | The plan defines major dataclasses in `design.md` lines 77-405. | Several referenced types are not defined, including `ActionDefinition`, `PickStrategy`, `CachePolicy`, `RelationRule`, `PaginationPolicy`, `CollectionDiagnosticsPolicy`, `SelectorEvidence`, `Frame`, and `JsonValue`. Required/optional/default/validation rules are not consistently specified per field. |
| New/changed fields highlighted | Fail | The plan says contracts are proposal-level in `design.md` lines 77-81. | New fields and changed fields are not explicitly marked. Add a field matrix for every proposed object with new/changed status, type, requiredness, default, validation, owner, compatibility, and migration notes. |
| Data flow clarity | Pass | End-to-end data flow and selector/collection flows are shown in `design.md` lines 407-477, with a WeChat sequence in lines 479-507. | Add failure and retry paths to the diagrams or surrounding text before implementation planning. |
| Core object lifecycle | Fail | Cache validation is partially described in `design.md` lines 389-405 and 519-542. | Lifecycle is not complete for selector profiles, selector results, action references, collection results, and cache entries. Define creation, update, ownership, persistence, expiration, invalidation, deletion, and observable states. |
| Flow diagram | Pass | The design includes data flow, selector resolution, collection extraction, and WeChat sequence diagrams in `design.md` lines 407-507. | Diagrams are sufficient for current review; failure paths can be strengthened. |
| Developer handoff readiness | Fail | Migration steps are listed in `design.md` lines 690-704 and open questions in lines 706-716. | The open questions include implementation-blocking decisions: profile storage, public API timing, transform ownership, cache locality, and locale fallback. Resolve or explicitly assign decisions before implementation. |

## Qualified Areas

- The package boundary is directionally sound: generic selector resolution stays
  in `computer-use-macos`, while WeChat-specific profiles and semantic mapping
  stay in `wechat-desktop-tool`.
- The plan correctly treats AX paths as cache hints rather than stable
  contracts.
- The design includes concrete examples for selector profiles, structural
  constraints, collection extraction, action references, diagnostics, and config
  overrides.
- The performance strategy is aligned with the repository architecture: bounded
  queries, stable landmarks, scoped traversal, cache validation, and truncation
  diagnostics.
- The privacy and safety section correctly calls out raw AX payload risk and
  separates read-only selectors from mutating actions.
- The testing strategy covers core selector behavior, fixture-based WeChat
  extraction, stale cache fallback, ambiguity, and manual smoke proof.

## Disqualified Gaps And Risks

| Severity | Issue | Evidence | Impact | Required fix | Blocks pass |
| --- | --- | --- | --- | --- | --- |
| Blocker | Field-level contract is incomplete. | Dataclasses are listed in `design.md` lines 88-405, but many fields lack required/default/validation/migration rules. | Developers may implement incompatible shapes or accidentally freeze unstable contracts. | Add a complete field matrix for every object and config shape. Mark each field as new or changed. | yes |
| Blocker | Referenced types are missing or undefined. | The design references types such as `ActionDefinition`, `PickStrategy`, `CachePolicy`, `RelationRule`, `SelectorEvidence`, and `JsonValue` without definitions. | Developers must invent semantics, which creates inconsistent implementations and review churn. | Define each referenced type or explicitly mark it out of scope with an owner and follow-up artifact. | yes |
| Blocker | Core object lifecycle is not complete. | Cache entry lifecycle is partially covered in `design.md` lines 389-405, but profile, selector result, action reference, and collection result lifecycles are not. | Cache invalidation, profile overrides, actionRef reuse, and result observability may diverge across direct/helper/service modes. | Add lifecycle sections for profile, selector result, actionRef, collection result, and cache entry. | yes |
| Blocker | Open questions contain implementation-boundary decisions. | `design.md` lines 706-716 leave profile storage, API exposure, transform ownership, cache locality, and locale fallback unresolved. | Developers cannot choose package boundaries or public/private APIs confidently. | Decide these before implementation or split the plan into explicit implementation phases with owners and decision deadlines. | yes |
| Major | Failure and recovery behavior is under-specified. | Failure kinds are listed in `design.md` lines 569-584, but caller recovery and mapping behavior are only briefly mentioned. | Callers and semantic packages may handle failures inconsistently. | For each failure kind, define producer, recoverability, retry behavior, semantic mapping, and expected caller response. | no |
| Major | Public API migration path is too high-level. | API direction is deferred in `design.md` lines 609-634 and migration steps appear in lines 690-704. | It is unclear which implementation slice changes internal APIs only and which later changes protocol/schema contracts. | Add phase gates: internal-only MVP, WeChat migration, public protocol proposal, docs/tests/migration note requirements. | no |
| Major | Direct/helper/service behavior is not explicitly reconciled. | The design mentions `accessibility_query` and `accessibility_action`, but does not define where resolver state and cache live across runtime modes. | Behavior may differ between direct client, helper transport, and local service. | Define runtime ownership for profile loading, cache storage, snapshot ids, diagnostics, and actionRef execution. | no |

## Data Structure Review

| Object / schema | Field | New or changed | Type | Required | Default | Validation | Compatibility / migration note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AccessibilitySelectorProfile` | `schema_version` | Not specified | `str` | Implied yes | Not specified | Must be explicit per config rules | Needs schema-version compatibility policy. |
| `AccessibilitySelectorProfile` | `profile_id`, `profile_version` | Not specified | `str` | Implied yes | Not specified | Included in diagnostics | Needs ownership and upgrade/downgrade policy. |
| `AccessibilitySelectorProfile` | `actions` | Not specified | `dict[str, ActionDefinition]` | Unknown | Not specified | `ActionDefinition` missing | Define `ActionDefinition` or remove from MVP. |
| `SelectorDefinition` | `pick` | Not specified | `PickStrategy` | Implied yes | Not specified | `PickStrategy` missing | Define allowed values in contract, not only search algorithm prose. |
| `SelectorDefinition` | `cache` | Not specified | `CachePolicy` | Unknown | Not specified | `CachePolicy` missing | Required for cache behavior and invalidation consistency. |
| `SelectorStep` | `relation` | Not specified | `RelationRule \| None` | Optional | `None` implied | `RelationRule` missing | Needed for relative anchors and geometry constraints. |
| `CollectionDefinition` | `pagination`, `diagnostics` | Not specified | `PaginationPolicy`, `CollectionDiagnosticsPolicy` | Unknown | Not specified | Both missing | Needed before collection extraction implementation. |
| `ResolvedElement` | `frame`, `evidence` | Not specified | `Frame \| None`, `SelectorEvidence` | Mixed | Not specified | Both missing | Decide debug/evidence exposure boundary. |
| `ActionRef` | `risk`, `preconditions` | Not specified | Literals / list | Implied yes | Not specified | Partial definition only | Needs execution, reuse, expiry, and confirmation semantics. |
| `SelectorCacheEntry` | `expires_at` | Not specified | `str \| None` | Optional | `None` implied | Partial | Needs TTL/invalidation policy across app version/window changes. |

## Data Flow And Lifecycle Review

- Data flow: The main path is clear. Application calls WeChat semantic APIs,
  WeChat loads a profile and calls the selector resolver, the resolver uses
  bounded `accessibility_query`, normalized elements/actionRefs flow back to
  WeChat, and semantic models flow to the application.
- Core object lifecycle: Incomplete. The design describes cached path validation
  and update behavior, but not the lifecycle for profile loading/override
  selection, selector result snapshots, actionRef validity, collection result
  pagination, or cache eviction.
- Missing transitions or ownership rules: Add explicit transitions for profile
  load -> validate -> active -> superseded/rejected; selector result unresolved
  -> resolved/ambiguous/not_found/stale/failed; actionRef created -> prechecked
  -> executed/rejected/stale/expired; cache entry created -> hit/stale/expired
  -> refreshed/deleted.

## Flow Diagram Review

- Diagram present: yes.
- Diagram adequacy: Sufficient for the happy path and primary selector
  algorithm. The diagrams are good enough to explain the proposed architecture.
- Recommended diagram changes: Add failure branches for query truncation,
  ambiguous matches, stale actionRef execution, override profile validation
  failure, and fallback selector exhaustion.

## Implementation Readiness

- Clear implementation path: Partially. The migration plan gives a reasonable
  order, but it is too coarse to start implementation without follow-up design
  decisions.
- Affected modules/components: The plan identifies `computer-use-macos` and
  `wechat-desktop-tool`, but should name concrete package areas such as profile
  schema modules, resolver module, config loading, helper/local service state,
  WeChat profile data, semantic API adapters, tests, and docs.
- Open decisions developers would still need to make:
  - Whether profiles live in package data, application config, or both.
  - Whether generic selector operations are internal-only for MVP.
  - How much transform logic can be declarative.
  - Whether selector cache is process-local or service-owned.
  - How locale fallback works when app labels differ by app version.

## Verification Readiness

- Test strategy: Good directionally. Unit and fixture tests are listed, and the
  design correctly says manual smoke tests should not be the only proof.
- Missing proof: No acceptance criteria per implementation phase, no contract
  tests for public/private protocol boundaries, no config override failure tests,
  no helper/local-service parity tests, and no explicit migration proof for
  WeChat hard-coded region lookup.
- Manual or smoke validation needed: Real WeChat smoke should verify contact
  list extraction, conversation/message row extraction, profile override
  behavior, stale cache fallback, and actionRef precondition failure.

## Modification Recommendations

1. Add a field-level contract matrix for all proposed dataclasses and TOML
   shapes. Mark each field as new or changed, and define type, requiredness,
   default, validation, owner, compatibility, and migration notes.
2. Define all currently referenced but missing types, or explicitly move them to
   a later phase with non-blocking placeholders.
3. Add a lifecycle section for selector profiles, selector results,
   actionRefs, collection results, and cache entries.
4. Resolve the five open questions or convert them into phase gates with owners
   and acceptance criteria before implementation begins.
5. Expand failure-kind definitions with producer, recoverability, retry rules,
   semantic mapping, and caller response.
6. Split the migration plan into concrete implementation slices with affected
   files/modules, test commands, docs updates, rollout/rollback notes, and
   manual smoke proof.

## Re-review Requirements

Re-review after the design includes:

1. A complete field matrix for proposed objects and config schema.
2. Definitions for all referenced helper types and policy objects.
3. Lifecycle definitions for profile, selector result, actionRef, collection
   result, and cache entry.
4. Decisions or phase gates for profile storage, public API timing, transform
   ownership, cache locality, and locale fallback.
5. A concrete implementation plan that names modules, tests, docs, rollout, and
   rollback proof.
