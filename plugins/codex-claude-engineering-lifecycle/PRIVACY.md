# Privacy

Codex-Claude Engineering Lifecycle is a local plugin and does not operate a
separate hosted service. It coordinates Codex, local Git/GitHub tools, and the
user's installed Claude Code CLI.

## Local data

For each initialized repository it stores:

- canonical repository and Git common-directory identity;
- workflow, Codex task, Claude session, feature, message, GoalRun, and
  authorization IDs;
- configured models, turn/budget/timeout limits, Goal/merge/release policies,
  role acknowledgements, and dispatch status;
- lifecycle stages, paths, commit SHAs, SHA-256 digests, bounded
  titles/summaries/findings, timestamps, and sanitized error kinds;
- validated Claude structured results and merge/release/closure proof.

The state root is:

```text
${CODEX_HOME:-~/.codex}/codex-claude-engineering-lifecycle/projects/<repository-key>/
```

It intentionally excludes credentials, authorization headers, API/OAuth
tokens, raw Claude transcripts, source-file copies, large diffs, and raw
command logs. Structured review reports may contain repository paths, concise
source evidence, and findings; treat the state root as private.

## Anthropic data boundary

Claude Code is a third-party external processing boundary. During Frontend and
Review operations, Claude may read repository files and Git state using its
normal local tools. The bridge sends the bounded transport request, role
prompt, and structured output schema to the user's configured Claude service.

Authentication and data handling are governed by the user's Claude
installation, account, organization settings, model selection, and Anthropic
terms. The plugin probes only version and authenticated/not-authenticated
status. It does not install Claude, log in, read credential files, print auth
details, or forward Anthropic/API token environment variables.

## Other external systems

Git and GitHub/PyPI actions use the user's configured tools and accounts. The
plugin does not proxy credentials. GitHub receives normal repository, PR,
review-record, merge, tag, artifact, and release operations only when the
relevant role and policy gate allows them. PyPI/TestPyPI receives only an
explicitly authorized publication.

## Retention and deletion

Uninstalling the plugin does not remove local state, Codex tasks, Claude
sessions, branches, PRs, review records, tags, releases, or packages.

To remove local workflow state, first obtain the exact `stateRoot` from both
status commands, resolve every pending/UNKNOWN operation, confirm that
retry/audit history may be lost, and delete only that exact project directory.
Archive Codex tasks separately. Claude history and external Git/package records
require their own explicit cleanup decisions.
