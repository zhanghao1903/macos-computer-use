# Accessibility Selector Engine PR Description

## Current Review Status

`APPROVE` for reviewed head
`a77f5d45b0869f764105fef9cc62b45068e96fe4`. The current F6 report is
[`pr-review-macos-computer-use-3-a77f5d4.md`](./pr-review-macos-computer-use-3-a77f5d4.md).

`PRR-001` through `PRR-019` are resolved. Exact-head GitHub CI is green. The
post-fix transport passed real subprocess readiness/framing tests with 100
immediate query and 100 immediate action responses plus unknown-outcome
no-replay. Queue and delayed-startup expiration also write zero worker frames,
preserve the process, and allow same-process recovery. Historical live evidence
records a `2461 ms` public send and a `58 ms` warm Contacts-to-Chats action
without fallback.

## Problem

WeChat semantic APIs depended on brittle Accessibility paths and broad scans.
Layout, locale, row structure, app focus, and list reordering could make
contact, conversation, message, and action workflows slow or unsafe to adapt.

## Solution

This feature adds an internal Accessibility selector engine owned by
`computer-use-macos` and a packaged WeChat selector/control map owned by
`wechat-desktop-tool`:

- validated selector, matcher, constraint, relation, confidence, cache,
  collection, and actionRef contracts;
- bounded AX query execution with scoped roots, safe attributes,
  node/time/depth limits, step timing, and a warm query worker;
- verified AX action execution with a separate warm action worker and no replay
  after an uncertain mutating dispatch;
- stable control-map resolution with bounded selector fallback;
- current-frame, policy-gated coordinate fallback and semantic postconditions;
- selector-backed contacts, conversations, contact opening/focus, and visible
  message reads;
- verified app identity and exact row actionRef identity preconditions;
- honest visible-window list pagination with no synthetic cursor;
- optional application-injected `wechat.selector_profile_path`;
- coordinated `0.2.0` dependencies and clean wheel checks;
- privacy-safe, source-bound selector release proof v2.

No public `resolve_selector` or `extract_collection` protocol operation is
introduced.

## Consumer Impact

Consumers keep the existing semantic methods:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `focus_contact`
- `read_visible_messages`
- `read_contact_messages`
- `send_message`

Behavior changes:

- `focus_contact` delegates to verified `open_contact`; `send_message` proves
  the requested chat before drafting or submitting;
- legacy search-hotkey configuration remains accepted but does not drive normal
  contact switching;
- AXRow actionRefs include the exact current label in `labelIn` and fail before
  any backend/coordinate work when identity is missing;
- contact/conversation `nextPageToken` is always null, and non-null page tokens
  return `pagination_not_supported`;
- direct Accessibility queries and actions use independent warm workers;
- worker readiness is consumed before dispatch, and responses use fd-level
  newline framing to avoid buffered-response false timeouts;
- request serialization, worker queueing, startup, readiness, dispatch, and
  response waiting share one deadline; pre-dispatch expiration writes nothing
  and preserves a healthy worker;
- a query worker may fall back once because it is read-only, while an action
  worker never replays after dispatch;
- helper-backed WeChat selector construction remains unsupported in `0.2.0`.

New optional configuration:

- `[wechat] selector_profile_path`
- `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`

Invalid or policy-invalid override profiles fall back to the packaged profile.

## Safety

- app/window identity is verified before Accessibility reads and actions;
- unknown search focus fails before replacing or typing contact text;
- same-name candidates fail before action;
- coordinates come only from a current in-window AX frame and remain
  policy-gated;
- stale/reordered row refs fail exact identity preconditions;
- opened contact title is verified before reads, drafts, or sends continue;
- action worker timeout/protocol failure is returned without replay;
- an expired request waiting for worker access or startup returns before
  dispatch without terminating a healthy worker;
- submit uncertainty is non-retryable until manual inspection;
- public release proof excludes contacts, messages, titles, local paths,
  tokens, raw AX nodes, and operation observations.

## Verification

- root repository: 127 tests passed;
- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 139 tests passed, 1 skipped, with resource warnings
  treated as errors;
- `wechat-desktop-tool`: 123 tests passed;
- wheel/build/install compatibility, compile, release preflight, and diff checks
  passed;
- real subprocess tests passed coalesced framing, failed readiness, 100
  immediate query responses, 100 immediate action responses, fresh-worker
  stress, lock-expired and delayed-startup zero-write checks, same-process
  recovery, and timeout after synthetic action dispatch with zero replay;
- GitHub Actions run `29267848330`, job `86877739176`, passed every step
  against exact reviewed head `a77f5d4...`;
- one authorized public `send_message` verified `文件传输助手`, clipboard-
  drafted the message, accepted Return submission, and returned
  `success=true`, `submitted=true` in `2461 ms`;
- a separate no-submit probe started in Contacts and completed
  `open_contact("文件传输助手")` in `1272 ms`;
- that probe measured the remediated Chats `AXPress` at `58 ms` wall time,
  `44 ms` worker transport, `fallback=false`, with verified preconditions.

The public send started with Chats selected; the Contacts-origin transition was
measured separately without drafting or sending. Post-send read-back was not
requested, so `verified=false` means delivery was not independently confirmed.
No private raw payload is committed.

The live measurements predate the framing fix and establish AppKit worker
integration. The post-fix evidence directly exercises the private subprocess
protocol and no-replay boundary without performing another desktop mutation.

## Merge Decision

No open blocking finding remains for the reviewed implementation head. PR #3
is open, draft, and GitHub reports it mergeable. Marking the PR ready and
merging it remain repository-owner actions. Signed-helper and publication proof
belong to the later release phase.

## Release Note

Add an internal Accessibility selector engine, packaged WeChat selector/control
maps, verified selector-backed contact and message operations, exact actionRef
identity, visible-window list semantics, optional profile injection, warm
bounded AX query/action execution, performance diagnostics, and privacy-safe
release proof.
