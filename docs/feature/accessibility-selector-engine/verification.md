# Accessibility Selector Engine Verification

- Verification date: 2026-07-07
- Branch: `codex/accessibility-selector-engine`
- Scope: automated F5 verification snapshot after Slice 5
- Status: automated checks passed; real WeChat smoke remains pending

## Automated Checks

| Area | Command | Result |
| --- | --- | --- |
| `app-control-protocol` tests | `PYTHONPATH=packages/app-control-protocol/src python -m unittest discover -s packages/app-control-protocol/tests` | Passed: 54 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 74 tests, 1 skipped |
| `wechat-desktop-tool` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 86 tests |
| WeChat package-boundary tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_package_boundary.py` | Passed: 5 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile ...` | Passed |
| Whitespace/conflict check | `git diff --check` | Passed |

## Unavailable Checks

`uv run ruff check ...` was attempted, but the local environment does not have a
`ruff` executable available:

```text
error: Failed to spawn: `ruff`
Caused by: No such file or directory (os error 2)
```

This is an environment/tooling gap, not a reported lint failure.

## Fixture And Unit Coverage

Covered by automated tests:

- selector profile parsing, validation, defaults, transforms, cache policy, and
  collection extraction;
- normalized collection `elementRef` generation and fail-closed validation;
- packaged WeChat selector profile loading and override fallback;
- selector-backed WeChat contacts, conversations, visible messages, and
  open-contact flows;
- WeChat selector profile override config propagation from `AppControlConfig`;
- package boundary rule that only `wechat_desktop_tool.profiles` imports
  `computer_use_macos.selectors`.

## Real WeChat Smoke Checklist

These checks require a real macOS desktop, Accessibility permission, running
WeChat, and the local app-control service. They are required before merge or
release readiness:

1. `inspect_window` returns a normalized WeChat window model.
2. `list_contacts(limit=30)` returns visible contacts and action refs.
3. `list_conversations(limit=30)` returns visible conversations and action refs.
4. `open_contact("文件传输助手")` switches the active chat.
5. `read_visible_messages(limit=30)` returns visible message rows.
6. `[wechat] selector_profile_path` loads a valid local override without
   rebuilding the package.
7. Invalid `selector_profile_path` falls back to the packaged profile.
8. Stale or invalid action refs fail preconditions instead of raw-coordinate
   clicking.

Recommended smoke setup:

```bash
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

Then run the existing SDK/example scripts against that service, saving JSON
reports under the repository root for release review.

## Release Readiness Gate

The feature is not release-ready until real WeChat smoke evidence is added to
this file or linked from it. Public selector protocol commands remain deferred;
this feature currently ships only the internal selector engine, WeChat packaged
profile migration, and profile override configuration.
