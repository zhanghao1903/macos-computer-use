# PR Review - `zhanghao1903/macos-computer-use#3` @ `e86181a`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `zhanghao1903/macos-computer-use` |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `e86181a9c300cd9929d4ce61c08188a1a36f3bb9` |
| Reviewed at | `2026-07-17T04:11:27Z` |
| Reviewer | `Codex (GPT-5)` with three independent parallel review passes |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| GitHub state | `OPEN`, `DRAFT`, mechanically mergeable, merge state `CLEAN` |
| Scope size | 148 commits; 125 local base-to-head changed paths; 51,263 additions; 1,650 deletions |
| Previous authoritative review | `pr-review-macos-computer-use-3-59c6fb5.md` @ `59c6fb5`, `REQUEST_CHANGES` |
| Previous result SHA-256 | `38facf1f681fb79433972c70feb515a5d06310b57a2347549f144bd06eacce49` |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable under this Review Contract:** `false`
- **Blocking findings:** `PRR-023`, `PRR-026`, `PRR-037`, `PRR-038`, `PRR-039`
- **Approval renewal:** `WITHHELD`
- **Independent pass:** `FAIL`
- **Applies only to:** exact head
  `e86181a9c300cd9929d4ce61c08188a1a36f3bb9`

The current head must not be approved, marked ready, or merged. Eleven of the
twelve open blockers from `59c6fb5` are resolved, but `PRR-026` remains
reproducible. A fresh forward-risk pass found three additional code blockers,
and the previously resolved lifecycle finding `PRR-023` has regressed because
the live GitHub body still publishes the obsolete `f19cbd9` approval.

## 3. Executive Summary

The remediation correctly closes most of the previous selector, collection,
configuration, privacy, failure-routing, background-target, and review-result
findings. All package and root suites, compilation, packaging, preflight, and
exact-head GitHub CI pass.

Those green checks do not cover five blocking counterexamples:

1. Legacy explicit-unsupported and pre-dispatch action results can still
   authorize a second mutation while known evidence says `performed`,
   `unknown`, or carries native error `-25204`.
2. A correct WeChat bundle is rejected when its legitimate localized
   `localizedName` differs from the caller's `targetApp` alias.
3. The three operation-specific frontmost-target failure values are emitted but
   absent from the stable public failure registry.
4. Direct WeChat contact-target queries can click or press Return after a
   truncated candidate scan, so unseen duplicate contacts can invalidate the
   uniqueness decision.
5. The live PR body still claims the obsolete `f19cbd9` approval and old CI
   while the tracked lifecycle records and current head say otherwise.

## 4. Re-review Reconciliation

### Snapshot delta

- Previous head: `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- Current head: `e86181a9c300cd9929d4ce61c08188a1a36f3bb9`
- Range:
  `59c6fb59fd08481b07217b9e236d1038bd9736ce..e86181a9c300cd9929d4ce61c08188a1a36f3bb9`
- Delta: six commits, 31 files, 4,759 additions, 600 deletions
- Full PR diff: reconciled against base `fed6523`
- Excluded or unclassified delta files: none

### Track A: prior-finding closure

| Finding | Previous | Current | Current-head proof |
|---|---|---|---|
| `PRR-021` | open | **resolved** | All known proof roots and nested containers are traversed; malformed or conflicting attempt/dispatch copies block fallback. |
| `PRR-026` | open | **open** | Legacy explicit-unsupported and pre-dispatch branches still ignore semantically contradictory effect/code evidence and execute a second click. |
| `PRR-027` | open | **resolved** | Corrected `f19cbd9` and `59c6fb5` results both pass the current schema/invariant validator. |
| `PRR-028` | open | **resolved** | Decision-critical truncation now returns before candidate construction, pick, or cache publication. |
| `PRR-029` | open | **resolved** | Unsupported embedded collection selector semantics are rejected before execution. |
| `PRR-030` | open | **resolved** | Generic selector profile and WeChat control map activate as one validated immutable pair. |
| `PRR-031` | open | **resolved** | Pagination counts accepted semantic records and uses accepted-item lookahead. |
| `PRR-032` | open | **resolved** | Query/action/tree workers no longer enumerate or operate on a background target. |
| `PRR-033` | open | **resolved** | Query/action/observe normal evidence and events use the documented safe projections. |
| `PRR-034` | open | **resolved** | Batch query limits stay at or below 500 and missing entries take bounded per-item fallback. |
| `PRR-035` | open | **resolved** | Structured selector failure cause and truncation precede message heuristics. |
| `PRR-036` | open | **resolved** | The four warm query/action worker failure values are declared, exported, registered, and tested. |
| `PRR-022` | resolved | **resolved** | Native unsupported producers still preserve the exact requested action. |
| `PRR-025` | resolved | **resolved** | `accessibility_action_unsupported` remains in the stable routing tuple. |

### Track B: forward-risk review

| Surface | Result | Findings |
|---|---|---|
| Resolver truncation, cache, collection semantics, pagination, and public limit | **PASS** | Prior `PRR-028/029/031/034` remain resolved. |
| Frontmost application identity and failure propagation | **FAIL** | `PRR-037`, `PRR-038` |
| Atomic WeChat selector assets | **PASS** | Prior `PRR-030` remains resolved. |
| WeChat mutation target selection and no-replay proof | **FAIL** | `PRR-026`, `PRR-039` |
| Normal observability privacy and structured failure routing | **PASS** | Prior `PRR-033/035` remain resolved. |
| Review-result and feature lifecycle evidence | **FAIL** | `PRR-023` reopened; `PRR-027` remains resolved. |

## 5. Findings

### PRR-039 - `[S1][Blocking][High]` Truncated contact-target queries still execute a mutation

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:1233`,
  `:1413`, `:1515`, and `:1608`
- **Category:** correctness / data integrity
- **Observation:** the direct control-map target, visible-row target, and search
  result paths inspect returned candidates and then click, run an
  Accessibility action, or press Return without first rejecting
  `diagnostics.truncated=true`.
- **Trigger:** a bounded or time-limited query returns zero or one matching
  visible contact while reporting truncation; another matching contact was not
  scanned.
- **Impact:** the code treats an incomplete set as unique and can open the wrong
  same-named conversation. Composite draft/send flows can then target the wrong
  recipient even though the generic selector resolver itself is fail-closed.
- **Evidence:** `/private/tmp/pr3_truncated_contact_mutation_probe_e86181a.py`
  (SHA-256
  `06323eedf2277fbbbb13f641dd2487c33d230ca77203be3ea3827a1da692dab6`,
  exit 39) returned success and executed
  `open_app -> observe -> accessibility_query -> accessibility_action ->
  accessibility_query` from a truncated one-candidate response. An independent
  control-map variant likewise executed `click`. Source audit found the same
  missing gate in visible-row and search-result mutation paths; the search
  branch also presses Return when a truncated query returns no parsed
  candidate.
- **Remediation:** centralize a mutation-target query gate that treats any
  decision-critical truncation as `wechat_query_truncated` before candidate
  ranking or action. Do not fall through to Return or another mutation using an
  incomplete candidate set.
- **Verification:** cover zero/one/multiple returned candidates for
  limit/time/depth truncation across all three paths and assert zero click,
  Accessibility action, Return, draft, and submit operations.

### PRR-026 - `[S2][Blocking][High]` Known action evidence still authorizes replay with a contradictory outcome

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4253-4300`
  and `:4527-4570`
- **Category:** reliability / mutation safety
- **Observation:** the consistency helper validates types and duplicate values,
  but it does not validate cross-field meaning. The legacy
  `unsupported_operation` branch returns `true` whenever
  `actionAttempted` is not true; the pre-dispatch branch can also return
  `true` while known effect/code fields contradict “no effect.”
- **Trigger:** an explicit-unsupported or retryable pre-dispatch result includes
  `actionEffect=performed`, `actionEffect=unknown`, or
  `nativeErrorCode=-25204`.
- **Impact:** a first action whose outcome is not proven safe can be followed by
  a coordinate/selector click or Return, violating the documented no-replay
  boundary.
- **Evidence:** `/private/tmp/prr026_legacy_nested_replay_probe_e86181a.py`
  (SHA-256
  `eeec50fb4e357aa7d208c970a5b1fd1167406a0e8e0cd7275ec1ef90ce20ad20`,
  exit 3) produced success with operations
  `["accessibility_action", "click"]` for result-evidence `performed`,
  ToolError-evidence `unknown`, and nested `-25204`. The retained matrix
  `action_evidence_probe_59c6fb5.py` also fails exactly those three cases.
  `/private/tmp/pr3_predispatch_replay_probe_e86181a.py` (SHA-256
  `51f8f9670c22d02c53f0a4567b540ce89399f25bf247a4424cda3fb78a03d947`,
  exit 38) separately proves that
  `requestDispatched=false/actionAttempted=false/actionEffect=performed/-25204`
  executes the same second click.
- **Remediation:** validate the semantic state as one proof: fallback is allowed
  only for a complete definite-no-effect native pair or a proven pre-dispatch
  result with no contradictory attempted/effect/code evidence.
- **Verification:** run every shared fallback caller over absent, malformed,
  contradictory, performed, unknown, wrong-code, retryable, and dispatch
  combinations; every unsafe case must execute exactly one original operation
  and zero fallback mutations.

### PRR-037 - `[S2][Blocking][High]` Correct bundle identity is rejected by a legitimate localized app name

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:3388-3410`
  and `:4217-4236`
- **Category:** correctness / compatibility
- **Observation:** after the frontmost bundle matches, query and action workers
  still require `localizedName == targetApp`. The WeChat adapter always sends
  both values, while the supported profile recognizes both `WeChat` and
  `微信`.
- **Trigger:** `targetApp="WeChat"`,
  `bundleId="com.tencent.xinWeChat"`, and the same frontmost bundle exposes
  localized name `微信`.
- **Impact:** every selector query and Accessibility action fails before
  `AXUIElementCreateApplication`, disabling the default WeChat workflow on a
  supported localization.
- **Evidence:** `/private/tmp/pr3_bundle_precedence_probe_e86181a.py`
  (SHA-256
  `a706926d5bfbd5a4970e4798f6eb7cf77a34c2d5e1204a62a53574c5ff683c88`,
  exit 0) ran the real generated scripts: query returned
  `accessibility_query_target_app_not_frontmost`, action returned
  `target_app_not_frontmost`, and both had `createApplication=0`. The local
  installed app's `zh-Hans.lproj/InfoPlist.strings` declares display name
  `微信`.
- **Remediation:** make an exact requested bundle match authoritative, or pass
  and validate an explicit alias set. Name matching should be the fallback only
  when no bundle was requested, as the design states.
- **Verification:** executable generated-worker tests must cover correct bundle
  plus different supported alias, name-only fallback, wrong bundle, wrong
  name-only target, hidden/terminated app, and no frontmost app.

### PRR-038 - `[S2][Blocking][High]` Frontmost-target failure values bypass the stable public registry

- **Location:** `packages/computer-use-macos/src/computer_use_macos/errors.py:63-109`
  and `client.py:3393-3409,4222-4235,4640-4650`
- **Category:** API contract
- **Observation:** query emits
  `accessibility_query_target_app_not_frontmost`, action emits
  `target_app_not_frontmost`, and tree emits
  `accessibility_tree_target_app_not_frontmost`. None has a constant or entry
  in `COMPUTER_USE_FAILURE_KINDS`; the registered
  `target_not_frontmost` is a different helper value.
- **Trigger:** any new frontmost guard rejects a missing, hidden, terminated,
  bundle-mismatched, or name-mismatched target.
- **Impact:** public consumers using the advertised stable tuple cannot
  exhaustively route real package-owned failures and may treat them as unknown.
- **Evidence:** `/private/tmp/pr3_target_failure_registry_probe_e86181a.py`
  (SHA-256
  `5fbce30d1695bb89c97d2ab32a09c2f115b4c84fa62fecc4dd6c0a79f52a0962`,
  exit 0) proved the query/action values become top-level observations with
  registry membership `false`; source propagation proves the tree value is
  published as `accessibility.treeFailureKind`. The existing registry regex
  does not inspect literals embedded in generated worker scripts.
- **Remediation:** choose a canonical public contract—normalize all three to
  `TARGET_NOT_FRONTMOST`, or declare/export/register the operation-specific
  values—and synchronize docs, consumers, and producer-to-observation tests.
- **Verification:** execute the real generated producers and assert every
  caller-visible package-owned failure is declared once, importable from the
  wheel, documented, and registry-routable.

### PRR-023 - `[S2][Blocking][High]` F6 platform records again publish obsolete review state

- **Location:** live GitHub PR body and
  `docs/feature/accessibility-selector-engine/pr-description.md`
- **Category:** documentation / lifecycle
- **Observation:** the live PR body still says the implementation and approval
  are current at `f19cbd9`, all `PRR-021/022/025/026` findings are resolved,
  and CI run `29463591047` is authoritative. The actual PR head is
  `e86181a`; the tracked description instead records the later `59c6fb5`
  request-changes state and exact-head remediation verification.
- **Trigger:** a maintainer or automation uses the canonical PR body to decide
  readiness, approval, or merge.
- **Impact:** the platform and repository publish contradictory decisions,
  finding ledgers, and CI evidence, breaking the auditable F6 lifecycle gate.
- **Evidence:** fresh `gh pr view` returned head `e86181a`, exact-head CI run
  `29519769061`, and the obsolete `f19cbd9` body. The tracked
  `pr-description.md` is 8,158 bytes with SHA-256
  `a0aad7b42a03e9e1e1b8d906d721d80f1141f0f7dbadc68cda707596bec18a7c`
  and is not the live body.
- **Remediation:** after code findings are fixed and re-reviewed, synchronize
  merge-readiness, the tracked PR description, the live GitHub body, finding
  ledger, current decision, and exact-head CI before changing draft state.
- **Verification:** all three F6 surfaces agree byte-for-byte where applicable
  on the current snapshot, findings, decision, behavior, and CI.

## 6. Required Actions

- [ ] `PRR-039` - reject every truncated contact-target query before click,
  Accessibility action, Return, draft, or send; add all-path operation-count
  regressions.
- [ ] `PRR-026` - make fallback proof semantically coherent, not merely
  type/duplicate consistent; prove zero replay for performed/unknown/wrong-code
  and contradictory pre-dispatch evidence.
- [ ] `PRR-037` - restore bundle-first identity semantics and cover supported
  localized aliases in executable generated-worker tests.
- [ ] `PRR-038` - normalize or publicly register all three frontmost-target
  failures and test real producer-to-wheel propagation.
- [ ] `PRR-023` - synchronize tracked F6 records and the live GitHub body only
  after the code fixes and replacement review are current.

## 7. Risk Assessment

| Category | Level | Current risk | Mitigation / owner |
|---|---|---|---|
| Data integrity and privacy | **High** | A truncated target set can be treated as unique and open the wrong same-named conversation. | Resolve `PRR-039`; WeChat tool maintainer. |
| Reliability and mutation safety | **High** | Contradictory action evidence can authorize a second mutation. | Resolve `PRR-026`; WeChat tool maintainer. |
| Compatibility | **Medium** | Supported localized app names are rejected despite an exact bundle match. | Resolve `PRR-037`; computer-use maintainer. |
| Public API | **Medium** | Real package-owned target failures are absent from the stable tuple. | Resolve `PRR-038`; package maintainer. |
| Deployment/governance | **Medium** | Live and tracked F6 state disagree. | Resolve `PRR-023`; PR maintainer. |
| Release | **Medium residual** | Signed helper, notarization, and publication were not exercised. | Keep as separate F7 gates; release maintainer. |

## 8. Validation Evidence

All local checks ran from detached exact-head clone
`/private/tmp/mcu-pr3-review-e86181a.x9ABDZ`; unrelated primary-worktree
changes were not used.

| Check | Result |
|---|---|
| Root `unittest discover` | **PASS** - 127 passed |
| `app-control-protocol` suite | **PASS** - 55 passed |
| `computer-use-macos` suite | **PASS** - 155 passed, 1 skipped |
| `wechat-desktop-tool` suite | **PASS** - 149 passed |
| Focused selector/frontmost/registry tests | **PASS** - 10 passed, 145 deselected |
| Focused WeChat atomicity/privacy/no-replay/routing tests | **PASS** - 12 passed, 132 deselected |
| Compileall | **PASS** |
| Release preflight | **PASS** - expected socket/external-release warnings only |
| Three-wheel build/install/API checks | **PASS** through the root suite |
| Historical `f19cbd9` result validator | **PASS / VALID** |
| Previous `59c6fb5` result validator | **PASS / VALID** |
| Current `e86181a` result validator | **PASS / VALID** |
| `git diff --check fed6523..e86181a` | **PASS** |
| PRR-026 legacy proof matrix | **FAIL** - 3 unsafe cases |
| PRR-026 end-to-end operation probe | **FAIL** - all 3 cases executed a second click |
| Bundle/name precedence generated-worker probe | **FAIL** - correct bundle rejected twice |
| Target failure registry probe | **FAIL** - emitted query/action values unregistered |
| Truncated contact-target mutation probe | **FAIL** - truncated candidate was clicked |

Exact-head GitHub evidence observed at review time:

- workflow: `CI / test`
- run:
  <https://github.com/zhanghao1903/macos-computer-use/actions/runs/29519769061>
- job:
  <https://github.com/zhanghao1903/macos-computer-use/actions/runs/29519769061/job/87693668474>
- conclusion: `SUCCESS`
- remote head: `e86181a9c300cd9929d4ce61c08188a1a36f3bb9`
- PR state: open, draft, mechanically mergeable, merge state `CLEAN`

## 9. Coverage, Limitations, and Open Questions

- All 31 remediation-delta paths were classified; the full 125-path
  base-to-head diff was reconciled.
- Three independent passes covered previous-finding closure, computer-use
  selector/worker forward risk, and WeChat/lifecycle forward risk; the primary
  reviewer independently reproduced the blocking counterexamples.
- No live desktop mutation was performed. Generated-worker and SDK
  counterexamples are deterministic; a real WeChat smoke remains release
  evidence, not a substitute for fixing these merge blockers.
- Signed/notarized helper execution and TestPyPI/PyPI/trusted-publisher proof
  remain F7 release work.
- Ruff is unavailable and repository-wide strict mypy has no accepted clean
  baseline; neither is a configured CI gate.
- This decision expires immediately if base or head changes.
- The report pair is not part of the reviewed snapshot; committing it to the PR
  branch would itself require exact-head approval renewal.
- No open question changes the current `REQUEST_CHANGES` decision.

## 10. Non-blocking Recommendations

- After the five blockers are closed and independently re-reviewed, run the
  documented read-only selector smoke and separately authorized WeChat mutation
  smoke before publishing a release candidate.
- Keep the PR draft until tracked lifecycle state, live PR body, replacement
  report, and exact-head CI agree.

## 11. Publication State

This is a local read-only review artifact. No GitHub review, approval,
ready-state transition, merge, tag, or package publication was performed.
