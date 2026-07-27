# Changelog

## 0.1.0 - 2026-07-27

### Added

- Three-task Init for Requirements, Engineering Main, and Engineering Review.
- Confirmed requirements handoff and independent technical-plan review.
- Serialized initial and remediation GoalRuns with blocked-state recovery.
- Exact-head PR review, immutable review-record branches, and merge policy.
- Typed GitHub Release/PyPI authorization, partial-failure retry, and closure.
- Strict runtime contracts, Draft 2020-12 schemas, fixtures, and integration
  tests.
- GitHub install, update, uninstall, privacy, support, and terms guidance.

### Fixed

- Keep review-only workflows open at READY until an external merge is observed,
  then accept exact-head merge proof without granting automatic merge authority.
- Make acceptance validation atomic and deterministic message/release replay
  idempotent.
- Require exact previous-result authority for every re-review cycle.
- Bind GitHub Release and PyPI/TestPyPI proof URLs to authorized destinations.
- Make Init task creation recoverable, permit strict bootstrap-only role
  acknowledgements, and reject all feature work until global bootstrap.
- Require confirmed requirements to use the deterministic branch/path at the
  exact authoritative remote tip.
- Make Goal prepare/activate response-loss replays idempotent and require green
  checks for every merge-authorizing READY result.
- Revalidate persisted release target sets and closure targets against the full
  canonical authorization on every state load.
- Bind successful release replay to the exact last submission or complete
  cumulative result, and reject future-stage proof under an earlier stage.
- Pass strict mypy validation for both workflow runtime scripts.
- Reject missing Goal authorization before Init persistence and reject
  duplicate/shadow requirements metadata.
- Bind release replay authority to ordered, reconstructable submission history
  with unique targets and history entries.
