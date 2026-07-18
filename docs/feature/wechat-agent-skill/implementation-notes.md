# WeChat Agent Skill Implementation Notes

## Phase Status

| Field | Value |
| --- | --- |
| Lifecycle phase | F4 implementation |
| Status | Complete |
| Branch | `codex/wechat-agent-skill` |
| Requirements | [requirements.md](./requirements.md) |
| Design | [design.md](./design.md) |
| Plan | [implementation-plan.md](./implementation-plan.md) |

## Implemented Slice

`wechat-desktop-tool` now owns a packaged, versioned `wechat-use` Agent skill
and a framework-neutral Python loading surface.

Added public API:

- `WECHAT_AGENT_SKILL_SCHEMA`;
- `WECHAT_USE_SKILL_NAME`;
- `WECHAT_USE_SKILL_RESOURCE`;
- `WeChatAgentSkillFile`;
- `WeChatAgentSkill`;
- `load_wechat_use_skill()`;
- `export_wechat_use_skill(parent_directory)`.

The skill bundle contains:

- `manifest.json` with schema `wechat.agent-skill.v1` and version `1.0.0`;
- a standard `SKILL.md` entrypoint;
- `agents/openai.yaml` display metadata;
- operation and recovery references.

## Loader Behavior

The loader uses `importlib.resources` and Python standard-library parsing only.
It validates the exact manifest fields, schema, skill identity, semantic
version, entrypoint, unique file list, supported suffixes, and safe relative
POSIX paths before returning an immutable model.

Each loaded UTF-8 resource contains:

- relative path;
- deterministic media type;
- exact text content;
- SHA-256 digest of the UTF-8 bytes.

`WeChatAgentSkill.instructions` resolves the manifest entrypoint. `get_file()`
returns a named bundled resource, and `to_dict()` produces a JSON-compatible
application-registration payload.

Loading has no dependency on macOS frameworks, app-control clients, local
services, Agent SDKs, or network access.

## Export Behavior

`export_wechat_use_skill(parent_directory)`:

1. loads and validates the entire source bundle;
2. expands and resolves the selected parent directory;
3. exclusively creates `<parent>/wechat-use`;
4. writes a deterministic manifest and every validated resource;
5. removes only the newly created target if a write fails;
6. returns the resolved target path.

The v1 implementation has no overwrite or merge option. An existing target
raises `FileExistsError` before any target content changes.

## Agent Guidance Implemented

The skill maps inspect, contact, conversation, read, draft, and send intent to
the existing semantic operations. It requires bounded list/message limits,
exact contact verification, explicit distinction between draft and send, and
application-owned authorization and confirmation.

The recovery contract treats `submit_unknown`, `send_unverified`,
`status=unknown`, transport loss after a possible submit, and contradictory
mutation evidence as manual-verification states. It explicitly forbids
automatic replay, regardless of a generic retry hint.

The skill does not contain raw AX paths, coordinates, tokens, local paths, real
contacts, message content, or application configuration.

## Packaging Changes

`packages/wechat-desktop-tool/pyproject.toml` now explicitly includes manifest,
Markdown, Agent metadata YAML, and reference Markdown patterns. Package and
suite boundary tests assert these patterns and continue to enforce the absence
of Agent/LLM SDK dependencies.

Release preflight and installed-wheel smoke updates are intentionally reserved
for F5, where packaging proof and stable developer documentation are completed
together.

## Automated Checks

The following checks passed on 2026-07-18:

```text
12/12  packages/wechat-desktop-tool/tests/test_agent_skill.py
171/171 packages/wechat-desktop-tool test suite
8/8    tests.test_package_boundary
ruff check: passed for all changed Python files
mypy --strict package config: no issues in agent_skill.py
skill quick_validate.py: Skill is valid
```

The tests cover malformed manifests, duplicate JSON keys, unsafe paths, missing
resources, model/hash integrity, complete export, existing-target protection,
partial-write cleanup, operation/safety content, and context-size limits.

No live WeChat smoke was run because this slice loads static package resources
and intentionally performs no desktop action.

## Design Conformance

Implementation matches the approved F2 public names, data structures, manifest
schema, initial skill version, no-overwrite behavior, standard-library-only
dependency boundary, and no-replay safety contract.

There are no design deviations in F4.

## Remaining F5 Work

- add the application-side SDK example;
- document the stable API and Agent integration path;
- extend public API and wheel/sdist release preflight expectations;
- extend the clean-installed-distribution smoke;
- run repository regression, release preflight, and wheel/sdist proof;
- record exact verification evidence in `verification.md`.
