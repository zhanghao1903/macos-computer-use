# F4 Implementation Notes: Codex Engineering Lifecycle Plugin

- Date: 2026-07-27
- Branch: `codex/engineering-lifecycle-plugin`
- Phase: F4 implementation
- Technical-plan authority:
  `technical-review-2026-07-27-2.md` — Pass

## Delivered structure

- Created repo-marketplace plugin `codex-engineering-lifecycle` version `0.1.0`.
- Added four role skills:
  - `engineering-workflow-init`;
  - `engineering-requirements`;
  - `engineering-main`;
  - `engineering-review`.
- Packaged the five repository engineering skills without runtime-content
  changes and applied explicit-only invocation metadata:
  - `feature-lifecycle`;
  - `product-workflow-gate`;
  - `technical-plan-write`;
  - `technical-plan-review`;
  - `pr-review`.
- Added a repo marketplace entry at `.agents/plugins/marketplace.json`.

## Runtime

`scripts/workflowctl.py` uses Python's standard library and provides:

- canonical GitHub repository and Git common-directory binding;
- locked, atomically written config/state;
- exact role/task authorization;
- deterministic cross-task message IDs and replay protection;
- committed artifact and review-record branch proof;
- plan and code review cycles;
- one global active/blocked GoalRun with ordered immutable run history;
- exact-head merge proof and local merge-policy enforcement;
- typed GitHub Release/PyPI targets and deterministic target IDs;
- partial-release retention with retry restricted to failed targets;
- all-target closure proof.

The runtime performs independent exact-key validation even without
`jsonschema`.

## Contracts

Added strict Draft 2020-12 schemas for:

1. Requirements handoff;
2. technical-plan review request;
3. technical-plan review result;
4. code-review request;
5. code-review result;
6. release authorization;
7. release result;
8. closure record.

Sixteen positive/negative fixtures exercise both Schema and runtime
validators.

## Verification performed during implementation

- Official plugin validator: Pass.
- Official quick skill validator: Pass for all nine skills.
- Full plugin test suite with temporary `jsonschema`/PyYAML:
  21 tests, Pass.
- Schema/runtime fixture parity:
  16 fixtures, zero failures.
- End-to-end disposable-Git lifecycle:
  - Init and three acknowledgements;
  - confirmed requirements;
  - plan request/Pass result;
  - Goal prepare/activate/block/resume/complete;
  - exact-head code review and merge proof;
  - GitHub Release success plus PyPI failure;
  - pre-release closure rejection;
  - failed-target-only PyPI retry;
  - successful closure.

Temporary dependency environments were isolated and did not modify project
dependencies or package APIs.

## Implementation corrections found by tests

- A blocked GoalRun continues to occupy the single global Goal slot.
- Requirements message authority is persisted for final closure traceability.
- Review reports must use the request's deterministic branch and descend from
  the immutable reviewed snapshot.
- Review-only policy cannot produce a merged result; merge method and PR URL
  must match the request and local policy.
- A partial release preserves successful targets and accepts only the exact
  previously failed targets on retry.

## Remaining phase work

F5 adds user/policy documentation, repository changelog and verification
records. F6 performs independent code review against a clean pushed snapshot.
