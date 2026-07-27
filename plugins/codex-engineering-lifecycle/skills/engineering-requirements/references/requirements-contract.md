# Requirements Contract

## Required document metadata

Use exact fields near the top of the requirements Markdown:

```text
- Status: Draft|Confirmed
- FeatureId: <lowercase-slug>-<12 lowercase hex>
- Branch: codex/<feature-slug>
- ConfirmedBy: <user label or empty while Draft>
- ConfirmedAt: <strict RFC3339 UTC Z or empty while Draft>
```

The helper reads the committed document and requires all confirmed fields.
Revisions after confirmation must return status to Draft until reconfirmed.

## Content

Include:

- problem and current behavior;
- desired user/developer scenarios;
- goals and measurable acceptance criteria;
- non-goals;
- failure/recovery expectations;
- public API, safety, privacy, permissions, compatibility, and release impact;
- assumptions and open questions.

Do not include technical design or an implementation plan.

## Handoff authority

`prepare-requirements` binds:

- workflow/repository and exact task route;
- feature ID, title, branch;
- document path, commit SHA, and SHA-256;
- confirmed user/timestamp/evidence;
- deterministic message ID.

The JSON must be delivered unchanged. Prose may explain the handoff but cannot
add, remove, or override authority.

## Retry

An identical committed snapshot yields the same message ID and is safe to
redeliver. Any changed path, commit, digest, confirmation, branch, route, or
workflow requires a new message.
