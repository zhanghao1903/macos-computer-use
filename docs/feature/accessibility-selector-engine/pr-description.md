# Accessibility Selector Engine

## Current Status

The latest authoritative review is
[`pr-review-macos-computer-use-3-59c6fb5.md`](./pr-review-macos-computer-use-3-59c6fb5.md)
for head `59c6fb5`, published at `0a1e5cb`. Its decision is
`REQUEST_CHANGES`. Runtime remediation is complete at `3abc501`, and the
historical `f19cbd9` machine-result integrity defect has been corrected without
changing its represented decision or inventing exact-head test runs. Full
exact-head verification, GitHub CI, and a new re-review remain required before
merge.

## Problem

WeChat semantic APIs previously depended on brittle Accessibility paths and
broad scans. The selector-engine work added fast, bounded, identity-checked AX
queries and actions, but a no-replay remediation later collapsed Apple's
definite unsupported errors into the same class as uncertain attempted
actions. Rows that safely rejected `AXPress` could therefore lose their one
configured fallback. Later reviews found producer/proof defects and broader
boundedness and trust-boundary gaps: truncated selector decisions, collection
step drift and pagination errors, background-app targeting, non-atomic profile
overrides, private AX evidence leakage, ambiguous failure routing, incomplete
failure registration, and an invalid historical review artifact.

## Solution

This PR provides an internal Accessibility selector engine owned by
`computer-use-macos` and packaged WeChat selector/control maps owned by
`wechat-desktop-tool`:

- validated selector, relation, confidence, cache, collection, and actionRef
  contracts;
- bounded AX queries with scoped/indexed roots, safe attributes, time and node
  limits, timing diagnostics, and a warm query worker;
- verified AX actions with a separate warm action worker and dispatch-aware
  no-replay behavior;
- packaged WeChat navigation, contact, conversation, search, chat, and message
  maps with optional profile injection;
- policy-gated current-frame or selector fallbacks and semantic
  postconditions;
- selector-backed inspect, list, open/focus, message-read, draft, and send
  workflows;
- privacy-safe source-bound release proof and coordinated package version
  `0.2.0`.

The latest remediation adds these invariants:

- truncated selector/collection data cannot produce a normal match, cache
  write, or false not-found result;
- collection pages count accepted semantic records and enforce the public
  query limit;
- generated query/action/tree workers target only the current visible
  frontmost application;
- WeChat profile and control-map overrides activate as one validated pair;
- all supported action-proof containers participate in one request-bound,
  fail-closed consistency check;
- query/action/observe evidence and events use privacy-safe allowlists;
- structured permission, timeout, transport, and truncation causes take
  precedence over message keywords;
- all emitted worker failure kinds are exported and registered.

The earlier action-recovery remediation adds precise native action effect
evidence:

- successful native calls publish `actionEffect=performed`;
- `AXPress/-25206` and `AXSetFocus/-25205` publish
  `failureKind=accessibility_action_unsupported`, the exact requested `action`,
  `actionAttempted=true`, `actionEffect=none`, and `nativeErrorCode`;
- all other native errors, including `-25204`, publish
  `actionEffect=unknown` and remain fail-closed.

`computer-use-macos` now declares
`errors.ACCESSIBILITY_ACTION_UNSUPPORTED` and includes it in
`COMPUTER_USE_FAILURE_KINDS`. Malformed action-effect or attempted values remain
nested raw diagnostics and are not promoted as trusted metadata.

The WeChat adapter permits exactly one existing fallback only when the new
failure kind, action, attempted state, effect, and native code form the exact
`AXPress/-25206` or `AXSetFocus/-25205` no-effect proof. Every public,
metadata, alias, and nested occurrence must have the expected type, agree, and
match the outbound request action. Attempted and dispatch evidence is parsed as
absent, valid true, valid false, or invalid without truthiness coercion. It does
not replay EOF, timeout, malformed container/value, missing, contradictory,
request-mismatched, wrong-code, generic attempted, or unknown-dispatch outcomes.

No public `resolve_selector` or `extract_collection` protocol operation is
introduced. No command or schema version changes in the remediation.

## Consumer Impact

Consumers continue using the existing semantic methods:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `focus_contact`
- `read_visible_messages`
- `read_contact_messages`
- `send_message`

Direct `accessibility_action` observations now add `actionEffect` and, for
native failures, the requested `action` plus `nativeErrorCode`. Existing fields
remain compatible.
Applications routing failures through `COMPUTER_USE_FAILURE_KINDS` now receive
the emitted `accessibility_action_unsupported` value as a declared package
failure.
Truncated WeChat selector reads return the stable
`wechat_query_truncated` failure rather than an operation-specific not-found
result. Raw Accessibility query payloads are available only through explicit
`inspect_window(include_raw=True)` result data, not normal evidence or events.

## Safety

- App, bundle, window, snapshot, role, label, enabled state, and action
  preconditions are checked before native actions.
- A definite unsupported/no-effect result may use only one already configured,
  policy-gated fallback.
- `-25204`, transport loss, malformed response, missing proof, wrong
  action/code pairing, request/response action mismatch, malformed truthy or
  falsey values, malformed containers, contradictory duplicates, and unknown
  dispatch remain non-replayable.
- A failed fallback is final.
- Contact identity is verified before reads, drafts, or sends continue.
- Private UI content and raw observations are excluded from release proof.
- Background or hidden applications cannot receive generated AX query, action,
  or tree work.
- Truncated data and malformed selector profile steps cannot drive a semantic
  decision.

## Verification

Current remediation verification:

- generic selector slice: 72 selector tests, 83 computer-use package tests,
  and 9 WeChat profile tests passed;
- WeChat boundary slice: 149 package tests passed;
- WeChat source/test compilation and whitespace checks passed;
- corrected `f19cbd9` machine result validates under schema/invariant validator
  version `1.1`, with SHA-256
  `01ed707a583c533e50c7a736d3dd235832211701db42552f3419d47c72b04653`.

Repository-wide tests, release preflight, wheel/install checks, and GitHub CI
must be rerun at the final remediation head. Earlier `65f8855` full-suite and
`f19cbd9` CI evidence remains historical support, not current-head proof.

No fresh real WeChat mutation was needed for this error-classification fix.
Historical authorized live evidence remains recorded separately and is not
represented as post-remediation proof.

## Finding State

- `PRR-001` through `PRR-020`, plus `PRR-022` through `PRR-025`: previously
  resolved; final regression revalidation remains part of the next review.
- `PRR-021`, `PRR-026`, `PRR-030`, `PRR-033`, `PRR-035`: remediated in
  `3abc501`.
- `PRR-028`, `PRR-029`, `PRR-031`, `PRR-032`, `PRR-034`, `PRR-036`:
  remediated in `b9493a8`.
- `PRR-027`: historical machine result corrected and validator-clean; final
  downstream re-review remains pending.

## Release Record

The existing Unreleased changelog records the selector engine and fallback for
WeChat rows that omit or reject `AXPress`. The final release note should
explicitly mention both
dispatch/attempt-aware no-replay and the definite unsupported/no-effect single
fallback exception.

## Merge Decision

The current authoritative decision remains `REQUEST_CHANGES`. Do not mark the
PR ready or merge until full final-head validation, exact-head GitHub CI, and a
new schema-valid review close all findings and grant approval. Signed-helper
proof and publication remain separate release actions.
