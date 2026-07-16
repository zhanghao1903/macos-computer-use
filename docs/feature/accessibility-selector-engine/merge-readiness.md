# Accessibility Selector Engine Merge Readiness

- Updated: 2026-07-17
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Latest authoritative review:
  [`pr-review-macos-computer-use-3-59c6fb5.md`](./pr-review-macos-computer-use-3-59c6fb5.md)
  for head `59c6fb5`, published at `0a1e5cb`
- Latest implementation fix head: `3abc501`
- Current decision: `REQUEST_CHANGES`; implementation is remediated but a new
  exact-head verification and re-review are still required

## Current Remediation

The `59c6fb5` re-review opened 12 blockers. Runtime and package fixes are now
complete in two independently verified slices:

- `b9493a8` closes `PRR-028`, `PRR-029`, `PRR-031`, `PRR-032`, `PRR-034`, and
  `PRR-036`: bounded truncation decisions, executable collection profiles,
  accepted-record pagination, frontmost-only AX targeting, public query limits,
  and complete worker failure registration;
- `3abc501` closes `PRR-021`, `PRR-026`, `PRR-030`, `PRR-033`, and `PRR-035`:
  request-bound action proof, atomic WeChat selector assets, privacy-safe
  evidence/events/logging, and structured failure routing;
- `PRR-027` is addressed by correcting the historical `f19cbd9` machine result
  without changing its decision or inventing test runs. Preserved finding
  fingerprints, the two-dot delta, all changed-path risk surfaces, and
  exact-reviewed-head run binding now pass the repository validator.

The corrected historical machine result SHA-256 is
`01ed707a583c533e50c7a736d3dd235832211701db42552f3419d47c72b04653`.
The older broad checks at implementation head `65f8855` remain supporting
evidence in the report narrative; only the six tests actually run at
`f19cbd9` remain in machine-readable `reviewer_runs`.

## Safety Contract

- A selector decision cannot use truncated data, except for the narrow exact
  cached-node validation case defined by the design.
- Collection limits count accepted semantic records, rejected AX rows do not
  consume the page, and semantic lookahead determines `hasMore`.
- Query, action, and tree workers resolve only the current visible frontmost
  target application.
- Mutation fallback requires complete, type-valid, internally consistent proof
  for the exact outbound action and a definite native no-effect result.
- Normal evidence, events, and default redacted logs exclude AX nodes, paths,
  labels, values, descriptions, window titles, and raw payloads.
- A selector profile override activates only when its generic profile and
  WeChat control map both validate from the same parse.

## Verification To Date

Focused verification for `b9493a8`:

- `computer-use-macos/tests/test_selectors.py`: 72 passed;
- `computer-use-macos/tests/test_package.py`: 83 passed;
- `wechat-desktop-tool/tests/test_profiles.py`: 9 passed.

Verification for `3abc501`:

- WeChat package discovery: 149 passed;
- WeChat source and test compilation: passed;
- whitespace validation: passed.

Historical artifact verification:

- `validate_review_result.py ...pr-review-macos-computer-use-3-f19cbd9.json`:
  `VALID`;
- JSON syntax and SHA-256 checks: passed;
- no historical run was rebound to a commit where it did not execute.

No live Accessibility action or WeChat mutation was executed during this
remediation.

## Finding Ledger

| Finding | Current remediation state |
| --- | --- |
| `PRR-021` | Fixed in `3abc501`; all known proof copies are request-bound and conflicts fail closed. |
| `PRR-026` | Fixed in `3abc501`; response proof must match the outbound action. |
| `PRR-027` | Historical machine result corrected and validator-clean; final re-review pending. |
| `PRR-028`, `PRR-029`, `PRR-031` | Fixed in `b9493a8`; truncation, executable selector steps, and semantic pagination are bounded. |
| `PRR-030` | Fixed in `3abc501`; selector assets load atomically. |
| `PRR-032` | Fixed in `b9493a8`; background targets cannot receive query/action/tree work. |
| `PRR-033` | Fixed in `3abc501`; private AX content is excluded from normal observability channels. |
| `PRR-034` | Fixed in `b9493a8`; public batch limits are enforced. |
| `PRR-035` | Fixed in `3abc501`; structured causes take precedence over message text. |
| `PRR-036` | Fixed in `b9493a8`; emitted worker failures are registered and exported. |

These are implementation claims awaiting independent exact-head re-review; the
older `REQUEST_CHANGES` decision is not treated as approved merely because the
fixes exist.

## Remaining Gates

1. Commit and push the historical artifact correction.
2. Run full repository/package, compilation, preflight, and packaging checks at
   the resulting head and record exact commands and outcomes.
3. Observe GitHub Actions for that exact head.
4. Produce a new schema-valid re-review that revalidates every open finding and
   supersedes the `59c6fb5` decision.
5. Synchronize the GitHub PR body, mark the PR ready, and merge only after the
   new review grants approval.

Signed-helper proof and package publication remain separate release gates.
