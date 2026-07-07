# Accessibility Selector Engine Requirements

Status: F1 requirement confirmation, revised after the 2026-07-06 technical
review.

Feature branch: `codex/accessibility-selector-engine`.
Feature directory: `docs/feature/accessibility-selector-engine/`.
Design artifact: `design.md`.
Review artifact: `technical-review-2026-07-06.md`.

## Background

macOS Accessibility returns a large graph of UI elements. Absolute paths such
as `0/12/2/0/353/0/1` are useful for debugging, but they are not reliable as
application contracts. WeChat Desktop made this visible because contacts,
navigation tabs, message rows, and search controls can be found in the tree,
but their exact paths may change by version, locale, selected tab, or window
layout.

The feature needs to turn raw Accessibility graph search into reusable,
bounded, profile-driven selectors. Application developers should receive
semantic, actionable results instead of needing to inspect raw AX dumps.

## User And Developer Scenarios

| Scenario | Current problem | Required outcome |
| --- | --- | --- |
| Inspect WeChat window state | The caller receives raw or incomplete window data that does not clearly describe next actions. | The adapter can return normalized landmarks, visible regions, and actionable references. |
| List visible contacts | Fixed AX paths are brittle and full-window scans are slow. | The selector engine resolves the contacts tab, main content, contact table, row items, and display-name fields using bounded queries. |
| Read visible messages | Message rows require repeated region and field extraction. | The collection extractor can scan a bounded message region and return semantic fields with pagination diagnostics. |
| Open or switch contact | Coordinate clicks and text entry are unsafe without target verification. | The adapter resolves an action target, carries risk metadata, verifies preconditions, and fails closed when stale. |
| Update WeChat selectors after UI drift | Package consumers should not need a repackaged wheel for every locator change. | A validated profile override can replace labels, selectors, limits, and fallback order while packaged defaults remain available. |
| Reuse the graph-search capability for other apps | The WeChat-specific solution should not live in generic traversal code. | `computer-use-macos` owns generic selector resolution; app packages own semantic profiles and mappings. |

## Goals

- Provide a reusable selector engine in `computer-use-macos`.
- Keep WeChat-specific labels, row classification, and semantic models in
  `wechat-desktop-tool`.
- Treat AX paths as cache hints that must be revalidated, not as stable
  identity.
- Use bounded Accessibility queries with explicit depth, limit, and time budget.
- Return normalized elements, collection items, action references, confidence,
  and diagnostics.
- Keep raw AX attributes out of normal application-facing responses and logs.
- Support validated profile overrides after packaged profiles and fallback
  behavior are tested.
- Keep the MVP internal until fixture tests and real WeChat smoke proof justify
  public protocol commands.

## Non-Goals

- Do not make `computer-use-macos` depend on WeChat.
- Do not expose full raw AX trees as the main application contract.
- Do not publish `resolve_selector` or `extract_collection` protocol commands
  during the internal MVP.
- Do not use selector profiles as authorization policy.
- Do not allow profile-defined actions to bypass caller confirmation, audit, or
  semantic-package safety checks.
- Do not promise selectors survive arbitrary app redesigns without profile
  updates.

## Requirements From The 2026-07-06 Review

| Requirement | Documentation carrier | Implementation implication |
| --- | --- | --- |
| Define field-level contracts for every proposed object and config shape. | `design.md` field matrices. | Slice 1 validation must implement or explicitly defer every row. |
| Define all referenced helper types and policy objects. | `design.md` referenced type definitions and helper matrix. | Developers must not invent missing types while implementing resolver behavior. |
| Define lifecycle rules for profiles, selector results, collection results, action references, and cache entries. | `design.md` core object lifecycle section. | Slices must add lifecycle tests before claiming completion. |
| Resolve package-boundary decisions before implementation. | `design.md` resolved architectural decisions. | Changes to public API timing, cache locality, profile storage, locale fallback, transform ownership, or semantic response shape require design update and re-review. |
| Expand failure and recovery behavior. | `design.md` failure kinds and recovery table. | Generic failures must be preserved in diagnostics and mapped by app adapters. |
| Split migration into concrete implementation slices. | `implementation-plan.md`. | Each slice must name files, tests, rollback, docs, and proof. |

## Assumptions

- The first implementation is package-private to `computer-use-macos`.
- Existing WeChat semantic API shapes remain compatible while internals migrate
  to selectors.
- The resolver cache is process-local and in-memory for the MVP.
- Profile overrides are validated before activation and may fall back to
  packaged defaults only when explicitly optional.
- Cursor pagination is represented as a future design value but not enabled in
  the MVP.
- Real macOS and real WeChat smoke proof is required before merge readiness,
  even when fixture tests pass.

## Open Decisions

No implementation-blocking decisions remain for the internal MVP after the
2026-07-07 re-review. These decisions remain gated for later phases:

| Decision | Owner | Needed by | Default for MVP |
| --- | --- | --- | --- |
| Public selector protocol commands | `app-control-protocol` and `computer-use-macos` maintainers | Slice 6 | Do not expose protocol commands. |
| Service-owned resolver and cache | `computer-use-macos` maintainers | Future public selector phase | Keep resolver and cache in the Python caller process. |
| Public profile override config | Package maintainers and application integrators | Slice 5 | Keep override loading internal or adapter-owned until validation and fallback tests exist. |
| Higher-risk action support such as text submission | Semantic package and application policy owners | Future safety review | Keep text submission outside selector action definitions. |

