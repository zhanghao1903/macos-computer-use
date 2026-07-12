# PR Review: `zhanghao1903/macos-computer-use#3` @ `feb937d`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository / PR | [zhanghao1903/macos-computer-use#3](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Title | Add internal Accessibility selector engine |
| Author | `zhanghao1903` |
| Base | `main` @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | `codex/accessibility-selector-engine` @ `feb937d7aaac0aff9747dd802e03d5d6eb063707` |
| Reviewed at | 2026-07-12T16:32:22Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |

The title and author are carried forward from the prior frozen review. Local
refs prove the base/head SHAs and pushed branch equality. GitHub metadata and
current checks could not be refreshed because the local-action approval service
had reached its usage limit.

## 2. Decision

| Decision | Mergeable | Open blocking findings |
|---|---:|---|
| `INCOMPLETE` | `unknown` | none identified |

`PRR-001` through `PRR-016` are resolved in the reviewed source and named
deterministic counterexamples pass. Approval is still withheld because the
required exact-code public `send_message` smoke to `文件传输助手` did not execute,
and current GitHub CI could not be observed. These are evidence gaps rather than
known code defects.

## 3. Executive Summary

The latest remediation unifies public focus/send with verified
`open_contact`, enforces app identity for target-app-only AX operations, adds
exact identity preconditions to row actionRefs, and makes list pagination
honestly visible-window-only. Fresh static review also moved unlabeled-row
rejection ahead of every action and coordinate path while keeping public
semantic element labels clean.

Local unit, package, wheel, preflight, compile, and diff checks pass. The next
action is not another code change: capture one non-retried live send result on
the authorized target and confirm current PR CI, then reissue the merge decision.

## 4. Scope and Change Map

### Reviewed scope

- complete local `origin/main...feb937d` change set and prior review contracts;
- remediation delta from `2bf6faf` through `feb937d`;
- public `focus_contact` and `send_message` call paths;
- query/action app allowlisting and worker process selection;
- row actionRef creation, execution, coordinate fallback, and identity failure;
- list visible-window pagination, CLI dry-run, release preflight, tests, and
  stable developer documentation.

### Excluded or unavailable scope

- exact-code live `send_message` execution; process creation was rejected by
  the approval service before any desktop action;
- current GitHub Actions/check status;
- signed helper end-to-end execution and real package/release publication;
- Ruff, which is not installed; broad existing mypy cleanup is out of scope.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Public WeChat send | `focus_contact` delegates to verified `open_contact`. | Send verifies the requested chat before draft/submit. | High | Call-path review and no-hotkey sequence tests. |
| AX target identity | Query/action validate allowlist and infer configured bundle. | Explicit targets cannot silently resolve to another frontmost app. | High | Positive bundle and unallowlisted-target tests plus worker source review. |
| Row actions | Exact row label is required in `labelIn`; unlabeled rows fail before action/click. | Reordered or unverifiable rows cannot be pressed through a stale ref. | High | Changed-label, matching-label, no-label, and zero-command tests. |
| Pagination | Lists expose `mode=visibleWindow`, null continuation, and reject tokens. | Callers cannot loop over duplicate synthetic pages. | Medium | No-token and supplied-token tests. |
| Docs/preflight | Dry-run and public docs match selector-backed behavior. | Integrators see the actual command and recovery contract. | Low | Exact-head release preflight. |

## 5. Findings

No new open finding was identified for this snapshot.

### Current finding ledger

| ID | Status | Closure evidence on `feb937d` |
|---|---|---|
| `PRR-001` | resolved | Whitelist-only source-bound proof v2 and validate-before-copy release gate. |
| `PRR-002` | resolved | Unknown search focus emits no clear/type/Return command. |
| `PRR-003` | resolved | Actions use current bounded AX frames and semantic postconditions, not packaged coordinates. |
| `PRR-004` | resolved | Two same-name candidates fail before action. |
| `PRR-005` | resolved | Unsupported WeChat helper mode fails during construction. |
| `PRR-006` | resolved | Cache hits reapply matcher, state, relation, action, frame, and signature checks. |
| `PRR-007` | resolved | Query backend failures remain distinct from successful empty results. |
| `PRR-008` | resolved | Collection batch depth is normalized and capped at 8. |
| `PRR-009` | resolved | N+1 lookahead is pagination evidence, not incomplete extraction. |
| `PRR-010` | resolved | Coordinated `0.2.0` floors reject mixed `0.1.1` dependencies. |
| `PRR-011` | resolved | Clean release WeChat tests include every required source path. |
| `PRR-012` | resolved | Strict proof validates source SHA, counts, timings, keys, and privacy canaries. |
| `PRR-013` | resolved in code; live proof pending | `focus_contact` delegates to `_open_contact`; `send_message` uses it; tests assert selector query/action/title verification and no global-search hotkey. |
| `PRR-014` | resolved | Query/action reject unallowlisted targets, infer configured bundles, and verify target-app-only frontmost identity. |
| `PRR-015` | resolved | Row refs require exact `labelIn`; execution rejects missing identity; unlabeled framed rows emit zero commands. |
| `PRR-016` | resolved | `nextPageToken` is always null and non-null input returns `pagination_not_supported` before app-control work. |

## 6. Required Actions Before Merge

No additional code remediation is currently required.

- [ ] Run the documented exact-code `send_message` smoke once against
  `文件传输助手`; do not retry an unknown post-submit result.
- [ ] Observe current GitHub Actions for the final code/doc head.
- [ ] Re-run the short F6 decision audit after those two evidence gates pass.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | Low | Real target switching was not rerun after the compatibility change. | One authorized exact-code smoke; target restricted to `文件传输助手`. |
| Data integrity | Low | Desktop state can still change between resolution and action. | Exact label preconditions, short-lived refs, and target-title postcondition. |
| Reliability | Medium | Live wrapper integration remains unproven on this head. | Capture the single live send result before merge. |
| Performance | Low | New wrapper adds no unbounded search, but final live duration is unknown. | Existing `open_contact` proof is under 3 s; record final wrapper timing. |
| API & compatibility | Low | Non-null list tokens now fail instead of repeating page one. | Stable docs and migration notes describe visible-window-only behavior. |
| Deployment & rollback | Unknown | Current remote CI was not observed. | Confirm PR checks; rollback is the scoped remediation commits. |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit | Notes |
|---|---|---|---:|---|
| Root `unittest discover -s tests` | macOS, Python 3.12, code head `ca6d4a8` | PASS | 0 | 127 tests; includes wheel/preflight orchestration. Review head adds verification docs only. |
| Protocol package tests | same | PASS | 0 | 55 tests. |
| macOS package tests | same | PASS | 0 | 128 tests, 1 platform-conditional skip. |
| WeChat package tests | same | PASS | 0 | 123 tests. |
| `scripts/release_preflight.py --json` | exact review head `feb937d` | PASS | 0 | Public API/docs/config/workflow/dry-run checks passed; external proof warnings remain. |
| `compileall -q packages examples scripts tests` | code head `ca6d4a8` | PASS | 0 | No syntax failures. |
| `git diff --check origin/main...HEAD` | exact review head `feb937d` | PASS | 0 | No whitespace errors. |
| strict mypy | working tree after `5aa6266` | FAIL | 1 | Existing broad baseline: 184 errors in 15 files; not a merge gate for this scoped remediation. |

### CI / platform checks observed

No current check result was observed. The latest previously observed CI was
green for the earlier reviewed head, but it is not evidence for `feb937d`.

### Checks not run

- exact-code live `send_message` smoke: local-action escalation was rejected
  after the approval service reached its usage limit; no process or message ran;
- current PR checks: GitHub CLI execution was blocked by the same approval limit;
- Ruff: executable/module unavailable;
- signed helper and real release publication: outside this feature merge gate.

Overall validation status: `PARTIAL`.

## 9. Coverage and Limitations

- This report is valid only for
  `feb937d7aaac0aff9747dd802e03d5d6eb063707`; any runtime-source commit makes it
  stale.
- Local `origin/main` was used as the frozen base because remote fetch/PR reads
  were unavailable during this review.
- The existing exact-head selector read/open proof remains strong evidence for
  the shared `open_contact` implementation, but it is not a substitute for the
  required public `send_message` wrapper proof.
- Unrelated dirty skill, README, generated output, build, and lock files were
  excluded from review commits.

## 10. Open Questions and Assumptions

### Open questions

1. When the local-action approval service becomes available, does the one-shot
   public send smoke return success and stay within the 3000 ms API target?
2. Are the current GitHub checks green for the pushed final code head?

### Assumptions

1. The pushed local tracking ref accurately represents PR #3 head; local
   `HEAD` and `origin/codex/accessibility-selector-engine` were equal.
2. The documentation-only commit after `ca6d4a8` does not change runtime test
   behavior.
3. User authorization remains restricted to one message to `文件传输助手`.

## 11. Non-blocking Recommendations

- `NOTE-012` - Remove the now-unreferenced private legacy focus implementation
  in a later cleanup after this merge gate; keeping the compatibility config
  fields is independent of retaining dead executable code.
- `NOTE-013` - Add Ruff to the development dependency group so configured lint
  checks are reproducible instead of environment-dependent.

## 12. Machine-readable Summary

Structured result:
[`pr-review-macos-computer-use-3-feb937d.json`](./pr-review-macos-computer-use-3-feb937d.json).

Decision: `INCOMPLETE`. Open code findings: none. Remaining evidence gates:
exact-code live public send and current GitHub CI.
