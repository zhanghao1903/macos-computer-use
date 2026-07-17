# PR Review: `zhanghao1903/macos-computer-use#3` @ `5a010da`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository / PR | [zhanghao1903/macos-computer-use#3](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Title | Add internal Accessibility selector engine |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `5a010dab632eda2d3d9b39205f4f867c1fed0097` |
| Reviewed at | `2026-07-13T12:19:32Z` |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |

GitHub reports PR #3 open, draft, and mergeable. The repository is public and
the exact-head CI run completed successfully.

## 2. Decision

| Decision | Mergeable | Open blocking findings |
|---|---:|---|
| `APPROVE` | yes | none |

`PRR-001` through `PRR-016` remain resolved. The final performance finding,
`PRR-017`, is resolved by deterministic no-replay worker coverage, a successful
`2461 ms` public send, a separate real Contacts-origin `open_contact` result of
`1272 ms`, a `58 ms` warm Chats action, and green exact-head CI.

## 3. Executive Summary

The PR replaces broad, brittle WeChat Accessibility traversal with bounded
selectors, packaged control maps, verified semantic actions, and privacy-safe
release proof. The final remediation keeps the existing action script and
safety checks but executes it through a prewarmed worker; action failure or
timeout after dispatch is never replayed.

One authorized public send succeeded once in `2461 ms`. Because that send began
with Chats selected, a separate non-submit probe started in Contacts and proved
the remediated transition: Chats `AXPress` took `58 ms` with worker transport,
no fallback, verified preconditions, and a successful target-title
postcondition. No open blocking finding remains.

## 4. Scope And Change Map

### Reviewed scope

- complete `main...5a010da` feature diff and prior finding ledger;
- warm query/action worker lifecycle, transport diagnostics, timeout, failure,
  fallback, and no-replay behavior;
- public WeChat focus, open, draft, and send call path;
- deterministic package/root suites and release preflight;
- exact-head GitHub Actions result;
- authorized public send and separate non-submit Contacts-to-Chats proof.

### Excluded or unavailable scope

- post-submit delivery read-back;
- repeated latency sampling or percentile characterization;
- a single send command whose initial state was Contacts;
- signed-helper execution and real release publication;
- unrelated dirty worktree files and private raw smoke artifacts.

| Area | Current result | Risk | Evidence |
|---|---|---|---|
| Selector engine | Passed | Low | Bounded models, resolver, cache, collection, and negative tests. |
| Mutating AX transport | Passed | Low | Warm action worker preserves script checks and never replays after dispatch. |
| Public send | Passed | Low | Verified target, clipboard draft, Return submit, `2461 ms`. |
| Contacts-origin action | Passed | Low | `open_contact=1272 ms`; Chats `AXPress=58 ms`, worker, no fallback. |
| Packaging / CI | Passed | Low | Exact-head run passed tests, preflight, wheels, and distribution checks. |

## 5. Findings

### PRR-017 - `[S2][Resolved][performance] Public send exceeds the three-second API contract`

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:_run_accessibility_action_request` @ `5a010dab632eda2d3d9b39205f4f867c1fed0097`
- **Confidence:** High
- **Status:** resolved
- **Observation:** The previous public send took `3116 ms`; the largest
  removable component was a `1042 ms` one-shot Chats action.
- **Trigger:** Start WeChat outside Chats and execute the verified contact-open
  path used by public `send_message`.
- **Impact:** The public convenience API could exceed the approved `3000 ms`
  representative performance target.
- **Evidence:**
  - the direct backend now has a prewarmed action worker and returns worker
    failure/timeout without replay;
  - deterministic tests cover success, protocol failure, timeout, and original
    subprocess compatibility;
  - the authorized public send returned `success=true`, `submitted=true` in
    `2461 ms`;
  - the separate Contacts-origin probe returned `open_contact` in `1272 ms`
    and measured Chats `AXPress` at `58 ms` (`44 ms` worker transport,
    `fallback=false`);
  - exact-head GitHub Actions passed.
- **Required change:** Completed. Preserve all app, target, frame, action, and
  postcondition checks while removing repeated framework startup.
- **Verification:** Completed. Deterministic suites, public send, real
  non-submit state transition, and exact-head CI all passed.

No open blocking findings were identified for the reviewed snapshot.

## 6. Required Actions Before Merge

None.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | Low | Local raw logs can contain transient WeChat text. | Keep raw artifacts untracked and publish only bounded semantic evidence. |
| Data integrity | Low | Desktop state may change between resolution and action. | Exact identity, snapshot, frame, precondition, and title checks fail closed. |
| Reliability & concurrency | Low | Worker timeout can leave action outcome unknown. | Never replay a dispatched action; return timeout/failure for manual recovery. |
| Performance & scalability | Low | Live evidence is representative, not percentile data. | Keep bounded query/action diagnostics and add repeated sampling later if needed. |
| API & compatibility | Low | Transport changed internally for direct mode. | Public semantic APIs and helper behavior remain compatible. |
| Deployment & rollback | Low | Two long-lived AX workers replace repeated subprocess startup. | Original subprocess remains available before dispatch; revert `5a010da` as one slice. |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| Root unittest discovery | macOS, Python 3.12, `5a010da` | PASS | 0 | 127 passed in 41.695 s. |
| `computer-use-macos` unittest discovery | macOS, Python 3.12, `5a010da` | PASS | 0 | 132 passed, 1 skipped. |
| `wechat-desktop-tool` unittest discovery | macOS, Python 3.12, `5a010da` | PASS | 0 | 123 passed. |
| Release preflight | macOS, Python 3.12, `5a010da` | PASS | 0 | Required local gates passed; unavailable external proof remained warning-only. |
| Authorized one-shot public send | Live WeChat, target restricted to `文件传输助手` | PASS | 0 | `success=true`, `submitted=true`, `2461 ms`, no retry. |
| Non-submit Contacts-origin probe | Live WeChat, no draft or Return | PASS | 0 | `open_contact=1272 ms`; Chats action `58 ms`, worker, no fallback. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| GitHub Actions run `29217691709`, job `86797719880` | `2026-07-13T12:19:32Z` | PASS | Exact head `5a010da`; all test, preflight, wheel, and distribution steps passed. |

### Checks not run

- Post-submit delivery read-back: the authorized send did not request
  `verifyAfterSubmit`.
- One-command send starting in Contacts: the single authorized send began in
  Chats; the exact transition was exercised separately without sending.
- Ruff: no Ruff executable or module is installed.
- Signed helper and real release publication: these are later release gates.

## 9. Coverage And Limitations

- **Reviewed:** feature diff, public semantic paths, worker lifecycle,
  uncertainty/no-replay behavior, tests, packaging, CI, and live evidence.
- **Not reviewed:** unrelated worktree edits, private raw logs, signed helper,
  actual release publication, and delivery read-back.
- **Missing context:** no material design or acceptance input is missing.
- **Staleness condition:** any product source, test, schema, config, or workflow
  change after `5a010da` requires re-review. A documentation-only carrier commit
  does not change the reviewed implementation but still requires CI.

One timing sample cannot characterize percentiles. The public send and
Contacts-origin transition were separate runs, and the report preserves that
distinction.

## 10. Open Questions And Assumptions

### Open questions

None that block merge.

### Assumptions

1. The approved performance gate is a bounded representative live sample, not
   a percentile service-level objective.
2. API-level `submitted=true` is sufficient for the send workflow gate;
   delivery read-back is outside the approved one-shot proof.
3. The committed changelog entries already describe the feature and its
   performance behavior; unrelated local changelog edits remain excluded.

## 11. Non-Blocking Recommendations

- `NOTE-012`: remove the unreferenced private legacy focus implementation in a
  later cleanup.
- `NOTE-013`: add Ruff to the development dependency group so the configured
  lint gate is reproducible.
- `NOTE-014`: collect repeated live timing samples if this target becomes an
  operational SLO rather than a feature acceptance threshold.

## 12. Machine-Readable Summary

- Result file:
  [`pr-review-macos-computer-use-3-5a010da.json`](./pr-review-macos-computer-use-3-5a010da.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: APPROVE
mergeable: true
head_sha: 5a010dab632eda2d3d9b39205f4f867c1fed0097
blocking_findings: []
validation_status: PASSED
report_status: CURRENT
```
