# PR Review - `zhanghao1903/macos-computer-use#3` @ `3392c27`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `3392c27cb7aec8efa0d9bc722a8d2ef775d1ddd9` |
| Reviewed at | 2026-07-14T17:02:44Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 119 commits; 106 changed files; 38,274 additions; 1,387 deletions |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` under this Review Contract
- **Open blocking findings:** 1 (`PRR-021`)
- **Resolved in the reviewed delta:** `PRR-020`
- **Rationale:** The focused action-timeout change correctly classifies the
  worker dispatch boundary, but WeChat's higher-level recovery paths ignore
  that boundary and can execute a second UI action after a dispatched action
  loses its response. A deterministic cross-package probe reproduced one
  recorded `AXPress` followed by a coordinate click and an outer success result.

## 3. Executive Summary

The four-commit delta from `002fd72` records, repairs, verifies, and documents
`PRR-020`. At the macOS protocol boundary, explicit pre-dispatch timeouts remain
retryable while dispatched or unknown action outcomes now fail closed.

The complete caller-path re-review found `PRR-021`: WeChat navigation, contact,
and search recovery can discard the non-retryable/dispatch evidence and perform
another click, Return keypress, or strategy after the first action may already
have executed. The PR must not merge until every mutating fallback honors the
same no-replay boundary and cross-package regressions prove that dispatched or
unknown outcomes cause zero additional mutations.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, full changed-file metadata,
  complete local `main...head` diff, commit history, and exact-head CI;
- focused `002fd72...3392c27` delta: four commits, 11 files, 1,642 additions,
  and 57 deletions;
- `_AccessibilityWorker.run()` serialization, lock/startup deadline, write
  boundary, EOF/protocol failure, response timeout, and dispatch evidence;
- action result conversion, transport propagation, protocol retryability, and
  top-level/nested error consistency;
- WeChat mapped navigation, `_click_node_phase`, visible-contact, search-result,
  search-focus, Return, coordinate, selector, and strategy-continuation paths;
- native Accessibility action payload construction, including the
  `actionAttempted` field after the native API call;
- isolated root/package suites, focused stability checks, compilation, release
  preflight, whitespace, clean-tree evidence, docs, changelog, and lifecycle
  records.

### Excluded scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff installation and repository-wide strict-mypy cleanup.

### Change map

| Area | Main change or observation | External behavior | Risk | Validation |
|---|---|---|---|---|
| Worker dispatch evidence | A private result records whether a worker write was attempted. | Action transport exposes `requestDispatched` when known. | Low | Pre/post-dispatch, unknown worker, subprocess, and 100-response tests pass. |
| Protocol recovery | Only an action timeout with explicit `requestDispatched=false` is retryable. | Top-level and nested retryability agree and unknown outcomes fail closed. | Low | `PRR-020` focused tests pass for ten consecutive iterations. |
| WeChat recovery | Higher-level paths select fallback by generic failure kind or strategy failure and ignore dispatch/retryability. | A dispatched action can be followed by coordinate click, Return, or another mutation. | High | Cross-package dispatch-then-EOF probe reproduced `accessibility_action` then `click`. |
| Native action evidence | The generated worker calls the native action before handling a nonzero error, while generic `fail()` still emits `actionAttempted=false`. | A structured failure can understate that the native API was invoked. | High | Static call-path proof at `client.py:4059-4067,4367-4377`. |
| Review and release records | Current branch adds the `ba733dc` approval artifacts, but the PR advanced to `3392c27`. | The prior report and tracked merge-readiness claim are stale; the GitHub body is older still. | Medium | Current SHA, platform body, branch docs, and exact-head CI were compared. |

## 5. Findings

### PRR-021 - `[S1][Blocking][Reliability/Safety]` WeChat replays an action after the backend reports a dispatched unknown outcome

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:946-985,1360-1382,1461-1478,1537-1554,1718-1802,2997-3029,4119-4139` @ `3392c27cb7aec8efa0d9bc722a8d2ef775d1ddd9`
- **Confidence:** High
- **Status:** open
- **Observation:** The macOS layer preserves `requestDispatched=true` and
  returns `retryable=false` after an action request is written but its response
  is lost. WeChat's coordinate/Return/strategy recovery gates inspect only a
  generic `accessibility_action_failed` kind, or collapse any failed strategy
  to `None`, so they can issue another mutating command despite that explicit
  no-replay result.
- **Trigger:** A warm action worker reads an `AXPress` request and the native
  operation executes or may execute, but the worker exits, emits EOF, returns a
  malformed response, or otherwise loses the result before the parent receives
  a successful frame. Structured native action failure is another unsafe case
  because the current payload sets `actionAttempted=false` even after invoking
  the native API.
- **Impact:** One semantic operation can perform two desktop mutations. If the
  first action changes the WeChat view, the fallback uses coordinates from the
  old snapshot and may activate a different control. The outer layer can then
  report success, hiding the unknown first outcome and violating the PR's
  documented no-replay contract.
- **Evidence:**
  - `client.py:289-337,1509-1517,1582-1592` marks write-attempted EOF/protocol
    failure as dispatched, exposes that evidence, and returns a non-retryable
    `accessibility_action_failed` observation;
  - `tool.py:4119-4127` unconditionally authorizes coordinate fallback for that
    generic failure kind, and `tool.py:3008-3026` issues the second click;
  - mapped navigation, search result, visible-contact, and search-focus paths at
    the other listed locations repeat the same root behavior through coordinate
    click, Return, selector click, or continued strategy search;
  - a safe synthetic worker recorded exactly one `AXPress`, returned
    `requestDispatched=true` with both retryability fields `false`, made zero
    macOS one-shot fallback calls, and then the WeChat layer issued
    `['accessibility_action', 'click']` with stale coordinates and returned
    success; the invariant probe exited 21;
  - `client.py:4059-4067,4367-4377` calls the native action before handling its
    error but emits `actionAttempted=false` from the generic failure helper;
  - `test_tool.py:1655-1686,2586-2647` contains no dispatch evidence and
    explicitly expects generic action failure to be followed by `click`, so the
    green suite currently encodes the unsafe behavior rather than refuting it.
- **Required change:** Centralize a side-effect recovery predicate and apply it
  before every alternative action or strategy continuation. A dispatched,
  attempted, non-retryable, or unknown action outcome must fail closed with zero
  additional click, keypress, selector action, or search mutation. Only an
  explicitly proven pre-dispatch result or an explicitly unsupported operation
  may authorize an automatic fallback. Correct native action-attempt evidence
  so a post-call error is not represented as `actionAttempted=false`.
- **Verification:** Add cross-package regressions using a real synthetic worker
  for dispatch-then-EOF, post-dispatch timeout, malformed response, and native
  action failure. Assert one recorded action, `requestDispatched=true` (or
  unknown), non-retryable public guidance, zero further mutating commands in
  every affected WeChat path, and preservation of explicitly safe
  pre-dispatch/unsupported fallback behavior.

### PRR-020 - `[S2][Resolved][API Contract]` A dispatched action timeout was incorrectly advertised as retryable

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:210-351,1493-1507,1573-1592,5024-5070` @ `3392c27cb7aec8efa0d9bc722a8d2ef775d1ddd9`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The prior worker result lost the write boundary and generic
  protocol mapping made every action timeout retryable. The current worker
  result preserves dispatch state and `_result_retryable()` returns true only
  when `requestDispatched` is exactly `false`.
- **Trigger:** The caller deadline expires either before the worker write or
  after the worker received an action but before its response arrives.
- **Impact:** Before remediation, a direct protocol consumer could retry an
  already-executed action. The macOS protocol result now distinguishes the safe
  zero-write case from dispatched and unknown outcomes.
- **Evidence:**
  - `client.py:210-351,1573-1592,5024-5070` retains and consumes dispatch
    evidence with fail-closed unknown handling;
  - `test_package.py:1712-1753,1893-2082` covers subprocess unknown, fake-worker
    unknown, real pre-dispatch, and real post-dispatch outcomes;
  - the full package suite passed, and the real pre/post-dispatch pair passed
    ten consecutive iterations (20 executions) under strict resource warnings;
  - exact-head GitHub CI passed all configured checks.
- **Required change:** Completed at the macOS protocol boundary. `PRR-021`
  separately tracks downstream callers that bypass this result.
- **Verification:** Completed for direct consumers: pre-dispatch, post-dispatch,
  unknown transport, non-action compatibility, package/root, release, and
  exact-head CI checks pass.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-017` | Resolved | Privacy, identity, selector, packaging, workflow, pagination, proof, and performance gates remain green. |
| `PRR-018` | Resolved | Readiness, fd-level framing, stress, cleanup, and internal no-replay gates remain green. |
| `PRR-019` | Resolved | Bounded queue/startup deadline, zero-write expiration, and worker preservation remain green. |
| `PRR-020` | Resolved | Direct action-timeout recovery is dispatch-aware and fail-closed. |
| `PRR-021` | Open, blocking | WeChat downstream recovery still replays dispatched or unknown action outcomes. |

## 6. Required Actions Before Merge

- [ ] `PRR-021` - Make every WeChat mutating fallback honor dispatch,
  attempt, and non-retryable evidence; correct post-native-call attempt
  reporting; add cross-package no-replay regressions for all affected paths.

`PRR-020` is completed; it does not close `PRR-021`'s downstream replay path.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish bounded semantic evidence only. / feature maintainer |
| data-integrity | High | A fallback can mutate the post-action UI using a stale frame. | Block merge; fail closed after dispatch/attempt/unknown outcome. / wechat-desktop-tool |
| reliability-concurrency | High | Lost or malformed worker responses produce duplicate high-level actions. | Centralize no-replay recovery and add real-worker cross-package tests. / both package owners |
| performance-scalability | Low | One worker serializes operations and can apply queue backpressure. | Retain the bounded deadline and timing diagnostics. / computer-use-macos |
| api-compatibility | Medium | The direct result is correct, but downstream behavior contradicts its retryability contract. | Treat public recovery fields as authoritative across package boundaries. / package maintainers |
| deployment-rollback | Medium | Shipping this feature exposes the unsafe fallback on normal WeChat workflows. | Fix before merge or revert the higher-level automatic fallbacks; no data migration exists. / feature maintainer |
| maintainability | Medium | Recovery policy is duplicated across several helpers and strategy branches. | Use one predicate and parameterized path coverage. / wechat-desktop-tool |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Synthetic dispatch-then-EOF macOS-to-WeChat invariant probe (`PYTHONPATH=... python - <<'PY'`) | isolated `3392c27`; Darwin arm64; CPython 3.12.7 | FAIL (defect reproduced) | 21 | One `AXPress`; lower `requestDispatched=true`, top-level/nested retryable false, zero runner fallback; upper operations were `accessibility_action`, `click`, and upper result was success. |
| Root repository unittest discovery | same exact-head isolated clone | PASS | 0 | 127 tests passed in 70.268 s. |
| `app-control-protocol` unittest discovery | same exact-head isolated clone | PASS | 0 | 55 tests passed in 0.010 s. |
| `computer-use-macos` with `-W error::ResourceWarning` | same exact-head isolated clone | PASS | 0 | 141 tests passed in 1.580 s; 1 Unix-socket sandbox skip; no resource warning. |
| Real pre/post-dispatch focused pair repeated 10 times | separate clean exact-head clone; strict resource warnings | PASS | 0 | 20 executions passed; each pre-dispatch case wrote zero frames and each post-dispatch case recorded one action. |
| `wechat-desktop-tool` unittest discovery | exact-head isolated clone | PASS | 0 | 123 tests passed in 0.338 s; current expectations do not cover dispatch evidence. |
| `PYTHONPYCACHEPREFIX=/private/tmp/... python -m compileall -q packages scripts tests examples` | exact-head isolated clone | PASS | 0 | Python compilation passed without dirtying the clone. |
| `PYTHONDONTWRITEBYTECODE=1 python scripts/release_preflight.py` | exact-head isolated clone | PASS | 0 | All mandatory gates passed; expected socket and seven unavailable external-proof warnings remained. |
| `git diff --check origin/main...HEAD` and final `git status --short` | exact-head isolated clone | PASS | 0 | No whitespace error; verification clone remained clean. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test - run 29343716952, job 87121834070](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29343716952/job/87121834070) | 2026-07-14T16:54:20Z | PASS | Exact head `3392c27`; configured tests/package/wheel checks pass, but no cross-package dispatch-aware fallback test exists. |

### Checks not run

- **Fresh real WeChat action/send:** The blocking replay is deterministically
  reproduced with a synthetic worker and fake outer transport; no desktop
  mutation was needed or authorized.
- **Post-submit delivery read-back:** Outside this recovery review.
- **Signed helper and real release publication:** Later F7 external gates.
- **Ruff and strict mypy:** Ruff is unavailable; the previously recorded mypy
  baseline is not a configured passing gate and was not rerun for this docs/code
  delta.

Overall validation status is `FAILED`: broad suites and CI are green, but the
targeted safety invariant fails deterministically.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `3392c27cb7aec8efa0d9bc722a8d2ef775d1ddd9`; any new commit requires re-review.
- The complete feature diff is covered through the prior stable finding ledger,
  focused review of the 11-file delta, and a new end-to-end cross-package action
  recovery trace.
- Local validation ran on clean exact-head clones. The main shared worktree's
  unrelated user changes and private/untracked proof files were excluded.
- No fresh real desktop mutation, signed helper, or publication was performed.
- The prior `ba733dc` report and tracked merge-readiness/PR-description records
  are stale at this head, and `PRR-021` invalidates their approval conclusion.
- The GitHub PR remains draft and its platform body still describes the much
  older `07fa052` request-changes result with 12 blockers.

## 10. Open Questions and Assumptions

### Open questions

None that change the blocking decision. The author may choose whether an
explicitly proven pre-dispatch result should trigger an automatic alternative
method or be returned to the caller; either choice must preserve no replay.

### Assumptions

1. Coordinate click, selector click, Return, and continued search/open strategy
   are retries of the same semantic side effect when invoked after an action
   failure.
2. Once a mutating worker request is written, response loss leaves the desktop
   outcome unknown even if the protocol status is `failed` rather than
   `timeout`.
3. `retryable=false`, `requestDispatched=true`, and missing dispatch evidence
   require fail-closed behavior unless a stronger explicit pre-dispatch fact is
   available.
4. Green broad tests cannot override a deterministic counterexample when those
   tests currently assert the unsafe fallback sequence.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable documented gate.
- **NOTE-014 [performance]** Collect repeated live percentiles if the
  three-second target becomes an operational SLO.
- **NOTE-015 [documentation]** After `PRR-021` is fixed and re-reviewed,
  synchronize the GitHub PR body, tracked PR description, and merge-readiness
  record before changing draft state.
- **NOTE-016 [release record]** Expand the Unreleased changelog entry to name
  the warm action worker and dispatch-aware recovery behavior before release.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-3392c27.json`](./pr-review-macos-computer-use-3-3392c27.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: REQUEST_CHANGES
mergeable: false
head_sha: 3392c27cb7aec8efa0d9bc722a8d2ef775d1ddd9
blocking_findings:
  - PRR-021
resolved_findings:
  - PRR-020
validation_status: FAILED
report_status: CURRENT
```
