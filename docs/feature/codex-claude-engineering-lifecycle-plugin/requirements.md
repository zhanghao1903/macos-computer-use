# Codex-Claude Engineering Lifecycle Requirements

## F0 — Intake and repository hygiene

- Feature: add a separate `codex-claude-engineering-lifecycle` plugin.
- Base: `codex/engineering-lifecycle-plugin` at
  `c8fa2770bc35aac428b5aaf22b1c5fb79ca0f222`.
- Feature branch: `codex/claude-hybrid-engineering-lifecycle-plugin`.
- Isolation: development runs in
  `/private/tmp/macos-computer-use-claude-hybrid-lifecycle`; unrelated
  untracked smoke and release artifacts in the primary worktree are excluded.
- Existing behavior: `codex-engineering-lifecycle` uses three Codex tasks for
  Requirements, Main, and Review.
- Requested behavior: keep requirements and primary engineering in Codex while
  delegating frontend implementation and independent review to durable Claude
  sessions.
- Packaging boundary: add one sibling repo-marketplace plugin. Do not change
  package APIs, desktop automation behavior, or the existing lifecycle plugin.
- External dependency: Claude Code CLI must be installed and authenticated by
  the user. The plugin must probe it and fail closed; Init must not install or
  authenticate Claude automatically.
- Phase records: this directory carries requirements, design, implementation
  plan, implementation notes, verification, and merge-readiness evidence.
- Release impact: plugin-only Unreleased entry; no Python package version bump
  or package publishing.

## F0 assumptions

- “Claude session” means a persistent Claude Code session addressable by an
  explicit UUID and resumed programmatically from the repository.
- Claude Frontend and Claude Review are different session IDs.
- This feature may build on the unmerged engineering-lifecycle source branch;
  its eventual pull request must declare that dependency.
