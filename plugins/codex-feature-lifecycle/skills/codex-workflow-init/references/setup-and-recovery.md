# Setup and Recovery

## Install from this repository

In Codex Desktop, add the repository as a marketplace and install
`codex-feature-lifecycle`. From the CLI, the equivalent flow is:

```bash
codex plugin marketplace add https://github.com/zhanghao1903/macos-computer-use.git
codex plugin add codex-feature-lifecycle@macos-computer-use
```

Restart Codex if the host does not discover newly installed skills in the
current process. Then explicitly invoke `$codex-workflow-init` from a trusted
GitHub repository checkout.

## Initialize

Init checks Codex task-management and GitHub capabilities before creating
anything. It creates or binds exactly two project-scoped tasks, waits for both
role readiness markers, and only then stores a repository-scoped config.

Automatic merging is off by default. Enabling it is a separate durable grant
limited to an approved exact head with green required checks and no blocker.
It never permits admin bypass, automatic release publication, or merging a
different head.

## Local data

The plugin stores routing, merge policy, and dispatch state outside the git
repository:

```text
${CODEX_HOME:-~/.codex}/feature-lifecycle/projects/<repo-key>/config.json
${CODEX_HOME:-~/.codex}/feature-lifecycle/projects/<repo-key>/state.json
```

It does not store credentials, prompts, task transcripts, source code, diffs,
or findings. The directory is private to the current user where the platform
supports POSIX permissions.

Use `workflowctl.py locate --repo-root <root>` to find the paths without
printing credentials. Use `workflowctl.py validate --repo-root <root>` to
verify schema, repository binding, and state consistency.

## Update

Update the marketplace checkout or reinstall the newer plugin version through
Codex. Re-run `$codex-workflow-init`; a healthy existing workflow is reused
without creating tasks or rewriting config. Schema migrations must be explicit
in a future release—never manually change `schemaVersion`.

## Recover a partial initialization

- If one newly created task never becomes ready, Init must not write config.
- Init may archive only tasks it created in that failed attempt and only after
  resolving their exact IDs.
- If config exists but a route is stale, invoke Init explicitly in repair mode.
  It must prove a replacement pair before using `--replace`.
- If delivery fails after a ReviewRequest is prepared, retry the same dispatch;
  the stable dispatch ID prevents a duplicate review cycle.
- Never select a task by title alone when more than one candidate matches.

## Uninstall

Uninstall the plugin through Codex. Uninstalling does not delete user-owned
tasks or repository-scoped local state. Archive tasks explicitly if no longer
needed. Delete the exact `<repo-key>` state directory only after confirming it
belongs to the intended repository; this is irreversible and removes retry
history and durable merge policy.
