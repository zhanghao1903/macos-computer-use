# Code Review: Codex Engineering Lifecycle Plugin

## Review Metadata

- Repository: `zhanghao1903/macos-computer-use`
- Target: `origin/main...origin/codex/engineering-lifecycle-plugin`
- Title: Add the Codex Engineering Lifecycle plugin
- Author: zhanghao1903 / Codex implementation task
- Base: `main`
- Base SHA: `1935b33e29586757ec41cc1df4b99aa1ae074a8f`
- Head: `codex/engineering-lifecycle-plugin`
- Head SHA: `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- Reviewed at: 2026-07-27 (Asia/Shanghai)
- Reviewer: Codex, `$pr-review`
- Report status: CURRENT for the recorded head
- Review type: INITIAL
- Previous report: none

## Decision

- Decision: `REQUEST_CHANGES`
- Mergeable: false
- Blocking findings: 6 (`PRR-001` through `PRR-006`)
- Rationale: the plugin structure, role separation, tests, and most lifecycle
  guards are strong, but the recommended review-only policy cannot reach
  release, several retry/acceptance operations are not atomic or idempotent,
  re-review authority can be omitted, durable state validation is incomplete,
  and external release proof is not bound to the authorized repository/project.

## Executive Summary

The change adds a substantial three-task workflow, deterministic state helper,
strict routed contracts, packaged engineering skills, and strong disposable-Git
tests. Review concentrated on authority transitions, retry/replay behavior,
Goal serialization, review records, merge policy, and release/closure proof.
Six correctness/reliability gaps can violate the approved design or stop the
default workflow, so this snapshot must not merge. After remediation, all six
findings require current-head tests and a full re-review.

## Scope and Change Map

| Area | Change | External behavior | Risk | Review/validation |
| --- | --- | --- | --- | --- |
| Init and state | Repository/task/policy binding, atomic files | Three durable tasks and local authority | High | Code path and state invariants |
| Routed contracts | Five deterministic message types | Cross-task authority/retry | High | Runtime/Schema parity and counterexamples |
| Plan/code review | Immutable report branches, results | Independent approval and merge | High | Stage/result path tracing |
| GoalRun | One active/blocked run | Serialized implementation/remediation | High | Integration test and state tracing |
| Release/closure | Typed targets and cumulative proof | External publication and closure | High | Authorization/result mismatch analysis |
| Skills/docs | Nine skills and GitHub install docs | User workflow and policy | Medium | Official validators and parity tests |

Reviewed all changed paths at the subsystem level, with line-level focus on
`workflowctl.py`, role skill contracts, contract schemas, tests, and user
guidance. Copied `pr-review` examples/schema/validator were checked through
source parity and their packaged upstream tests rather than re-reviewed
line-by-line as newly authored logic. SVG artwork and MIT license were treated
as low-risk assets.

## Findings

### PRR-001 — [S1][Blocking][Correctness] Review-only policy cannot record a later authorized merge

- **Location:** `plugins/codex-engineering-lifecycle/scripts/workflowctl.py:1787,1854-1857` @ `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- **Confidence:** High
- **Observation:** `prepare-code-result` rejects every `MERGED` result when the
  request policy is `review-only`, and `apply-code-result` independently rejects
  every merged result when local policy is review-only. The first approved
  result moves the feature only to `MERGE_READY`; no other command can record an
  externally/user-authorized merge.
- **Trigger:** Init uses the documented recommended `review-only` policy, Review
  returns `APPROVE/READY`, and an authorized human or separate actor merges the
  exact approved head.
- **Impact:** The feature remains permanently at `MERGE_READY`; release
  authorization, publication, and closure are unreachable under the default
  policy.
- **Evidence:** Command inventory contains no `record-merge` transition, and
  both result preparation and application reject the only existing `MERGED`
  representation.
- **Required change:** Add a fail-closed path that records authoritative merge
  proof after a prior exact-head `APPROVE/READY` under review-only without
  granting Review automatic merge authority. Preserve the existing
  merge-on-approve path.
- **Verification:** Exercise both policies: direct auto-merge proof for
  merge-on-approve; READY followed by observed external MERGED proof for
  review-only; reject direct review-only MERGED and wrong request/head/method.
- **Status:** open

### PRR-002 — [S2][Blocking][Data Integrity] Failed acceptance can persist an accepted stale or mismatched request

- **Location:** `plugins/codex-engineering-lifecycle/scripts/workflowctl.py:1377-1428` @ `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- **Confidence:** High
- **Observation:** `accept_request` marks and saves a dispatch as `accepted`
  before `accept-requirements`, `accept-plan-review`, or `accept-code-review`
  checks the feature snapshot/current pending transition. A later check can
  raise after the acceptance mutation has already committed.
- **Trigger:** A validly signed prepared request is delivered after a newer
  cycle became pending, or its durable feature snapshot no longer satisfies the
  role-specific gate.
- **Impact:** The command reports failure but durable audit state says accepted;
  Review can then prepare a result for a request the role command rejected,
  producing misleading delivery/review evidence and non-atomic state.
- **Evidence:** Acceptance is saved inside `accept_request`; all role-specific
  `feature_for` and pending/stage checks occur after it returns.
- **Required change:** Perform role-specific snapshot/stage validation and any
  requirements transition in the same lock and atomic save as the acceptance
  status. A failed command must leave state unchanged.
- **Verification:** Snapshot state before stale/mismatched acceptance, assert
  exit failure and byte-identical state afterward; retain idempotent duplicate
  acceptance after legitimate lifecycle advancement.
- **Status:** open

### PRR-003 — [S2][Blocking][Reliability] Deterministic message retry conflicts solely because `createdAt` changed

- **Location:** `plugins/codex-engineering-lifecycle/scripts/workflowctl.py:1126-1138` @ `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- **Confidence:** High
- **Observation:** `messageId` intentionally excludes `createdAt`, but
  `record_message` compares a full-payload digest that includes `createdAt`.
  Re-preparing unchanged authority later yields the same ID and a different
  payload digest, so it is rejected as `replay_conflict`.
- **Trigger:** A sender loses its temporary payload or retries preparation one
  second later after delivery failure.
- **Impact:** Documented deterministic retry cannot recover without reading raw
  internals or preserving an out-of-band file; requirements and review-result
  delivery can stall.
- **Evidence:** `message_authority` excludes both `messageId` and `createdAt`;
  `record_message` compares `digest(payload)`.
- **Required change:** Treat matching canonical authority as an idempotent
  duplicate and return the originally stored payload/timestamp. Continue to
  reject any same-ID authority mismatch.
- **Verification:** Freeze time across two values, prepare identical authority
  twice, assert same ID and exact original payload; mutate one authority field
  and assert a distinct ID or conflict.
- **Status:** open

### PRR-004 — [S2][Blocking][Reliability] Successful release-result replay is rejected

- **Location:** `plugins/codex-engineering-lifecycle/scripts/workflowctl.py:2097-2104` @ `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- **Confidence:** High
- **Observation:** After all targets publish, the stage becomes `RELEASED`.
  `record-release-result` accepts only `RELEASE_AUTHORIZED` or
  `RELEASE_FAILED`, so retrying the exact successful submission fails instead
  of returning the durable result as a duplicate.
- **Trigger:** The state save succeeds but the caller loses the command response
  and retries.
- **Impact:** The caller receives a false failure after a successful
  publication, violating the helper's stated idempotent mutation contract and
  making recovery ambiguous at the most sensitive external boundary.
- **Evidence:** Stage gate precedes duplicate comparison and excludes
  `RELEASED`; partial retry input can also be a subset of the cumulative stored
  result.
- **Required change:** In `RELEASED`, accept any replay whose normalized
  submitted target proofs exactly match the corresponding durable successful
  targets and return the cumulative stored result with `duplicate: true`.
- **Verification:** Replay both a full all-success result and the final
  failed-target-only retry; reject mismatched proof, target, digest, or URL.
- **Status:** open

### PRR-005 — [S2][Blocking][Review Integrity] Re-review requests may omit or misbind the previous result

- **Location:** `plugins/codex-engineering-lifecycle/scripts/workflowctl.py:1455-1456,1737-1738` @ `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- **Confidence:** High
- **Observation:** `previousResultMessageId` is always optional and, when
  supplied, is only format-checked. Plan/code cycles after a failed/stale result
  can omit it or reference an unrelated digest.
- **Trigger:** Main prepares cycle 2+ without the prior result ID or supplies an
  older/unrelated result.
- **Impact:** Review loses authoritative prior findings and closure context,
  undermining mandatory re-review gates and allowing an incomplete review
  record even though state knows the exact previous result.
- **Evidence:** Both preparation functions conditionally copy the CLI argument;
  neither compares it to `feature.planResultMessageId` or
  `feature.codeResultMessageId`.
- **Required change:** Require the exact latest result ID for every re-review
  cycle/stage and reject a previous ID on the initial cycle. Document and test
  the rule.
- **Verification:** Positive cycle-2 plan/code requests with exact previous
  IDs; negative missing, wrong, initial-cycle, and stale-ID cases.
- **Status:** open

### PRR-006 — [S1][Blocking][Release Safety] Publication proof URLs are not bound to the authorized repository or project

- **Location:** `plugins/codex-engineering-lifecycle/scripts/workflowctl.py:2032-2090` @ `a1dd2b865e8ac407cad29d82706ff5acb12f13ea`
- **Confidence:** High
- **Observation:** A published GitHub target requires only a `github.com` URL,
  while PyPI accepts any credential-free HTTPS `projectUrl`; artifact URLs also
  accept any HTTPS host. Target identity and artifact digest comparisons do not
  prove those URLs refer to the authorized repository/project/tag/version.
- **Trigger:** A malformed, stale, or accidentally copied result uses a release
  URL from another GitHub repository/PyPI project while retaining the expected
  IDs and digests.
- **Impact:** The workflow can record `RELEASED` and close the feature without
  authoritative public proof at the authorized destination.
- **Evidence:** `require_https_url` validates only scheme/host (GitHub) or
  scheme (PyPI), and `normalize_target_result` never compares URL paths to
  `repositoryKey`, `tag`, `projectName`, `version`, or artifact name.
- **Required change:** Canonically bind GitHub release/artifact URLs to the
  authorized repository and tag; bind PyPI/TestPyPI project and artifact hosts,
  normalized project name, version, and artifact filename. Reject query,
  fragment, credential, port, or cross-target proof.
- **Verification:** Accept canonical encoded paths; reject cross-repository,
  cross-project, wrong-version/tag, wrong artifact host/name, query, fragment,
  credential, and port counterexamples.
- **Status:** open

## Required Actions

1. Fix and test `PRR-001` through `PRR-006`.
2. Re-run official plugin and nine-skill validators.
3. Re-run 24+ full tests, strict 16-fixture contract validation, repository
   release preflight, diff/secret/generated-artifact checks.
4. Perform a full current-head re-review, including forward-risk review of all
   remediation changes.

## Risk Assessment

- Security/privacy: no credential storage or obvious command injection found;
  local Git operations use argument arrays. Release proof binding remains a
  blocking safety issue.
- Data integrity: atomic file replacement and locking are sound, but acceptance
  is not atomic with role transition validation.
- Reliability: Goal blocked-slot behavior and partial release retry are good;
  deterministic message and successful release replays are incomplete.
- Performance: bounded local JSON/Git operations; no material hot-path concern.
- Compatibility: no package API/dependency changes. Plugin schema v1 has no
  downgrade path by design.
- Operations: review-record branches and state retention are documented.

## Validation Evidence

- `uv run --isolated --with pyyaml --with jsonschema python -m unittest discover -s plugins/codex-engineering-lifecycle/tests -p 'test_*.py' -v`
  - Exit 0 at reviewed head before counterexample additions.
  - 24 tests passed.
- `uv run --isolated --with jsonschema python plugins/codex-engineering-lifecycle/scripts/validate_contracts.py --require-jsonschema`
  - Exit 0.
  - 16 fixtures, zero failures, Schema/runtime parity.
- Official plugin validator
  - Exit 0.
- Official quick validator for all nine skills
  - Exit 0 for each skill.
- `python3 scripts/release_preflight.py`
  - Exit 0; expected sandbox/external-smoke warnings only.
- `git diff --check`
  - Exit 0.
- Static path tracing and counterexamples above were not yet encoded as tests at
  this reviewed head.

## Coverage and Limitations

- No GitHub PR existed at review time; target is the pushed branch range.
- Live GitHub required-check, mergeability, and release API behavior were not
  exercised.
- Real Codex task creation/pinning/messaging and Goal tools were not invoked;
  disposable integration tests validate the helper contract only.
- No production GitHub Release or PyPI publication was attempted.

## Open Questions and Assumptions

- Assumption verified: repository `origin` is canonical
  `https://github.com/zhanghao1903/macos-computer-use.git`.
- Assumption verified from requirements/design: review-only is a supported and
  recommended Init choice, not a documentation-only mode.
- No decision-critical open question remains; the findings are statically
  reproducible.

## Non-blocking Recommendations

- After the blocking fixes, consider splitting the 2,400-line runtime into
  internal standard-library modules in a later version; preserve the CLI and
  avoid expanding this remediation.

## Machine-readable Summary

```json
{
  "schemaVersion": "review-summary.v1",
  "baseSha": "1935b33e29586757ec41cc1df4b99aa1ae074a8f",
  "headSha": "a1dd2b865e8ac407cad29d82706ff5acb12f13ea",
  "decision": "REQUEST_CHANGES",
  "mergeable": false,
  "blockingFindingIds": [
    "PRR-001",
    "PRR-002",
    "PRR-003",
    "PRR-004",
    "PRR-005",
    "PRR-006"
  ],
  "reportStatus": "CURRENT"
}
```
