# PR Review — `zhanghao1903/macos-computer-use#3` @ `435d945`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | zhanghao1903/macos-computer-use |
| Pull Request | [#3 — Add internal Accessibility selector engine](https://github.com/zhanghao1903/macos-computer-use/pull/3) |
| Author | zhanghao1903 |
| Base | main @ `fed652343ec73734247955d44dc8e60293a7b373` |
| Head | codex/accessibility-selector-engine @ `435d94574efa4cc3d27f7791f49bb991d450f24b` |
| Reviewed at | 2026-07-13T15:09:43Z |
| Reviewer | Codex (GPT-5) |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| GitHub state | `OPEN`, `DRAFT`, mechanical `MERGEABLE`, merge state `CLEAN` |
| Scope size | 106 commits; 94 changed files; 33,528 additions; 1,325 deletions |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false` under this Review Contract (GitHub mechanical mergeability is `true`)
- **Blocking findings:** 1 (`PRR-018`)
- **Rationale:** PRR-001 through PRR-017 remain resolved, and deterministic suites plus current CI are green. However, PRR-018 is an unresolved S1 blocking reliability defect: the real warm-worker framing can falsely time out after buffering a valid response, including after a mutating AX action has executed. The reviewed snapshot is therefore not safe to merge.

## 3. Executive Summary

The latest head contains the planned remediation for all 17 historical findings and keeps the selector, WeChat safety, packaging and release-proof contracts covered by deterministic tests. Re-review found one new high-confidence transport defect in the warm query/action worker: a valid response can remain in TextIOWrapper's buffer while the parent waits on an empty kernel fd, producing a false timeout and an unknown mutating-action result. Decision: REQUEST_CHANGES; fix PRR-018 and re-review the new head before changing the draft or merging.

## 4. Scope and Change Map

### Reviewed scope

- current GitHub PR metadata, 106-commit range, 94 changed files and full local main...head diff
- 29-commit remediation delta from the prior 07fa052 review through current head
- prior finding lifecycle PRR-001 through PRR-017
- selector matcher, cache, resolver, collection, failure and pagination paths
- WeChat list, open, focus, row identity, coordinate fallback, draft and send call paths
- warm query/action worker lifecycle, readiness framing, timeout and no-replay behavior
- package dependencies, wheel compatibility, CI/release workflow and privacy-safe proof v2
- isolated root/package tests, release preflight, compile, whitespace and targeted counterexamples

### Excluded or unavailable scope

- fresh real WeChat desktop mutation or message submission; no new authorization was provided
- signed/notarized helper application end-to-end execution
- real GitHub Release, TestPyPI or PyPI publication
- production logs and private raw smoke artifacts
- strict mypy baseline cleanup and Ruff lint, which was unavailable
- unrelated dirty and untracked files in the user's primary worktree

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Historical review remediation | Resolve privacy, focus, coordinate, ambiguity, helper, cache, failure, batch, pagination, dependency, workflow and proof findings. | Selector-backed WeChat operations fail closed and release proof is source-bound and sanitized. | Medium | PRR-001..PRR-017 lifecycle recheck, deterministic suites and current code inspection. |
| Warm Accessibility transport | Reuse persistent query and action subprocesses; action failures are not replayed after dispatch. | Direct-mode AX operations should avoid per-call framework startup. | High | Code review plus real _AccessibilityWorker framing counterexample; PRR-018 remains open. |
| WeChat semantic operations | Use verified open_contact, current-frame clicks, row identity and visible-window list semantics. | Existing semantic APIs preserve target identity and explicit submission boundaries. | Medium | 123 WeChat package tests, prior live evidence and call-path review. |
| Packaging and compatibility | Coordinate all package versions and dependency floors at 0.2.0 and reject incompatible wheel combinations. | Clean installs cannot pair the new WeChat wheel with old selector/config runtimes. | Low | 127 root tests include wheel build/install and 0.1.1 rejection. |
| CI, release and proof | Fix release source paths and require whitelist-only selector proof v2. | Release automation checks clean source paths and rejects sensitive, stale or empty proof. | Low | Release preflight passed; exact-head GitHub CI passed. |

## 5. Findings

### PRR-018 — `[S1][Blocking][reliability]` Warm worker 会丢失已缓冲的响应，并在动作已执行后误报超时

- **Location:** `packages/computer-use-macos/src/computer_use_macos/client.py:294-318` (`_AccessibilityWorker._read_response_line`) @ `435d94574efa4cc3d27f7791f49bb991d450f24b`
- **Confidence:** High
- **Status:** open
- **Observation:** _read_response_line() 在每次 TextIOWrapper.readline() 前都重新对 process.stdout 执行 select()。当 workerReady 行和首个请求响应同时到达时，第一次 readline() 可把两行都读入 Python 用户态缓冲区但只返回 workerReady；下一次 select() 只观察已经为空的内核文件描述符，于是等待到 deadline 并返回 timeout，尽管完整响应仍在 TextIOWrapper 中。当前 direct 模式的 query 与 action worker 都复用该协议，而 action path 不会 replay，以避免重复执行未知结果的桌面动作。
- **Trigger:** 首次 warm-worker 请求的处理很快，使 workerReady 与该请求的 JSON 响应在父进程消费 readiness 行之前都进入 stdout；快速 AXPress/AXSetFocus 或快速空查询均可满足该时序。
- **Impact:** 读取请求会发生虚假超时；更严重的是 mutating Accessibility action 可能已成功执行，却向调用方返回 TIMEOUT/unknown 并杀死 worker。调用方无法可靠判断桌面状态，人工恢复或重试可能再次作用于已经改变的 UI，也使本 PR 用 warm action worker 关闭性能门槛的核心路径不可靠。
- **Evidence:**
  - [code] 循环先 select 再读取 buffered TextIOWrapper；识别 workerReady 后直接 continue，没有先消费或确认缓冲区中可能已有的响应。 — `packages/computer-use-macos/src/computer_use_macos/client.py:294-318`
  - [code] direct client 默认启动 query/action 两个 warm worker，action 请求一旦交给 worker 就不回退重放。 — `packages/computer-use-macos/src/computer_use_macos/client.py:396-416,1415-1431`
  - [reproduction] 在 Darwin 25.5.0 arm64 / CPython 3.12.7 上，让真实 _AccessibilityWorker 子进程先输出 workerReady，再对请求立即输出一行 JSON；20/20 次在 timeout=0.2s 时误超时，单次 timeout=2.0s 仍误超时。独立复核以同一协议运行 100 次，复现 79 次虚假超时。 — `reviewer synthetic _AccessibilityWorker protocol reproduction`
  - [test] 现有 action-worker tests 注入 FakeAccessibilityQueryWorker，worker-script tests 只 compile/grep 源码；没有启动真实 _AccessibilityWorker 验证 readiness/response framing。 — `packages/computer-use-macos/tests/test_package.py:1361-1481,1771-1783`
- **Required change:** 把 readiness 作为明确的启动握手，在 start() 返回及写入首个请求前消费并校验；或改用 fd-level/unbuffered framing、专用 reader thread/queue 等能同时尊重用户态缓冲区与 deadline 的实现。必须保持 action dispatch 后不自动 replay 的安全边界，并让每个请求与唯一响应可靠对应。
- **Verification:** 新增使用真实 subprocess/_AccessibilityWorker 的协议回归测试：worker 无延迟连续输出 workerReady 与响应，至少重复 100 次，query/action 均要求零虚假 timeout、零丢失/串线响应；另验证 action 已 dispatch 后的真实 timeout 仍不 replay。

### Prior finding lifecycle

The historical IDs remain stable. Re-review confirmed these findings are still resolved:

| Finding | Status | Current closure evidence |
|---|---|---|
| `PRR-001` | Resolved | Whitelist-only proof v2; sensitive/stale/legacy proof rejected. |
| `PRR-002` | Resolved | Unknown search focus fails before text or Return. |
| `PRR-003` | Resolved | Only current verified AX frames may produce coordinate fallback. |
| `PRR-004` | Resolved | Two-candidate ambiguity is checked before action. |
| `PRR-005` | Resolved | Unsupported helper-backed selector use fails at construction. |
| `PRR-006` | Resolved | Cache hits revalidate full matcher/actions/constraints. |
| `PRR-007` | Resolved | Backend query failures preserve cause and do not become not-found. |
| `PRR-008` | Resolved | Batch collection depth is capped at the shared limit. |
| `PRR-009` | Resolved | N+1 lookahead is separated from real truncation. |
| `PRR-010` | Resolved | All package versions/floors are coordinated at 0.2.0. |
| `PRR-011` | Resolved | Release WeChat tests include every workspace source root. |
| `PRR-012` | Resolved | Strict proof requires non-zero consistent semantic collections. |
| `PRR-013` | Resolved | Public focus/send delegates to verified open_contact. |
| `PRR-014` | Resolved | Explicit AX target application identity is verified. |
| `PRR-015` | Resolved | Row actionRefs require exact current identity. |
| `PRR-016` | Resolved | Visible-window lists expose no synthetic continuation token. |
| `PRR-017` | Resolved | Representative public send met the approved three-second feature gate. |

## 6. Required Actions Before Merge

- [ ] `PRR-018` — 修复 warm-worker readiness/response framing，加入真实 subprocess 协议回归测试，并证明快速 query/action 响应不会误超时且 mutating action 仍不会在未知结果后 replay。

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| security-privacy | Low | 真实 WeChat raw observations 和本机路径仍可能存在于私有调试产物。 | 继续只发布 whitelist proof v2，并保持 raw artifacts untracked。 / feature maintainer |
| data-integrity | High | PRR-018 可在动作已执行后返回 timeout，使调用方对当前桌面状态产生错误认知。 | 可靠消费 worker 响应；未知 dispatch 结果继续禁止自动 replay，并要求调用方人工恢复。 / computer-use-macos |
| reliability-concurrency | High | ready/response 时序与两层缓冲会让 warm worker 丢失可见响应并误超时。 | 解决 PRR-018，并用真实 worker 的快速、重复、首请求和连续请求测试覆盖 framing。 / computer-use-macos |
| performance-scalability | High | 虚假等待完整 timeout 会抵消 warm worker 的延迟收益，并使代表性单次性能证据不稳定。 | 修复 framing 后重跑确定性测试，并对首次与热路径各采集至少一个代表性 live 样本。 / feature maintainer |
| api-compatibility | Medium | 返回 TIMEOUT 与实际 AX action outcome 可能不一致，破坏调用方的恢复契约。 | 确保一请求一响应，并保留明确的 non-retryable unknown-outcome 语义。 / computer-use-macos |
| deployment-rollback | Medium | direct mode 默认启用 warm query/action workers，问题会进入主运行路径。 | 在修复前回退 warm action slice 或禁用不可靠 worker；修复后以 exact-head CI 和协议反例作为 gate。 / feature maintainer |
| maintainability | Low | PR body 仍引用旧 07fa052 REQUEST_CHANGES 状态，而仓库内文档又声明 5a010da APPROVE。 | 修复 PRR-018 后把 PR body 和 merge-readiness 同步到同一个最新 Review Contract。 / feature maintainer |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s tests` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | 127 tests passed in 82.215 seconds, including wheel build/install, API smoke, release preflight and incompatible 0.1.1 dependency rejection. |
| `PYTHONPATH=packages/app-control-protocol/src .venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | 55 tests passed. |
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | 132 tests passed and 1 skipped. |
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | 123 tests passed. |
| `env -u PYTHONPATH .venv/bin/python scripts/release_preflight.py` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | Required source, docs, API, config, workflow and package gates passed; unavailable external proof and socket checks remained explicit warnings. |
| `.venv/bin/python -m compileall -q packages examples scripts tests` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | Python compilation passed. |
| `git diff --check fed652343ec73734247955d44dc8e60293a7b373...435d94574efa4cc3d27f7791f49bb991d450f24b` | isolated clone; git; head 435d94574efa4cc3d27f7791f49bb991d450f24b | PASS | 0 | No whitespace errors. |
| `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -c '<real _AccessibilityWorker emits workerReady then immediate JSON response; 20 runs; timeout=0.2s>'` | Darwin 25.5.0 arm64; isolated clone; CPython 3.12.7; head 435d94574efa4cc3d27f7791f49bb991d450f24b | FAIL | 0 | 20 of 20 requests returned CommandResult(returncode=124, timed_out=True) even though the child emitted a valid response; a separate 2.0-second run also falsely timed out. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| [CI / test — run 29249789405, job 86815256378](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29249789405/job/86815256378) | 2026-07-13T14:57:06Z | PASS | Exact current head completed successfully; GitHub reports the PR mechanically mergeable and merge state CLEAN. |

### Checks not run

- **fresh real WeChat selector/send smoke:** Would inspect or mutate a real desktop and could submit a message; no new authorization was provided. Prior 5a010da live evidence was reviewed but not represented as a current rerun.
- **signed helper app and real release publication:** These are later F7 external gates and would change external state.
- **Ruff:** The project environment has no ruff module or executable.
- **strict mypy:** Prior review recorded a broad mixed baseline; the worker framing defect is runtime/protocol behavior and the available mypy run would not distinguish it.

Overall validation status: `FAILED` because the targeted worker-protocol counterexample fails, despite all existing suites and CI passing.

## 9. Coverage and Limitations

- **Reviewed:** full PR diff; 29-commit remediation delta; all historical finding paths; query/action worker; WeChat semantic actions; packaging, proof and workflows.
- **Not reviewed live:** fresh real WeChat mutation, signed helper, TestPyPI/PyPI and GitHub Release execution.
- **Missing context:** no private raw smoke payload was accessed; no new live desktop authorization was provided.
- **Staleness condition:** any head other than `435d94574efa4cc3d27f7791f49bb991d450f24b` requires re-review.
- No fresh real WeChat action was performed; deterministic and synthetic tests cannot replace real desktop proof after PRR-018 is fixed.
- The repository's prior 5a010da APPROVE report predates the current head and did not exercise real _AccessibilityWorker readiness framing.
- Ruff was unavailable and strict mypy was not rerun.
- Signed helper, TestPyPI/PyPI and actual GitHub Release publication were not executed.
- The user's primary worktree is dirty; code validation used an isolated clone, and only this report pair is added to the primary worktree.

## 10. Open Questions and Assumptions

### Open questions

None.

### Assumptions

1. The TextIOWrapper/select buffering behavior reproduced on Darwin CPython 3.12.7 is representative of the supported direct-mode runtime.
2. Mutating Accessibility actions must remain non-replayable after uncertain dispatch.
3. The current head differs from implementation head 5a010da only by documentation/review artifacts, so prior exact-code live evidence remains historical context but not a substitute for fixing PRR-018.
4. Pre-existing exact-name matching concerns not introduced or expanded by this PR do not block this review.

## 11. Non-blocking Recommendations

- **NOTE-012 [maintainability]** 在后续清理未引用的 legacy private focus implementation。 减少重复的可执行安全逻辑，同时独立保留兼容配置解析。
- **NOTE-013 [testing]** 把 Ruff 加入开发依赖或明确移除不可执行的 lint gate。 使静态检查在干净环境中可重复。
- **NOTE-014 [performance]** 若三秒目标升级为运行 SLO，应收集重复样本和 percentile，而不是只保存单次代表值。 区分功能验收样本与稳定性能保证。
- **NOTE-015 [documentation]** 修复 PRR-018 后同步 GitHub PR body、merge-readiness 和最新 head 报告链接。 避免外部 PR 描述仍指向 07fa052 REQUEST_CHANGES，而仓库文档指向过期的 5a010da APPROVE。

## 12. Machine-readable Summary

- Result file: [`pr-review-macos-computer-use-3-435d945.json`](./pr-review-macos-computer-use-3-435d945.json)
- Schema: `.agents/skills/pr-review/schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.0"
decision: REQUEST_CHANGES
mergeable: false
head_sha: 435d94574efa4cc3d27f7791f49bb991d450f24b
blocking_findings:
  - PRR-018
validation_status: FAILED
report_status: CURRENT
```

