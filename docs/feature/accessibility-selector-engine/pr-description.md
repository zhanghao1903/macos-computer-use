# Accessibility Selector Engine

## Current Status

The implementation and deterministic verification are complete through F5
head `916ac1d`. The replacement review of synchronized F6 head `d5204dd`
resolved `PRR-022`, `PRR-023`, and `PRR-024` and returned `APPROVE` with no
blocking findings. The review is recorded in
[`pr-review-macos-computer-use-3-d5204dd.md`](https://github.com/zhanghao1903/macos-computer-use/blob/bf20423eaad97958980a467350d37bc4885fb5b6/docs/feature/accessibility-selector-engine/pr-review-macos-computer-use-3-d5204dd.md)
and published at `bf20423`.

GitHub Actions run
[`29396951638`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29396951638),
job `87292520782`, passed against exact F5 head `916ac1d`.

GitHub Actions run
[`29418761726`](https://github.com/zhanghao1903/macos-computer-use/actions/runs/29418761726),
job `87363517193`, passed against exact reviewed F6 head `d5204dd` after the
tracked and GitHub PR descriptions were synchronized.

## Problem

WeChat semantic APIs previously depended on brittle Accessibility paths and
broad scans. The selector-engine work added fast, bounded, identity-checked AX
queries and actions, but a no-replay remediation later collapsed Apple's
definite unsupported errors into the same class as uncertain attempted
actions. Rows that safely rejected `AXPress` could therefore lose their one
configured fallback. At the same time, F6 and platform descriptions continued
to publish obsolete review SHAs and decisions.

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

The WeChat adapter permits exactly one existing fallback only when the new
definite unsupported failure kind has complete, non-contradictory `none`
effect evidence. It does not replay EOF, timeout, malformed, missing,
contradictory, generic attempted, or unknown-dispatch outcomes.

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

## Safety

- App, bundle, window, snapshot, role, label, enabled state, and action
  preconditions are checked before native actions.
- A definite unsupported/no-effect result may use only one already configured,
  policy-gated fallback.
- `-25204`, transport loss, malformed response, missing or contradictory
  effect data, and unknown dispatch remain non-replayable.
- A failed fallback is final.
- Contact identity is verified before reads, drafts, or sends continue.
- Private UI content and raw observations are excluded from release proof.

## Verification

Clean-clone deterministic verification:

- root: 127 passed;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 142 passed, 1 skipped;
- `wechat-desktop-tool`: 137 passed;
- seven unsafe cross-package result modes repeated ten times: 70 executions,
  zero second mutation;
- native `AXPress/-25206` and `AXSetFocus/-25205`: exactly one configured
  fallback each;
- compile, release preflight, wheel build/install/import/API smoke, dependency
  rejection, whitespace, and clean-tree checks: passed;
- exact F5 head GitHub Actions: passed.

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

## Release Record

The existing Unreleased changelog records the selector engine, bounded warm AX
execution, no-replay behavior, and fallback for WeChat rows that omit or reject
`AXPress`. The final release note should explicitly mention both
dispatch/attempt-aware no-replay and the definite unsupported/no-effect single
fallback exception.

## Merge Decision

The replacement review approved the synchronized F6 snapshot and its
exact-head CI is green. This final description update does not change the PR
from draft automatically; marking ready and merging remain repository-owner
actions. Signed-helper proof and publication remain separate F7 release
actions.
