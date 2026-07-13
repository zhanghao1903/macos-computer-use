# PR Review: `zhanghao1903/macos-computer-use#3` @ `a49c57e`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository / PR | [zhanghao1903/macos-computer-use#3](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Title | Add internal Accessibility selector engine |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `a49c57ef26a471b0e28f89223554895de3bcf8fd` |
| Reviewed at | 2026-07-12T16:53:03Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |

GitHub reports PR #3 open, draft, and mergeable. Local `HEAD`, the pushed
tracking branch, and the PR head identify the same frozen snapshot.

## 2. Decision

| Decision | Mergeable | Open blocking findings |
|---|---:|---|
| `INCOMPLETE` | yes | none identified |

No additional code defect was identified. `PRR-001` through `PRR-016` remain
resolved, and no runtime source changed after the passing remediation suites.
Approval is withheld for two evidence gates: the public send smoke has not yet
succeeded, and current GitHub CI could not start because of an external
Billing/spending-limit condition.

## 3. Executive Summary

The implementation provides a bounded internal Accessibility selector engine,
packaged WeChat control maps, target-app identity verification, exact row
actionRef identity, verified contact switching, visible-window list semantics,
configuration override support, performance diagnostics, and privacy-safe
release proof.

The user-authorized public smoke ran exactly once against `文件传输助手`. Codex
remained frontmost after bounded focus recovery, so the operation returned
`not_ready` before any Accessibility query/action, contact click, text entry,
draft, submit, or send. It was not retried. This confirms fail-closed target
identity but is not successful send evidence.

GitHub workflow run `29200626621`, job `86671264119`, failed before any step
started. The check annotation states that recent account payments failed or
the spending limit must be increased. No workflow or product-code change is
indicated.

## 4. Scope And Change Map

### Reviewed scope

- complete `origin/main...a49c57e` feature change set and prior review ledger;
- runtime remediation through `ca6d4a8` and documentation-only commits after it;
- one-shot public `send_message` behavior at the target-app identity boundary;
- current GitHub PR metadata and check-run annotation;
- existing unit, package, wheel, preflight, compile, and diff evidence.

### Excluded or unavailable scope

- a successful public message submission;
- a GitHub Actions run that starts and executes repository checks;
- signed helper end-to-end execution and real package/release publication;
- Ruff, which is not installed; broad existing mypy cleanup is out of scope.

| Area | Current result | Risk | Evidence |
|---|---|---|---|
| Selector engine | Implemented and regression-tested. | Low | 127 root tests plus package suites. |
| Public WeChat send | Uses verified contact path and fails closed on wrong frontmost app. | Medium | One-shot live attempt; no side-effect commands. |
| Row/action identity | Exact AXRow identity required before action or coordinate fallback. | Low | Named changed/missing-label counterexamples. |
| Pagination | Visible-window-only with null continuation and token rejection. | Low | API tests and stable docs. |
| Remote CI | Runner did not start because of GitHub Billing. | Unknown | Check-run failure annotation. |

## 5. Findings

No new open finding was identified for this snapshot.

| Finding range | Status | Closure |
|---|---|---|
| `PRR-001` through `PRR-012` | Resolved | Prior remediation, release proof, packaging, and exact-head verification. |
| `PRR-013` | Resolved in code; successful live proof pending | Public focus/send delegates to verified `open_contact`; one-shot wrong-frontmost attempt failed closed before side effects. |
| `PRR-014` | Resolved | Explicit AX targets are allowlisted and app identity is proven. |
| `PRR-015` | Resolved | Row actionRefs require exact identity; unlabeled rows emit no action/click. |
| `PRR-016` | Resolved | Visible-window lists return null continuation and reject supplied tokens. |

## 6. Required Actions Before Merge

No additional code remediation is currently required.

- [ ] Correct the GitHub account Billing/spending-limit condition.
- [ ] Rerun the existing workflow unchanged and require green current checks.
- [ ] Capture one successful public send smoke where WeChat can remain
  frontmost, restricted to `文件传输助手`.
- [ ] Do not retry an `unknown` submit result; inspect message state manually.
- [ ] Reissue the F6 decision after both evidence gates pass.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security and privacy | Low | A successful target switch/send was not observed on this head. | One restricted smoke; feature maintainer. |
| Data integrity | Low | Desktop state can change between resolution and action. | Exact identity preconditions and title postcondition; package owner. |
| Reliability | Medium | Public wrapper success remains unproven live. | Capture one successful non-retried smoke. |
| Performance | Low | Wrong-frontmost recovery took 2.941 s before fail-closed stop. | Existing successful semantic APIs are below 3 s; record successful wrapper timing. |
| Deployment | Unknown | Current CI executed no repository step. | Fix GitHub Billing and rerun unchanged workflow. |

## 8. Validation Evidence

### Automated regression

| Check | Head | Result |
|---|---|---|
| Root unit suite | `ca6d4a8` | 127 passed in 42.09 s |
| `app-control-protocol` | `ca6d4a8` | 55 passed |
| `computer-use-macos` | `ca6d4a8` | 128 passed, 1 skipped |
| `wechat-desktop-tool` | `ca6d4a8` | 123 passed |
| Release preflight | `feb937d` | Passed; expected external-proof warnings only |
| Compile and diff checks | runtime/review heads | Passed |

The commits from `ca6d4a8` through `a49c57e` contain verification and review
documentation only, so they do not alter the tested runtime.

### One-shot live smoke

| Step | Duration | Result |
|---|---:|---|
| `open_app` | 86 ms | Accepted |
| Initial `observe` | 539 ms | Expected WeChat, observed Codex |
| Bounded `focus_app` | 2132 ms | Accepted |
| Post-focus `observe` | 184 ms | Codex still frontmost; stopped |

Overall public result: `not_ready`; zero contact/message side effects; no
retry. The local service was stopped after the attempt.

### Current CI

Workflow run `29200626621`, job `86671264119`: `FAILURE` before any step. The
failure annotation identifies GitHub Billing/spending limit. The
`macos-latest` migration annotation is informational and did not cause this
run's failure.

Overall validation status: `PARTIAL`.

## 9. Coverage And Limitations

- This report is valid only for
  `a49c57ef26a471b0e28f89223554895de3bcf8fd`; a runtime-source commit makes it
  stale.
- The failed live attempt proves target-app fail-closed behavior, not successful
  contact selection or submission.
- A check that never reached a runner is not repository CI evidence.
- Unrelated dirty and generated workspace files remain excluded.

## 10. Open Questions And Assumptions

### Open questions

1. Does the public send complete within 3000 ms when WeChat remains frontmost?
2. Do all current checks pass after GitHub Billing is corrected?

### Assumptions

1. Runtime behavior at `a49c57e` is identical to tested code head `ca6d4a8`.
2. User authorization remains restricted to `文件传输助手` and does not permit
   retrying an unknown outcome.
3. The GitHub failure annotation accurately reflects an account-level gate.

## 11. Non-Blocking Recommendations

- `NOTE-012`: remove the unreferenced private legacy focus implementation in a
  later cleanup while retaining compatibility configuration parsing.
- `NOTE-013`: add Ruff to development dependencies so the configured lint gate
  is reproducible.

## 12. Machine-Readable Summary

Structured result:
[`pr-review-macos-computer-use-3-a49c57e.json`](./pr-review-macos-computer-use-3-a49c57e.json).

Decision: `INCOMPLETE`. Open code findings: none. Remaining evidence gates: a
successful restricted public send and a green CI run after GitHub Billing is
corrected.
