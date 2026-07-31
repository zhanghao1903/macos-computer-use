# PR Review — `acme/payments#482` @ `7f31a9c`

> Fictional re-review example. Repository names, commits and findings are illustrative.

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `acme/payments` |
| Pull Request | `#482` — Retry provider requests after transient failures |
| Author | `dev-example` |
| Base | `main` @ `1111111111111111111111111111111111111111` |
| Head | `feature/provider-retry` @ `7f31a9c222222222222222222222222222222222` |
| Reviewed at | `2026-07-11T08:30:00Z` |
| Reviewer | `AI PR Reviewer` |
| Report status | `CURRENT` |
| Review mode | `READ_ONLY` |
| Review kind | `RE_REVIEW` |
| Previous review | `example-pr-review-previous-result.json` @ `6e20a1b333333333333333333333333333333333`, `REQUEST_CHANGES` |
| Previous result integrity | `.agents/skills/pr-review/examples/example-pr-review-previous-result.json`, SHA-256 `f3281b3816fab9984a87b81812051c02f2091a209fd95bfbe1f91c0c1018bee5` |
| Supersedes | Previous `6e20a1b` decision |

## 2. Decision

- **Decision:** `REQUEST_CHANGES`
- **Mergeable:** `false`
- **Blocking findings:** `1` (`PRR-002`)
- **Approval renewal:** `WITHHELD`
- **Rationale:** `PRR-001` is resolved, but the remediation emits
  `idempotency_replay` without declaring it in the stable
  `PROVIDER_OUTCOMES` registry.

## 3. Executive Summary

This re-review closes the duplicate-charge finding with a payment-scoped
idempotency key. The independent forward-risk track found that the remediation
also emits a new public provider outcome that is absent from the advertised
registry. Approval renewal is withheld until `PRR-002` is resolved.

## 4. Scope and Change Map

### Reviewed scope

- previous finding `PRR-001` closure at the current head;
- the complete `6e20a1b...7f31a9c` remediation delta;
- the current base-to-head payment retry path and public failure routing.

### Excluded or unavailable scope

- Production provider logs and sandbox credentials.

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| Payment retry identity | Attempts reuse a key derived from the immutable payment ID. | Lost responses no longer create a second charge. | Low | Current-head lost-response regression passes. |
| Provider outcome contract | Client emits `idempotency_replay`. | Registry consumers receive an undeclared value. | Medium | Executable registry assertion fails. |

### Re-review reconciliation

| Previous report | Previous base/head | Previous decision | Current base/head | Delta | Old decision state |
|---|---|---|---|---|---|
| `example-pr-review-previous-result.json` | `1111111` / `6e20a1b` | `REQUEST_CHANGES` | `1111111` / `7f31a9c` | `6e20a1b...7f31a9c` | `SUPERSEDED` |

- **Delta commits reviewed:** `7f31a9c222222222222222222222222222222222`
- **Delta files reviewed:** `errors.ts`, `provider-client.ts`, `submit.ts`, and `retry.test.ts`
- **Unclassified changes:** none
- **Full base-to-head diff reconciled:** `true`

#### Finding closure ledger

| Finding | Previous status | Current status | Current-head evidence | Negative regression |
|---|---|---|---|---|
| `PRR-001` | open | resolved | One key is derived from the immutable payment ID. | Lost-response test proves all attempts reuse it. |

#### Forward-risk surfaces

| Surface | Risk triggers | Affected paths | Discriminating checks | Result |
|---|---|---|---|---|
| New provider replay outcome | public-contract, test-adequacy | client, errors, consumer, test | Real observation plus registry membership assertion | `FAIL` → `PRR-002` |

#### Approval-renewal gate

- [x] Old decision invalidated
- [x] Previous findings revalidated at current head
- [x] Forward-risk review completed
- [x] All delta changes classified and full PR diff reconciled
- [x] Decision-critical assumptions verified
- [x] Current-head validation and CI complete
- [ ] No open blocker or decision-blocking limitation
- **Independent pass:** `PASS` — a fresh-context reviewer reproduced `PRR-002`.

## 5. Findings

### PRR-002 — `[S2][Blocking][API contract]` New replay outcome is absent from the public registry

- **Location:** `src/payments/errors.ts:18-31` @ `7f31a9c222222222222222222222222222222222`
- **Confidence:** High
- **Status:** open
- **Origin:** `DELTA_INTRODUCED`
- **Observation:** `provider-client.ts` emits `idempotency_replay`, but
  `PROVIDER_OUTCOMES` does not contain the value.
- **Trigger:** A lost-response retry returns the provider's original operation
  and a caller routes the outcome through the stable registry.
- **Impact:** A registry consumer treats a legitimate package outcome as
  unknown and can select the wrong recovery path.
- **Evidence:** A real client observation returned `idempotency_replay`; the
  registry membership assertion failed.
- **Required change:** Declare the outcome and validate emitted observations
  against the registry.
- **Verification:** Registry assertion, retry tests and package CI pass.

### PRR-001 — `[S1][Resolved][Data integrity]` Lost-response retries could submit the same payment twice

- **Location:** `src/payments/submit.ts:118-138` @ `7f31a9c222222222222222222222222222222222`
- **Confidence:** High
- **Status:** resolved
- **Origin:** `BASE_DIFF`
- **Observation:** The current implementation reuses a payment-scoped key.
- **Trigger:** The provider accepts the first charge and the response is lost.
- **Impact:** The provider now returns the original operation instead of
  creating another charge.
- **Evidence:** The lost-response regression records one logical key.
- **Required change:** Completed.
- **Verification:** The original trigger returns one provider operation.

## 6. Required Actions Before Merge

- [ ] `PRR-002` — Register the new provider outcome and add executable
  contract coverage.

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Data integrity | Low | The original duplicate path is regression-tested. | Preserve the payment-scoped identity invariant. |
| API & compatibility | Medium | Registry consumers cannot classify the replay outcome. | Resolve `PRR-002` before merge. |
| Deployment & rollback | Low | No persisted migration is involved. | Revert the remediation commit if necessary. |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| `npm test -- retry.test.ts` | Node.js 22, Linux, current head | PASS | 0 | Lost-response regression closes `PRR-001`. |
| Registry membership assertion | Real provider-client fixture, current head | FAIL | 1 | `idempotency_replay` is undeclared. |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| `unit-tests` | `2026-07-11T08:20:00Z` | PASS | Passed for `7f31a9c`. |

### Checks not run

- Provider sandbox integration — no sandbox credentials; the deterministic
  public-contract failure is local.

## 9. Coverage and Limitations

- **Reviewed:** complete remediation delta, prior finding closure, affected
  callers, public registry and tests.
- **Not reviewed:** provider service implementation and production logs.
- **Missing context:** live sandbox behavior.
- **Staleness condition:** any base/head change restarts the re-review gates.

## 10. Open Questions and Assumptions

### Open questions

None that change the current request-changes decision.

### Assumptions

| Assumption | Decision-critical | Status | Evidence |
|---|---|---|---|
| One immutable payment ID represents one charge. | true | VERIFIED | Identity contract and lost-response regression. |
| Sandbox replay behavior matches production. | false | UNVERIFIED | No sandbox credentials. |

## 11. Non-blocking Recommendations

- `NOTE-001` — Emit an idempotency replay metric for rollout visibility.

## 12. Machine-readable Summary

- Result file: `example-pr-review-result.json`
- Schema: `schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.1"
review_kind: RE_REVIEW
decision: REQUEST_CHANGES
mergeable: false
head_sha: 7f31a9c222222222222222222222222222222222
blocking_findings:
  - PRR-002
validation_status: FAILED
report_status: CURRENT
```
