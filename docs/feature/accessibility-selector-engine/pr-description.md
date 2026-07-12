# Accessibility Selector Engine PR Description

## Current Review Status

`REQUEST_CHANGES` for head
`eb0e793b04dc05c4c9e1773380d73990a3d6dcbb`. The current F6 report is
[`pr-review-macos-computer-use-3-eb0e793.md`](./pr-review-macos-computer-use-3-eb0e793.md).

The 12 blockers from the previous `07fa052` snapshot are resolved. Four new
blocking findings remain:

- `PRR-013`: public `focus_contact`/`send_message` still use an obsolete live
  path;
- `PRR-014`: target-app-only AX requests do not prove the selected process;
- `PRR-015`: conversation row actionRefs do not revalidate contact identity;
- `PRR-016`: emitted pagination tokens cannot advance.

PR #3 remains draft until those findings are fixed and a new-head review passes.

## Problem

WeChat semantic APIs previously depended on brittle Accessibility paths and
broad row scans. Layout, locale, and row-structure changes made contact,
conversation, and message operations slow and difficult to adapt without
repackaging the tool.

## Solution

This feature adds an internal Accessibility selector engine owned by
`computer-use-macos` and a packaged WeChat selector/control map owned by
`wechat-desktop-tool`.

The implementation includes:

- validated selector, matcher, constraint, relation, confidence, cache,
  collection, and actionRef contracts;
- bounded AX query execution with a warm subprocess, scoped roots, safe
  attributes, node/time/depth limits, and per-step timing;
- fast stable-path control-map resolution with selector fallback;
- current-frame, policy-gated coordinate fallback and selected-state/title
  postconditions;
- selector-backed contacts, conversations, `open_contact`, and visible message
  reads;
- optional application-injected `wechat.selector_profile_path`;
- coordinated `0.2.0` package dependencies and clean wheel checks;
- privacy-safe, source-bound selector release proof v2.

No public `resolve_selector` or `extract_collection` protocol operation is
introduced in this feature.

## Consumer Impact

Consumers continue to use semantic methods:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `focus_contact`
- `read_visible_messages`
- `read_contact_messages`
- `send_message`

New optional configuration:

- `[wechat] selector_profile_path`
- `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`

Missing, unreadable, invalid, or policy-invalid override profiles fall back to
the packaged profile. `computer_use.backend=helper` is rejected when building a
selector-backed WeChat tool in `0.2.0`; direct and direct-backed local service
modes remain supported.

The SDK recent-messages example reads one configurable contact, defaults to
`文件传输助手`, accepts `--contact` and `--message-limit`, verifies the opened
chat title, and prints returned semantic message rows.

## API and Safety

- Existing semantic schema names remain:
  - `wechat.window.v1`
  - `wechat.contacts.v1`
  - `wechat.conversations.v1`
  - `wechat.messages.v1`
  - `wechat.open_contact.v1`
- `accessibility_action` supports verified `AXPress` and `AXSetFocus`.
- Mapped navigation verifies app/window identity, role, localized label,
  enabled state, current frame containment, action availability, and selected
  state after mutation.
- `open_contact` verifies the resulting chat title before reads continue.
- Unknown search focus fails before clear, paste, or Return.
- Coordinate clicks remain disabled unless configured and use only a current
  queried AX frame.
- Message submission remains explicit; selector resolution does not submit
  text.
- Public release proof excludes contact names, messages, window titles, local
  paths, tokens, raw AX nodes, and operation observations.

The current review requires the same safety model to be applied to the legacy
focus/send path, target-app-only AX operations, row actionRefs, and pagination
before merge.

## Verification

Current reviewed head:

- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 125 tests passed;
- `wechat-desktop-tool`: 122 tests passed;
- whitespace diff check: passed;
- GitHub Actions run `29196700910`, job `86660857594`: passed.

Latest exact-code-head selector proof (`6a74c1d...`):

- all 10 checks passed;
- 11 contacts, 14 conversations, and 30 visible messages;
- all measured public selector-backed APIs below 3 seconds;
- offscreen verified-search contact switch below 3 seconds;
- expired actionRef rejected before backend execution;
- frame-derived coordinate rule, target postcondition, and focus gate passed;
- raw observation absent and no message submitted;
- strict source-bound preflight passed.

F6 counterexamples:

- default `Command+F` `focus_contact` failed safely in 1781 ms;
- prior `Command+K` override failed at the same focus verification in 1278 ms;
- neither run drafted or submitted;
- an AXRow actionRef carried a contact label in its target but omitted it from
  executable preconditions;
- code inspection proved target-app-only AX workers select the frontmost app
  without checking its name;
- code inspection proved list `pageToken` is echoed but never consumed.

## Required Before Merge

1. Resolve `PRR-013` through `PRR-016` with deterministic regression tests.
2. Run the user-authorized live focus/send smoke to `文件传输助手` after the
   target title is verified.
3. Regenerate the privacy-safe proof for the final exact source SHA.
4. Run package/root/wheel/preflight suites and current-head CI.
5. Produce a fresh F6 report with no open blocking findings.

## Release Note

Add an internal Accessibility selector engine, packaged WeChat selector/control
maps, selector-backed semantic contact and message operations, optional
`wechat.selector_profile_path`, bounded AX performance diagnostics, and a
privacy-safe release proof.
