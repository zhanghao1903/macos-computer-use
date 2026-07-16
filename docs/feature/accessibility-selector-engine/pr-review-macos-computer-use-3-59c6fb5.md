# PR Review - `zhanghao1903/macos-computer-use#3` @ `59c6fb5`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `zhanghao1903/macos-computer-use` |
| Pull Request | [#3 - Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `59c6fb59fd08481b07217b9e236d1038bd9736ce` |
| Reviewed at | `2026-07-16T14:14:49Z` |
| Reviewer | `Codex (GPT-5)` |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| GitHub state | `OPEN`, `DRAFT`, mechanically mergeable, merge state `CLEAN` |
| Scope size | 142 commits; 123 changed files; 47,018 additions; 1,564 deletions |
| Previous authoritative review | `pr-review-macos-computer-use-3-1e56b00.md` @ `1e56b00`, `REQUEST_CHANGES` |
| Previous result integrity | `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-1e56b00.json`, SHA-256 `e5a26ab93c56e63a29b270ffbb2628789416503bda89c988a6c99e9d3c726218` |
| Supersedes | The invalid `f19cbd9` approval and the uncommitted earlier `59c6fb5` approval draft |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable under this Review Contract:** `false`
- **Blocking findings:** 12 (`PRR-021`, `PRR-026`-`PRR-036`, excluding resolved `PRR-022` and `PRR-025`)
- **Approval renewal:** `WITHHELD`
- **Independent pass:** `FAIL`
- **Rationale:** `PRR-022` is resolved and `PRR-025` remains resolved, but
  current-head counterexamples reproduce twelve blockers spanning action proof,
  selector/collection correctness, target selection, privacy, compatibility,
  failure routing/registry, configuration, and report integrity.

The PR was not approved, marked ready, or merged.

## 3. Executive Summary

This PR adds an internal Accessibility selector engine and uses it in WeChat
semantic workflows. The latest seven-commit delta repairs the native action
producer and direct expected-action binding, adds tests and documentation, and
publishes an approval. Those changes close `PRR-022` and preserve `PRR-025`.

Approval nevertheless remains blocked at exact head `59c6fb5`. Known
diagnostics and protocol evidence can still contradict the no-replay proof
without stopping a second mutation. Selector/collection paths can resolve
truncated data, ignore accepted steps, paginate raw instead of semantic items,
and exceed the public query limit. A background target can receive AXPress;
private AX content escapes into normal evidence/events/logs; structured
failures are misrouted; four emitted worker failures are absent from the stable
registry; overrides activate non-atomically; and the committed `f19cbd9`
approval artifact is invalid. The author must resolve all twelve findings,
push a new head, obtain exact-head CI, and request another re-review.

## 4. Scope and Change Map

### Reviewed scope

- exact `1e56b0086b2d996124d5c60db5723eb98ac29ec0..59c6fb59fd08481b07217b9e236d1038bd9736ce`
  delta: seven commits, 16 changed paths, 2,834 insertions and 226 deletions;
- all prior finding closures at the current head;
- native worker -> `ComputerUseClient` normalization -> WeChat recovery and
  every shared fallback caller;
- full base-to-head selector resolver, collection extractor/pagination,
  profile validation, optional overrides, cache/worker behavior, frontmost-app
  enforcement, evidence privacy, failure routing/registry, and mutation consumers;
- review-result chain, lifecycle status, live PR body, exact-head CI, package
  tests, preflight, and compilation.

### Excluded or unavailable scope

- fresh real WeChat or macOS Accessibility mutation;
- signed/notarized helper execution and TestPyPI/PyPI publication;
- private raw desktop observations and unrelated dirty primary-worktree files;
- repository-wide strict-mypy cleanup.

### Re-review reconciliation

| Previous report | Previous base/head | Previous decision | Current base/head | Delta | Old decision state |
|---|---|---|---|---|---|
| `pr-review-macos-computer-use-3-1e56b00.md` | `fed6523` / `1e56b00` | `REQUEST_CHANGES` | `fed6523` / `59c6fb5` | seven commits, 16 paths | `SUPERSEDED` |

Delta commits reviewed:

- `cdcbd47f1780fd1d08fb8c371a1db0e1f035e4cc`
- `b4026eef0b91944e51eebea1a1e2326e7b8dfadb`
- `da4e011d760cb2121e9efa12f91408e1a30fd8c3`
- `65f8855767971f864154c6173f134c6d03fea37b`
- `f19cbd9118c30ced9a3812d9829a3b7e6fbd3592`
- `412a2d380caafff4bf7573a5908ffe9ab88328ca`
- `59c6fb59fd08481b07217b9e236d1038bd9736ce`

Delta files reviewed:

- `docs/api.md`
- `docs/feature/accessibility-selector-engine/design.md`
- `docs/feature/accessibility-selector-engine/implementation-notes.md`
- `docs/feature/accessibility-selector-engine/implementation-plan.md`
- `docs/feature/accessibility-selector-engine/merge-readiness.md`
- `docs/feature/accessibility-selector-engine/pr-description.md`
- `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-1e56b00.json`
- `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-1e56b00.md`
- `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-f19cbd9.json`
- `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-f19cbd9.md`
- `docs/feature/accessibility-selector-engine/verification.md`
- `docs/wechat-desktop-tool.md`
- `packages/computer-use-macos/src/computer_use_macos/client.py`
- `packages/computer-use-macos/tests/test_package.py`
- `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py`
- `packages/wechat-desktop-tool/tests/test_tool.py`

No delta file was excluded or left unclassified. The full base-to-head diff is
reconciled through the prior ledger plus this review's independent risk audit.

### Finding closure ledger

| Finding | Previous | Current | Current-head evidence | Negative regression |
|---|---|---|---|---|
| `PRR-021` | open | **open** | Direct payload parsing improved, but diagnostics/transport/protocol evidence remain outside the proof collector. | Real worker-to-client-to-WeChat path executes `accessibility_action -> click`. |
| `PRR-022` | open | **resolved** | Generated failures now carry action through normalization. | Both native action/code pairs preserve exactly one fallback. |
| `PRR-025` | resolved | **resolved** | Stable failure tuple still declares the emitted value. | Package and preflight tests pass. |
| `PRR-026` | open | **open** | Direct response action is bound to the request, but known nested copies are ignored. | `diagnostics.action=AXSetFocus` does not block an `AXPress` fallback. |

### Change map and forward-risk surfaces

| Surface | Main change | Risk triggers | Discriminating checks | Result |
|---|---|---|---|---|
| Action proof and shared fallbacks | Producer action/effect/code plus strict recovery proof | trust boundary, mutation recovery, data integrity | real worker normalization; nested/evidence contradiction matrix; operation count/order | **FAIL** (`PRR-021`, `PRR-026`) |
| Selector resolver | bounded multi-step resolution, picking, cache | state transition, mutation target, truncation | candidate-present truncated query and cache inspection | **FAIL** (`PRR-028`) |
| Collection extraction | item/field selectors, batching, pagination | public config contract, data integrity, compatibility | two-step decoy; rejected-leading rows; maximum-page batch through real normalizer | **FAIL** (`PRR-029`, `PRR-031`, `PRR-034`) |
| Optional WeChat override | selector profile and control map from one path | configuration trust boundary, fast-path mutation | half-valid override in both parsers | **FAIL** (`PRR-030`) |
| Frontmost target selection | generated bundle/name query/action worker | trust boundary, mutation target | different actual frontmost app plus usable background target | **FAIL** (`PRR-032`) |
| Evidence and event privacy | low-level Accessibility observations in normal selector/control-map channels | privacy, observability, semantic output boundary | canary beyond semantic limit in evidence/events/default redacted logger | **FAIL** (`PRR-033`) |
| Failure routing and registry | structured selector failures and warm-worker failures | public API, compatibility, recovery | adversarial cause/message matrix; producer-to-normalizer registry check | **FAIL** (`PRR-035`, `PRR-036`) |
| Review/lifecycle publication | committed approval and F6 status | evidence integrity, deployment governance | schema/invariant validator, hashes, range, head binding | **FAIL** (`PRR-027`) |

### Approval-renewal gate

- [x] Old decision invalidated
- [x] Previous findings revalidated at current head
- [x] Forward-risk review completed
- [x] All delta changes classified and full PR diff reconciled
- [x] Decision-critical assumptions verified
- [x] Current-head validation and CI observed
- [ ] No open blocker
- **Independent pass:** `FAIL` - independent action-safety, forward-risk,
  cache/concurrency, lifecycle, and protocol/privacy passes reproduced the open
  gaps and found the new blockers; the primary reviewer reran the decisive
  privacy and registry probes.

## 5. Findings

### PRR-021 - `[S1][Blocking][reliability]` Known diagnostics and protocol evidence are excluded from the no-replay proof

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4247-4320`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** `_accessibility_action_proof_payloads()` reads result
  metadata, observation, observation metadata, and one nested action mapping.
  It does not add diagnostics, diagnostics transport, `ToolObservation.evidence`,
  or `ToolError.evidence` to attempted/action/effect/code consistency checks.
  The dispatch helper separately recognizes `diagnostics.transport`, proving
  this is a known container rather than an arbitrary extension.
- **Trigger:** Direct payloads contain a valid-looking unsupported proof while a
  known diagnostics/evidence copy says `actionAttempted=false`, conflicts, or
  is malformed.
- **Impact:** A semantic operation can execute `accessibility_action` and then
  click, Return, focus, or another strategy despite contradictory evidence
  about the first outcome.
- **Evidence:**
  - `/private/tmp/action_evidence_e2e_probe_59c6fb5.py` (SHA-256
    `c72836691bfcbbfe0ae81d5a2e2584b7ea4a87fd880537d76a570e0ca36a974c`)
    exited 1 after reporting `result_success True` and operations
    `['accessibility_action', 'click']` while raw diagnostics said
    `actionAttempted=false` and `requestDispatched=true`.
  - Code: `tool.py:4247-4320,4389-4420`.
  - Contract: `design.md:1317-1340` and
    `docs/wechat-desktop-tool.md:460-486`.
- **Required change:** Traverse every supported public, metadata, nested action,
  diagnostics, transport, and protocol evidence container with one
  presence-sensitive fail-closed model.
- **Verification:** For every known container and shared caller, malformed or
  contradictory attempt/dispatch evidence must stop after
  `accessibility_action`. Only valid pre-dispatch or exact definite-no-effect
  cases may perform one fallback.

### PRR-028 - `[S1][Blocking][correctness]` A truncated selector query can still resolve and cache a candidate

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py:210-334`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** The resolver records `truncated=true` but continues through
  pick, cache update, and `status=resolved` whenever any candidate exists.
  `selector_query_truncated` is returned only when no candidate is picked.
- **Trigger:** A bounded query returns one matching node and truncates before
  all candidates are observed.
- **Impact:** A hidden candidate may score higher or create ambiguity. The
  returned and cached element can therefore receive the wrong `AXPress`, focus,
  or semantic action.
- **Evidence:**
  - `/private/tmp/pr3-forward-risk-counterexamples.py` (SHA-256
    `d6072ab8f1668fa3855e5b22379337ab855772574d0b0e5945954f6c43738e65`)
    printed `truncated-selector resolved 0/2 True None`.
  - Code: `resolver.py:210-216,250-334`.
  - Contract: `design.md:854-864` permits partial output only under an
    explicit policy.
- **Required change:** Fail closed before pick/cache for decision-critical
  truncation unless an explicit reviewed policy proves partial selection safe;
  never cache an unsafe truncated selection.
- **Verification:** Cover time/limit truncation, hidden higher-score/duplicate
  candidates, all pick strategies, and cache state. Unsafe cases return
  `selector_query_truncated` with no mutation.

### PRR-026 - `[S2][Blocking][reliability]` Known nested action copies are not bound to the requested action

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:4257-4320`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** The direct response action is now compared with
  `expected_action`, but action, effect, and native-code copies in diagnostics,
  transport, and protocol evidence are not part of that comparison.
- **Trigger:** An `AXPress` request has valid direct `AXPress/-25206` proof but
  `diagnostics.action=AXSetFocus`, `actionEffect=performed`,
  `nativeErrorCode=-25204`, or an equivalent evidence conflict.
- **Impact:** A known contradictory response can authorize a second mutation.
- **Evidence:**
  - `/private/tmp/action_evidence_probe_59c6fb5.py` (SHA-256
    `5586186c8396d6d892d803ad203ef1655e11ec6b5b06db1cc16599e30e11bc20`)
    exited 19: direct payload checks passed, but 19 nested/evidence
    contradictions were ignored.
  - An end-to-end `AXPress` request with
    `diagnostics.action=AXSetFocus` still reached `click`.
  - Contract: `design.md:1309-1323`.
- **Required change:** Include every supported action/effect/code occurrence in
  the same fail-closed request-binding and consistency pass.
- **Verification:** For both native pairs, test every public/metadata/nested/
  diagnostics/transport/evidence copy. Matching pairs use one fallback;
  mismatches, malformed copies, `-25204`, and performed/unknown effects use none.

### PRR-027 - `[S2][Blocking][documentation]` The committed approval result is invalid under the current review contract

- **Location:** `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-f19cbd9.json:34-106`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** The current validator rejects the committed result for four
  preserved-ID fingerprint drifts, a three-dot commit range, eight reviewed
  paths absent from all risk surfaces, and six approval-required runs bound to
  `65f8855` instead of `f19cbd9`.
- **Trigger:** Automation or a maintainer validates the approval artifact or
  relies on downstream F6 claims that it passed schema, SHA, and internal
  consistency checks.
- **Impact:** The approval chain is not machine-auditable and cannot support a
  merge/release decision.
- **Evidence:** The current
  `validate_review_result.py ...pr-review-macos-computer-use-3-f19cbd9.json`
  command exited 1 with `INVALID` and 12 invariant errors.
- **Required change:** Preserve historical fingerprints, use the exact two-dot
  range, cover all reviewed delta paths, bind approval-required runs to the
  reviewed head, and update downstream hashes/status claims.
- **Verification:** The repaired artifact and its downstream chain validate;
  the pushed replacement head receives exact-head CI and a fresh review.

### PRR-029 - `[S2][Blocking][correctness]` Collection extraction silently ignores selector steps after the first

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/collections.py:228-415`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** Item and descendant-field selectors are validated as full
  `SelectorDefinition` objects, but collection extraction directly selects
  `steps[0]`. The batch path does the same, and full root/pick/confidence/
  fallback semantics are not executed.
- **Trigger:** A valid collection profile uses `AXGroup -> AXStaticText` as a
  two-step descendant field.
- **Impact:** The extractor can report a resolved collection using a value from
  the wrong container, omit valid rows/fields, or attach the wrong element.
- **Evidence:**
  - The forward-risk probe returned
    `({'displayName': 'WRONG-CONTAINER'},)` with three query calls; the fourth
    step query never ran.
  - Code: `collections.py:228-264,340-415,439-507` and
    `validation.py:132-163,345-410`.
  - Contract: `design.md:866-888`.
- **Required change:** Execute complete selector semantics or reject every
  unsupported selector shape/policy during validation; do not silently
  truncate accepted configuration.
- **Verification:** Add multi-step item/field decoys, root, constraints, pick,
  confidence, fallbacks, and batch/non-batch parity. Accepted profiles execute
  every step; unsupported ones fail before any query.

### PRR-030 - `[S2][Blocking][reliability]` Selector profile and control-map overrides do not activate atomically

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py:35-48`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** `load_selector_profile` and `load_control_map` parse and
  fall back independently. The tool fixes the map at construction while
  resolver builders load the selector profile separately.
- **Trigger:** One override section is valid and changed while the other is
  invalid.
- **Impact:** Configuration rejected for selector semantics can still drive an
  incompatible fast-path navigation or mutation.
- **Evidence:**
  - The forward-risk probe loaded packaged profile
    `wechat.macos/app-control.selector-profile.v1` while activating override
    path `('0/99',)`.
  - Code: `profiles.py:35-48`, `control_map.py:67-78`, `tool.py:128-142`.
  - Contract: `design-remediation-2026-07-12.md:538-539` requires atomic
    activation.
- **Required change:** Parse and validate both sections in one transaction and
  keep one immutable source pair. If either fails, use both packaged defaults
  or fail configuration.
- **Verification:** Cover both half-valid directions, invalid TOML, missing
  sections, construction/reload, and fast-path operation counts. Mixed sources
  must be impossible.

### PRR-031 - `[S2][Blocking][correctness]` Collection pagination applies the caller limit before semantic acceptance

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/collections.py:83-216`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** The extractor fetches only `effective_limit + 1` raw AX rows,
  computes `hasMore` from them, then skips rows whose required fields fail
  without scanning later candidates. The public limit therefore bounds raw
  candidates instead of accepted semantic items.
- **Trigger:** Rejected candidates precede a later valid row.
- **Impact:** A valid item can be hidden behind a `failed` empty result that
  simultaneously reports `hasMore=true` and `nextCursor=null`.
- **Evidence:** `/private/tmp/collection-accepted-limit-probe-59c6fb5.py`
  (SHA-256 `232c3e7635dab89e0f41ae8c11e399c6471ba1883c35c2cf8f460b78a631dec7`)
  exited 36 after querying two rejected rows while a valid third row existed.
  Code: `collections.py:83-143,162-216`; contract: `design.md:890-896`.
- **Required change:** Use bounded overscan/continuation until the accepted
  semantic page plus accepted lookahead is obtained or visible exhaustion is
  proven; keep coherent cursor semantics.
- **Verification:** Cover rejected leading/middle rows, later valid items,
  exact limits, exhaustion, truncation, bounds, `hasMore`, and `nextCursor`.

### PRR-032 - `[S1][Blocking][security]` Bundle targeting can execute an Accessibility action in a background app

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:4230-4252`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** If the actual frontmost app does not match, the generated
  worker enumerates same-bundle processes and selects an active or merely
  usable background candidate before performing the AX action.
- **Trigger:** Another app is frontmost while the requested bundle remains
  running in the background.
- **Impact:** A semantic command can mutate stale or unintended background UI
  despite the declared `appFrontmost=true` precondition.
- **Evidence:** `/private/tmp/background-bundle-action-probe-59c6fb5.py`
  (SHA-256 `9210a94b1d0b20e747fff668072bc671d849b5ed25e9ab29f14a43f898b50d7b`)
  exited 34 after performing `('Send', 'AXPress')` on inactive WeChat while
  TextEdit was frontmost. Code: `client.py:3385-3407,4230-4252`; contract:
  `design.md:748-759`.
- **Required change:** Require the exact requested bundle/name to be the current
  frontmost usable app; never fall back to a background same-bundle process.
- **Verification:** Generated query/action worker tests for background,
  inactive, terminated, and multiple-instance targets must assert zero AX
  actions on every mismatch.

### PRR-033 - `[S1][Blocking][privacy]` Normal selector evidence and events expose raw AX content beyond the semantic limit

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:3289`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** New selector/control-map paths store complete low-level
  `accessibility_query` observations in normal evidence. The sanitizer only
  redacts selected nested input keys, so node values/titles/descriptions also
  reach progress/final events and `LoggingToolObserver(redact_text=True)`.
- **Trigger:** A private AX node is observed beyond the semantic list limit.
- **Impact:** Contact, preview, message, window, or AX-value data intentionally
  omitted from semantic output leaks to evidence, telemetry, and logs.
- **Evidence:** `/private/tmp/pr3_privacy_evidence_probe_59c6fb5.py`
  (SHA-256 `9c03b3767fa4bb04b39159087e70df8fb2db790f2a85b09df1338aba33503a4f`)
  exited 41: `PRIVATE_CANARY_CHARLIE` was absent from semantic items but present
  in evidence and progress/final events. `/private/tmp/pr3_privacy_logging_probe_59c6fb5.py`
  (SHA-256 `140daeb4be9c0510b10144e09768a3f97b514d7bdbd2c4b78f564e3c844f82db`)
  exited 42 with the canary in default redacted logs. Code:
  `tool.py:3252-3305,5196-5217,5243-5259`; contract:
  `requirements.md:45`, `design.md:641-646,668-671,1114-1123`.
- **Required change:** Allowlist privacy-safe normal evidence fields and remove
  nodes/raw/window/AX values; raw observations require explicit private-debug
  opt-in.
- **Verification:** Canary tests must cover contacts, conversation previews,
  messages, `includeRaw=false`, result evidence, progress/final events, and the
  default redacted logger while preserving intended semantic output.

### PRR-034 - `[S2][Blocking][compatibility]` Maximum collection pages generate batch query limits rejected by the public client

- **Location:** `packages/computer-use-macos/src/computer_use_macos/selectors/collections.py:454`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** Batch field extraction computes
  `len(item_paths) * step.limit` without capping/chunking, while
  `ComputerUseClient` accepts query limits only through 500.
- **Trigger:** The packaged contacts maximum page produces 101 lookahead paths
  with field limit 8, hence a generated limit of 808.
- **Impact:** A valid documented maximum-page request fails normalization
  before execution.
- **Evidence:** `/private/tmp/pr3_batch_limit_probe.py` (SHA-256
  `428624cad449328519e19b3c7963c59a1dfacede77cc5ea79300cf2e30669cc9`)
  exited 35 with limit 808 and `ValueError: query.limit must be between 1 and
  500`. Code: `collections.py:430-462`, `client.py:2711-2716`.
- **Required change:** Bound/chunk every batch query at 500 without dropping
  item/field coverage.
- **Verification:** Run packaged maximum pages through the real normalizer and
  compare batch output with an unbatched semantic reference.

### PRR-035 - `[S2][Blocking][correctness]` WeChat selector failure routing does not treat structured diagnostics as authoritative

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:3360-3496`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** Only `selector_query_failed` enters the special mapper, so
  `selector_query_truncated` becomes generic not-found. The mapper concatenates
  structured cause and free text, then lets keyword order choose the outcome.
- **Trigger:** A known transport cause has permission-like message text, or a
  query is structurally truncated.
- **Impact:** Status, failure kind, retryability, and recovery guidance become
  wrong; users can be sent to fix permissions for a transport failure.
- **Evidence:** `/private/tmp/mcu_pr3_failure_routing_probe.py` (SHA-256
  `2ebb9b37aca93ba280cc47a26cddd224941b64549ce959869de5fce056b1bf5e`)
  exited 2: `helper_transport_failed` became `missing_accessibility`, and
  truncation became `main_content_not_found`. Code: `tool.py:3360-3496`;
  contract: `design.md:1007-1025`.
- **Required change:** Map exact structured kind/cause first; use message
  heuristics only when structured information is absent or unknown.
- **Verification:** Adversarial cross-keyword matrices must assert status,
  failure kind, retryability, hint, and nested diagnostics for permission,
  timeout, transport, and limit/time-budget truncation.

### PRR-036 - `[S2][Blocking][api-contract]` New query and action worker failures are absent from the stable package registry

- **Location:** `packages/computer-use-macos/src/computer_use_macos/errors.py:55-97`
  @ `59c6fb59fd08481b07217b9e236d1038bd9736ce`
- **Confidence:** `High`
- **Status:** `open`
- **Observation:** Warm workers emit four package-owned failure kinds for query/
  action failure and empty response; the client preserves them top-level, but
  `COMPUTER_USE_FAILURE_KINDS` declares none.
- **Trigger:** A warm worker raises or returns no response and a tuple-based
  public consumer routes the normalized observation.
- **Impact:** Stable-registry consumers see real package failures as unknown and
  cannot make exhaustive routing decisions.
- **Evidence:** `/private/tmp/pr3_failure_registry_probe_59c6fb5.py` (SHA-256
  `cb55c455ee6dc77915fe9dd027355aae5528e07f16f379d31a4289a661282606`)
  exited 43 with both real normalized worker failures `registered=False`; code
  audit confirms both empty-response variants are also absent. Code:
  `client.py:1375-1388,1564-1577,4010-4045,4505-4542`, `errors.py:55-97`;
  contract: `packages/computer-use-macos/README.md:165`, `docs/api.md:794-810`.
- **Required change:** Declare/export all four constants and add them uniquely
  to the stable tuple.
- **Verification:** Cover query/action failure and empty response from producer
  through normalizer, public wheel imports, tuple membership/uniqueness, and
  release preflight.

### Resolved findings retained for continuity

| Finding | Status | Evidence |
|---|---|---|
| `PRR-022` | **resolved** | Generated post-call failures carry action through normalization; both real native pairs preserve one allowed fallback. |
| `PRR-025` | **resolved** | `ACCESSIBILITY_ACTION_UNSUPPORTED` remains in `COMPUTER_USE_FAILURE_KINDS` and package tests pass. |

## 6. Required Actions Before Merge

- [ ] `PRR-021` - collect and validate every known attempted/dispatch evidence
  container; prove zero replay across all shared fallback callers.
- [ ] `PRR-026` - bind every known action/effect/code copy to the outbound
  request and reject malformed or contradictory proof.
- [ ] `PRR-027` - repair the committed `f19cbd9` result and downstream
  integrity/status references, then obtain exact-head CI.
- [ ] `PRR-028` - fail closed and avoid caching on decision-critical selector
  truncation; add hidden-candidate regressions.
- [ ] `PRR-029` - implement complete collection selector semantics or reject
  unsupported definitions before any query.
- [ ] `PRR-030` - activate selector profile and control map atomically and add
  split-override regressions.
- [ ] `PRR-031` - paginate over accepted semantic items with bounded
  overscan/continuation and coherent cursor behavior.
- [ ] `PRR-032` - require the requested app to be currently frontmost before
  any generated Accessibility query/action.
- [ ] `PRR-033` - replace normal raw AX evidence/events with a privacy-safe
  allowlist and add cross-channel canary regressions.
- [ ] `PRR-034` - chunk/bound collection batch queries to the public limit
  without dropping field coverage.
- [ ] `PRR-035` - route exact structured failure kinds/causes before free-text
  fallback heuristics.
- [ ] `PRR-036` - declare, export, and register all four warm-worker failure
  kinds with producer-to-wheel tests.

After all actions are complete: push a new head, wait for CI, re-run this
review, and only then mark the PR ready and merge.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | High | Wrong selectors/background targeting can mutate unintended UI; raw AX data escapes into normal evidence/events/logs. | Resolve `PRR-028`, `PRR-030`, `PRR-032`, `PRR-033`. / selector, computer-use, WeChat owners |
| Data integrity | High | Contradictory proof can authorize a second desktop mutation. | Resolve `PRR-021`/`PRR-026` with end-to-end operation-count tests. / computer-use and WeChat owners |
| Reliability & concurrency | High | Resolver, collection, pagination, override, and failure-routing paths can return confident but incorrect semantic results. | Resolve `PRR-028`-`PRR-031`, `PRR-035`. / selector and WeChat owners |
| Performance & scalability | Medium | Accepted-item continuation must remain bounded; max-page batch queries currently exceed the backend limit. | Resolve `PRR-031`/`PRR-034` with bounds, chunking, and parity tests. |
| API & compatibility | Medium | Accepted config/max pages cannot always execute, and emitted worker failures are missing from the stable registry. | Resolve `PRR-029`, `PRR-034`, `PRR-036`. |
| Deployment & rollback | Medium | Approval artifact is invalid and PR is draft; F7 proof is incomplete. | Resolve `PRR-027`, rerun exact-head CI/review, then complete F7. |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit | Evidence / notes |
|---|---|---|---:|---|
| `git diff --name-status 1e56b00..59c6fb5` + content audit | clean exact-head Darwin arm64 clone | PASS | 0 | Seven commits and all 16 delta paths classified; full diff reconciled. |
| root `unittest discover` | clean exact-head CPython 3.12.7 | PASS | 0 | 127 passed in 163.082 s. |
| protocol `unittest discover` | same clone | PASS | 0 | 55 passed. |
| computer-use `unittest discover` | same clone | PASS | 0 | 144 passed, 1 skipped. |
| WeChat `unittest discover` | same clone | PASS | 0 | 140 passed. |
| `action_evidence_e2e_probe_59c6fb5.py` | local packages; no UI mutation | **FAIL** | 1 | Contradictory diagnostics reached `accessibility_action -> click`. |
| `action_evidence_probe_59c6fb5.py` | local packages; no UI mutation | **FAIL** | 19 | 19 nested/evidence contradictions ignored. |
| `pr3-forward-risk-counterexamples.py` | selector and WeChat test helpers | **FAIL** | 0 | Printed three invalid outcomes; probe exits zero by design. |
| `collection-accepted-limit-probe-59c6fb5.py` | deterministic selector runner | **FAIL** | 36 | Valid third semantic row hidden behind two rejected raw rows. |
| `background-bundle-action-probe-59c6fb5.py` | generated worker with in-memory AppKit/AX fakes | **FAIL** | 34 | Background WeChat received AXPress while TextEdit was frontmost. |
| `pr3_privacy_evidence_probe_59c6fb5.py` | selector/control-map fake backend | **FAIL** | 41 | Limit-excluded canary leaked to evidence and progress/final events. |
| `pr3_privacy_logging_probe_59c6fb5.py` | default redacted observer | **FAIL** | 42 | Canary leaked to `redact_text=True` logs. |
| `pr3_batch_limit_probe.py` | packaged profile + real client normalizer | **FAIL** | 35 | Generated 808 exceeds public maximum 500. |
| `mcu_pr3_failure_routing_probe.py` | deterministic selector diagnostics | **FAIL** | 2 | Structured transport/truncation causes were misrouted. |
| `pr3_failure_registry_probe_59c6fb5.py` | real wrapper normalization | **FAIL** | 43 | Emitted worker failures were absent from the stable tuple. |
| targeted cache/warm-worker pytest | clean clone | PASS | 0 | 16 passed, 128 deselected; no additional cache/concurrency blocker. |
| validate committed `f19cbd9.json` | current skill validator | **FAIL** | 1 | `INVALID`: fingerprint, range, coverage, and head-binding failures. |
| compileall + release preflight | clean clone; external pycache | PASS | 0 | Compilation/preflight passed; only documented F7/socket warnings. |
| validate this `59c6fb5.json` | current skill validator | PASS | 0 | `VALID`. |
| `git diff --check fed6523..59c6fb5` | clean exact-head clone | PASS | 0 | No whitespace errors. |

Broad green suites do not override the discriminating failing invariants.

### CI and platform checks observed

| Check | Observed at | Status | Evidence |
|---|---|---|---|
| GitHub Actions `CI / test` | `2026-07-16T14:14:49Z` | PASS | [run 29464092118 / job 87513460562](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29464092118/job/87513460562), exact head `59c6fb5` |
| GitHub PR state | `2026-07-16T14:14:49Z` | PASS | Open, draft, mechanically mergeable, merge state clean; base/head unchanged |
| Live body synchronization | same observation | PASS | Raw local/remote body: 7,232 characters; SHA-256 `cb6323c69d12187efd1175b802567061f48166d29cd4baa8375393ad03f3add8` |

### Checks not run

- Fresh live WeChat/macOS Accessibility mutation - it would modify the user's
  desktop and cannot resolve the deterministic blockers.
- Signed helper, notarization, TestPyPI, PyPI, and trusted-publisher proof -
  separate F7 gates.
- Repository-wide strict mypy and Ruff - no accepted clean strict-mypy baseline;
  Ruff is not configured exact-head CI.

## 9. Coverage and Limitations

- **Reviewed:** all seven delta commits/16 paths, complete base-to-head affected
  selector/action/configuration paths, prior finding ledger, tests, lifecycle
  evidence, report chain, CI, and GitHub state.
- **Not reviewed:** fresh real desktop effects, signing/notarization, and
  publication systems.
- **Missing context:** none that changes `REQUEST_CHANGES`.
- **Report persistence:** this Markdown/JSON pair remains uncommitted so writing
  it does not change and invalidate the reviewed head.
- **Platform condition:** the PR remains draft; even a future clean review must
  mark it ready before merge.
- **Staleness condition:** any base/head or decision-critical evidence change
  requires re-review.

## 10. Open Questions and Assumptions

### Open questions

None.

### Assumptions

| Assumption | Decision-critical | Status | Evidence |
|---|---:|---|---|
| Remote base/head remain `fed6523`/`59c6fb5`. | true | VERIFIED | Fresh `gh pr view` returned exact SHAs, green CI, open/draft, mergeable/clean. |
| `PRR-028`-`PRR-036` are introduced, expanded, or made reachable by this PR. | true | VERIFIED | Selector/collection/profile/worker paths are new; this PR adds the normal selector evidence/event consumers, routing helpers, and worker failure producers. |
| Minimal caller-fabricated non-row actionRef behavior is baseline. | false | VERIFIED | Base already accepts `target.axPath` with default `AXPress`; the PR adds some narrowing checks. |
| Live PR body matches tracked source. | false | VERIFIED | Raw values match at 7,232 characters and SHA-256 `cb6323...`. |

## 11. Non-blocking Recommendations

- `NOTE-031` - Track strict provenance/completeness validation for caller-supplied
  non-row actionRef objects as a separate baseline security issue. It is
  reproducible at both base and head, so it is not a PR blocker.
- `NOTE-023` - Keep production-derived fixtures for generated native action
  fields.
- `NOTE-016` - Retain dispatch-aware no-replay and definite-no-effect wording in
  final release notes.

## 12. Machine-readable Summary

- Result file:
  `docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-59c6fb5.json`
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`
- Validator result: `VALID`

```yaml
schema_version: "1.1"
review_kind: RE_REVIEW
decision: REQUEST_CHANGES
mergeable: false
head_sha: 59c6fb59fd08481b07217b9e236d1038bd9736ce
blocking_findings:
  - PRR-021
  - PRR-026
  - PRR-027
  - PRR-028
  - PRR-029
  - PRR-030
  - PRR-031
  - PRR-032
  - PRR-033
  - PRR-034
  - PRR-035
  - PRR-036
validation_status: FAILED
report_status: CURRENT
```
