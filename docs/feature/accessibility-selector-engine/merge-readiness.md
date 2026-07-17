# Accessibility Selector Engine Merge Readiness

- Updated: 2026-07-17
- Branch: `codex/accessibility-selector-engine`
- Draft PR: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Base: `fed652343ec73734247955d44dc8e60293a7b373`
- Latest authoritative review:
  [`pr-review-macos-computer-use-3-e86181a.md`](./pr-review-macos-computer-use-3-e86181a.md)
- Reviewed head: `e86181a9c300cd9929d4ce61c08188a1a36f3bb9`
- Latest implementation head: `45774fe`
- Current decision: `REQUEST_CHANGES`
- Merge status: **not ready**; independent exact-head re-review is required

## Remediation Snapshot

The latest review opened five blockers. The implementation now contains the
following candidate fixes; these are implementation claims, not an approval:

| Finding | Candidate remediation | Evidence added |
| --- | --- | --- |
| `PRR-026` | `7464ad1` rejects legacy and pre-dispatch recovery when any known effect or native-code evidence contradicts a definite no-effect result. | Shared-policy and end-to-end operation-count regressions cover `performed`, `unknown`, `-25204`, malformed, and contradictory evidence. |
| `PRR-037` | `60138f3` makes an exact requested bundle match authoritative and uses localized-name matching only when no bundle was supplied. | Generated query/action worker tests cover localized aliases, name-only fallback, wrong identity, hidden/terminated apps, and missing frontmost apps. |
| `PRR-038` | `60138f3` declares, exports, and registers all three operation-specific frontmost-target failure values; `7d870ac` proves installed-wheel propagation. | Real producer-to-observation and isolated wheel/API-smoke assertions cover the public registry. |
| `PRR-039` | `1967107` rejects truncated contact-target queries before candidate parsing or mutation; `45774fe` also fails closed when the final search-result query itself fails. | Twenty-seven truncation combinations cover three target paths and zero/one/multiple candidates; composite send tests assert zero target action, Return, draft, and submit. |
| `PRR-023` | Tracked F6 records now describe the current `REQUEST_CHANGES` state and candidate fixes without reusing obsolete approval or CI claims. | The live PR body must be synchronized after the remediation commits are pushed. |

## Safety Contract

- A correct requested bundle is the target identity; localized app names are
  aliases and are only authoritative when no bundle was requested.
- Any emitted package-owned failure is declared, exported, documented, and
  routable through `COMPUTER_USE_FAILURE_KINDS`.
- Mutation recovery is allowed only for a complete native definite-no-effect
  pair or a proven pre-dispatch result with no attempted, effect, or native
  error contradiction.
- A truncated or failed target-selection query cannot rank a contact, click,
  execute an Accessibility action, press Return, draft, or submit a message.
- A failed target-selection query is final for that workflow; it cannot be
  reinterpreted as an empty candidate set.

## Local Verification

The latest broad local implementation verification passed:

- root repository: 128 tests;
- `app-control-protocol`: 55 tests;
- `computer-use-macos`: 158 tests, 1 sandbox socket skip;
- `wechat-desktop-tool`: 154 tests after the final search-query regression;
- compilation, release preflight, all three wheel builds, isolated
  install/import/API smoke, old dependency rejection, review-result
  validation, and whitespace checks.

These counts are local remediation evidence. They do not replace exact-head
GitHub CI or an independent review. No live Accessibility action, contact
switch, message read, draft, or WeChat send was executed.

## Remaining Gates

1. Push every remediation commit to `codex/accessibility-selector-engine`.
2. Run and observe GitHub CI for the resulting exact remote head.
3. Synchronize the live PR body with
   [`pr-description.md`](./pr-description.md) while keeping the PR draft and
   the decision `REQUEST_CHANGES`.
4. Obtain an independent, schema-valid exact-head re-review that explicitly
   revalidates `PRR-023`, `PRR-026`, `PRR-037`, `PRR-038`, and `PRR-039`.
5. Mark ready or merge only if that replacement review grants approval.

Signed-helper proof, notarization, TestPyPI/PyPI publication, and trusted
publisher evidence remain separate release gates.
