# Hybrid Main Lifecycle

## Stage ownership

| Stage | Main action |
| --- | --- |
| `REQUIREMENTS_CONFIRMED` | Write complete plan and frontend path ownership |
| `PLAN_REVIEW_PENDING` | Wait for exact Claude Review result |
| `PLAN_CHANGES_REQUESTED` | Remediate plan findings and dispatch next cycle |
| `PLAN_APPROVED` | Prepare/activate the initial GoalRun |
| `DEVELOPMENT_ACTIVE` | Serialize Main work, Claude Frontend, and integration |
| `DEVELOPMENT_BLOCKED` | Recover exact active operation; do not start another |
| `DEVELOPMENT_COMPLETE` | Prepare exact PR review |
| `CODE_CHANGES_REQUESTED` | Route findings by frontend/non-frontend owner |
| `MERGE_READY` | Wait for external merge or perform policy-authorized mechanics |
| `MERGED` | Prepare exact release proposal |
| `RELEASE_*` | Preserve existing authorization/proof/retry gates |
| `CLOSED` | Report traceability to Requirements |

## Plan authority

Requirements, design, and implementation plan must exist at one commit and
produce the existing canonical composite digest. The plan must also contain:

- frontend-owned path prefixes;
- frontend acceptance criteria and verification commands;
- non-frontend ownership;
- integration ordering;
- recovery for an invalid/unknown frontend result.

Claude PASS applies only to the exact plan commit/digest.

## One GoalRun, two executors

The platform Goal belongs to Main. Claude Frontend is a serialized sub-operation
inside it, not another Goal. Recommended order:

1. Main implements/commits/pushes non-frontend work.
2. Main prepares exact FrontendWorkRequest from a clean pushed head.
3. Claude Frontend commits/pushes only authorized paths.
4. Main validates Git proof and runs whole-repository integration.
5. Main completes the Goal only after every criterion and proof is complete.

Never run Main mutation and Claude Frontend concurrently in one worktree.

## Finding ownership

- Findings whose affected paths are wholly inside accepted frontend prefixes:
  Claude Frontend remediation.
- Other findings: Main `CODE_REMEDIATION` GoalRun.
- Mixed findings: Main first, then Claude Frontend, then integration.

Every remediation creates a new head and exact Claude Review cycle. Do not
preserve or replay stale approval.

## Merge mechanics

Claude’s APPROVE is review authority, not GitHub mutation permission. Main may
merge only under configured `merge-on-approve`, after independently proving:

- same canonical PR and reviewed head;
- PR not draft;
- required checks green;
- repository reports mergeable;
- configured method;
- no bypass.

With `review-only`, return READY and wait for a separately authorized owner.

## Release

Use the copied lifecycle’s exact GitHub Release/PyPI proposal, per-release user
authorization, artifact digest, partial retry, replay, and closure rules.
Claude receives neither credentials nor release authority.
