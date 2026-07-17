# PR Review: `zhanghao1903/macos-computer-use#3` @ `f2b98ed`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository / PR | [zhanghao1903/macos-computer-use#3](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Title | Add internal Accessibility selector engine |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `f2b98ed11da7a261f0e81ea8fb671cf5e633c4b2` |
| Reviewed at | 2026-07-13T01:10:38Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |

The runtime source remains `ca6d4a8`; intervening commits contain review and
verification documentation only. GitHub reports PR #3 open, draft, and
mergeable, while its current CI job did not start because of account Billing.

## 2. Decision

| Decision | Mergeable | Open blocking findings |
|---|---:|---|
| `REQUEST_CHANGES` | yes | `PRR-017` |

The newly authorized public send succeeded functionally, closing the prior live
integration evidence gap. It measured `3116 ms`, exceeding the approved
`<=3000 ms` public semantic API contract by `116 ms`. The result is direct,
same-head evidence and therefore opens a blocking performance finding.

Current GitHub CI is also not usable merge evidence: workflow run
`29216231545`, job `86712598586`, failed with zero steps because recent account
payments failed or the spending limit must be increased.

## 3. Executive Summary

`PRR-001` through `PRR-016` remain resolved. The public `send_message` path now
has positive real-client evidence: it activated WeChat, switched from Contacts
to Chats, selected `文件传输助手`, verified the current chat title, clipboard-
drafted the configured message, pressed Return, and returned `success=true` and
`submitted=true`. The command ran once and was not retried.

The top-level result had `verified=false` because post-submit message read-back
was not requested. This is API-level submission proof, not delivery read-back.
No raw live payload is committed.

The remaining code work is performance-only. It must remove at least `116 ms`
from the representative path without bypassing frontmost-app identity, exact
target identity, current-frame coordinate derivation, or title postcondition.

## 4. Scope And Change Map

### Reviewed scope

- complete `origin/main...f2b98ed` feature diff and prior finding ledger;
- newly authorized public `send_message` result and child-operation timings;
- current PR head, CI run, and check annotation;
- the `<=3000 ms` performance contract in the reviewed design;
- existing deterministic tests and exact-code selector read/open proof.

### Excluded or unavailable scope

- post-submit message delivery read-back;
- a remediated public send timing result;
- a GitHub Actions run that reaches a runner;
- signed helper and real release publication.

| Area | Current result | Risk | Evidence |
|---|---|---|---|
| Functional send | Passed | Low | Verified title, clipboard draft, accepted Return, submitted true. |
| Send performance | Failed | Medium | `3116 ms`, contract maximum `3000 ms`. |
| Safety checks | Passed | Low | Frontmost, selector/action identity, frame-derived coordinate, title postcondition. |
| Existing selector APIs | Passed | Low | Prior non-zero live proof and deterministic suites. |
| Remote CI | Not executed | Unknown | GitHub Billing annotation, zero job steps. |

## 5. Finding

### `PRR-017` - Public send exceeds the three-second API contract

- Severity: `S2`
- Blocking: yes
- Confidence: high
- Category: performance
- Location: `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py:2574`

Observation: the representative public `send_message` operation completed
successfully in `3116 ms`. The approved performance contract requires each
public WeChat semantic API to complete within `3000 ms` in this environment.

Trigger: start with WeChat frontmost in Contacts, send to a visible
conversation, and execute the public focus, draft, and submit flow.

Impact: callers cannot rely on the documented three-second upper bound for the
public convenience API, even though all individual actions complete and the
target is correct.

Evidence:

- top-level `send_message`: `3116 ms`, `success=true`, `submitted=true`;
- chats selector query: `73 ms`;
- chats Accessibility action: `1042 ms` wall time, `734 ms` backend time;
- visible target query: `24 ms`, coordinate click: `482 ms`, title verify:
  `20 ms`;
- clipboard draft: `517 ms`, Return submit: `319 ms`.

Required remediation: remove bounded transport/startup overhead or make an
equivalent safe optimization. A warm Accessibility action transport is the
first candidate because the action currently pays roughly `308 ms` outside its
backend diagnostic. Do not replace or skip identity, frame, and semantic
postconditions merely to meet the timing target.

Verification: deterministic action-worker/fallback tests, package suites,
preflight, and one newly authorized public send measuring `<=3000 ms`.

## 6. Required Actions Before Merge

- [ ] Remediate `PRR-017` with safety-equivalent behavior.
- [ ] Run deterministic transport success, timeout, and fallback tests.
- [ ] Obtain new explicit authorization before another live send.
- [ ] Record a successful public `send_message <=3000 ms` result; do not retry
  an `unknown` submit result.
- [ ] Correct GitHub Billing and require green current CI.
- [ ] Reissue the frozen-head F6 decision.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security and privacy | Low | No delivery read-back was requested. | Represent evidence as submission only; feature maintainer. |
| Data integrity | Low | UI state can change between resolution and action. | Preserve exact preconditions and title postcondition; package owner. |
| Reliability | Low | Functional public integration now has positive evidence. | Keep one-shot unknown-result policy. |
| Performance | Medium | Public send exceeds the contract by 116 ms. | Resolve `PRR-017` and rerun authorized timing proof. |
| Deployment | Unknown | CI job never reached a runner. | Fix GitHub Billing and rerun unchanged workflow. |

## 8. Validation Evidence

### Automated evidence carried forward

| Check | Head | Result |
|---|---|---|
| Root unit suite | `ca6d4a8` | 127 passed in 42.09 s |
| `app-control-protocol` | `ca6d4a8` | 55 passed |
| `computer-use-macos` | `ca6d4a8` | 128 passed, 1 skipped |
| `wechat-desktop-tool` | `ca6d4a8` | 123 passed |
| Release preflight | `feb937d` | Passed; expected external-proof warnings only |
| Compile and diff checks | runtime/review heads | Passed |

### Newly authorized live evidence

| Field | Result |
|---|---|
| Target | `文件传输助手` only |
| Attempts | One |
| Target postcondition | Passed |
| Draft | Clipboard, no submit during draft phase |
| Submit | Return accepted; `sendAttempted=true` |
| Public result | `success=true`, `submitted=true` |
| Delivery read-back | Not requested; `verified=false` |
| Duration | `3116 ms`; performance contract failed |

The local service was stopped after evidence collection.

### Current CI

Run `29216231545`, job `86712598586`: failed before any step because of GitHub
Billing/spending limit. The macOS 26 runner-label notice is informational.

Overall validation status: `FAILED` because the measured API timing violates an
approved acceptance criterion.

## 9. Coverage And Limitations

- This report is valid only for
  `f2b98ed11da7a261f0e81ea8fb671cf5e633c4b2`.
- The live result proves API submission, not delivery read-back.
- One timing sample is sufficient to disprove a hard maximum but not to
  characterize percentiles.
- No sensitive raw payload or local smoke artifact is tracked.

## 10. Open Questions And Assumptions

### Open questions

1. Does a safety-equivalent warm action path bring public send below 3000 ms?
2. Do current checks pass after GitHub Billing is corrected?

### Assumptions

1. The observed top-level timing uses the same public SDK path consumers use.
2. WeChat in Contacts with a visible target is representative of the approved
   smoke environment.
3. A future live send requires new explicit authorization.

## 11. Non-Blocking Recommendations

- `NOTE-012`: remove the unreferenced private legacy focus implementation in a
  later cleanup.
- `NOTE-013`: add Ruff to development dependencies.

## 12. Machine-Readable Summary

Structured result:
[`pr-review-macos-computer-use-3-f2b98ed.json`](./pr-review-macos-computer-use-3-f2b98ed.json).

Decision: `REQUEST_CHANGES`. Blocking finding: `PRR-017`. External gate:
GitHub Billing must allow current CI to start and pass.
