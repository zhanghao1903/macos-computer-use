# PR Review - `zhanghao1903/macos-computer-use#3` @ `002fd72`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `002fd7226634c7777e07416cb2e4401843e7b2b0` |
| Reviewed at | 2026-07-14T01:06:03Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 115 commits; 102 changed files; 36,690 additions; 1,388 deletions |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` under this Review Contract
- **Open blocking findings:** 1 (`PRR-020`)
- **Resolved in the reviewed delta:** `PRR-019`
- **Rationale:** The queued-deadline repair is correct and every existing local
  and exact-head CI gate passes. However, a real worker request that is already
  dispatched and then times out is exposed to protocol consumers as
  `retryable=true`, contradicting the PR's non-retryable unknown-outcome
  contract and permitting duplicate mutating actions.

## 3. Executive Summary

The five-commit delta records, repairs, verifies, and documents `PRR-019`.
Bounded lock acquisition and the post-readiness write gate now prevent expired
requests from reaching the worker, preserve the process, and pass deterministic
zero-write tests. Re-review found one distinct protocol defect: an AX action
that was definitely dispatched but whose response timed out is still marked
retryable for callers. Resolve `PRR-020`, add protocol-level retryability tests,
and re-review the resulting head before merge.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, complete changed-file metadata,
  full `main...head` diff, commit delta, and exact-head CI;
- focused `14c58c7...002fd72` delta: five commits, ten files, 1,562 additions,
  and 40 deletions;
- `_AccessibilityWorker` serialization, lock/startup deadline, readiness,
  dispatch, response timeout, process preservation, and cleanup;
- `accessibility_action()` timeout conversion, warm-worker no-fallback path,
  protocol observation/error retryability, and consumer recovery contract;
- prior finding lifecycle, release record, package boundaries, root/package
  tests, compilation, whitespace, release preflight, wheel checks, current CI,
  and PR hygiene.

### Excluded scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff installation and cleanup of the repository's existing strict-mypy
  baseline.

### Change map

| Area | Main change or observation | External behavior | Risk | Validation |
|---|---|---|---|---|
| Queue and startup deadline | Lock acquisition uses the remaining budget, with checks after lock acquisition and readiness. | Pre-dispatch expiration writes zero frames and preserves a healthy worker. | Low | Prior counterexample now writes zero frames; both real-subprocess regressions pass. |
| Post-dispatch action timeout | Worker termination and no one-shot fallback are retained, but dispatch state is lost when building the protocol result. | An unknown mutating outcome is returned as retryable. | Medium, blocking | Synthetic AXPress dispatch marker plus delayed response yields `timeout`, `retryable=true`, and zero internal fallback. |
| Framing and resources | Readiness handshake, fd-level newline framing, and cleanup are unchanged. | Fast responses stay ordered and workers close cleanly. | Low | 139 package tests with resource warnings as errors; 100 query/action stress remains green. |
| Compatibility and release | No schema, config, dependency, or version changed. | Existing 0.2.0 surface remains, except the documented retryability contract is not honored. | Medium | Root/package suites, preflight, wheel checks, compile, and CI pass; the new contract assertion fails. |
| Documentation and PR hygiene | Repository docs approve `a77f5d4`; platform body remains at an old request-changes snapshot. | Maintainers see conflicting review state. | Low | Branch docs and GitHub body compared against current head. |

## 5. Findings

### PRR-020 - `[S2][Blocking][API Contract]` A dispatched action timeout is incorrectly advertised as retryable

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:1453-1468` @ `002fd7226634c7777e07416cb2e4401843e7b2b0`
- **Confidence:** High
- **Status:** open
- **Observation:** The warm action path intentionally returns a worker timeout
  without one-shot fallback, but `accessibility_action()` converts both
  pre-dispatch and post-dispatch timeouts to the same generic
  `ComputerUseStatus.TIMEOUT`. `_result_to_protocol_observation()` then marks
  every timeout retryable, so both the top-level observation and nested
  `ToolError` expose `retryable=true` even when the worker already received the
  action.
- **Trigger:** The action worker receives an `AXPress` request and begins the
  action, but no response arrives before the request deadline. A caller uses
  `run_command()` and follows the returned protocol retryability guidance.
- **Impact:** The caller can retry an unknown mutating outcome and execute the
  same UI side effect twice. Internal fallback suppression does not protect a
  package consumer that relies on the public `retryable` classification.
- **Evidence:**
  - `client.py:1453-1468` maps the worker timeout to a generic Accessibility
    action timeout without preserving whether dispatch occurred;
  - `client.py:1533-1549` proves the new warm action path returns the worker
    result directly and does not invoke one-shot fallback;
  - `client.py:5004-5009` marks every `ComputerUseStatus.TIMEOUT` retryable, and
    `_protocol_failure()` copies that value into the nested error;
  - `merge-readiness.md:146` declares the opposite public contract: action
    worker timeout/protocol failure is non-retryable after dispatch;
  - an exact-head synthetic worker recorded an `AXPress`, then withheld its
    response. The result was `status=timeout`,
    `failureKind=accessibility_action_timeout`, `retryable=true`, with zero
    fallback calls. An assertion requiring `retryable=false` failed with exit
    code 1;
  - the existing real-worker no-replay regression checks only that the marker
    exists and `runner.calls == []`; it does not assert top-level or nested
    retryability.
- **Required change:** Preserve whether an action request crossed the dispatch
  boundary and set both protocol retryability fields to `false` for a
  post-dispatch timeout or other unknown action outcome. A pre-dispatch
  zero-write timeout may remain retryable only if it is reliably distinguished;
  conservatively marking every Accessibility action timeout non-retryable is
  also safe. Keep documentation aligned with the implemented result contract.
- **Verification:** Extend the real dispatched-timeout regression to assert one
  recorded action, zero internal fallback calls, and top-level plus nested
  `retryable=false`. Add a separate pre-dispatch expiration assertion for the
  chosen safe retry policy, then rerun the package/root, framing/deadline,
  release, and exact-head CI gates.

This is S2 rather than S1 because the library itself does not replay the action,
the caller owns its retry policy, and the requested target/action was already
authorized. It remains blocking because `retryable` is a public backend
recovery classification and the PR explicitly promises the safer opposite
behavior for a newly added warm action path.

### PRR-019 - `[S2][Resolved][Concurrency]` Expired queued actions were dispatched before timeout was reported

- **Status:** resolved
- **Closure evidence:** One monotonic deadline now bounds serialization, lock
  waiting, startup/readiness, pre-write dispatch, and response waiting. The
  prior 0.1-second request held behind a lock now completes in approximately
  0.105 seconds with zero writes and the same healthy process. Real subprocess
  tests also cover delayed startup/readiness, zero writes, and same-process
  follow-up success.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-017` | Resolved | Privacy, focus/frame/identity, selector, packaging, workflow, pagination, proof, and performance paths remain unchanged and their gates remain green. |
| `PRR-018` | Resolved | Explicit readiness, fd-level framing, coalesced/100-response stress, cleanup, internal no-replay, and CI remain green. |
| `PRR-019` | Resolved | Bounded queue/startup deadline, zero-write expiration, healthy-worker preservation, and exact-head CI pass. |
| `PRR-020` | Open | Post-dispatch action timeout still emits `retryable=true` to protocol consumers. |

## 6. Required Actions Before Merge

- [ ] `PRR-020` - distinguish post-dispatch unknown action outcomes from safe
  pre-dispatch expiration, emit `retryable=false` after dispatch, add protocol
  assertions, and synchronize the declared contract.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish only bounded semantic evidence. / feature maintainer |
| data-integrity | Medium | A consumer can retry an action whose first outcome is unknown and duplicate a UI mutation. | Make post-dispatch outcomes non-retryable and require observation/manual recovery. / computer-use-macos |
| reliability-concurrency | Low | Pre-dispatch queue/startup expiration is now bounded and preserves the worker. | Retain one total deadline and the deterministic zero-write regressions. / computer-use-macos |
| performance-scalability | Low | Contended calls can exhaust their budget before dispatch. | Return promptly without process churn and retain transport timing diagnostics. / computer-use-macos |
| api-compatibility | Medium | The emitted retryability value contradicts the feature's declared recovery contract. | Preserve dispatch state and test top-level/nested protocol fields. / computer-use-macos |
| deployment-rollback | Medium | Shipping the warm action path with unsafe retry guidance can duplicate desktop effects. | Resolve `PRR-020` before changing the PR from draft or releasing. / feature maintainer |
| maintainability | Low | Worker transport and generic result mapping encode different safety knowledge. | Carry an explicit dispatch/outcome classification across the boundary. / computer-use-macos |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Post-dispatch action non-retryability assertion | isolated `002fd72` clone; Darwin arm64; CPython 3.12.7 | **FAIL** | 1 | Worker recorded `AXPress`; result was timeout with `retryable=true`; runner fallback count was 0. `PRR-020`. |
| Prior queued-deadline zero-write counterexample | isolated `002fd72` clone; CPython 3.12.7 | PASS | 0 | Completed while lock remained held; 0 writes; timeout 124; same process preserved. `PRR-019`. |
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | isolated `002fd72` clone; CPython 3.12.7 | PASS | 0 | 139 tests passed, 1 skipped; no resource warning. |
| Root repository unittest discovery | isolated `002fd72` clone; CPython 3.12.7 | PASS | 0 | 127 tests passed, including wheel build/install/API smoke, dependency rejection, and release checks. |
| App-control protocol unittest discovery | isolated `002fd72` clone; CPython 3.12.7 | PASS | 0 | 55 tests passed. |
| WeChat package unittest discovery | isolated `002fd72` clone; CPython 3.12.7 | PASS | 0 | 123 tests passed. |
| `.venv/bin/python -m compileall -q packages examples scripts tests` | isolated `002fd72` clone | PASS | 0 | Python compilation passed. |
| `git diff --check origin/main...HEAD` | isolated `002fd72` clone | PASS | 0 | No whitespace errors. |
| `env -u PYTHONPATH .venv/bin/python scripts/release_preflight.py` | isolated `002fd72` clone | PASS | 0 | Local public, package, workflow, and documentation gates passed; only expected sandbox socket and unavailable external-proof warnings remained. |
| Isolated worktree status | isolated `002fd72` clone after verification | PASS | 0 | `git status --short` was empty. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test - run 29268604523, job 86880315238](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29268604523/job/86880315238) | 2026-07-14T01:00:52Z | PASS | Exact head `002fd72` completed successfully; GitHub reports mechanical mergeability and merge state CLEAN. |

### Checks not run

- **Fresh real WeChat action/send:** No new live desktop mutation was
  authorized or needed; both findings are distinguished with synthetic worker
  frames and protocol results.
- **Post-submit delivery read-back:** Outside this worker recovery review.
- **Signed helper and real release publication:** Later release-stage external
  gates.
- **Ruff:** No Ruff executable or module is installed in the project virtual
  environment or available Anaconda runtime.
- **Strict mypy:** The prior exact implementation run reported three existing
  errors outside the worker delta; it is not a configured CI gate.

Overall validation status: `FAILED` because the new protocol recovery assertion
fails, despite all existing local and CI checks passing.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `002fd7226634c7777e07416cb2e4401843e7b2b0`.
- The complete feature diff is covered through the stable prior finding ledger
  plus focused re-review of the ten-file delta and the affected end-to-end
  timeout/result path.
- The post-dispatch reproduction uses a synthetic worker and temporary marker;
  it does not execute a real macOS Accessibility action.
- The generic timeout-to-retryable mapping existed on the base branch, but this
  PR adds a default warm action transport that reaches it and explicitly adds a
  contrary after-dispatch public contract, so the new path and contract are
  within PR attribution.
- No fresh desktop mutation, signed helper, or publication was performed.
- Private raw observations and unrelated dirty worktree files were excluded.
- The GitHub PR remains draft and its platform body still describes the old
  `07fa052` request-changes snapshot.

## 10. Open Questions and Assumptions

### Open questions

None that prevent fixing or verifying `PRR-020`.

### Assumptions

1. Protocol consumers may use `retryable` to decide whether an automatic or
   manual retry is safe; this is the field's backend recovery purpose.
2. A mutating request becomes an unknown outcome once write/flush crosses the
   worker dispatch boundary; loss of the response must not be advertised as
   safely retryable.
3. Pre-dispatch expiration may be retryable only when the implementation
   reliably preserves and propagates its zero-write state.
4. The current release record satisfies the MR-level changelog gate; an
   additional entry for each review-only remediation commit is not required.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable documented gate.
- **NOTE-014 [performance]** Collect repeated live percentiles if the
  three-second target becomes an operational SLO.
- **NOTE-015 [documentation]** Synchronize the GitHub PR body with the current
  head and latest review decision; it still advertises obsolete findings and
  asks that the PR remain draft.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-002fd72.json`](./pr-review-macos-computer-use-3-002fd72.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: REQUEST_CHANGES
mergeable: false
head_sha: 002fd7226634c7777e07416cb2e4401843e7b2b0
blocking_findings:
  - PRR-020
resolved_findings:
  - PRR-019
validation_status: FAILED
report_status: CURRENT
```
