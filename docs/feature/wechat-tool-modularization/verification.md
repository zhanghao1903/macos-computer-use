# Verification: WeChat Tool Internal Modularization

## Status

| Field | Value |
| --- | --- |
| Feature | WeChat Tool Internal Modularization |
| Branch | `codex/wechat-tool-modularization` |
| Verified code commit | `af70630c1028bece0b92ea6ca499d17e2ed64838` |
| Verification date | 2026-07-20 |
| Lifecycle phase | F5 complete |
| Result | Pass; ready for F6 implementation review |
| Public behavior | Unchanged |

This record verifies the implementation against
[`requirements.md`](./requirements.md), using workspace source, built archives,
and an isolated wheel installation. Generated artifacts and virtual
environments were kept outside the repository.

## Acceptance Matrix

| Requirement | Evidence | Result |
| --- | --- | --- |
| R1 Public API compatibility | Frozen `__all__`, version, facade identity, and every public `WeChatDesktopTool` signature pass in `test_tool_equivalence.py`; source and installed-wheel API smoke pass | Pass |
| R2 Observation compatibility | Existing result assertions, exact canonical send result, focused pure/domain tests, and all 138 historical regression test bodies pass unchanged | Pass |
| R3 Command and event compatibility | Exact child-command trace and event order/phase contracts pass; operation wrappers and dispatcher tests pass | Pass |
| R4 Safety compatibility | Action proof, pre-dispatch fallback, contradictory evidence, unknown result, no-replay, truncation, ambiguity, input-focus, and redaction suites pass | Pass |
| R5 Performance compatibility | No control-map, selector, timeout, or command sequence changed; exact trace tests pass and no extra app-control call was introduced. Live 3000 ms release proof is deferred to the next coordinated release as allowed by the requirement | Pass with release proof deferred |
| R6 Package boundaries | Private import graph is acyclic, no private module imports the facade, forbidden imports are absent, and all private modules are packaged | Pass |
| R7 Maintainability | Facade and all implementation/test modules satisfy the documented size budgets; the monolithic regression file is removed | Pass |

## Automated Test Evidence

All unittest commands ran with workspace source paths explicit and
`ResourceWarning` promoted to an error.

| Suite | Result | Duration |
| --- | ---: | ---: |
| Root repository | 148 passed | 56.073 s |
| `app-control-protocol` | 55 passed | 0.026 s |
| `computer-use-macos` | 168 passed, 1 skipped | 1.672 s |
| `wechat-desktop-tool` | 254 passed | 1.782 s |
| Release-preflight unit suite | 111 passed | 56.953 s |

The one `computer-use-macos` skip is the existing live Unix-socket test whose
fixture calls `skipTest` when the execution sandbox does not permit binding a
socket. The root suite's wheel-check path still built all packages, performed
content preflight, installed a local wheelhouse, and passed all three package
API smoke snippets.

Representative commands:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  /opt/anaconda3/bin/python -W error::ResourceWarning -m unittest discover \
  -s tests -p 'test_*.py'

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  /opt/anaconda3/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p 'test_*.py'
```

## Equivalence Evidence

- The public equivalence suite freezes 47 package exports, package version
  `0.3.0`, the facade object identity, and 17 public facade signatures.
- A successful `send_message` case compares the complete ordered app-control
  command trace, including command ids, operations, input payloads, timeouts,
  parent ids, and phases.
- Stream tests freeze event type order, sequence numbers, phases, summaries,
  and final observations after replacing only wall-clock timing values.
- Safety tests prove contradictory or unknown mutation evidence never causes
  a second action or fallback.
- AST comparison of the old monolithic test file against the split modules
  reported `before=138 after=138 missing=0 added=0 bodyChanged=0` by
  `(class name, test method)`.
- Each production extraction slice recorded an AST-equivalence check in
  [`implementation-notes.md`](./implementation-notes.md).

## Static And Structural Evidence

The following checks passed:

```bash
/opt/anaconda3/bin/python -m compileall -q \
  packages/wechat-desktop-tool/src/wechat_desktop_tool \
  packages/wechat-desktop-tool/tests

uv run --with ruff ruff check \
  packages/wechat-desktop-tool/src \
  packages/wechat-desktop-tool/tests \
  scripts/release_preflight.py tests/test_release_preflight.py

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  /opt/anaconda3/bin/mypy \
  packages/wechat-desktop-tool/src/wechat_desktop_tool

git diff --check
```

Ruff reported no findings. Strict mypy reported no issues in 29 source files.
The package-boundary suite passed all 8 tests, including source-size, test-size,
failure-kind inventory, dependency-cycle, reverse-facade-edge, dependency, and
package-data gates.

### Production Sizes

| Module | Lines |
| --- | ---: |
| `tool.py` | 344 |
| `_action_operations.py` | 250 |
| `_action_safety.py` | 551 |
| `_collection_operations.py` | 324 |
| `_contact_operations.py` | 870 |
| `_contact_search.py` | 671 |
| `_diagnostics.py` | 593 |
| `_mapped_controls.py` | 459 |
| `_message_operations.py` | 522 |
| `_query_mapping.py` | 1091 |
| `_row_parsing.py` | 835 |
| `_runtime.py` | 945 |
| `_window_operations.py` | 252 |

The facade fell from 6979 baseline lines to 344. It is below the 1000-line
budget, and every private implementation module is below 1500 lines.

### Split Regression Sizes

| Module | Lines |
| --- | ---: |
| `_tool_test_fixtures.py` | 1724 |
| `test_tool_action_regressions.py` | 1137 |
| `test_tool_cli.py` | 184 |
| `test_tool_contact_regressions.py` | 1569 |
| `test_tool_examples.py` | 731 |
| `test_tool_facade.py` | 705 |
| `test_tool_message_regressions.py` | 472 |
| `test_tool_window_collection_regressions.py` | 981 |

Every split file is below the 2500-line test budget.

## Source And Archive Preflight

Source preflight passed:

```bash
env -u PYTHONPATH /opt/anaconda3/bin/python scripts/release_preflight.py
```

Fresh wheels and sdists were then built outside the repository for all three
packages with `uv build --wheel --sdist`. The output contained exactly these
six current-version artifacts:

| Artifact | SHA-256 |
| --- | --- |
| `app_control_protocol-0.3.0-py3-none-any.whl` | `2cf0f0556265450815a7c7976198090f878b964da153d27c6a147ecf9a64ae31` |
| `app_control_protocol-0.3.0.tar.gz` | `fcca451240ec1fa8927cb75dc2400d437cb4391cb3c892415c926f7d6734ce52` |
| `computer_use_macos-0.3.0-py3-none-any.whl` | `807502b1aaee084d1bea4293ff05ae391cc461c6a581139ba72e8a289c8fd09b` |
| `computer_use_macos-0.3.0.tar.gz` | `8b58c4f3b56d32bd2854f353e48c8c84c7383b563733aed24167d685e09b959b` |
| `wechat_desktop_tool-0.3.0-py3-none-any.whl` | `45bb0eb3acd2a575c9a1736393b6a8a5523300c0f875609b271232b09cce553a` |
| `wechat_desktop_tool-0.3.0.tar.gz` | `433c91ccf4db11325759da987920ba70f13b7e79efc67cb67dcf251563a7320a` |

Archive preflight passed for both archive types:

```bash
env -u PYTHONPATH /opt/anaconda3/bin/python scripts/release_preflight.py \
  --wheel-dir "$DIST_DIR" --sdist-dir "$DIST_DIR"
```

It verified metadata, dependencies, entry points, package data, schemas,
`py.typed`, no bytecode, and every new private WeChat source module in both
archive formats.

The three built wheels were then installed together into a new virtual
environment with `pip --isolated --no-index --find-links`. Imports were checked
to originate from that virtual environment, all versions were `0.3.0`, and the
existing package API smoke snippets printed three `api-smoke-ok` results plus
`isolated-wheel-smoke-ok`.

## Warnings And Deferred Proof

- Source/archive preflight warns that live Unix-socket smoke cannot bind in
  this sandbox. Deterministic transport tests and the wheel install path pass.
- External helper, TextEdit, WeChat, TestPyPI, and publishing proofs were not
  supplied. This work changes no desktop behavior, selector/profile,
  configuration, dependency, version, or release workflow, and no release is
  being published from this branch.
- The next coordinated release must refresh the existing real WeChat safety
  and 3000 ms performance proof. This is the release-proof deferral explicitly
  allowed by R5; it is not claimed as executed here.
- `uv build` emitted existing workspace-root and setuptools license-table
  deprecation warnings. All six artifacts built successfully; those warnings
  are unrelated packaging debt and do not change this feature's result.

## F5 Decision

F5 passes. Current evidence proves the requested internal modularization is
packaged, importable, structurally bounded, and covered by unchanged historical
behavior tests. Proceed to F6 self-review and merge readiness.
