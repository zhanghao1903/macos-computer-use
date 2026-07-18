# WeChat Semantic Operations

Use this reference to map Agent intent to the stable operations already exposed
by `wechat-desktop-tool`. The application may expose one generic
`wechat.desktop` tool with `operation` and `input`, or separate operation
wrappers. Follow the registered tool schema when field casing differs.

## Result Envelope

Read structured result fields before `summary` text:

| Field | Meaning |
| --- | --- |
| `success` | Whether the operation reports success. |
| `status` | Stable status such as `ok`, `not_found`, `not_ready`, `permission_missing`, `timeout`, `failed`, or `unknown`. |
| `observation` | Normalized operation-specific data. |
| `error.failureKind` | Stable package failure used for recovery routing. |
| `error.retryable` | A hint, never permission to replay a possibly completed mutation. |
| `diagnostics` | Privacy-safe details for application logs and recovery. |

Do not infer stronger facts from `summary` than structured fields support.

## Operation Table

| Operation | Protocol input | Python method | Normalized result or key fields |
| --- | --- | --- | --- |
| `open_wechat` | `{}` | `open_wechat()` | Verified WeChat foreground environment. |
| `inspect_window` | `includeRaw=false`, optional `includeActionables` | `inspect_window(include_raw=False, include_actionables=True)` | `wechat.window.v1`. |
| `list_contacts` | `limit` up to 30; omit `pageToken` | `list_contacts(limit=30)` | `wechat.contacts.v1`. |
| `list_conversations` | `limit` up to 30; omit `pageToken` | `list_conversations(limit=30)` | `wechat.conversations.v1`. |
| `open_contact` | exact `contact` | `open_contact(contact)` | `wechat.open_contact.v1` with verified target or candidates. |
| `read_visible_messages` | `limit` up to 30 | `read_visible_messages(limit=30)` | `wechat.messages.v1`. |
| `read_contact_messages` | exact `contact`, `limit` up to 30 | `read_contact_messages(contact, limit=30)` | `wechat.contact_messages.v1`. |
| `draft_message` | exact `message` | `draft_message(message)` | Draft readiness; never evidence of send. |
| `submit_draft` | optional `method` | `submit_draft(method="keyboard_return")` | Submit attempt fields; mutating. |
| `send_message` | `contact`, `message`, optional `verifyAfterSubmit=true`, optional `verifyLimit` | `send_message(contact=..., message=..., verify_after_submit=True)` | Focus/draft/submit outcome and optional bounded verification. |

## Inspect And Lists

- Keep `includeRaw` false. Normalized navigation, region, conversation, contact,
  message, and action data is the Agent contract.
- `list_contacts` returns visible contact rows. Continuation tokens are not
  supported in the current contract.
- `list_conversations` returns visible recent-chat rows, not the address book.
- Treat empty results, truncation, and failed collection queries as observed UI
  state, not proof that no data exists.

## Contact And Message Reads

- Use `open_contact` for an exact target. Do not choose among ambiguous results.
- Use `read_contact_messages` when the target must be opened before reading.
- Use `read_visible_messages` only when the intended chat is already verified
  as current.
- Both message operations return visible, currently loaded messages. They are
  not a server-side export and do not guarantee the requested count exists.
- Keep requested limits bounded to 30 or fewer.

## Draft And Send

- Use `draft_message` only for unsent preparation after the contact is verified.
- Use `submit_draft` only when an existing draft, target, and explicit send
  intent are all authorized.
- Prefer `send_message` for one authorized exact-contact/exact-content send.
- Enable bounded post-submit verification when available, but do not equate
  visible text with delivery or a read receipt.
- Never retry a possibly completed mutation without structured proof that no
  submit attempt occurred. See [recovery.md](recovery.md).

## Compatibility Operations

`focus_contact` remains available as a compatibility wrapper around verified
contact opening. Prefer `open_contact` in new Agent workflows.

`execute_action` accepts a fresh `wechat.action_ref.v1` returned by normalized
operations. Use it only when the intended semantic continuation has no named
operation and the reference still belongs to the current window snapshot.
