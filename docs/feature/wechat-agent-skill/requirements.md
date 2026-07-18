# WeChat Agent Skill Requirements

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | `wechat-agent-skill` |
| Branch | `codex/wechat-agent-skill` |
| Baseline | `origin/main` at `95f6364` |
| Current phase | F0 intake and repository hygiene complete; F1 pending |
| Started | 2026-07-18 |
| Affected package | `wechat-desktop-tool` |

## F0 Intake

Application developers can currently register the semantic operations exposed
by `wechat-desktop-tool`, but an Agent receives no packaged instructions for
choosing those operations, sequencing them safely, interpreting failures, or
recovering from ambiguous and unknown outcomes.

The requested feature is a distributable `wechat-use` skill that an application
can load alongside `wechat-desktop-tool`. The skill should teach an Agent how to:

- inspect the current WeChat state;
- list contacts and conversations;
- open an exact contact and read visible messages;
- draft and send a message through the package-owned semantic operations;
- ask for clarification or confirmation at the correct boundary;
- avoid unsafe retries when a mutating result is unknown.

This phase records the request and repository boundary only. The consumer
contract, file format, loader API, and implementation are intentionally deferred
to F1 through F4.

## Existing Upstream Capabilities

The package already exposes the semantic operations needed by the skill:

- `open_wechat` and `inspect_window`;
- `list_contacts` and `list_conversations`;
- `open_contact` and `focus_contact`;
- `read_visible_messages` and `read_contact_messages`;
- `draft_message`, `submit_draft`, and `send_message`;
- normalized `ToolObservation` results and stable WeChat failure kinds.

The feature should orchestrate and explain these APIs. It must not duplicate
Accessibility selectors, implement a second WeChat automation backend, or make
the package depend on an LLM or Agent framework.

## Initial Scope Boundary

The expected implementation area is limited to:

- packaged skill assets owned by `wechat-desktop-tool`;
- an additive, framework-neutral way for Python applications to load or export
  those assets;
- package metadata required to include the skill in wheel and sdist artifacts;
- deterministic tests and an application-developer example;
- stable integration documentation and a release record.

No changes are currently expected in `app-control-protocol` or
`computer-use-macos`. Any later need to change those packages must be documented
and reviewed before implementation.

## Safety Baseline

- Contact and message content is private application data and must not be
  logged or embedded in skill assets.
- Read-only operations may be selected without a desktop mutation
  confirmation, subject to the embedding application's own authorization.
- Opening a contact changes desktop state but does not send content.
- Drafting and sending are mutating operations. The embedding application owns
  business authorization, user confirmation, and audit records.
- `submit_unknown`, `send_unverified`, transport loss after submission, or any
  equivalent unknown result must never trigger an automatic replay.
- The skill must use normalized WeChat operations and must not instruct the
  Agent to issue raw coordinate clicks or consume raw Accessibility trees.

## Repository Hygiene

The feature branch was created from `origin/main` so that the unrelated local
`main` commit is not included in this feature history. Existing local smoke
outputs, raw WeChat window captures, build artifacts, and generated lock files
remain untracked and are excluded from every feature phase commit.

## Working Assumptions For F1

- The distributable artifact will use the repository's standard skill shape:
  a `SKILL.md` file with optional `agents/openai.yaml` and focused references.
- The package will remain independent of Codex, OpenAI Agents SDK, LangChain,
  and other Agent runtimes.
- Application developers will be able to consume structured skill content from
  Python and materialize the standard directory when their runtime expects
  filesystem-based skills.
- The exact loading API, version contract, overwrite behavior, and supported
  workflows are not confirmed until F1 and F2 are complete.

## Phase Documents

| Phase | Documentation carrier |
| --- | --- |
| F0-F1 | `requirements.md` |
| F2 | `design.md` |
| F3 | `implementation-plan.md` |
| F4 | `implementation-notes.md` |
| F5 | `verification.md` and stable package docs |
| F6 | `merge-readiness.md`, PR description, and `CHANGELOG.md` |
