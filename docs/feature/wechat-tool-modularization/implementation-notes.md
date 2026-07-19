# Implementation Notes: WeChat Tool Internal Modularization

## Status

| Field | Value |
| --- | --- |
| Branch | `codex/wechat-tool-modularization` |
| Current lifecycle phase | F4 implementation |
| Current slice | I1 diagnostics extraction |
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
