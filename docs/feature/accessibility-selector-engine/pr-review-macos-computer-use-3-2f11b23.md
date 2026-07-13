# PR Review - `zhanghao1903/macos-computer-use#3` @ `2f11b23`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `2f11b23b79040bf315513e1341d15a5e57f72379` |
| Reviewed at | 2026-07-13T15:52:52Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 109 commits; 96 changed files; 34,621 additions; 1,392 deletions |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable:** `true` under this Review Contract
- **Open blocking findings:** 0
- **Resolved in this review:** `PRR-018`
- **Rationale:** The warm-worker transport now completes and validates readiness before request dispatch, owns unbuffered newline framing, and retains the action no-replay boundary. Real subprocess counterexamples, package tests, packaging checks, and exact-head CI pass.

## 3. Executive Summary

The three-commit delta records `PRR-018`, replaces the unsafe
`select()`/`TextIOWrapper.readline()` combination with explicit fd-level
framing, and adds real subprocess protocol tests. Query and action workers each
returned 100 immediate responses without timeout or cross-wiring, including
fresh-worker first requests under a 0.2-second deadline. A dispatched synthetic
action with no response still returns timeout without subprocess replay.

No new blocking finding was identified. `PRR-001` through `PRR-018` are
resolved for the reviewed snapshot. A fresh real WeChat mutation was not run;
the prior live AppKit integration proof remains historical context while the
new transport race is closed by direct subprocess protocol evidence.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, complete changed-file inventory,
  and local `main...head` diff;
- the focused `435d945...2f11b23` delta: 3 commits, 6 files, 1,053 additions,
  and 27 deletions;
- `_AccessibilityWorker` startup, framing, timeout, restart, locking, and pipe
  lifecycle;
- query fallback and action no-replay call paths;
- real subprocess first-response, repeated-response, coalesced-frame,
  readiness-failure, timeout, and resource-cleanup tests;
- prior finding lifecycle, deterministic feature gates, package compatibility,
  release preflight, and exact-head GitHub CI.

### Excluded scope

- a new real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff and strict mypy baseline cleanup.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Worker startup | `start()` consumes and validates one readiness frame before requests. | A worker with failed or missing readiness is unavailable before dispatch. | Low | Failed-readiness subprocess test and constructor path review. |
| Response framing | Parent uses `os.read()` plus an owned byte buffer and newline frames. | Buffered fast responses are not lost behind kernel-fd readiness checks. | Low | Coalesced-frame test, 100 query responses, 100 action responses, and fresh-worker stress. |
| Mutating action safety | Worker failures after request write still return directly. | Unknown action outcomes are never replayed through one-shot subprocess fallback. | Low | Synthetic dispatch marker plus timeout and zero fallback calls. |
| Process lifecycle | Timeout, failure, and stop clear framing state and close pipes. | Repeated workers do not leak pipe wrappers. | Low | Full package suite with `ResourceWarning` promoted to error. |
| Packaging and CI | No public API, schema, config, dependency, or version change. | Existing 0.2.0 consumers and helper behavior remain compatible. | Low | Root/package suites, wheel build/install, preflight, and exact-head CI. |

## 5. Findings

No new open findings were identified.

### PRR-018 - `[S1][Blocking][Reliability]` Warm worker could lose a buffered response and report a false timeout

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:231-449` @ `2f11b23b79040bf315513e1341d15a5e57f72379`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The previous implementation checked the kernel fd before every buffered text `readline()`. Readiness and a fast response could enter the text wrapper together, leaving the response invisible to the next `select()`.
- **Trigger:** A newly started query or action worker emits readiness and then handles the first request before the parent consumes readiness.
- **Impact:** Queries could falsely time out; a mutating action could execute and still be reported as unknown, making manual retries hazardous.
- **Evidence:** `start()` now completes readiness before request write; `_read_response_line()` checks an owned byte buffer before `select()` and reads with `os.read()`; real subprocess tests cover coalesced frames, 100 immediate query responses, 100 immediate action responses, and unknown action outcomes.
- **Required change:** Completed. Preserve a one-readiness/one-request/one-response protocol without replaying a dispatched action.
- **Verification:** Exact-head fresh-worker stress passed 100/100 query and 100/100 action requests at 0.2 seconds. The `computer-use-macos` suite passed 137 tests with one conditional skip and `ResourceWarning` treated as an error.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-012` | Resolved | Privacy-safe proof, focus/frame/ambiguity guards, helper/cache/failure/batch/pagination fixes, coordinated packaging, and strict release checks remain unchanged and green. |
| `PRR-013` through `PRR-016` | Resolved | Verified public focus/open paths, target identity, row identity, and visible-window pagination remain unchanged and green. |
| `PRR-017` | Resolved | Historical exact-head live evidence recorded a 2461 ms public send, 1272 ms Contacts-origin open, and 58 ms warm Chats action. |
| `PRR-018` | Resolved | Explicit readiness, fd-level framing, real subprocess stress, unknown-outcome no-replay, and exact-head CI pass. |

## 6. Required Actions Before Merge

- [x] `PRR-018` - repair readiness/response framing, add real subprocess regression tests, prove fast query/action responses do not falsely time out, and preserve mutating-action no-replay.

No required action remains under this Review Contract. Changing the draft PR
to ready, merging it, and publishing a release remain repository-owner actions.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish only bounded semantic evidence. / feature maintainer |
| data-integrity | Low | A genuine lost action response can still leave the desktop outcome unknown. | Never replay after dispatch; require observation or manual recovery. / computer-use-macos |
| reliability-concurrency | Low | Workers serialize requests and depend on newline-delimited UTF-8 frames. | Lock one request to one response, cap frames at 16 MiB, fail and restart on protocol errors. / computer-use-macos |
| performance-scalability | Low | Startup now waits up to five seconds for readiness if a framework hangs. | Startup is outside the warm API path; failures disable the worker and retain the pre-dispatch fallback. / computer-use-macos |
| api-compatibility | Low | Direct-mode internal transport changed. | Public APIs, schemas, config, helper transport, versions, and dependencies are unchanged. / computer-use-macos |
| deployment-rollback | Low | Reverting only the framing fix would restore the known S1 race. | Roll back the complete warm-worker slice or disable it; do not restore the old mixed-buffer reader. / feature maintainer |
| maintainability | Low | Parent framing and generated worker scripts remain private implementation details in one large module. | Preserve focused protocol tests; future extraction can be a separate cleanup. / computer-use-macos |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | isolated `2f11b23` clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | 137 tests passed, 1 skipped; real worker framing and no-replay tests included. |
| Real `_AccessibilityWorker`, new process per request, `timeout=0.2`, 100 query plus 100 action requests | isolated `2f11b23` clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | Query 100/100 and action 100/100; zero timeout, loss, or cross-wiring. |
| `.venv/bin/python -m compileall -q packages examples scripts tests` | isolated `2f11b23` clone; CPython 3.12.7 | PASS | 0 | Python compilation passed. |
| `git diff --check origin/main...HEAD` | isolated `2f11b23` clone | PASS | 0 | No whitespace errors. |
| Root and all package suites | isolated `68d2e4f` implementation clone; code identical to `2f11b23` | PASS | 0 | Root 127; protocol 55; computer-use 137 plus 1 skip; WeChat 123. |
| Release preflight and `/opt/anaconda3/bin/python scripts/wheel_check.py` | isolated `68d2e4f` implementation clone; Python 3.12 | PASS | 0 | Preflight passed; all wheels built, installed, imported, passed API smoke, and rejected incompatible 0.1.1 dependencies. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test - run 29263722778, job 86863397587](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29263722778/job/86863397587) | 2026-07-13T15:50:17Z | PASS | Exact head `2f11b23` completed in 2m37s; GitHub reports the PR mechanically mergeable and CLEAN. |

### Checks not run

- **Fresh real WeChat action/send:** No new live mutation authorization was
  used for this review. The parent protocol is covered directly with real
  subprocesses; prior live worker/AppKit evidence remains historical context.
- **Post-submit delivery read-back:** Outside the framing remediation and not
  requested.
- **Signed helper and real release publication:** Later F7 external gates.
- **Ruff:** No executable or module is installed in the project environment.
- **Strict mypy:** The repository has a broad existing baseline; this runtime
  transport defect is distinguished by subprocess tests rather than that gate.

Overall validation status: `PASSED`.

## 9. Coverage and Limitations

- This report is authoritative for head
  `2f11b23b79040bf315513e1341d15a5e57f72379`.
- The reviewed delta changes only internal direct-mode worker transport, tests,
  and feature evidence; no public schema or package metadata changed.
- No fresh real desktop mutation was performed after the framing fix.
- Historical live evidence proves AppKit worker integration but not delivery
  read-back or latency percentiles.
- Private raw observations and unrelated dirty worktree files were excluded.
- The report commit itself is documentation-only and follows the reviewed
  snapshot, consistent with the repository's review-artifact convention.

## 10. Open Questions and Assumptions

### Open questions

None.

### Assumptions

1. Newline-delimited UTF-8 is the private worker protocol contract.
2. A mutating request is considered potentially dispatched once its write and
   flush are attempted; subsequent failure must never trigger automatic replay.
3. The prior live AppKit proof plus direct post-fix subprocess framing proof is
   sufficient for this transport-only remediation without another desktop
   mutation.
4. The 16 MiB private response cap exceeds every bounded selector response
   permitted by current query limits.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable local gate.
- **NOTE-014 [performance]** Collect repeated live samples and percentiles if
  the three-second feature target becomes an operational SLO.
- **NOTE-015 [documentation]** Update merge-readiness and the PR description to
  reference this review and `PRR-018` closure.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-2f11b23.json`](./pr-review-macos-computer-use-3-2f11b23.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: 2f11b23b79040bf315513e1341d15a5e57f72379
blocking_findings: []
resolved_findings:
  - PRR-018
validation_status: PASSED
report_status: CURRENT
```
