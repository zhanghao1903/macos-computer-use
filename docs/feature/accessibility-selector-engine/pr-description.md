# Accessibility Selector Engine

## Current Status

The implementation and deterministic verification are complete through F5
head `f19cbd9`. The replacement review resolved reopened `PRR-021`, `PRR-022`,
and `PRR-026`, revalidated `PRR-025`, and returned `APPROVE` with no blocking
findings. The review is recorded in
[`pr-review-macos-computer-use-3-f19cbd9.md`](https://github.com/zhanghao1903/macos-computer-use/blob/412a2d3/docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-f19cbd9.md)
and published at `412a2d3`.

GitHub Actions run
[`29463591047`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29463591047)
passed against exact F5/review head `f19cbd9`.

## Problem

WeChat semantic APIs previously depended on brittle Accessibility paths and
broad scans. The selector-engine work added fast, bounded, identity-checked AX
queries and actions, but a no-replay remediation later collapsed Apple's
definite unsupported errors into the same class as uncertain attempted
actions. Rows that safely rejected `AXPress` could therefore lose their one
configured fallback. Later review found that the new failure was absent from
the stable routing tuple. The latest review then exercised the real generated
producer and found that it omitted action, request action was not bound to the
response proof, and malformed attempted/dispatch values could still trigger a
fallback.

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

The latest remediation adds precise native action effect evidence:

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

## Verification

Clean-clone deterministic verification:

- root: 127 passed;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 144 passed, 1 skipped;
- `wechat-desktop-tool`: 140 passed;
- decision-focused tests repeated ten times: 350 unsafe subcases, zero second
  mutation;
- 20 production-generated `AXPress/-25206` and `AXSetFocus/-25205` executions:
  exactly one configured fallback each;
- compile, release preflight, wheel build/install/import/API smoke, dependency
  rejection, whitespace, and clean-tree checks: passed;
- exact F5/review head GitHub Actions run `29463591047`: passed.

No fresh real WeChat mutation was needed for this error-classification fix.
Historical authorized live evidence remains recorded separately and is not
represented as post-remediation proof.

## Finding State

- `PRR-001` through `PRR-020`: resolved.
- `PRR-021`: resolved; malformed or contradictory attempted/dispatch evidence
  cannot authorize another mutation.
- `PRR-022`: resolved; definite unsupported/no-effect recovery and uncertain
  outcome no-replay use the real generated producer and are deterministically
  verified.
- `PRR-023`: resolved; tracked F6 records and the GitHub PR body were
  synchronized and verified by the replacement review.
- `PRR-024`: resolved; both stable API documents publish one precedence rule.
- `PRR-025`: resolved; the emitted failure is declared in the stable public
  routing tuple.
- `PRR-026`: resolved; malformed, incomplete, contradictory, or
  request-mismatched proof cannot trigger a second mutation.

## Release Record

The existing Unreleased changelog records the selector engine and fallback for
WeChat rows that omit or reject `AXPress`. The final release note should
explicitly mention both
dispatch/attempt-aware no-replay and the definite unsupported/no-effect single
fallback exception.

## Merge Decision

The replacement review approved implementation/evidence head `f19cbd9`, and
its exact-head CI is green. This report/status-only update must receive final
exact-head CI and review renewal. It does not change the PR from draft
automatically; marking ready and merging remain repository-owner actions.
Signed-helper proof and publication remain separate F7 release actions.
