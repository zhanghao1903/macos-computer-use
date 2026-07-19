# WeChat Tool Modularization Requirements

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | WeChat Tool Internal Modularization |
| Branch | `codex/wechat-tool-modularization` |
| Current phase | F0 intake and repository hygiene |
| Baseline | `23d293d01245f3c46c67c5be6a6553a989d14e0a` (`origin/main`) |
| Affected package | `wechat-desktop-tool` |
| Public surface | No planned change |
| Release impact | Internal maintenance entry in the next changelog |

## F0 Intake

The package's `tool.py` has accumulated operation dispatch, workflow
orchestration, Accessibility query mapping, action execution and fallback,
failure translation, event evidence, timing, and redaction. The file is now a
material maintenance risk even though its behavior is protected by substantial
tests.

The requested outcome is an internal modularization that improves ownership,
reviewability, and test locality without changing software behavior.

## Repository Hygiene

- The user's primary checkout is on another feature branch and contains
  unrelated untracked files. Those files are not part of this feature and will
  not be modified, staged, or removed.
- This feature uses the isolated worktree
  `/private/tmp/macos-computer-use-wechat-tool-modularization`.
- The feature branch was created from the latest fetched `origin/main`.
- The feature worktree was clean before this document was added.
- Generated smoke output, tokens, build directories, local lock files, and raw
  Accessibility data are out of scope for commits.

## Baseline Evidence

At the baseline:

- `tool.py` contains 6979 lines and approximately 238 KB of source;
- it accounts for 63.5 percent of the package's Python production source;
- `WeChatDesktopTool` contains 62 methods;
- the module contains 161 top-level functions and 228 total functions/methods;
- `tests/test_tool.py` contains 7246 lines and 138 test methods;
- the public package exports `WeChatDesktopTool`, while the module's helper
  functions and support classes remain private implementation details.

These measurements establish a maintainability problem; they are not a claim
that line count alone proves incorrect behavior.

## F0 Scope Decision

The work proceeds as behavior-preserving internal maintenance. Requirements,
module contracts, safety invariants, implementation slices, and verification
evidence will be completed in later lifecycle phases before implementation.

## Phase Commit Plan

Each completed lifecycle phase will update a tracked feature document, be
committed independently, and be pushed to the dedicated feature branch before
the next phase starts.
