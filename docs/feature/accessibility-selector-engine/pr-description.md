# Accessibility Selector Engine

## Current Status

The latest authoritative review is
[`pr-review-macos-computer-use-3-eb543ec.md`](./pr-review-macos-computer-use-3-eb543ec.md)
for reviewed head `eb543ec9eb3800de104dadeb5d2fbb1382d14416`.
Its decision is `REQUEST_CHANGES`, with blockers `PRR-039`, `PRR-040`,
`PRR-041`, `PRR-042`, and `PRR-043`.

Candidate runtime fixes are implemented through `b01aa01`. The PR remains
draft and must not be treated as approved or merged until the exact remote head
passes CI and an independent re-review closes those findings.

## Problem

The latest review identified five fail-open contract gaps:

- an earlier failed, truncated, or malformed contact query could be hidden by
  a later root or target strategy and still lead to mutation;
- an explicit empty or falsey `any_of` matcher could be erased and broaden a
  selector;
- non-finite profile numbers could bypass range validation;
- malformed or contradictory query envelopes could normalize as success;
- empty, malformed, offscreen, or ambiguously filtered search results could
  reach Return, draft, and submit.

## Candidate Remediation

- `bb8506d` preserves key presence when parsing `any_of` and rejects explicit
  empty or malformed matcher sets.
- `bb8506d` rejects non-finite confidence, weight, relation-distance, and frame
  values at parser and validator boundaries.
- `63a45cf` validates schema, status, availability, failures, nodes,
  diagnostics, retryability, and truncation before selector resolution.
- `b01aa01` treats every unsafe WeChat target-query result as final across
  roots and strategies.
- `b01aa01` decides search-result cardinality before frame filtering, requires
  one finite in-window target, and reserves Return for a verified target action
  with definite no-effect evidence.
- `057154a`, `27fe73f`, and `4601ecf` preserve the review, remediation design,
  and implementation plan for this lifecycle pass.

## Consumer Impact

Public method signatures and request schemas are unchanged. Invalid selector
profiles now fail during configuration validation. Malformed query envelopes
return `selector_query_failed` instead of producing candidates or cache
entries. Unsafe WeChat target evidence returns existing structured failure
kinds before any contact action or message operation.

## Safety

- Incomplete evidence from one root cannot be overwritten by a later root.
- A failed visible-contact query cannot continue into mutating search.
- Candidate uniqueness is established before visibility filtering.
- Invalid frame members are rejected rather than coerced to zero.
- Empty or unverified search sets cannot use Return as an implicit selection.
- Composite-send regressions assert zero target action, Return, draft, and
  submit after every unsafe query or candidate result.
- No live WeChat mutation was used as remediation evidence.

## Verification

Latest broad local candidate verification passed:

- root repository: 128 tests;
- `app-control-protocol`: 55 tests;
- `computer-use-macos`: 168 tests, 1 sandbox socket skip;
- `wechat-desktop-tool`: 159 tests;
- compilation, release preflight, three-wheel build and isolated API smoke,
  old dependency rejection, latest review-result validation, and whitespace
  checks.

The new tests exercise strict profile parsing, all supported query envelope
families, contradictory response aliases, all three WeChat contact-target
paths, mixed-root continuation, the seven-case search candidate matrix, and
the full `send_message` side-effect sequence.

## Finding State

| Finding | State |
| --- | --- |
| `PRR-039` | Candidate fixes in `63a45cf` and `b01aa01`; independent revalidation pending. |
| `PRR-040` | Candidate fix in `bb8506d`; independent revalidation pending. |
| `PRR-041` | Candidate fix in `bb8506d`; independent revalidation pending. |
| `PRR-042` | Candidate fix in `63a45cf`; independent revalidation pending. |
| `PRR-043` | Candidate fix in `b01aa01`; independent revalidation pending. |

All previously resolved findings remain subject to regression review at the
new exact head.

## Merge Decision

The authoritative decision remains `REQUEST_CHANGES`. Keep the PR draft. Do
not mark ready, approve, or merge until exact-head CI is green, the live and
tracked F6 surfaces agree, and a new independent review grants approval.
