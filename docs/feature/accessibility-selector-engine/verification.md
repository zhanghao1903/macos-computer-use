# Accessibility Selector Engine Verification

- Verification date: 2026-07-12
- Branch: `codex/accessibility-selector-engine`
- Scope: historical selector-engine evidence plus F5 review-remediation
  verification
- Status: review-remediation automation passed on exact head `ebee2dd`; a new
  explicitly authorized real WeChat proof is still required before F5 closes

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
- the then-current private diagnostic report used schema
  `macos_computer_use.sdk.wechat_selector_engine_smoke_test.v1`. That schema is
  retained here as historical test evidence only; it cannot satisfy current
  strict release proof after proof v2 remediation.

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
`examples/wechat_contacts_recent_messages_test.py --contact "文件传输助手"
--message-limit 30` on the live desktop. That read-only fallback isolates
contact opening and visible-message extraction without relying on a send path.
Do not run `wechat_file_transfer_send_test.py` for this verification gate.

## Remaining Real WeChat Smoke Checklist

These checks require a real macOS desktop, Accessibility permission, running
WeChat, and the local app-control service. Remaining checks are required before
merge or release readiness:

1. Move or resize the visible WeChat main window before the run.
2. `list_conversations(limit=30)` returns at least one visible conversation and
   executable action reference.
3. `open_contact("文件传输助手")` switches the active chat without drafting or
   sending content and verifies the target title postcondition.
4. `read_visible_messages(limit=30)` returns between 1 and 30 visible rows.
5. `list_contacts(limit=30)` returns at least one semantic contact.
6. `[wechat] selector_profile_path` loads a valid local override, while an
   invalid override falls back to the packaged profile.
7. Expired action refs fail before backend execution.
8. Every measured semantic API completes within 3000 ms.
9. The public report is source-bound proof v2 with no sensitive content.

Recommended smoke setup:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m computer_use_macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

Then run the consolidated SDK smoke checklist against that service:

```bash
HEAD_SHA="$(git rev-parse HEAD)"
.venv/bin/python examples/wechat_selector_engine_smoke_test.py \
  --head-sha "$HEAD_SHA" \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-selector-engine-proof-v2.json \
  --contact "文件传输助手" \
  --conversation-limit 30 \
  --contact-limit 30 \
  --message-limit 30
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

## Historical Verification: AXRow ActionRef And Live Smoke Pass

Date: 2026-07-08.

This section records the live v1 smoke accepted by the pre-remediation release
gate. It remains useful runtime evidence for that historical head, but it is
not source-bound proof for the current branch and cannot close current F5.

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

## Historical Release Readiness Gate

The 2026-07-08 consolidated smoke was recognized by the historical v1 gate. The
current release gate requires a fresh, exact-head proof v2 and remains open as
recorded in the F5 review-remediation section below. Public selector protocol
commands remain deferred.

## Historical Release Proof v1 Recognition (Superseded)

The following describes the pre-remediation proof contract and is retained only
to explain historical test counts. Proof v1 is no longer strict or bundleable:

- report file name expected by release tooling:
  `wechat-selector-engine-smoke.json`;
- proof key: `wechat_selector_engine_smoke`;
- report schema:
  `macos_computer_use.sdk.wechat_selector_engine_smoke_test.v1`;
- recognized through repeated `--wechat-smoke-report` arguments on
  `scripts/release_preflight.py`;
- bundled through
  `scripts/release_proof_bundle.py --wechat-selector-engine-report`;
- enforced by the GitHub Release workflow before PyPI publishing.

The historical loader accepted a report when its summary, checklist,
protocol-shaped observations, profile checks, and expired actionRef result
passed. Current proof v2 instead uses a whitelist-only structural projection,
exact source SHA, non-zero collection evidence, timing limits, and recursive
sensitive-data rejection.

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

## Historical Verification: WeChat Mapped Navigation Click Performance

Date: 2026-07-09.

This verification covers the follow-up fix for slow mapped navigation clicks.
The live contact-list smoke showed `control_map_switch_contacts_0` spending
about 11.9 seconds in `accessibility_action` even though the target window was
already `微信 (通讯录)`.

The fixed-coordinate preference described by this historical slice was rejected
by review finding `PRR-003` and removed in remediation commit `9e11a75`. Current
runtime behavior ignores packaged `screen_coordinates`, queries the mapped AX
element, validates its semantic identity and current frame, then uses `AXPress`
or the validated frame center and verifies a semantic postcondition.

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
- the historical implementation preferred packaged direct
  `screen_coordinates`; this behavior is no longer executable;
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

## Additional Verification: Indexed Root Resolver And Visible Rows

Date: 2026-07-10.

This verification covers the follow-up fix for stable mapped root resolution
and large WeChat contact tables. The live smoke result after the text-only
query optimization still showed `listContacts.timing.durationMs = 12136` and
`control_map_contacts_0.timing.durationMs = 11803`, while the inner
Accessibility diagnostics reported only 277 ms.

| Area | Command | Result |
| --- | --- | --- |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/client.py packages/wechat-desktop-tool/src/wechat_desktop_tool/control_map.py packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/computer-use-macos/tests/test_package.py packages/wechat-desktop-tool/tests/test_profiles.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| `computer-use-macos` targeted query tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py -k accessibility_query` | Passed: 5 tests |
| WeChat targeted contact tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py packages/wechat-desktop-tool/tests/test_tool.py -k list_contacts` | Passed: 4 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 109 tests, 1 skipped |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 99 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 109 tests |
| Whitespace/conflict check | `git diff --check` | Passed |

New coverage:

- `accessibility_query` preserves an `attributePath` root resolver and
  normalizes `path_index` to `pathIndex`;
- `accessibility_query` preserves opt-in `preferVisibleRows`;
- the query script contains `AXContents`, `AXVisibleRows`, `child_entries`,
  and root-resolution diagnostics support;
- the packaged WeChat contacts control map loads resolver steps for
  `0/12/2/0`;
- contacts fast-path queries send the resolver payload and `preferVisibleRows`;
- contacts parsing filters the `联系人` utility row before caller limits.

Manual proof still required:

- restart `computer-use-macos serve` so the service loads the updated packages;
- rerun `examples/wechat_contacts_list_test.py` against the real WeChat client;
- confirm `listContacts.evidence.control_map_contacts_0.observation`
  contains `diagnostics.rootResolution.strategy = "attributePath"` and
  `diagnostics.preferVisibleRows = true`;
- confirm `listContacts.timing.durationMs` is below 3000 ms, or capture the new
  phase timings for another focused optimization.

## Additional Verification: Accessibility Query Step Timing Diagnostics

Date: 2026-07-10.

This verification covers the diagnostics slice that records each major
`accessibility_query` script phase. The preceding live smoke showed that
`control_map_contacts_0` spent about 10.6 seconds in the app-control wrapper
while the inner collect phase took only 16 ms, so future optimization needs
sub-step timings.

| Area | Command | Result |
| --- | --- | --- |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/client.py packages/computer-use-macos/tests/test_package.py` | Passed |
| `computer-use-macos` targeted query tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py -k accessibility_query` | Passed: 5 tests |
| Local no-permission script smoke | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python - <<'PY' ...` | Passed: failure response included `parseRequest`, `pyobjcImport`, and `permissionCheck` step timings |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 109 tests, 1 skipped |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 109 tests |
| Whitespace/conflict check | `git diff --check` | Passed |

New coverage:

- the query script source includes the `mark_step` timing helper;
- successful query responses include `diagnostics.stepTimings`;
- failure responses include timing diagnostics when available;
- source assertions cover timing steps for PyObjC import, permission checks,
  app selection, focused-window lookup, collect, and response serialization.

Manual proof still required:

- restart `computer-use-macos serve` so the service loads the updated packages;
- rerun `examples/wechat_contacts_list_test.py` against the real WeChat client;
- inspect
  `listContacts.evidence.control_map_contacts_0.observation.accessibilityQuery.diagnostics.stepTimings`;
- identify the largest step and use that as the next optimization target.

## Additional Verification: Persistent Accessibility Query Worker

Date: 2026-07-10.

This verification covers the performance slice that keeps a warm
`accessibility_query` worker process alive in default direct service mode. The
preceding live smoke showed `listContacts.timing.durationMs = 12575`, while the
inner query collected 75 nodes in 19 ms and spent about 10914 ms in
`pyobjcImport` plus about 952 ms in `appKitLoad`.

| Area | Command | Result |
| --- | --- | --- |
| Python compile check | `python -m py_compile packages/computer-use-macos/src/computer_use_macos/client.py packages/computer-use-macos/tests/test_package.py` | Passed |
| `computer-use-macos` targeted query tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest packages/computer-use-macos/tests/test_package.py -k accessibility_query` | Passed: 8 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 112 tests, 1 skipped |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s tests` | Passed: 109 tests |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 99 tests |
| Whitespace/conflict check | `git diff --check` | Passed |

New coverage:

- `accessibility_query` can return successful payloads through the warm worker
  without calling the one-shot runner;
- non-timeout worker protocol failures fall back to the existing subprocess
  execution path;
- returned query payloads include `diagnostics.transport.mode`, fallback state,
  worker return code, and bounded worker stderr when fallback occurs;
- the worker script source wraps the existing query script, emits a
  `workerReady` line, redirects query stdout, and loops over stdin requests.

Manual proof still required:

- restart `computer-use-macos serve` so the service starts the warm query
  worker;
- rerun `examples/wechat_contacts_list_test.py` against the real WeChat client;
- confirm the contact-list query reports
  `diagnostics.transport.mode = "worker"`;
- confirm `listContacts.timing.durationMs` is below 3000 ms or use
  `diagnostics.transport` and `diagnostics.stepTimings` for the next focused
  performance slice.

## Additional Verification: File Transfer Recent Messages Workflow

Date: 2026-07-10.

This verification covers the corrected end-to-end workflow:

1. open and focus WeChat;
2. enter the Chats section;
3. switch to `文件传输助手`;
4. verify the active chat title;
5. read and print up to 30 visible message rows.

Automated checks:

| Area | Command | Result |
| --- | --- | --- |
| Python compile check | `.venv/bin/python -m py_compile examples/wechat_contacts_recent_messages_test.py packages/computer-use-macos/src/computer_use_macos/_coordinate_click.py packages/computer-use-macos/src/computer_use_macos/client.py packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/computer-use-macos/tests/test_package.py packages/wechat-desktop-tool/tests/test_profiles.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py` | Passed |
| Protocol package tests | `PYTHONPATH=packages/app-control-protocol/src .venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | Passed: 54 tests |
| `computer-use-macos` package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests` | Passed: 112 tests, 1 skipped |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 101 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s tests` | Passed: 109 tests, including wheel and release preflight checks |
| Whitespace/conflict check | `git diff --check` | Passed |

New automated coverage proves:

- the SDK example starts in a different fake conversation, opens
  `文件传输助手`, then reads two fake message rows;
- the example exposes separate `openContact` and `readVisibleMessages` results
  and prints each returned message;
- a mismatched verified chat title returns `contact_not_found` and composed
  message reading stops before issuing a message-list query;
- `open_contact` enters the Chats section when the current navigation section
  is Contacts;
- a conversation row without `AXPress` uses its AX-frame center coordinate;
- the coordinate-click client invokes the internal Quartz event module and
  reports `method = quartz_cg_event`;
- the packaged profile loads both current `0/12` and older `0/11` control-map
  variants.

Live macOS and WeChat proof:

- a first smoke with the title-verification fix but the old AppleScript click
  backend correctly failed with `contact_not_found`, `messageCount = 0`, and
  `failedStep = openContact` instead of reading the unrelated active chat;
- a native Quartz click at the queried file-transfer row frame was visually
  confirmed to open `文件传输助手`;
- an isolated service using the updated source completed
  `examples/wechat_contacts_recent_messages_test.py` with:
  - `success = true`;
  - `contact = 文件传输助手`;
  - `currentChat = 文件传输助手`;
  - `messageCount = 30`;
  - `messageLimit = 30`;
  - `failedStep = null`;
- the example printed all 30 returned records to the terminal;
- measured SDK operation timings were:
  - `openWeChat = 463 ms`;
  - `openContact = 1175 ms`;
  - `readVisibleMessages = 2052 ms`;
- measured `openContact` phases included:
  - mapped target query: 96 ms;
  - Quartz coordinate click: 627 ms;
  - target-title verification query: 23 ms.

The live output was written only under `/private/tmp` and is intentionally not
tracked because it contains private chat data. The smoke changed focus and read
visible content only; it did not draft or send a message.

## Additional Verification: Alternate Control-Map Root Remediation

Date: 2026-07-10.

This verification covers the F6 review finding that an empty result from the
first configured control-map root could prevent the next compatible root from
being queried.

| Area | Command | Result |
| --- | --- | --- |
| Python compile check | `.venv/bin/python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py` | Passed |
| WeChat package tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | Passed: 103 tests |
| SDK example tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest tests.test_sdk_examples` | Passed: 9 tests |
| Root repository tests | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s tests` | Passed: 109 tests, including wheel and release preflight checks |
| Whitespace/conflict check | `git diff --check` for the remediation files | Passed |

New regression coverage proves:

- `list_conversations` queries `0/12/1/0`, observes an empty result, then
  queries `0/11/1/0` and returns the conversation found there;
- `open_contact` follows the same root order, opens the target returned by the
  second root, and verifies its title under `0/11/4`;
- selector/search fallback tests model both mapped roots returning empty before
  selector discovery begins;
- current-layout fast paths still stop after a non-empty `0/12` result.

The available live WeChat client uses the `0/12` layout and cannot provide real
desktop proof for the older `0/11` branch. That compatibility branch is covered
by deterministic command-sequence tests; the existing `0/12` live smoke remains
the real desktop proof for mapped target lookup, coordinate click, title
verification, and message reading.

## F5 Review-Remediation Integration Verification

Date: 2026-07-12.

Exact tested source:

- commit: `ebee2dd272d29caed2d6b1423f90f4d14e3a408d`;
- branch: `codex/accessibility-selector-engine`;
- Python: `3.12.7` in both the project and clean release environments;
- clean interpreter:
  `/tmp/accessibility-selector-release-clean-20260712/bin/python`;
- package isolation probe: `app_control_protocol`, `computer_use_macos`, and
  `wechat_desktop_tool` were all absent from the clean interpreter before the
  source-path tests ran.

### Exact clean release commands

The four unit-test commands from `.github/workflows/release.yml` ran with only
their declared `PYTHONPATH` source roots and no installed workspace package:

| Area | Result | Wall time |
| --- | --- | ---: |
| Root repository | Passed: 124 tests | 44.34 s |
| `app-control-protocol` | Passed: 55 tests | 0.11 s |
| `computer-use-macos` | Passed: 125 tests, 1 skipped | 0.52 s |
| `wechat-desktop-tool` | Passed: 116 tests | 0.52 s |

The root suite includes release preflight, wheel-check orchestration,
source-path mutation tests, strict proof-v2 validation, and package-boundary
coverage. The skipped macOS test is the existing environment-dependent test,
not a selector remediation failure.

### Build and repository gates

| Area | Command | Result |
| --- | --- | --- |
| Compile | `.venv/bin/python -m compileall -q packages examples scripts tests` | Passed |
| Default preflight | `.venv/bin/python scripts/release_preflight.py` | Passed in 1.26 s; only expected unavailable external-proof and sandbox socket warnings remained |
| Real wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py --wheel-dir /tmp/accessibility-selector-f5-wheels-ebee2dd` | Passed in 9.37 s |
| Branch diff | `git diff --check origin/main...HEAD` | Passed |
| Worktree diff | `git diff --check` | Passed |

The actual wheel run occurred after `compileall` had populated ignored cache
directories. It proved:

- all three packages built as version `0.2.0` from temporary sanitized source
  trees;
- `wheel-no-bytecode` passed for every wheel, with no `.pyc` or
  `__pycache__` member;
- dependency metadata and required selector/profile resources were present;
- the complete wheel set installed in a clean virtual environment;
- package imports and public API smoke passed from the installed wheels;
- pip rejected `wechat-desktop-tool==0.2.0` with the local `0.1.1`
  protocol/backend dependency set.

The project `.venv` does not include `pip`, `setuptools`, or `wheel`, so the
Anaconda Python was used only as the wheel build driver. Wheel installation and
API checks still ran in a new temporary virtual environment without source-tree
imports.

### Live proof status

No desktop operation ran during this remediation verification. The live proof
from 2026-07-08 remains useful historical coverage but is not source-bound
proof for `ebee2dd` and cannot close the current gate.

After explicit user authorization, the remaining smoke must use a moved or
resized WeChat window and the exact commit selected for that run, then:

1. open one unique configured contact without drafting or sending content;
2. list at least one contact and one conversation;
3. read between 1 and 30 visible messages;
4. keep every measured semantic API at or below 3000 ms;
5. prove the target postcondition and expired actionRef rejection;
6. emit public proof v2 and pass strict preflight for the exact source SHA;
7. pass sensitive-canary scanning while keeping private debug data outside the
   repository and release bundle.

F5 remains open until this authorized proof is captured and recorded. F6
new-head review and merge-readiness refresh must not start before that gate is
resolved.

## F5 Exact-Head WeChat Live Proof

Date: 2026-07-12.

Exact tested source:

- commit: `6a74c1d677c767bc68b993f038739fe092c9c204`;
- branch: `codex/accessibility-selector-engine`;
- package versions: coordinated `0.2.0` set;
- Python: project `.venv` Python 3.12;
- public proof:
  `/private/tmp/selector-live-selector-engine-proof-v2-6a74c1d.json`;
- private diagnostic:
  `/private/tmp/selector-live-selector-engine-private-6a74c1d.json`, retained
  locally and excluded from the repository and release bundle.

Before the proof series, Computer Use invoked the WeChat window's zoom action.
The exact-head query observed the resulting moved/resized window at
`x=307`, `y=31`, `width=1307`, `height=965`; no fixed profile coordinate was
used. The smoke opened `文件传输助手`, read visible content, and did not draft or
send a message.

### Public proof result

| Gate | Result |
| --- | --- |
| Exact source SHA | Passed |
| Required checklist operations | 10/10 passed |
| Contacts | 11 |
| Visible conversations | 14 |
| Visible messages | 30 |
| Focus gate | Passed |
| Target title postcondition | Passed |
| Expired actionRef rejection | Passed |
| Frame-derived coordinates only | Passed |
| Raw observation absent | Passed |
| Sensitive-field scan | Passed |
| `failedStep` | `null` |

Measured public API timings:

| API | Duration |
| --- | ---: |
| `openWeChat` | 251 ms |
| `inspectWindow` | 330 ms |
| `listConversations` | 336 ms |
| `openContact` | 829 ms |
| `readVisibleMessages` | 1095 ms |
| `listContacts` | 1446 ms |

Every measured API is below the 3000 ms feature target. The low-level contact
query reported `diagnostics.transport.mode=worker`.

### Explicit non-visible target branch

Before the exact-head proof, the target conversation was deliberately scrolled
out of the visible table and the same implementation was exercised through
`openMethod=search`. The branch selected existing search text, clipboard-pasted
the target, opened and title-verified `文件传输助手`, and returned 30 messages.
It measured `openContact=2457 ms` and `readVisibleMessages=1282 ms`, proving the
bounded global-search fallback also satisfies the performance target.

### Strict release validation

```bash
.venv/bin/python scripts/release_preflight.py \
  --wechat-smoke-report \
    /private/tmp/selector-live-selector-engine-proof-v2-6a74c1d.json \
  --expected-source-sha 6a74c1d677c767bc68b993f038739fe092c9c204
```

Result: exit 0. `external-proof:wechat_selector_engine_smoke` was verified;
only the separately scoped helper, TextEdit, submit, TestPyPI, and Trusted
Publisher proofs remained warnings.

GitHub Actions run `29196280097`, job `86659712229`, passed against the same
commit in 2m25s.

`release_proof_bundle.py --allow-incomplete` then built a local bundle with
the real selector proof and intentionally empty placeholders for unrelated
proof categories. It reported `wechat_selector_engine_smoke=true`, copied the
selector proof byte-for-byte, and rejected no selector content with
`--sensitive-canary 文件传输助手`. An exact forbidden-key/path scan found no
contact, raw observation, AX path, socket/config path, message text, `/Users/`,
or `/private/tmp/` value in the copied selector asset or aggregate proof.

F5 is complete for Accessibility Selector Engine review remediation. F6 may
now start from this exact head.

## F5 Follow-Up Verification For PRR-013 Through PRR-016

Date: 2026-07-12.

Reviewed implementation commit:
`5aa6266d` (`fix: close selector review follow-ups`) on
`codex/accessibility-selector-engine`.

### Automated regression

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s tests` | 127 passed in 42.04 s |
| Protocol package | `PYTHONPATH=packages/app-control-protocol/src .venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | 55 passed |
| macOS package | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests` | 128 passed, 1 skipped |
| WeChat package | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | 122 passed |
| Pytest cross-check | Package suites run separately | 55, 128, and 122 passed |
| Release preflight | `.venv/bin/python scripts/release_preflight.py` | Passed; only expected unavailable external-proof and socket warnings |
| Compile | `.venv/bin/python -m compileall -q packages examples scripts tests` | Passed |
| Worktree diff | `git diff --check` | Passed |
| Branch diff | `git diff --check origin/main...HEAD` | Passed |

Named counterexamples now pass for:

- selector-backed `focus_contact` and `send_message` command ordering with no
  global-search hotkey;
- target-app-only query/action requests using the configured bundle and
  rejecting unallowlisted targets before worker execution;
- row actionRef creation and execution with exact label identity, including
  fail-closed missing-identity cases;
- visible-window pagination with null continuation and explicit rejection of a
  caller-supplied token;
- CLI dry-run, smoke entrypoint, root SDK contract, and release-preflight
  command-sequence consumers.

Ruff could not run because no `ruff` executable/module is installed in the
project or Anaconda environment. Strict mypy ran and reported the existing
repository baseline of 184 errors across 15 files; broad type cleanup remains
outside this remediation scope and is not represented as a passing gate.

### Live send proof status

The user explicitly authorized one live smoke that may send only to
`文件传输助手`. The local service was restarted from the current worktree, but
the client command did not start: Codex rejected the local-action escalation
because its approval service had reached the current usage limit. The rejection
occurred before process creation, so no contact switch, draft, submit, or
message send happened.

The remaining exact-code proof command is:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
WECHAT_TOOL_CONTACT="文件传输助手" \
WECHAT_TOOL_MESSAGE="accessibility selector smoke 2026-07-12" \
WECHAT_TOOL_CONFIG=./app-control.toml \
WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock \
WECHAT_TOOL_TOKEN_FILE=./app-control.token \
WECHAT_TOOL_ALLOW_FOCUS_SELECT=1 \
WECHAT_TOOL_ALLOW_SEND=1 \
.venv/bin/python -m wechat_desktop_tool.examples.wechat_smoke
```

Run it at most once. If submission returns `unknown`, do not retry until the
message state is checked manually. F5 follow-up proof and fresh-head F6 approval
remain open until this command succeeds or an equivalent public
`send_message` proof is captured against the reviewed implementation.

### Post-review hardening verification

Commit `ca6d4a8412978e4be44f546ee839c187fb71a7d0` moves unlabeled-row identity
rejection ahead of every action/coordinate path and executes an already-issued
candidate actionRef without replacing its exact AX identity with a semantic
display label.

After that commit:

- root repository: 127 tests passed in 42.09 seconds;
- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 128 tests passed, 1 skipped;
- `wechat-desktop-tool`: 123 tests passed;
- `compileall` and worktree `git diff --check` passed.

The new counterexample supplies an unlabeled `AXRow` with a valid frame and
asserts `wechat_action_target_unverified` plus zero app-control commands. The
live send-proof limitation above is unchanged.

## F5 One-Shot Public Send Attempt And Current CI

Date: 2026-07-13 Asia/Shanghai (`2026-07-12T16:44Z`).

Reviewed branch head: `a49c57ef26a471b0e28f89223554895de3bcf8fd`.
The runtime source is unchanged from `ca6d4a8412978e4be44f546ee839c187fb71a7d0`;
the intervening commits contain review and verification documentation only.

The local service was restarted from the current worktree. The user-authorized
public smoke was then executed exactly once with target `文件传输助手`, explicit
focus/select permission, and explicit send permission.

Result: `send_message` returned `not_ready` before resolving or acting on a
contact. The initial target identity observation and the bounded focus recovery
both found `com.openai.codex` frontmost instead of the required
`com.tencent.xinWeChat`, so the operation failed closed.

| Step | Duration | Result |
| --- | ---: | --- |
| `open_app` | 86 ms | WeChat launch/activation command accepted |
| Initial `observe` | 539 ms | Target identity mismatch |
| Bounded `focus_app` | 2132 ms | Action accepted |
| Post-focus `observe` | 184 ms | Codex was still frontmost; stop |

No Accessibility query/action, contact-row click, `type_text`, draft, Return,
submit, or message-send command ran. No message was sent, and the smoke was not
retried. This is positive fail-closed evidence for target-app identity, but it
does not satisfy the successful public `send_message` merge gate.

Current PR metadata was also refreshed for
[PR #3](https://github.com/zhanghao1903/macos-computer-use/pull/3): the draft PR
is open and GitHub reports the branch as mergeable. Workflow run
`29200626621`, job `86671264119`, failed before any step started because recent
account payments failed or the repository spending limit must be increased.
This is an external GitHub Billing gate, not a product-code or workflow
failure. The separate `macos-latest` migration annotation is informational.

After GitHub Billing is corrected, rerun CI without changing the workflow. A
successful public send smoke must be captured in an environment where WeChat
can remain frontmost; do not retry an `unknown` submit result.

## F5 Authorized Public Send Success And Performance Result

Date: 2026-07-13 Asia/Shanghai (`2026-07-13T01:04:48Z`).

Tested branch head: `f2b98ed11da7a261f0e81ea8fb671cf5e633c4b2`.
Runtime source remains `ca6d4a8412978e4be44f546ee839c187fb71a7d0`;
commits between those heads contain review and verification documentation only.

The user granted a new one-shot authorization. The local service was started
from the current worktree, WeChat was activated immediately before the public
smoke, and `send_message` was executed once with target `文件传输助手`. The
attempt was not retried.

Result:

| Contract | Evidence |
| --- | --- |
| Public status | `ok`; `success=true` |
| Focus result | `focus_contact` succeeded through verified `open_contact` |
| Open method | `control_map_visible_action_ref` |
| Target postcondition | `currentChatTitle=文件传输助手`, confidence `0.95` |
| Draft input | Clipboard method, 39 characters, `submitted=false` at draft phase |
| Submit | Return key accepted, `submitted=true`, `sendAttempted=true` |
| Read-back verification | Not requested; top-level `verified=false` |
| Total public API duration | `3116 ms` |

Selected child timings from the same command:

| Child operation | Duration |
| --- | ---: |
| `open_app` | 67 ms |
| Frontmost-window `observe` | 504 ms |
| Chats selector query | 73 ms |
| Chats `AXPress` | 1042 ms wall time; 734 ms backend diagnostic |
| Visible-conversation query | 24 ms |
| Current-frame coordinate click | 482 ms |
| Contact-title verification | 20 ms |
| Clipboard `type_text` | 517 ms |
| Submit Return | 319 ms |

This closes the successful public focus/draft/submit evidence gate. It does not
claim delivery read-back because `verifyAfterSubmit` was false. No private raw
observation, message body, token, socket path, AX path, or conversation preview
is promoted into a tracked proof artifact.

The `3116 ms` result exceeds the approved `<=3000 ms` public semantic API
contract by `116 ms`. The live result therefore opens a performance remediation
gate even though functional submission succeeded. Remediation must preserve
frontmost-app identity, exact target identity, current-frame coordinates, and
the target-title postcondition; bypassing those checks is not acceptable.

## F5 Deterministic Verification For PRR-017 Remediation

Date: 2026-07-13.

The direct backend now uses a prewarmed worker for `accessibility_action` while
retaining the existing action script and subprocess fallback. Named regression
coverage proves:

- worker success returns the original action payload plus
  `diagnostics.transport.mode=worker` and emits no subprocess call;
- worker protocol failure returns `FAILED` without invoking the subprocess
  fallback;
- worker timeout returns `TIMEOUT` without invoking the subprocess fallback;
- the generated worker script compiles and contains ready, execution, failure,
  and empty-response protocol branches;
- existing direct action, configured-bundle inference, AXRow, and AXSetFocus
  tests continue to pass.

Commands and results:

| Scope | Command | Result |
| --- | --- | --- |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests` | 132 passed, 1 skipped |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s tests` | 127 passed in 41.695 s |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | 123 passed |
| Non-mutating worker protocol smoke | Start the real action worker and send an unsupported action request | Worker returned protocol success with `unsupported_accessibility_action=true`; no target or action was resolved |
| Non-mutating direct-client smoke | Send an `AXPress` request while WeChat has no focused AX window | Returned `focused_window_missing`, `actionAttempted=false`, `transport.mode=worker`; no action executed |
| Compile | `.venv/bin/python -m compileall -q packages examples scripts tests` | Passed |
| Release preflight | `.venv/bin/python scripts/release_preflight.py` | Passed; only expected unavailable external-proof and socket warnings |

No additional live desktop action was run. `PRR-017` remains open until the
remediation is committed and a newly authorized public send measures
`<=3000 ms`. This section does not replace that external proof.

## F5 Exact-Head Public Send And Warm-Action Live Proof

Date: 2026-07-13 Asia/Shanghai (`2026-07-13T12:14:23Z` through
`2026-07-13T12:18:44Z`).

Tested implementation head:
`5a010dab632eda2d3d9b39205f4f867c1fed0097`.

The user authorized one new live send. The local service was started from the
tested head and `send_message` was executed exactly once with target
`文件传输助手`, focus/select permission, and submit permission. The command was
not retried. A prior sandbox-denied `uv` startup exited before Python started
and before the service received a command, so it did not consume a send
attempt.

### Public send result

| Contract | Evidence |
| --- | --- |
| Public status | `ok`; `success=true` |
| Target | `focusedContact=文件传输助手` |
| Target postcondition | `currentChatTitle=文件传输助手`, confidence `0.95` |
| Open method | `control_map_visible_action_ref` |
| Draft input | Clipboard, 56 characters, draft phase `submitted=false` |
| Submit | Return accepted; `submitted=true`, `sendAttempted=true` |
| Read-back | Not requested; top-level `verified=false` |
| Total public API duration | `2461 ms` |

Selected child timings from the same command:

| Child operation | Duration |
| --- | ---: |
| `open_app` | 96 ms |
| Frontmost-window `observe` | 477 ms |
| Visible-conversation query | 96 ms |
| Current-frame coordinate click | 585 ms |
| Contact-title verification | 183 ms |
| Clipboard `type_text` | 595 ms |
| Submit Return | 393 ms |

This public result is `539 ms` below the `3000 ms` contract and `655 ms`
faster than the earlier `3116 ms` result. It proves API-level submission, not
delivery read-back. The command began with Chats already selected, and the log
therefore records `control_map_switch_chats_skipped`; it did not exercise the
new action worker during that send.

### Separate non-submit Contacts-to-Chats proof

To test the remediated component without sending another message, a second
service session performed two semantic operations:

1. `list_contacts(limit=1)` switched WeChat from Chats to Contacts;
2. `open_contact("文件传输助手")` switched back to Chats, opened the target, and
   verified the current chat title.

No draft, `type_text`, Return, submit, or send command ran in this probe. No
returned contact or message value is retained in tracked evidence.

| Measurement | Result |
| --- | ---: |
| Contacts `AXPress` wall time | 108 ms |
| Contacts worker transport | 95 ms; `fallback=false` |
| Chats selector query | 24 ms |
| Chats `AXPress` wall time | 58 ms |
| Chats worker transport/backend | 44 ms / 42 ms; `fallback=false` |
| Chats selected-state verification | 156 ms |
| Complete `open_contact` from Contacts | 1272 ms reported; 1273 ms wall |

The prior failing send measured the same Chats `AXPress` at `1042 ms`. The
exact-head warm-worker probe reduced that action by `984 ms` while retaining
bundle/app identity, snapshot, role, label, action, and selected-state
postconditions. The send and state-transition measurements are separate runs;
they are not represented as a single end-to-end sample.

### Exact-head CI

After the repository became public, GitHub Actions run `29217691709`, job
`86797719880`, was rerun unchanged against the exact tested head and passed.
Unit tests, release preflight, all three package suites, all three wheel builds,
wheel-content checks, and final sdist/wheel content verification completed
successfully.

Together, the successful `2461 ms` public send, the `1272 ms` real
Contacts-to-target open path, the `58 ms` warm `AXPress`, deterministic
no-replay tests, and exact-head green CI close the `PRR-017` performance
remediation gate without weakening safety checks. Residual limitations are one
timing sample per live path, no same-command send sample that started in
Contacts, and no post-submit delivery read-back.

## F5 Deterministic Closure For PRR-018

Date: 2026-07-13.

Tested implementation head:
`68d2e4f85a216f2898f40162650bae222552ec96`.

Validation ran from an isolated clone of that commit so unrelated dirty files
in the primary worktree could not affect source, package, or documentation
inputs. The change does not alter public commands, schemas, configuration, or
package versions.

### Protocol counterexamples

The `computer-use-macos` suite now launches real `_AccessibilityWorker`
subprocesses rather than substituting the previous fake worker. Named tests
prove all required boundaries:

| Counterexample | Required result | Result |
| --- | --- | --- |
| Readiness and a following response arrive in one OS write. | `start()` consumes only readiness and preserves the complete response frame. | Passed |
| Query worker emits immediate responses. | 100 requests produce 100 ordered responses, zero timeout, zero fallback. | Passed |
| Action worker emits immediate responses. | 100 requests produce 100 ordered responses, zero timeout, zero fallback. | Passed |
| Readiness reports `status=error`. | Startup fails before any request dispatch. | Passed |
| Action worker records dispatch and then returns no response. | Client reports `TIMEOUT`; one-shot runner call count remains zero. | Passed |
| Workers stop, fail readiness, or time out. | All pipes close without `ResourceWarning`. | Passed with warnings treated as errors |

The timeout counterexample's file write is a synthetic subprocess side effect,
not a macOS Accessibility action. It proves the parent observed that dispatch
had occurred while preserving the no-replay boundary.

### Exact commands and results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s tests` | 127 passed in 42.077 s |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src .venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | 55 passed |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src .venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 137 passed, 1 skipped |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | 123 passed |
| Compile | `.venv/bin/python -m compileall -q packages examples scripts tests` | Passed |
| Release preflight | `env -u PYTHONPATH .venv/bin/python scripts/release_preflight.py` | Passed; only expected socket and external-proof warnings |
| Wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py` | All three 0.2.0 wheels built, installed, imported, passed API smoke, and rejected the incompatible 0.1.1 dependency set |

The workspace `.venv` intentionally has no `pip` module, so an initial direct
`.venv/bin/python scripts/wheel_check.py` invocation stopped before building a
wheel. The check was rerun with the repository's available Python 3.12 runtime
at `/opt/anaconda3/bin/python` and passed completely. This is an environment
tooling distinction, not a product failure.

`git diff --check` initially found one extra blank line at the end of the newly
received `435d945` review Markdown. The non-semantic EOF whitespace was removed
in the verification documentation slice and must pass again on its resulting
head.

No real Accessibility query/action or WeChat send was run for this closure.
The prior `5a010da` live evidence remains historical performance context and is
not claimed as post-`PRR-018` live proof. A fresh review of the resulting head,
plus exact-head CI, remains required before merge readiness can be restored.

## F5 Deterministic Closure For PRR-019

Date: 2026-07-14.

Tested implementation head:
`55d76f1fef52cc17bfb4e44983576f897ae671f6`.

Validation ran from a clean isolated clone of that exact commit. The primary
worktree's unrelated modified and untracked files therefore could not affect
the tested source, package contents, or documentation. The clone remained
clean after verification, and `git diff --check` passed.

### Deadline counterexamples

The real-subprocess tests record each request frame received by the synthetic
worker and assert process identity before and after timeout. They prove both
pre-dispatch expiration boundaries introduced for `PRR-019`:

| Counterexample | Required result | Result |
| --- | --- | --- |
| The worker lock remains held longer than the queued request's complete timeout. | The queued call returns `TIMEOUT` while the lock is still held and the worker receives zero frames. | Passed |
| A new worker emits valid readiness, but startup completion is held until after the same request deadline. | The final pre-write deadline check returns `TIMEOUT` and the worker receives zero frames. | Passed |
| A pre-dispatch timeout occurs against a healthy process. | The process remains alive; a follow-up request uses the same process and is the only recorded frame. | Passed in both counterexamples |
| An action frame was already dispatched and its response times out. | The worker is terminated and the mutating request is not replayed through the one-shot runner. | Existing regression still passed |
| Readiness and immediate responses share or rapidly fill the stdout stream. | Framing remains ordered with zero false timeout across 100 query and 100 action responses. | Existing regressions still passed |

The timeout budget now covers request serialization, bounded lock acquisition,
worker startup/readiness, the final pre-write gate, and response waiting. This
is an internal worker transport correction; public commands, schemas,
configuration, dependencies, and package versions are unchanged.

### Exact commands and results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -m unittest discover -s tests` | 127 passed in 42.348 s, including wheel and release checks |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | 55 passed |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 139 passed, 1 skipped |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | 123 passed |
| Compile | `<workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only expected sandbox socket and unavailable external-proof warnings |
| Wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py` | All three 0.2.0 wheels built, installed, imported, passed API smoke, and rejected the incompatible 0.1.1 dependency set |
| Whitespace and clean tree | `git diff --check` and `git status --short` | Passed; no tracked or untracked output in the isolated clone |

Ruff is not installed in either the workspace virtual environment or the
available Anaconda runtime. Strict mypy was run against the changed
`computer_use_macos/client.py`; it reported the existing three-error baseline
at lines 660, 2488, and 2537, all outside the worker change. It is therefore
recorded as a non-passing repository baseline rather than claimed as proof for
this slice.

No real Accessibility query/action or WeChat send was executed. Every new
deadline test used a synthetic subprocess and a temporary request log. A fresh
review of the verified implementation head and exact-head CI remain required
before merge readiness can be restored.

## F5 Deterministic Closure For PRR-020

Date: 2026-07-14.

Tested implementation head:
`74d589057f994a0918c441243259543bd61a9f63`.

Validation ran from a clean isolated clone of that exact commit. Unrelated
modified and untracked files in the primary worktree could not affect source,
package, documentation, or wheel inputs. The clone remained clean after all
configured checks, and `git diff --check origin/main...HEAD` passed.

### Retryability counterexamples

The worker result now carries a private `request_dispatched` boundary and the
action transport publishes it as `requestDispatched` when known. Protocol
retryability is computed once and copied into both the top-level observation
and nested `ToolError`.

| Counterexample | Required result | Result |
| --- | --- | --- |
| An action request exhausts its deadline while waiting for the worker lock. | Zero worker frames and zero fallback calls; `requestDispatched=false`; both retryability fields are `true`. | Passed with a real synthetic worker subprocess. |
| A worker records an `AXPress` and then withholds its response. | Exactly one recorded action and zero fallback calls; `requestDispatched=true`; both retryability fields are `false`. | Passed with a real synthetic worker subprocess. |
| A legacy/fake worker returns a timeout without dispatch evidence. | Treat the unknown action outcome as non-retryable. | Passed. |
| The one-shot action subprocess times out without dispatch evidence. | Treat the unknown action outcome as non-retryable. | Passed. |
| A non-action command times out. | Preserve the existing retryable timeout contract. | Existing regression passed. |

### Exact commands and results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -m unittest discover -s tests` | 127 passed in 53.942 s, including all three wheel builds, isolated installs, API smoke, dependency rejection, and release checks |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | 55 passed |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 141 passed in 1.618 s, 1 skipped |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests` | 123 passed |
| Compile | `<workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only expected sandbox socket and unavailable external-proof warnings |
| Whitespace and clean tree | `git diff --check origin/main...HEAD` and `git status --short` | Passed; isolated clone remained clean |

The workspace virtual environment does not include mypy. `uv run mypy` was
also recorded as a non-passing repository baseline: it reported 29 strict
errors across six imported files, with no error on a line changed by this
remediation. Mypy is not a configured CI gate and is not claimed as passing
evidence.

This correction adds transport diagnostics and changes only action-timeout
recovery guidance; it does not change a command, protocol schema version,
configuration key, dependency, or package version. No live Accessibility
action or WeChat message was executed. A fresh review of the resulting
documented head and exact-head CI remain required before merge readiness can be
restored.

## F5 Deterministic Closure For PRR-021

Date: 2026-07-15.

Tested implementation head:
`b8d4bbdcc2da27dea6f2206713ceafb49c39a867`.

Validation ran from a clean local clone of that exact commit. The primary
worktree's unrelated modified and untracked files could not affect source,
tests, package contents, or wheel inputs. The clone remained clean after all
checks, and `git diff --check` passed.

### Cross-package no-replay counterexamples

The WeChat regression uses the real `ComputerUseClient`, real
`_AccessibilityWorker` subprocess framing, and a recording fake outer app
control. Each unsafe mode writes one `AXPress` request and then exercises a
different lower-layer result boundary.

| Worker outcome after dispatch | Required WeChat result | Result |
| --- | --- | --- |
| Worker exits before a response frame. | Return failure with zero click/key/strategy mutations. | Passed; one recorded `AXPress`, only one outer `accessibility_action`, zero runner fallback calls. |
| Worker withholds its response past the deadline. | Return non-retryable timeout with zero additional mutations. | Passed with `requestDispatched=true`. |
| Worker returns malformed JSON. | Fail closed instead of treating protocol failure as a safe click fallback. | Passed. |
| Worker returns structured native failure with `actionAttempted=true`. | Preserve attempted-action evidence and execute no fallback. | Passed. |
| Worker times out before dispatch while its lock is held. | Permit exactly one configured fallback because the write count is proven zero. | Passed; worker request log was absent and one selector click ran. |
| Worker explicitly reports an unsupported action without an attempt. | Permit exactly one configured fallback. | Passed; one action request and one selector click ran. |

The four unsafe modes were then executed together ten consecutive times with
`ResourceWarning` promoted to an error. All ten runs passed, covering 40
dispatch/outcome executions without a second mutation.

Path-specific tests additionally prove that mapped navigation, control-map and
selector visible-contact opening, search-box coordinate and AX focus, search
result Return recovery, and failed selector fallback all stop after an unsafe
mutation result.

### Exact commands and results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -m unittest discover -s tests` | 127 passed in 43.043 s, including wheel and release integration checks. |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -m unittest discover -s packages/app-control-protocol/tests` | 55 passed in 0.014 s. |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 141 passed in 1.531 s, 1 skipped. |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/wechat-desktop-tool/tests` | 132 passed in 0.812 s. |
| Cross-package stress | Core dispatched no-replay test repeated ten times with `ResourceWarning` as error. | 10 of 10 passed; each run covered EOF, timeout, malformed response, and native failure. |
| Compile | `PYTHONPYCACHEPREFIX=<temp> <workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed. |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only the sandbox socket and seven unavailable external-proof warnings remained. |
| Wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py` | All three 0.2.0 wheels built, installed in isolation, imported, passed API smoke, and rejected the incompatible local 0.1.1 dependency set. |
| Whitespace and clean tree | `git diff --check`, `git status --short`, and `git rev-parse HEAD` | Passed; clone remained clean at the tested SHA. |

Ruff and mypy are not installed in the workspace virtual environment and are
not configured CI gates; both module-version probes returned `No module named`.
No passing static-analysis claim is made.

This verification used only synthetic worker processes. No real Accessibility
action, WeChat contact switch, or message send was executed. A fresh review of
the resulting documentation head and exact-head GitHub CI remain required
before merge readiness can be restored.

## F5 Deterministic Closure For PRR-022

Date: 2026-07-15.

Tested implementation head:
`3fd41ce2459e6ebf79eeb9aa2ac65a68d56fd5a8`.

Validation ran from a clean local clone of that exact commit. Unrelated changes
and private smoke artifacts in the primary worktree could not affect source,
tests, documentation, or wheel inputs. The clone remained clean after every
check, and `git diff --check` passed.

### Unsupported/no-effect counterexamples

The cross-package tests use the real `ComputerUseClient`, the real warm action
worker protocol, and a recording outer WeChat adapter. They distinguish a
native call being attempted from the requested UI effect being performed.

| Native or transport result | Required downstream behavior | Result |
| --- | --- | --- |
| `AXPress` returns `kAXErrorActionUnsupported` (`-25206`). | Publish `accessibility_action_unsupported`, `actionAttempted=true`, `actionEffect=none`, and execute exactly one configured selector fallback. | Passed; one action request and one click. |
| `AXSetFocus` returns `kAXErrorAttributeUnsupported` (`-25205`). | Publish the same definite no-effect contract and execute exactly one selector-focus fallback. | Passed; one action request, one click, and one focus verification query. |
| Native action returns `kAXErrorCannotComplete` (`-25204`). | Publish `actionEffect=unknown` and execute zero downstream mutations. | Passed. |
| Worker exits, times out, or returns malformed JSON after dispatch. | Preserve unknown-outcome no-replay behavior. | Passed. |
| Unsupported failure kind conflicts with `actionEffect=unknown`. | Treat the evidence as contradictory and execute zero fallback. | Passed. |
| Definite-unsupported failure kind omits `actionEffect`. | Fail closed because no-effect was not proven. | Passed. |
| Legacy `unsupported_accessibility_action` claims a native attempt. | Do not apply the new precedence exception to the legacy result. | Passed. |
| Request expires before dispatch, or backend reports unsupported without an attempt. | Preserve the existing single safe fallback. | Passed. |

The seven unsafe worker modes were executed together ten consecutive times
with `ResourceWarning` promoted to an error. All ten runs passed, covering 70
dispatch/outcome executions without a second mutation. Mapped navigation,
public actionRef recovery, search focus, and both native unsupported error codes
also have path-specific regressions.

### Exact commands and results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests` | 127 passed in 44.070 s, including wheel and release integration checks. |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/app-control-protocol/tests` | 55 passed in 0.013 s. |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 142 passed in 1.563 s, 1 skipped. |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/wechat-desktop-tool/tests` | 137 passed in 0.963 s. |
| Unsafe cross-package stress | Core dispatched no-replay test repeated ten times with `ResourceWarning` as error. | 10 of 10 passed in 3.835 s; each run covered seven unsafe result shapes. |
| Compile | `PYTHONPYCACHEPREFIX=<temp> <workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed without dirtying the clone. |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only the expected sandbox socket and seven unavailable external-proof warnings remained. |
| Wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py` | All three 0.2.0 wheels built, installed in isolation, imported, passed API smoke, and rejected the incompatible local 0.1.1 dependency set. |
| Whitespace and clean tree | `git diff --check`, `git status --short`, and `git rev-parse HEAD` | Passed; clone remained clean at the tested SHA. |

Ruff and mypy remain unavailable in the workspace virtual environment and are
not configured CI gates. No real Accessibility action, WeChat contact switch,
or message send was executed; the SDK constants and synthetic native results
exercise this classification boundary deterministically. Exact-head GitHub CI
and a replacement review remain required after the F5 evidence commit.

## F5 Deterministic Closure For PRR-025 And PRR-026

Date: 2026-07-15.

Tested implementation head:
`0b78effec7ef822c589b4a77a1b5eb7642d6d818`.

Validation ran from a clean no-hardlink local clone of that exact commit at
`/private/tmp/macos-computer-use-prr025-026-0b78eff.nvDEoc/repo`. Unrelated
modified and untracked files in the primary worktree could not affect source,
tests, package contents, docs, or wheels. The clone remained clean after all
checks, and `git diff --check origin/main...HEAD` passed.

### Public Routing And Strict Proof Counterexamples

The computer-use package tests now route real normalized
`AXPress/-25206` and `AXSetFocus/-25205` observations through
`COMPUTER_USE_FAILURE_KINDS`. A malformed object-valued `actionEffect` is
preserved only in nested diagnostic evidence and no longer raises while
metadata is normalized.

The WeChat tests preserve exactly one configured fallback for both valid
native unsupported pairs. Every unsafe shape below returns after the first
`accessibility_action` and executes zero click, keypress, focus, or strategy
fallbacks:

| Unsafe proof or transport result | Required result | Result |
| --- | --- | --- |
| `-25204` paired with unsupported/none | Reject contradictory native proof. | Passed. |
| Wrong action/error pair | Reject instead of inferring no effect. | Passed. |
| Missing action, attempted state, effect, or native code | Reject incomplete proof. | Passed. |
| Non-string or empty effect | Reject malformed proof. | Passed. |
| Non-integer native code | Reject malformed proof. | Passed. |
| Conflicting failure kind, action, attempted state, effect, or code duplicate | Reject every contradictory duplicate. | Passed. |
| Worker EOF, timeout, or malformed frame after dispatch | Preserve unknown-outcome no-replay. | Passed. |
| Legacy unsupported result with positive attempt evidence | Do not apply the new exception. | Passed. |

The expanded cross-package unsafe test covers 15 distinct worker outcomes. It
was repeated ten consecutive times with `ResourceWarning` promoted to an
error: 10/10 runs passed, representing 150 unsafe dispatch/outcome executions
without a second mutation.

### Exact Commands And Results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests` | 127 passed in 51.076 seconds, including wheel and release integration checks. |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/app-control-protocol/tests` | 55 passed in 0.017 seconds. |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 143 passed in 1.602 seconds, 1 skipped. |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/wechat-desktop-tool/tests` | 138 passed in 1.193 seconds. |
| Unsafe cross-package stress | The 15-mode dispatched no-replay test repeated ten times with `ResourceWarning` as error. | 10/10 passed in 7.4 seconds; 150 unsafe outcomes and zero fallback. |
| Compile | `PYTHONPYCACHEPREFIX=<temp> <workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed without writing bytecode into the clone. |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only the expected sandbox socket and seven unavailable external-proof warnings remained. |
| Wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py` | All three 0.2.0 wheels built, installed in isolation, imported, passed API smoke, and rejected WeChat 0.2.0 with local 0.1.1 dependencies. |
| Whitespace and clean tree | `git diff --check origin/main...HEAD`, `git status --short`, and `git rev-parse HEAD` | Passed; the clone remained clean at the tested SHA. |

Ruff and mypy remain unavailable in the workspace virtual environment and are
not configured CI gates. No real Accessibility action, WeChat contact switch,
or message send was executed. Exact-head GitHub CI and a replacement review
remain required after this F5 evidence commit.

## F5 Deterministic Closure For Reopened PRR-021, PRR-022, And PRR-026

Date: 2026-07-16.

Tested implementation head:
`65f8855767971f864154c6173f134c6d03fea37b`.

Validation ran from the clean no-hardlink local clone
`/private/tmp/macos-computer-use-selector-f5-65f8855` at that exact detached
head. The clone used the workspace virtual environment only as its Python
runtime; every source, test, documentation, package, and wheel input came from
the clone. The primary worktree's unrelated modified and untracked files could
not affect the result. The clone remained clean after all checks, and
`git diff --check origin/main...HEAD` passed against base `fed6523`.

### Producer-To-Consumer And No-Replay Proof

The valid compatibility tests now execute the production-generated
`_accessibility_action_worker_script()` rather than a hand-shaped action
payload. Temporary test-only `objc` and `ApplicationServices` modules provide a
deterministic focused window and return Apple's two unsupported error codes.
The generated failure travels through the real warm-worker framing,
`ComputerUseClient` normalization, protocol observation conversion, and the
shared WeChat recovery policy.

| Scenario | Required result | Result |
| --- | --- | --- |
| Requested `AXPress`; generated native code `-25206`. | Result carries `action=AXPress`; one action and one configured click fallback. | Passed. |
| Requested `AXSetFocus`; generated native code `-25205`. | Result carries `action=AXSetFocus`; one action, one configured focus fallback, and one read-only verification query. | Passed. |
| Requested `AXPress`; response is internally valid `AXSetFocus/-25205`. | Reject before any fallback. | Passed; only `accessibility_action`. |
| Requested `AXSetFocus`; response is internally valid `AXPress/-25206`. | Reject before any fallback. | Passed; only `accessibility_action`. |
| Attempt evidence is truthy string `"true"` or falsey string `""`. | Treat as invalid, not as Boolean. | Passed; zero fallback. |
| Attempt aliases disagree or action/metadata containers are malformed. | Treat the complete evidence as invalid. | Passed; zero fallback. |
| Dispatch aliases contain a malformed duplicate or conflicting Boolean. | Treat dispatch evidence as invalid. | Passed; zero fallback. |
| Valid explicit unsupported or proven pre-dispatch result. | Preserve exactly one configured compatibility fallback. | Passed. |

The direct-client normalization regression also proves that malformed truthy
and falsey `actionAttempted` values remain only in the raw nested action result;
they are not promoted into normalized `action_attempted` or top-level
`actionAttempted` fields.

### Stress And Operation Counts

Six decision-focused test methods were repeated ten consecutive times with
`ResourceWarning` promoted to an error. Each iteration covered 15 dispatched
worker outcomes, 7 malformed attempt/dispatch shapes, 12 incomplete or
contradictory strict proofs, both request/response mismatch directions, and the
two valid production-generated native pairs. All 10 iterations passed in 7.3
seconds: 350 unsafe subcases executed zero downstream mutation, while 20 valid
native-pair executions each used exactly one configured fallback.

### Exact Commands And Results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests` | 127 passed in 42.752 seconds, including wheel and release integration checks. |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/app-control-protocol/tests` | 55 passed in 0.013 seconds. |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests` | 144 passed in 1.544 seconds, 1 skipped for sandbox socket restrictions. |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/wechat-desktop-tool/tests` | 140 passed in 1.135 seconds. |
| Adversarial stress | Six named producer/recovery test methods repeated ten times with `ResourceWarning` as error. | 10/10 passed in 7.3 seconds; 350 unsafe subcases and zero downstream mutation. |
| Compile | `PYTHONPYCACHEPREFIX=<external-temp> <workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed without writing bytecode into the clone. |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only the expected sandbox socket warning and seven unavailable external-proof warnings remained. |
| Wheel build/install | `/opt/anaconda3/bin/python scripts/wheel_check.py` | All three 0.2.0 wheels built, passed content checks, installed in isolation, imported, passed API smoke, and rejected WeChat 0.2.0 with local 0.1.1 dependencies. |
| Whitespace and clean tree | `git diff --check origin/main...HEAD`, `git status --short`, and `git rev-parse HEAD` | Passed; clone remained clean at `65f8855`. |

Ruff remains unavailable and strict mypy still has no accepted repository
baseline; neither is a configured CI gate. No real Accessibility action,
WeChat contact switch, or message send was executed. The fake framework modules
exist only inside temporary test directories and do not enter package artifacts.
Exact-head GitHub CI and a replacement review remain required after this F5
evidence commit.

## R5 Full Remediation Verification

Date: 2026-07-17.

Exact tested head:
`681170d0f459ff52b7281d957e3fd0b88d66a665`.

Validation ran in the clean no-hardlink clone
`/private/tmp/macos-computer-use-selector-r5-txUFXg/repo`. The clone was made
from the committed feature branch after the R2/R3 runtime fixes and R4 review
artifact correction. It remained clean after tests, compilation, preflight,
and wheel checks. The primary worktree's unrelated dirty files were not
available to the test process.

### Exact Commands And Results

| Scope | Command | Result |
| --- | --- | --- |
| Root repository | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` | 127 passed in 42.840 seconds, including wheel and release integration checks. |
| `app-control-protocol` | `PYTHONPATH=packages/app-control-protocol/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/app-control-protocol/tests -p 'test_*.py'` | 55 passed in 0.014 seconds. |
| `computer-use-macos` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests -p 'test_*.py'` | 155 passed in 1.543 seconds; 1 sandbox socket test skipped. |
| `wechat-desktop-tool` | `PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src <workspace>/.venv/bin/python -W error::ResourceWarning -m unittest discover -s packages/wechat-desktop-tool/tests -p 'test_*.py'` | 149 passed in 1.241 seconds. |
| Compile | `PYTHONPYCACHEPREFIX=<external-temp> <workspace>/.venv/bin/python -m compileall -q packages examples scripts tests` | Passed without writing bytecode into the clone. |
| Release preflight | `env -u PYTHONPATH <workspace>/.venv/bin/python scripts/release_preflight.py` | Passed; only the expected sandbox socket and seven unavailable external-proof warnings remained. |
| Wheel build/install | `/opt/anaconda3/bin/python3 scripts/wheel_check.py` | All three 0.2.0 wheels built, passed metadata/content/no-bytecode checks, installed together in isolation, imported, passed API smoke, and rejected WeChat 0.2.0 with local 0.1.1 dependencies. |
| Historical review result | `/opt/anaconda3/bin/python3 <workspace>/.agents/skills/pr-review/scripts/validate_review_result.py docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-f19cbd9.json` | `VALID`; corrected SHA-256 `01ed707a583c533e50c7a736d3dd235832211701db42552f3419d47c72b04653`. |
| Latest blocking review result | Same validator against `pr-review-macos-computer-use-3-59c6fb5.json` | `VALID`. |
| Diff and clean tree | `git diff --check origin/main...HEAD`, `git status --short`, and `git rev-parse HEAD` | Passed; clone remained clean at `681170d`. |

The report validator is an untracked workspace skill and therefore was invoked
by absolute path against the committed JSON inside the clean clone. The skill
itself was not treated as feature content or test input.

### Exact-Head CI And PR State

GitHub Actions workflow `CI / test` passed for exact head `681170d`:

- run: https://github.com/zhanghao1903/macos-computer-use/actions/runs/29519349230
- job: https://github.com/zhanghao1903/macos-computer-use/actions/runs/29519349230/job/87692268230
- started: `2026-07-16T17:20:21Z`
- completed: `2026-07-16T17:22:56Z`

At observation time, PR #3 was open and draft, mechanically mergeable, and had
merge state `CLEAN`. Its remote head matched full SHA
`681170d0f459ff52b7281d957e3fd0b88d66a665`.

### Limitations

Ruff is unavailable in the workspace environment. Repository-wide strict mypy
still has no accepted clean baseline and is not a configured CI gate. No live
Accessibility action, WeChat contact switch, message read, draft, or send was
executed. Signed-helper, TestPyPI, PyPI, and trusted-publisher proof remain
release-stage gates rather than merge-review evidence for this remediation.

## R9 Remediation Evidence For Review `e86181a`

Date: 2026-07-17.

Reviewed head:
`e86181a9c300cd9929d4ce61c08188a1a36f3bb9`.

Latest implementation head:
`45774fe`.

The latest review reopened or introduced five blockers. The following
implementation slices provide candidate remediation without changing the
authoritative `REQUEST_CHANGES` decision:

| Finding | Implementation | Deterministic evidence |
| --- | --- | --- |
| `PRR-037` | `60138f3` | Generated query/action workers accept exact bundle plus localized alias, retain name-only fallback, and reject wrong, hidden, terminated, or absent targets. |
| `PRR-038` | `60138f3`, `7d870ac` | All three produced values are declared, exported, registered, normalized, documented, and imported from an isolated installed wheel. |
| `PRR-026` | `7464ad1` | Result evidence `performed`, ToolError evidence `unknown`, nested `-25204`, and contradictory pre-dispatch evidence execute the original operation only and zero fallback mutations. |
| `PRR-039` | `1967107` | Zero, one, and multiple candidates under limit, time-budget, and depth truncation across all three paths execute zero click, Accessibility action, Return, draft, and submit operations. |
| `PRR-023` | F6 tracked-record update | Merge-readiness and PR-description records preserve the current decision and pending re-review instead of publishing obsolete approval. |

An additional forward-risk regression in `45774fe` proves that failure of the
final search-result query is not interpreted as an empty candidate list. The
structured permission, timeout, transport, truncation, or generic query
failure returns before Return, draft, or submit.

### Latest Local Results

| Scope | Result |
| --- | --- |
| Root repository | 128 passed, including wheel and release integration checks. |
| `app-control-protocol` | 55 passed. |
| `computer-use-macos` | 158 passed, 1 sandbox socket test skipped. |
| `wechat-desktop-tool` | 154 passed after the final search-query regression. |
| Compile and diff | Passed. |
| Release preflight | Passed with the expected sandbox socket and unavailable external-release-proof warnings. |
| Three-wheel package proof | Built and installed all packages in isolation, imported public APIs, checked metadata/content/no-bytecode rules, and rejected the incompatible old dependency set. |
| Latest review result | `pr-review-macos-computer-use-3-e86181a.json` validates under the repository review-result validator. |

### Limitations

- These are implementation-owner claims. An independent exact-head re-review
  must reproduce the blockers and decide whether they are closed.
- No live Accessibility action, contact switch, message read, draft, or WeChat
  send was executed.
- At the time this record was prepared, GitHub access through the configured
  local proxy returned HTTP 503. Remote push, exact-head CI observation, and
  live PR-body synchronization therefore remained pending external gates.
- Signed-helper, notarization, TestPyPI/PyPI, and trusted-publisher proof remain
  release-stage work.

## R10 Selector Contract Remediation For Review `eb543ec`

Date: 2026-07-17.

Reviewed head:
`eb543ec9eb3800de104dadeb5d2fbb1382d14416`.

Candidate runtime implementation head:
`b01aa01312a8c64f3476c966ee5659eaed9eed6f`.

The current authoritative review opened five blockers. The following slices
provide candidate remediation while preserving its `REQUEST_CHANGES` decision:

| Finding | Implementation | Deterministic evidence |
| --- | --- | --- |
| `PRR-039` | `63a45cf`, `b01aa01` | Failed, truncated, malformed, and mixed-root query results are final across control-map, visible-row, and search-result paths; composite sends perform zero downstream mutation. |
| `PRR-040` | `bb8506d` | Absent `any_of` retains default behavior, while explicit empty, falsey, and malformed forms are rejected for JSON and TOML-compatible inputs. |
| `PRR-041` | `bb8506d` | `NaN` and infinity are rejected for confidence, weights, relation distances, and frame members in parsed and directly constructed profiles. |
| `PRR-042` | `63a45cf` | Canonical, generated, and narrow legacy success/failure envelopes remain supported; malformed and contradictory fields fail before candidate or cache creation. |
| `PRR-043` | `b01aa01` | Seven search-result cases prove that empty, malformed, offscreen, or ambiguous sets cannot action a target, press Return, draft, or submit. |

### Candidate Verification Results

| Scope | Result |
| --- | --- |
| Root repository | 128 passed, including all three wheel builds, isolated install/import/API smoke, and incompatible old dependency rejection. |
| `app-control-protocol` | 55 passed. |
| `computer-use-macos` | 168 passed, 1 sandbox socket test skipped. |
| `wechat-desktop-tool` | 159 passed. |
| Compile and diff | Passed. |
| Release preflight | Passed with the expected sandbox socket and unavailable external-release-proof warnings. |
| Latest review result | `pr-review-macos-computer-use-3-eb543ec.json` validates under the repository review-result validator. |

### Limitations

- These are implementation-owner claims. An independent exact-head re-review
  must reproduce the blockers and decide whether they are closed.
- Exact-head GitHub CI and live PR-body synchronization are pending until the
  F5/F6 evidence commit is pushed.
- No live Accessibility action, contact switch, message read, draft, or WeChat
  send was executed.
- Signed-helper, notarization, TestPyPI/PyPI, and trusted-publisher proof remain
  release-stage work.
