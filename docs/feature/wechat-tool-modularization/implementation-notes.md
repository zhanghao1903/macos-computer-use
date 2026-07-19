# Implementation Notes: WeChat Tool Internal Modularization

## Status

| Field | Value |
| --- | --- |
| Branch | `codex/wechat-tool-modularization` |
| Current lifecycle phase | F4 implementation |
| Current slice | I3 row parsing extraction |
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
