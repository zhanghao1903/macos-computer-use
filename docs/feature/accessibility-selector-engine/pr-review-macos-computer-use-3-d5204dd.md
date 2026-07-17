# PR Review - `zhanghao1903/macos-computer-use#3` @ `d5204dd`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `d5204dd7c859937fad07f84a69f3774a4f208855` |
| Reviewed at | 2026-07-15T13:26:32Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT`; supersedes the `d2dadd0` report |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 127 commits; 112 changed files; 41,694 additions; 1,500 deletions |

## 2. Decision

- **Decision:** `APPROVE`
- **Mergeable:** `true` under this Review Contract
- **Open blocking findings:** none
- **Resolved in the reviewed delta:** `PRR-022`, `PRR-023`, `PRR-024`
- **Rationale:** Definite unsupported native AX results now carry an explicit
  no-effect contract and receive one policy-gated fallback. Unknown,
  contradictory, malformed, post-dispatch, and legacy attempted outcomes
  remain fail-closed. Clean-clone tests, repeated cross-package
  counterexamples, package/release/wheel gates, synchronized F6 surfaces, and
  exact-head CI all pass.

## 3. Executive Summary

The remediation separates a native call attempt from its UI effect.
`AXPress/-25206` and `AXSetFocus/-25205` are normalized as definite
unsupported/no-effect results, while `-25204` and all transport-unknown results
remain non-replayable. The WeChat adapter accepts the exception only when the
new failure kind has complete and non-contradictory `actionEffect=none`
evidence, then executes at most one existing fallback.

Tracked merge-readiness, the tracked PR description, and the GitHub PR body now
describe the same implementation, finding state, test counts, and pending
replacement-review state. No blocking defect was identified. `PRR-001`
through `PRR-024` are resolved for this snapshot.

## 4. Scope and Change Map

### Reviewed scope

- frozen GitHub PR metadata, body, draft/merge state, base/head SHAs, full
  changed-file metadata, and exact-head CI;
- focused `d2dadd0...d5204dd` delta: four commits, twelve files, 1,632
  additions, and 334 deletions;
- native AX result generation, client metadata/protocol propagation, WeChat
  fallback precedence, and every existing action recovery caller;
- `AXPress/-25206`, `AXSetFocus/-25205`, `-25204`, EOF, response timeout,
  malformed JSON, contradictory effect, missing effect, legacy attempted
  unsupported, pre-dispatch, and pre-call unsupported outcomes;
- stable API docs, implementation notes, F5 evidence, merge-readiness,
  tracked PR description, existing changelog contract, and live GitHub body;
- clean-clone root/package tests, ten-iteration stress, compile, release
  preflight, wheel build/install/API smoke, whitespace, clean-tree proof, and
  exact-head GitHub Actions.

### Excluded scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff and mypy, which are unavailable and are not configured CI gates.

### Change map

| Area | Main change or observation | External behavior | Risk | Validation |
|---|---|---|---|---|
| Native result semantics | Action results publish `actionEffect` and native failures publish `nativeErrorCode`. | Callers can distinguish performed, definite no-effect, and unknown effect. | Low | Both native unsupported codes and `-25204` mapping pass package tests. |
| WeChat recovery | One narrow precedence exception requires the new failure kind plus consistent `none` effect. | AX rows and unsupported focus can use one fallback without weakening no-replay. | Low | Cross-package success and seven unsafe modes pass. |
| Compatibility | Legacy unsupported-without-attempt and proven pre-dispatch fallback remain available. | Existing integrations preserve their safe recovery paths. | Low | Existing and new regressions pass. |
| F6 lifecycle | Tracked records and GitHub body were synchronized to the same pending-review snapshot. | Maintainers no longer see obsolete SHAs, counts, or decisions. | Low | GitHub REST snapshot matches the tracked PR description. |
| Packaging/release | No version, dependency, command, config key, or schema version changed. | Additive observation fields preserve package compatibility. | Low | Preflight, wheels, isolated installs, API smoke, and CI pass. |

## 5. Findings

### PRR-022 - `[S2][Resolved][Correctness/Compatibility]` Definite unsupported AX actions were treated as unknown mutations

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:132-145,1560-1584,4073-4121,4401-4435` and `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4133-4235` @ `d5204dd7c859937fad07f84a69f3774a4f208855`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The native script now maps only
  `kAXErrorActionUnsupported` for `AXPress` and
  `kAXErrorAttributeUnsupported` for `AXSetFocus` to
  `accessibility_action_unsupported`, with `actionAttempted=true`,
  `actionEffect=none`, and the exact native error code. Other native failures
  carry `actionEffect=unknown`.
- **Trigger:** A verified WeChat row rejects `AXPress` with `-25206`, or a
  verified search element rejects the focused attribute with `-25205`.
- **Impact:** Both cases retain exactly one configured fallback, restoring the
  documented AXRow compatibility path without replaying uncertain actions.
- **Evidence:** Native mapping and protocol propagation are explicit in
  `client.py`; the WeChat predicate requires the new failure kind and all
  observed effect values to be `none`; cross-package worker tests record one
  native request and one fallback for both supported cases.
- **Required change:** Completed.
- **Verification:** Completed. `-25206` and `-25205` use one fallback;
  `-25204`, EOF, timeout, malformed, contradictory, missing, and legacy
  attempted outcomes use zero.

### PRR-023 - `[S2][Resolved][Documentation/Lifecycle]` F6 merge records published obsolete review state

- **Location:** `docs/feature/accessibility-selector-engine/merge-readiness.md`,
  `docs/feature/accessibility-selector-engine/pr-description.md`, and the
  GitHub PR #3 body @ `d5204dd7c859937fad07f84a69f3774a4f208855`
- **Confidence:** High
- **Status:** resolved
- **Observation:** Both tracked F6 documents now identify `916ac1d` as the F5
  evidence head, retain the `d2dadd0` request-changes decision until this
  replacement review exists, and record the remediated finding state and
  current test counts. The GitHub body was replaced from the tracked
  description and no longer contains the obsolete `07fa052` decision.
- **Trigger:** A maintainer reads the repository or platform surface before
  changing the draft/merge state.
- **Impact:** All three surfaces now present one auditable pre-review state;
  this report supplies the replacement decision.
- **Evidence:** GitHub REST returned head `d5204dd`, draft/open/clean state, and
  the same body as tracked `pr-description.md`; exact-head CI run 29418761726
  passed.
- **Required change:** Completed. A final docs-only status sync should link
  this approval before changing draft state.
- **Verification:** Completed for the reviewed snapshot.

### PRR-024 - `[S3][Resolved][API Contract]` Unsupported-action documentation had contradictory precedence

- **Location:** `docs/api.md:252-270` and
  `docs/wechat-desktop-tool.md:462-480` @
  `d5204dd7c859937fad07f84a69f3774a4f208855`
- **Confidence:** High
- **Status:** resolved
- **Observation:** Both documents now state that definite unsupported/no-effect
  evidence is the sole attempted/dispatched exception and that `-25204`,
  unknown, missing, or contradictory effect evidence remains blocked.
- **Required change:** Completed.
- **Verification:** Preflight validated both stable documents and tests enforce
  the same precedence.

No blocking findings were identified for the reviewed snapshot.

### Prior finding lifecycle

| Finding range | Status | Closure evidence |
|---|---|---|
| `PRR-001` through `PRR-017` | Resolved | Privacy, identity, selector, packaging, pagination, proof, and performance gates remain green. |
| `PRR-018` through `PRR-021` | Resolved | Worker framing/deadline/dispatch and downstream no-replay gates remain green. |
| `PRR-022` | Resolved | Definite unsupported/no-effect and uncertain native outcomes are separated and cross-package tested. |
| `PRR-023` | Resolved | Tracked F6 records and GitHub body agree on the reviewed snapshot. |
| `PRR-024` | Resolved | Stable documents publish the implemented precedence. |

## 6. Required Actions Before Merge

None under this Review Contract.

Before changing the GitHub draft state, perform the non-behavioral status
synchronization in `NOTE-019` so maintainers can discover this report from all
F6 surfaces.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Desktop diagnostics can contain transient UI text. | Keep raw artifacts untracked and publish bounded semantic evidence. / feature maintainer |
| data-integrity | Low | A dispatched action can still have an unknown outcome. | Preserve fail-closed handling unless no effect is explicitly and consistently proven. / both package owners |
| reliability-concurrency | Low | Worker EOF, timeout, or malformed responses remain possible. | Preserve dispatch evidence and zero downstream mutation. / both package owners |
| api-compatibility | Low | Consumers may not recognize the new additive fields or failure kind. | Existing fields remain; stable docs define recovery and unknown consumers still receive a normal failure. / computer-use-macos |
| performance-scalability | Low | One warm worker serializes AX actions. | Keep bounded deadlines and timing diagnostics. / computer-use-macos |
| deployment-rollback | Low | Recovery semantics changed in WeChat action paths. | Revert `3fd41ce`; no migration or persisted state conversion exists. / feature maintainer |
| maintainability | Low | Effect evidence appears in direct, metadata, and nested locations. | Keep one extraction predicate and cross-package contract tests. / wechat-desktop-tool |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root repository unittest discovery | clean isolated `3fd41ce`; Darwin arm64; CPython 3.12.7 | PASS | 0 | 127 tests passed in 44.070 s, including wheel and release integration checks. |
| Protocol package | same isolated clone | PASS | 0 | 55 tests passed in 0.013 s. |
| macOS package with `ResourceWarning` as error | same isolated clone | PASS | 0 | 142 tests passed in 1.563 s; one sandbox skip. |
| WeChat package with `ResourceWarning` as error | same isolated clone | PASS | 0 | 137 tests passed in 0.963 s. |
| Seven unsafe cross-package outcomes, ten iterations | same isolated clone | PASS | 0 | 10/10 tests passed in 3.835 s; 70 dispatch/outcome executions, zero replay. |
| Compile | same isolated clone with external pycache | PASS | 0 | All package, example, script, and test Python sources compiled. |
| Release preflight | same isolated clone | PASS | 0 | Mandatory gates passed; only expected socket and seven external-proof warnings remained. |
| Wheel build/install/API smoke | same isolated clone; `/opt/anaconda3/bin/python` | PASS | 0 | Three 0.2.0 wheels built and installed; API smoke and old dependency rejection passed. |
| Diff/whitespace/clean tree | exact local review head and isolated implementation clone | PASS | 0 | `git diff --check origin/main...HEAD` passed; clone remained clean. |
| GitHub PR body and metadata | GitHub REST API | PASS | 0 | Head/base, open/draft/clean state, body, commit/file counts, and synchronized F6 text were observed. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| CI / test - run 29396951638, job 87292520782 | 2026-07-15 | PASS | Exact F5 head `916ac1d` passed every configured check. |
| CI / test - run 29418761726, job 87363517193 | 2026-07-15T13:26:32Z | PASS | Exact review head `d5204dd`; configured tests, preflight, package, wheel, sdist, and content checks passed in 1m47s. |

### Checks not run

- **Fresh real WeChat action or send:** deterministic SDK/error and real worker
  protocol tests cover this classification boundary without risking a desktop
  mutation.
- **Post-submit delivery read-back:** outside this remediation review.
- **Signed helper and real release publication:** later F7 external gates.
- **Ruff and mypy:** unavailable and not configured CI gates.

Overall validation status is `PARTIAL` only because live desktop and external
release proof were deliberately excluded. All deterministic and platform
checks required for `PRR-022` through `PRR-024` passed.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `d5204dd7c859937fad07f84a69f3774a4f208855`; later behavior changes require
  re-review.
- Local implementation verification ran at `3fd41ce`; `916ac1d` adds only F5
  evidence and `d5204dd` adds only F6 records. Exact-head CI reran all
  configured checks.
- No fresh real desktop mutation, signed helper, or publication was performed.
- Private raw observations and unrelated dirty worktree files were excluded.
- The PR remains draft by design.

## 10. Open Questions and Assumptions

### Open questions

None that block merge.

### Assumptions

1. Apple's `kAXErrorActionUnsupported` and
   `kAXErrorAttributeUnsupported` mean the requested operation was rejected
   without applying its UI effect.
2. `kAXErrorCannotComplete`, transport loss, and missing or contradictory
   effect evidence leave the outcome unknown and prohibit another mutation.
3. Additive observation fields and a more specific failure kind are compatible
   with consumers that already handle Accessibility action failure.
4. A final docs-only approval-link synchronization does not alter reviewed
   runtime behavior.

## 11. Non-blocking Recommendations

- **NOTE-019 [documentation]** Update `merge-readiness.md`, tracked
  `pr-description.md`, and the GitHub body to link this approval and the latest
  exact-head CI before changing draft state.
- **NOTE-020 [hardening]** Consider rejecting any present non-string or empty
  duplicate `actionEffect` value as contradictory, even when another location
  reports `none`; supported backend output is already consistent.
- **NOTE-013 [testing]** Add Ruff to the development dependency group or remove
  it as an unavailable documented gate.
- **NOTE-014 [performance]** Collect repeated live percentiles if the
  three-second target becomes an operational SLO.
- **NOTE-016 [documentation]** Keep the final release note explicit about warm
  workers, dispatch-aware no-replay, and definite unsupported fallback.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-d5204dd.json`](./pr-review-macos-computer-use-3-d5204dd.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: d5204dd7c859937fad07f84a69f3774a4f208855
blocking_findings: []
resolved_findings:
  - PRR-022
  - PRR-023
  - PRR-024
validation_status: PARTIAL
report_status: CURRENT
```
