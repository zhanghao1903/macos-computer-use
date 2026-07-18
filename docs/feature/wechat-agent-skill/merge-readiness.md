# WeChat Agent Skill Merge Readiness

## Decision

| Field | Value |
| --- | --- |
| Lifecycle phase | F6 review and merge readiness |
| Status | Ready for pull request review |
| Feature branch | `codex/wechat-agent-skill` |
| Reviewed base | `eb518006617b14839014d08b929f4035855b0ae8` |
| Reviewed feature head | `8c9052095214370f629137c55beee3a3bb256aac` |
| Blocking findings | None identified in the local merge-readiness review |
| Release record | `CHANGELOG.md` under `Unreleased / Added` |
| Release impact | Candidate for the next minor package-suite release; no version bump in this feature branch |

The reviewed feature implementation and F5 evidence are ready to enter pull
request review. The final F6 commit adds only this readiness record, the PR
description, lifecycle status, and changelog entry. GitHub CI and review of the
remote PR head remain authoritative after that documentation-only commit.

## Scenario Solved

An application that already registers `wechat-desktop-tool` semantic
operations can now load a packaged `wechat-use` skill. The Agent receives
framework-neutral instructions for inspecting WeChat, listing contacts and
conversations, opening exact contacts, reading visible messages, drafting text,
sending authorized text, and recovering without replaying an unknown send.

Applications that discover skills from disk can export the same validated
bundle into an application-selected parent directory. Applications with an
in-memory registry can consume an immutable Python model or its JSON-compatible
dictionary representation.

## Public Contract Review

The package adds these public symbols without changing existing APIs:

- `WECHAT_AGENT_SKILL_SCHEMA`;
- `WECHAT_USE_SKILL_NAME`;
- `WECHAT_USE_SKILL_RESOURCE`;
- `WeChatAgentSkillFile`;
- `WeChatAgentSkill`;
- `load_wechat_use_skill()`;
- `export_wechat_use_skill(parent_directory)`.

The skill schema is `wechat.agent-skill.v1`; the initial independent skill
version is `1.0.0`. Loading is read-only. Export creates
`<parent>/wechat-use` exclusively and raises `FileExistsError` rather than
overwriting or merging an application-owned directory.

No Agent framework, LLM SDK, desktop backend, protocol, configuration, or
runtime dependency was added. Existing consumers that do not load the skill
observe no behavior change.

## Safety And Privacy Review

- Skill loading and export do not connect to the local service, read a token,
  request permissions, open WeChat, register tools, or send content.
- The skill routes the Agent through normalized semantic operations and does
  not teach raw Accessibility paths or coordinate clicks.
- Contact names, message content, authorization, confirmation, privacy policy,
  and audit records remain application-owned.
- Sending requires exact target, exact content, and explicit intent.
- `submit_unknown`, `send_unverified`, `status=unknown`, and transport loss
  after a possible submit require manual verification and prohibit automatic
  replay.
- Packaged assets contain no contacts, messages, credentials, local paths, or
  raw WeChat captures.

## Verification Evidence

The detailed record is in [verification.md](./verification.md). Merge-relevant
evidence includes:

| Surface | Evidence |
| --- | --- |
| Skill model, manifest, loader, export, cleanup, safety content | 12 unit tests passed |
| `wechat-desktop-tool` regression | 171 tests passed |
| Root SDK and package boundaries | 132 tests passed |
| Protocol package regression | 55 tests passed |
| macOS backend regression | 168 passed, 1 environment skip |
| Static quality | Ruff passed; strict mypy passed for `agent_skill.py` |
| Skill structure | Skill Creator validation passed |
| Consumer flow | Offline SDK example passed |
| Source contract | Release preflight passed |
| Distribution contract | Wheel, sdist, and clean-wheel import smoke passed |
| Scope hygiene | Diff whitespace and sensitive-value checks passed |

No live WeChat mutation was needed because this feature loads static package
resources and delegates all desktop behavior to existing operations.

## Review Findings

The local review followed the complete path from packaged resources through
manifest validation, immutable models, public exports, safe directory export,
package metadata, wheel/sdist expectations, installed-package smoke, SDK
example, and developer documentation.

No correctness, security, compatibility, packaging, or test finding was found
that should block pull request review. The following residual risks are
explicit and non-blocking for this additive feature:

- downstream Agent runtimes must map the framework-neutral payload into their
  own registration API;
- static instructions cannot replace application authorization, confirmation,
  privacy, or audit enforcement;
- TestPyPI installation proof is deferred to the version-release phase;
- v1 export intentionally has no overwrite, update, or merge mode;
- a real Agent-runtime behavioral evaluation may be added by an embedding
  application, but the package itself has no Agent-runtime dependency.

## Merge Checklist

- [x] One feature per branch.
- [x] F0-F5 each have a tracked documentation carrier and pushed commit.
- [x] Requirements, design, implementation plan, implementation notes, and
  verification evidence agree with the shipped contract.
- [x] Stable API, package, Agent integration, and feature-index docs updated.
- [x] Package data, wheel, sdist, and clean-install checks updated.
- [x] Application-consumer example added and tested.
- [x] `CHANGELOG.md` release record added.
- [x] Local generated JSON, raw window captures, lock files, build directories,
  and private proof artifacts excluded.
- [x] F6 readiness artifacts included in the phase commit for push.
- [ ] Pull request created and remote CI passed.
- [ ] Independent pull request review completed on the final remote head.

## Rollback And Migration

Rollback is removal of the additive exports, `agent_skill.py`, packaged skill
resources, package-data patterns, and related docs/tests. No stored data,
protocol schema, desktop selector map, or configuration migration is involved.

Existing application code requires no migration. New consumers should treat
the skill schema and skill version as separate compatibility values and should
not assume the Python package version equals the skill version.
