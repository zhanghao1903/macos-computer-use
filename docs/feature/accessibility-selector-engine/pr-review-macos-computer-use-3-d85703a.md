# PR Review - `zhanghao1903/macos-computer-use#3` @ `d85703a`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `d85703a7d95f0dab4b1062678ad0cf4d7e6dd983` |
| Reviewed at | 2026-07-15T15:47:37Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT`; supersedes the `3f792e4` report for merge evaluation |
| Review mode | `READ_ONLY` |
| Scope size | 133 commits; 117 changed files; 43,803 additions; 1,533 deletions |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable:** `true` under this Review Contract
- **Blocking findings:** none
- **Resolved in this remediation:** `PRR-025`, `PRR-026`
- **Previously resolved and revalidated:** `PRR-022`, `PRR-023`, `PRR-024`
- **Rationale:** The emitted unsupported failure is now part of the stable
  package routing tuple, and WeChat accepts a second mutation only for a
  complete, type-correct, internally consistent native no-effect proof. Clean
  clone tests, 150 unsafe stress outcomes, package/release checks, and
  exact-head GitHub CI pass.

No GitHub review event was published and the PR was not merged.

## 3. Executive Summary

The remediation closes both blockers from the `3f792e4` review.
`computer-use-macos` declares `ACCESSIBILITY_ACTION_UNSUPPORTED`, includes it
in `COMPUTER_USE_FAILURE_KINDS`, and tests both native unsupported
observations against that public routing contract.

The WeChat recovery boundary now validates failure kind, action, attempted
state, effect, and native error code across public, metadata, alias, and nested
copies. Only `AXPress/-25206` and `AXSetFocus/-25205` with
`actionAttempted=true` and `actionEffect=none` permit one configured fallback.
Missing, malformed, empty, mismatched, or contradictory evidence fails closed.

## 4. Scope And Change Map

### Reviewed scope

- full `3f792e4...d85703a` four-commit remediation delta across fourteen files;
- public failure constants, tuple membership, emitted observation routing, and
  package docs;
- strict proof collection and validation at every WeChat mutating fallback;
- valid `-25206` and `-25205` paths plus `-25204`, wrong pairing, missing
  fields, malformed values, contradictions, EOF, timeout, and malformed worker
  frames;
- design amendment, implementation notes, exact-head verification record,
  release preflight, wheel/API smoke, and GitHub CI.

### Excluded scope

- fresh real WeChat action or message submission;
- signed/notarized helper execution and TestPyPI/PyPI publication;
- private raw observations and unrelated dirty primary-worktree files;
- Ruff and mypy because they are unavailable and are not configured CI gates.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Failure routing | Declare and register `accessibility_action_unsupported`. | Tuple-based consumers classify both native unsupported results. | Low | Real normalized observations assert tuple membership. |
| Proof parsing | Type-check action effect before metadata promotion. | Malformed payloads remain diagnostic and do not raise. | Low | Object-valued effect regression passes. |
| WeChat recovery | Require one complete, consistent action/error/no-effect proof. | Valid results fallback once; every uncertain shape stops. | Low | Path, cross-package, and stress tests pass. |
| Documentation | Define the same proof in design and stable API docs. | Integrators receive one recovery contract. | Low | Preflight validates docs and public surfaces. |

## 5. Findings

### PRR-025 - `[S2][Resolved][API Contract]` New package failure was missing from the stable routing tuple

- **Location:** `packages/computer-use-macos/src/computer_use_macos/errors.py:52-96` and `packages/computer-use-macos/tests/test_package.py:2261-2344` @ `d85703a7d95f0dab4b1062678ad0cf4d7e6dd983`
- **Confidence:** High
- **Status:** resolved
- **Observation:** `ACCESSIBILITY_ACTION_UNSUPPORTED` now owns the emitted
  value and is included in `COMPUTER_USE_FAILURE_KINDS`.
- **Trigger:** A direct native `AXPress/-25206` or `AXSetFocus/-25205` result is
  routed by a package consumer.
- **Impact:** The result is classified as a stable package failure instead of
  falling into an unknown route.
- **Evidence:** Both normalized observations assert their failure kind is in
  the tuple; package, root, wheel, API smoke, and CI checks pass.
- **Required change:** Completed.
- **Verification:** 143 computer-use tests and exact-head CI passed.

### PRR-026 - `[S2][Resolved][Reliability/Safety]` Contradictory unsupported evidence could trigger a second mutation

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4137-4326` and `packages/wechat-desktop-tool/tests/test_tool.py:2793-2892,3184-3237` @ `d85703a7d95f0dab4b1062678ad0cf4d7e6dd983`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The recovery exception now requires consistent failure kind,
  action, attempted state, effect, and native error code evidence. Present
  malformed containers or values invalidate the proof.
- **Trigger:** A version-skewed, custom, or malformed backend supplies an
  unsupported result with incomplete or contradictory evidence.
- **Impact:** WeChat returns the first failure and performs no coordinate click,
  selector click, keypress, focus operation, or next opening strategy.
- **Evidence:** Eleven synthetic proof variants and fifteen real worker result
  modes fail closed; the worker set passed ten stress repetitions for 150
  unsafe outcomes with zero fallback. Valid press and focus cases still use
  exactly one fallback.
- **Required change:** Completed.
- **Verification:** 138 WeChat tests, clean-clone stress, and exact-head CI
  passed.

`PRR-001` through `PRR-024` remain resolved for this reviewed snapshot.

## 6. Required Actions Before Merge

No blocking actions remain under this Review Contract.

Repository-owner actions such as changing the PR from draft to ready, merging,
signed-helper proof, and publication are outside this read-only review.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security and privacy | Low | Diagnostics can contain bounded transient UI data. | Keep raw observations and smoke JSON untracked. / maintainer |
| Data integrity | Low | Future backend shapes could add proof aliases. | Unknown aliases do not establish proof; update parser and tests together. / both package owners |
| Reliability | Low | Worker EOF and timeout remain possible. | Dispatch-aware no-replay remains covered by real subprocess tests. / computer-use-macos |
| API compatibility | Low | New named constant is additive. | Existing tuple and observation fields remain compatible. / computer-use-macos |
| Deployment and rollback | Low | Recovery is stricter for malformed backends. | Revert `0b78eff`; no persisted migration exists. / maintainer |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root unittest discovery | clean `0b78eff`; Darwin arm64; CPython 3.12.7 | PASS | 0 | 127 tests in 51.076 s, including wheel/release integration. |
| Protocol package | same clean clone | PASS | 0 | 55 tests in 0.017 s. |
| Computer-use package | same clone; `ResourceWarning` as error | PASS | 0 | 143 tests in 1.602 s; one sandbox socket skip. |
| WeChat package | same clone; `ResourceWarning` as error | PASS | 0 | 138 tests in 1.193 s. |
| Unsafe cross-package stress | same clone; 15 modes x 10 | PASS | 0 | 150 unsafe outcomes, zero fallback. |
| Compile | external pycache | PASS | 0 | Package, example, script, and test sources compiled. |
| Release preflight | same clean clone | PASS | 0 | Mandatory gates passed; expected socket and seven external-proof warnings. |
| Wheel/API smoke | isolated temporary wheelhouse | PASS | 0 | Three 0.2.0 wheels passed build/install/import/API smoke; old dependency pairing rejected. |
| Diff and clean tree | exact `d85703a` clean clone | PASS | 0 | Whitespace passed and clone remained clean. |

### CI / platform checks observed

| Check | Status | Evidence / notes |
|---|---|---|
| GitHub Actions run 29428052131 | PASS | Exact implementation head `0b78eff`. |
| GitHub Actions run 29429104699 | PASS | Exact review/evidence head `d85703a`. |

### Checks not run

- Fresh live WeChat mutation was unnecessary for deterministic result-shape
  and no-replay verification.
- Signed helper, TestPyPI, PyPI, and publication proof remain F7 gates.
- Ruff and mypy are unavailable and are not configured CI gates.

Overall validation is `PARTIAL` only because external live/release proof is
outside this remediation. Every automated and review-specific check passed.

## 9. Coverage And Limitations

- This report is authoritative only for
  `d85703a7d95f0dab4b1062678ad0cf4d7e6dd983`.
- No real desktop mutation or package publication was performed.
- Private smoke outputs and unrelated worktree changes were excluded.
- Existing generated-script failure-kind inventory outside `PRR-025` was not
  broadened in this remediation.

## 10. Open Questions And Assumptions

### Open questions

None blocking.

### Assumptions

1. `nativeErrorCode` remains required safety proof for the new unsupported
   failure kind, as recorded in the amended feature design.
2. The direct backend owns the exact `AXPress/-25206` and
   `AXSetFocus/-25205` pairings.
3. Draft/merge/release state changes remain repository-owner actions.

## 11. Non-blocking Recommendations

- **NOTE-023 [testing]** Inventory older generated-script failure literals in
  a separate maintenance change instead of widening this reviewed remediation.
- **NOTE-024 [maintainability]** If new proof aliases are added, centralize
  their schema and add malformed duplicate counterexamples in the same change.
- **NOTE-016 [documentation]** Keep release notes explicit about both
  dispatch-aware no-replay and the definite unsupported single-fallback
  exception.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-d85703a.json`](./pr-review-macos-computer-use-3-d85703a.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: d85703a7d95f0dab4b1062678ad0cf4d7e6dd983
blocking_findings: []
resolved_findings:
  - PRR-025
  - PRR-026
validation_status: PARTIAL
report_status: CURRENT
```
