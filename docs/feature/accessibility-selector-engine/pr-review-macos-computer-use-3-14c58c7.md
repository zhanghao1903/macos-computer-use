# PR Review - `zhanghao1903/macos-computer-use#3` @ `14c58c7`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `14c58c7276035d795be39e8efac8d7eb8ac9be2c` |
| Reviewed at | 2026-07-13T16:14:49Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 110 commits; 98 changed files; 35,172 additions; 1,392 deletions |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` under this Review Contract
- **Open blocking findings:** 1 (`PRR-019`)
- **Resolved in the reviewed delta:** `PRR-018`
- **Rationale:** The response-framing remediation is correct and the exact-head test and CI gates pass. However, a concurrent request that spends its timeout waiting for the worker lock is still written and flushed after its deadline, allowing a mutating action to start before the caller receives a timeout and retryable failure.

## 3. Executive Summary

The four-commit delta records and fixes `PRR-018`, adds real subprocess
framing tests, and updates review documentation. The original buffering race is
resolved: readiness is consumed before dispatch and the parent now owns fd-level
newline framing. A newly identified concurrency boundary remains: the deadline
is calculated before lock acquisition, but it is not checked again before an
action is written after the wait. Fix `PRR-019` and add contention regressions
before merging.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, all changed-file metadata, the
  complete `main...head` diff, and exact-head CI;
- the focused `435d945...14c58c7` delta: four commits, ten files, 1,633
  additions, and 56 deletions;
- `_AccessibilityWorker` readiness, framing, deadline, serialization, restart,
  timeout, and pipe lifecycle;
- query fallback, action no-replay, protocol retryability, and direct shared
  client concurrency paths;
- prior finding lifecycle, package/repository tests, compilation, whitespace,
  release preflight, wheel checks, and documentation state.

### Excluded scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff and strict mypy baseline cleanup.

### Change map

| Area | Main change or observation | External behavior | Risk | Validation |
|---|---|---|---|---|
| Worker framing | Startup consumes readiness; stdout uses `os.read()` and an owned frame buffer. | Fast first responses are no longer hidden by `TextIOWrapper` buffering. | Low | Original counterexample, coalesced-frame test, and 100 query/action responses pass. |
| Worker deadlines | `run()` fixes the deadline before waiting on `_lock`, then dispatches without rechecking it. | A queued request can start after its timeout has expired. | Medium, blocking | Deterministic contention assertion fails with one late action write. |
| Mutating action safety | Internal subprocess fallback remains disabled after worker dispatch. | The library does not automatically replay an unknown action result. | Medium | Existing dispatch-timeout/no-replay test passes; protocol timeout is still marked retryable. |
| Compatibility and release | Public API, schemas, dependencies, and versions are unchanged. | Existing 0.2.0 consumers retain their public surface. | Low | All suites, compile, preflight, wheel checks, and exact-head CI pass. |
| Review documentation | New reports record `PRR-018`; some status text remains stale. | Maintainers may see conflicting readiness statements. | Low | GitHub body and feature documentation compared against current head. |

## 5. Findings

### PRR-019 - `[S2][Blocking][Concurrency]` Expired queued actions are dispatched before timeout is reported

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:241-267` @ `14c58c7276035d795be39e8efac8d7eb8ac9be2c`
- **Confidence:** High
- **Status:** open
- **Observation:** `run()` calculates `deadline` before acquiring `_lock`.
  After the lock is acquired, `_ensure_started()` can return a live process and
  the request is written and flushed without checking whether the deadline has
  already expired. `_read_response_line()` then observes no remaining time,
  terminates the worker, and returns a timeout.
- **Trigger:** Two threads share one `ComputerUseMacOS` instance; request A
  occupies the action worker longer than request B's timeout, so B acquires the
  lock only after its own deadline.
- **Impact:** B can perform an authorized but late UI mutation while its caller
  receives an unknown timeout result. The protocol adapter marks timeout errors
  retryable, so a generic or manual retry can duplicate the side effect even
  though the internal worker path itself does not replay it.
- **Evidence:**
  - `client.py:241-261` fixes the deadline before the lock and contains no
    remaining-budget check before `stdin.write()` and `flush()`.
  - `client.py:4979-4985` classifies every `TIMEOUT` protocol failure as
    retryable.
  - An exact-head deterministic recording-process assertion held the lock for
    0.2 seconds with a 0.1-second timeout. It recorded one `AXPress` payload at
    0.203 seconds, returned `timed_out=true`, and failed the zero-write safety
    assertion (exit 1).
  - The prior approved report explicitly treats write plus flush as
    “potentially dispatched”; therefore this late write crosses the existing
    no-replay safety boundary.
- **Required change:** Acquire the worker lock using the remaining budget or
  check the deadline immediately after acquisition, then check again after
  startup/readiness and before the write. If the budget is exhausted, return a
  timeout without writing and without killing a healthy existing worker.
- **Verification:** Add deterministic contention coverage that holds the lock
  past the request deadline and asserts zero stdin writes, plus a slow
  restart/readiness case that expires before dispatch. Retain the coalesced
  framing, 100-response query/action, dispatched-action timeout/no-replay,
  package, root, preflight, and CI gates.

This is S2 rather than S1 because the bundled Unix socket service is
synchronous, the requested target/action was caller-authorized, and the trigger
requires concurrent direct use of one client. It is still blocking because the
failure crosses the timeout boundary before a mutating operation and exposes a
retryable unknown outcome.

### PRR-018 - `[S1][Blocking][Reliability]` Warm worker could lose a buffered response and report a false timeout

- **Status:** resolved
- **Closure evidence:** `start()` now consumes and validates readiness before
  dispatch; response reads use `os.read()` with a worker-owned byte buffer;
  coalesced readiness/response, readiness failure, 100 immediate query
  responses, 100 immediate action responses, and dispatched-action no-replay
  tests pass. The exact-head `computer-use-macos` suite passed 137 tests with
  one conditional skip.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-016` | Resolved | Their implementation paths are unchanged by the reviewed source delta; privacy, focus/frame/identity, selector, packaging, workflow, and strict-proof gates remain green. |
| `PRR-017` | Resolved | Warm action worker safety and no internal replay remain intact; historical exact-head live performance evidence is unchanged. |
| `PRR-018` | Resolved | Explicit readiness, fd-level framing, real subprocess stress, resource cleanup, and exact-head CI pass. |
| `PRR-019` | Open | Queue time is charged to the timeout, but an expired request is still dispatched after lock acquisition. |

## 6. Required Actions Before Merge

- [ ] `PRR-019` - prevent request dispatch after the deadline while waiting for
  the worker lock or startup, return timeout without disturbing a healthy
  worker, and add zero-write contention and slow-readiness regressions.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish only bounded semantic evidence. / feature maintainer |
| data-integrity | Medium | A late action can mutate UI after its caller's deadline and may be retried. | Block expired dispatch and preserve no replay after actual dispatch. / computer-use-macos |
| reliability-concurrency | Medium | Shared-client contention violates total timeout semantics and kills the warm worker. | Use the remaining budget for serialization/startup and add contention tests. / computer-use-macos |
| performance-scalability | Low | Workers serialize calls and startup can consume up to five seconds. | Bound queue/startup by the request deadline; monitor live percentiles if they become an SLO. / computer-use-macos |
| api-compatibility | Low | The needed fix changes only private direct-mode transport. | Preserve public APIs, schemas, result mapping, and no-replay behavior. / computer-use-macos |
| deployment-rollback | Medium | Shipping the current worker exposes a bounded but real late-action window. | Resolve `PRR-019` before enabling the warm action path in a release. / feature maintainer |
| maintainability | Low | Worker framing and scripts remain private details in one large module. | Keep focused protocol tests; extract separately if useful. / computer-use-macos |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Deterministic queued-deadline zero-write assertion (`timeout=0.1`, lock held `0.2`) | isolated `14c58c7` clone; Darwin arm64; CPython 3.12.7 | **FAIL** | 1 | One `AXPress` payload was written at 0.203 seconds; result was timeout; assertion expected zero writes. `PRR-019`. |
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | isolated `14c58c7` clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | 137 tests passed, 1 skipped. |
| Root repository suite | isolated `14c58c7` clone; CPython 3.12.7 | PASS | 0 | 127 tests passed, including wheel build/install/API smoke and release-preflight coverage. |
| App-control protocol suite | isolated `14c58c7` clone; CPython 3.12.7 | PASS | 0 | 55 tests passed. |
| WeChat package suite | isolated `14c58c7` clone; CPython 3.12.7 | PASS | 0 | 123 tests passed. |
| `.venv/bin/python -m compileall -q packages examples scripts tests` | isolated `14c58c7` clone | PASS | 0 | Python compilation passed. |
| `git diff --check origin/main...HEAD` | isolated `14c58c7` clone | PASS | 0 | No whitespace errors. |
| `env -u PYTHONPATH .venv/bin/python scripts/release_preflight.py` | isolated `14c58c7` clone | PASS | 0 | All local gates passed; only expected unavailable external-proof and sandbox socket warnings remained. |
| Original `PRR-018` counterexample and first-response stress | isolated exact-head clone | PASS | 0 | Original coalesced frame succeeds; query 100/100 and action 100/100 return matching first responses. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test - run 29264538026, job 86866228431](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29264538026/job/86866228431) | 2026-07-13T16:06:49Z | PASS | Exact head `14c58c7` completed successfully; GitHub reports the PR mechanically mergeable and CLEAN. |

### Checks not run

- **Fresh real WeChat action/send:** No new live desktop mutation was
  authorized or needed to reproduce the parent transport defect.
- **Post-submit delivery read-back:** Outside this transport re-review.
- **Signed helper and real release publication:** Later F7 external gates.
- **Ruff:** No Ruff executable or module is installed in the project
  environment.
- **Strict mypy:** The repository has a broad existing baseline; this runtime
  concurrency defect is covered by a deterministic reproduction.

Overall validation status: `FAILED` because the new deadline safety assertion
fails, despite all existing automated and CI checks passing.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `14c58c7276035d795be39e8efac8d7eb8ac9be2c`.
- The complete PR was reviewed through prior finding lifecycle plus focused
  re-review of the source delta and its affected call paths.
- The concurrency reproduction uses a recording process to make the
  post-deadline write deterministic; it does not invoke a real macOS action.
- The bundled local Unix socket server is synchronous, so the trigger applies
  to concurrent direct use of one shared client rather than that server path.
- No fresh real desktop mutation, signed helper, or publication was performed.
- Private raw observations and unrelated dirty worktree files were excluded.

## 10. Open Questions and Assumptions

### Open questions

None that prevent fixing or verifying `PRR-019`.

### Assumptions

1. A request timeout is a total caller budget, including worker queue and
   startup time, because `deadline` is computed before lock acquisition.
2. A mutating request is potentially dispatched once write and flush are
   attempted; subsequent failure must never trigger automatic replay.
3. Direct users may share a `ComputerUseMacOS` instance across threads; the
   worker lock is the serialization boundary for that use.
4. Newline-delimited UTF-8 remains the private worker protocol contract.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable local gate.
- **NOTE-014 [performance]** Collect repeated live samples and percentiles if
  the three-second target becomes an operational SLO.
- **NOTE-015 [documentation]** Synchronize the GitHub PR body with the current
  head and latest review decision; it still presents an older
  `REQUEST_CHANGES` snapshot and asks that the PR remain draft.
- **NOTE-016 [documentation]** Update
  `implementation-notes.md:3863-3864`, which still says repository-wide F5
  verification and the new-head review are pending.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-14c58c7.json`](./pr-review-macos-computer-use-3-14c58c7.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: REQUEST_CHANGES
mergeable: false
head_sha: 14c58c7276035d795be39e8efac8d7eb8ac9be2c
blocking_findings:
  - PRR-019
resolved_findings:
  - PRR-018
validation_status: FAILED
report_status: CURRENT
```
