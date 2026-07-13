# Accessibility Selector Engine PR Description

## Current Review Status

`INCOMPLETE` for reviewed head
`a49c57ef26a471b0e28f89223554895de3bcf8fd`. The fresh F6 report is
[`pr-review-macos-computer-use-3-a49c57e.md`](./pr-review-macos-computer-use-3-a49c57e.md).

No open code finding remains. `PRR-001` through `PRR-016` are resolved in the
source and deterministic regression suites. PR #3 remains draft until one
exact-code public send smoke to `文件传输助手` and current green GitHub CI are
observed.

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
- bounded AX query execution with a warm worker, scoped roots, safe attributes,
  node/time/depth limits, and step timing;
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
- helper-backed WeChat selector construction remains unsupported in `0.2.0`;
  direct and direct-backed local service modes remain supported.

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
- submit uncertainty is non-retryable until manual inspection;
- public release proof excludes contacts, messages, titles, local paths,
  tokens, raw AX nodes, and operation observations.

## Verification

- root repository: 127 tests passed;
- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 128 tests passed, 1 skipped;
- `wechat-desktop-tool`: 123 tests passed;
- wheel/build/install compatibility checks passed through the root suite;
- exact-head release preflight, compile, and diff checks passed;
- historical exact-code selector proof recorded 11 contacts, 14
  conversations, 30 visible messages, and every measured semantic API below
  3000 ms.

Not yet observed:

- a successful public `send_message` smoke after focus-path unification;
- green GitHub Actions for the pushed final code/doc head;
- Ruff, which is not installed.

The authorized live command ran exactly once and failed closed before contact
resolution because Codex remained frontmost after bounded focus recovery. No
Accessibility query/action, contact click, draft, submit, or message send ran,
and the attempt was not retried. Current GitHub Actions was observed, but job
`86671264119` never started because the account's Billing/spending limit needs
attention; this is external to the code and workflow.

## Required Before Merge

1. Correct the GitHub Billing/spending-limit condition and rerun the unchanged
   workflow to green.
2. Run the documented public send smoke where WeChat can remain frontmost,
   restricted to `文件传输助手`; do not retry an unknown submit result.
3. Confirm the target-title postcondition, submit result, and public API time.
4. Reissue the short F6 merge decision as `APPROVE` when both evidence gates
   pass.

## Release Note

Add an internal Accessibility selector engine, packaged WeChat selector/control
maps, verified selector-backed contact and message operations, exact actionRef
identity, visible-window list semantics, optional profile injection, bounded AX
performance diagnostics, and privacy-safe release proof.
