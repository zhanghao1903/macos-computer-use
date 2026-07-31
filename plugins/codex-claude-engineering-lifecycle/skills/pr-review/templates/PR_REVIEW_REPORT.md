# PR Review — `<owner>/<repo>#<pr-number>` @ `<short-head-sha>`

## 1. Review Metadata

| Field | Value |
|---|---|
| Repository | `<owner>/<repo>` |
| Pull Request | `#<number>` — `<title>` |
| Author | `<author>` |
| Base | `<branch>` @ `<full-base-sha>` |
| Head | `<branch>` @ `<full-head-sha>` |
| Reviewed at | `<ISO-8601 timestamp>` |
| Reviewer | `<AI/reviewer identity and version, when available>` |
| Report status | `CURRENT \| STALE` |
| Review mode | `READ_ONLY \| PUBLISHED` |
| Review kind | `INITIAL \| RE_REVIEW` |
| Previous review | `<report/ref, previous base/head and decision; N/A for INITIAL>` |
| Previous result integrity | `<repo-relative JSON path and SHA-256; N/A for INITIAL>` |
| Supersedes | `<previous report/ref; N/A for INITIAL>` |

## 2. Decision

- **Decision:** `APPROVE | REQUEST_CHANGES | COMMENT | INCOMPLETE`
- **Mergeable:** `true | false | unknown`
- **Blocking findings:** `<count>` (`<IDs or none>`)
- **Approval renewal:** `<PASS \| FAIL \| NOT_APPLICABLE>`
- **Rationale:** `<1–3 sentences connecting the decision to findings, evidence, and limitations>`

## 3. Executive Summary

`<2–5 sentences describing the intent, actual behavior change, review result, principal risks, and immediate next action.>`

## 4. Scope and Change Map

### Reviewed scope

- `<paths, modules, call paths, migrations, tests, configuration>`

### Excluded or unavailable scope

- `<generated files, inaccessible dependencies, truncated diff, unavailable environment, none>`

### Change map

| Area | Main change | External behavior | Risk | Validation |
|---|---|---|---|---|
| `<area>` | `<change>` | `<behavior>` | `High/Medium/Low` | `<method/result>` |

### Re-review reconciliation

`<Required for RE_REVIEW; write "Not applicable — initial review" otherwise.>`

| Previous report | Previous base/head | Previous decision | Current base/head | Delta | Old decision state |
|---|---|---|---|---|---|
| `<ref>` | `<base/head>` | `<decision>` | `<base/head>` | `<previous-head..current-head>` | `SUPERSEDED` |

- **Delta commits reviewed:** `<full SHAs or none>`
- **Delta files reviewed:** `<paths or none>`
- **Unclassified changes:** `<none or list; any item prohibits APPROVE>`
- **Full base-to-head diff reconciled:** `true | false`

#### Finding closure ledger

| Finding | Previous status | Current status | Current-head evidence | Negative regression |
|---|---|---|---|---|
| `<PRR-ID>` | `<status>` | `<status>` | `<evidence>` | `<check/result>` |

#### Forward-risk surfaces

| Surface | Risk triggers | Affected paths | Discriminating checks | Result |
|---|---|---|---|---|
| `<new/widened contract or behavior>` | `<public-contract/trust-boundary/...>` | `<paths>` | `<checks>` | `PASS/FAIL/PARTIAL` |

#### Approval-renewal gate

- [ ] Old decision invalidated
- [ ] Previous findings revalidated at current head
- [ ] Forward-risk review completed
- [ ] All delta changes classified and full PR diff reconciled
- [ ] Decision-critical assumptions verified
- [ ] Current-head validation and CI complete
- [ ] No open blocker or decision-blocking limitation
- **Independent pass:** `<PASS/FAIL/NOT_AVAILABLE/NOT_REQUIRED — reviewer and summary>`

## 5. Findings

> Sort by blocking status, severity, then path/line. Preserve IDs across re-reviews.

### PRR-001 — `[S1][Blocking][<category>] <specific defect and consequence>`

- **Location:** `<path>:<line-or-symbol>` @ `<full-head-sha>`
- **Confidence:** `High | Medium`
- **Status:** `open | resolved | accepted-risk | false-positive`
- **Observation:** `<what the implementation does and which invariant/contract it violates>`
- **Trigger:** `<minimal realistic preconditions and execution path>`
- **Impact:** `<user, data, security, reliability, performance, compatibility, or operational consequence>`
- **Evidence:**
  - `<code path, test, log, specification, or reproduction>`
- **Required change:** `<outcome or constraint that must be satisfied>`
- **Verification:** `<specific test or check with a pass/fail condition>`

<!-- Repeat for each finding. If none, write:
No blocking findings identified for the reviewed snapshot.
-->

## 6. Required Actions Before Merge

- [ ] `<PRR-001>` — `<required outcome>`
- [ ] `<PRR-00N>` — `<required outcome>`

`<Write "None" when there are no blocking actions.>`

## 7. Risk Assessment

| Category | Level | Residual risk | Mitigation / owner |
|---|---|---|---|
| Security & privacy | `High/Medium/Low/None/Unknown` | `<risk>` | `<mitigation>` |
| Data integrity | `High/Medium/Low/None/Unknown` | `<risk>` | `<mitigation>` |
| Reliability & concurrency | `High/Medium/Low/None/Unknown` | `<risk>` | `<mitigation>` |
| Performance & scalability | `High/Medium/Low/None/Unknown` | `<risk>` | `<mitigation>` |
| API & compatibility | `High/Medium/Low/None/Unknown` | `<risk>` | `<mitigation>` |
| Deployment & rollback | `High/Medium/Low/None/Unknown` | `<risk>` | `<mitigation>` |

## 8. Validation Evidence

### Reviewer-executed checks

| Command / check | Environment | Result | Exit code | Evidence / notes |
|---|---|---|---:|---|
| `<command>` | `<runtime, OS, relevant config, head SHA>` | `PASS/FAIL/ERROR` | `<code>` | `<summary or artifact ref>` |

### CI / platform checks observed

| Check | Observed at | Status | Evidence / notes |
|---|---|---|---|
| `<check name>` | `<ISO-8601 timestamp>` | `PASS/FAIL/PENDING/UNKNOWN` | `<summary>` |

### Checks not run

- `<check>` — `<reason and resulting limitation>`

## 9. Coverage and Limitations

- **Reviewed:** `<files, modules, paths, behaviors>`
- **Not reviewed:** `<files, modules, paths, behaviors>`
- **Missing context:** `<requirements, environment, logs, dependency source, none>`
- **Staleness condition:** `<what change would require re-review>`

## 10. Open Questions and Assumptions

### Open questions

1. `<question that can materially change the decision or implementation>`

### Assumptions

| Assumption | Decision-critical | Status | Evidence |
|---|---|---|---|
| `<explicit assumption>` | `true/false` | `VERIFIED/UNVERIFIED/NOT_VERIFIABLE` | `<evidence or none>` |

## 11. Non-blocking Recommendations

- `<PRR-optional-ID or NOTE-001>` — `<recommendation and value>`

`<Keep these separate from merge requirements. Write "None" when empty.>`

## 12. Machine-readable Summary

- Result file: `pr-review-result.json`
- Schema: `schemas/pr-review-result.schema.json`

```yaml
schema_version: "1.1"
review_kind: RE_REVIEW
decision: REQUEST_CHANGES
mergeable: false
head_sha: <full-head-sha>
blocking_findings:
  - PRR-001
validation_status: PARTIAL
report_status: CURRENT
```
