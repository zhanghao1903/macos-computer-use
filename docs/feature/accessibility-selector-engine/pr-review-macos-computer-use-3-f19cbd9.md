# PR Review - `zhanghao1903/macos-computer-use#3` @ `f19cbd9`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `zhanghao1903/macos-computer-use` |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `f19cbd9118c30ced9a3812d9829a3b7e6fbd3592` |
| Reviewed at | `2026-07-16T01:17:53Z` |
| Reviewer | `Codex (GPT-5)` |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| GitHub state | `OPEN`, `DRAFT`, mechanically mergeable, merge state `clean` |
| Scope size | 140 commits; 121 changed files; 46,144 additions; 1,564 deletions |
| Previous review | `pr-review-macos-computer-use-3-1e56b00.md` @ `1e56b00`, `REQUEST_CHANGES` |
| Previous result integrity | `pr-review-macos-computer-use-3-1e56b00.json`, SHA-256 `e5a26ab93c56e63a29b270ffbb2628789416503bda89c988a6c99e9d3c726218` |
| Supersedes | The `1e56b00` request-changes decision |
| Integrity correction | `2026-07-17`; machine result corrected without changing the historical decision or represented test outcomes |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable under this Review Contract:** `true`
- **Blocking findings:** none
- **Resolved findings:** `PRR-021`, `PRR-022`, `PRR-025`, `PRR-026`
- **Approval renewal:** `GRANTED`
- **Rationale:** The native producer now carries the requested action, the
  consumer binds every proof to the outbound action, and attempted/dispatch
  evidence is presence-sensitive and fail-closed. Production-generated valid
  pairs retain one fallback, while malformed, contradictory, mismatched, and
  unknown outcomes execute no second mutation. Exact-head focused local
  validation and GitHub CI pass; broader implementation checks are supporting
  evidence from `65f8855`.

This report does not publish a GitHub review, change draft state, or merge the
PR.

## 3. Executive Summary

The five-commit remediation delta records the request-changes review, amends
the end-to-end recovery contract and plan, implements both package changes, and
publishes exact-implementation verification.

`computer-use-macos` now emits `action` from the real generated native failure
path and no longer converts malformed `actionAttempted` values with
`bool(...)`. `wechat-desktop-tool` models attempted and dispatch evidence as
absent, valid true, valid false, or invalid. All fallback callers pass the
outbound expected action, and the strict native proof requires every response
action copy to equal it.

The tests execute the production warm-worker action script through the real
client and WeChat policy for both valid native pairs. Separate adversarial
cases cover both mismatch directions, malformed truthy and falsey attempt
values, malformed containers, conflicting dispatch aliases, transport loss,
timeouts, missing proof, and contradictory proof. Operation counts establish
that every unsafe result stops after `accessibility_action`.

No new blocker was found in the remediation delta or its affected producer,
normalizer, consumer, caller, test, documentation, packaging, or CI paths.

## 4. Scope And Change Map

### Reviewed scope

- exact `1e56b00..f19cbd9` remediation delta and all 12 changed paths;
- prior finding closure at the current head;
- producer to normalization to protocol observation to WeChat recovery flow;
- every shared fallback call site and expected-action source;
- malformed, missing, duplicated, contradictory, request-mismatched,
  pre-dispatch, unsupported, timeout, transport-loss, and valid native results;
- current base-to-head effective diff reconciled through the prior finding
  ledger and current affected-path audit;
- implementation-head package/root tests, stress, compilation, release
  preflight, wheel/install/API smoke, dependency rejection, clean-tree checks,
  plus exact-reviewed-head focused tests and CI.

### Excluded scope

- fresh real WeChat or macOS Accessibility mutation;
- signed/notarized helper execution and TestPyPI/PyPI publication;
- unrelated dirty primary-worktree files and private desktop observations;
- repository-wide strict-mypy cleanup outside this remediation.

### Delta commits

- `cdcbd47f1780fd1d08fb8c371a1db0e1f035e4cc` - record the latest review;
- `b4026eef0b91944e51eebea1a1e2326e7b8dfadb` - amend recovery proof design;
- `da4e011d760cb2121e9efa12f91408e1a30fd8c3` - add the remediation plan;
- `65f8855767971f864154c6173f134c6d03fea37b` - implement and test the fix;
- `f19cbd9118c30ced9a3812d9829a3b7e6fbd3592` - publish F5 evidence.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Native action producer | Post-call failures include the validated requested action. | Real unsupported results satisfy the documented proof shape. | Medium | Production worker tests cover both native pairs. |
| Client normalization | Promote attempted evidence only when it is Boolean. | Malformed values remain raw and cannot become trusted false/true. | High | Truthy and falsey malformed normalization tests pass. |
| WeChat recovery | Parse four-state Boolean evidence and require expected-action equality. | Unsafe outcomes stop; matching definite no-effect results retain one fallback. | High | 350 unsafe stress subcases and 20 valid pair executions pass. |
| Documentation and proof | Design, plan, stable docs, implementation notes, and F5 evidence agree. | Integrators receive one consistent recovery contract. | Low | Release preflight and diff audit pass. |

### Finding closure ledger

| Finding | Previous status | Current status | Current-head evidence |
|---|---|---|---|
| `PRR-021` | open | **resolved** | Four-state parsing rejects malformed/contradictory attempt and dispatch evidence; zero fallback assertions pass. |
| `PRR-022` | open | **resolved** | The real generated native failure carries action through client normalization and both valid pairs use one fallback. |
| `PRR-025` | resolved | **resolved** | The stable failure constant and routing tuple remain unchanged and covered. |
| `PRR-026` | open | **resolved** | Every recovery call supplies expected action; both mismatch directions stop after one action. |

### Forward-risk review

| Surface | Risk triggers | Checks | Result |
|---|---|---|---|
| Generated producer and public observation | public contract, deployment compatibility | Real generated worker payload, client normalization, wheel/API smoke | `PASS` |
| Boolean evidence parser | trust boundary, data integrity, mutation recovery | Missing/type/container/alias/duplicate/conflict cases | `PASS` |
| Expected-action propagation | mutation recovery, test adequacy | All call sites audited; both mismatch directions and valid pairs tested | `PASS` |
| Contract and evidence publication | public contract, data integrity, deployment compatibility | Stable docs, prior report/hash, verification claims, and all eight documentation paths reconciled | `PASS` |
| Test harness and temporary framework stubs | test adequacy, packaging | Temp-only modules, wheel-content checks, clean clone | `PASS` |

All delta files were classified. No unclassified change remains. The full PR
diff is reconciled through the prior reports plus this delta review.

## 5. Findings

### PRR-021 - `[S1][Resolved][Reliability/Safety]` Malformed attempt or dispatch evidence could replay an action

- **Status:** resolved.
- **Resolution:** `_BooleanEvidence` preserves presence and validity;
  attempted and dispatch collectors reject malformed containers, non-Boolean
  values, and conflicting aliases before the shared recovery predicate permits
  a fallback. Client normalization no longer uses truthiness coercion.
- **Verification:** truthy/falsey strings, conflicts, malformed containers,
  malformed dispatch duplicates, transport loss, and every shared caller stop
  after one `accessibility_action`.

### PRR-022 - `[S2][Resolved][Compatibility]` The real native producer omitted action

- **Status:** resolved.
- **Resolution:** generated post-call failures receive `action=action`; the raw
  result is preserved through `ComputerUseClient` and protocol conversion.
- **Verification:** production `_accessibility_action_worker_script()` tests
  prove `AXPress/-25206` and `AXSetFocus/-25205` each use exactly one matching
  configured fallback.

### PRR-026 - `[S2][Resolved][Reliability/Safety]` Proof action was not compared with the request

- **Status:** resolved.
- **Resolution:** every recovery predicate requires `expected_action`, derived
  from the exact outbound action input, and strict proof requires equality.
- **Verification:** both internally valid mismatch directions execute only the
  original action; matching directions retain one fallback.

### PRR-025 - `[S2][Resolved][API Contract]` Stable failure registry propagation

- **Status:** remains resolved.
- **Resolution:** `ACCESSIBILITY_ACTION_UNSUPPORTED` remains in
  `COMPUTER_USE_FAILURE_KINDS`; this remediation did not regress routing.
- **Verification:** computer-use package, root, preflight, and wheel checks pass
  at implementation head `65f8855`; focused tests and CI pass at reviewed head
  `f19cbd9`.

## 6. Required Actions Before Merge

- [x] `PRR-021` - reject malformed or contradictory attempted/dispatch evidence
  without coercion and prove zero replay.
- [x] `PRR-022` - align the generated producer, client normalization, and strict
  consumer contract for both native pairs.
- [x] `PRR-026` - bind proof action to request action and cover both mismatch
  directions.
- [x] Refresh exact implementation verification and exact-head CI.

No finding-driven code action remains. F6 merge-readiness and tracked/live PR
description synchronization are lifecycle publication steps, not blockers in
the reviewed implementation snapshot.

## 7. Risk Assessment

| Category | Residual level | Assessment | Mitigation / owner |
|---|---|---|---|
| Reliability and mutation safety | Low | Recovery is fail-closed for malformed, unknown, or mismatched evidence. | Keep operation-count regressions in CI. / both package owners |
| API compatibility | Low | The additive action field matches the requested action and existing schema version. | Preserve raw payload plus typed normalization. / computer-use owner |
| Test portability | Low | Production action code runs against temp stubs without requiring a live desktop. | Keep stubs test-only and wheel-content checks enabled. / test owner |
| External desktop behavior | Medium | No fresh live mutation was run for this remediation. | Existing live smoke remains an F7 proof; deterministic tests cover the changed classification. / release owner |

## 8. Validation Evidence

### Exact-reviewed-head checks

| Check | Environment | Result |
|---|---|---|
| Decision-focused exact-head pass | clean no-hardlink clone @ `f19cbd9` | 6 named tests passed |

### Supporting implementation-head checks

The following checks ran at implementation head `65f8855`. They remain useful
supporting evidence because `f19cbd9` changes only `verification.md`, but they
are not represented as exact-head `reviewer_runs` in the machine result.

| Check | Environment | Result |
|---|---|---|
| Root unittest discovery with `ResourceWarning` as error | clean no-hardlink clone @ `65f8855` | 127 passed in 42.752 s |
| Protocol package | same clone | 55 passed |
| Computer-use package | same clone | 144 passed, 1 skipped |
| WeChat package | same clone | 140 passed |
| Adversarial stress | implementation clone, ten iterations | 350 unsafe subcases, zero second mutation; 20 valid pair fallbacks |
| Compile | external pycache | passed |
| Release preflight | clean clone | passed with expected socket/external-proof warnings |
| Wheel build/install/API smoke/dependency rejection | clean clone, Anaconda build driver | passed for all three 0.2.0 wheels |
| Diff and clean tree | base `fed6523`, exact clones | passed |

### CI and platform checks

| Check | Head | Status | Evidence |
|---|---|---|---|
| GitHub Actions `test` | `f19cbd9` | `PASS` | [run 29463591047 / job 87511953080](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29463591047/job/87511953080) |
| GitHub PR state | `f19cbd9` | `PASS` | Open draft; mechanically mergeable; merge state clean. |

Overall validation is `PASSED`.

### Checks not run

- Fresh real WeChat/macOS Accessibility mutation: unnecessary for this
  deterministic classification fix and would modify the user's desktop.
- Signed helper, TestPyPI, PyPI, and trusted-publisher proof: separate F7
  release gates.
- Ruff and strict mypy: Ruff is unavailable; strict mypy has no accepted clean
  repository baseline and is not a configured CI gate.

## 9. Coverage And Limitations

- This decision is authoritative only for base `fed6523` and head `f19cbd9`.
- The large base-to-head diff is reconciled through the complete prior review
  ledger and this fully classified two-dot remediation delta.
- The `2026-07-17` integrity correction restores preserved finding
  fingerprints, classifies all changed paths, and removes stale-head runs from
  the machine `reviewer_runs` list. It does not assert that the supporting
  `65f8855` checks ran at `f19cbd9`.
- Independent agents were unavailable. A separate second-pass source/caller
  audit and a clean-clone exact-head test pass were used instead.
- No live desktop mutation, signed helper, or package publication occurred.
- Any base/head change invalidates this decision and requires approval renewal.

## 10. Open Questions And Assumptions

No open question changes the decision.

| Assumption | Decision-critical | Status | Evidence |
|---|---:|---|---|
| Fallback may occur only for the same requested action with definite no effect. | true | verified | Expected-action binding and bidirectional mismatch tests. |
| Present malformed attempt/dispatch evidence must never be treated as absence. | true | verified | Four-state parser and adversarial operation-count tests. |
| Temporary fake framework modules exercise production generation without entering packages. | true | verified | Actual worker script path, temp directories, wheel contents, and clean tree. |

## 11. Non-Blocking Recommendations

- `NOTE-023` - keep production-derived fixtures for future generated action
  result fields so synthetic tests cannot drift from emitted payloads.
- `NOTE-016` - retain explicit dispatch-aware no-replay and narrow
  definite-no-effect wording in final release notes.

## 12. Machine-Readable Summary

The companion file
`pr-review-macos-computer-use-3-f19cbd9.json` is the authoritative structured
result and validates against `pr-review-result.schema.json` version `1.1`.
Its corrected SHA-256 is
`01ed707a583c533e50c7a736d3dd235832211701db42552f3419d47c72b04653`.
