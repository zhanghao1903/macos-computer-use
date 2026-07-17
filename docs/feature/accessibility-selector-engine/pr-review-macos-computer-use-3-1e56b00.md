# PR Review - `zhanghao1903/macos-computer-use#3` @ `1e56b00`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `zhanghao1903/macos-computer-use` |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `1e56b0086b2d996124d5c60db5723eb98ac29ec0` |
| Reviewed at | `2026-07-15T17:14:39Z` |
| Reviewer | `Codex (GPT-5)` |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| GitHub state | `OPEN`, `DRAFT`, mechanically mergeable, merge state `clean` |
| Scope size | 135 commits; 119 changed files; 44,379 additions; 1,533 deletions |
| Previous review | `pr-review-macos-computer-use-3-d85703a.md` @ `d85703a`, `APPROVE` |
| Previous result integrity | `pr-review-macos-computer-use-3-d85703a.json`, SHA-256 `1ac89491d9f0f0b45adc0a3e3c2908cf76556cb77c51fa569d35d0fca92056db` |
| Supersedes | The `d85703a` decision and its published F6 approval state |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable under this Review Contract:** `false`
- **Blocking findings:** `3` (`PRR-021`, `PRR-022`, `PRR-026`)
- **Resolved finding revalidated:** `PRR-025`
- **Approval renewal:** `WITHHELD`
- **Rationale:** The package failure registry is fixed, but production-shaped
  native unsupported results cannot use the documented safe fallback. In the
  opposite direction, request-mismatched or malformed attempt/dispatch
  evidence can still authorize a second mutation.

The PR was not merged, changed from draft, approved, or published as a GitHub
review.

## 3. Executive Summary

The two commits after the previous review publish its approval in synchronized
F6 documents, and exact-head CI is green. Revalidating that decision against
the complete producer-to-consumer action path found that the tests prove a
synthetic result shape rather than the generated production shape.

The native failure producer omits `action`, while the new strict WeChat gate
requires it; both legitimate native unsupported cases therefore fail instead
of using one configured fallback. The gate also trusts a response-internal
action/code pair without comparing it with the requested action. Older attempt
and dispatch collectors silently ignore malformed present values. Controlled
current-head probes show the latter two gaps executing
`accessibility_action` followed by `click`.

The author must repair the end-to-end action proof, make all attempt/dispatch
parsing presence-sensitive, add production-shaped and adversarial tests, then
refresh F5/F6 evidence and request another review.

## 4. Scope and Change Map

### Reviewed scope

- exact `d85703a...1e56b00` two-commit delta and both changed F6 documents;
- prior `PRR-025` and `PRR-026` closure evidence at the current head;
- the six-commit `3f792e4...1e56b00` remediation history and its affected
  producer, normalizer, consumer, callers, tests, and stable documentation;
- current base-to-head effective diff reconciled through the prior finding
  ledger plus the current affected-path audit;
- malformed, duplicate, contradictory, request-mismatched,
  production-shaped, timeout, and unsupported evidence;
- package/root tests, release preflight, compilation, whitespace, live PR
  metadata/body, and exact-head CI.

### Excluded or unavailable scope

- fresh real WeChat or macOS Accessibility mutation;
- signed/notarized helper execution and TestPyPI/PyPI publication;
- private raw desktop observations and unrelated primary-worktree changes;
- a strict-mypy cleanup baseline for the repository's 190 existing diagnostics.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Failure-kind routing | Register `accessibility_action_unsupported`. | Tuple consumers can classify the native failure. | Low | Producer/registry/docs/tests pass; `PRR-025` remains resolved. |
| Strict no-effect proof | Require consistent action, code, attempt, and effect evidence. | Intended fallback is narrower, but action proof is not bound end to end. | High | Production-shaped and request-mismatch probes fail. |
| Legacy fallback evidence | Preserve generic unsupported and pre-dispatch recovery. | Malformed present fields can be mistaken for safe absence/false. | High | Two probes execute a second click. |
| F6 publication | Publish the `d85703a` approval in tracked and live descriptions. | Live/tracked text agrees, but this review supersedes its decision. | Medium | REST metadata, exact body comparison, and CI inspected. |

### Re-review reconciliation

| Previous report | Previous base/head | Previous decision | Current base/head | Immediate delta | Old decision state |
|---|---|---|---|---|---|
| `pr-review-macos-computer-use-3-d85703a.json` | `fed6523` / `d85703a` | `APPROVE` | `fed6523` / `1e56b00` | `d85703a...1e56b00` | `SUPERSEDED` |

- **Delta commits reviewed:**
  `376401e8685c0f1c28705e8772f9f2e5b08c78ce`,
  `1e56b0086b2d996124d5c60db5723eb98ac29ec0`.
- **Delta files reviewed:** `merge-readiness.md`, `pr-description.md`.
- **Unclassified changes:** none.
- **Full base-to-head diff reconciled:** `true`.
- The live PR body and tracked `pr-description.md` were byte-identical at
  snapshot freeze. Both now describe the superseded approval and must be
  refreshed after remediation.

#### Finding closure ledger

| Finding | Previous state | Current state | Current-head evidence |
|---|---|---|---|
| `PRR-021` | resolved | **open** | Malformed attempted/dispatch evidence produces a second click. |
| `PRR-022` | resolved | **open** | Real native failure payload lacks `action`, so valid fallback is disabled. |
| `PRR-025` | resolved | resolved | Constant, tuple, normalization, docs, and executable membership tests agree. |
| `PRR-026` | resolved | **open** | Response action is internally checked but never compared with the request. |

#### Forward-risk surfaces

| Surface | Risk triggers | Discriminating checks | Result |
|---|---|---|---|
| Native producer to strict recovery consumer | public contract, trust boundary, mutation recovery, test adequacy | Exact production payload; request/response action comparison; operation count | `FAIL` - `PRR-022`, `PRR-026` |
| Legacy attempted/dispatch extraction | trust boundary, data integrity, mutation recovery | Malformed truthy/falsey values and duplicate aliases | `FAIL` - `PRR-021` |
| Public failure registry and F6 platform state | public contract, deployment compatibility | Tuple assertion, body comparison, exact-head CI | `PASS` - `PRR-025` |

#### Approval-renewal gate

- [x] Old decision invalidated.
- [x] Immediate delta and all changed files classified.
- [x] Prior findings revalidated at the current head.
- [x] Forward-risk review and independent passes completed.
- [x] Current-head automated validation and CI observed.
- [ ] No open blocker.
- **Independent pass:** `PASS` - separate read-only passes reproduced the
  producer/consumer mismatch, request mismatch, and malformed-evidence replay.
- **Renewal result:** `WITHHELD`.

## 5. Findings

### PRR-021 - `[S1][Blocking][Reliability/Safety]` Malformed attempt or dispatch evidence can still replay an action

- **Location:**
  `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4137-4370`
  and `packages/computer-use-macos/src/computer_use_macos/client.py:125-139`
  @ `1e56b0086b2d996124d5c60db5723eb98ac29ec0`.
- **Confidence:** High.
- **Status:** open; historical finding reopened.
- **Origin:** `PREVIOUSLY_MISSED`.
- **Observation:** `_accessibility_action_attempted()` and
  `_accessibility_action_request_dispatched()` collect only valid booleans and
  silently discard malformed present copies. `ComputerUseClient` also applies
  `bool(...)` to untrusted attempted evidence, turning a falsey malformed value
  into trusted `false`.
- **Trigger:** A compatible, version-skewed, or malformed backend reports
  `unsupported_operation` with non-boolean `actionAttempted`, or a retryable
  result carries `requestDispatched=false` plus a malformed duplicate.
- **Impact:** The shared recovery gate can issue a selector, coordinate,
  Return, focus, or strategy mutation after the first action's effect remains
  unknown.
- **Evidence:**
  - `unsupported_operation` plus `actionAttempted="true"` produced
    `['accessibility_action', 'click']` and success;
  - a retryable timeout with one `requestDispatched=false` and one malformed
    `"true"` duplicate produced the same sequence;
  - the combined invariant probe exited `21` because both cases violated the
    required one-operation boundary.
- **Required change:** Make attempt/dispatch parsing presence-sensitive. Any
  malformed container, value, alias, or inconsistent duplicate must invalidate
  recovery; do not use boolean coercion for untrusted safety evidence.
- **Verification:** Test truthy and falsey malformed attempted values,
  malformed dispatch duplicates, missing evidence, and conflicts across every
  shared caller. Unsafe cases must execute only `accessibility_action`; valid
  pre-dispatch and explicit unsupported cases retain one fallback.

### PRR-022 - `[S2][Blocking][Compatibility]` Strict proof rejects real native unsupported results because the producer omits action

- **Location:**
  `packages/computer-use-macos/src/computer_use_macos/client.py:4077-4103,4411-4419`
  and
  `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4212-4244`
  @ `1e56b0086b2d996124d5c60db5723eb98ac29ec0`.
- **Confidence:** High.
- **Status:** open; historical finding reopened by the strict-proof regression.
- **Origin:** `PREVIOUSLY_MISSED`.
- **Observation:** The generated native `fail()` helper has no `action`
  parameter and does not emit the field for `AXPress/-25206` or
  `AXSetFocus/-25205`. The consumer now requires `action`. Current tests
  manually inject a production-absent field.
- **Trigger:** The real direct backend returns either documented definite
  unsupported result and a WeChat semantic path evaluates its configured
  fallback.
- **Impact:** Mapped navigation, contact opening, search focus/result
  selection, node clicking, and `execute_action` fail instead of using the one
  compatibility fallback promised by the API and design.
- **Evidence:**
  - exact production-shaped payloads passed through real
    `ComputerUseClient` normalization retained no top-level or nested action;
  - both valid native pairs returned `fallback_allowed=false`; the invariant
    probe exited `29`;
  - `test_package.py:2261-2344` and `test_tool.py:1047-1095` synthesize
    `action`, explaining why 143 computer-use and 138 WeChat tests stay green.
- **Required change:** Define one end-to-end action proof contract. The native
  result must carry the actual requested action, or an equivalently trustworthy
  normalization path must bind the expected action before recovery evaluation.
- **Verification:** Exercise the real generated failure path through
  `ComputerUseClient` and WeChat. Matching `AXPress/-25206` and
  `AXSetFocus/-25205` each use exactly one configured fallback; uncertain
  results use none.

### PRR-026 - `[S2][Blocking][Reliability/Safety]` Proof action is not compared with the action actually requested

- **Location:**
  `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4212-4244`
  @ `1e56b0086b2d996124d5c60db5723eb98ac29ec0`.
- **Confidence:** High.
- **Status:** open; previous closure rejected by current-head counterevidence.
- **Origin:** `PREVIOUSLY_MISSED`.
- **Observation:** The predicate accepts an internally valid response
  `action`/native-code pair but receives no expected action and never compares
  it with the command input.
- **Trigger:** A custom, stale, version-skewed, or malformed backend returns a
  complete `AXSetFocus/-25205` proof for an `AXPress` request, or the inverse.
- **Impact:** A fallback can execute after the actual requested action has an
  unknown effect, creating a second desktop mutation.
- **Evidence:** An `AXPress` request plus internally consistent
  `AXSetFocus/-25205` evidence made `proof_accepted=true`, then executed
  `['accessibility_action', 'click']` and returned success. The invariant probe
  exited `27`. The existing wrong-pair test changes fields inside one response
  and does not cover a response that is internally valid but mismatches the
  request.
- **Required change:** Bind the expected request action into the recovery
  decision and require every response action copy to equal it, without
  weakening the existing type, duplicate, effect, attempt, and code checks.
- **Verification:** Matching results retain one fallback. Both mismatch
  directions and all missing, malformed, duplicate, or contradictory variants
  execute zero fallback across every caller.

### PRR-025 - `[S2][Resolved][API Contract]` New package failure was missing from the stable routing tuple

- **Location:**
  `packages/computer-use-macos/src/computer_use_macos/errors.py:52-96`
  @ `1e56b0086b2d996124d5c60db5723eb98ac29ec0`.
- **Confidence:** High.
- **Status:** resolved.
- **Observation:** `ACCESSIBILITY_ACTION_UNSUPPORTED` owns the emitted value
  and belongs to `COMPUTER_USE_FAILURE_KINDS`.
- **Trigger:** A tuple-based consumer routes either native unsupported result.
- **Impact:** The result is classified through the stable package contract.
- **Evidence:** Both normalized native observations assert membership; package,
  root, preflight, and exact-head CI checks pass.
- **Required change:** Completed.
- **Verification:** Current-head executable membership assertions pass.

## 6. Required Actions Before Merge

- [ ] `PRR-021` - reject every malformed or contradictory attempted/dispatch
  value without boolean coercion; add zero-replay caller coverage.
- [ ] `PRR-022` - align the real native producer, normalization, and strict
  consumer action contract; prove both valid production pairs use one fallback.
- [ ] `PRR-026` - bind proof action to request action; add both mismatch
  directions as zero-fallback regressions.
- [ ] After the fixes pass re-review, regenerate F5/F6 evidence and synchronize
  merge-readiness plus the live/tracked PR description before changing draft
  state.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security and privacy | Low | Bounded diagnostics can contain transient UI identity data. | Keep raw observations and private smoke output untracked. / maintainer |
| Data integrity | High | Malformed or request-mismatched evidence can authorize a second mutation. | Resolve `PRR-021` and `PRR-026`; preserve operation-count assertions. / WeChat owner |
| Reliability and concurrency | High | One shared gate affects all navigation, search, click, Return, and actionRef recovery. | Use one presence-sensitive, expected-action-bound policy. / both owners |
| API and compatibility | Medium | Real direct-backend results do not satisfy the consumer proof shape. | Resolve `PRR-022` with a real producer-to-consumer test. / both owners |
| Performance and scalability | Low | One warm worker serializes bounded actions. | Preserve deadlines and timing diagnostics. / computer-use owner |
| Deployment and rollback | Medium | F6 says approved while production behavior and safety probes disagree. | Fix, re-review, and refresh F6 before ready/merge. / maintainer |
| Maintainability | Medium | Synthetic fixtures have drifted from the generated producer. | Derive integration fixtures from the real producer contract. / both owners |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root unittest discovery with `ResourceWarning` as error | clean exact-head clone; Darwin arm64; CPython 3.12.7 | PASS | 0 | 127 tests in 51.924 s, including wheel/release integration. |
| Protocol package | same clone | PASS | 0 | 55 tests in 0.015 s. |
| Computer-use package | same clone | PASS | 0 | 143 tests in 1.581 s; one sandbox socket skip. |
| WeChat package | same clone | PASS | 0 | 138 tests in 1.258 s. |
| Release preflight | same clone | PASS | 0 | Mandatory gates passed; expected socket and seven external-proof warnings. |
| Compile all package/script/test/example sources | external pycache | PASS | 0 | Clone remained clean. |
| `git diff --check fed6523...1e56b00` | same clone | PASS | 0 | No whitespace/conflict error. |
| Request/response action-binding invariant | repository-native observation and tool | **FAIL** | 27 | Requested `AXPress`, reported valid `AXSetFocus`; action then click; success. |
| Malformed attempted/dispatch zero-replay invariant | repository-native observations and tool | **FAIL** | 21 | Both cases executed action then click; success. |
| Production-shaped native result contract | real client normalization plus WeChat gate | **FAIL** | 29 | Both valid native pairs lacked action and disabled fallback. |
| Ruff on changed Python files | same clone | ERROR | 2 | Ruff executable unavailable; not a configured CI gate. |
| Strict mypy across both source packages | no accepted repository baseline | FAIL | 1 | 190 diagnostics across 15 files; not treated as a new delta finding. |

### CI and platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| GitHub Actions `test` | `2026-07-15T16:07:20Z` | PASS | Exact head; [run 29430910094 / job 87405343993](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29430910094/job/87405343993). |
| GitHub PR state | `2026-07-15T17:10Z` | INFO | Open, draft, mechanically mergeable/clean; live body equals tracked description. |

Overall validation is `FAILED`: broad configured checks pass, but three
decision-critical invariants fail at the exact head.

### Checks not run

- Fresh real WeChat/macOS Accessibility mutation - it would alter the user's
  desktop, while deterministic generated-script, normalization, and policy
  probes establish the decision.
- Signed helper, TestPyPI, PyPI, and trusted-publisher proof - separate F7
  release gates, unnecessary to reproduce the blockers.

## 9. Coverage and Limitations

- This report is authoritative only for base
  `fed652343ec73734247955d44dc8e60293a7b373` and head
  `1e56b0086b2d996124d5c60db5723eb98ac29ec0`.
- The immediate delta is fully classified; the wider behavior audit used the
  complete prior finding ledger and current affected producer/caller graph.
- No live desktop mutation, signed helper, or publication was performed.
- Ruff is unavailable. Strict mypy has no accepted baseline and its 190
  diagnostics cannot be attributed solely to this delta.
- The primary worktree contains unrelated user changes. Tests ran in a clean
  isolated clone; only this report pair is new locally.
- Any base/head change invalidates this decision and requires re-review.

## 10. Open Questions and Assumptions

### Open questions

None that change the current request-changes decision.

### Assumptions

| Assumption | Decision-critical | Status | Evidence |
|---|---:|---|---|
| A definite unsupported result can authorize fallback only for the same requested action. | true | VERIFIED | Action-specific native constants, documented contract, and mismatch reproduction. |
| Present malformed attempt/dispatch evidence cannot be treated as safe absence. | true | VERIFIED | Fail-closed design plus three malformed-evidence reproductions. |
| Green broad tests cannot override a deterministic trigger outside their fixture coverage. | true | VERIFIED | Suites pass while production-shaped and adversarial invariants fail. |

## 11. Non-blocking Recommendations

- `NOTE-023` - derive cross-package result fixtures from the real generated
  action producer so tests cannot prove fields production does not emit.
- `NOTE-024` - parse recovery evidence into an explicit
  valid/invalid/absent object consumed by one expected-action-aware policy.
- `NOTE-016` - retain explicit dispatch-aware no-replay and narrow
  definite-unsupported wording in the final release note.

## 12. Machine-readable Summary

- Result file:
  [`pr-review-macos-computer-use-3-1e56b00.json`](./pr-review-macos-computer-use-3-1e56b00.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`
- Schema validation: `VALID` with the repository validator.

```yaml
schema_version: "1.1"
review_kind: RE_REVIEW
decision: REQUEST_CHANGES
mergeable: false
head_sha: 1e56b0086b2d996124d5c60db5723eb98ac29ec0
blocking_findings:
  - PRR-021
  - PRR-022
  - PRR-026
resolved_findings:
  - PRR-025
validation_status: FAILED
report_status: CURRENT
```
