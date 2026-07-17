# PR Review - `zhanghao1903/macos-computer-use#3` @ `d20636c`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `d20636cd5edf3db4e9521a982fce976cbbb656ba` |
| Reviewed at | 2026-07-14T18:37:47Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE` |
| Scope size | 122 commits; 108 changed files; 39,761 additions; 1,466 deletions |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable:** `true` under this Review Contract
- **Open blocking findings:** none
- **Resolved in the reviewed delta:** `PRR-021`
- **Rationale:** WeChat now applies one dispatch- and attempt-aware recovery
  predicate before every mutating fallback. Real synthetic-worker
  counterexamples, path-specific regressions, package/root gates, wheel checks,
  and exact-head GitHub CI all pass.

## 3. Executive Summary

The three-commit delta records, repairs, and verifies `PRR-021`. Dispatched,
attempted, non-retryable, and unknown Accessibility action outcomes now stop
before any coordinate click, selector click, Return keypress, or next mutating
strategy. Only an explicitly proven pre-dispatch retryable result or an
explicitly unsupported action can use one configured fallback.

The generated native action script also reports `actionAttempted=true` after a
native API invocation returns an error. No new blocking defect was identified;
`PRR-001` through `PRR-021` are resolved for this snapshot. The PR remains a
GitHub draft, and its stale platform description should be synchronized before
changing draft state.

## 4. Scope and Change Map

### Reviewed scope

- current PR metadata, exact base/head SHAs, complete changed-file metadata,
  full local `main...head` diff, and exact-head GitHub CI;
- focused `3392c27...d20636c` delta: three commits, ten files, 1,461 additions,
  and 53 deletions, including the prior report and F5 evidence;
- focused `b8d4bbd` implementation: seven files covering the macOS native
  action script, WeChat recovery, tests, and developer documentation;
- mapped navigation, node click, selector fallback, control-map and selector
  visible-contact opening, search focus, search result, Return, coordinate, and
  public actionRef paths;
- EOF, post-dispatch timeout, malformed response, structured native failure,
  pre-dispatch timeout, and unsupported-action outcomes;
- isolated root/package tests, ten-iteration cross-package stress, compilation,
  release preflight, wheel build/install, whitespace, clean-tree evidence, and
  exact-head CI.

### Excluded scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff and mypy, which are unavailable in the workspace environment and are
  not configured CI gates.

### Change map

| Area | Main change or observation | External behavior | Risk | Validation |
|---|---|---|---|---|
| Recovery policy | One predicate consumes attempt, dispatch, retryability, and unsupported evidence. | Unsafe or unknown action outcomes return without another mutation. | Low | Four real-worker unsafe outcomes and path-specific tests pass. |
| Safe fallback | Proven pre-dispatch retryable and explicit unsupported outcomes retain one fallback. | Existing compatibility fallback remains available without replaying an action. | Low | Real worker lock-timeout and unsupported-response tests pass. |
| Fallback finality | A selector fallback result is returned even when it fails. | A failed fallback cannot trigger coordinate or strategy replay. | Low | Dedicated failed-selector-fallback regression passes. |
| Native attempt evidence | Native AX errors set `actionAttempted=true`; pre-call failures keep the default false. | Downstream recovery can distinguish attempted native operations. | Low | Source assertion and structured-failure cross-package test pass. |
| Compatibility and release | No command, schema version, configuration key, dependency, or package version changed. | Recovery becomes fail-closed while public schemas remain stable. | Low | Package boundaries, docs, wheels, preflight, and CI pass. |

## 5. Findings

### PRR-021 - `[S1][Resolved][Reliability/Safety]` WeChat replayed actions after dispatched or unknown outcomes

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:950-990,1355-1390,1450-1572,1706-1885,2991-3141,4133-4247` @ `d20636cd5edf3db4e9521a982fce976cbbb656ba`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The prior implementation selected coordinate, selector,
  Return, or strategy fallback from a generic failure kind and could ignore
  `requestDispatched=true`, `actionAttempted=true`, and `retryable=false`. The
  current implementation routes every affected action recovery through one
  fail-closed predicate and treats an issued fallback as final.
- **Trigger:** A warm action worker receives `AXPress` or `AXSetFocus`, but its
  response is lost, malformed, times out, or reports a native API error after
  invocation.
- **Impact:** Before remediation, one semantic operation could mutate the
  desktop twice and use stale coordinates after the first unknown outcome. The
  current paths execute zero additional mutations in every unsafe case.
- **Evidence:**
  - `tool.py:4133-4247` centralizes positive-attempt and dispatch evidence,
    gives `true` precedence over contradictory `false`, requires explicit
    `requestDispatched=false` plus `retryable=true`, and preserves explicit
    unsupported fallback;
  - `tool.py:950-990,1355-1390,1450-1572,1706-1885,2991-3141` applies the same
    decision to mapped navigation, visible contacts, search focus, search
    results, coordinates, selector fallback, and strategy continuation;
  - `client.py:4059-4079,4373-4385` reports `actionAttempted=true` when the
    native AX API was invoked and returned an error;
  - `test_tool.py:1876,2727-2866,2939-3029,3368-3428` covers mapped navigation,
    all cross-package transport outcomes, both visible-contact paths, search
    result and search focus, safe fallback, and failed-fallback finality;
  - the four unsafe cross-package outcomes passed ten consecutive iterations,
    for 40 dispatch/outcome executions with one recorded action and no second
    mutation;
  - exact-head GitHub Actions run 29358425055, job 87171908549, passed every
    configured test, package, preflight, wheel, sdist, and content check.
- **Required change:** Completed. Preserve the no-replay boundary throughout
  WeChat and report native action attempts accurately.
- **Verification:** Completed. EOF, timeout, malformed response, native failure,
  pre-dispatch, unsupported, path-specific, package/root, wheel, preflight, and
  exact-head CI gates pass.

No blocking findings were identified for the reviewed snapshot.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-017` | Resolved | Privacy, identity, selector, packaging, workflow, pagination, proof, and performance gates remain green. |
| `PRR-018` | Resolved | Readiness, fd-level framing, response stress, cleanup, and internal no-replay gates remain green. |
| `PRR-019` | Resolved | Bounded queue/startup deadline, zero-write expiration, and worker preservation remain green. |
| `PRR-020` | Resolved | Direct action timeout recovery remains dispatch-aware and fail-closed. |
| `PRR-021` | Resolved | Downstream fallback is dispatch/attempt-aware, native attempt evidence is correct, and cross-package no-replay tests pass. |

## 6. Required Actions Before Merge

None under this Review Contract.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish bounded semantic evidence only. / feature maintainer |
| data-integrity | Low | A dispatched action can still have an unknown desktop outcome. | Return non-retryable failure and execute zero downstream mutations. / both package owners |
| reliability-concurrency | Low | Worker EOF, timeout, or malformed responses remain possible. | Preserve dispatch evidence and central fail-closed recovery. / both package owners |
| performance-scalability | Low | One worker serializes Accessibility actions. | Keep the bounded deadline and existing timing diagnostics. / computer-use-macos |
| api-compatibility | Low | Unsafe generic fallback is now rejected. | Preserve schemas and explicitly allow proven pre-dispatch and unsupported fallbacks. / wechat-desktop-tool |
| deployment-rollback | Low | Recovery semantics changed across normal WeChat action paths. | Revert `b8d4bbd` if necessary; no data migration or state conversion exists. / feature maintainer |
| maintainability | Low | Recovery evidence exists in direct and nested protocol locations. | Keep one extraction/policy helper and cross-package contract tests. / wechat-desktop-tool |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root repository unittest discovery | clean isolated `b8d4bbd` implementation clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | 127 tests passed in 43.043 s, including wheel and release integration checks. |
| Protocol package | same isolated clone | PASS | 0 | 55 tests passed in 0.014 s. |
| macOS package with `ResourceWarning` as error | same isolated clone | PASS | 0 | 141 tests passed in 1.531 s; one sandbox skip. |
| WeChat package with `ResourceWarning` as error | same isolated clone | PASS | 0 | 132 tests passed in 0.812 s. |
| Cross-package unsafe-outcome test, ten iterations | same isolated clone | PASS | 0 | 10/10 passed; each iteration covers EOF, timeout, malformed response, and native failure. |
| Compile | same isolated clone with external pycache | PASS | 0 | All package, example, script, and test Python sources compiled. |
| Release preflight | same isolated clone | PASS | 0 | Mandatory gates passed; only expected socket and seven external-proof warnings remained. |
| Wheel build/install/API smoke | same isolated clone; `/opt/anaconda3/bin/python` | PASS | 0 | Three 0.2.0 wheels built and installed; incompatible local 0.1.1 dependency set was rejected. |
| Exact review-head delta and whitespace | local git at `d20636c` | PASS | 0 | `b8d4bbd...d20636c` changes only F5 verification docs; `git diff --check origin/main...HEAD` passed. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| CI / test - run 29358425055, job 87171908549 | 2026-07-14T18:37:47Z | PASS | Exact head `d20636c`; unit tests, preflight, all package tests, wheels, sdist, and distribution-content checks passed. |

### Checks not run

- **Fresh real WeChat action or send:** deterministic synthetic workers cover
  the recovery boundary without risking a desktop mutation; prior authorized
  live feature evidence remains historical context.
- **Post-submit delivery read-back:** outside this recovery review.
- **Signed helper and real release publication:** later F7 external gates.
- **Ruff and mypy:** neither module is installed in the workspace environment,
  and neither is a configured CI gate.

Overall validation status is `PARTIAL` only because live desktop and external
release proof were deliberately excluded. All deterministic checks required to
resolve `PRR-021`, including exact-head CI, passed.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `d20636cd5edf3db4e9521a982fce976cbbb656ba`; any later code or behavior change
  requires re-review.
- The complete feature diff is covered through the prior stable finding ledger,
  focused three-commit delta review, and current root/package/CI gates.
- Local implementation tests ran at `b8d4bbd`; `d20636c` adds only the F5
  verification record, and exact-head CI reran all configured checks.
- No fresh real desktop mutation, signed helper, or publication was performed.
- Private raw observations and unrelated dirty worktree files were excluded.
- The GitHub PR remains draft and its body still describes the obsolete
  `07fa052` request-changes result.

## 10. Open Questions and Assumptions

### Open questions

None that block merge.

### Assumptions

1. `unsupported_operation` and `unsupported_accessibility_action` mean the
   requested native action was not performed unless positive attempt evidence
   contradicts that result.
2. Once a mutating request is dispatched or attempted, missing response data
   leaves its desktop outcome unknown and prohibits another mutation.
3. A result is safe for automatic fallback only when the implementation can
   prove zero dispatch and advertises retryability, or explicitly reports an
   unsupported action without a positive attempt.
4. The unavailable Ruff/mypy checks are not merge gates because exact-head CI
   does not configure them.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** Remove the unreferenced legacy private focus
  implementation in a separate cleanup.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable documented gate.
- **NOTE-014 [performance]** Collect repeated live percentiles if the
  three-second target becomes an operational SLO.
- **NOTE-015 [documentation]** Synchronize the GitHub PR body, tracked PR
  description, and merge-readiness record before changing draft state.
- **NOTE-016 [documentation]** Expand the final release note to name the warm
  action worker and dispatch-aware downstream recovery behavior.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-d20636c.json`](./pr-review-macos-computer-use-3-d20636c.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: d20636cd5edf3db4e9521a982fce976cbbb656ba
blocking_findings: []
resolved_findings:
  - PRR-021
validation_status: PARTIAL
report_status: CURRENT
```
