# PR Review - `zhanghao1903/macos-computer-use#3` @ `3f792e4`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `3f792e4a2537a9aecbc68f236606f367da6797d2` |
| Reviewed at | 2026-07-15T14:38:08Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT`; supersedes the `d5204dd` report for merge evaluation |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 129 commits; 114 changed files; 42,422 additions; 1,500 deletions |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` under this Review Contract
- **Blocking findings:** 2 (`PRR-025`, `PRR-026`)
- **Resolved findings revalidated:** `PRR-022`, `PRR-023`, `PRR-024`
- **Rationale:** The direct native mapping, exact-head CI, F6 synchronization,
  and configured tests pass. However, the new package-owned failure kind is
  absent from the package's stable routing tuple, and WeChat can still execute
  a second mutation when an unsupported result carries contradictory native
  error or malformed duplicate evidence.

The PR was not merged and no GitHub review was published.

## 3. Executive Summary

The latest remediation correctly separates definite unsupported native
results (`-25206`/`-25205`, `actionEffect=none`) from uncertain outcomes such
as `-25204`, and it synchronizes the tracked and GitHub F6 descriptions. Root,
package, stress, preflight, and exact-head CI checks are green.

Two public-boundary gaps remain. `computer-use-macos` emits
`accessibility_action_unsupported` without declaring it in
`COMPUTER_USE_FAILURE_KINDS`, so callers using the advertised stable routing
contract see a legitimate package failure as unknown. Separately, the WeChat
predicate trusts any collected string `actionEffect=none` and ignores
contradictory `nativeErrorCode` or malformed duplicate values; a controlled
`-25204` counterexample therefore issued a click after the failed action.

## 4. Scope and Change Map

### Reviewed scope

- current PR body, draft/merge state, base/head SHAs, full commit/file delta,
  and exact-head GitHub CI;
- focused `d2dadd0...3f792e4` delta: six commits, fourteen files, 2,360
  additions, and 334 deletions;
- `3fd41ce` native AX error mapping, action-effect metadata propagation,
  WeChat recovery predicate, and every mutating fallback caller;
- public failure constants/tuple, package exports, contract tests, stable API
  docs, implementation notes, F5 verification, merge-readiness, tracked PR
  description, GitHub body, and release record;
- `-25206`, `-25205`, `-25204`, EOF, timeout, malformed, contradictory,
  missing, pre-dispatch, legacy unsupported, and version-skewed result shapes;
- isolated exact-head root/package tests, targeted cross-package tests, stress,
  compilation, release preflight, whitespace, clean-tree checks, and CI.

### Excluded or unavailable scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty primary-worktree files;
- Ruff and mypy, which are unavailable and are not configured CI gates.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Native result semantics | Results add `actionEffect` and native failures add `nativeErrorCode`. | Direct callers can distinguish performed, definite no-effect, and unknown effect. | Low | Native/package and cross-package regressions pass. |
| WeChat recovery | One attempted/dispatched exception accepts the new unsupported kind with collected `none` effects. | Valid `-25206`/`-25205` results receive one fallback; uncertain normal results stop. | Medium | Valid and standard unsafe tests pass; malformed contradiction counterexample fails closedness. |
| Failure routing contract | A new package-owned failure kind is emitted but not registered. | Tuple-based consumers cannot classify the new failure. | Medium | Real client observation reports `declared=false`. |
| F6 lifecycle | Approval links, tracked descriptions, GitHub body, and CI are synchronized. | Maintainers can discover the prior approval and current exact-head state. | Low | Tracked/platform bodies match; exact-head CI passes. |
| Packaging/release | No version or dependency change; observation fields are additive. | Existing packages remain install-compatible. | Low | Root wheel checks, preflight, and CI pass. |

## 5. Findings

### PRR-025 - `[S2][Blocking][API Contract]` New package failure is missing from the stable routing tuple

- **Location:** `packages/computer-use-macos/src/computer_use_macos/errors.py:51-95` @ `3f792e4a2537a9aecbc68f236606f367da6797d2`
- **Confidence:** High
- **Status:** open
- **Observation:** `client.py:4401-4424` now emits the package-owned
  `failureKind="accessibility_action_unsupported"`, but `errors.py` declares
  only `UNSUPPORTED_ACCESSIBILITY_ACTION` and
  `ACCESSIBILITY_ACTION_FAILED`; the new value is absent from
  `COMPUTER_USE_FAILURE_KINDS`.
- **Trigger:** A direct `accessibility_action` receives native `-25206` or
  `-25205`, and the application routes the returned failure through the public
  `COMPUTER_USE_FAILURE_KINDS` tuple.
- **Impact:** The exact compatibility path fixed by this delta is exposed as an
  unknown or non-package failure to applications following the documented
  stable routing contract. Callers may take a generic recovery path or reject
  a legitimate package result.
- **Evidence:**
  - a real `ComputerUseClient` fixture returned
    `{"failureKind":"accessibility_action_unsupported","declared":false}`;
  - `packages/computer-use-macos/README.md:163-166`, `docs/api.md:778-791`, and
    the `errors.py` module contract identify the tuple as stable package-owned
    failure routing;
  - `test_failure_kinds_are_declared_as_public_contract` intends to enforce
    exhaustiveness, but its regex scans `failure_kind="..."` and misses the
    generated action script's `fail("accessibility_action_unsupported", ...)`;
  - an explicit registry assertion failed with exit code 1 while every
    configured package test passed.
- **Required change:** Declare the new stable failure constant and add its
  value to `COMPUTER_USE_FAILURE_KINDS`. Extend the contract test with real
  `-25206` and `-25205` observations so every emitted package-owned failure is
  proven to belong to the public tuple.
- **Verification:** Both native unsupported observations must satisfy
  `observation.failure_kind in COMPUTER_USE_FAILURE_KINDS`; package/root,
  preflight, wheel/API smoke, and exact-head CI must pass.

### PRR-026 - `[S2][Blocking][Reliability/Safety]` Contradictory unsupported evidence can still trigger a second mutation

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4133-4235` @ `3f792e4a2537a9aecbc68f236606f367da6797d2`
- **Confidence:** High
- **Status:** open
- **Observation:** The recovery exception checks only that the top-level
  failure kind is `accessibility_action_unsupported` and that every collected
  non-empty string effect equals `none`. It does not reject a contradictory
  `nativeErrorCode`, missing/contradictory action evidence, or present
  non-string/empty duplicate effect values; malformed values are ignored.
- **Trigger:** A compatible but version-skewed or partially malformed backend
  returns the new failure kind and one `actionEffect=none`, while another
  public field reports `nativeErrorCode=-25204`, omits the required diagnostic,
  or carries an invalid duplicate effect.
- **Impact:** WeChat can execute a coordinate, selector, or Return fallback
  after an outcome whose native evidence is unknown. The controlled `-25204`
  reproduction produced operations `["accessibility_action", "click"]` and
  success, violating the no-replay safety boundary.
- **Evidence:**
  - a repository-native `ToolObservation` with the new failure kind,
    consistent string effects of `none`, and `nativeErrorCode=-25204` made the
    predicate return `true`; `_click_node_phase` then executed the click;
  - replacing one nested effect with an object also returned `true` because
    the invalid duplicate was ignored;
  - the inverse assertion that the `-25204` contradiction fail closed exited
    1;
  - current tests cover string `unknown` and wholly missing effects, but not
    malformed duplicates or failure/effect/native-code consistency;
  - the supported direct backend currently emits consistent values, which
    limits but does not remove the version-skew/custom-backend trigger.
- **Required change:** Validate the unsupported/no-effect proof at the trust
  boundary and fail closed on every present malformed or contradictory value.
  Define and enforce the complete safe contract (including action/native-code
  consistency when those fields are part of the proof) without weakening
  `-25204`, EOF, timeout, malformed, missing, or legacy attempted no-replay.
- **Verification:** Add end-to-end counterexamples for `-25204` paired with
  unsupported/none, wrong action-code pairing, missing required proof, and
  non-string/empty/contradictory duplicates; each must execute zero fallback.
  Valid `AXPress/-25206` and `AXSetFocus/-25205` must still execute exactly one.

### PRR-022 - `[S2][Resolved][Correctness/Compatibility]` Definite unsupported native actions were treated as unknown mutations

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:4073-4435` and `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4133-4235` @ `3f792e4a2537a9aecbc68f236606f367da6797d2`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The direct backend now emits `none` only for
  `AXPress/-25206` and `AXSetFocus/-25205`; other native errors emit `unknown`.
- **Trigger:** Native Accessibility returns one of the supported or uncertain
  error codes.
- **Impact:** Valid definite no-effect results retain one fallback while normal
  unknown results do not replay.
- **Evidence:** Package and cross-package tests cover both definite unsupported
  cases and seven unsafe modes; ten stress iterations produced 70 zero-replay
  unsafe outcomes.
- **Required change:** Completed for the supported production path; preserve it
  while resolving `PRR-026`.
- **Verification:** Completed for well-formed direct-backend results.

### PRR-023 - `[S2][Resolved][Documentation/Lifecycle]` F6 records published obsolete review state

- **Location:** `docs/feature/accessibility-selector-engine/merge-readiness.md`, `docs/feature/accessibility-selector-engine/pr-description.md`, and GitHub PR #3 @ `3f792e4a2537a9aecbc68f236606f367da6797d2`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The tracked F6 records and GitHub body now agree on the
  implementation/evidence head, replacement review, finding ledger, and
  approval state.
- **Trigger:** A maintainer evaluates draft readiness or merge state.
- **Impact:** The previous contradictory F6 decision is no longer presented as
  current.
- **Evidence:** GitHub body equals tracked `pr-description.md`; current head is
  open/draft/mergeable/clean and exact-head CI passed.
- **Required change:** Completed for this snapshot.
- **Verification:** Platform and tracked surfaces were compared directly.

### PRR-024 - `[S3][Resolved][API Contract]` Unsupported recovery documentation had contradictory precedence

- **Location:** `docs/api.md:251-270` and `docs/wechat-desktop-tool.md:460-477` @ `3f792e4a2537a9aecbc68f236606f367da6797d2`
- **Confidence:** High
- **Status:** resolved
- **Observation:** Both stable documents now describe the same definite
  no-effect exception and fail-closed handling for normal unknown evidence.
- **Trigger:** A developer implements or diagnoses action recovery.
- **Impact:** The prior prose ambiguity has been removed.
- **Evidence:** The two documents, implementation notes, and well-formed
  cross-package tests agree.
- **Required change:** Completed; extend the wording only if `PRR-026` refines
  which evidence is mandatory.
- **Verification:** Release preflight and manual contract comparison pass.

`PRR-001` through `PRR-024` otherwise remain resolved for this snapshot.

## 6. Required Actions Before Merge

- [ ] `PRR-025` - declare the new package failure kind in the stable public
  routing tuple and test real native unsupported observations against it.
- [ ] `PRR-026` - make the unsupported/no-effect exception reject every
  malformed or contradictory proof and add zero-replay counterexamples.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | Low | Desktop diagnostics can contain transient UI text. | Keep raw artifacts untracked and publish bounded semantic proof. / feature maintainer |
| Data integrity | Medium | A contradictory unsupported result can currently cause a second desktop mutation. | Resolve PRR-026 and preserve fail-closed evidence validation. / both package owners |
| Reliability & concurrency | Low | Worker EOF, timeout, and malformed response remain possible. | Existing normal-path no-replay tests and dispatch evidence remain in place. / both package owners |
| Performance & scalability | Low | One warm worker serializes AX actions. | Keep bounded deadlines and timing diagnostics. / computer-use-macos |
| API & compatibility | Medium | The new package failure is absent from the advertised stable routing tuple. | Resolve PRR-025 and test emitted observations against the registry. / computer-use-macos |
| Deployment & rollback | Low | Action recovery semantics changed across WeChat paths. | Revert `3fd41ce`; no persisted migration exists. / feature maintainer |
| Maintainability | Medium | Evidence is duplicated across public, metadata, and nested locations. | Validate one complete contract at the boundary and reject inconsistent duplicates. / wechat-desktop-tool |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root unittest discovery | clean isolated `3f792e4`; Darwin 25.5.0 arm64; CPython 3.12.7 | PASS | 0 | 127 tests passed in 47.677 s, including wheel and release integration checks. |
| Protocol package | same isolated clone | PASS | 0 | 55 tests passed in 0.033 s. |
| macOS package with `ResourceWarning` as error | same isolated clone | PASS | 0 | 142 tests passed in 1.631 s; one sandbox socket skip. |
| WeChat package with `ResourceWarning` as error | same isolated clone | PASS | 0 | 137 tests passed in 1.045 s. |
| Five cross-package recovery tests | same isolated clone | PASS | 0 | Valid native unsupported, pre-dispatch, pre-call unsupported, and unsafe outcomes passed in 0.636 s. |
| Seven unsafe modes repeated ten times | same isolated clone | PASS | 0 | 10/10 tests, 70 outcomes, zero fallback for currently covered malformed/unknown shapes. |
| Compile all Python sources | same isolated clone with external pycache | PASS | 0 | Package, example, script, and test sources compiled. |
| Release preflight | same isolated clone | PASS | 0 | Mandatory gates passed; one sandbox socket and seven external-proof warnings remained. |
| Diff/whitespace/clean tree | same isolated clone | PASS | 0 | `git diff --check` passed and the clone remained clean. |
| Stable failure registry assertion | same isolated clone | **FAIL** | 1 | `accessibility_action_unsupported` is not in `COMPUTER_USE_FAILURE_KINDS`. |
| Real client routing reproduction | same isolated clone | **FAIL** | 0 | Client output was `failureKind=accessibility_action_unsupported`, `declared=false`. |
| Contradictory native-code fail-closed assertion | same isolated clone | **FAIL** | 1 | `-25204` plus unsupported/none made the predicate allow fallback. |
| Malformed duplicate-effect reproduction | same isolated clone | **FAIL** | 0 | Nested object effect was ignored and the predicate returned true. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| CI / test - run 29420504340, job 87369436552 | 2026-07-15T14:38:08Z | PASS | Exact head `3f792e4`; configured tests, preflight, packages, wheels, sdist, and content checks passed. |

### Checks not run

- **Fresh real WeChat action or send:** deterministic result-shape
  counterexamples expose both blockers without risking a desktop mutation.
- **Post-submit delivery read-back:** outside this recovery review.
- **Signed helper and real release publication:** later F7 external gates.
- **Ruff and mypy:** unavailable and not configured CI gates.

Overall validation status is `FAILED`: the configured suite and CI pass, but
two review-specific public/safety contract assertions fail.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `3f792e4a2537a9aecbc68f236606f367da6797d2`; later changes require re-review.
- The complete feature diff was covered through the prior finding ledger,
  focused six-commit delta review, and current exact-head tests/CI.
- No fresh live desktop mutation, signed helper, or publication was performed.
- Controlled protocol observations reproduce `PRR-025` and `PRR-026` without
  requiring a real WeChat action.
- Private raw observations and unrelated dirty primary-worktree files were
  excluded.

## 10. Open Questions and Assumptions

### Open questions

1. Is `nativeErrorCode` mandatory safety evidence for
   `accessibility_action_unsupported`, or diagnostic-only? The final contract
   must still reject any present value that contradicts the claimed no-effect
   result.

### Assumptions

1. `COMPUTER_USE_FAILURE_KINDS` is intended to enumerate package-owned public
   failures, as stated by the module, package README, API docs, and contract
   test.
2. `WeChatDesktopTool` may receive a compatible but version-skewed/custom
   app-control observation and must fail closed on malformed or contradictory
   evidence.
3. The supported direct backend's current `-25206`, `-25205`, and `-25204`
   mapping is correct.
4. Current GitHub body synchronization and exact-head CI close the previous F6
   remaining gates without another docs-only commit loop.

## 11. Non-blocking Recommendations

- **NOTE-016 [documentation]** Keep the final Unreleased text explicit about
  warm action workers, dispatch-aware no-replay, and the definite unsupported
  exception.
- **NOTE-021 [design]** Backfill the feature design/field contract with
  `actionEffect`, `nativeErrorCode`, the new failure kind, precedence, and
  compatibility semantics; stable API docs already describe the runtime
  contract.
- **NOTE-022 [testing]** Extend the failure-kind contract scanner to include
  generated-script `fail("...")` literals or, preferably, validate failure
  kinds from executable observations.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-3f792e4.json`](./pr-review-macos-computer-use-3-3f792e4.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: REQUEST_CHANGES
mergeable: false
head_sha: 3f792e4a2537a9aecbc68f236606f367da6797d2
blocking_findings:
  - PRR-025
  - PRR-026
resolved_findings:
  - PRR-022
  - PRR-023
  - PRR-024
validation_status: FAILED
report_status: CURRENT
```
