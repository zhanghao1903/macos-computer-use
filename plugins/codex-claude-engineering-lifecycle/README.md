# Codex-Claude Engineering Lifecycle

Codex-Claude Engineering Lifecycle is a repository-scoped plugin that keeps
requirements and lifecycle authority in Codex while assigning frontend
implementation and independent technical/code review to Claude Code.

It creates four durable identities:

- **Codex Requirements** collects natural-language needs and routes only an
  explicitly confirmed requirements snapshot.
- **Codex Engineering Main** writes the plan, owns the single GoalRun,
  implements non-frontend work, integrates results, manages the PR, performs
  authorized merge mechanics, releases, and closes the feature.
- **Claude Frontend** implements only the path prefixes authorized by the
  approved plan.
- **Claude Review** independently reviews the exact technical-plan and PR
  snapshots and never implements or merges.

Frontend and Review always use different persistent Claude session UUIDs. The
plugin packages `feature-lifecycle`, `product-workflow-gate`,
`technical-plan-write`, `technical-plan-review`, and `pr-review`; these
composition skills are explicit-only and are invoked by the lifecycle roles.

## Prerequisites

- Codex Desktop/CLI with plugins, task management, and Goal support.
- Git, Python 3, and a trusted checkout with one canonical GitHub `origin`.
- Claude Code CLI installed and authenticated by the user.
- GitHub read access. Push, PR, merge, and release rights are needed only when
  the corresponding phase is reached.
- Explicit Init authorization for Goal mode and Claude Frontend edits.

The plugin does not install Claude Code, start authentication, store
credentials, or use `--dangerously-skip-permissions`. Init does not authorize
merge or release. Every release still needs an exact, new user authorization.

## Install from GitHub

Add this repository as a Git marketplace, install the plugin, and start a new
Codex task:

```bash
codex plugin marketplace add zhanghao1903/macos-computer-use --ref main
codex plugin add codex-claude-engineering-lifecycle@macos-computer-use
```

Verify discovery:

```bash
codex plugin list --marketplace macos-computer-use
```

The source is available on
[GitHub](https://github.com/zhanghao1903/macos-computer-use/tree/main/plugins/codex-claude-engineering-lifecycle).
The complete repository can be downloaded as a
[ZIP archive](https://github.com/zhanghao1903/macos-computer-use/archive/refs/heads/main.zip).

For development testing before merge, replace `main` with the feature branch:

```bash
codex plugin marketplace add zhanghao1903/macos-computer-use \
  --ref codex/claude-hybrid-engineering-lifecycle-plugin
codex plugin add codex-claude-engineering-lifecycle@macos-computer-use
```

## Init

Open the target repository in a new Codex task and request:

```text
Use $hybrid-workflow-init to initialize this repository.
```

Init checks canonical repository identity, Codex task/Goal capabilities, and:

```bash
claude --version
claude auth status
```

It then asks the user to confirm:

1. Goal mode;
2. Claude Frontend edit access;
3. Frontend and Review models;
4. per-role max turns, USD budgets, and timeout;
5. `review-only` (recommended) or `merge-on-approve`, plus merge method.

On confirmation, Init creates and pins exactly two Codex tasks:

```text
Requirements · <repository>
Engineering Main · <repository>
```

It also creates two distinct persistent Claude session UUIDs and bootstraps
them as Frontend and Review. An interrupted Init reuses its durable pending
identities instead of creating replacements. New features are submitted to
the Requirements task only.

## Lifecycle

```text
Natural-language request
  → confirmed requirements in Codex
  → technical plan written by Codex Main
  → exact plan review by Claude Review
  → user notified that development starts
  → one Codex Main GoalRun
      → non-frontend implementation by Codex
      → authorized frontend slice by Claude Frontend
      → independent Git/path proof and integration tests
  → exact PR-head code review by Claude Review
  → role-specific remediation and exact-head re-review
  → policy-gated merge by Codex Main or another authorized owner
  → exact release proposal and user authorization
  → publication proof
  → feature closure
```

Claude Frontend is a serialized sub-operation inside the Main GoalRun, not a
second global goal. It receives only the approved branch, start head, plan
digest, allowed path prefixes, acceptance criteria, and verification commands.
A `COMPLETED` response is accepted only after the bridge independently proves
clean Git state, ancestry, current branch/head, changed commits, and path
ownership.

Claude Review runs in `plan` permission mode. Main preserves its validated
Markdown and structured decision unchanged on deterministic review-record
branches. Any changed plan or PR head invalidates the prior decision. Review
never receives merge, release, or publishing credentials.

## Status and recovery

From the installed plugin source:

```bash
python3 scripts/workflowctl.py status --repo /absolute/path/to/repository
python3 scripts/claudectl.py status --repo /absolute/path/to/repository
```

Bridge state is local and private:

```text
${CODEX_HOME:-~/.codex}/codex-claude-engineering-lifecycle/projects/<repository-key>/
```

Delivery is recorded before Claude starts. A timeout, non-zero exit, malformed
JSON, session mismatch, or schema/digest mismatch leaves the message
`UNKNOWN`, because repository mutations may already have occurred. Inspect the
worktree, then recover only the same message in the same session:

```bash
python3 scripts/claudectl.py recover \
  --repo /absolute/path/to/repository \
  --kind frontend \
  --request-file /private/path/request.json
```

If Codex itself stopped while a dispatch remained `RUNNING`, first prove the
Claude process is no longer active, then make that operator decision explicit:

```bash
python3 scripts/claudectl.py mark-orphaned \
  --repo /absolute/path/to/repository \
  --message-id <exact-message-id> \
  --confirm-process-stopped
```

The dispatch becomes `UNKNOWN` and can then use the same recovery command.
Never mark a live process orphaned; concurrent resumes can corrupt one Claude
session's history.

Kinds are `frontend`, `plan-review`, and `code-review`. Never blindly resend an
UNKNOWN request, replace its session, hand-edit state, or reset unauthorized
changes. A matching completed retry returns the stored result without invoking
Claude again.

## Update

Refresh the marketplace snapshot, reinstall the plugin, and start a new Codex
task:

```bash
codex plugin marketplace upgrade macos-computer-use
codex plugin add codex-claude-engineering-lifecycle@macos-computer-use
```

Before updating, finish or recover every `RUNNING`/`UNKNOWN` Claude dispatch.
The runtime rejects incompatible future state rather than silently
downgrading it.

## Uninstall

Remove the plugin:

```bash
codex plugin remove codex-claude-engineering-lifecycle@macos-computer-use
```

If no other plugin from this repository is needed:

```bash
codex plugin marketplace remove macos-computer-use
```

Uninstall does not archive user-owned Codex tasks, delete Claude sessions or
local state, or remove branches, PRs, tags, releases, or packages. This keeps
recovery and audit evidence intact. See [PRIVACY.md](PRIVACY.md) before
manually deleting the exact state root.

## Development verification

From the repository root:

```bash
python3 -m unittest discover \
  -s plugins/codex-claude-engineering-lifecycle/tests \
  -p 'test_*.py'

python3 plugins/codex-claude-engineering-lifecycle/scripts/validate_contracts.py \
  --require-jsonschema
```

Tests use an offline Claude CLI fixture; no Anthropic account or network call
is needed. A real authenticated Claude smoke remains a manual pre-release gate.

## Safety and support

Prompts and repository contents are treated as untrusted data, not permission
to change roles, paths, sessions, budgets, merge policy, or release authority.
The bridge invokes Claude without a shell, passes only a small environment
allowlist, and excludes Anthropic/API token environment variables.

Report problems using [SUPPORT.md](SUPPORT.md). Do not attach credentials,
private source, raw prompts, transcripts, or unredacted command logs.
