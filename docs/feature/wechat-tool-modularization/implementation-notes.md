# Implementation Notes: WeChat Tool Internal Modularization

## Status

| Field | Value |
| --- | --- |
| Branch | `codex/wechat-tool-modularization` |
| Current lifecycle phase | F4 implementation |
| Current slice | I7a window operations complete; I7b collections next |
| Production behavior | Unchanged |

## Slice I0: Behavior Lock

### Scope

- Added an exact snapshot of package exports and public
  `WeChatDesktopTool` signatures.
- Added a complete ordered app-control child-command trace for a successful
  `send_message` workflow.
- Added an event-order and phase-name contract for streamed open-WeChat.
- Added a public `execute_action` regression proving contradictory dispatch
  evidence produces one Accessibility action and no replay or fallback.
- Added test-only canonicalization that replaces wall-clock timing values but
  does not omit any result field.

No production file changed in this slice. The initially planned migration of
the large shared fixture block into `_tool_test_support.py` is deferred to I8;
I0 adds only small equivalence helpers so the behavior oracle itself remains a
reviewable change.

### Evidence

- Focused equivalence suite: 5 tests passed in 0.010 seconds.
- Full `wechat-desktop-tool` suite: 177 tests passed in 1.403 seconds with
  `ResourceWarning` treated as an error.
- Python compile check passed for both new test modules.
- `git diff --check` passed.

The inventory is the 172-test baseline plus five new equivalence tests; no
production test was removed or renamed.

### Rollback

Revert the I0 commit. No production rollback or migration is required.

## Slice I1: Diagnostics Extraction

### Scope

- Added private `_diagnostics.py` for foundational input parsing, scalar and
  observation extraction, message text parsing, safe envelope helpers,
  redaction, timing, event construction, and semantic failure construction.
- Moved 54 complete private functions and their nine private constants without
  changing function bodies.
- Imported only the 41 moved functions and two constants still referenced by
  the monolithic module.
- Added six direct diagnostics tests covering redaction scope, message parsing
  and truncation, protocol failure fields, public AX projection, scalar input
  validation, and timing preservation.

Five safe-observation/event functions remain temporarily in `tool.py` because
they depend on query mapping or action-proof functions scheduled for I2 and I4.
They move after those dependencies have stable owners, avoiding a circular
import during migration.

### Evidence

- AST equivalence compared all 54 moved functions against the I0 commit:
  54 equal, 0 changed.
- Focused diagnostics suite: 6 tests passed.
- Full `wechat-desktop-tool` suite: 183 tests passed in 1.432 seconds with
  `ResourceWarning` treated as an error.
- Python compile check passed for `tool.py`, `_diagnostics.py`, and the new
  diagnostics tests.
- `git diff --check` passed.
- `tool.py` decreased from 6979 to 6100 lines; `_diagnostics.py` is 969 lines.
- `uv run ruff` could not execute because Ruff is not installed in the
  workspace environment. This check remains required in F5; no Ruff result is
  claimed for I1.

### Rollback

Revert the I1 commit. The I0 behavior locks remain independent and continue to
exercise the original implementation.

## Slice I2: Query Mapping Extraction

### Scope

- Added private `_query_mapping.py` for selector result translation, scoped
  query envelopes, navigation/window normalization, AX node/frame helpers,
  actionRef construction, mapped-control identity checks, and safe public AX
  projection.
- Moved 40 complete functions and eight constants from `tool.py` plus six AX
  projection functions from `_diagnostics.py`.
- Updated the two tests that intentionally call selector-query private helpers
  to import them from their new owning module.
- Added six direct query-mapping tests covering envelope copying, navigation
  actionRefs and TTL, pressable-target requirements, current-window frame
  validation, bundle/window identity, collection-node mapping, and truncation.

No app-control call, query payload, selector condition, actionRef field, or
failure route changed.

### Evidence

- AST equivalence compared all 46 moved functions against the I1 commit:
  46 equal, 0 changed.
- Focused query-mapping suite: 6 tests passed.
- Existing diagnostics suite: 6 tests passed after ownership import updates.
- Full `wechat-desktop-tool` suite: 189 tests passed in 1.417 seconds with
  `ResourceWarning` treated as an error.
- Python compile and `git diff --check` passed.
- `tool.py` decreased to 5245 lines, `_diagnostics.py` to 871 lines, and
  `_query_mapping.py` is 1021 lines.
- Ruff remains deferred for the same I1 environment limitation.

### Rollback

Revert the I2 commit. `_diagnostics.py` and all I0/I1 behavior locks remain
independently usable.

## Slice I3: Row Parsing Extraction

### Scope

- Added private `_row_parsing.py` for mapped collection items, contact-row
  synthesis and filtering, conversation metadata, search/visible candidates,
  visible messages, text-extract messages, chat titles, pagination, contact
  confidence, and ambiguity result construction.
- Moved 24 complete functions from `tool.py` and 15 complete functions plus
  three constants from `_diagnostics.py`.
- Moved the direct text-message parsing test import to the new owner.
- Added six row-parsing tests covering conversation metadata, synthesized
  contact rows, exact normalized contact matching, descendant message text,
  search-title exclusion, and truncation pagination.

Moving contact ambiguity builders with parsed candidates keeps dependencies
acyclic: `_row_parsing` depends on diagnostics primitives, while diagnostics
does not import row parsing.

### Evidence

- AST equivalence compared all 39 moved functions against the I2 commit:
  39 equal, 0 changed.
- Focused row-parsing suite: 6 tests passed.
- Existing diagnostics suite: 6 tests passed after the ownership import move.
- Full `wechat-desktop-tool` suite: 195 tests passed in 1.413 seconds with
  `ResourceWarning` treated as an error.
- Python compile and `git diff --check` passed.
- `tool.py` decreased to 4727 lines, `_diagnostics.py` to 591 lines, and
  `_row_parsing.py` is 833 lines.
- The private module dependency scan found no facade or backend import.
- Ruff remains deferred for the same I1 environment limitation.

### Rollback

Revert the I3 commit. Earlier diagnostics and query-mapping modules remain
independently validated.

## Slice I4: Action Safety Extraction

### Scope

- Added private `_action_safety.py` for actionRef expiry and target identity,
  native Accessibility mutation proof reconciliation, fallback eligibility,
  request-dispatch evidence, failure classification, and selector fallback.
- Moved 22 complete functions, three frozen evidence data classes, and the
  native unsupported-error constant from `tool.py`.
- Updated tests that intentionally exercise private fallback policies to use
  their new owning module.
- Moved five shared Accessibility action response fixtures into
  `_tool_test_support.py` so focused safety tests do not import the monolithic
  test module; existing tests consume the same fixtures through compatibility
  aliases.
- Added six focused tests covering immutable evidence, pre-dispatch fallback,
  proven native unsupported fallback, contradictory/unknown no-replay,
  actionRef expiry, and row target identity.

No fallback branch, native error code, proof key, failure payload, expiry
rule, actionRef field, or app-control call changed.

### Evidence

- AST equivalence compared all 25 moved functions/classes against the I3
  commit: 25 equal, 0 changed.
- Focused action-safety suite: 6 tests passed.
- Full `wechat-desktop-tool` suite: 201 tests passed in 1.542 seconds with
  `ResourceWarning` treated as an error.
- Python compile and `git diff --check` passed.
- `tool.py` decreased to 4206 lines and `_action_safety.py` is 551 lines.
- The private module dependency scan remains acyclic: action safety imports
  diagnostics and query mapping only; neither imports action safety.
- Ruff remains deferred for the same I1 environment limitation.

### Rollback

Revert the I4 commit. I0 behavior locks and I1-I3 extracted modules remain
independently validated.

## Slice I5: Runtime Extraction

### Scope

- Added private `_runtime.py` with a frozen `WeChatToolRuntime` dependency
  container for the app-control client, resolved config, selector assets,
  control map, and selector profile.
- Moved 11 complete transport/query/input methods, eight complete safe
  projection and readiness functions, `_PhaseEventCollector`,
  `_WeChatSelectorQueryRunner`, and `_QUERY_ATTRIBUTES` out of `tool.py`.
- Replaced the facade's five independently assigned private dependency fields
  with one runtime instance and read-only compatibility properties.
- Routed existing operation call sites directly through the runtime. The
  selector query runner now holds the runtime instead of the public facade;
  its counter, phase names, command inputs, and failure payload are unchanged.
- Added six focused runtime tests covering single construction-time selector
  loading, helper-backend rejection text, dependency identity and read-only
  facade aliases, input/child-command construction, phase events, and selector
  runner sequencing.

The runtime adds no cache, retry, process, socket, serialization, or desktop
round trip. Selector assets are still loaded once during tool construction.

### Evidence

- AST equivalence compared 20 moved methods/functions/classes against the I4
  commit: 20 equal, 0 changed; `_QUERY_ATTRIBUTES` was also AST-identical.
- The selector runner's intentional facade-to-runtime dependency change is
  covered by an exact two-query phase/command characterization test.
- Focused runtime suite: 6 tests passed in 0.012 seconds.
- Existing public equivalence suite: 5 tests passed in 0.010 seconds.
- Existing selector/profile suite: 12 tests passed in 0.042 seconds.
- Full `wechat-desktop-tool` suite: 207 tests passed in 1.433 seconds with
  `ResourceWarning` treated as an error.
- Python compile, Pyflakes, Black, and `git diff --check` passed for the
  production and focused test modules.
- `tool.py` decreased to 3460 lines; `_runtime.py` is 895 lines and the new
  focused test module is 214 lines.
- The dependency direction remains acyclic: runtime imports diagnostics,
  query mapping, and action safety; none imports runtime or the facade.
- Ruff remains deferred for the same I1 environment limitation.

### Rollback

Revert the I5 commit. The facade returns to owning its five dependency fields;
I0-I4 remain independently validated.

## Slice I6: Action And Mapped-Control Extraction

### Scope

- Added private `_action_operations.py` with explicit-runtime functions for
  public action execution, node click routing, and actionRef execution.
- Added private `_mapped_controls.py` with explicit-runtime functions for
  mapped navigation, verified control execution/postconditions, bounded
  collection and conversation-target queries, and mapped region lookup.
- Moved nine complete facade methods and four mapped-control timeout constants;
  operation call sites now pass `self._runtime` explicitly.
- Moved shared app-control/open-phase failure translation to `_runtime.py` and
  pure contact-target query integrity checks to `_query_mapping.py`, preserving
  the directional import graph.
- Updated legacy private-helper tests through one test-only adapter instead of
  retaining an action proxy on the public facade.
- Added six focused action-operation tests and seven focused mapped-control
  tests. They cover successful envelopes, expiry before dispatch,
  pre-dispatch selector fallback, unknown-result no-replay, verified AX-frame
  coordinate use, navigation skip/missing cases, configured query bounds,
  target-window validation, and selected-state postconditions.

No action proof branch, coordinate gate, selector fallback, command phase,
timeout, query bound, map lookup, postcondition, or failure payload changed.

### Evidence

- Canonical AST comparison normalized only `self` dependency access into the
  explicit runtime argument: all nine moved method bodies were equal.
- Four shared moved functions and four moved timeout constants were directly
  AST-identical to the I5 commit.
- Focused action-operation suite: 6 tests passed in 0.015 seconds.
- Focused mapped-control suite: 7 tests passed in 0.014 seconds.
- Full `wechat-desktop-tool` suite: 220 tests passed in 1.469 seconds with
  `ResourceWarning` treated as an error.
- Python compile, Pyflakes, formatting checks for new/changed production
  modules and new focused tests, and `git diff --check` passed.
- `tool.py` decreased to 2767 lines; `_action_operations.py` is 250 lines,
  `_mapped_controls.py` is 459, `_runtime.py` is 933, and
  `_query_mapping.py` is 1066.
- The import graph remains acyclic: mapped controls depend on action
  operations and runtime; action operations depend on runtime; runtime and the
  pure helper modules import neither operation module nor the facade.
- Ruff remains deferred for the same I1 environment limitation.

### Rollback

Revert the I6 commit. Runtime and all pure extraction slices I0-I5 remain
independently validated.

## Slice I7a: Window Operations

### Scope

- Added private `_window_operations.py` for the `open_wechat` and
  `inspect_window` workflows.
- Moved both complete facade methods to explicit-runtime functions and changed
  only facade dispatch dependency wiring.
- Added six focused tests covering the two-phase ready flow, exact scoped
  query sequence, explicit raw inclusion with safe evidence, actionable
  suppression, query-failure translation, and missing-main-content diagnostic
  output.

No readiness check, query payload, raw-data boundary, normalization reason,
available action, failure translation, or app-control call changed.

### Evidence

- Canonical AST comparison normalized only facade/runtime dependency access:
  both moved method bodies were equal.
- Focused window-operation suite: 6 tests passed in 0.014 seconds.
- Full `wechat-desktop-tool` suite: 226 tests passed in 1.500 seconds with
  `ResourceWarning` treated as an error.
- Python compile, Pyflakes, Black, and `git diff --check` passed for the
  changed production and focused test modules.
- `tool.py` decreased to 2551 lines; `_window_operations.py` is 248 lines and
  its focused test module is 259 lines.
- The window module depends only on runtime, diagnostics, pure query/row
  mapping, commands, and models; no facade import was introduced.

### Rollback

Revert the I7a commit. I0-I6 remain independently validated.
