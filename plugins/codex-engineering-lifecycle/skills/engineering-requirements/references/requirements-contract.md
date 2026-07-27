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

The five lines form one ordered, contiguous metadata block within the first
40 lines. Each field appears exactly once in the entire document. Duplicate,
reordered, separated, or later shadow metadata is malformed and cannot carry
confirmation authority.

The helper reads the committed document and requires all confirmed fields.
Revisions after confirmation must return status to Draft until reconfirmed.
The branch and path are deterministic:

```text
codex/<feature-slug>
docs/feature/<feature-slug>/requirements.md
```

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
- exact canonical `origin` branch tip at that commit;
- confirmed user/timestamp/evidence;
- deterministic message ID.

The JSON must be delivered unchanged. Prose may explain the handoff but cannot
add, remove, or override authority.

## Retry

An identical committed snapshot yields the same message ID and is safe to
redeliver. Re-preparation returns the first stored payload, including its
original timestamp. Any changed path, commit, digest, confirmation, branch,
route, or workflow requires a new message.
