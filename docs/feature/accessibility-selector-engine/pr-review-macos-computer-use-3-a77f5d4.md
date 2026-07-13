# PR Review - `zhanghao1903/macos-computer-use#3` @ `a77f5d4`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `a77f5d45b0869f764105fef9cc62b45068e96fe4` |
| Reviewed at | 2026-07-13T16:51:42Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 113 commits; 100 changed files; 36,100 additions; 1,388 deletions |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable:** `true` under this Review Contract
- **Open blocking findings:** none
- **Resolved in the reviewed delta:** `PRR-019`
- **Rationale:** Lock waiting and worker startup now consume the same request
  deadline, both required pre-write checks are present, expired requests write
  zero frames without terminating a healthy worker, and an already-dispatched
  mutating action remains non-replayable. Exact-head CI and all required local
  runtime, resource, package, and release checks pass.

## 3. Executive Summary

The three-commit delta records, repairs, and verifies `PRR-019`. Worker access
is now acquired with the remaining request budget, followed by deadline checks
after lock acquisition and after startup/readiness immediately before dispatch.
Real subprocess tests prove both expired paths receive zero request frames and
that the same healthy process handles the next request.

No new blocking defect was identified. `PRR-001` through `PRR-019` are resolved
for this snapshot. The PR remains a GitHub draft and its platform body is stale;
those workflow/documentation states do not invalidate the reviewed code but
should be synchronized before the maintainer changes draft state or merges.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, complete changed-file metadata,
  full local `main...head` diff, and exact-head CI;
- focused `14c58c7...a77f5d4` delta: three commits, six files, 936 additions,
  and four deletions;
- `_AccessibilityWorker.run()` serialization, lock contention, startup,
  readiness, dispatch, response timeout, process preservation, and pipe cleanup;
- query fallback and mutating action no-replay call paths;
- both new real-subprocess deadline regressions and the existing framing,
  immediate-response, failed-readiness, and dispatched-timeout regressions;
- isolated root/package tests, compile, release preflight, wheel build/install,
  whitespace, clean-tree evidence, and feature documentation state.

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
| Worker queue deadline | Serialize first and acquire the worker lock only within the remaining budget. | A queued request returns timeout without late dispatch. | Low | Lock remains held beyond timeout; call completes with zero worker frames. |
| Startup/readiness deadline | Recheck the same deadline after `_ensure_started()` and before `stdin.write()`. | A ready worker is preserved when startup completion consumes the request budget. | Low | Delayed startup completion produces zero frames; follow-up reuses the same PID. |
| Mutating action safety | Keep post-dispatch response timeout termination and disable action fallback/replay. | Unknown action outcomes are not automatically duplicated. | Low | Existing dispatched-action timeout test records one dispatch and zero fallback calls. |
| Framing and resources | Retain readiness handshake, fd-level buffering, and pipe cleanup. | Immediate responses remain ordered and worker resources close cleanly. | Low | 100 query/action responses and warning-as-error package tests pass. |
| Compatibility and release | No public API, schema, config, dependency, or version change. | Existing 0.2.0 consumers retain the same surface. | Low | Root/package suites, compile, preflight, wheel checks, and CI pass. |

## 5. Findings

### PRR-019 - `[S2][Resolved][Concurrency]` Expired queued actions were dispatched before timeout was reported

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:241-310` @ `a77f5d45b0869f764105fef9cc62b45068e96fe4`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The previous worker fixed its deadline before waiting for the
  lock but could write after that wait consumed the complete budget. The current
  worker serializes within the budget, bounds lock acquisition by the remaining
  time, checks immediately after acquisition, and checks again after
  startup/readiness before writing.
- **Trigger:** Either another request holds the shared worker lock beyond this
  request's timeout, or a worker restart reaches readiness but startup completion
  returns after the same deadline.
- **Impact:** Before remediation, a mutating AX action could begin after its
  caller's timeout and then be retried as an unknown result. The repaired paths
  now return timeout before dispatch and preserve a healthy worker.
- **Evidence:**
  - `client.py:245-270` uses one monotonic deadline for serialization, bounded
    lock acquisition, startup/readiness, and the final pre-write gate;
  - `test_package.py:1082-1136` proves a lock-expired request completes while
    the lock remains held, writes zero frames, and reuses the same process;
  - `test_package.py:1138-1212` proves delayed startup completion after valid
    readiness writes zero frames and reuses the same process;
  - the prior post-dispatch timeout regression still records one action frame,
    terminates the timed-out worker, and makes zero one-shot fallback calls;
  - exact-head package tests, root tests, wheels, preflight, and CI pass.
- **Required change:** Completed. Expired requests must return timeout before
  writing, and pre-dispatch expiration must not kill a healthy worker.
- **Verification:** Completed. Both required zero-write counterexamples,
  follow-up same-process checks, framing stress, no-replay, package/root,
  release, wheel, and exact-head CI gates pass.

No blocking findings were identified for the reviewed snapshot.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-017` | Resolved | Privacy, focus/frame/identity, selector, packaging, workflow, pagination, proof, and performance paths remain unchanged and their gates remain green. |
| `PRR-018` | Resolved | Explicit readiness, fd-level framing, coalesced/100-response stress, resource cleanup, no-replay, and CI remain green. |
| `PRR-019` | Resolved | Bounded lock wait and post-readiness pre-write checks have deterministic zero-write and same-process regression proof. |

## 6. Required Actions Before Merge

None under this Review Contract.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish only bounded semantic evidence. / feature maintainer |
| data-integrity | Low | A timeout after actual dispatch still represents an unknown desktop outcome. | Never replay a dispatched mutating action; require caller recovery. / computer-use-macos |
| reliability-concurrency | Low | One worker intentionally serializes requests and may return pre-dispatch timeout under contention. | Charge queue/startup to one deadline and preserve the healthy process. / computer-use-macos |
| performance-scalability | Low | Contended calls can exhaust their budget before dispatch. | Return promptly without process churn; retain transport timing diagnostics. / computer-use-macos |
| api-compatibility | Low | Internal timeout timing is stricter for queued direct-mode requests. | Public APIs, schemas, failure status, configuration, and versions are unchanged. / computer-use-macos |
| deployment-rollback | Low | The warm worker remains on the direct/service path. | Revert the focused worker commits if needed; one-shot behavior remains available before worker dispatch. / feature maintainer |
| maintainability | Low | The private worker and generated scripts remain in a large module. | Keep real-subprocess contract tests; extract only as a separate change. / computer-use-macos |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root repository unittest discovery | isolated `55d76f1` implementation clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | 127 tests passed in 42.348 s, including wheel and release checks. |
| `app-control-protocol` unittest discovery | same isolated clone | PASS | 0 | 55 tests passed. |
| `computer-use-macos` discovery with `-W error::ResourceWarning` | same isolated clone | PASS | 0 | 139 tests passed, 1 skipped; no resource warnings. |
| `wechat-desktop-tool` unittest discovery | same isolated clone | PASS | 0 | 123 tests passed. |
| `.venv/bin/python -m compileall -q packages examples scripts tests` | same isolated clone | PASS | 0 | Python compilation passed. |
| `env -u PYTHONPATH .venv/bin/python scripts/release_preflight.py` | same isolated clone | PASS | 0 | All local gates passed; expected socket and unavailable external-proof warnings remained. |
| `/opt/anaconda3/bin/python scripts/wheel_check.py` | same isolated clone; Python 3.12 | PASS | 0 | Three 0.2.0 wheels built, installed, imported, passed API smoke, and rejected the 0.1.1 dependency set. |
| `git diff --check` and isolated `git status --short` | exact implementation clone and current review diff | PASS | 0 | No whitespace error; verification clone remained clean. |
| Strict mypy on changed `client.py` | exact implementation clone; mypy 1.11.2 | FAIL (non-gate baseline) | 1 | Three existing errors at lines 660, 2488, and 2537; none intersect the worker delta. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test - run 29267848330, job 86877739176](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29267848330/job/86877739176) | 2026-07-13T16:49:49Z | PASS | Exact reviewed head `a77f5d4`; GitHub reports mechanical mergeability and merge state CLEAN. |

### Checks not run

- **Fresh real WeChat action/send:** This transport correction is fully
  exercised with synthetic subprocesses and did not require another desktop
  mutation. Prior authorized live evidence is historical, not claimed as a
  post-PRR-019 rerun.
- **Post-submit delivery read-back:** Outside this worker deadline review.
- **Signed helper and real release publication:** Later release-stage external
  gates.
- **Ruff:** No Ruff executable or module is installed in the project virtual
  environment or available Anaconda runtime.

Overall in-scope validation passed. The optional strict-mypy run remains a
known, non-attributable repository baseline and does not weaken the runtime
counterexamples or merge decision.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `a77f5d45b0869f764105fef9cc62b45068e96fe4`.
- The complete feature diff is covered through the prior stable finding ledger
  plus focused re-review of the six-file delta and affected call paths.
- The implementation validation ran at `55d76f1`; `a77f5d4` adds only the
  corresponding verification documentation and passed exact-head CI.
- No fresh real desktop mutation, signed helper, or publication was performed.
- Private raw observations and unrelated dirty worktree files were excluded.
- The GitHub PR body still points to an old REQUEST_CHANGES snapshot, and the PR
  remains draft until the maintainer explicitly changes platform state.

## 10. Open Questions and Assumptions

### Open questions

None that block merge.

### Assumptions

1. A request timeout is a total caller budget, including serialization, queue,
   startup/readiness, dispatch, and response time.
2. A mutating request is potentially dispatched once write/flush begins; an
   unknown post-dispatch result must never trigger automatic replay.
3. Direct users may share one client across threads, and the worker lock is the
   intended serialization boundary.
4. The existing three strict-mypy errors are outside this delta and are not a
   configured CI merge gate.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable documented gate.
- **NOTE-014 [performance]** Collect repeated live percentiles if the
  three-second target becomes an operational SLO.
- **NOTE-015 [documentation]** Synchronize the GitHub PR body with this current
  review and the refreshed repository merge-readiness record before changing
  draft state.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-a77f5d4.json`](./pr-review-macos-computer-use-3-a77f5d4.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: a77f5d45b0869f764105fef9cc62b45068e96fe4
blocking_findings: []
resolved_findings:
  - PRR-019
validation_status: PARTIAL
report_status: CURRENT
```
