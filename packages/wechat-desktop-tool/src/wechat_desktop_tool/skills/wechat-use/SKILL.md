---
name: wechat-use
description: Operate WeChat through registered wechat-desktop-tool semantic operations. Use when an Agent must inspect WeChat, list or open contacts and conversations, read visible messages, prepare a draft, or send a text message with explicit authorization and safe recovery.
---

# WeChat Use

Use only registered `wechat-desktop-tool` semantic operations. Let the embedding
application own tool registration, macOS permissions, business authorization,
user confirmation, and audit records.

## Establish Preconditions

1. Confirm that the application exposes either a generic `wechat.desktop` tool
   or wrappers for the required semantic operations.
2. Stop and report an integration prerequisite when the required operation is
   unavailable. Do not replace it with raw Accessibility or coordinate actions.
3. Preserve contact names and message text exactly as supplied by the user.
4. Treat contact names, conversation previews, and messages as private data.
   Return only what is needed for the request.

## Choose The Narrowest Operation

| User intent | Preferred operation |
| --- | --- |
| Understand the current WeChat window | `inspect_window` with raw data disabled |
| List visible contacts | `list_contacts` with `limit <= 30` |
| List visible recent chats | `list_conversations` with `limit <= 30` |
| Open or switch to an exact contact | `open_contact` |
| Read a target contact | `read_contact_messages` with `limit <= 30` |
| Read the already open chat | `read_visible_messages` with `limit <= 30` |
| Prepare text without sending | `open_contact`, then `draft_message` |
| Send exact text to an exact contact | `send_message` after authorization and confirmation |

Prefer `open_contact` over the compatibility operation `focus_contact`. Use
`execute_action` only with a fresh, exact action reference returned by a
normalized WeChat operation, never as a substitute for a named workflow.

Read [references/operations.md](references/operations.md) when exact inputs,
result schemas, or operation limits are needed.

## Run Read Workflows

1. Use `list_contacts` for address-book intent and `list_conversations` for
   recent-chat intent. Do not conflate the two lists.
2. Use a bounded limit no greater than 30.
3. Report only returned normalized entries. Do not invent missing contacts or
   claim that an empty visible result means the account has no contacts.
4. Describe messages as visible and currently loaded. Never claim that
   `read_visible_messages` or `read_contact_messages` returns complete
   server-side history.
5. A read-only timeout or transport failure may receive one bounded retry when
   application policy permits. Report partial or truncated results explicitly.

## Resolve Contacts

1. Call `open_contact` with the exact contact string.
2. On `contact_ambiguous`, present safe candidate labels when returned or ask
   the user for a more precise name. Never select a candidate implicitly.
3. On `contact_not_found`, report that no verified match was found and ask for
   a corrected name.
4. Continue to drafting, reading, or sending only after the target is verified.

## Prepare A Draft

1. Verify the target with `open_contact`.
2. Call `draft_message` with the exact requested text.
3. Report that the text is drafted, not sent.
4. Do not call `submit_draft` unless the user has explicitly changed the intent
   to send and the application authorizes that mutation.

## Send A Message

Send only when all three facts are known:

- the exact contact;
- the exact message content;
- explicit intent to send now.

Before the mutating call, use the embedding application's authorization and
confirmation mechanism. The skill itself is not authorization. If the target,
content, or intent is missing, materially inferred, or changed after
confirmation, ask the user before proceeding.

Prefer one authorized `send_message` call over manually replaying focus, draft,
and submit steps. Request post-submit verification with
`verifyAfterSubmit=true` when the registered tool exposes it. Treat that check
as bounded observation evidence, not proof of delivery or a read receipt.

After any send attempt:

1. Inspect structured `status`, `error.failureKind`, `sendAttempted`, and
   `failedPhase` fields before interpreting the summary.
2. On `submit_unknown`, `send_unverified`, `status=unknown`, transport loss
   after a possible submit, or any outcome that cannot prove no mutation
   occurred, require manual WeChat verification.
3. Never automatically replay an unknown mutating result, even when a generic
   retry flag suggests retrying.
4. Report only the level of success supported by evidence. A completed key
   press is not proof that the recipient received or read the message.

Read [references/recovery.md](references/recovery.md) before retrying or
recovering from a failed draft, submit, or send.

## Interpret Results

- Inspect structured fields before free-text summaries.
- Use normalized observation schemas and semantic fields; do not expose raw AX
  nodes, paths, values, window dumps, or coordinates.
- Treat `ok` as operation-level success only.
- Correct invalid or unsupported calls from the registered tool schema instead
  of retrying unchanged input.
- Stop for missing permissions, login requirements, or unavailable WeChat and
  tell the user which prerequisite must change.
- Keep the application in control of policy, confirmation, logging, and any
  permitted retry.
