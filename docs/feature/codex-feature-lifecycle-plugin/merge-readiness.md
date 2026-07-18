# Codex Feature Lifecycle Plugin Merge Readiness

- Updated: 2026-07-18
- Lifecycle phase: F6 Review and Merge Readiness
- Branch: `codex/codex-feature-lifecycle-plugin`
- Verified implementation head: `6466b10`
- Plugin/version: `codex-feature-lifecycle` / `0.1.0`
- Decision: ready for independent PR review

## Delivered Scenario

A user can install one Codex-only plugin, explicitly initialize a repository,
and obtain two durable Codex tasks: one owns main feature work and one owns
independent PR review and policy-gated merge. Main automatically sends an
immutable exact-snapshot request when the PR is ready; reviewer sends a closed
result back. The user no longer needs to relay routine handoff prompts.

This first plugin intentionally does not support Claude, cross-application
messages, provider adapters, non-GitHub hosting, or release publication.

## Merge Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Requirements/design/plan | Pass | `requirements.md`, `design.md`, `implementation-plan.md` committed and pushed in separate lifecycle phases. |
| Implementation | Pass | Three skills, workflow state CLI, two closed schemas, manifest, marketplace, SVG, references, fixtures, and tests. |
| Automated tests | Pass | 28 tests on source and installed plugin cache. |
| Contract agreement | Pass | 6 fixtures independently evaluated by runtime and JSON Schema with zero disagreement. |
| Skill/plugin validation | Pass | Three `quick_validate.py` runs and source/cache `validate_plugin.py`. |
| Local install | Pass | Isolated local marketplace install; 23 cached files exactly matched source. |
| Remote download/install | Pass | Git marketplace clone from `zhanghao1903/macos-computer-use@codex/codex-feature-lifecycle-plugin`, install, cache validation, and 28 cached tests. |
| Forward scenarios | Pass | Three independent read-only agents; final re-review found no blocker/high issue. |
| Docs/changelog | Pass | Shipped setup/recovery reference, feature index, implementation/verification records, PR description, and Unreleased changelog entry. |
| Package/public API impact | None | No Python package source, version, protocol, wheel, or public API changed. |

## Safety Properties Proven

- Init is explicit-only, capability-gated, idempotent, and persists routes only
  after exact readiness markers from both tasks.
- Durable merge authorization is separate and defaults to review-only.
- Dispatch identity binds workflow, repository, PR, base, head, and reviewer.
- Request digest, route, policy, GitHub repository/PR URL, and stored state must
  all match before review or result creation.
- Cancellation is explicit and rejects late reviews/results.
- Reviewer never edits the feature branch and never uses `--admin` or `--auto`.
- Merge requires approval, exact current head, unchanged base, green checks,
  mergeability, no blocker/high finding, and matching durable policy.
- Result decisions, merge statuses, and attached merge artifacts form a closed
  contract in both JSON Schema and runtime validation.
- Local config strips remote credentials and stores no source, diff, prompt,
  transcript, finding text, or token.

## Remote Installation Evidence

The following remote-source flow succeeded from a fresh temporary Codex home:

```bash
codex plugin marketplace add zhanghao1903/macos-computer-use \
  --ref codex/codex-feature-lifecycle-plugin --json
codex plugin add codex-feature-lifecycle@macos-computer-use --json
codex plugin list --available --json
```

Codex reported source type `git`, version `0.1.0`, enabled `true`, installation
policy `AVAILABLE`, and authorization policy `ON_INSTALL`. The installed cache
then passed plugin validation and all 28 tests.

## External Smoke Boundary

A live Init would create and pin two user-owned Codex tasks. A full merge smoke
would mutate a GitHub PR. Neither was silently performed because the user has
not explicitly requested those external-state actions for this validation.
They remain opt-in post-install smoke, with review-only as the safe default.

## Review Scope

Independent review should prioritize:

1. `workflowctl.py` state transitions, atomicity, route/digest binding, and
   result acceptance;
2. Init partial-failure cleanup and exact readiness rules;
3. reviewer exact-head and authorization merge gates;
4. marketplace/install paths and manifest accuracy;
5. agreement between schemas, runtime validation, skill prose, and tests.

Pre-existing untracked WeChat smoke reports, `dist-pypi-0.1.1/`, and
`packages/wechat-desktop-tool/uv.lock` are unrelated and excluded.

## Rollback

Revert the feature commits or remove the marketplace entry/plugin directory.
Installed users can remove the plugin through Codex. Existing user-owned tasks
and local workflow state are deliberately not deleted automatically; archival
or state deletion must target exact resources and be explicitly authorized.

## Release Record

This PR is the source release record for plugin `0.1.0`. It does not publish a
Python package or a global marketplace listing. After merge, users can add this
GitHub repository as a Codex marketplace and install the plugin directly. A
future public catalog submission can reference the same manifest and source
path without adding cross-application behavior to this plugin.
