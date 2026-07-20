# Merge Readiness: WeChat Tool Internal Modularization

## Review Snapshot

| Field | Value |
| --- | --- |
| Repository | `zhanghao1903/macos-computer-use` |
| Branch | `codex/wechat-tool-modularization` |
| Base | `main` @ `23d293d01245f3c46c67c5be6a6553a989d14e0a` |
| Reviewed implementation head | `9a90340bae4204ab8898db89ccf3148a35f9da57` |
| Reviewed at | 2026-07-20 (Asia/Shanghai) |
| Review kind | Initial implementation self-review |
| Decision | `READY_TO_OPEN_PR` |
| Blocking findings | 0 |
| CI state | Pending until the PR is opened |

This is the F6 lifecycle carrier, not a published platform approval. The
review covers the complete base-to-head implementation and F5 verification
snapshot. The commit adding this document is documentation-only and must pass
a post-commit diff check and final-head CI before merge.

## Intent And Contract

The change replaces a 6979-line multi-domain implementation module with a
344-line public facade and 12 cohesive private modules. Its contract is strict
behavior preservation: application developers keep the same imports,
signatures, commands, observations, failures, configuration, safety decisions,
and desktop call sequences.

No version bump, migration, selector update, control-map update, public export,
protocol change, dependency change, or release publication is included.

## Change Map

| Area | Main change | External behavior | Risk | Review evidence |
| --- | --- | --- | --- | --- |
| Facade and runtime | Move dependency state and child-command helpers behind `WeChatToolRuntime`; keep public wrappers and explicit dispatch | None | High | Constructor/signature locks, exact command traces, facade/runtime tests |
| Query, parsing, diagnostics | Move pure normalization, row parsing, failures, timing, evidence, and redaction | None | Medium | Slice AST checks, focused suites, full historical suite |
| Action safety and execution | Isolate mutation proof, fallback, actionRef, and mapped-control logic | None | High | Contradictory/malformed/unknown evidence and no-replay tests |
| Domain workflows | Move window, collection, contact/search, and message orchestration | None | High | Per-domain focused suites and unchanged child-command/result assertions |
| Test organization | Split the historical regression module and add direct module tests and structural gates | None | Medium | 138/138 method inventory with zero changed ASTs; 254 tests pass |
| Packaging and docs | Require every private module in archives; document stable ownership and release record | None | Low | Real wheel/sdist preflight and isolated wheel API smoke |

The full 50-file base-to-head diff was classified. No production file changed
in `app-control-protocol` or `computer-use-macos`; production changes are
limited to the WeChat facade/private-module rearrangement plus type-only
narrowing in existing WeChat files.

## Findings

No blocking or non-blocking correctness findings were identified for the
reviewed snapshot.

The review specifically searched for:

- constructor timing or validation-order changes;
- dispatch exception-scope and unsupported-operation changes;
- altered command ids, phases, inputs, timeouts, query bounds, or round trips;
- replay after attempted, dispatched, contradictory, malformed, or unknown
  mutation evidence;
- coordinate fallback without a current validated Accessibility frame;
- redaction or raw Accessibility data regressions;
- contact ambiguity, truncation, input-focus, or submit-uncertainty weakening;
- public export/signature/config/dependency changes;
- import cycles, facade reverse edges, missing archive content, and lost tests.

The implementation and tests provide discriminating evidence against each of
those failure classes. Private helper import locations and writable private
instance fields are not supported application contracts; the design records
their internal movement explicitly.

## Merge Gates

### Completed

- [x] F0 repository hygiene and isolated feature branch.
- [x] F1 requirements and behavior-preservation acceptance criteria.
- [x] F2 technical design and package boundary.
- [x] F3 implementation slices, rollback strategy, and test plan.
- [x] F4 implementation, per-slice tests, notes, commits, and pushes.
- [x] F5 full source, static, archive, and isolated-install verification.
- [x] Stable architecture document updated.
- [x] `CHANGELOG.md` has an `Unreleased / Internal` entry.
- [x] No token, raw Accessibility capture, local smoke JSON, wheel, sdist,
  virtual environment, or generated proof file is tracked.
- [x] Local branch and remote feature branch matched at the reviewed head.

### Required Before Merge

- [ ] Open the PR from `codex/wechat-tool-modularization` to `main`.
- [ ] Confirm GitHub Actions is green on the final PR head.
- [ ] Re-run review if base/head changes beyond this F6 documentation commit or
  CI-driven fixes.

There is no code remediation required before opening the PR.

## Verification Summary

Detailed command, duration, artifact, hash, and limitation evidence is in
[`verification.md`](./verification.md). The decisive results are:

- root 148, protocol 55, computer-use 168, and WeChat 254 tests passed;
- one existing Unix-socket test skipped because the sandbox cannot bind;
- release-preflight unit suite: 111 passed;
- strict Ruff, mypy (29 files), compileall, and diff checks passed;
- old split inventory: 138 before, 138 after, zero missing/added/changed ASTs;
- facade: 344 lines; all private modules below 1500; split files below 2500;
- six real wheel/sdist artifacts passed metadata and content preflight;
- all three real wheels installed offline into a clean venv and passed API
  smoke from the installed paths.

## Residual Risk

| Category | Level | Residual risk | Mitigation |
| --- | --- | --- | --- |
| Security and privacy | Low | A movement error could expose raw evidence or sensitive text | Existing redaction/raw-boundary regressions and exact observations pass |
| Mutation safety | Low | A movement error could authorize a fallback after unknown action effect | No-replay truth tables and cross-package mutation-count tests pass |
| API compatibility | Low | Unsupported consumers may import or monkeypatch private helpers | Public exports/signatures are frozen; private movement is documented |
| Packaging | Low | A new private module could be omitted from an archive | Deterministic content gates plus real wheel/sdist preflight pass |
| Performance | Low | Python call indirection could add negligible local overhead | No desktop round trip or query changed; release live 3000 ms proof remains required |
| Reviewability | Low | Large historical fixtures remain costly to navigate | Split ownership and 2500-line maintenance alarms are enforced |

Real WeChat and helper external proofs were not refreshed because this branch
does not alter desktop behavior or publish a release. The next coordinated
release must refresh the existing safety and API-latency proof. This is a
documented residual proof obligation, not evidence claimed by this review.

## Lifecycle Commit Ledger

| Phase or slice | Commit |
| --- | --- |
| F0 intake | `94caec9` |
| F1 requirements | `8fbba74` |
| F2 design | `4f4d674` |
| F3 plan | `420a51a` |
| I0 behavior lock | `212c14a` |
| I1 diagnostics | `7e3ece2` |
| I2 query mapping | `915222e` |
| I3 row parsing | `03c442f` |
| I4 action safety | `59bd1bd` |
| I5 runtime | `7b459e4` |
| I6 action/mapped controls | `f63011b` |
| I7a window operations | `bd4bed1` |
| I7b collection operations | `a0177d5` |
| I7c contact operations | `c925781` |
| I7d message operations | `9ab8c28` |
| I8 test/docs/package finish | `af70630` |
| F5 verification | `9a90340` |

Every listed commit is present on the pushed feature branch. The F6 commit
carrying this document is recorded by Git history and the PR after it is
created.

## Rollback

The complete change can be reverted as one PR without data migration, version
coordination, or configuration rollback. Each extraction slice is also an
independent commit, but partial rollback should proceed in reverse dependency
order from I8 through I1. No persisted data or external state is introduced.

## Proposed Pull Request

### Title

`refactor: modularize WeChat desktop tool internals`

### Description

```markdown
## Problem

`wechat_desktop_tool.tool` had grown to 6979 lines and combined public dispatch,
runtime transport, Accessibility normalization, action safety, contact flows,
and message flows. The matching regression test file had the same ownership
problem, making local changes difficult to review safely.

## Solution

- Keep `WeChatDesktopTool` as a 344-line public facade and explicit dispatcher.
- Move runtime, diagnostics, query mapping, row parsing, action safety,
  action/mapped-control orchestration, and domain workflows into 12 private
  modules with an acyclic dependency graph.
- Split the historical regression suite without changing any of its 138 test
  method bodies, and add direct module, size, dependency, and package-content
  gates.
- Update the stable architecture map and add an `Unreleased / Internal` record.

## Compatibility

No public API, protocol, config, command, observation, failure, selector,
control-map, timeout, safety decision, desktop call sequence, dependency, or
version changes. Application developers do not need to migrate.

## Verification

- Root: 148 passed.
- `app-control-protocol`: 55 passed.
- `computer-use-macos`: 168 passed, 1 sandbox socket skip.
- `wechat-desktop-tool`: 254 passed.
- Release-preflight tests: 111 passed.
- Ruff, strict mypy, compileall, and `git diff --check`: passed.
- Six real wheel/sdist artifacts: content preflight passed.
- Clean offline wheel install: all three package API smoke snippets passed.

Full evidence: `docs/feature/wechat-tool-modularization/verification.md`.

## Release Record

`CHANGELOG.md` records this under `Unreleased / Internal`. No version bump or
release publication is part of this PR. Real WeChat performance/safety proof is
deferred to the next coordinated release because desktop behavior is unchanged.
```

## F6 Decision

The reviewed implementation is ready to open as a non-draft PR. Merge remains
conditional on green GitHub Actions for the final head.
