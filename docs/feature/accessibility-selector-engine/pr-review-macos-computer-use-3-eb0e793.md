# PR Review: `zhanghao1903/macos-computer-use#3` @ `eb0e793`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository / PR | [zhanghao1903/macos-computer-use#3](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Title | Add internal Accessibility selector engine |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb` |
| Reviewed at | 2026-07-12T15:19:48Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |

## 2. Decision

| Decision | Mergeable | Blocking findings |
|---|---:|---|
| `REQUEST_CHANGES` | `false` | `PRR-013`, `PRR-014`, `PRR-015`, `PRR-016` |

The 12 blockers from the `07fa052` review have implementation and verification
evidence and are resolved on this snapshot. Four newly identified regressions
remain: the legacy public contact/send flow is unusable on the live client,
generic AX query/action requests can select the wrong app when `bundle_id` is
omitted, row actionRefs do not revalidate conversation identity, and list APIs
publish continuation tokens that cannot advance. These are core correctness and
desktop-safety contracts, so green CI is not sufficient to approve this head.

## 3. Executive Summary

The PR now has a bounded selector engine, a fast WeChat control map, fail-closed
query diagnostics, privacy-safe release proof v2, coordinated package metadata,
and successful live evidence for `inspect_window`, lists, `open_contact`, and
message reads. The prior 12 review findings are closed.

Reviewing the complete public call paths exposed four gaps outside that proof:
`focus_contact` and `send_message` still use the obsolete hotkey/observe flow;
the low-level AX worker ignores `target_app` without a bundle id; generated row
actionRefs omit the label precondition required to detect reordering; and
visible-window pagination fabricates a cursor that is only echoed back. The PR
must return to remediation and be re-reviewed on a new head.

## 4. Scope and Change Map

### Reviewed scope

- PR metadata, 83 changed files, full local `base...head` diff, and current CI;
- selector profile parsing, validation, matching, resolver, cache, collections,
  bounded query worker, AX action worker, and coordinate fallback;
- WeChat control map, semantic list/open/read/action APIs, legacy focus/send
  compatibility path, configuration, examples, and package boundaries;
- release workflow, wheel compatibility, strict preflight, public proof v2,
  lifecycle documents, and all prior review remediation claims;
- authorized live WeChat focus-only counterexamples; no message was drafted or
  submitted.

### Excluded or unavailable scope

- signed/notarized helper application end-to-end execution;
- actual PyPI/TestPyPI publication and a real GitHub Release publication;
- duplicate-contact live mutation tests and intentional wrong-app desktop
  actions, because static/deterministic evidence is sufficient and safer;
- exhaustive prose review of every historical paragraph in the long feature
  log; current contracts and claimed evidence were reviewed.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Selector core | Validated profiles, bounded resolver/cache/collection engine. | WeChat semantic APIs resolve mapped/selector AX targets. | High | Source review, package tests, prior counterexamples. |
| AX transport | Warm query worker, path resolver, AXPress/AXSetFocus, frame clicks. | Reads and actions can target application Accessibility elements. | High | Identity/action script review and safety tests. |
| WeChat APIs | Lists, open/read, actionRef execution, legacy focus/send. | Existing consumers should retain semantic behavior. | High | Unit tests plus authorized live comparison. |
| Release proof | Sanitized source-bound proof v2 and strict bundle gate. | Release assets exclude private AX observations. | High | Validator tests, exact-code-head live proof, current CI. |
| Packaging/docs | Coordinated `0.2.0`, dependency floors, workflow/docs updates. | Clean installs require the coordinated package set. | Medium | Wheel/preflight evidence and CI. |

## 5. Findings

### PRR-014 - [S1][Blocking][Security] Target-app-only AX requests can read or act on the wrong frontmost application

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:3092` (`_accessibility_query_script.selected_running_app`) and `:3901` (`_accessibility_action_script.selected_running_app`) @ `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`
- **Confidence / status:** `High` / `open`
- **Observation:** Both worker scripts inspect only `REQUEST.bundleId`. When it
  is empty they return `workspace.frontmostApplication()` without comparing
  `REQUEST.targetApp`. The parent action allowlist accepts an allowlisted
  `target_app` with no bundle id, and the query path has no equivalent target
  allowlist check. Public method signatures and docs make `bundle_id` optional.
- **Trigger:** Configure `TextEdit` as an allowlisted app without an associated
  bundle id, place another app in front, and call `accessibility_action` with
  `target_app="TextEdit"`; the same identity error affects target-app-only
  queries.
- **Impact:** A verified path can be resolved and pressed in the wrong app, or
  a read can return another app's private UI while labelling the request as the
  intended target. This breaks both the action safety boundary and query data
  isolation.
- **Evidence:**
  1. The two `selected_running_app` implementations branch only on `bundle_id`
     and otherwise return `frontmost`.
  2. `_accessibility_action_allowlist_failure` accepts a known app name when
     its configured bundle mapping is `None`.
  3. `docs/api.md` documents `bundle_id=None`, while the AX query design says
     the engine must locate the target process by bundle id.
- **Required change:** Resolve and pass the configured expected bundle id, or
  verify the selected process against the requested app name before any query
  or action. Reject unallowlisted query identities and fail closed when an
  action target identity cannot be proven.
- **Verification:** Add target-app-only wrong-frontmost tests for query and
  action, bundle mismatch tests, and a positive configured-name-to-bundle test;
  assert no worker/action call occurs on identity failure.

### PRR-015 - [S1][Blocking][Data Integrity] Conversation-row actionRefs can press a different contact after list reordering

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:3675-3703` (`_action_ref_from_node`) @ `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`
- **Confidence / status:** `High` / `open`
- **Observation:** `_action_ref_from_node` deliberately excludes `labelIn` for
  every `AXRow`, even when the row has a contact-bearing `AXDescription`. The
  action target stores that label, but `_accessibility_action_input` forwards
  only `preconditions`; the low-level executor therefore checks role, action,
  and enabled state but not contact identity. The snapshot id is based only on
  app/window title and remains unchanged when rows reorder.
- **Trigger:** List conversations, receive an AXPress actionRef for row path
  `.../0`, let unread/pinned state reorder the rows within its five-minute TTL,
  then call `execute_action` with the original ref.
- **Impact:** The action can open a different contact while reporting success.
  A caller that follows with a read or draft can operate on the wrong chat,
  violating the documented one-shot signature revalidation lifecycle.
- **Evidence:** A current-head counterexample generated an AXRow actionRef whose
  target contained a contact label but whose preconditions contained only
  `roleIn`, `actionIn`, and `enabled`. The design requires app/window/signature
  revalidation before execution.
- **Required change:** Publish row actionRefs only when the target identity can
  be revalidated. Add an exact current label/signature precondition or
  re-resolve the semantic contact immediately before action; otherwise omit
  the actionRef and require `open_contact(displayName)`.
- **Verification:** Simulate same-role path reuse with a changed row label and
  assert `execute_action` fails before AXPress/fallback; retain a positive
  unchanged-row test and an unlabeled-row no-actionRef test.

### PRR-013 - [S1][Blocking][Compatibility] Public `focus_contact` and `send_message` remain on an obsolete live path

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:1970` (`_focus_contact`) and `:2470` (`_send_message`) @ `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`
- **Confidence / status:** `High` / `open`
- **Observation:** The new `open_contact` operation uses the verified control
  map/selector search flow, but `focus_contact` still sends a configured hotkey
  and verifies focus through the legacy coarse `observe` snapshot.
  `send_message` still calls `_focus_contact`, so it never benefits from the
  verified implementation. This PR also changed the default search hotkey from
  `Command+K` to `Command+F`.
- **Trigger:** On the authorized current WeChat client, call
  `focus_contact("文件传输助手")` with either the new default or the prior
  default hotkey.
- **Impact:** The public contact-switch API returns `search_not_focused`, and
  the convenience send API stops at `focus_contact`. Existing package
  consumers cannot perform a core documented workflow after upgrading.
- **Evidence:**
  1. Default `Command+F` live smoke failed safely in 1781 ms before typing.
  2. A `Command+K` override failed at the same focus-verification stage in
     1278 ms, ruling out the shortcut value as the complete fix.
  3. `_send_message` directly invokes `_focus_contact`; no draft or message was
     produced in either reproduction.
- **Required change:** Make `focus_contact` delegate to `open_contact` or share
  its selector-backed implementation, and make `send_message` use that verified
  target-switch contract. Remove or clearly deprecate the obsolete hotkey path
  rather than maintaining two safety models.
- **Verification:** Add delegation/call-sequence tests and run an authorized
  live `focus_contact` plus `send_message` to `文件传输助手`, proving the target
  title before draft and submit.

### PRR-016 - [S2][Blocking][API Contract] Visible-window list APIs return continuation tokens that always repeat the first page

- **Location:** `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:617-790` (`_list_row_items_with_selector_profile`, `_list_row_items_with_control_map`) @ `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`
- **Confidence / status:** `High` / `open`
- **Observation:** `pageToken` is parsed and echoed but never changes the AX
  root, offset, scroll state, or collection query. When more than `limit` rows
  are visible, both selector and control-map paths fabricate
  `<section>:next:<snapshot>` and advertise `hasMore=true`.
- **Trigger:** Request a small page, then pass the returned `nextPageToken` into
  the next list call while the window remains unchanged.
- **Impact:** The caller receives the same rows and another equivalent token,
  causing duplicate data or an unbounded agent pagination loop. The approved
  design explicitly says visible-window pagination has no cursor and
  `next_cursor` must remain `None` for the MVP.
- **Evidence:** Data flow inspection shows `page_token` has no consumer beyond
  response serialization, while the token is generated at lines 699 and 778.
- **Required change:** For this MVP, keep `nextPageToken=null` and reject a
  non-null input token (or document a non-cursor visible-window response).
  Alternatively implement and verify a real scroll/cursor continuation before
  advertising a token.
- **Verification:** Add two-call tests that either reject unsupported tokens or
  return a disjoint second page; assert no repeating continuation token can be
  emitted.

### Resolved findings retained from the previous snapshot

| ID | Status | Closure evidence on `eb0e793` |
|---|---|---|
| `PRR-001` | `resolved` | Proof v2 is whitelist-only; strict validator/bundler reject forbidden keys, paths, canaries, and raw observations. |
| `PRR-002` | `resolved` | Only verified search focus permits clear/type/Return; unknown states stop before input. |
| `PRR-003` | `resolved` | Packaged fixed coordinates are not executed; fallback coordinates come from a current in-window AX frame and have a postcondition. |
| `PRR-004` | `resolved` | Mapped target lookup retains two candidates and returns ambiguity before action. |
| `PRR-005` | `resolved` | Selector-backed WeChat construction rejects helper mode before transport use; direct-backed local service remains supported. |
| `PRR-006` | `resolved` | Cache hits rerun matcher, actions, state, constraints, relation, and signature checks. |
| `PRR-007` | `resolved` | Backend availability/failure cause survives normalization and is not mapped to not-found. |
| `PRR-008` | `resolved` | Shared maximum depth is 8 and combined batch depth is capped before client normalization. |
| `PRR-009` | `resolved` | Completed N+1 limit lookahead is separated from actual truncation. |
| `PRR-010` | `resolved` | Coordinated `0.2.0` dependency floors and clean wheel checks reject mixed old packages. |
| `PRR-011` | `resolved` | Release workflow includes all three source roots and preflight protects the command. |
| `PRR-012` | `resolved` | Strict proof requires source binding, non-zero/count-consistent collections, complete checks, and bounded timings. |

## 6. Required Actions

- [ ] `PRR-013` - unify `focus_contact`/`send_message` with verified
  selector-backed `open_contact`, then run the authorized target/send smoke.
- [ ] `PRR-014` - enforce target application identity in query and action
  before Accessibility access or mutation.
- [ ] `PRR-015` - make conversation row actionRefs identity-revalidating or do
  not publish them.
- [ ] `PRR-016` - remove false continuation semantics or implement real
  continuation.
- [ ] Re-run the complete review and exact-head release proof after fixes.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation |
|---|---|---|---|
| Security/privacy | High | Target-app-only AX requests can touch/read the wrong process. | Resolve `PRR-014`; add wrong-frontmost negatives. |
| Data integrity | High | Stale row refs can open the wrong contact. | Resolve `PRR-015`; revalidate semantic identity. |
| API compatibility | High | Existing focus/send methods are unavailable live. | Resolve `PRR-013`; use one verified contact-switch path. |
| Reliability | Medium | False pagination tokens can loop callers. | Resolve `PRR-016`; expose honest visible-window semantics. |
| Performance | Low | Proven selector operations remain below the 3-second target in the latest authorized proof. | Preserve current bounded budgets in fixes. |
| Deployment | Low | CI and coordinated package checks pass; exact final-head proof must be regenerated after remediation. | Re-run strict preflight and wheel checks. |

## 8. Validation Evidence

### Reviewer-executed checks

- **PASS** `uv run pytest packages/app-control-protocol/tests -q`
  - Environment: macOS, Python 3.12, head `eb0e793b...`; exit `0`.
  - Result: 55 passed.
- **PASS** `uv run pytest packages/computer-use-macos/tests -q`
  - Environment: macOS, Python 3.12, head `eb0e793b...`; exit `0`.
  - Result: 125 passed.
- **PASS** `uv run pytest packages/wechat-desktop-tool/tests -q`
  - Environment: macOS, Python 3.12, head `eb0e793b...`; exit `0`.
  - Result: 122 passed.
- **PASS** `git diff --check origin/main...HEAD`
  - Environment: local git, head `eb0e793b...`; exit `0`.
- **FAIL (expected counterexample)** authorized live `focus_contact` with
  packaged `Command+F`.
  - Head `eb0e793b...`; exit `1`; `search_not_focused` after 1781 ms; no draft
    and no submission.
- **FAIL (expected counterexample)** same live operation with
  `APP_CONTROL_WECHAT_SEARCH_HOTKEY=Command,K`.
  - Head `eb0e793b...`; exit `1`; same failure after 1278 ms; no draft and no
    submission.
- **PASS counterexample construction** current-head `_action_ref_from_node`
  output inspection.
  - An AXRow target with a contact-bearing label produced no `labelIn`
    precondition, confirming `PRR-015`.

### CI and prior exact-code proof

- **PASS** GitHub Actions `test`, run `29196700910`, job `86660857594`, 1m47s,
  observed 2026-07-12.
- **PASS** exact-code-head sanitized live proof at
  `6a74c1d677c767bc68b993f03873990a3d6dcbb`: all 10 checks true, contacts 11,
  conversations 14, messages 30, no raw observation, no message submission,
  and all measured semantic APIs below 3 seconds.
- **PASS** strict preflight for that exact code head. `eb0e793` adds only F5
  documentation after `6a74c1d`; final exact-head proof still must be rerun
  after the blocking code fixes.

Overall validation status: `FAILED` because four blocking counterexamples remain.

## 9. Coverage and Limitations

- This report is valid only for head
  `eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`; a new commit makes it stale.
- Live operations were limited to the authorized WeChat target and stopped
  before drafting or submitting. Wrong-app action and reordered-row mutation
  were not executed because code/data-flow evidence is conclusive.
- The helper skeleton was not signed or run end to end; the reviewed contract
  intentionally rejects selector-backed WeChat helper mode in `0.2.0`.
- Real publishing was not run. Release workflow, wheel and preflight behavior
  were validated locally/through CI.
- Ruff remains unavailable in the current environment.
- Unrelated dirty and untracked workspace files were excluded from the diff,
  tests, and review artifacts.

## 10. Open Questions and Assumptions

### Open questions

- Should unsupported `pageToken` input return `invalid_input`, or should the
  current public schema retain the field as always-null until scrolling exists?
- Should row actionRefs be omitted entirely in `0.2.0`, or can WeChat provide a
  stable, current row signature suitable for fail-closed execution?

### Assumptions

- Existing public `focus_contact` and `send_message` behavior is part of the
  compatibility contract and cannot silently become unavailable.
- `target_app` means the requested application even when `bundle_id` is omitted;
  it is not an alias for whatever application is frontmost.
- An actionRef authorizes only its represented semantic target, not any same-role
  element that later occupies the same AX path.
- Visible-window extraction may indicate that more rows are visible, but must
  not advertise a cursor unless it can continue without duplicates.

## 11. Non-blocking Recommendations

- **NOTE-009 [maintainability]** Split the 5,000-line WeChat tool module by
  semantic operation after the merge gate is green; keep this remediation
  scoped to the four findings first.
- **NOTE-010 [observability]** Preserve the current per-step AX timing fields in
  all fixes so the established sub-3-second performance evidence remains
  comparable.
- **NOTE-011 [documentation]** After remediation, mark this report stale rather
  than rewriting it, and generate a new snapshot report with the same finding
  IDs and updated statuses.

## 12. Machine-readable Summary

Structured result:
[`pr-review-macos-computer-use-3-eb0e793.json`](./pr-review-macos-computer-use-3-eb0e793.json).

Decision: `REQUEST_CHANGES`. Open blocking findings: `PRR-013`, `PRR-014`,
`PRR-015`, and `PRR-016`. Previous findings `PRR-001` through `PRR-012` remain
resolved on this snapshot.
