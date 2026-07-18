# Add a packaged WeChat Agent skill

## Problem

Applications can already register `wechat-desktop-tool` semantic operations,
but the package gives their Agent no reusable instructions for choosing those
operations, handling contact ambiguity, distinguishing a draft from a send, or
recovering safely from an unknown send result.

Each application therefore has to rebuild the same WeChat operation knowledge
and can easily introduce unsafe retry behavior.

## Solution

Ship a versioned, framework-neutral `wechat-use` skill inside
`wechat-desktop-tool` and expose additive Python APIs to:

- load the validated bundle as immutable models;
- obtain JSON-compatible registration data;
- export a standard `wechat-use` directory for filesystem-based Agent
  runtimes, without overwriting existing application files.

The skill covers WeChat inspection, contacts, conversations, exact-contact
opening, visible-message reads, drafts, authorized text sends, and structured
failure recovery. It uses the existing semantic operations and does not add an
Agent/LLM SDK or another desktop automation backend.

## Public API

```python
from wechat_desktop_tool import (
    export_wechat_use_skill,
    load_wechat_use_skill,
)

skill = load_wechat_use_skill()
registration = skill.to_dict()

skill_dir = export_wechat_use_skill(".agents/skills")
```

New public models and constants describe schema `wechat.agent-skill.v1`, skill
name `wechat-use`, skill version `1.0.0`, entrypoint `SKILL.md`, bundled files,
media types, content, and SHA-256 digests.

Loading and export perform no desktop, socket, token, permission, network,
tool-registration, or send action. Export raises `FileExistsError` when the
target already exists.

## Safety

The embedding application remains responsible for tool registration,
authorization, confirmation, privacy, and audit. The skill requires exact
contact, exact message content, and explicit intent before sending.

Unknown mutation outcomes, including `submit_unknown`, `send_unverified`,
`status=unknown`, or transport loss after a possible submit, require manual
WeChat verification and must never be replayed automatically.

## Verification

- 12 Agent-skill unit tests passed.
- 171 `wechat-desktop-tool` tests passed.
- 132 root SDK and boundary tests passed.
- 55 `app-control-protocol` tests passed.
- 168 `computer-use-macos` tests passed; 1 environment-dependent socket test
  was skipped.
- Ruff, strict mypy for `agent_skill.py`, and Skill Creator validation passed.
- The offline application example passed.
- Source release preflight passed.
- All three wheels and sdists passed content checks.
- A clean installed wheel loaded and validated the packaged skill.

No live WeChat mutation was needed for this static loading/export feature.
TestPyPI installation proof remains part of the version-release phase.

## Documentation And Release Record

- Added stable API and Agent integration guidance.
- Updated the package README and WeChat package documentation.
- Added requirements, design, implementation, verification, and merge-readiness
  lifecycle records.
- Added an `Unreleased / Added` changelog entry.

## Compatibility And Migration

This change is additive. Existing imports, protocol schemas, semantic
operations, runtime dependencies, and configuration are unchanged. Consumers
that do not load the skill observe no behavior change.

The skill version is independent of the Python package version. No application
migration is required.
