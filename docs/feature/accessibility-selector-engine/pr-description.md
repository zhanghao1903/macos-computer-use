# Accessibility Selector Engine

## Current Status

The latest authoritative review is
[`pr-review-macos-computer-use-3-e86181a.md`](./pr-review-macos-computer-use-3-e86181a.md)
for reviewed head `e86181a9c300cd9929d4ce61c08188a1a36f3bb9`.
Its decision is `REQUEST_CHANGES`, with blockers `PRR-023`, `PRR-026`,
`PRR-037`, `PRR-038`, and `PRR-039`.

Candidate fixes are implemented through `45774fe`. The PR remains draft and
must not be treated as approved or merged until the remote head passes CI and
an independent exact-head re-review closes those findings.

## Problem

The selector engine had five remaining correctness and lifecycle gaps:

- legacy or pre-dispatch action evidence could authorize a second mutation
  despite known `performed`, `unknown`, or `-25204` evidence;
- a correct WeChat bundle could be rejected when the localized app name was
  `微信` instead of `WeChat`;
- three emitted frontmost-target failure values were missing from the stable
  public failure registry;
- truncated direct contact-target queries could still click, invoke an
  Accessibility action, or press Return using an incomplete candidate set;
- the live PR body still published an obsolete approval and CI snapshot.

## Candidate Remediation

- `60138f3` restores bundle-first frontmost identity. Name matching is used
  only when no bundle was requested.
- `60138f3` declares, exports, registers, documents, and producer-tests the
  query, action, and tree frontmost-target failure values.
- `7464ad1` requires semantically coherent recovery evidence. Legacy and
  pre-dispatch paths reject known effects and native codes unless the strict
  native unsupported/no-effect contract is complete.
- `1967107` rejects limit, time-budget, and depth truncation before parsing or
  mutating across control-map, visible-row, and search-result contact paths.
- `7d870ac` proves the new public failures survive wheel build, isolated
  install, import, and registry routing.
- `45774fe` closes an adjacent fail-open path: a failed final search-result
  query now returns its structured failure instead of being treated as zero
  candidates and followed by Return.
- The tracked F6 records now state the current `REQUEST_CHANGES` decision and
  pending re-review instead of claiming obsolete approval.

## Consumer Impact

Existing semantic APIs and request schemas are unchanged. Public consumers can
now import and route these additional package-owned failure constants:

- `ACCESSIBILITY_QUERY_TARGET_APP_NOT_FRONTMOST`
- `TARGET_APP_NOT_FRONTMOST`
- `ACCESSIBILITY_TREE_TARGET_APP_NOT_FRONTMOST`

The values are members of `COMPUTER_USE_FAILURE_KINDS`. WeChat contact-target
workflows return structured query or `wechat_query_truncated` failures before
any mutation when target-selection data is failed or incomplete.

## Safety

- Exact bundle identity takes precedence over a localized display-name alias.
- Contradictory action evidence cannot authorize replay.
- Native `-25204`, `performed`, and `unknown` outcomes remain non-replayable.
- Truncation is checked before candidates are ranked or acted upon.
- A failed final target query cannot fall through to Return, draft, or send.
- Composite send regressions assert zero target action, Return, message draft,
  and submit for unsafe target-selection outcomes.
- No live WeChat mutation was used as remediation evidence.

## Verification

Latest broad local remediation verification passed:

- root repository: 128 tests;
- `app-control-protocol`: 55 tests;
- `computer-use-macos`: 158 tests, 1 sandbox socket skip;
- `wechat-desktop-tool`: 154 tests;
- compilation, release preflight, three-wheel build and isolated API smoke,
  old dependency rejection, review-result validation, and whitespace checks.

The new counterexamples execute real generated workers, all shared action
recovery entry points, all three contact-target paths, and the full
`send_message` operation sequence. GitHub CI must still pass on the pushed
exact head.

## Finding State

| Finding | State |
| --- | --- |
| `PRR-026` | Candidate fix in `7464ad1`; independent revalidation pending. |
| `PRR-037` | Candidate fix in `60138f3`; independent revalidation pending. |
| `PRR-038` | Candidate fix in `60138f3` and wheel proof in `7d870ac`; independent revalidation pending. |
| `PRR-039` | Candidate fix in `1967107`, with adjacent query-failure hardening in `45774fe`; independent revalidation pending. |
| `PRR-023` | Tracked records corrected; live PR body synchronization and independent revalidation pending. |

All previously resolved findings remain subject to regression review at the
new exact head.

## Merge Decision

The authoritative decision remains `REQUEST_CHANGES`. Keep the PR draft. Do
not mark ready, approve, or merge until exact-head CI is green, the live and
tracked F6 surfaces agree, and a new independent review grants approval.
