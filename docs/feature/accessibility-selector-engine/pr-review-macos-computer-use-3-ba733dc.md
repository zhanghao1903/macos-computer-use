# PR Review - `zhanghao1903/macos-computer-use#3` @ `ba733dc`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `ba733dc622f794b7e49bba17b96f64a0ac4c2e0a` |
| Reviewed at | 2026-07-14T14:59:34Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 118 commits; 104 changed files; 37,689 additions; 1,387 deletions |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable:** `true` under this Review Contract
- **Open blocking findings:** none
- **Resolved in the reviewed delta:** `PRR-020`
- **Rationale:** Accessibility action timeout recovery now retains the worker
  dispatch boundary. Only a proven zero-write timeout is retryable; dispatched
  or unknown action outcomes are fail-closed. Real subprocess counterexamples,
  package/root gates, release checks, and exact-head CI all pass.

## 3. Executive Summary

The three-commit delta records, repairs, and verifies `PRR-020`. The private
worker result distinguishes pre-write expiration from a write-attempted
request, carries that evidence through action transport metadata, and computes
one protocol retryability value for both the observation and nested error.

No new blocking defect was identified. `PRR-001` through `PRR-020` are resolved
for this snapshot. The PR remains a GitHub draft; changing draft state and
merging remain maintainer actions after the tracked PR description is
synchronized to the platform.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, complete changed-file metadata,
  full local `main...head` diff, and exact-head GitHub CI;
- focused `002fd72...ba733dc` delta: three commits, seven files, 1,020
  additions, and 20 deletions;
- `_AccessibilityWorker.run()` request serialization, queue/startup deadline,
  write boundary, response timeout, termination, and result classification;
- action transport propagation, timeout conversion, protocol retryability, and
  top-level/nested error consistency;
- real pre-dispatch and post-dispatch worker counterexamples, unknown legacy
  worker timeout, one-shot subprocess timeout, framing stress, and generic
  non-action timeout compatibility;
- isolated root/package tests, compilation, release preflight, wheel checks,
  whitespace, clean-tree evidence, API docs, and feature lifecycle records.

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
| Worker dispatch evidence | A private result records whether write/flush was attempted. | Action transport exposes `requestDispatched` when known. | Low | Success, lock-timeout, startup-timeout, and response-timeout paths are asserted. |
| Pre-dispatch timeout | A zero-write timeout carries `requestDispatched=false`. | Both retryability fields remain `true`. | Low | Lock held beyond the budget; zero frames and zero fallback calls. |
| Post-dispatch timeout | A write-attempted timeout carries `requestDispatched=true`. | Both retryability fields are `false`. | Low | Exactly one synthetic `AXPress`; response withheld; zero fallback calls. |
| Unknown action outcome | Missing dispatch evidence fails closed. | Legacy worker and subprocess timeouts are not retryable. | Low | Dedicated protocol regressions pass. |
| Compatibility and release | No command or schema version changed; diagnostics are additive. | Non-action timeout behavior is unchanged. | Low | Root/package suites, docs, wheels, preflight, and CI pass. |

## 5. Findings

### PRR-020 - `[S2][Resolved][API Contract]` A dispatched action timeout was incorrectly advertised as retryable

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:210-351,1493-1507,1573-1592,5025-5070` @ `ba733dc622f794b7e49bba17b96f64a0ac4c2e0a`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The prior implementation suppressed internal action replay
  but converted every action timeout into a generic retryable protocol result.
  The current worker result preserves the dispatch boundary, the action
  transport carries that evidence, and `_result_retryable()` permits retry only
  when `requestDispatched` is exactly `false`.
- **Trigger:** A worker receives an `AXPress` request but its response is lost or
  exceeds the caller deadline; alternatively, the caller's deadline expires
  before the worker lock can be acquired.
- **Impact:** Before remediation, a consumer could follow `retryable=true` and
  duplicate an already-executed UI action. The current result prevents that
  retry while retaining safe recovery for a proven zero-write timeout.
- **Evidence:**
  - `client.py:210-351` marks every result before a write attempt as
    undispatched and every write/read/response result after that boundary as
    dispatched;
  - `client.py:1573-1592` exposes known dispatch evidence in action transport;
  - `client.py:5025-5070` computes one fail-closed retryability value used to
    construct both public protocol fields;
  - `test_package.py:1932-2006` proves pre-dispatch timeout, zero frames, zero
    fallback, `requestDispatched=false`, and both retryability fields `true`;
  - `test_package.py:2008-2082` proves one recorded `AXPress`, zero fallback,
    `requestDispatched=true`, and both retryability fields `false`;
  - unknown worker and subprocess timeout tests prove missing evidence remains
    non-retryable, while the existing non-action timeout stays retryable;
  - exact-head local package/root/release checks and GitHub CI pass.
- **Required change:** Completed. Preserve dispatch evidence and fail closed for
  dispatched or unknown mutating outcomes.
- **Verification:** Completed. Both sides of the dispatch boundary, unknown
  transports, non-action compatibility, framing/resource stress, package/root,
  wheel, preflight, and exact-head CI gates pass.

No blocking findings were identified for the reviewed snapshot.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-017` | Resolved | Privacy, focus/frame/identity, selector, packaging, workflow, pagination, proof, and performance paths remain unchanged and their gates remain green. |
| `PRR-018` | Resolved | Explicit readiness, fd-level framing, coalesced/100-response stress, cleanup, internal no-replay, and CI remain green. |
| `PRR-019` | Resolved | Bounded queue/startup deadline, zero-write expiration, healthy-worker preservation, and exact-head CI remain green. |
| `PRR-020` | Resolved | Dispatch-aware action timeout recovery has protocol-level pre/post-dispatch and unknown-outcome proof. |

## 6. Required Actions Before Merge

None under this Review Contract.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish bounded semantic evidence only. / feature maintainer |
| data-integrity | Low | A timeout after dispatch remains an unknown desktop outcome. | Emit non-retryable recovery guidance and never replay internally. / computer-use-macos |
| reliability-concurrency | Low | Contended calls can expire before dispatch. | Use one deadline, return zero-write evidence, and preserve a healthy worker. / computer-use-macos |
| performance-scalability | Low | One worker serializes operations and can apply queue backpressure. | Bound lock wait with the caller deadline and retain timing diagnostics. / computer-use-macos |
| api-compatibility | Low | Action-timeout recovery changes from unsafe generic retryability to dispatch-aware guidance. | Additive transport evidence, stable status/failure kind, and explicit API docs. / computer-use-macos |
| deployment-rollback | Low | The warm action worker remains on the direct/service path. | Revert the focused worker remediation commits if needed; no data migration exists. / feature maintainer |
| maintainability | Low | Dispatch safety spans the private worker and generic protocol mapper. | Keep the boundary explicit and retain real-subprocess contract tests. / computer-use-macos |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root repository unittest discovery | isolated `74d5890` implementation clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | 127 tests passed in 53.942 s, including wheel build/install/API smoke and release checks. |
| `app-control-protocol` unittest discovery | same isolated clone | PASS | 0 | 55 tests passed. |
| `computer-use-macos` with `-W error::ResourceWarning` | same isolated clone | PASS | 0 | 141 tests passed, 1 skipped; no resource warning. |
| `wechat-desktop-tool` unittest discovery | same isolated clone | PASS | 0 | 123 tests passed. |
| `.venv/bin/python -m compileall -q packages examples scripts tests` | same isolated clone | PASS | 0 | Python compilation passed. |
| `env -u PYTHONPATH .venv/bin/python scripts/release_preflight.py` | same isolated clone | PASS | 0 | All local gates passed; expected socket and unavailable external-proof warnings remained. |
| `git diff --check origin/main...HEAD` and `git status --short` | exact implementation clone and current review diff | PASS | 0 | No whitespace error; verification clone remained clean. |
| `uv run mypy .../client.py` | exact implementation clone | FAIL (non-gate baseline) | 1 | 29 existing strict errors across imported modules; no error intersects a remediation line. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test - run 29342939601, job 87119164572](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29342939601/job/87119164572) | 2026-07-14T14:59:34Z | PASS | Exact reviewed head `ba733dc`; GitHub reports mechanical mergeability and merge state CLEAN. |

### Checks not run

- **Fresh real WeChat action/send:** The recovery classification is fully
  distinguished with synthetic subprocess frames and protocol results; no new
  desktop mutation was required.
- **Post-submit delivery read-back:** Outside this worker recovery review.
- **Signed helper and real release publication:** Later F7 external gates.
- **Ruff:** No Ruff executable or module is installed in the available project
  runtimes.

Overall in-scope validation passed. Optional external/live and repository-wide
strict type cleanup remain explicitly outside this merge decision.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `ba733dc622f794b7e49bba17b96f64a0ac4c2e0a`.
- The complete feature diff is covered through the prior stable finding ledger
  plus focused re-review of the seven-file remediation delta and affected
  end-to-end timeout/result path.
- Local implementation validation ran at `74d5890`; `ba733dc` adds only the
  corresponding verification document and passed exact-head CI.
- No fresh real desktop mutation, signed helper, or publication was performed.
- Private raw observations and unrelated dirty worktree files were excluded.
- The GitHub PR remains draft, and its platform body still requires
  synchronization with this current review.

## 10. Open Questions and Assumptions

### Open questions

None that block merge.

### Assumptions

1. Protocol consumers use `retryable` as recovery guidance and may automate a
   retry when it is `true`.
2. A mutating request has an unknown outcome once `stdin.write()` is attempted,
   even if write or flush later raises.
3. Missing dispatch evidence must fail closed for action timeouts.
4. The existing strict-mypy errors are outside this delta and are not a
   configured CI merge gate.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable documented gate.
- **NOTE-014 [performance]** Collect repeated live percentiles if the
  three-second target becomes an operational SLO.
- **NOTE-015 [documentation]** Synchronize the GitHub PR body with this review
  and the refreshed merge-readiness record before changing draft state.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-ba733dc.json`](./pr-review-macos-computer-use-3-ba733dc.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: ba733dc622f794b7e49bba17b96f64a0ac4c2e0a
blocking_findings: []
resolved_findings:
  - PRR-020
validation_status: PARTIAL
report_status: CURRENT
```
