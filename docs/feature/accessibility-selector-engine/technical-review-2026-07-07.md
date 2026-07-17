# Technical Plan Review: Accessibility Selector Engine Technical Design

- Review date: 2026-07-07
- Reviewed artifact(s):
  - `docs/feature/accessibility-selector-engine/design.md`
  - `docs/feature/accessibility-selector-engine/technical-review-2026-07-06.md`
  - `docs/architecture/computer-use-macos.md`
  - `docs/architecture/wechat-desktop-tool.md`
  - `docs/api.md`
- Reviewer stance: Architect handoff readiness
- Final decision: Pass
- Decision summary: The revised design closes the blocker gaps from the
  2026-07-06 review. It is now sufficiently clear for developers to proceed to
  implementation planning, with remaining risks tracked as implementation-phase
  details rather than design blockers.

## Handoff Judgment

I would hand this revised plan to developers for F3 implementation planning.
The design now explains the problem, goals, package ownership, proposed data
contracts, helper types, field-level validation, object lifecycles, runtime
ownership, failure recovery, implementation slices, rollback paths, and
verification gates. It also keeps the MVP internal, which prevents premature
public protocol freeze while WeChat migration and real macOS proof validate the
model.

The plan should not be treated as permission to implement all public protocol
surfaces immediately. The approved handoff is for the internal selector engine,
WeChat semantic migration, and gated proof work described in the implementation
slices.

## Mandatory Criteria

| Criterion | Status | Evidence | Gap / required fix |
| --- | --- | --- | --- |
| Requirement background and goals | Pass | Problem, goals, non-goals, and ownership are defined in `design.md` lines 51-95. | None. |
| Data structure clarity | Pass | Core dataclasses are defined in lines 97-425; helper types are defined in lines 442-546. | Keep implementation dataclasses aligned with the field matrix. |
| New/changed fields highlighted | Pass | Contract status and field matrix are defined in lines 427-625, including new/internal/future-public status and validation notes. | None blocking. |
| Data flow clarity | Pass | Main data flow and runtime ownership are defined in lines 711-756. Selector and collection flows include failure branches in lines 758-819. | None blocking. |
| Core object lifecycle | Pass | Profile, selector result, collection result, actionRef, and cache lifecycles are defined in lines 627-709. | None blocking. |
| Flow diagram | Pass | Mermaid data flow, selector resolution, collection extraction, and WeChat sequence diagrams are present in lines 711-859. | None. |
| Developer handoff readiness | Pass | Resolved architecture decisions are in lines 1048-1056; implementation slices, tests, rollback, and proof are in lines 1058-1193. | Continue with F3 implementation planning before code changes. |

## Qualified Areas

- The revised plan directly responds to the failed 2026-07-06 review and lists
  the addressed gaps in `design.md` lines 32-49.
- Package boundaries are clear: `computer-use-macos` owns generic selector
  resolution, `wechat-desktop-tool` owns WeChat profiles and semantic mapping,
  and applications own authorization and audit.
- The MVP scope is appropriately conservative: selector contracts remain
  internal until WeChat migration, parity tests, docs, and smoke proof justify a
  public protocol proposal.
- The field matrix is detailed enough for implementation planning and prevents
  developers from inventing default/validation behavior ad hoc.
- Runtime ownership is explicit across direct, helper, local-service, and future
  service-owned selector modes.
- Failure kinds now include producer, recoverability, retry behavior, semantic
  mapping, and expected caller response.
- Implementation slices name package boundaries, candidate modules, tests,
  rollback paths, and public API phase gates.

## Disqualified Gaps And Risks

| Severity | Issue | Evidence | Impact | Required fix | Blocks pass |
| --- | --- | --- | --- | --- | --- |
| Minor | The field matrix is broad and may be hard to keep synchronized during implementation. | `design.md` lines 548-625. | Drift between plan and code can appear as models evolve. | In F3, make each implementation slice identify which rows it implements and which rows remain proposed. | no |
| Minor | Public protocol proposal remains intentionally deferred. | `design.md` lines 957-992 and 1170-1179. | Stakeholders may expect `resolve_selector` or `extract_collection` commands too early. | Keep PR/MR descriptions explicit that the first implementation is internal-only. | no |
| Minor | Manual WeChat proof is still required before release readiness. | `design.md` lines 1138-1145 and 1181-1193. | Automated tests alone cannot prove real macOS Accessibility behavior. | Record real smoke evidence in `verification.md` during F5. | no |

## Data Structure Review

| Object / schema | Field | New or changed | Type | Required | Default | Validation | Compatibility / migration note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Selector profile schema | All profile/app/selector/collection/action fields | New internal, future public | Defined in dataclasses and matrix | Defined per row | Defined per row | Field matrix lines 548-625 | MVP remains internal; public exposure requires later protocol proposal. |
| Helper policy types | `PickStrategy`, `CachePolicy`, `RelationRule`, `PaginationPolicy`, diagnostics, evidence | New | Defined in lines 442-546 | Defined in matrix | Defined in matrix | Helper types and matrix now close the previous missing-type blocker. | Keep package-private until API review. |
| Runtime result types | `SelectorResult`, `CollectionResult`, `ActionRef`, `SelectorCacheEntry` | New internal | Defined in lines 357-425 and 525-546 | Defined in matrix | Defined in matrix | Lifecycle and runtime ownership clarify validity and stale handling. | Future public schema must be additive or documented in migration notes. |

## Data Flow And Lifecycle Review

- Data flow: Clear. Application-facing data remains semantic; raw AX values stay
  bounded evidence and are redacted by default.
- Core object lifecycle: Complete enough for implementation planning. The plan
  covers profile activation/rejection/supersession, selector result states,
  collection partial/failure behavior, actionRef authorization/prechecks, and
  cache stale/expiry/delete paths.
- Missing transitions or ownership rules: No blocker. F3 should turn lifecycle
  states into explicit tests for cache stale behavior, invalid overrides,
  actionRef precondition failures, and collection partial results.

## Flow Diagram Review

- Diagram present: yes.
- Diagram adequacy: Adequate for developer handoff. Diagrams cover the primary
  happy paths and text now covers failure branches.
- Recommended diagram changes: Optional only. If implementation uncovers more
  service/runtime divergence, add a sequence diagram for helper/local-service
  parity before proposing public selector commands.

## Implementation Readiness

- Clear implementation path: Yes. The design provides six slices: internal
  contract/profile validation, resolver, collection extraction, WeChat
  migration, config overrides, and future public protocol proposal.
- Affected modules/components: Candidate modules are named for
  `computer-use-macos`, `wechat-desktop-tool`, and possible future
  `app-control-protocol` config work.
- Open decisions developers would still need to make: No blocker. The prior
  open questions are resolved for MVP in the architecture decision table.

## Verification Readiness

- Test strategy: Adequate. The design calls for profile validation, matching,
  cache lifecycle, failure recovery, collection extraction, WeChat fixture
  extraction, package-boundary tests, release preflight where public docs change,
  and real macOS smoke proof.
- Missing proof: Real WeChat smoke and public-protocol parity proof remain
  future phase requirements, not F2 blockers.
- Manual or smoke validation needed: Required during F5 for contact listing,
  conversation listing, visible messages, profile override failure, stale cache
  fallback, and actionRef precondition rejection.

## Modification Recommendations

1. In F3, create `implementation-plan.md` that maps each slice to concrete
   commits, test files, and docs updates.
2. Treat the field matrix as the implementation checklist and mark rows as
   implemented, deferred, or revised during F4.
3. Keep the first PR/MR internal-only. Do not expose public selector commands
   until WeChat migration and parity proof pass.
4. Add `verification.md` during F5 with automated commands, fixture names,
   skipped checks, and real macOS smoke evidence.

## Re-review Requirements

No design re-review is required before F3 implementation planning. Re-review is
required if implementation changes any of these assumptions:

1. Generic selector commands become public earlier than the documented phase
   gate.
2. Resolver/cache ownership moves into the helper or local service during MVP.
3. Profile overrides become public config before validation and fallback tests
   exist.
4. ActionRefs expand into text submission or other high-risk mutating actions.
5. The WeChat semantic response shapes change instead of remaining compatible.
