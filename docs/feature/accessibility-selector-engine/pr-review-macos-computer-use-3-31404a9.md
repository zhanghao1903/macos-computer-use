# PR Review — `zhanghao1903/macos-computer-use#3` @ `31404a9`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `zhanghao1903/macos-computer-use` |
| Pull Request | `#3` — Add internal Accessibility selector engine |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d` |
| Reviewed at | `2026-07-17T16:50:37Z` |
| Reviewer | Codex (GPT-5), Track A closure plus independent Track B selector/WeChat passes |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| Previous review | `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-eb543ec.md` @ `eb543ec9eb3800de104dadeb5d2fbb1382d14416`, `REQUEST_CHANGES` |
| Previous result integrity | `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-eb543ec.json`; SHA-256 `b5ba351a0cbdf2d5d32cdf5d030cc6e3fdf7118398d0f8b97ccc34981f6782c1` |
| Supersedes | `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-eb543ec.md` |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` from the review gate (GitHub reports mechanically mergeable/clean)
- **Blocking findings:** 4 (`PRR-039`, `PRR-042`, `PRR-043`, `PRR-044`)
- **Approval renewal:** `FAIL`
- **Rationale:** Exact-head probes reproduce resolution, caching, UI mutation, drafting, and submission from contradictory or malformed evidence. Configured tests and CI are green but do not cover these counterexamples, so the PR must remain draft and must not be merged.

## 3. Executive Summary

The eight remediation commits close `PRR-040` and `PRR-041` and keep 17 earlier findings closed. They only partially close `PRR-039`, `PRR-042`, and `PRR-043`; an independent fresh-context profile pass also found `PRR-044`. The unsafe cases cross target-selection and sensitive-send boundaries, so the result remains `REQUEST_CHANGES`.

## 4. Scope and Change Map

### Reviewed scope

- All 20 delta paths and eight commits in `eb543ec9eb3800de104dadeb5d2fbb1382d14416..31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`.
- Full `fed652343ec73734247955d44dc8e60293a7b373..31404a933f29ef9a50d671a0fe2a5d75a3a36b5d` PR diff reconciled through prior closure and fresh forward-risk passes.
- Selector profiles, query envelope normalization/cache, WeChat target selection and send ordering, tests, lifecycle records, packaging/preflight, and exact-head CI.

### Excluded or unavailable scope

- Live WeChat contact switch/draft/send, signed/notarized helper execution, and external publication proof.
- Ruff and strict repository-wide mypy are not configured clean gates for this repository.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Profile validation | Presence-sensitive `any_of` and finite checks | Prior cases close; malformed root/no-op matcher still activates | High | Track A closure + Track B probe |
| Query envelopes | Structural success/failure validation | Duplicate/outer/error/completeness contradictions still resolve/cache | High | Exits 4 and 31 |
| WeChat targets | Contact-target and search-result gates | Hidden duplicates, partial names, malformed paths, wrong provenance remain actionable | High | Exits 3, 43, 46, 45 |
| Lifecycle records | Remediation design, plan, verification, handoff | PR remains draft / request changes | Medium | All 20 paths reconciled |

### Re-review reconciliation

| Previous report | Previous base/head | Previous decision | Current base/head | Delta | Old decision state |
|---|---|---|---|---|---|
| `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-eb543ec.md` | `fed652343ec73734247955d44dc8e60293a7b373` / `eb543ec9eb3800de104dadeb5d2fbb1382d14416` | `REQUEST_CHANGES` | `fed652343ec73734247955d44dc8e60293a7b373` / `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d` | eight commits, 20 files | `SUPERSEDED` |

- **Delta commits reviewed:** `057154a657ef51bb78279dbc22d3e21186af9691`, `27fe73f8c228cb6174f62591261771878d641db3`, `4601ecfe03a69e717dad6487a75eb28647a7f4bd`, `bb8506da18bad164002a2c6b1781c8841d1d1d95`, `63a45cfe53b6b7864ba27531b936cd2c8bea6e6e`, `b01aa01312a8c64f3476c966ee5659eaed9eed6f`, `a186f2b64b57484144bf814da097c4da88edbba1`, `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`
- **Delta files reviewed:** all 20 paths; see machine-readable result.
- **Unclassified changes:** none.
- **Full base-to-head diff reconciled:** `true`

#### Finding closure ledger

| Finding | Previous status | Current status | Current-head evidence | Negative regression |
|---|---|---|---|---|
| PRR-021 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-028 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-026 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-027 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-029 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-030 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-031 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-032 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-033 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-034 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-035 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-036 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-022 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-025 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-037 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-038 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-039 | open | open | Partial remediation: the original ordinary malformed/truncated matrix closes, but false-plus-reason and alias contradictions still mutate (exit 3). | FAIL |
| PRR-023 | resolved | resolved | No fingerprint recurrence in current-head suites/reconciliation. | PASS |
| PRR-040 | open | resolved | Resolved: presence-sensitive any_of parsing and empty/wrong-type rejection pass current-head tests and Track A closure. | PASS |
| PRR-041 | open | resolved | Resolved: non-finite numeric fields are rejected by parser/defensive validation and current-head matrices pass. | PASS |
| PRR-042 | open | open | Partial remediation: the original field-type matrix closes, but outer/duplicate/error/completeness contradictions still resolve and cache (exits 4 and 31). | FAIL |
| PRR-043 | open | open | Partial remediation: the original seven candidate cases close, but exact-name, full-cardinality, path, and app/window provenance counterexamples still draft/submit (exits 43, 46, and 45). | FAIL |

New forward-risk finding: `PRR-044` is `open`.

#### Forward-risk surfaces

| Surface | Risk triggers | Affected paths | Discriminating checks | Result |
|---|---|---|---|---|
| Lifecycle/public records | public contract, test adequacy | 11 docs/report paths | Claim-to-code reconciliation | FAIL |
| Profile parser/validator | public contract, trust boundary | profile, validation, tests | falsey root + no-op matcher matrices | FAIL |
| Query envelope/cache | trust boundary, data integrity | resolver, collections, tests | duplicate/outer/error/reason agreement | FAIL |
| WeChat send path | mutation, privacy, data integrity | tool and tests | exact cardinality/name/path/window + order | FAIL |

#### Approval-renewal gate

- [x] Old decision invalidated
- [x] Previous findings revalidated at current head
- [x] Forward-risk review completed
- [x] All delta changes classified and full PR diff reconciled
- [x] Decision-critical assumptions verified
- [x] Current-head validation and CI complete
- [ ] No open blocker or decision-blocking limitation
- **Independent pass:** `FAIL` — independent selector and WeChat tracks reproduced current-head fail-open behavior.

## 5. Findings

### PRR-039 — `[S1][Blocking][data-integrity]` Contradictory completeness evidence still authorizes mutation

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:5312` @ `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`
- **Confidence:** High
- **Status:** open
- **Observation:** `diagnostics.truncated` is type-checked, but reason aliases and their coherence are not. `truncated=false` with `truncationReason=limit` is accepted as complete.
- **Trigger:** A canonical one-candidate target query contains that contradiction or conflicting reason aliases.
- **Impact:** The workflow performs an action and can continue to draft/submit while candidate completeness is unproved.
- **Evidence:** Track A exit 3, SHA-256 `d3ec8a...`; independent Track B reproduced full action/draft/submit.
- **Required change:** Validate all completeness aliases by presence/type/agreement and make every contradiction final before mutation.
- **Verification:** Cross-product all flag/reason/alias states for every target strategy and assert exact zero downstream side effects.

### PRR-042 — `[S2][Blocking][api-contract]` Duplicate, outer, and contradictory query evidence normalizes as success

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py:1040` @ `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`
- **Confidence:** High
- **Status:** open
- **Observation:** The first direct/nested wrapper is selected while outer failure and duplicate wrapper evidence is ignored; success-plus-error and contradictory truncation reasons also remain actionable.
- **Trigger:** Outer failed/inner success, direct success/nested failure, success with `error.message`, false-plus-reason, or conflicting reason aliases.
- **Impact:** A failed/incomplete query returns and caches an actionable element.
- **Evidence:** Track A exit 4; independent selector probe exit 31 with cache writes.
- **Required change:** Inventory and reconcile every visible envelope/alias before normalization; rejected results produce no element and no cache entry.
- **Verification:** Add agreement matrices with explicit failed/no-element/no-cache assertions.

### PRR-043 — `[S1][Blocking][data-integrity]` Search target cardinality, identity, and structure fail open before send

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:5169` @ `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`
- **Confidence:** High
- **Status:** open
- **Observation:** Candidate extraction caps at ten before cardinality, uses substring matching, accepts substring postconditions, coerces bad paths, and does not establish verified WeChat window provenance.
- **Trigger:** Matching rows 1 and 11, request `Ada` with only `Ada Lovelace`, malformed/missing path, or a wrong-app node with a plausible frame.
- **Impact:** An ambiguous or wrong contact can receive drafted and submitted sensitive text.
- **Evidence:** Exact-head probes exit 43 (partial name), 46 (path), and 45 (hidden duplicate); independent WeChat pass reproduced wrong-app coordinate mutation.
- **Required change:** Compute exact-name cardinality over the complete validated set and require valid in-snapshot/in-WeChat-window target proof before any action/click/draft/submit.
- **Verification:** Add >10 duplicate, partial-name, path, app/window, offscreen, and valid exact-one controls with command-order assertions.

### PRR-044 — `[S2][Blocking][api-contract]` Explicit malformed roots and no-op matchers broaden profiles

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/profile.py:102` @ `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`
- **Confidence:** High
- **Status:** open
- **Observation:** Falsey present roots default to `focusedWindow`; empty, `equals:null`, and unknown-key matchers become predicate-free.
- **Trigger:** Load such an otherwise valid override profile, then resolve against a non-matching node.
- **Impact:** Malformed/version-skewed configuration activates, resolves `Settings` for a `Contacts` selector at confidence 1.0, and can become an action target.
- **Evidence:** Independent exact-head selector probe resolves all six falsey roots and three no-op/version-skewed matchers; exit 31, SHA-256 `a3c93495...`.
- **Required change:** Parse roots by key presence and reject present malformed roots, ineffective/null matchers, and unknown v1 matcher keys before activation.
- **Verification:** All invalid profiles must raise the stable validation error and execute zero queries; retain documented absent-root compatibility controls only where applicable.

## 6. Required Actions Before Merge

- [ ] `PRR-039` — Reject all contradictory completeness states before mutation and add strategy-wide zero-side-effect matrices.
- [ ] `PRR-042` — Reconcile all wrapper/failure/completeness evidence and assert no element/cache on rejection.
- [ ] `PRR-043` — Require complete-set exact identity plus structurally valid in-window target proof before send.
- [ ] `PRR-044` — Reject malformed roots/no-op matchers/unknown matcher keys before query.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | High | Wrong/unverified contact can receive user text | PRR-039/043; WeChat maintainer |
| Data integrity | High | Hidden ambiguity selects wrong conversation | Exact complete-set cardinality |
| Reliability & concurrency | Medium | Contradictory envelopes resolve/cache | PRR-042; computer-use maintainer |
| Performance & scalability | Low | Presentation cap is misused as correctness cap | Separate display and decision limits |
| API & compatibility | High | Malformed/version-skewed profiles broaden | PRR-044; profile owner |
| Deployment & rollback | Medium | F6 claims are not yet executable | Keep draft; renew exact-head records |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root suite | clean exact-head clone | PASS | 0 | 128 tests; wheel/install/API smokes |
| app-control-protocol suite | clean exact-head clone | PASS | 0 | 55 tests |
| computer-use-macos suite | clean exact-head clone | PASS | 0 | 168 passed, 1 sandbox skip |
| wechat-desktop-tool suite | clean exact-head clone | PASS | 0 | 159 tests |
| compileall / release preflight / diff check | clean exact-head clone | PASS | 0 | passed; expected external-proof warnings |
| Track A PRR-039 contradiction | exact source/fake app control | FAIL | 3 | mutation after contradictory completeness |
| Track A PRR-042 duplicate wrapper | exact SelectorResolver | FAIL | 4 | four contradictions resolve |
| Independent selector matrix | exact source/tests | FAIL | 31 | resolve/cache plus profile broadening |
| PRR-043 partial name | exact WeChat send path | FAIL | 43 | draft and submit |
| PRR-043 malformed path | exact WeChat send path | FAIL | 46 | draft and submit |
| PRR-043 row-11 duplicate | exact WeChat send path | FAIL | 45 | hidden ambiguity submits |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| CI / test | `2026-07-17T16:50:37Z` | PASS | Job 87935347092 completed at 2026-07-17T16:21:10Z |

### Checks not run

- Live WeChat mutation — review remained read-only; exact-source deterministic probes establish the blockers.
- Signing, notarization, publication — separate release gates.
- Ruff/strict mypy — no configured accepted clean gate.

## 9. Coverage and Limitations

- **Reviewed:** all delta files, full PR reconciliation, profile/query/contact-target/send boundaries, tests/docs/lifecycle/CI.
- **Not reviewed:** live application mutation and external release infrastructure.
- **Missing context:** no additional requirement or log is needed to reproduce the blockers.
- **Staleness condition:** any base/head change or material external evidence change requires re-review.

## 10. Open Questions and Assumptions

No open question changes the decision.

| Assumption | Decision-critical | Status | Evidence |
|---|---|---|---|
| Remote snapshot stayed fixed | true | VERIFIED | base `fed6523`, head `31404a9`, draft, CI success |
| Deterministic paths preserve production branching/order | true | VERIFIED | exact-source imports and independent reproductions |
| Green configured tests cover boundary contradictions | true | FALSIFIED | exits 3, 4, 31, 43, 46, 45 |

## 11. Non-blocking Recommendations

None.

## 12. Machine-readable Summary

- Result file: `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-31404a9.json`
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.1"
review_kind: RE_REVIEW
decision: REQUEST_CHANGES
mergeable: false
head_sha: 31404a933f29ef9a50d671a0fe2a5d75a3a36b5d
blocking_findings:
  - PRR-039
  - PRR-042
  - PRR-043
  - PRR-044
validation_status: FAILED
report_status: CURRENT
```
