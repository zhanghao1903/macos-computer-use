# Accessibility Selector Engine

## Current Status

The implementation and deterministic verification are complete through F5
head `d85703a`. The replacement review resolved `PRR-025` and `PRR-026`,
revalidated `PRR-022` through `PRR-024`, and returned `APPROVE` with no blocking
findings. The review is recorded in
[`pr-review-macos-computer-use-3-d85703a.md`](https://github.com/zhanghao1903/macos-computer-use/blob/376401e8685c0f1c28705e8772f9f2e5b08c78ce/docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-d85703a.md)
and published at `376401e`.

GitHub Actions run
[`29428052131`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29428052131)
passed against exact implementation head `0b78eff`. Run
[`29429104699`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29429104699)
passed against exact F5/review head `d85703a`.

## Problem

WeChat semantic APIs previously depended on brittle Accessibility paths and
broad scans. The selector-engine work added fast, bounded, identity-checked AX
queries and actions, but a no-replay remediation later collapsed Apple's
definite unsupported errors into the same class as uncertain attempted
actions. Rows that safely rejected `AXPress` could therefore lose their one
configured fallback. Later review found that the new failure was absent from
the stable routing tuple and malformed or contradictory proof could still
trigger a fallback.

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
  `failureKind=accessibility_action_unsupported`, `actionAttempted=true`,
  `actionEffect=none`, and `nativeErrorCode`;
- all other native errors, including `-25204`, publish
  `actionEffect=unknown` and remain fail-closed.

`computer-use-macos` now declares
`errors.ACCESSIBILITY_ACTION_UNSUPPORTED` and includes it in
`COMPUTER_USE_FAILURE_KINDS`. Malformed action-effect values remain nested
diagnostics and are not promoted as trusted metadata.

The WeChat adapter permits exactly one existing fallback only when the new
failure kind, action, attempted state, effect, and native code form the exact
`AXPress/-25206` or `AXSetFocus/-25205` no-effect proof. Every public,
metadata, alias, and nested occurrence must have the expected type and agree.
It does not replay EOF, timeout, malformed, missing, contradictory, wrong-code,
generic attempted, or unknown-dispatch outcomes.

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
native failures, `nativeErrorCode`. Existing fields remain compatible.
Applications routing failures through `COMPUTER_USE_FAILURE_KINDS` now receive
the emitted `accessibility_action_unsupported` value as a declared package
failure.

## Safety

- App, bundle, window, snapshot, role, label, enabled state, and action
  preconditions are checked before native actions.
- A definite unsupported/no-effect result may use only one already configured,
  policy-gated fallback.
- `-25204`, transport loss, malformed response, missing proof, wrong
  action/code pairing, malformed values, contradictory duplicates, and unknown
  dispatch remain non-replayable.
- A failed fallback is final.
- Contact identity is verified before reads, drafts, or sends continue.
- Private UI content and raw observations are excluded from release proof.

## Verification

Clean-clone deterministic verification:

- root: 127 passed;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 143 passed, 1 skipped;
- `wechat-desktop-tool`: 138 passed;
- fifteen unsafe cross-package result modes repeated ten times: 150 executions,
  zero second mutation;
- native `AXPress/-25206` and `AXSetFocus/-25205`: exactly one configured
  fallback each;
- compile, release preflight, wheel build/install/import/API smoke, dependency
  rejection, whitespace, and clean-tree checks: passed;
- exact implementation and F5/review head GitHub Actions: passed.

No fresh real WeChat mutation was needed for this error-classification fix.
Historical authorized live evidence remains recorded separately and is not
represented as post-remediation proof.

## Finding State

- `PRR-001` through `PRR-021`: resolved.
- `PRR-022`: resolved; definite unsupported/no-effect recovery and uncertain
  outcome no-replay are implemented and deterministically verified.
- `PRR-023`: resolved; tracked F6 records and the GitHub PR body were
  synchronized and verified by the replacement review.
- `PRR-024`: resolved; both stable API documents publish one precedence rule.
- `PRR-025`: resolved; the emitted failure is declared in the stable public
  routing tuple.
- `PRR-026`: resolved; malformed, incomplete, or contradictory proof cannot
  trigger a second mutation.

## Release Record

The existing Unreleased changelog records the selector engine and fallback for
WeChat rows that omit or reject `AXPress`. The final release note should
explicitly mention both
dispatch/attempt-aware no-replay and the definite unsupported/no-effect single
fallback exception.

## Merge Decision

The replacement review approved the synchronized F6 snapshot and its
exact-head CI is green. This final description update does not change the PR
from draft automatically; marking ready and merging remain repository-owner
actions. Signed-helper proof and publication remain separate F7 release
actions.
