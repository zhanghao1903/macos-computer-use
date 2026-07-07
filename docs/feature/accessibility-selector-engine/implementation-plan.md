# Accessibility Selector Engine Implementation Plan

Status: F3 implementation plan.

Feature branch: `codex/accessibility-selector-engine`.
Feature directory: `docs/feature/accessibility-selector-engine/`.
Design source: `design.md`.
Review sources:

- `technical-review-2026-07-06.md`
- `technical-review-2026-07-07.md`

## Scope

This plan implements the Accessibility Selector Engine as an internal MVP
before any public selector protocol is added. The first code slice belongs only
to `computer-use-macos` and covers contract dataclasses plus profile validation.

The final feature remains broader than Slice 1:

1. internal selector contract and profile validation;
2. selector resolver over bounded Accessibility queries;
3. collection extraction;
4. WeChat packaged profile and semantic API migration;
5. optional config override path;
6. public protocol proposal only after the internal model is proven.

## Review-Driven Handoff Checklist

The 2026-07-06 technical review is the source of truth for the gaps this plan
must close. Each implementation slice should update this checklist when work is
completed, deferred, or revised.

| Review requirement | Owning slice | Files/modules | Required proof |
| --- | --- | --- | --- |
| Field matrix implemented before behavior. | Slice 1 | `selectors/models.py`, `selectors/validation.py`, `test_selectors.py` | Profile/model validation tests cover required/default fields, unsupported schema versions, invalid references, invalid regexes, unbounded steps, invalid confidence/cache policies, and risky action definitions. |
| Missing helper types defined or explicitly deferred. | Slice 1 | `selectors/models.py` | Tests can construct full profiles, selector results, collection results, actionRefs, and cache entries without ad hoc dictionaries. Deferred helper types are listed in this plan before Slice 1 is committed. |
| Profile lifecycle is executable. | Slices 1 and 5 | `selectors/profile.py`, config/override loader when added | Tests cover packaged profile load, valid override activation, invalid override rejection, optional packaged fallback, profile version cache invalidation, and unsupported schema rejection. |
| Selector result lifecycle is executable. | Slice 2 | `selectors/resolver.py`, `selectors/diagnostics.py` | Tests cover `resolved`, `ambiguous`, `not_found`, `stale`, and `failed` states, with redacted evidence by default. |
| Collection result lifecycle is executable. | Slice 3 | `selectors/collections.py`, `selectors/transforms.py` | Tests cover visible-window limits, skipped items, missing required fields, partial results, transform allowlist, and truncation diagnostics. |
| ActionRef lifecycle is executable. | Slices 2 and 4 | `selectors/resolver.py`, WeChat adapter modules | Tests cover actionRef creation, risk metadata, caller-visible preconditions, stale target rejection, and no auto-execution of high-risk actions. |
| Cache lifecycle is executable. | Slice 2 | `selectors/cache.py` | Tests cover cache hit, signature validation, stale fallback, TTL expiry, disabled cache, and profile/window mismatch invalidation. |
| Open architecture decisions stay closed during MVP. | All slices | Feature docs and PR/MR description | Any change to profile storage, public API timing, transform ownership, cache locality, locale fallback, or WeChat semantic response shape triggers design update and re-review before code merge. |
| Failure recovery is consistent. | Slices 2-4 | `selectors/diagnostics.py`, WeChat failure mapping | Tests map generic selector failures to WeChat diagnostics while preserving generic `failure_kind`; retry behavior remains bounded. |
| Direct/helper/local-service ownership remains consistent. | Slices 2, 4, and 6 | Resolver integration and future protocol modules | MVP resolver state is process-local; public service-owned selector commands are blocked until Slice 6 parity tests and API docs exist. |

## Phase Rules

- Each implementation slice must update this feature directory with notes or
  verification evidence before it is committed.
- Each slice gets its own focused commit and push.
- Generated raw AX captures, smoke JSON outputs, local build artifacts, and
  generated lock files must not be committed unless explicitly promoted to
  reviewed fixtures.
- `computer-use-macos` must not import `wechat-desktop-tool`.
- Public protocol schemas, command builders, CLI surfaces, and stable docs are
  not changed until the public protocol phase gate.
- Before committing a slice, update the row status in the handoff checklist by
  recording proof in `verification.md` or noting the explicit deferral in this
  plan.

## Slice 1: Internal Contract And Profile Validation

### Files

Add package-private selector modules:

- `packages/computer-use-macos/src/computer_use_macos/selectors/__init__.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/models.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/profile.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/validation.py`

Add focused tests:

- `packages/computer-use-macos/tests/test_selectors.py`

Optional only if needed:

- `packages/computer-use-macos/src/computer_use_macos/selectors/errors.py`

### Behavior

Implement internal dataclasses and validation helpers for:

- profile identity and app identity;
- selector roots, steps, match rules, attribute matchers, structural
  constraints, confidence policy, cache policy, relation rules;
- collection definitions, fields, pagination policy, diagnostics policy;
- element references, signatures, resolved elements, selector diagnostics,
  selector results, collection results, action definitions, action references,
  action preconditions, cache entries;
- `JsonValue` typing and literal policy enums.

Validation must fail closed for:

- unsupported schema versions;
- missing required fields;
- duplicate selector, collection, or action ids;
- selector fallback cycles;
- missing selector references;
- invalid regexes;
- unbounded steps;
- invalid confidence weights or minimums;
- cache policies that disable signature validation while using cache;
- action definitions that omit risk or target selector;
- unknown transform names;
- `alias_ref` values missing from `locale_aliases`.

### Public Surface

Slice 1 is internal-only:

- no export from `computer_use_macos.__init__`;
- no new app-control protocol command;
- no new JSON Schema;
- no CLI change;
- no stable API documentation update beyond feature docs.

### Tests

Run targeted tests:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Minimum new test coverage:

- valid minimal profile validates;
- unknown schema version is rejected;
- invalid selector references are rejected;
- fallback cycles are rejected;
- invalid regex is rejected;
- `alias_ref` without locale alias is rejected;
- unbounded selector step is rejected;
- unknown transform is rejected;
- risky action definitions require explicit risk and known selector;
- package-boundary test still proves no WeChat dependency.

### Rollback

Remove the selector package modules and `test_selectors.py`. Since Slice 1 is
internal-only, no public migration is required.

## Slice 2: Selector Resolver

### Files

- `packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/matching.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/cache.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/diagnostics.py`
- `packages/computer-use-macos/tests/test_selectors.py`

### Behavior

Resolve selector roots, execute bounded steps through existing
`accessibility_query`, apply hard filters, score candidates, validate cached
path hints, follow fallback selectors, and return internal `SelectorResult`
objects with redacted evidence by default.

### Tests

Use fake query fixtures. Cover role/attribute/action matching, cache hit and
stale fallback, ambiguity, not-found diagnostics, truncation diagnostics, and
debug-evidence redaction.

## Slice 3: Collection Extraction

### Files

- `packages/computer-use-macos/src/computer_use_macos/selectors/collections.py`
- `packages/computer-use-macos/src/computer_use_macos/selectors/transforms.py`
- `packages/computer-use-macos/tests/test_selectors.py`

### Behavior

Resolve collection roots, item selectors, required/optional fields, visible
window pagination state, skipped item diagnostics, and allowlisted scalar
transforms.

### Tests

Cover nested row/cell/static text fixtures, required field failures, partial
collections, pagination limits, and transform allowlist rejection.

## Slice 4: WeChat Packaged Profile And Migration

### Files

- `packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles/wechat-macos.toml`
- `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py`
- `packages/wechat-desktop-tool/src/wechat_desktop_tool/window_model.py`
- `packages/wechat-desktop-tool/src/wechat_desktop_tool/observations.py`
- `packages/wechat-desktop-tool/tests/test_tool.py`
- fixture files only after explicit review

### Behavior

Move WeChat navigation, contact-list, conversation-list, and message-region
lookup behind packaged selector profiles while preserving existing WeChat
semantic API shapes. Map generic selector failures into WeChat diagnostics.

### Tests

Use deterministic fixture trees for contacts, conversations, messages, stale
cache fallback, ambiguous selectors, missing fields, and action precondition
failure. Run WeChat package tests and relevant SDK example tests.

### Manual Proof

Real WeChat smoke remains required before merge readiness:

- list contacts;
- list conversations;
- read visible messages;
- profile override failure and packaged fallback;
- stale cache fallback;
- actionRef precondition rejection.

## Slice 5: Config Override Path

Add application-injected profile override support only after packaged profile
migration is proven. If the override becomes a public config field, update
`app-control-protocol`, stable docs, tests, release preflight expectations, and
migration notes in the same slice.

## Slice 6: Public Protocol Proposal

Do not implement public `resolve_selector` or `extract_collection` protocol
commands until internal selector behavior, WeChat migration, helper/local
service parity, and smoke proof are complete. This phase needs a separate API
proposal, JSON schemas, docs, changelog, and migration notes.

## Verification Plan

For each code slice:

1. Run targeted package tests for touched packages.
2. Run package-boundary tests when imports or dependencies change.
3. Run release preflight when public docs, examples, config, or protocol fields
   change.
4. Record commands and results in `verification.md` before merge readiness.

## Release And Changelog Plan

No changelog entry is required for this F3 planning commit. Add an `Unreleased`
entry when implementation changes behavior, APIs, docs, tests, examples, or
packaging, and finalize it during F6 merge readiness.
