# Main Lifecycle

## Stage ownership

| Stage | Main action |
| --- | --- |
| `REQUIREMENTS_CONFIRMED` | Author requirements/design/implementation plan |
| `PLAN_REVIEW_PENDING` | Wait for exact Review result |
| `PLAN_CHANGES_REQUESTED` | Remediate findings and dispatch next plan cycle |
| `PLAN_APPROVED` / `DEVELOPMENT_QUEUED` | Prepare and activate initial GoalRun when slot is free |
| `DEVELOPMENT_ACTIVE` | Continue the active Goal only |
| `DEVELOPMENT_BLOCKED` | Wait for user/external recovery, then resume same blocked run |
| `DEVELOPMENT_COMPLETE` | Prepare exact-head code review |
| `CODE_CHANGES_REQUESTED` | Queue a new remediation GoalRun |
| `MERGED` | Prepare exact release proposal |
| `RELEASE_AWAITING_AUTHORIZATION` | Wait for exact user authorization |
| `RELEASE_AUTHORIZED` / `RELEASE_FAILED` | Publish or retry authorized targets |
| `RELEASED` | Validate and record closure |

## Plan snapshot

All three artifacts must exist at one commit:

- `requirements.md`;
- `design.md`;
- `implementation-plan.md`.

The helper computes individual digests and a canonical composite digest.
Review approval applies only to that commit and composite digest.

## GoalRun

The initial run is bound to the PASS plan result. A remediation run is bound to
the exact code-review REQUEST_CHANGES result and cycle. The objective must name
the feature, branch, artifacts, required implementation/tests/docs/changelog/PR,
and genuine completion condition.

Use the same `start-development` command twice:

1. with objective and authority to create PREPARED state;
2. after `create_goal`, with the returned run ID and task/thread ID to activate.

If platform Goal creation fails, leave PREPARED and retry idempotently. Never
create a second Goal for the same run ID.

## Release target examples

GitHub Release target:

```json
{
  "kind": "GITHUB_RELEASE",
  "repositoryKey": "owner/repo",
  "tag": "v1.2.3",
  "releaseName": "Version 1.2.3",
  "artifacts": [
    {"name": "artifact.zip", "sha256": "<64 lowercase hex>"}
  ]
}
```

PyPI target:

```json
{
  "kind": "PYPI",
  "repository": "PYPI",
  "projectName": "example-package",
  "version": "1.2.3",
  "artifacts": [
    {"name": "example_package-1.2.3-py3-none-any.whl", "sha256": "<digest>"}
  ]
}
```

The helper returns deterministic target IDs. The result must contain exactly
one entry per target. One failure prevents RELEASED and CLOSED.

## External proof

Use authoritative GitHub/PyPI APIs or supported connectors. Do not paste tokens,
signed temporary URLs, headers, or raw logs into state. Record canonical public
URLs, commit/tag/version, artifact names/digests, timestamps, and sanitized
errors only.
