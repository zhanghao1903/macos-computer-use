# Changelog

## 0.1.0 - 2026-07-31

### Added

- Two-task Codex Init for Requirements and Engineering Main plus distinct
  persistent Claude Frontend and Review sessions.
- Explicit Claude CLI/auth probe, model/turn/budget/timeout configuration, and
  Frontend edit authorization.
- Confirmed requirements handoff, Codex technical-plan writing, Claude exact
  plan review, one serialized Main GoalRun, Claude frontend delivery, and
  Claude exact-head code review.
- Shell-free Claude invocation with fixed session UUIDs, structured JSON
  schemas, environment allowlisting, and separate `acceptEdits`/`plan`
  permission modes.
- Persist-before-send dispatch ledger, idempotent completed replay, UNKNOWN
  outcome recovery on the same message/session, and session-busy exclusion.
- Independent frontend Git ancestry/head/commit/path verification.
- Existing exact merge, per-release authorization, partial retry, publication
  proof, and closure gates.
- GitHub installation, Init, update, uninstall, privacy, support, and recovery
  guidance.
- Offline Claude bridge, schema/runtime contract, packaged-skill parity, and
  lifecycle integration tests.
