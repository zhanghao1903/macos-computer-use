# WeChat Agent Skill Requirements

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | `wechat-agent-skill` |
| Branch | `codex/wechat-agent-skill` |
| Release branch | `codex/release-0.3.0` |
| Baseline | `origin/main` at `eb51800` |
| Current phase | F0-F6 complete; F7 release preparation active |
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

## F2 Design Decisions

- The distributable artifact will use the repository's standard skill shape:
  a `SKILL.md` file with `agents/openai.yaml` and focused references.
- The package will remain independent of Codex, OpenAI Agents SDK, LangChain,
  and other Agent runtimes.
- Application developers will be able to consume structured skill content from
  Python and materialize the standard directory when their runtime expects
  filesystem-based skills.
- The loading API, version contract, no-overwrite export behavior, and supported
  workflows are defined in [design.md](./design.md).

## F1 Consumer Requirements

### Consumer And Runtime Contract

The primary consumer is an application developer who already uses
`wechat-desktop-tool` and exposes its semantic operations to an Agent. Loading
the skill must give the Agent procedural knowledge; it must not create a
`ComputerUseClient`, connect to a local service, read a token, request macOS
permissions, or register tools on the application's behalf.

Before invoking the skill, the embedding application is responsible for:

- constructing and configuring `WeChatDesktopTool` or an equivalent protocol
  client;
- exposing the supported `wechat.desktop` operations as Agent-callable tools;
- enforcing user identity, business authorization, confirmation, and audit
  policy;
- ensuring the helper or service has the required macOS permissions;
- deciding which contact and message data the Agent may observe.

The skill must remain useful whether the application exposes one generic
`wechat.desktop` command tool or separate wrappers named after individual
operations. It may describe the stable operation names and inputs, but must not
assume framework-specific decorators, tool-call envelopes, or response classes.

### Required Agent Scenarios

#### Inspect WeChat

Given a request to understand the current WeChat state, the Agent should use
`inspect_window` and reason from the normalized `wechat.window.v1` result. It
must not request raw Accessibility data unless the application explicitly runs
a diagnostic workflow outside this skill.

#### List Contacts Or Conversations

Given a request to show contacts, the Agent should call `list_contacts` with a
bounded limit no greater than 30 and report only the returned visible contacts.
Given a request about recent chats, it should use `list_conversations` instead.
It must not claim full address-book pagination or fabricate contacts when the
visible result is empty or truncated.

#### Read A Contact's Messages

Given an exact contact and a bounded requested count, the Agent should use
`read_contact_messages(contact, limit)` or the equivalent `open_contact`
followed by `read_visible_messages`. It must state that results contain visible,
currently loaded messages rather than a complete server-side history. The
default and maximum skill-guided request is 30 messages.

#### Open Or Switch To A Contact

Given an exact contact, the Agent should use `open_contact`. On
`contact_ambiguous`, it must present the returned candidates or ask the user for
a more precise name. On `contact_not_found`, it must report that no verified
match was found. It must never choose an ambiguous result implicitly.

#### Draft A Message

When the user asks to prepare text but not send it, the Agent should open the
verified target and call `draft_message`. Drafting must not be described as a
successful send, and the Agent must not call `submit_draft` afterward without a
new or already explicit send authorization.

#### Send A Message

The Agent may call `send_message` only when all of these values are known and
authorized by the embedding application:

- exact target contact;
- exact message content;
- explicit intent to send now.

If any value is missing, inferred with material uncertainty, or changed after
confirmation, the Agent must ask for clarification or confirmation. The skill
should prefer `verifyAfterSubmit=true` when the application exposes that input,
while treating verification as observation evidence rather than an exactly-once
delivery guarantee.

### Result And Recovery Requirements

The skill must teach the Agent to inspect structured status and failure fields
before interpreting summaries. Required routing behavior is:

- `ok`: use only the normalized observation fields returned by the operation;
- `contact_ambiguous`: ask the user to select or refine the contact;
- `contact_not_found`: report no verified match and allow a corrected name;
- `wechat_not_ready`, `wechat_not_logged_in`, or permission failures: explain
  the prerequisite and stop the workflow;
- query timeout, truncation, or transport failure during a read: report partial
  or unavailable data and allow a bounded read retry;
- validation and unsupported-operation failures: correct the tool call rather
  than retrying unchanged input;
- `submit_unknown`, `send_unverified`, transport loss after a send attempt, or
  any result with `status=unknown`: tell the user to verify WeChat manually and
  never replay the mutating operation automatically.

The Agent must not translate an operation-level success into stronger claims
than the result supports. In particular, a successful key press is not proof
that a message was delivered or read.

### Skill Delivery Requirements

- The standard skill directory must be included in both wheel and sdist.
- Python consumers must have an additive public API for reading skill metadata
  and instructions without depending on a filesystem installation layout.
- Filesystem-based Agent runtimes must have a safe export operation that creates
  a complete skill directory at an application-selected destination.
- Export must not overwrite an existing directory by default.
- Skill loading and export must perform no desktop, network, or authentication
  operation.
- The skill must declare a version independently from the package version so a
  consumer can cache or audit the loaded instructions.
- The skill must contain no local paths, tokens, contact names, message content,
  raw Accessibility captures, or machine-specific configuration.

### Compatibility Requirements

- Existing imports and WeChat operations must remain unchanged.
- The package must not add an Agent framework or LLM SDK dependency.
- The public skill-loading API must work from a normal source checkout and from
  an installed wheel.
- Consumers that do not use the Agent skill must observe no behavior change.
- Runtime support remains Python 3.11 and later, matching the package metadata.

## Non-Goals

- Building an Agent runtime, planner, memory system, tool registry, or UI.
- Granting macOS permissions or starting the local app-control service.
- Defining business authorization or replacing application-owned confirmation.
- Exporting a complete WeChat address book or server-side message history.
- Adding image, file, voice, payment, deletion, group administration, or account
  management workflows.
- Teaching raw Accessibility selector construction, raw coordinate clicking, or
  fallback automation outside `wechat-desktop-tool`.
- Guaranteeing message delivery, receipt, or exactly-once execution.

## F1 Acceptance Criteria

F1 is complete when the tracked requirements unambiguously define:

- the application developer and Agent responsibilities;
- the required inspect, contact, conversation, read, draft, and send scenarios;
- the confirmation and unknown-result replay boundaries;
- the portable delivery and compatibility expectations;
- the private data and package-boundary constraints;
- explicit non-goals that prevent the skill from expanding into another Agent
  framework or desktop backend.

## Phase Documents

| Phase | Documentation carrier |
| --- | --- |
| F0-F1 | `requirements.md` |
| F2 | `design.md` |
| F3 | `implementation-plan.md` |
| F4 | `implementation-notes.md` |
| F5 | `verification.md` and stable package docs |
| F6 | `merge-readiness.md`, PR description, and `CHANGELOG.md` |
