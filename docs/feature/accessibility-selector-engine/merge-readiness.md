# Accessibility Selector Engine Merge Readiness

- Updated: 2026-07-17
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Latest authoritative review:
  [`pr-review-macos-computer-use-3-eb543ec.md`](./pr-review-macos-computer-use-3-eb543ec.md)
- Reviewed head: `eb543ec9eb3800de104dadeb5d2fbb1382d14416`
- Latest runtime implementation head: `b01aa01312a8c64f3476c966ee5659eaed9eed6f`
- Current decision: `REQUEST_CHANGES`
- Merge status: **not ready**; independent exact-head re-review is required

## Remediation Snapshot

The latest review contains five blockers. The following changes are candidate
fixes and do not supersede the independent review decision:

| Finding | Candidate remediation | Deterministic evidence |
| --- | --- | --- |
| `PRR-039` | `63a45cf` validates query envelopes centrally; `b01aa01` makes failed, truncated, malformed, or mixed-root WeChat target evidence final before another root or strategy. | Contract matrices cover all three contact-target paths, the first incomplete root, visible-query failure, and composite send side effects. |
| `PRR-040` | `bb8506d` distinguishes an absent `any_of` key from an explicitly empty or falsey value and rejects the latter. | JSON and TOML-compatible profile tests cover missing, empty, falsey, malformed, and valid matcher forms. |
| `PRR-041` | `bb8506d` rejects `NaN` and infinity in confidence, weight, relation-distance, and frame values during parse and validation. | Non-finite matrices cover direct construction and parsed profile inputs. |
| `PRR-042` | `63a45cf` rejects unsupported schemas and malformed or contradictory status, availability, failure, node, diagnostics, retryability, and truncation fields. | Canonical, generated, narrow legacy, malformed, and contradictory response envelopes are tested; invalid data creates no candidates or cache entries. |
| `PRR-043` | `b01aa01` checks candidate cardinality before frame filtering, requires one finite in-window frame, and removes Return fallback for empty or unverified sets. | Seven search-result cases prove zero target action, Return, draft, and submit for empty, malformed, offscreen, or ambiguous inputs. |

The latest review artifact and its remediation design and plan are committed in
`057154a`, `27fe73f`, and `4601ecf` respectively.

## Safety Contract

- A query result is actionable only when its envelope is structurally valid,
  semantically coherent, complete, and non-truncated.
- A multi-root or multi-strategy target lookup stops at the first unsafe
  decision result; later roots cannot hide earlier incomplete evidence.
- Search-result uniqueness is evaluated before visibility filtering. Exactly
  one candidate must also have a finite, positive, in-window frame.
- Empty, ambiguous, malformed, offscreen, failed, or truncated candidate sets
  cannot click, execute an Accessibility action, press Return, draft, or
  submit a message.
- Explicit empty selector matchers and non-finite profile numbers are invalid
  configuration, not permissive defaults.

## Local And Remote Verification

The complete verification set was rerun on lifecycle evidence head
`a186f2b64b57484144bf814da097c4da88edbba1` and passed:

- root repository: 128 tests, including wheel and release integration checks;
- `app-control-protocol`: 55 tests;
- `computer-use-macos`: 168 tests, 1 sandbox socket skip;
- `wechat-desktop-tool`: 159 tests;
- compilation, release preflight, all three wheel builds, isolated
  install/import/API smoke, old dependency rejection, latest review-result
  validation, and whitespace checks.
- GitHub Actions `CI / test` passed on the same exact head in 2 minutes 22
  seconds: https://github.com/zhanghao1903/macos-computer-use/actions/runs/29595247922/job/87933943045.
- The live PR body was synchronized to the current review and candidate
  findings while the PR remained draft.

These results are implementation-owner evidence. No live Accessibility action,
contact switch, message read, draft, or WeChat send was executed.

## Remaining Gates

1. Keep GitHub CI green on every later lifecycle-only commit; the live PR
   check is authoritative for the current remote head.
2. Obtain an independent, schema-valid exact-head re-review that explicitly
   revalidates `PRR-039` through `PRR-043`.
3. Address any newly opened blocker through another documented remediation
   cycle.
4. Mark ready or merge only if the replacement review grants approval.

Signed-helper proof, notarization, TestPyPI/PyPI publication, and trusted
publisher evidence remain separate release gates.
