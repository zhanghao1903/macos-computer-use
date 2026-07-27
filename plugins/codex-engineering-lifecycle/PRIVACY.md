# Privacy

Codex Engineering Lifecycle runs locally in Codex and does not operate a
separate hosted service.

## Local data

For each initialized repository it stores:

- canonical repository and Git common-directory identity;
- workflow, task, feature, message, GoalRun, and authorization IDs;
- role acknowledgements and configured Goal/merge/release policies;
- lifecycle stages, queue state, paths, commit SHAs, SHA-256 digests, bounded
  titles/summaries, timestamps, and sanitized errors;
- merge, release-target, and closure proof metadata.

The state root is:

```text
${CODEX_HOME:-~/.codex}/engineering-lifecycle/projects/<repository-key>/
```

The workflow intentionally excludes credentials, authorization headers,
tokens, raw prompts, transcripts, source contents, diffs, finding text, and raw
command logs.

## External systems

Git operations and GitHub/PyPI actions use the user's configured tools and
accounts. The plugin does not proxy those credentials. GitHub receives normal
repository, PR, review-record, merge, tag, artifact, and release operations
only when the relevant role and policy gate allows them. PyPI/TestPyPI receives
only an explicitly authorized publication.

## Retention and deletion

Uninstalling the plugin does not remove state or user-owned tasks and does not
delete branches, PRs, review records, tags, releases, or packages.

To remove local workflow state, first obtain the exact `stateRoot` from
`workflowctl.py status`, confirm that retry/policy/audit history may be lost,
and delete only that exact project directory. Archive Codex tasks separately.
External Git and package records require their own explicit cleanup decisions.
