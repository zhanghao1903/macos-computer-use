# Technical Review Remediation: Accessibility Selector Engine

- Remediation date: 2026-07-08
- Source review: `technical-review-2026-07-06.md`
- Revised design: `design.md`
- Implementation plan: `implementation-plan.md`
- Follow-up review: `technical-review-2026-07-07.md`
- Lifecycle phase: F2/F3 handoff hardening

## Purpose

The 2026-07-06 technical review failed the first Accessibility Selector Engine
design because the architecture direction was sound, but the plan was not yet
implementation-ready. The blocking issues were field-level contract gaps,
undefined referenced types, incomplete object lifecycle rules, unresolved
package-boundary decisions, underspecified recovery behavior, and an overly
coarse migration plan.

This remediation record makes the improvement traceable. It records where each
review issue is now handled and what implementation evidence is required before
a later slice can claim completion.

## Remediation Summary

| 2026-07-06 review issue | Remediated in plan | Implementation gate | Acceptance evidence |
| --- | --- | --- | --- |
| Field-level contract incomplete. | `design.md` `Field Contract Matrix` and `Helper Type Field Matrix`. | Slice 1 must implement model validation from the matrix before resolver behavior. | Validation tests for required/default fields, enum values, invalid references, cycles, regexes, bounds, cache policy, relation policy, pagination policy, diagnostics policy, and action risk. |
| Referenced helper types missing. | `design.md` `Referenced Type Definitions` defines `JsonValue`, `PickStrategy`, `Frame`, `SelectorEvidence`, `ActionDefinition`, `CachePolicy`, `RelationRule`, `PaginationPolicy`, `CollectionDiagnosticsPolicy`, `CollectionResult`, and `PaginationState`. | Slice 1 must either implement each helper type or explicitly defer it in `implementation-notes.md` with owner and follow-up slice. | Tests can construct full profiles, selector results, collection results, actionRefs, and cache entries without ad hoc dictionaries. |
| Core object lifecycle incomplete. | `design.md` `Core Object Lifecycle`. | Slices 1-4 must add lifecycle tests for profiles, selector results, collection results, actionRefs, and cache entries. | Tests cover invalid overrides, profile supersession, selector states, partial collections, stale cache fallback, expired actionRefs, and precondition rejection. |
| Implementation-boundary decisions left open. | `design.md` `Resolved Architectural Decisions` and `Runtime Ownership`. | Any change to profile storage, public API timing, transform ownership, cache locality, locale fallback, resolver ownership, or WeChat semantic response shape requires design update and re-review. | PR/MR text and implementation notes state that the MVP is internal-only and process-local. |
| Failure and recovery under-specified. | `design.md` `Failure Kinds And Recovery`. | Resolver and WeChat adapters must preserve generic selector failure kinds in diagnostics while mapping to app-specific failures. | Unit tests cover not-found, ambiguity, truncation, profile invalid, field missing, stale cache, expired actionRef, precondition failure, and bounded retry behavior. |
| Public API migration too high-level. | `design.md` `API Direction` and `Implementation Slices And Handoff Gates`; `implementation-plan.md` `Review Remediation Gates By Slice`. | Slices 1-5 must not add public selector protocol commands. Slice 6 requires a separate public protocol proposal. | Release readiness confirms no premature public schema, CLI, local-service command, or stable config field. |
| Direct/helper/local-service ownership not reconciled. | `design.md` `Runtime Ownership`. | MVP resolver state and cache stay in the Python caller process and use the configured transport for underlying AX query/action operations. | Fake transport tests and later parity tests prove consistent direct/helper/local-service behavior before public selector commands. |

## Current Design Decisions

| Decision | Current plan | Why this closes the review gap |
| --- | --- | --- |
| Profile storage | Packaged defaults live in semantic packages such as `wechat-desktop-tool`; applications may inject validated overrides later. | Keeps `computer-use-macos` generic and avoids embedding app labels or semantics in the generic layer. |
| Public API timing | Generic selector commands remain internal until WeChat migration and parity proof pass. | Avoids freezing unstable protocol shapes before real fixtures and smoke proof validate the model. |
| Transform ownership | Generic transforms are allowlisted scalar transforms; domain transforms stay in adapters. | Prevents selector profiles from becoming unreviewed executable logic. |
| Cache locality | Cache is in-memory per resolver instance for the MVP. | Avoids cross-process persistence, privacy, and invalidation complexity. |
| Locale fallback | Profiles define explicit alias order; system locale may choose an alias group but does not infer labels alone. | Handles app-version and app-language drift without relying on unreliable global locale state. |

## Implementation Traceability Rules

Every implementation slice must keep the remediation evidence current:

1. Update `implementation-notes.md` with the matrix rows, lifecycle states, and
   review gaps handled by that slice.
2. Update `verification.md` with commands, test results, fixtures, skipped
   checks, and any real macOS proof that applies.
3. Keep the generic selector API internal until the Slice 6 public API gate.
4. Record any deferred matrix row with owner, reason, target slice, and required
   test.
5. Trigger re-review before merge if implementation changes an architectural
   decision listed above.

## Required Proof By Slice

| Slice | Proof required before the slice is complete |
| --- | --- |
| Slice 1: internal contract and profile validation | Model/profile validation tests; no public exports or protocol changes. |
| Slice 2: selector resolver | Resolver tests for cache hit/stale/disabled states, ambiguity, not-found, truncation, redacted evidence, and bounded query behavior. |
| Slice 3: collection extraction | Fixture tests for visible-window limits, skipped rows, required field failures, partial results, and transform allowlist enforcement. |
| Slice 4: WeChat profile and semantic migration | WeChat fixture tests for contacts, conversations, visible messages, open contact, stale selectors, ambiguous selectors, and semantic failure mapping. |
| Slice 5: config override path | Override activation/fallback tests, invalid override rejection, locale alias order tests, and logging redaction checks. |
| Slice 6: public protocol proposal | Protocol/schema tests, direct/helper/local-service parity tests, stable docs, migration notes, release preflight, and changelog entry. |

## Remaining Non-Blocking Risks

- The field matrix is intentionally broad. Implementation must mark rows as
  implemented, revised, or deferred to avoid drift between plan and code.
- Real WeChat smoke proof remains mandatory before merge/release readiness for
  selector-backed WeChat behavior.
- Public selector protocol commands remain out of scope until the separate
  public API proposal is written and reviewed.

## Next Step

Proceed with F3/F4 Slice 1 only: implement internal model dataclasses and
profile validation in `computer-use-macos`, update `implementation-notes.md`
and `verification.md`, then commit and push that slice independently.
