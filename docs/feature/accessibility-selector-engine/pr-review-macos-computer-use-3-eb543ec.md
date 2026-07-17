# PR Review - `zhanghao1903/macos-computer-use#3` @ `eb543ec`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `zhanghao1903/macos-computer-use` |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `eb543ec9eb3800de104dadeb5d2fbb1382d14416` |
| Reviewed at | `2026-07-17T14:01:31Z` |
| Reviewer | `Codex (GPT-5)` with three independent review passes |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| GitHub state | `OPEN`, `DRAFT`, mechanically mergeable, merge state `CLEAN` |
| Scope size | 156 commits; 128 base-to-head changed paths; 53,942 additions; 1,639 deletions |
| Previous authoritative review | `pr-review-macos-computer-use-3-e86181a.md` @ `e86181a`, `REQUEST_CHANGES` |
| Previous result integrity | `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-e86181a.json`, SHA-256 `d613b748f5c843636fdfc79cc6f1a930ab92ac908ffcb4839e4be28b1f60a208` |
| Supersedes | `pr-review-macos-computer-use-3-e86181a.md` |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable under this Review Contract:** `false`
- **Blocking findings:** 5 (`PRR-039`, `PRR-040`, `PRR-041`, `PRR-042`, `PRR-043`)
- **Approval renewal:** `WITHHELD`
- **Independent pass:** `FAIL`
- **Applies only to:** exact head
  `eb543ec9eb3800de104dadeb5d2fbb1382d14416`

The PR must remain draft and must not be merged. The remediation closes
`PRR-023`, `PRR-026`, `PRR-037`, and `PRR-038`, but `PRR-039` remains open
under mixed-root, malformed-result, and strategy-continuation inputs. The fresh
forward-risk review also found four previously missed selector-profile,
query-contract, and search-target blockers.

## 3. Executive Summary

The latest commits correctly restore bundle-first app identity, publish the
frontmost-target failure constants, reject the previously demonstrated
contradictory action evidence, and fail closed for ordinary single-query
truncation and final search-query failure. All repository/package suites,
compilation, packaging, release preflight, and exact-head GitHub CI pass.

Those green checks do not cover five blocking counterexample classes. WeChat
can still mutate after an earlier root or strategy returned incomplete,
malformed, or failed target-selection evidence; unverified search-result sets
can still reach Return, draft, and submit; malformed selector profiles can
erase an explicit matcher or inject non-finite confidence values; and
contradictory query-result envelopes can still become actionable selector
targets. The immediate next action is to repair all five contracts and add the
discriminating side-effect and validation matrices before another exact-head
review.

## 4. Scope and Change Map

### Reviewed scope

- The complete `e86181a..eb543ec` remediation delta: eight commits and all 19
  changed paths.
- The complete base-to-head PR diff as reconciled through the previous review
  ledger and fresh forward-risk passes.
- `computer-use-macos` generated query/action workers, public failure registry,
  selector profile parser/validator, query-result normalization, resolver,
  matching, package exports, wheel smoke, and compatibility documentation.
- `wechat-desktop-tool` contact-target queries, multi-root selection,
  truncation/failure parsing, action recovery, search-result selection,
  frame validation, Return fallback, chat verification, draft, and submit.
- Feature lifecycle records, PR body, changelog, release preflight, package
  tests, root integration tests, compilation, diff hygiene, and exact-head CI.

### Excluded or unavailable scope

- No live WeChat contact switch, draft, or send was executed; mutation evidence
  used deterministic fake-transport and generated-worker paths.
- Signed/notarized helper execution, TestPyPI/PyPI publication, and trusted
  publisher proof remain release-stage work.
- Ruff is unavailable, and repository-wide strict mypy has no accepted clean
  baseline; neither is a configured CI gate.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Frontmost identity | Exact bundle match now takes precedence over localized name. | Supported `WeChat`/`微信` aliases reach the requested app. | Medium | Generated query/action workers reach `AXUIElementCreateApplication`; negative identity cases pass. |
| Public failure contract | Three frontmost-target failure constants are declared, exported, registered, documented, and packaged. | Consumers can import and route every new value. | Medium | Producer, registry, root-suite, wheel-install, and API-smoke checks pass. |
| Action recovery | Legacy/pre-dispatch recovery rejects `performed`, `unknown`, and native-code contradictions. | Previously unsafe results no longer execute a second mutation. | High | Exact-head revalidation probe and focused/full tests pass. |
| Contact target selection | Normal single-query truncation and final query failure now stop. | Some unsafe inputs fail with structured failures before mutation. | High | Positive regressions pass, but mixed-root/malformed/strategy-continuation probe fails (`PRR-039`). |
| Selector profile/query contracts | No remediation in this delta. | Malformed profiles and result envelopes can still produce actionable targets. | High | Adversarial probes fail (`PRR-040`, `PRR-041`, `PRR-042`). |
| Search-result mutation | Frame filtering was added earlier in this PR while the zero-candidate Return path remained. | Unverified or hidden ambiguity can still reach draft and submit. | High | Search candidate matrix fails (`PRR-043`). |
| Lifecycle and release | Tracked/live handoff records describe the prior request-changes state; tests and CI are current. | The PR remains draft and does not publish obsolete approval. | Low | Live PR body, tracked description, exact head, and CI were compared. |

### Re-review reconciliation

| Previous report | Previous base/head | Previous decision | Current base/head | Delta | Old decision state |
|---|---|---|---|---|---|
| `pr-review-macos-computer-use-3-e86181a.md` | `fed6523` / `e86181a` | `REQUEST_CHANGES` | `fed6523` / `eb543ec` | `e86181a..eb543ec` | `SUPERSEDED` |

- **Delta commits reviewed:** `35660cc7832b1c01401a2b4e4e04a3d2e9df7e2c`,
  `9cd88d09c03a7a61b0c125963197b442b2c2f8cf`,
  `60138f3d5c56047848280546e1c304dc493e8e19`,
  `7464ad15dd703e0f1ec690861c81e95be579ad5e`,
  `196710753d3318ac86d72dc34c1d004eab08bb26`,
  `7d870ac508b8fd518f145baf4aa0f327f54bd834`,
  `45774fe5bf0d7fbb2e5c2a551c1ae6d278034cbf`, and
  `eb543ec9eb3800de104dadeb5d2fbb1382d14416`.
- **Delta files reviewed:** all 19 changed paths.
- **Unclassified changes:** none.
- **Full base-to-head diff reconciled:** `true`.

#### Finding closure ledger

| Finding | Previous | Current | Current-head evidence |
|---|---|---|---|
| `PRR-021` | resolved | resolved | Named proof containers remain presence/type consistent and malformed copies block fallback. |
| `PRR-028` | resolved | resolved | Valid Boolean truncation in the generic resolver remains fail-closed; malformed result envelopes are separately tracked by `PRR-042`. |
| `PRR-026` | open | **resolved** | The four original legacy/pre-dispatch counterexamples execute only `accessibility_action`; no fallback mutation occurs. |
| `PRR-027` | resolved | resolved | Historical and current review results validate under schema 1.1 invariants. |
| `PRR-029` | resolved | resolved | Unsupported collection selector semantics remain rejected before execution. |
| `PRR-030` | resolved | resolved | Generic selector profile and WeChat control map still activate atomically. |
| `PRR-031` | resolved | resolved | Semantic pagination counts accepted records and accepted lookahead. |
| `PRR-032` | resolved | resolved | Query/action/tree workers retain usable-frontmost target enforcement. |
| `PRR-033` | resolved | resolved | Normal evidence/events retain allowlisted safe projections. |
| `PRR-034` | resolved | resolved | Generated query limits remain at or below 500. |
| `PRR-035` | resolved | resolved | Structured failure cause/truncation remains authoritative over text heuristics. |
| `PRR-036` | resolved | resolved | Worker failures remain declared, exported, and registry-routable. |
| `PRR-022` | resolved | resolved | Native unsupported results retain the exact requested action. |
| `PRR-025` | resolved | resolved | `accessibility_action_unsupported` remains in the stable tuple. |
| `PRR-037` | open | **resolved** | Exact bundle plus localized alias reaches application creation; wrong/name-only/hidden cases remain rejected. |
| `PRR-038` | open | **resolved** | All three values are public, unique, producer-tested, and present in installed-wheel smoke. |
| `PRR-039` | open | **open** | Ordinary single-query cases pass, but nine malformed/mixed-root/continuation cases still mutate. |
| `PRR-023` | open | **resolved** | Live/tracked handoff records now agree on `e86181a` request-changes state, draft status, and pending re-review; final F6 renewal remains required after remediation. |

The diagnostic case where a complete native unsupported/no-effect tuple also
carries valid `requestDispatched=false` is not a finding: design lines
1342-1349 expressly allow the complete native proof to override valid dispatch
evidence, and the first operation is proven to have no effect.

#### Forward-risk surfaces

| Surface | Risk triggers | Affected paths | Discriminating checks | Result |
|---|---|---|---|---|
| Remediation closure | public contract, mutation recovery | worker/client/error exports, `tool.py`, focused tests | Original five blocker probes, producer registry, wheel install | **FAIL** - `PRR-039` remains open |
| Profile validation | public contract, trust boundary | `selectors/profile.py`, `validation.py`, `matching.py`, `resolver.py` | Empty/falsey `any_of`; TOML-compatible `NaN` weights | **FAIL** - `PRR-040`, `PRR-041` |
| Query-result normalization | trust boundary, compatibility | `selectors/resolver.py`, `selectors/collections.py`, WeChat query runner | Wrong-type/contradictory available, status, failure kind, diagnostics, nodes | **FAIL** - `PRR-042` |
| Search target and side effects | data integrity, mutation recovery | WeChat search, frame, verification, draft/submit paths | Seven-case candidate matrix with side-effect order | **FAIL** - `PRR-039`, `PRR-043` |
| Lifecycle/package evidence | deployment compatibility, test adequacy | all delta docs, changelog, scripts, package tests | PR body comparison, 128/55/158/154 suites, compile, preflight, wheel, CI | **PASS** |

#### Approval-renewal gate

- [x] Old decision invalidated.
- [x] Every previous finding revalidated at the current head.
- [x] Forward-risk review completed.
- [x] All delta changes classified and full PR diff reconciled.
- [x] Decision-critical assumptions resolved by verification or falsification.
- [x] Current-head local validation and CI observed.
- [ ] No open blocker or decision-blocking limitation.
- **Independent pass:** `FAIL` - independent public-contract and WeChat
  mutation passes reproduced current-head blockers.

## 5. Findings

### PRR-039 - `[S1][Blocking][High]` Incomplete or failed contact-target queries still lead to mutation

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:1232-1264`,
  `:1354-1378`, `:1543-1552`, `:1640-1647`, and `:5277-5332`
- **Category:** data integrity / reliability
- **Confidence:** High
- **Status:** open (partial remediation)
- **Observation:** `_query_mapped_conversation_target` continues after a failed
  query or a successful truncated empty result and returns only the later root's
  observation. The outer gate therefore cannot see earlier incompleteness.
  `_open_visible_contact_phase` returns `None` on query failure, which the
  caller interprets as permission to continue into the mutating search
  strategy. `_query_truncated` also uses truthiness, so a missing flag or
  integer `0` is treated as a valid complete result.
- **Trigger:** any of: root 1 truncates/fails and root 2 returns one match; a
  visible-target query times out and the later search succeeds; or a decision
  query carries missing/wrong-type `truncated` evidence.
- **Impact:** click, Accessibility action, or Return can execute without a
  complete and valid uniqueness proof. An unseen same-named contact may be
  selected, allowing a composite send flow to target the wrong conversation.
- **Evidence:**
  - `/private/tmp/prr039_re_review_probe_eb543ec.py`, SHA-256
    `643a1da3d3a16e16499345d0c30d69d15bd1110b9c7dd5b0f40fd8f0e099b476`,
    exit 9. Nine unsafe cases executed one or more post-query mutations.
  - Positive controls show valid `truncated=true`, including a missing reason,
    and final search-query failure now stop before the next mutation.
- **Required change:** validate every decision-query result for success,
  diagnostics presence/type, and truncation before continuing a root or target
  strategy. Any failed, truncated, malformed, or incomplete result must be
  final for that target decision.
- **Verification:** run zero/one/multiple candidates over every root/path with
  valid, missing, falsey wrong-type, contradictory, failed, and truncated
  diagnostics; assert exact operation order and zero click, action, Return,
  draft, or submit after the unsafe result.

### PRR-043 - `[S1][Blocking][High]` Unverified search-result sets can reach Return, draft, and submit

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:1441-1496`,
  `:3896-3912`, `:4170-4198`, `:2749-2768`, and `:5986-5995`
- **Category:** data integrity
- **Confidence:** High
- **Status:** open
- **Observation:** search candidates are filtered by frame before ambiguity is
  decided. Zero candidates then take an unbound Return path, and two matches
  with one offscreen are reduced to a false unique match. Missing/malformed
  frames and malformed node collections likewise become Return or an action;
  `_element_from_query_node` converts invalid frame members to zero. The title
  postcondition checks only the display name/substrings and cannot distinguish
  two contacts with the same title.
- **Trigger:** an empty complete result, offscreen-only result, missing or
  malformed frame, malformed nodes shape, or two same-name matches where only
  one passes the frame filter.
- **Impact:** an unverified contact may be opened, after which `send_message`
  drafts and submits sensitive text to that conversation.
- **Evidence:**
  - `/private/tmp/pr3_search_candidate_gate_matrix_probe_eb543ec.py`, SHA-256
    `612d719288dc6fbe2c0ccca475494dac4f6566dbc486b85996cf849e57b9eb3f`,
    exit 44. Six unsafe inputs all returned success and completed draft/submit;
    two valid in-window matches correctly blocked as the negative control.
  - `/private/tmp/pr3_offscreen_search_send_probe_eb543ec.py`, SHA-256
    `4a867ab8d06d0c5efa8a0fb0088b7f80b80537f5a85c6430178511f7833f1990`,
    exit 41, executed `... query -> Return -> verify -> type_text -> Return`.
  - `test_open_contact_ignores_offscreen_search_candidate_and_uses_return`
    currently codifies the unsafe expectation introduced by PR commit
    `6a74c1d`.
- **Required change:** require exactly one structurally valid target from the
  complete pre-filter candidate set, and require that target to have a valid
  in-window frame before any mutation. Zero, malformed, offscreen, or ambiguous
  sets must fail closed. Return may only recover from a request-bound candidate
  action with definite no-effect evidence.
- **Verification:** retain the seven-case matrix and assert zero target action,
  Return, draft, and submit for all six unsafe sets; keep the two-valid-match
  ambiguity control.

### PRR-040 - `[S2][Blocking][High]` Explicit empty `any_of` matchers are erased and broaden selectors

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/profile.py:181-187`
- **Category:** correctness / configuration
- **Confidence:** High
- **Status:** open
- **Observation:** the parser uses `if any_of else None`, so explicit
  `any_of=[]` and other falsey wrong-type values become `None`. The validator's
  non-empty check can no longer distinguish malformed input from an absent
  constraint, and matching skips the attribute condition entirely.
- **Trigger:** a TOML/JSON override contains a present empty `any_of` for a
  selector attribute.
- **Impact:** a wrong-label control satisfying the remaining role/action fields
  can resolve with confidence 1.0 and later become a UI action target instead
  of causing the override to be rejected/falling back to packaged defaults.
- **Evidence:** `/private/tmp/pr3_selector_profile_failopen_probe_eb543ec.py`,
  SHA-256
  `91834ba30366bb0de6448c0da71cac93f7192010c270170fdebd5da074b1dba7`,
  exit 31: `parsed=None`, wrong label `Settings`, status `resolved`, confidence
  `1.0`.
- **Required change:** parse `any_of` based on key presence, reject empty or
  wrong-type values, and keep absence distinct from explicit malformed input.
- **Verification:** parser, override-activation, resolver, and action-path tests
  must reject empty/falsey wrong-type `any_of` before any AX query or mutation.

### PRR-041 - `[S2][Blocking][High]` Non-finite profile numbers bypass confidence validation

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/profile.py:436-439`,
  `validation.py:272-320`, `matching.py:250-278`, and `resolver.py:373-381`
- **Category:** correctness / configuration
- **Confidence:** High
- **Status:** open
- **Observation:** `_float` accepts `NaN` and infinities, while range and
  non-negative comparisons do not reject `NaN`. Confidence arithmetic can
  return `NaN`, and `confidence < minimum` is then false, so the candidate is
  accepted. TOML supports `nan`, making this reachable through the documented
  override format.
- **Trigger:** an override uses a non-finite confidence, constraint weight,
  relation distance, or frame numeric value; the deterministic case uses
  `structure_weight=nan` with a failed non-required structural constraint.
- **Impact:** a candidate that does not satisfy the intended confidence policy
  can resolve and become actionable; diagnostics also contain a non-JSON-safe
  confidence value.
- **Evidence:** the same profile probe (SHA-256 `91834b...`, exit 31) returned
  status `resolved` and confidence `nan` for the failed selected-state evidence.
- **Required change:** reject every non-finite numeric value during profile
  parsing/validation before constructing immutable profile objects.
- **Verification:** TOML and mapping tests for `nan`, `inf`, and `-inf` across
  all numeric profile fields must fail before query; finite boundary controls
  must retain current behavior.

### PRR-042 - `[S2][Blocking][High]` Malformed or contradictory query envelopes normalize as success

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py:896-950`
- **Category:** API contract / compatibility
- **Confidence:** High
- **Status:** open
- **Observation:** `_normalize_query_payload` ignores `status`, ignores
  malformed failure kinds, treats a present non-Boolean `available` as though
  the field were absent, silently drops malformed node entries, and replaces a
  malformed diagnostics object with `{}`. Downstream truncation consumers also
  use truthiness. A version-skewed or malformed lower-layer response can
  therefore be treated as a complete successful candidate set.
- **Trigger:** examples include `available="false"`, `available=true` with
  `status="failed"`, or `failureKind=123`, each accompanied by a matching node.
- **Impact:** the resolver returns an actionable element from an envelope whose
  success and completeness were never established; WeChat navigation can then
  click it.
- **Evidence:** `/private/tmp/pr3_selector_query_contract_probe_eb543ec.py`,
  SHA-256
  `d9caf56d2e63ab1893123974f0704becbdf7749ded65692ed2a51c975c8a6519`,
  exit 41: all three contradictory/wrong-type cases returned `resolved`.
  `PRR-039` independently proves missing/falsey malformed truncation reaches
  concrete mutation paths.
- **Required change:** perform presence-sensitive structural validation of the
  query schema, available/status/failure fields, nodes, diagnostics, and
  truncation before normalization. Reject contradictions and malformed or
  incomplete candidate sets instead of applying legacy success inference.
- **Verification:** a producer-to-resolver-to-WeChat matrix must cover absent,
  malformed, contradictory, and version-skewed fields and assert a structured
  failure plus zero action/click/Return; valid legacy shapes need explicit
  positive controls.

## 6. Required Actions Before Merge

- [ ] `PRR-039` - make every root and target strategy fail closed on failed,
  truncated, missing, or malformed completeness evidence; add exact side-effect
  count/order regressions.
- [ ] `PRR-043` - require exactly one structurally valid, in-window search
  target before mutation and remove unbound zero-candidate Return behavior.
- [ ] `PRR-040` - preserve `any_of` presence and reject explicit empty or
  wrong-type lists before override activation.
- [ ] `PRR-041` - reject all non-finite numeric profile values before query or
  resolver construction.
- [ ] `PRR-042` - structurally validate query-result envelopes and reject
  malformed/contradictory success, nodes, diagnostics, and truncation fields.

After these actions, renew the exact-head report, tracked merge-readiness and
PR description, live PR body, and CI snapshot before changing draft state.

## 7. Risk Assessment

| Category | Level | Current risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | **High** | An unverified contact path can reach draft/submit with user text. | Resolve `PRR-039` and `PRR-043`; WeChat maintainer. |
| Data integrity | **High** | Incomplete or hidden-ambiguous candidate sets can select the wrong same-name conversation. | Central target-decision gate and operation-count tests. |
| Reliability & concurrency | **Medium** | Failed/malformed query evidence is reinterpreted as permission to continue. | Resolve `PRR-039` and `PRR-042`. |
| Performance & scalability | **Low** | Current bounds and suite evidence remain intact. | Retain limit/time/depth tests. |
| API & compatibility | **High** | Malformed profiles and version-skewed result envelopes fail open. | Resolve `PRR-040` through `PRR-042`; add positive legacy controls. |
| Deployment & rollback | **Medium** | Live F6 state must be renewed after the next head; release proofs are intentionally incomplete. | Keep draft; refresh lifecycle records only after replacement review. |

## 8. Validation Evidence

All reviewer checks ran from detached exact-head clone
`/private/tmp/mcu-pr3-review-eb543ec.an1bFW/repo`; unrelated primary-worktree
changes were not used.

| Command / check | Result | Exit | Evidence / notes |
|---|---|---:|---|
| Root `unittest discover` | PASS | 0 | 128 tests; includes wheel build/install/API smoke and old dependency rejection. |
| `app-control-protocol` suite | PASS | 0 | 55 tests. |
| `computer-use-macos` suite | PASS | 0 | 158 tests, 1 sandbox socket skip. |
| `wechat-desktop-tool` suite | PASS | 0 | 154 tests. |
| `compileall` | PASS | 0 | External pycache; clone remained clean. |
| `scripts/release_preflight.py` | PASS | 0 | Expected socket/external-release warnings only. |
| `git diff --check fed6523..eb543ec` | PASS | 0 | No whitespace errors. |
| Previous `e86181a` result validator | PASS | 0 | Schema/invariants valid. |
| Current `eb543ec` result validator | PASS | 0 | Schema 1.1 and re-review invariants valid. |
| Exact-head old-blocker revalidation | PASS | 0 | `PRR-026/037/038` counterexamples no longer reproduce; ordinary `PRR-039` control stops. |
| `PRR-039` adversarial matrix | **FAIL** | 9 | Nine unsafe malformed/mixed-root/continuation cases. |
| Profile validation probe | **FAIL** | 31 | Empty `any_of` and `NaN` confidence fail open. |
| Query-result contract probe | **FAIL** | 41 | Three malformed/contradictory envelopes resolve. |
| Search candidate matrix | **FAIL** | 44 | Six unsafe sets reach draft/submit; ambiguity negative control blocks. |
| Offscreen full-send probe | **FAIL** | 41 | Offscreen candidate reaches Return, draft, and submit. |

Exact-head GitHub evidence observed at review completion:

- workflow: `CI / test`
- run/job:
  <https://github.com/zhanghao1903/macos-computer-use/actions/runs/29580279873/job/87884066504>
- conclusion: `SUCCESS`
- completed: `2026-07-17T12:29:47Z`
- remote head: `eb543ec9eb3800de104dadeb5d2fbb1382d14416`
- PR state: open, draft, mechanically mergeable, merge state `CLEAN`

## 9. Coverage and Limitations

- All 19 remediation-delta paths were classified and reviewed; the full
  128-path base-to-head change was reconciled through prior-finding closure and
  fresh public-contract/mutation passes.
- Three independent passes covered old finding closure, public contract and
  profile/query boundaries, and WeChat mutation/side-effect paths. The primary
  reviewer independently ran the decisive probes.
- No live desktop mutation was performed. Deterministic probes exercise the
  exact library call paths and operation order but do not replace an
  authorized release-candidate smoke.
- Signed/notarized helper, TestPyPI/PyPI, and trusted-publisher proof remain F7
  release work, not a reason to weaken the merge blockers.
- This decision expires immediately if base or head changes.
- The report pair is local and is not part of the reviewed snapshot; committing
  it to the PR branch would itself require another exact-head review.

## 10. Open Questions and Assumptions

### Open questions

None changes the request-changes decision.

### Assumptions

| Assumption | Decision-critical | Status | Evidence |
|---|---|---|---|
| Remote base/head and CI stayed fixed through report completion. | true | VERIFIED | Final `gh pr view` returned base `fed6523`, head `eb543ec`, and successful CI job `87884066504`. |
| Deterministic fake/generated-worker paths preserve production library branching and side-effect order. | true | VERIFIED | Probes call the exact `SelectorResolver` and `WeChatDesktopTool` methods; source path and full suite were checked at the same SHA. |
| Existing green tests alone cover malformed and contradictory boundary states. | true | FALSIFIED | Five discriminating probes fail while all configured suites and CI pass. |

## 11. Non-blocking Recommendations

- After the five blockers are closed and independently re-reviewed, run the
  documented read-only selector smoke and a separately authorized WeChat
  mutation smoke before a release candidate.
- Keep profile/result contract matrices table-driven and presence-sensitive so
  empty, falsey, malformed, non-finite, contradictory, and version-skewed
  states cannot disappear during normalization.

## 12. Machine-readable Summary

- Result file: `pr-review-macos-computer-use-3-eb543ec.json`
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.1"
review_kind: RE_REVIEW
decision: REQUEST_CHANGES
mergeable: false
head_sha: eb543ec9eb3800de104dadeb5d2fbb1382d14416
blocking_findings:
  - PRR-039
  - PRR-040
  - PRR-041
  - PRR-042
  - PRR-043
validation_status: FAILED
report_status: CURRENT
```

## 13. Publication State

This is a local read-only review artifact. No GitHub review, approval,
ready-state transition, merge, tag, package publication, or PR-body mutation
was performed.
