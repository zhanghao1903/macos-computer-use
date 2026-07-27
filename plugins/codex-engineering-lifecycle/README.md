# Codex Engineering Lifecycle

Codex Engineering Lifecycle is a repository-scoped plugin for feature delivery
with three durable Codex tasks:

- **Requirements** turns natural-language requests into a confirmed, committed
  requirements snapshot.
- **Engineering Main** writes the technical plan, runs serialized Goal-mode
  implementation and remediation, prepares the PR, publishes an explicitly
  authorized release, and closes the feature.
- **Engineering Review** independently reviews technical plans and exact PR
  heads, writes immutable review records, and merges only under the configured
  policy.

The plugin packages `feature-lifecycle`, `product-workflow-gate`,
`technical-plan-write`, `technical-plan-review`, and `pr-review`. Those
composition skills are explicit-only; the role skills invoke them at the
correct lifecycle gates.

## Prerequisites

- Codex Desktop/CLI with plugin, task-management, and Goal support.
- Git and Python 3.
- A trusted Git checkout with one canonical GitHub `origin`.
- GitHub read access; push, PR, merge, and release rights are needed only for
  the corresponding lifecycle actions.
- Explicit user authorization for Goal mode during Init.

Init does not authorize merging or releasing. Merge policy is selected during
Init, and every release requires a new exact per-release authorization.

## Install from GitHub

Add this repository as a Git marketplace, install the plugin, then start a new
Codex task:

```bash
codex plugin marketplace add zhanghao1903/macos-computer-use --ref main
codex plugin add codex-engineering-lifecycle@macos-computer-use
```

Verify discovery:

```bash
codex plugin list --marketplace macos-computer-use
```

The source can also be browsed or downloaded from
[GitHub](https://github.com/zhanghao1903/macos-computer-use/tree/main/plugins/codex-engineering-lifecycle)
or as a
[repository ZIP](https://github.com/zhanghao1903/macos-computer-use/archive/refs/heads/main.zip).

For pre-merge development testing, use the feature ref explicitly:

```bash
codex plugin marketplace add zhanghao1903/macos-computer-use \
  --ref codex/engineering-lifecycle-plugin
codex plugin add codex-engineering-lifecycle@macos-computer-use
```

## Init

Open the target repository in a new Codex task and request:

```text
Use $engineering-workflow-init to initialize this repository.
```

Init explains the policy and asks for the two material choices:

1. explicit permission to use Goal mode for approved implementation work;
2. `review-only` or `merge-on-approve` and, for automatic merge, the allowed
   merge method.

After confirmation, Init first writes a recoverable pending ledger, then creates
and pins exactly:

```text
Requirements · <repository>
Engineering Main · <repository>
Engineering Review · <repository>
```

Each returned task ID is recorded immediately, so an interrupted Init reuses
already-created tasks instead of duplicating them. Finalization binds their IDs
to the canonical repository, bootstraps the three roles, and reports the
workflow ID and local state location. Each role may emit only its strict
bootstrap acknowledgement before global readiness; feature work remains
forbidden until all three acknowledgements are durable.

Submit new feature requests to the Requirements task. Do not send a feature
directly to Main or Review.

## Lifecycle

```text
Natural-language request
  → confirmed requirements
  → technical plan
  → independent plan review
  → user notified that development starts
  → serialized GoalRun implementation
  → exact-head code review and report
  → findings remediation in a new GoalRun, when needed
  → policy-gated merge
  → exact release proposal and user authorization
  → GitHub Release and/or PyPI proof
  → feature closure
```

Plan and code failures return to Main. A completed GoalRun is never reopened;
code findings authorize a new `CODE_REMEDIATION` GoalRun. Only one GoalRun may
be active across the workflow, so multiple features remain deterministic.

Review uses `codex/review-records/...` branches. They contain only review
artifacts, are never force-pushed, and are retained as audit evidence.

With `review-only`, Review first returns `APPROVE`/`READY` and does not merge.
After a separately authorized human or merge owner merges the exact head,
Review refreshes GitHub state and records the observed `MERGED` proof. With
`merge-on-approve`, Review may perform and record the merge only when every
configured gate passes.

## Release behavior

Main presents the exact version, tag, merge commit, target types, artifact
names, and SHA-256 digests. The user must authorize that exact proposal.
Supported targets in v0.1.0 are:

- GitHub Release for the bound repository;
- PyPI or TestPyPI.

One failed target keeps the feature open. A retry may contain only the failed
targets from the same authorization; successful proof remains durable. A new
proposal requires a new explicit authorization. Closure is rejected until
every authorized target is published with matching artifact digests.
Successful GitHub URLs are bound to the authorized repository/tag, and
PyPI/TestPyPI URLs are bound to the normalized project/version and index.
After success, a response-loss retry is accepted only when it exactly repeats
the last accepted submission or the complete cumulative result. Other
successful subsets are rejected so they cannot impersonate the last operation.
State validation also rejects merge, release, or closure proof that belongs to
a later stage than the feature currently declares.

## Update

Refresh the Git snapshot, reinstall the plugin, and use a new task:

```bash
codex plugin marketplace upgrade macos-computer-use
codex plugin add codex-engineering-lifecycle@macos-computer-use
```

State schema v1 is validated before mutation. An incompatible future state is
rejected rather than silently downgraded.

## Uninstall

Remove the plugin:

```bash
codex plugin remove codex-engineering-lifecycle@macos-computer-use
```

If no other plugin from this repository is needed, remove the marketplace:

```bash
codex plugin marketplace remove macos-computer-use
```

Uninstall does **not** archive the three user-owned tasks or delete workflow
state, branches, PRs, tags, releases, or packages. This preserves recovery and
audit history. See [PRIVACY.md](PRIVACY.md) for the exact state boundary.

## Status and recovery

The helper is located at `scripts/workflowctl.py`. From the plugin source:

```bash
python3 scripts/workflowctl.py status --repo /absolute/path/to/repository
```

State is derived from the canonical GitHub origin and Git common directory:

```text
${CODEX_HOME:-~/.codex}/engineering-lifecycle/projects/<repository-key>/
```

Repeated Init is idempotent only when repository, task IDs, and policies match.
For interrupted task creation, `status` exposes the pending task IDs and missing
roles; reuse them and record only proven existing tasks. A config-only crash
window is finalized with the same IDs and workflow ID. For incomplete
bootstrap, resend only missing role messages. For malformed state, preserve the
files and diagnose them; do not hand-edit or delete them.
See the Init skill's `setup-and-recovery.md` for detailed error handling.

## Development verification

From the repository root:

```bash
python3 -m unittest discover \
  -s plugins/codex-engineering-lifecycle/tests \
  -p 'test_*.py'

python3 plugins/codex-engineering-lifecycle/scripts/validate_contracts.py
```

Strict JSON Schema and packaged `pr-review` tests require the development-only
`jsonschema` dependency:

```bash
python3 plugins/codex-engineering-lifecycle/scripts/validate_contracts.py \
  --require-jsonschema
```

## Safety and support

The runtime stores identifiers and proof metadata, not credentials, raw prompts,
transcripts, source content, diffs, or finding text. Review and release skills
still perform external actions only within their documented user and policy
gates.

Report problems using [SUPPORT.md](SUPPORT.md). Do not attach credentials,
private source, raw prompts, or unredacted command logs.
