# Implementation Notes: WeChat Tool Internal Modularization

## Status

| Field | Value |
| --- | --- |
| Branch | `codex/wechat-tool-modularization` |
| Current lifecycle phase | F4 implementation |
| Current slice | I0 behavior lock |
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
