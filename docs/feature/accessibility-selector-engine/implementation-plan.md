# Accessibility Selector Engine Implementation Plan

Status: F3 implementation plan.

Feature branch: `codex/accessibility-selector-engine`.
Feature directory: `docs/feature/accessibility-selector-engine/`.
Design source: `design.md`.
Review sources:

- `technical-review-2026-07-06.md`
- `technical-review-2026-07-07.md`
- `technical-review-remediation-2026-07-08.md`
- `requirements.md`

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

## F3 Handoff Status

The 2026-07-06 review failed the original design. The revised `design.md` and
`technical-review-remediation-2026-07-08.md` close those design-level blockers,
and `technical-review-2026-07-07.md` passes the plan for implementation
planning.

Implementation remains slice-gated. A slice is complete only when its code,
tests, `implementation-notes.md`, and `verification.md` show which 2026-07-06
review gaps were implemented, explicitly deferred, or revised. Public selector
protocol commands, public config overrides, service-owned resolver/cache state,
and higher-risk actionRefs remain blocked until their documented later gates.

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

## Contract Synchronization Rules

The 2026-07-06 review failed the original design partly because fields and
helper types were easy to infer differently during implementation. The F4
implementation work must keep the design matrix and code synchronized:

- Slice 1 must implement or explicitly defer every row in the `Field Contract
  Matrix` and `Helper Type Field Matrix` sections of `design.md`.
- If a field is deferred, the implementation notes must name the field, reason,
  owning slice, and test that will prove it later.
- If implementation changes a default, validation rule, enum value, lifecycle
  state, or risk boundary, update `design.md` before committing the code slice.
- Public API exposure remains blocked until the implementation plan, API docs,
  migration notes, and release record all describe the same field contracts.
- Verification notes must record which matrix rows were covered by automated
  tests for each slice.

## Review Remediation Gates By Slice

Each implementation slice must close a specific part of the failed 2026-07-06
review. A slice is not complete until its implementation notes and verification
evidence show the matching gate is satisfied or explicitly deferred with an
owner and follow-up phase.

| Slice | 2026-07-06 review gap covered | Required implementation evidence | Required documentation evidence |
| --- | --- | --- | --- |
| Slice 1 | Field-level contracts, missing helper types, profile lifecycle validation. | Dataclass/profile tests for supported schema, defaults, invalid references, cycles, regexes, bounds, aliases, cache policy, relation policy, pagination policy, diagnostics policy, and action risk defaults. | `implementation-notes.md` lists implemented field-matrix rows and any deferred fields. `verification.md` records targeted selector tests. |
| Slice 2 | Selector result lifecycle, cache lifecycle, failure recovery, direct/helper/local-service ownership. | Resolver tests for `resolved`, `not_found`, `ambiguous`, `stale`, `failed`, cache hit, cache stale fallback, TTL expiry, truncation diagnostics, redacted evidence, and process-local cache behavior. | `implementation-notes.md` records resolver and cache lifecycle behavior. `verification.md` records package tests and any skipped real macOS proof. |
| Slice 3 | Collection result lifecycle, pagination policy, field extraction diagnostics. | Collection tests for root resolution, item scanning, required field skip/failure, partial status, accepted-item limits, candidate overscan, transform allowlist, and diagnostics policy. | `implementation-notes.md` records collection lifecycle behavior and pagination limitations. |
| Slice 4 | WeChat migration boundary, semantic failure mapping, actionRef preconditions. | WeChat fixture tests for contacts, conversations, messages, stale selectors, ambiguous selectors, required-field failures, and action precondition rejection. | `verification.md` records fixture coverage and real WeChat smoke status. PR/MR notes state semantic response compatibility. |
| Slice 5 | Config override activation, profile fallback, override safety. | Override tests for valid activation, invalid rejection, optional fallback, locale alias order, no raw profile content in logs, and no risky action policy expansion. | Stable docs or feature docs describe config shape only when it becomes public. |
| Slice 6 | Public API migration path and runtime parity. | Protocol/schema tests, direct/helper/local-service parity tests, release preflight, migration tests, and public API example tests. | `docs/api.md`, package READMEs, `docs/migration-notes.md`, changelog, and release readiness are updated before any public command ships. |

The default behavior for an unimplemented gate is to keep the related API
internal and mark the missing proof in `verification.md`. It is not acceptable
to silently treat a review gap as closed because a field exists in a dataclass.

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

This planning update is documentation-only and does not change package
behavior. The release record for the full feature must still be present before
the feature PR/MR is marked merge-ready.

Add or update an `Unreleased` changelog entry when implementation changes
behavior, APIs, docs, tests, examples, packaging, or repository workflow. During
F6 merge readiness, confirm the changelog summarizes the package-consumer
scenario solved by each slice rather than only listing files changed.

## Review Remediation Slice: Strict Unsupported Action Proof

### Contract And Files

- `computer_use_macos/errors.py`: declare
  `ACCESSIBILITY_ACTION_UNSUPPORTED` and include it in
  `COMPUTER_USE_FAILURE_KINDS`.
- `computer-use-macos/tests/test_package.py`: prove real `AXPress/-25206` and
  `AXSetFocus/-25205` observations route through the public tuple, and cover
  generated `fail("...")` literals in the exhaustiveness check.
- `wechat_desktop_tool/tool.py`: accept the one-fallback exception only after
  strict validation of failure kind, action, attempted state, effect, native
  error code, and every duplicate proof field.
- `wechat-desktop-tool/tests/test_tool.py`: preserve the two valid native
  fallback paths and add zero-fallback cases for `-25204`, wrong action/code
  pairing, missing proof, malformed values, empty values, and contradictions.
- Stable API and WeChat docs plus `implementation-notes.md`: publish the exact
  proof contract and compatibility behavior.

### Verification

1. Run focused computer-use and WeChat regression tests with
   `ResourceWarning` promoted to errors.
2. Run complete package and root suites from an exact clean commit.
3. Repeat all unsafe cross-package shapes ten times and require zero fallback.
4. Run compile, release preflight, wheel/install/API smoke, dependency
   rejection, whitespace, clean-tree, and exact-head GitHub CI checks.
5. Produce a replacement review before restoring merge readiness.

### Rollback

Revert this remediation slice as one unit. No persisted data or configuration
migration exists. A rollback restores the previous tuple and permissive proof
parser, so it must also restore the prior `REQUEST_CHANGES` merge state rather
than representing that behavior as safe to merge.

## Review Remediation Slice: End-To-End Action And Recovery Evidence

This slice closes reopened `PRR-021`, `PRR-022`, and `PRR-026` without changing
the public command or semantic API shape.

### Contract And Files

- `computer_use_macos/client.py`:
  - add the validated requested action to generated native failure payloads
    after `AXUIElementPerformAction` or `AXUIElementSetAttributeValue` runs;
  - normalize `actionAttempted` only when its raw value is Boolean, without
    truthiness coercion;
  - preserve the raw payload so downstream validation sees malformed values.
- `computer-use-macos/tests/test_package.py`:
  - exercise the generated failure producer for both native unsupported pairs;
  - assert the requested action survives direct-client normalization;
  - assert truthy and falsey malformed attempt values are not promoted as
    trusted normalized Booleans.
- `wechat_desktop_tool/tool.py`:
  - model attempt and dispatch evidence as absent, valid true, valid false, or
    invalid;
  - treat malformed relevant containers, aliases, values, and contradictory
    duplicates as invalid;
  - pass the outbound action into every shared fallback decision and require
    all response action copies to equal it.
- `wechat-desktop-tool/tests/test_tool.py`:
  - derive cross-package native fixtures from the production generated action
    script instead of manually injecting an action field;
  - prove one fallback for matching `AXPress/-25206` and
    `AXSetFocus/-25205` producer-to-consumer paths;
  - prove zero fallback for both request/response mismatch directions, truthy
    and falsey malformed attempted values, malformed dispatch duplicates,
    malformed containers, missing evidence, and conflicts;
  - assert action/fallback operation counts across mapped navigation, visible
    contacts, search focus/results, node clicking, and public actionRef
    execution through their shared policy.
- `docs/api.md`, `docs/wechat-desktop-tool.md`, and
  `implementation-notes.md`: document producer ownership, expected-action
  binding, presence-sensitive parsing, compatibility, and fail-closed behavior.

### Verification

1. Run focused computer-use and WeChat regressions with `ResourceWarning`
   promoted to errors.
2. Run both full package suites, protocol tests, and root discovery from an
   exact clean implementation commit.
3. Repeat adversarial cross-package recovery cases ten times and require zero
   fallback for every unsafe result.
4. Run compilation, release preflight, wheel/install/API smoke, dependency
   rejection, whitespace, clean-tree, and exact-head GitHub CI checks.
5. Refresh `verification.md`, merge-readiness, tracked/live PR description, and
   produce a replacement schema-valid review report.

### Rollback

Revert producer, normalizer, recovery parser, tests, and stable documentation as
one unit. The change has no persisted state or configuration migration. A
rollback reopens all three safety/compatibility findings and must restore
`REQUEST_CHANGES` rather than retaining merge readiness.

## Review Remediation Plan 2026-07-17

This plan implements the `59c6fb5` review blockers in independently verifiable
commits. Every phase updates its lifecycle evidence before it is committed and
pushed.

### Phase R1: Design And Plan Baseline

- Record the bounded decision, semantic pagination, atomic profile, frontmost
  target, evidence privacy, structured failure, and historical evidence
  contracts in `design.md` and this plan.
- Preserve the latest schema-valid `REQUEST_CHANGES` report as the starting
  review baseline.
- Gate: documentation names every open finding and assigns one owner and test
  strategy.

### Phase R2: `computer-use-macos` Safety And Bounds

Implementation:

- resolver: reject decision-critical truncation before pick, fallback, or cache
  write; isolate the exact-self cache validation exception;
- profile validation: enforce the executable one-step collection-selector
  subset and context-specific pick/cache defaults;
- collection extraction: count accepted records, use accepted lookahead for
  `hasMore`, surface incomplete scans as truncation, and cap batch queries;
- native workers: require an exact usable frontmost target for query, action,
  and tree operations;
- errors: register and publicly export all query/action worker process failure
  kinds.

Tests:

- candidate-bearing truncated queries never resolve or cache;
- unsupported embedded collection semantics fail validation before query;
- required-field rejection does not consume page capacity and accepted
  lookahead controls `hasMore`;
- maximum packaged pages never generate a query above 500;
- background/multiple/terminated app fixtures perform zero AX work;
- producer literals, registry membership, uniqueness, and public imports agree.

Gate: focused selector, collection, worker, package, and profile tests pass with
no live desktop mutation.

### Phase R3: WeChat Recovery, Configuration, Privacy, And Failures

Implementation:

- replace independent selector/control-map loading with one immutable validated
  asset bundle and store it once per tool instance;
- replace action-proof parsing with one allowlisted collector shared by action,
  attempt, effect, native code, and dispatch decisions;
- sanitize query/action/observe evidence and events with operation-specific
  allowlists while retaining explicit semantic `includeRaw` behavior;
- route structured permission, timeout, transport, and truncation causes before
  legacy text heuristics.

Tests:

- every documented evidence container and alias is accepted only when complete,
  typed, mutually consistent, and bound to the outbound action;
- malformed or conflicting diagnostics/transport/evidence authorizes zero
  fallback and operation counts prove no hidden second mutation;
- half-valid overrides never produce mixed assets;
- contact/message canaries remain in semantic items but never appear in generic
  evidence, progress/final events, or redacted logs;
- adversarial messages cannot override recognized structured causes.

Gate: full WeChat package tests pass; mutation policy tests use fakes only.

### Phase R4: Historical Evidence Repair

- Validate the historical `f19cbd9` JSON with the current review validator.
- Restore preserved finding fingerprints from the authoritative predecessor,
  use two-dot commit ranges, cover every reviewed path in forward-risk surfaces,
  and distinguish exact-head required runs from earlier supporting runs.
- Recompute artifact hashes and update every downstream review-chain,
  merge-readiness, status, and PR-description reference.
- Do not relabel a supporting run as exact-head proof or alter the historical
  review decision without evidence.

Gate: every committed machine-readable review validates and all recorded SHA-256
references match repository bytes.

### Phase R5: Verification And Re-review

Run from an exact clean implementation commit:

1. focused tests for every finding;
2. full `computer-use-macos`, `wechat-desktop-tool`, protocol, and root suites;
3. compile, type/lint checks used by the repository, release preflight,
   wheel/install/API smoke, dependency rejection, and whitespace checks;
4. exact-head GitHub CI;
5. replacement evidence-driven PR review.

Update `verification.md`, `implementation-notes.md`, stable API/package docs,
changelog/release records, merge-readiness, and PR description with the exact
commands, head SHA, results, skipped live checks, and residual risks. Merge is
blocked until the replacement review is schema-valid and no required finding
remains open.

### Phase Commit Boundaries

| Commit | Contents | Push condition |
| --- | --- | --- |
| R1 | design and implementation-plan amendments | docs cross-reference all 12 blockers |
| R2 | generic selector/native-worker implementation, tests, and notes | focused generic tests pass |
| R3 | WeChat implementation, tests, and notes | full WeChat tests pass |
| R4 | corrected review artifacts and downstream hashes/status | validators and hash checks pass |
| R5 | exact-head verification and replacement review evidence | local and CI evidence is recorded |

## Review Remediation Plan For `e86181a`

The schema-valid report pair at `e86181a` is the frozen input. Remediation is
split by root cause so each commit carries implementation, discriminating
tests, documentation, and rollback evidence together.

### R6: Frontmost Identity And Public Failure Contract

- Change query and action generated workers to use name matching only when no
  bundle id is present; retain usability and exact-bundle checks.
- Declare, export, register, and document the query/action/tree frontmost
  failure values without renaming serialized failures.
- Extend generated-worker tests for localized alias mismatch, name-only
  fallback, wrong identity, hidden/terminated/missing app, and zero background
  lookup.
- Extend package contract tests so real generated values are registry-routable
  and importable from the installed package.
- Gate: focused `computer-use-macos` tests, full package suite, compile, and
  `git diff --check` pass.

### R7: Action Recovery Semantic State

- Centralize the non-native fallback semantic gate after typed/duplicate proof
  collection.
- Preserve the two complete native unsupported pairs and legacy no-evidence
  compatibility path.
- Reject performed/unknown effects, any native code on legacy/pre-dispatch
  paths, action mismatch, malformed values, and contradictory copies.
- Add a matrix for legacy explicit-unsupported and retryable pre-dispatch
  outcomes through every shared fallback caller; assert one original operation
  and zero fallback mutations for unsafe cases.
- Gate: focused no-replay tests and full `wechat-desktop-tool` suite pass.

### R8: Complete Contact-Target Queries

- Add one contact-target completeness gate that maps successful truncated
  low-level queries to `wechat_query_truncated`.
- Apply it before candidate construction in control-map, visible-row, and
  search-result paths.
- Cover zero, one, and multiple returned candidates with limit, time, and depth
  truncation. Assert no click, Accessibility action, Return, draft, or submit.
- Gate: focused open/focus/draft/send regressions and full WeChat suite pass.

### R9: Exact-Head Verification And F6 Synchronization

- Run root and all package suites, compile, release preflight, wheel build and
  installed API proof, review-result validation, and whitespace checks from a
  clean exact-head snapshot.
- Update implementation notes, verification, merge-readiness, PR description,
  API docs, WeChat docs, and `CHANGELOG.md` with the actual evidence.
- Push the candidate head and wait for exact-head GitHub CI.
- Synchronize the live PR body to the tracked pending-re-review record. Do not
  mark ready, approve, merge, tag, release, or perform live WeChat mutation.
- Hand the immutable head and all five finding IDs to independent re-review.

### Changed-Surface Classification

| Paths | Surface | Required proof |
| --- | --- | --- |
| `computer_use_macos/client.py`, `errors.py`, `__init__.py` | identity and public failure contract | generated producer, registry/export, package and wheel tests |
| `computer-use-macos/tests/test_package.py` | identity/registry counterexamples | executable scripts and operation counters |
| `wechat_desktop_tool/tool.py` | mutation replay and target completeness | exact operation-count regressions |
| `wechat-desktop-tool/tests/test_tool.py` | adversarial recovery and truncation | all direct paths plus composite no-mutation assertions |
| stable API/WeChat docs and feature lifecycle records | consumer recovery and F6 truth | preflight, diff inspection, platform comparison |
| `CHANGELOG.md` | release record | `Unreleased` entry names both affected packages |

No configuration, protocol schema, persisted data, dependency, live desktop
permission, or release-version change is planned.
