# PR Review - `zhanghao1903/macos-computer-use#3` @ `d2dadd0`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `d2dadd06e0b78f36364abbdf00fd0e988f5ab5a5` |
| Reviewed at | 2026-07-15T00:59:39Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT`; supersedes the `d20636c` report |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanically `MERGEABLE`, merge state `CLEAN` |
| Scope size | 123 commits; 110 changed files; 40,362 additions; 1,466 deletions |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` under this Review Contract
- **Open blocking findings:** `PRR-022`, `PRR-023`
- **Resolved finding revalidated:** `PRR-021`
- **Rationale:** The no-replay repair works for genuinely unknown dispatched
  outcomes, but it also classifies Apple's definite
  `kAXErrorActionUnsupported` result (`-25206`) as an unknown attempted action.
  That suppresses the one fallback deliberately retained for WeChat rows that
  reject `AXPress`. The F6 merge-readiness and PR descriptions also publish
  obsolete SHAs, finding state, test counts, and decision data.

The PR was not merged and no GitHub review was published.

## 3. Executive Summary

The focused `PRR-021` implementation correctly prevents a second desktop
mutation after EOF, timeout, malformed response, native unknown failure, or
missing dispatch evidence. Root and package suites, stress checks, release
preflight, and exact-head CI are green.

The same change regresses a known compatibility path. The macOS SDK defines
`-25206` as an unsuccessful request because the element does not support the
action, yet the client emits generic `accessibility_action_failed` with
`actionAttempted=true`; WeChat then refuses the safe unsupported-action
fallback. Existing tests were changed to assert that failure even though an
earlier feature commit and the changelog promise fallback when an `AXRow`
rejects `AXPress`. The implementation must distinguish definite unsupported
results from uncertain outcomes, then the canonical F6 records and GitHub PR
body must be synchronized before another merge review.

## 4. Scope and Change Map

### Reviewed scope

- frozen base/head SHAs, complete PR metadata, changed-file list, commit list,
  draft/merge state, and exact-head GitHub CI;
- the four-commit `3392c27...d2dadd0` review/remediation delta (12 files,
  2,062 additions, 53 deletions) and its `b8d4bbd` code change;
- macOS action-worker dispatch evidence, native result construction,
  retryability propagation, and generated PyObjC action script;
- all WeChat mutating fallback callers and the shared recovery predicate;
- Apple's installed macOS 26.5 SDK AX error definitions and function contract;
- the earlier `303b9b4` AXRow fallback contract, current changelog, stable API
  docs, tests, F6 records, and GitHub PR body;
- isolated exact-head root/package tests, targeted regressions, stress,
  compilation, release preflight, whitespace, and CI.

### Excluded scope

- a fresh real WeChat action or message submission;
- post-submit delivery read-back and repeated live latency percentiles;
- signed/notarized helper execution and real TestPyPI/PyPI publication;
- private raw smoke artifacts and unrelated dirty worktree files;
- Ruff and mypy, which are unavailable and are not configured CI gates.

### Change map

| Area | Main change or observation | External behavior | Risk | Validation |
|---|---|---|---|---|
| Unknown-outcome recovery | One predicate consumes attempt, dispatch, retryability, and unsupported evidence. | EOF, timeout, malformed, unknown, and native uncertain outcomes stop before another mutation. | Low | Cross-package unsafe outcomes, path tests, package suites, and CI pass. |
| Native AX errors | Every non-zero native AX result becomes generic attempted failure. | Definite unsupported and uncertain outcomes are indistinguishable. | Medium | SDK constants plus a failing compatibility assertion reproduce the defect. |
| AXRow compatibility | Rows may publish `AXPress` actionRefs even when WeChat later rejects the native action. | `-25206` now stops instead of using the configured coordinate/selector/Return fallback. | Medium | Current fixture and changed tests demonstrate the regression. |
| F6 lifecycle state | Canonical tracked and platform descriptions remain bound to old reviews. | Maintainers see contradictory merge decisions and evidence. | Medium | File history and live PR metadata were compared with `d2dadd0`. |
| Packaging/release | No version, dependency, command, or schema version changed in the focused delta. | Package boundaries remain intact. | Low | Preflight, package suites, distributions in CI, and diff checks pass. |

## 5. Findings

### PRR-022 - `[S2][Blocking][Correctness/Compatibility]` Definite unsupported AX actions are treated as unknown mutations

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:4373-4385` and `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4133-4162` @ `d2dadd06e0b78f36364abbdf00fd0e988f5ab5a5`
- **Confidence:** High
- **Status:** open
- **Observation:** The client maps every non-zero result from
  `AXUIElementPerformAction` or `AXUIElementSetAttributeValue` to
  `accessibility_action_failed` and `actionAttempted=true`. The WeChat predicate
  checks positive attempt evidence before it recognizes unsupported failures,
  so this result cannot use a fallback. The current test fixture uses error
  `-25206` for this supposedly unknown native failure.
- **Trigger:** A verified WeChat `AXRow` is offered as an `AXPress` target, but
  `AXUIElementPerformAction` returns `kAXErrorActionUnsupported` (`-25206`).
- **Impact:** Contacts/navigation/search flows can fail instead of executing
  the one current-frame, identity-gated fallback built for WeChat rows that
  omit or reject `AXPress`. This regresses the behavior introduced by
  `303b9b4` and promised in `CHANGELOG.md:85-87`.
- **Evidence:**
  - the installed macOS 26.5 SDK defines
    `kAXErrorActionUnsupported = -25206` and documents it as an unsuccessful
    call because the element does not support the action;
  - the same SDK explicitly distinguishes `kAXErrorCannotComplete` (`-25204`),
    whose action outcome may be uncertain, from the unsupported result;
  - `test_tool.py:928-958` constructs `-25206` with positive attempt/dispatch
    evidence, while `test_tool.py:1876-1904` now asserts that contact
    navigation stops without a click;
  - a reviewer assertion that `-25206` retains one safe fallback failed with
    exit code 1 because the current predicate returned `false`;
  - commit `303b9b4` added AXRow actionRefs and fallback specifically for this
    observed WeChat behavior; `b8d4bbd` changed the previous success test into
    a failure expectation instead of separating definite unsupported from
    uncertain native errors.
- **Required change:** Preserve fail-closed handling for `-25204`, lost
  responses, malformed responses, and other uncertain outcomes, but propagate
  a machine-readable definite-unsupported/no-effect result for `-25206` and
  allow exactly one configured fallback. Evaluate the equivalent
  `AXSetFocus`/`kAXErrorAttributeUnsupported` (`-25205`) case under the same
  contract.
- **Verification:** Add cross-package tests proving `-25206` (and any adopted
  definite unsupported focus result) executes exactly one fallback, while
  `-25204`, EOF, timeout, malformed, contradictory, and missing evidence execute
  zero downstream mutations. Rerun all package/root/preflight and exact-head CI
  gates.

### PRR-023 - `[S2][Blocking][Documentation/Lifecycle]` F6 merge records publish obsolete review state

- **Location:** `docs/feature/accessibility-selector-engine/merge-readiness.md:3-16` @ `d2dadd06e0b78f36364abbdf00fd0e988f5ab5a5`
- **Confidence:** High
- **Status:** open
- **Observation:** `merge-readiness.md` and tracked `pr-description.md` still
  make `ba733dc`, `PRR-001` through `PRR-020`, and CI run `29342939601`
  authoritative. The GitHub PR body is older still: it reports
  `REQUEST_CHANGES` at `07fa052` with 12 blockers and old test counts. The
  current head is `d2dadd0`, `PRR-021` was fixed and revalidated, and current CI
  is run `29359074400`.
- **Trigger:** A maintainer uses the canonical F6 artifacts or GitHub body to
  change draft state, approve, or merge the PR.
- **Impact:** The repository and platform present mutually incompatible merge
  decisions, finding ledgers, and verification evidence. This breaks the
  auditable merge-readiness contract and violates the feature-lifecycle rule
  that F6 review/description updates be committed and pushed before merge.
- **Evidence:** Both tracked F6 files were last updated in `3392c27`, before
  the four PRR-021 finding/fix/evidence/report commits; the `d20636c` report
  itself says the GitHub body is obsolete and requires synchronization before
  changing draft state; current GitHub metadata shows exact head `d2dadd0`,
  draft/open/clean state, and successful exact-head CI.
- **Required change:** After `PRR-022` is fixed, synchronize
  `merge-readiness.md`, tracked `pr-description.md`, and the GitHub PR body with
  the current finding ledger, behavior contract, test counts, review decision,
  and CI. Commit and push the F6 update and observe new exact-head CI.
- **Verification:** The three canonical surfaces agree on the implementation
  snapshot, open/resolved findings, decision, public behavior, and current CI;
  the replacement report is bound to the resulting review snapshot.

### PRR-024 - `[S3][Non-blocking][API Contract]` Unsupported-action recovery documentation is internally contradictory

- **Location:** `docs/api.md:251-258` and `docs/wechat-desktop-tool.md:460-468` @ `d2dadd06e0b78f36364abbdf00fd0e988f5ab5a5`
- **Confidence:** High
- **Status:** open
- **Observation:** Each section first permits an explicit unsupported action
  without positive attempt evidence, then says `requestDispatched=true` or
  `retryable=false` always stops recovery. The current synthetic unsupported
  worker result has both values while the predicate intentionally permits its
  fallback.
- **Trigger:** A developer interprets the documented recovery contract or a
  maintainer adds another backend result shape.
- **Impact:** Readers can implement the opposite precedence rule or incorrectly
  diagnose valid recovery. Runtime behavior is not changed by the prose alone.
- **Evidence:** The stable docs conflict within adjacent sentences;
  `implementation-notes.md:4032-4038` contains the intended unsupported
  exception; the exact-head unsupported cross-package test permits one
  fallback.
- **Remediation:** State explicitly whether definite unsupported/no-effect
  evidence overrides dispatch and retryability, and use the same precedence in
  both stable documents after resolving `PRR-022`.
- **Verification:** Documentation assertions and cross-package examples agree
  with the final predicate for unsupported, uncertain, pre-dispatch, and
  contradictory outcomes.

### PRR-021 - `[S1][Resolved][Reliability/Safety]` Downstream actions could replay after dispatched or unknown outcomes

- **Status:** resolved and revalidated at `d2dadd0`.
- **Evidence:** EOF, post-dispatch timeout, malformed response, unknown
  dispatch, and uncertain native failure make no second mutation; explicit
  pre-dispatch and synthetic unsupported cases retain one fallback; all mapped
  navigation, contact, search, selector, Return, coordinate, and strategy paths
  use the shared predicate.

`PRR-001` through `PRR-021` otherwise remain resolved for this snapshot.

## 6. Required Actions Before Merge

- [ ] `PRR-022` - distinguish definite unsupported/no-effect native results
  from uncertain attempted outcomes and add cross-package fallback/no-replay
  regressions.
- [ ] `PRR-023` - synchronize and push the F6 merge-readiness record, tracked
  PR description, and GitHub PR body after the code fix, then obtain exact-head
  green CI and re-review.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | Private desktop logs can contain transient UI text. | Keep raw artifacts untracked and publish bounded semantic proof only. / feature maintainer |
| data-integrity | Low | A genuinely dispatched action can still have an unknown desktop outcome. | Preserve PRR-021's fail-closed path for uncertain results. / both package owners |
| reliability-concurrency | Medium | Definite unsupported and uncertain native errors currently share one recovery class. | Implement PRR-022 with explicit error semantics and cross-package tests. / both package owners |
| performance-scalability | Low | One worker serializes Accessibility actions. | Keep the bounded deadline and timing diagnostics. / computer-use-macos |
| api-compatibility | Medium | WeChat rows that reject AXPress lose their documented fallback. | Restore only definite no-effect fallback; never retry an uncertain outcome. / wechat-desktop-tool |
| deployment-rollback | Low | Recovery semantics change across normal WeChat action paths. | No migration exists; revert the focused recovery commit if necessary. / feature maintainer |
| maintainability | Medium | F6 truth is split across stale tracked and platform descriptions. | Resolve PRR-023 and keep one current finding ledger. / feature maintainer |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root unittest discovery | clean isolated `d2dadd0`; Darwin 25.5.0 arm64; CPython 3.12.7 | PASS | 0 | 127 tests passed in 51.802 s. |
| Protocol package | same isolated clone | PASS | 0 | 55 tests passed in 0.011 s. |
| macOS package, `ResourceWarning` as error | same isolated clone | PASS | 0 | 141 tests passed in 1.539 s; one sandbox socket skip; no warning failure. |
| WeChat package, `ResourceWarning` as error | same isolated clone | PASS | 0 | 132 tests passed in 0.829 s. |
| Eleven PRR-021 path/cross-package regressions | same isolated clone | PASS | 0 | 11 tests passed in 0.475 s. |
| Unsafe cross-package test repeated ten times | same isolated clone | PASS | 0 | 10/10 passes; 40 EOF/timeout/malformed/native-failure subcases; zero replay. |
| Prior PRR-021 counterexample | same isolated clone | PASS | 0 | One `AXPress`, `requestDispatched=true`, `retryable=false`, and no runner/fallback call. |
| Installed SDK error constants | local macOS 26.5 SDK and PyObjC | PASS | 0 | `kAXErrorActionUnsupported == -25206`; `kAXErrorCannotComplete == -25204`; `kAXErrorAttributeUnsupported == -25205`. |
| Definite-unsupported compatibility assertion | same isolated clone | **FAIL** | 1 | Current predicate returned false for the repository's `-25206` fixture; expected exactly one safe fallback. |
| Compile all Python sources | same isolated clone with external pycache | PASS | 0 | Package, example, script, and test sources compiled. |
| Release preflight | same isolated clone | PASS | 0 | Mandatory gates passed; expected one socket and seven external-proof warnings remained. |
| Diff/whitespace/clean-tree checks | same isolated clone | PASS | 0 | `git diff --check` passed and isolated worktree remained clean. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| CI / test - run 29359074400, job 87174203802 | 2026-07-15T00:59:39Z | PASS | Exact head `d2dadd0`; configured tests, preflight, package, wheel, sdist, and content checks passed. |

### Checks not run

- **Fresh real WeChat action or send:** deterministic workers and the SDK error
  contract reproduce the blocker without risking a desktop mutation.
- **Post-submit delivery read-back:** outside this recovery review.
- **Signed helper and real release publication:** later F7 external gates.
- **Ruff and mypy:** unavailable and not configured CI gates.

Overall validation status is `FAILED`: configured tests and CI pass, but a
reviewer semantic compatibility assertion exposes `PRR-022`, and F6 lifecycle
validation exposes `PRR-023`.

## 9. Coverage and Limitations

- This report is authoritative only for head
  `d2dadd06e0b78f36364abbdf00fd0e988f5ab5a5`; later code or behavior changes
  require re-review.
- `d20636c...d2dadd0` adds only the previous review report, so code analysis is
  anchored to `b8d4bbd` and exact-head CI/tests confirm the same implementation.
- No fresh live desktop mutation, signed helper, or publication was performed.
- The macOS SDK contract and repository's own `-25206` fixture are sufficient
  to reproduce the compatibility defect without live WeChat.
- Private raw observations and unrelated dirty worktree files were excluded.

## 10. Open Questions and Assumptions

### Open questions

1. Should `AXSetFocus` map `kAXErrorAttributeUnsupported` (`-25205`) into the
   same definite no-effect class, or use a distinct normalized failure kind?

### Assumptions

1. Apple's documented `kAXErrorActionUnsupported` result means the requested
   action was not supported and the call was unsuccessful; it is safe to use
   the already policy-gated single fallback.
2. `kAXErrorCannotComplete`, transport loss, and missing/contradictory evidence
   remain outcome-unknown and must never trigger another mutation.
3. The existing AXRow fallback and changelog entry are part of the intended
   compatibility contract.
4. Feature-lifecycle F6 records must agree and be pushed before merge.

## 11. Non-blocking Recommendations

- `PRR-024` - clarify unsupported-result precedence in both stable API
  documents while implementing `PRR-022`.
- **NOTE-017 [documentation]** Expand the `Unreleased` record to name the warm
  action worker and dispatch/attempt-aware downstream recovery. The existing
  selector-engine release record satisfies the current MR gate, so this does
  not independently block merge.
- **NOTE-018 [testing]** Replace the misleading `-25206` unknown-failure fixture
  with `kAXErrorCannotComplete` (or another explicitly uncertain result) so a
  no-replay regression cannot accidentally encode the opposite compatibility
  contract again.

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-d2dadd0.json`](./pr-review-macos-computer-use-3-d2dadd0.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: REQUEST_CHANGES
mergeable: false
blocking_findings:
  - PRR-022
  - PRR-023
resolved_findings:
  - PRR-001..PRR-021
validation: FAILED
```
