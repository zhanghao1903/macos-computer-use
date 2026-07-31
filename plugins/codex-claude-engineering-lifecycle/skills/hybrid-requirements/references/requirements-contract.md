# Requirements Contract

Use one ordered metadata block within the first 40 lines:

```text
- Status: Draft|Confirmed
- FeatureId: <lowercase-slug>-<12 lowercase hex>
- Branch: codex/<feature-slug>
- ConfirmedBy: <user label or empty while Draft>
- ConfirmedAt: <strict RFC3339 UTC Z or empty while Draft>
```

Each field appears exactly once. Revisions return status to Draft until the user
confirms the complete new snapshot.

The deterministic location is:

```text
codex/<feature-slug>
docs/feature/<feature-slug>/requirements.md
```

Include problem/current behavior, user/developer scenarios, goals, measurable
acceptance, non-goals, failure/recovery, public API, safety/privacy/permission,
compatibility/release impact, assumptions, open questions, and whether
frontend work is expected. Do not include the technical design or final path
classification.

`prepare-requirements` binds workflow/repository/task route, feature/title,
branch, path, commit, content digest, remote tip, confirmation, and deterministic
message ID. Deliver its JSON unchanged. An identical committed snapshot returns
the original payload/timestamp and is safe to retry.
