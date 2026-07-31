# Claude Transport

## Rules

- Address exact session UUIDs only. Never use `--continue` or latest-session
  selection.
- Persist each request to a private temporary JSON file and call
  `claudectl.py`; do not build shell commands from request text.
- One unresolved RUNNING/UNKNOWN message blocks the same Claude role.
- Treat only saved, schema-valid, digest-bound structured output as a result.
- Do not copy raw CLI output, prompts, transcripts, credentials, or command
  logs into feature docs or state.

## Dispatch

```text
claudectl.py dispatch
  --repo <root>
  --kind <frontend|plan-review|code-review>
  --request-file <private-json>
```

An identical COMPLETED retry returns the saved result without another Claude
call. A reused message ID with another payload/schema is rejected.

## UNKNOWN recovery

Timeout, interruption, non-zero exit, malformed JSON, wrong session, missing
structured output, schema error, or binding mismatch is UNKNOWN because Claude
may already have acted.

Inspect:

```text
claudectl.py status --repo <root>
git status --short --branch
```

Then recover only the same request:

```text
claudectl.py recover
  --repo <root>
  --kind <same-kind>
  --request-file <identical-json>
```

If a crashed Codex process left the ledger RUNNING, do not resume immediately.
Prove the Claude process is no longer active, then run:

```text
claudectl.py mark-orphaned
  --repo <root>
  --message-id <exact-id>
  --confirm-process-stopped
```

Only then recover the identical request. Marking a live process orphaned could
resume one Claude session concurrently and is prohibited.

The recovery prompt tells the same session not to repeat completed mutation.
If still inconclusive, remain blocked. Do not start another role message or
silently perform the work in Main.

## Review persistence

Claude returns report Markdown and compact structured JSON. Main writes those
fields unchanged plus transport digests to the deterministic review-record
worktree. It may add headings/serialization only when values are not changed.
The resulting commit/path/digests feed the existing workflow result command.

## Frontend proof

Use the stored result path returned by `dispatch`, then run
`verify-frontend`. A valid proof checks clean state, exact branch/head,
ancestry, remote presence of the start SHA, actual commit/path sets, and every
allowed prefix. Failure is blocking and never triggers automatic reset.
