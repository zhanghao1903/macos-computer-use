# Codex-Claude Engineering Lifecycle Plugin — PR Preparation

- Phase: F6 draft PR
- Date: 2026-07-31
- Status: Draft; independent review pending
- Pull request:
  https://github.com/zhanghao1903/macos-computer-use/pull/13
- Base: `codex/engineering-lifecycle-plugin`
- Head: `codex/claude-hybrid-engineering-lifecycle-plugin`

## Review scope

The PR is intentionally stacked on the branch that introduces the Codex-only
engineering lifecycle plugin. This keeps the review diff focused on:

- the new sibling `codex-claude-engineering-lifecycle` plugin;
- two Codex roles plus separate Claude Frontend/Review sessions;
- the deterministic Claude Code bridge and transport schemas;
- frontend Git/path verification and recovery state machine;
- offline tests and validation fixtures;
- repository marketplace/root documentation entries.

The existing Codex-only plugin is not modified by this PR.

## Review priorities

1. Verify Frontend and Review session identity cannot collapse or cross-route.
2. Verify no message/result can authorize work without exact request,
   schema, session, workflow, repository, feature/cycle, and snapshot binding.
3. Verify UNKNOWN and orphaned RUNNING recovery cannot blindly resend a
   mutating operation.
4. Verify Frontend cannot gain authority outside approved path prefixes.
5. Verify Claude Review decisions remain independent and cannot merge/release.
6. Verify Init, update, uninstall, privacy, and external Anthropic data
   boundaries are understandable to another user installing from GitHub.

## Evidence

- Implementation commit: `1616ab5`
- Verification commit: `4062a19`
- Full plugin suite: 37 passing tests
- Strict contract suite: 26 fixtures, 0 failures
- Ruff: pass
- mypy: pass
- official plugin validator: pass
- three new role skill validators: pass

## Known review/release gap

The current host has no Claude Code executable. A real authenticated
bootstrap/frontend/plan-review/code-review/recovery smoke remains a documented
pre-release gate. The PR stays draft, and no merge or release is authorized.
