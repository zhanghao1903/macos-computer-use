# Accessibility Selector Engine Verification

- Verification date: 2026-07-07
- Branch: `codex/accessibility-selector-engine`
- Scope: automated F5 verification snapshot after Slice 5D
- Status: automated checks passed; real WeChat selector-engine smoke passed on
  2026-07-08; public selector protocol remains deferred

## Automated Checks

| Area | Command | Result |
| --- | --- | --- |
| `app-control-protocol` tests | `PYTHONPATH=packages/app-control-protocol/src python -m unittest discover -s packages/app-control-protocol/tests` | Passed: 54 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 75 tests, 1 skipped |
| `wechat-desktop-tool` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 88 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| WeChat package-boundary tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_package_boundary.py` | Passed: 5 tests |
| Root repository tests and release preflight | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 101 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile ...` | Passed |
| Whitespace/conflict check | `git diff --check` | Passed |

## Additional Verification: Multi-Step Selector Resolution

Date: 2026-07-07.

This verification covers a corrective selector-engine slice that makes
`SelectorResolver` execute selector steps as a chain instead of querying every
step from the same root.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 25 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 76 tests, 1 skipped |

New coverage:

- a two-step selector first resolves an `AXGroup` landmark from the focused
  window;
- the second step is queried under that landmark's AX path;
- the final `SelectorResult` returns the second-step `AXTable` element rather
  than the intermediate landmark;
- query evidence confirms no full-window second-step scan is used.

## Additional Verification: Action Definition Safe Defaults

Date: 2026-07-07.

This verification covers the contract-synchronization slice for
`ActionDefinition.enabled_by_default`. Profile actions now default to disabled,
read/focus actions may opt in, and mutating actions fail closed if a profile
tries to enable them by default.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 30 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 84 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/models.py packages/computer-use-macos/src/computer_use_macos/selectors/profile.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/models.py packages/computer-use-macos/src/computer_use_macos/selectors/profile.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- omitted `enabled_by_default` parses to `False`;
- `changes_focus` actions can explicitly opt into
  `enabled_by_default = true`;
- `submits_text` and other mutating actions cannot be enabled by default;
- non-boolean `enabled_by_default` values are rejected during profile parsing.

## Additional Verification: Profile Policy Validation Hardening

Date: 2026-07-07.

This verification covers additional field-matrix enforcement for profile
policies that were represented in the dataclasses but not fully fail-closed in
validation.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 34 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 88 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- `PaginationPolicy.mode = "cursor"` is rejected during the internal MVP;
- `RelationRule.relation = "near"` requires a positive `max_distance`;
- relation distances cannot be zero or negative;
- `pick = "best"` requires at least one non-zero confidence scoring weight;
- non-best pick strategies may still use zero scoring weights when they do not
  depend on best-candidate scoring.

## Additional Verification: Selector Cache TTL Enforcement

Date: 2026-07-07.

This verification covers the selector cache lifecycle rule that cache entries
expire by TTL and must not be treated as stable element identity.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 35 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 89 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- expired selector cache entries are deleted and refreshed from the selector
  root instead of validating the old AX path;
- expired refreshes report `cache_status = "stale"` and only count the fresh
  query;
- stale signature validation still validates the cached AX path once before
  falling back to a fresh query;
- cache validation query counts are no longer double-counted.

## Additional Verification: Relation Anchor Matching

Date: 2026-07-07.

This verification covers the selector resolver behavior for
`SelectorStep.relation`. The field was already represented and validated in the
profile model, but the resolver now applies relation anchors during candidate
selection.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 36 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 90 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- a selector can resolve a search-box anchor and filter button candidates using
  `relation = "rightOf"`;
- candidates on the wrong side, beyond `max_distance`, or outside the
  overlapping row are rejected;
- the selected element records `relation:rightOf` evidence;
- relation-anchor queries contribute to selector diagnostics query counts.

## Additional Verification: Nearest-To-Anchor Pick Strategy

Date: 2026-07-07.

This verification covers the `PickStrategy = "nearestToAnchor"` contract. The
strategy is now rejected unless a final-step relation anchor exists, and
resolver selection uses anchor geometry instead of candidate order or confidence
ties.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 38 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 92 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- `nearestToAnchor` without a final-step relation is rejected during profile
  validation;
- `nearestToAnchor` with a valid final-step relation parses successfully;
- resolver selection picks the candidate nearest to the anchor even when a
  farther candidate appears first;
- relation-anchor queries remain included in selector diagnostics.

## Additional Verification: Collection Diagnostics Policy Enforcement

Date: 2026-07-07.

This verification covers collection diagnostic policy behavior and strict
boolean parsing for selector profile fields that previously used Python
truthiness.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 40 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/profile.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 94 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/profile.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- collection field `required` values must be real booleans;
- collection diagnostics policy values must be real booleans;
- disabling `include_candidate_counts` suppresses collection result
  `node_count`;
- disabling skipped and field-failure count diagnostics preserves status and
  failure kind while returning a generic message.

## Additional Verification: Structural Constraint Enforcement

Date: 2026-07-07.

This verification covers frame-based `SelectorConstraint` values. These
constraint kinds were already represented in the model and validation enum; the
resolver now enforces them during final candidate matching.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 42 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 96 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/validation.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- `frameWithin` values must be complete numeric frame objects;
- `frameWithin`, `rightOf`, and `below` are applied to final candidates;
- required frame constraints reject candidates outside the configured geometry;
- matched structural constraints are recorded in selector evidence.

## Additional Verification: Visible Match Filter

Date: 2026-07-07.

This verification covers `MatchRule.visible`. The field was already parsed from
profiles and documented as a hard filter; selector matching now applies it.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 43 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 97 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- `visible = true` rejects explicitly hidden candidates;
- `visible = true` rejects zero-sized frame candidates;
- positive frame dimensions provide a conservative visibility fallback when AX
  visibility is absent;
- selector queries request `AXHidden` for visibility evidence.

## Additional Verification: WeChat Search Hotkey Recovery

Date: 2026-07-07.

This verification covers the live-smoke hardening slice that makes
`Command+F` the default WeChat search hotkey and recovers open-phase window
readiness from a bounded Accessibility query when `observe` omits the window
title.

| Area | Command | Result |
| --- | --- | --- |
| `app-control-protocol` config tests | `PYTHONPATH=packages/app-control-protocol/src python -m unittest packages/app-control-protocol/tests/test_config.py` | Passed: 7 tests |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 84 tests |

New coverage:

- default `[wechat].search_hotkey` is `["Command", "F"]`;
- explicit config and environment overrides can still set another hotkey such
  as `["Command", "K"]`;
- live `--allow-focus-select` no longer rejects `Command+F` before running;
- the open phase succeeds when `observe` has no title but
  `accessibility_query` returns an `AXWindow` title;
- the open phase still fails closed with `wechat_not_ready` when neither
  observation nor Accessibility can prove a focused WeChat window.

## Additional Verification: Contact Collection Fill And Search Focus Fallbacks

Date: 2026-07-07.

This verification covers the corrective slice for noisy WeChat contact rows,
frame-backed selector results, role-specific Accessibility selector click, and
verified `AXSetFocus` support.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 26 tests |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 80 tests, 1 skipped |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 86 tests |

New coverage:

- collection extraction continues past invalid candidates until it accepts the
  caller's requested number of valid semantic items or exhausts bounded visible
  candidates;
- WeChat contact listing skips special/header rows before filling the caller
  limit;
- selector resolver queries include `AXFrame`, allowing resolved element frames
  to drive verified fallback behavior;
- Accessibility selector click preserves `AXTextArea` and matches by
  `description` inside role-specific System Events collections;
- `accessibility_action` accepts verified `AXSetFocus` for resolved AX paths;
- `open_contact` attempts safe selector click, `AXSetFocus`, configured
  hotkey, and config-gated coordinate fallback before returning
  `search_not_focused`.

## Additional Verification: Listed Contact ActionRef Recent Messages

Date: 2026-07-07.

This verification covers the SDK example path for reading recent messages from
contacts that were already returned by `list_contacts`. The example now uses
the contact row `actionRef` when present, then reads visible messages from the
opened chat. It falls back to `read_contact_messages(contact)` only when the
contact item does not include an actionRef.

| Area | Command | Result |
| --- | --- | --- |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile examples/wechat_contacts_recent_messages_test.py tests/test_sdk_examples.py` | Passed |

New coverage:

- `examples/wechat_contacts_recent_messages_test.py` opens listed contacts with
  `execute_action(actionRef)` before reading messages;
- the recent-messages fake-service fixture uses realistic contact row heights,
  so rows are not filtered as section/header rows;
- the SDK test asserts the listed-contact path does not issue `type_text` for
  the contact name;
- existing `read_contact_messages(contact)` search behavior remains the
  fallback when a contact item lacks an actionRef.

## Additional Verification: Visible Row OpenContact ActionRef

Date: 2026-07-07.

This verification covers the WeChat semantic `open_contact(contact)` path. The
tool now tries visible row actionRefs under the selector-resolved main content
region before entering the search-box workflow. The search path remains the
fallback for contacts that are not currently visible.

| Area | Command | Result |
| --- | --- | --- |
| Open-contact focused tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k open_contact` | Passed: 5 tests |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 87 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| Python compile check | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py` | Passed |

New coverage:

- `open_contact("文件传输助手")` opens a visible conversation row by executing
  that row's actionRef before search;
- the visible actionRef path returns `openMethod=visible_action_ref`;
- the visible actionRef path does not issue `type_text`, search hotkeys, or raw
  coordinate clicks;
- no-match visible rows still fall back to the existing search-box flow;
- SDK send-message fixtures now cover opening File Transfer through the visible
  row actionRef before drafting and submitting.

## Additional Verification: ActionRef Precondition Failure Mapping

Date: 2026-07-07.

This verification covers the WeChat semantic `execute_action(actionRef)` failure
path for stale or invalid action references.

| Area | Command | Result |
| --- | --- | --- |
| Execute-action focused tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k execute_action` | Passed: 3 tests |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 88 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 6 tests |
| Python compile check | `python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md` | Passed |

New coverage:

- backend `precondition_failed` results are mapped to
  `wechat_action_precondition_failed`;
- stale actionRefs that fail role, label, action, or enabled checks do not use
  selector-click fallback;
- unsupported-backend responses still use selector fallback when one is
  available;
- backend failure details remain in the action evidence for caller diagnostics.

## Additional Verification: ActionRef Expiry Enforcement

Date: 2026-07-08.

This verification covers the WeChat semantic `execute_action(actionRef)`
lifecycle path for generated, expired, and malformed action references.

| Area | Command | Result |
| --- | --- | --- |
| Execute-action focused tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k execute_action` | Passed: 5 tests |
| Python compile check | `python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/src/wechat_desktop_tool/window_model.py packages/wechat-desktop-tool/src/wechat_desktop_tool/errors.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 95 tests |
| Release preflight | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python scripts/release_preflight.py` | Passed with existing external-proof warnings for real desktop, TestPyPI, and PyPI publisher checks |
| Whitespace/conflict check | `git diff --check -- packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/src/wechat_desktop_tool/window_model.py packages/wechat-desktop-tool/src/wechat_desktop_tool/errors.py packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/README.md docs/feature/accessibility-selector-engine/design.md docs/feature/accessibility-selector-engine/implementation-notes.md docs/feature/accessibility-selector-engine/verification.md docs/api.md docs/wechat-window-data-model.md CHANGELOG.md` | Passed |

New coverage:

- generated actionRefs include `createdAt` and `expiresAt`;
- expired actionRefs are rejected as `wechat_action_ref_expired`;
- malformed `expiresAt` values fail closed as expired;
- expiry rejection happens before backend `accessibility_action` or fallback
  execution;
- `WECHAT_FAILURE_KINDS` declares the new expiry failure and the existing
  action precondition failure for caller-side routing;
- legacy actionRefs without `expiresAt` continue to use the existing execution
  path for compatibility.

## Additional Verification: Selector Engine Smoke Checklist Example

Date: 2026-07-08.

This verification covers the consolidated SDK example that turns the remaining
real WeChat merge gate into one repeatable smoke report. The automated proof
uses a fake local-service client; it does not replace the real WeChat smoke.

| Area | Command | Result |
| --- | --- | --- |
| Focused SDK example test | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples -k selector_engine` | Passed: 1 test |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 7 tests |
| Python compile check | `python -m py_compile examples/wechat_selector_engine_smoke_test.py tests/test_sdk_examples.py` | Passed |
| Root tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 102 tests |
| Release preflight | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python scripts/release_preflight.py` | Passed with existing external-proof warnings for real desktop, TestPyPI, and PyPI publisher checks |

New coverage:

- the example opens WeChat, inspects the normalized window model, lists
  conversations, opens `文件传输助手`, reads visible messages, lists contacts,
  checks valid profile override loading, checks invalid override fallback, and
  verifies expired actionRefs fail as `wechat_action_ref_expired`;
- the fake-service test proves the checklist uses selector-backed
  `accessibility_action` paths, does not type text, and does not submit a
  message;
- the report schema
  `macos_computer_use.sdk.wechat_selector_engine_smoke_test.v1` gives release
  review one artifact for the remaining live WeChat proof.

## Additional Verification: Enabled Match Filter

Date: 2026-07-07.

This verification covers `MatchRule.enabled` as a fail-closed selector filter.
Previously the matcher used Python truthiness on `node.get("enabled")`, which
made missing enabled evidence indistinguishable from `False` and did not use
`AXEnabled` values returned by Accessibility queries.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 45 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 99 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |

New coverage:

- `enabled = true` rejects candidates without enabled-state evidence;
- explicitly disabled candidates are rejected;
- raw `AXEnabled = true` can satisfy the enabled filter;
- selector query payloads request `AXEnabled`;
- descendant collection field queries request `AXEnabled` when they may need to
  apply enabled filters.

## Additional Verification: Selected Constraint Evidence

Date: 2026-07-07.

This verification covers the `selected` structural constraint as a fail-closed
selector constraint. Previously the matcher used Python truthiness on
`node.get("selected")`, which made missing selected-state evidence satisfy
`selected = false`.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 46 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 100 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |

New coverage:

- required `selected = false` constraints reject candidates without selected
  evidence;
- raw `AXSelected = true` rejects a `selected = false` constraint;
- top-level `AXSelected = false` can satisfy a `selected = false` constraint;
- selector query payloads request `AXSelected`.

## Additional Verification: Structural Role Constraint Evidence

Date: 2026-07-08.

This verification covers structural role constraints and their supporting
`accessibility_query` summaries. Previously `hasChildRole` and
`hasDescendantRole` both read `childRoles or descendantRoles`, allowing deeper
descendant evidence to satisfy a direct-child constraint.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 47 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py` | Passed: 54 tests, 1 skipped |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/client.py packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py packages/computer-use-macos/tests/test_package.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 101 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Release preflight | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python scripts/release_preflight.py` | Passed with existing external-proof warnings |

New coverage:

- `hasChildRole` requires direct `childRoles` evidence;
- `hasDescendantRole` requires `descendantRoles` evidence;
- selector query payloads enable `includeChildRoles` and
  `includeDescendantRoles` only when final-step constraints require them;
- `accessibility_query` preserves the structural summary flags in normalized
  requests;
- the direct backend script contains `childRoles` and `descendantRoles`
  generation support.

## Additional Verification: Confidence Policy Weights

Date: 2026-07-08.

This verification covers `ConfidencePolicy` runtime scoring. The fields were
already parsed and validated, but resolver confidence previously used a simple
average that ignored the profile-defined category weights.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 48 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/matching.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 102 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |

New coverage:

- candidate confidence uses profile-defined category weights;
- a candidate that passes hard filters can still fail `minimum` when the
  profile requires structural evidence;
- matched optional structural constraints can lift a candidate above the
  profile minimum;
- selectors without weighted scoring signals keep hard-filter-only confidence
  behavior.

## Additional Verification: Collection Selector Constraints

Date: 2026-07-08.

This verification covers collection extraction constraint handling. Previously,
collection `item_selector` and descendant field selectors used match filters
but did not apply selector-level constraints, so a repeated row or field node
could be accepted without the structural evidence required by the profile.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 50 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 104 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |

New coverage:

- collection item selectors apply required constraints before field extraction;
- item selectors request `includeChildrenCount` when `minChildren` evidence is
  required;
- descendant field selectors apply required `selected` constraints before
  reading field values;
- descendant field queries request `AXSelected` when selected-state evidence is
  required;
- collection queries include custom step match attributes in their bounded AX
  attribute requests.

## Additional Verification: Frontmost App Query Root

Date: 2026-07-08.

This verification covers `SelectorRoot.kind = "frontmostApp"` and the matching
`accessibility_query` root behavior. Previously the selector resolver rewrote
`frontmostApp` to `focusedWindow`, and the direct query backend rejected
`frontmostApp` roots.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 51 tests |
| Package client tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py` | Passed: 55 tests, 1 skipped |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/client.py packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/tests/test_selectors.py packages/computer-use-macos/tests/test_package.py` | Passed |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 106 tests, 1 skipped |
| WeChat profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 6 tests |
| Release preflight | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python scripts/release_preflight.py` | Passed with existing external-proof warnings |

New coverage:

- resolver passes `frontmostApp` to its query runner without rewriting it;
- direct client request normalization accepts `root.kind = "frontmostApp"`;
- direct query script supports app-root paths such as `app`;
- script source keeps focused-window `0/...` paths and app-root `app/...`
  paths as distinct query roots.
- script source now verifies the no-focused-window bypass is limited to exactly
  `app` or `app/...`, not arbitrary paths that merely start with `app`.

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
  `computer_use_macos.selectors`;
- root release preflight allows the explicit selector-profile dependency while
  continuing to block broad WeChat-to-backend imports;
- SDK example fake-service fixtures cover selector-backed contact listing and
  recent-message reads after collection extraction;
- SDK example fake-service fixtures cover listed-contact actionRef execution
  before reading visible messages;
- WeChat tool and SDK example fixtures cover `open_contact` and File Transfer
  send flows that consume visible row actionRefs before using search.

## Real WeChat Smoke Evidence

Partial smoke was run on 2026-07-07 against a local app-control service using
the current checkout as `PYTHONPATH`.

The current no-focused-window desktop blocker and recovery steps are recorded
in `live-smoke-recovery.md`.

A read-only `frontmostApp` root probe was attempted from the current
Codex-hosted Python process on 2026-07-08. It did not reach WeChat because
`readiness.status=missing_accessibility` and `accessibility_trusted=false`.
That permission blocker is separate from the earlier trusted-session
`accessibility_query_no_focused_window` blocker and is now recorded in
`live-smoke-recovery.md`.

Passed evidence:

- `inspect_window` wrote `/private/tmp/accessibility-selector-inspect-fixed.json`
  and returned `success=true`, schema `wechat.window.v1`, title `微信 (聊天)`,
  active section `chats`, navigation labels `chats`, `contacts`, and
  `favorites`, regions `mainContent` and `searchBox`, `actionableCount=4`, and
  `availableActionCount=5`.
- `list_contacts(limit=30)` wrote
  `/private/tmp/accessibility-selector-contacts-list.json` and returned
  `success=true`, `listedContactCount=29`.

Incomplete evidence:

- `/private/tmp/accessibility-selector-conversations-open-read.json` could not
  complete `list_conversations`, `open_contact`, or `read_visible_messages`.
- `/private/tmp/accessibility-selector-inspect-after-focus.json` shows WeChat
  was frontmost, but `windowTitle` was empty and `accessibility_query` failed
  with `accessibility_query_no_focused_window` even after `focus_app`.
- `/private/tmp/accessibility-selector-contacts-list-rerun.json` failed for the
  same no-focused-window desktop state after the successful contacts run.
- `/private/tmp/selector-live-inspect-open-phase-fail.json` confirms the
  no-focused-window state now fails in the WeChat open phase with
  `status=not_ready` and `failureKind=wechat_not_ready`, before any selector
  `accessibility_query` runs.
- A direct PyObjC probe on 2026-07-07 still showed frontmost `loginwindow`,
  WeChat running but inactive, and WeChat `AXWindows` whose roles were
  `AXApplication` rather than `AXWindow`.
- `/private/tmp/selector-live-recent-messages-after-axsetfocus.json` listed one
  semantic contact but failed at `readContactMessages` with
  `search_not_focused`. Evidence shows `AXSetFocus` returned
  `AXUIElementSetAttributeValue` success for search box `0/12/0`, but a
  follow-up query still reported `AXFocused=false`. `Command+F`, `Command+K`,
  safe selector click, and several coordinate clicks inside the resolved
  search-box frame also failed to focus that live WeChat search input.
- `/private/tmp/selector-live-recent-messages-actionref.json` was rerun after
  the listed-contact actionRef and visible-row `open_contact` updates. The
  smoke did not reach `list_contacts`: `system_open_wechat` and readiness
  passed, but `open_wechat` returned `status=not_ready` with summary
  `WeChat is frontmost but no focused window is available.` The nested
  `verify_wechat_accessibility_window` failed with
  `accessibility_query_no_focused_window`.
- A direct PyObjC probe during that rerun showed frontmost `loginwindow`,
  WeChat running but inactive, `AXFocusedWindow` role `AXApplication`, and
  three WeChat `AXWindows` entries whose roles were all `AXApplication`, not
  `AXWindow`.
- `/private/tmp/selector-live-selector-engine-smoke-20260708.json` was run
  against the existing local service with `--skip-system-open`. It connected to
  `/tmp/app-control.sock`, readiness passed with
  `accessibility_trusted=true`, generated valid/invalid profile override proof,
  but failed at `openWeChat`. Evidence shows `open_app` and `focus_app` both
  returned success for WeChat, while `observe` before and after focus still
  reported `frontmostBundleId=com.openai.codex` and
  `failureKind=needs_user`. The WeChat adapter failed closed as
  `wechat_not_ready`.
- `/private/tmp/selector-live-selector-engine-smoke-system-open-20260708.json`
  reran the same consolidated smoke without `--skip-system-open`. The local
  `open -b com.tencent.xinWeChat` and AppleScript
  `tell application id "com.tencent.xinWeChat" to activate` attempts both
  returned code `0`, but the service observations still reported Codex as the
  frontmost bundle before and after `focus_app`. It failed at the same
  `openWeChat` gate with `wechat_not_ready`.
- `/private/tmp/selector-live-prereq-probe-continuation-20260708.json` was
  generated by `examples/wechat_live_prereq_probe.py` from the Codex-hosted
  Python process. It returned `failureKind=accessibility_not_trusted`, so it
  only proves that this process cannot read Accessibility directly; it is not
  the authoritative service smoke state.
- `/private/tmp/selector-live-selector-engine-smoke-continuation-20260708.json`
  reran the consolidated smoke through the existing local app-control service.
  Service readiness passed with `accessibility_trusted=true`, system open and
  AppleScript activation returned success, valid/invalid profile override
  checks passed, but `openWeChat` still failed before selector queries because
  `observe` reported `frontmostBundleId=com.openai.codex` before and after
  `focus_app`. The WeChat adapter again failed closed with
  `wechat_not_ready`.

This is not enough for merge readiness. It proves that the selector-backed
window model and contacts collection work on a live client, and it also proves
that the backend and WeChat semantic layer now fail closed when no focused AX
window is available, when the current Python host lacks Accessibility
permission, or when macOS focus remains on Codex despite successful WeChat
open/focus attempts.

After manually restoring a real WeChat `AXWindow`, first run
`examples/wechat_selector_engine_smoke_test.py`. The script writes one report
that covers conversation listing, opening `文件传输助手`, visible message
reading, valid override loading, invalid override fallback, and expired
actionRef fail-closed behavior.

If the consolidated checklist fails, rerun
`examples/wechat_contacts_recent_messages_test.py --max-contacts 1` on the live
desktop. That rerun should prove whether the already-listed contact row can be
opened through `execute_action(actionRef)` and read through
`read_visible_messages` without relying on the WeChat search box.

After the visible-row `open_contact` update, rerun
`examples/wechat_file_transfer_send_test.py` on the live desktop. If
`文件传输助手` is visible in the conversation list, the smoke should open it
through `openMethod=visible_action_ref` before drafting and submitting.

## Remaining Real WeChat Smoke Checklist

These checks require a real macOS desktop, Accessibility permission, running
WeChat, and the local app-control service. Remaining checks are required before
merge or release readiness:

1. `list_conversations(limit=30)` returns visible conversations and action refs.
2. `open_contact("文件传输助手")` switches the active chat, preferably through
   visible row `openMethod=visible_action_ref` when File Transfer is visible.
3. `examples/wechat_contacts_recent_messages_test.py --max-contacts 1` opens a
   listed contact through actionRef and reads visible message rows.
4. `read_visible_messages(limit=30)` returns visible message rows after a
   manually or actionRef-opened chat.
5. `[wechat] selector_profile_path` loads a valid local override without
   rebuilding the package.
6. Invalid `selector_profile_path` falls back to the packaged profile.
7. Stale or invalid action refs fail preconditions instead of raw-coordinate
   clicking.

Recommended smoke setup:

```bash
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

Then run the consolidated SDK smoke checklist against that service:

```bash
.venv/bin/python examples/wechat_selector_engine_smoke_test.py \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-selector-engine-smoke.json \
  --contact "文件传输助手"
```

For release review, save JSON reports under a reviewed location or link the
local proof paths from this file. If the consolidated checklist fails, run the
narrower existing SDK/example scripts against the same service to isolate the
failing step.

## Additional Verification: Live Prerequisite Probe

Date: 2026-07-08.

This verification covers the read-only live prerequisite probe added for the
remaining WeChat smoke blocker. The probe reports whether the current Python
host is Accessibility-trusted, whether WeChat is running, whether WeChat is
frontmost, and whether macOS exposes a WeChat `AXWindow`.

The probe is not a substitute for the selector-engine smoke checklist. It is a
preflight diagnostic that explains why the live checklist cannot proceed when
macOS keeps Codex or `loginwindow` frontmost, or when WeChat only exposes
`AXApplication` nodes.

| Area | Command | Result |
| --- | --- | --- |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples -k live_prereq` | Passed: 2 tests |
| Python compile check | `python -m py_compile examples/wechat_live_prereq_probe.py tests/test_sdk_examples.py` | Passed |
| Full SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 106 tests |

New coverage:

- a ready fake desktop state returns `readyForSmoke=true` and writes the JSON
  report;
- the observed Codex-frontmost blocker returns `frontmost_not_wechat` and keeps
  `readyForSmoke=false`;
- the report includes only normalized prerequisite data:
  `frontmost`, `wechat.apps[*].focusedWindow`, `wechat.apps[*].windows`, and
  summary checks.

## Additional Verification: AXRow ActionRef And Live Smoke Pass

Date: 2026-07-08.

This verification covers the corrective slice for live WeChat rows that do not
expose `AXPress` in `AXActionNames` and for `AXRow` targets where visible row
text lives on child cells instead of the row itself.

| Area | Command | Result |
| --- | --- | --- |
| `computer-use-macos` tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py packages/computer-use-macos/tests/test_selectors.py` | Passed: 108 tests, 1 skipped |
| WeChat tool/profile tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 91 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/client.py packages/computer-use-macos/tests/test_package.py packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| Live WeChat selector-engine smoke | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python examples/wechat_selector_engine_smoke_test.py --socket-path /private/tmp/app-control-selector-return-20260708.sock --token-file ./app-control.token --output /private/tmp/selector-live-selector-engine-smoke-return-20260708.json --contact "文件传输助手" --conversation-limit 30 --contact-limit 30 --message-limit 30` | Passed: `conversationCount=30`, `contactCount=30`, `messageCount=30`, `failedStep=null` |
| Release preflight with smoke proof | `python scripts/release_preflight.py --wechat-smoke-report /private/tmp/selector-live-selector-engine-smoke-return-20260708.json` | Passed; `external-proof:wechat_selector_engine_smoke` verified |

New coverage:

- `accessibility_query` safe attributes include `AXHidden`, preserving
  selector visible filtering through the local service;
- `AXRow` is accepted by selector normalization and action precondition
  handling;
- WeChat conversation rows produce `AXPress` actionRefs even when live rows do
  not expose actions;
- `AXRow` actionRefs avoid row label preconditions because WeChat row labels can
  be derived from child cells rather than the action target;
- `open_contact` presses the configured submit key when a unique search result
  row is found but `AXUIElementPerformAction` fails on the row target;
- the consolidated live smoke proves `open_contact`, `read_visible_messages`,
  `list_contacts`, `list_conversations`, profile override checks, and expired
  actionRef rejection on a real WeChat desktop.

## Additional Verification: Release Preflight And CI Source Path Recovery

Date: 2026-07-09.

This verification covers the CI failure where `python
scripts/release_preflight.py` ran from a clean checkout without `PYTHONPATH`.
The WeChat source entrypoints imported `computer_use_macos.selectors`, but the
preflight subprocess environment only included the protocol and WeChat source
roots. The next CI run also showed the workflow's WeChat package-test step had
the same missing dependency path, so the workflow now uses the complete
workspace source path and release preflight checks that contract.

| Area | Command | Result |
| --- | --- | --- |
| Targeted release-preflight tests | `uv run pytest tests/test_release_preflight.py -k "wechat_module_entrypoint or wechat_dry_run_smokes or default_preflight_passes_local_checks"` | Passed: 3 tests |
| Workflow dependency-path tests | `uv run pytest tests/test_release_preflight.py -k "workflow_check_requires_wechat_test_dependency_path or default_preflight_passes_local_checks"` | Passed: 2 tests |
| CI-equivalent release preflight | `env -u PYTHONPATH python scripts/release_preflight.py` | Passed; WeChat module-entrypoint, dry-run smoke, and workflow source-path checks were `OK` |
| Python compile check | `python -m py_compile scripts/release_preflight.py tests/test_release_preflight.py` | Passed |
| Whitespace/conflict check | `git diff --check -- .github/workflows/ci.yml scripts/release_preflight.py tests/test_release_preflight.py` | Passed |
| GitHub Actions PR CI | PR #3 run `28958774968`, job `85924596643` | Passed: `test` |

`uv run ruff check scripts/release_preflight.py tests/test_release_preflight.py`
could not run in the local environment because `ruff` is not installed.

New coverage:

- WeChat module-entrypoint preflight checks assert that subprocess
  `PYTHONPATH` contains `app-control-protocol/src`,
  `computer-use-macos/src`, and `wechat-desktop-tool/src`;
- both WeChat dry-run smoke checks assert the same workspace source-path
  contract;
- the GitHub Actions WeChat package-test step now uses the same three package
  source roots, and release preflight fails if that path regresses;
- full release preflight now passes with `PYTHONPATH` explicitly removed from
  the environment, matching the failing GitHub Actions mode.

## Additional Verification: Selector Collection Batch Field Extraction

Date: 2026-07-09.

This verification covers the performance fix for `list_contacts`, where live
WeChat contact listing previously issued one descendant Accessibility query per
candidate row. A live run with 30 returned contacts showed 44 selector query
phases and `listContacts.durationMs=53863`; the dominant cost was per-row
field extraction after the row list had already been found.

| Area | Command | Result |
| --- | --- | --- |
| Selector tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_selectors.py` | Passed: 51 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 108 tests, 1 skipped |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 96 tests |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| Whitespace/conflict check | `git diff --check -- packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py packages/computer-use-macos/src/computer_use_macos/selectors/collections.py packages/computer-use-macos/tests/test_selectors.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |

New coverage:

- collection extraction batches one-step descendant field queries under the
  collection root and maps field nodes back to row items by AX path prefix;
- missing required fields still fall back to per-item descendant queries and
  keep existing partial/failure diagnostics;
- WeChat `list_contacts` tests now prove batch extraction by returning all
  row text nodes from one query and asserting the query root is the main
  content area;
- selector resolution requests `AXHidden`, `AXEnabled`, and `AXSelected` only
  when profile rules need visible, enabled, or selected evidence.

## Release Readiness Gate

The consolidated real WeChat selector-engine smoke evidence has been recorded
above and is recognized by strict release preflight. Public selector protocol
commands remain deferred; this feature currently ships only the internal
selector engine, WeChat packaged profile migration, profile override
configuration, and semantic WeChat API behavior.

## Release Proof Preflight Recognition

The consolidated selector-engine smoke checklist is now consumable by the
strict release proof path:

- report file name expected by release tooling:
  `wechat-selector-engine-smoke.json`;
- proof key: `wechat_selector_engine_smoke`;
- report schema:
  `macos_computer_use.sdk.wechat_selector_engine_smoke_test.v1`;
- recognized through repeated `--wechat-smoke-report` arguments on
  `scripts/release_preflight.py`;
- bundled through `scripts/release_proof_bundle.py
  --wechat-selector-engine-report`;
- enforced by the GitHub Release workflow before PyPI publishing.

The loader accepts a report only when the summary succeeds, all required
checklist booleans are true, WeChat operations are protocol-shaped
observations, valid/invalid profile override checks pass, and the expired
actionRef check fails closed with `wechat_action_ref_expired`.

Automated checks run for this proof-recognition slice:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_release_preflight -k wechat_selector
```

Result: 2 tests passed.

```bash
python -m py_compile \
  scripts/release_preflight.py \
  scripts/release_proof_bundle.py \
  scripts/dev_check.py \
  tests/test_release_preflight.py \
  tests/test_dev_check.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_release_preflight
```

Result: 78 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_dev_check
```

Result: 7 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
```

Result: 104 tests passed.

This does not replace the real live WeChat smoke requirement. It makes the
future live smoke output structurally enforceable by release preflight once the
report is produced from a real desktop run.

## Additional Verification: WeChat Control Map Fast Path

Date: 2026-07-09.

This verification covers the control-map optimization for WeChat semantic APIs.
The prior batch extraction slice reduced per-row field queries, but still
depended on selector discovery from broad regions. The new fast path uses
packaged AX path maps derived from `examples/window.json.bak` and
`examples/window-contact.json`.

| Area | Command | Result |
| --- | --- | --- |
| `app-control-protocol` tests | `PYTHONPATH=packages/app-control-protocol/src python -m unittest discover -s packages/app-control-protocol/tests` | Passed: 54 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 108 tests, 1 skipped |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 98 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 109 tests |
| Python compile check | `python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/control_map.py packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_profiles.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py` | Passed |
| Whitespace/conflict check | `git diff --check` | Passed |
| Ruff check | `uv run ruff check packages/wechat-desktop-tool/src/wechat_desktop_tool/control_map.py packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_profiles.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py` | Not run: local environment could not spawn `ruff` |

New coverage:

- packaged control map loading and override loading from
  `selector_profile_path`;
- `list_contacts` normal path uses `0/2` navigation and `0/12/2/0` contact
  table root;
- contact rows map nested `AXStaticText` values back to the nearest `AXRow`
  and skip special/status rows before applying the caller limit;
- `list_conversations` normal path uses `0/1` navigation and `0/11/1/0`;
- `read_visible_messages` normal path uses `0/11/4/0/0`;
- visible `open_contact` rows use the mapped conversations root before the
  selector/search fallback path;
- selector fallback tests still cover missing navigation/search/message regions.

Manual proof still required:

- run the SDK examples against a real WeChat client and record wall-clock
  `durationMs` for each semantic API;
- confirm each normal API path returns within 3 seconds on the target machine;
- update the control map if a future WeChat client changes the stable AX paths.

## Additional Verification: WeChat Mapped Navigation Click Performance

Date: 2026-07-09.

This verification covers the follow-up fix for slow mapped navigation clicks.
The live contact-list smoke showed `control_map_switch_contacts_0` spending
about 11.9 seconds in `accessibility_action` even though the target window was
already `微信 (通讯录)`.

| Area | Command | Result |
| --- | --- | --- |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 99 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 109 tests |
| Python compile check | `python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py` | Passed |

New coverage:

- `list_contacts` skips mapped navigation when the observed window title is
  already `微信 (通讯录)`;
- mapped Contacts navigation uses `accessibility_query(scope=self)` with an
  800 ms timeout to read the button frame, then `click(coordinates=...)` with a
  1200 ms timeout;
- mapped navigation now prefers packaged direct `screen_coordinates`, so normal
  coordinate-click switching sends no Accessibility frame query;
- if coordinate click is disabled, mapped navigation falls back to `AXPress`
  with a 2000 ms command timeout instead of inheriting the parent API timeout;
- if mapped navigation still fails, the WeChat API returns
  `wechat_navigation_failed` instead of falling back to the old selector path;
- SDK example fakes now model the frame-query plus coordinate-click command
  shape and the direct-coordinate command shape.

Manual proof still required:

- rerun `examples/wechat_contacts_list_test.py` against the real WeChat client
  with coordinate click enabled in `app-control.toml`;
- confirm the `listContacts.timing.durationMs` value is below 3000 ms;
- confirm `control_map_switch_contacts_skipped` appears when the window is
  already `微信 (通讯录)`, or that the coordinate click phases complete within
  the 800 ms + 1200 ms budgets when a tab switch is required.

## Additional Verification: WeChat Contact List Query Performance

Date: 2026-07-09.

This verification covers the follow-up fix for slow contact table reads after
mapped navigation was already optimized. The live smoke result showed
`listContacts.timing.durationMs = 12805` and
`control_map_contacts_0.timing.durationMs = 12397`, while the inner query
diagnostics reported a much smaller Accessibility traversal time.

| Area | Command | Result |
| --- | --- | --- |
| WeChat targeted tests | `PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py` | Passed: 94 tests |
| `computer-use-macos` targeted tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py` | Passed: 57 tests, 1 skipped |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 99 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 108 tests, 1 skipped |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 109 tests |
| Python compile check | `python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/control_map.py packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/computer-use-macos/src/computer_use_macos/client.py` | Passed |
| Whitespace/conflict check | `git diff --check` | Passed |

New coverage:

- packaged contacts control-map collections request only `AXStaticText`;
- contacts collection queries use the reduced attribute set and disable
  action-name collection;
- `list_contacts` can build contact items and `AXRow` actionRefs from
  static-text-only query results;
- special Contacts utility rows, section labels, and status text remain
  filtered before applying the caller limit;
- SDK example fakes model the text-only contacts query path;
- `computer-use-macos` Accessibility query source includes a role prefilter
  before full node reads.

Manual proof still required:

- restart `computer-use-macos serve` so the service loads the updated packages;
- rerun `examples/wechat_contacts_list_test.py` against the real WeChat client;
- confirm `listContacts.evidence.control_map_contacts_0.timing.durationMs`
  drops materially from the previous 12397 ms result;
- confirm `listContacts.timing.durationMs` is below 3000 ms or capture the new
  phase timings for the next optimization slice.
