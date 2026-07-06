# WeChat Accessibility Action API Design

Status: implementation design
Date: 2026-07-03

This document defines the next-step design for replacing raw coordinate-driven
WeChat operations with Accessibility-backed semantic actions, and for exposing
application-facing APIs that are useful to an agent.

The most important decision is that applications should not receive a raw macOS
Accessibility tree as their primary interface. They should receive a normalized
WeChat model, visible information lists, and explicit action references that can
be executed through the WeChat tool.

## Background

The current WeChat automation path can read enough macOS Accessibility data to
understand the WeChat window:

- top-level navigation items such as `AXDescription=聊天`,
  `AXDescription=通讯录`, and `AXDescription=收藏`;
- the main content split group;
- visible row nodes for contacts and conversations;
- visible message rows;
- available AX actions such as `AXPress`.

However, some execution paths still fall back to screen coordinates. This is a
problem because `macos.computer_use.click` disables raw coordinate click by
default through `allow_coordinate_click = false`.

Coordinate fallback is acceptable only as a last resort. Navigation and row
opening should prefer `AXPress` on a verified Accessibility element.

## Goals

- Add a generic macOS `accessibility_action` operation for executing AX actions
  such as `AXPress` on a verified element.
- Keep `accessibility_query` as the read-side primitive, but query only scoped
  subtrees needed by each API.
- Expose WeChat-specific models and operations instead of raw AX data.
- Make each application-facing response explain what the agent can do next.
- Preserve enough identity for follow-up actions without making raw `axPath`
  the public business identifier.
- Keep raw coordinate click disabled by default.
- Make side-effecting actions auditable through stable action IDs, risk labels,
  target summaries, and precondition checks.

## Non-Goals

- Do not expose the full Accessibility tree as the default API response.
- Do not require application code to know WeChat's AX hierarchy.
- Do not make coordinate click the normal way to switch contacts, tabs, or rows.
- Do not parse complete historical chat records. The Accessibility tree can only
  expose currently visible or loaded content.
- Do not treat every AX action as safe. The WeChat layer must still classify
  risk and validate preconditions.

## Existing Capability Summary

Current `computer-use-macos` capabilities:

- `accessibility_query`: reads scoped AX nodes and can include attributes and
  action names.
- `click` with `selector`: performs a bounded System Events click by role and
  name or index.
- `click` with `coordinates`: performs raw coordinate click only when
  `allow_coordinate_click = true`.

Pre-implementation gaps addressed by this design:

- There was no generic `accessibility_action` operation.
- `click_accessibility` was selector based, not `axPath + AXPress` based.
- WeChat `_click_node_phase` preferred coordinates when a frame existed.
- Some selector paths expose raw AX roles such as `AXRadioButton`, while the
  selector click implementation expects normalized names such as
  `radio_button`.

## Layered Design

### Layer 1: Generic macOS Capability

`computer-use-macos` owns generic desktop capabilities:

- open or focus an app;
- query Accessibility nodes;
- execute a verified Accessibility action;
- perform keyboard and clipboard text operations;
- apply safety policy and app allowlisting.

This layer must not know WeChat-specific concepts such as contacts or chats.

### Layer 2: WeChat Domain Tool

`wechat-desktop-tool` owns WeChat-specific modeling:

- classify the WeChat window;
- identify navigation, search, conversation list, contact list, message list,
  chat title, toolbar, and composer;
- expose normalized contacts, conversations, and messages;
- map WeChat action references to macOS actions;
- decide fallback order.

### Layer 3: Application/Agent API

Applications should call WeChat operations:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `read_visible_messages`
- `read_contact_messages`
- `execute_action`
- existing send-message helpers

Applications should not call raw coordinate click for normal WeChat workflows.

## Public Data Contract Principles

The application-facing contract should be stable, small, and task oriented. It
should answer two questions for an agent:

1. What useful information is visible now?
2. What explicit actions are safe and available next?

Return these normalized fields instead of raw AX attributes:

| Concept | Public Field | Notes |
|---|---|---|
| Window identity | `snapshot`, `app`, `window` | Includes freshness and current section. |
| Navigation entries | `navigation[]` | Uses stable keys such as `chats`, `contacts`, `favorites`. |
| Visible rows | `items[]` | Contacts, conversations, and messages use domain fields. |
| Executable UI affordance | `actions[]`, `actionRef` | Caller passes `actionRef` back to `execute_action`. |
| Low-level location | inside `actionRef.target` | Treated as an opaque implementation detail. |
| Diagnostics | `diagnostics` | Query count, duration, truncation, and parse confidence. |

Do not expose `attributeNames`, raw recursive `children`, or raw frame geometry
in normal responses. Those belong in debug logs or explicit diagnostic APIs. The
normal API may carry `axPath` only inside `actionRef`, because it is not a
business identifier and becomes invalid after UI changes.

All list-style APIs should keep the same response pattern:

- `schema` for versioning;
- `snapshot` for freshness;
- `items` for normalized domain data;
- `actions` or item-level `actions` for next steps;
- `pagination` when the result is partial;
- `diagnostics` for performance and confidence.

All side-effecting APIs should return:

- `status`;
- the matched target, when applicable;
- the method used;
- structured step diagnostics;
- a clear failure kind when the UI state does not match preconditions.

### API Surface Summary

| API | Read/Write | Primary Return | Main Actions Exposed | Expected Query Scope |
|---|---|---|---|---|
| `inspect_window` | Read | `wechat.window.v2` | navigation, search, composer, available operations | focused window + main content |
| `list_contacts` | Read plus possible section switch | `wechat.contacts.page.v1` | open visible contact rows | navigation + visible contact list |
| `list_conversations` | Read plus possible section switch | `wechat.conversations.page.v1` | open visible conversation rows | navigation + visible chat list |
| `open_contact` | Write current chat selection | `wechat.open_contact.v1` | follow-up read/send operations | search box + result rows + verification |
| `read_visible_messages` | Read | `wechat.messages.visible.v1` | none by default | active chat panel visible rows |
| `read_contact_messages` | Write selection, then read | `wechat.contact_messages.v1` | none by default | composed `open_contact` + read |
| `execute_action` | Depends on action | `wechat.execute_action.v1` | executes a returned `actionRef` | no tree dump; direct action resolution |

## Generic Operation: `accessibility_action`

Add a new operation to `macos.computer_use`:

```json
{
  "operation": "accessibility_action",
  "input": {
    "targetApp": "WeChat",
    "bundleId": "com.tencent.xinWeChat",
    "snapshotId": "frontmost:WeChat:微信 (聊天):...",
    "target": {
      "kind": "axPath",
      "axPath": "0/2"
    },
    "action": "AXPress",
    "preconditions": {
      "roleIn": ["AXRadioButton"],
      "labelIn": ["通讯录", "Contacts"],
      "enabled": true,
      "actionIn": ["AXPress"]
    }
  }
}
```

### Request Fields

| Field | Required | Meaning |
|---|---:|---|
| `targetApp` | No | App name used for user-facing identity and fallback lookup. |
| `bundleId` | Recommended | Bundle ID used to locate the running app precisely. |
| `snapshotId` | Recommended | Snapshot that produced the `axPath`; used as a staleness guard. |
| `target.kind` | Yes | Initial version supports `axPath`. |
| `target.axPath` | Yes | Snapshot-local AX path to the element. |
| `action` | Yes | AX action name, initially allowlisted to `AXPress`. |
| `preconditions.roleIn` | No | Accepted current AX roles. |
| `preconditions.labelIn` | No | Accepted labels from description/title/value. |
| `preconditions.enabled` | No | Expected enabled state. |
| `preconditions.actionIn` | No | Accepted available AX actions. |

### Execution Steps

1. Resolve the target app by `bundleId` first, then `targetApp`.
2. Create the AX application element with `AXUIElementCreateApplication(pid)`.
3. Resolve the focused window.
4. Traverse from the focused window to `target.axPath`.
5. Read current role, label, enabled state, frame, and action names.
6. Validate preconditions.
7. Execute `AXUIElementPerformAction(element, action)`.
8. Return structured result with timing, target facts, and error details.

### Response

```json
{
  "schema": "macos.accessibility.action.result.v1",
  "status": "ok",
  "operation": "accessibility_action",
  "method": "AXUIElementPerformAction",
  "actionAttempted": true,
  "target": {
    "axPath": "0/2",
    "role": "AXRadioButton",
    "label": "通讯录",
    "enabled": true,
    "actions": ["AXPress"]
  },
  "diagnostics": {
    "durationMs": 42,
    "verifiedPreconditions": true
  }
}
```

### Failure Kinds

| Failure Kind | Meaning | Retryable |
|---|---|---:|
| `missing_accessibility` | Accessibility permission is unavailable. | No |
| `target_app_not_running` | Target app cannot be found. | Yes |
| `focused_window_missing` | No focused window is available. | Yes |
| `snapshot_stale` | Snapshot guard failed. | Yes |
| `ax_path_not_found` | Element cannot be resolved from `axPath`. | Yes |
| `precondition_failed` | Current element does not match expected role/label/action. | Yes |
| `unsupported_accessibility_action` | Action is not allowlisted. | No |
| `accessibility_action_failed` | macOS returned a non-zero AX error. | Yes |

## Selector Click Improvements

Selector click remains useful as a fallback when a node cannot be resolved by
`axPath`.

Enhance selector normalization to accept both API names and raw AX roles:

| Input Role | Normalized Selector Role |
|---|---|
| `AXButton` | `button` |
| `AXCheckBox` | `checkbox` |
| `AXMenuItem` | `menu_item` |
| `AXRadioButton` | `radio_button` |
| `AXPopUpButton` | `pop_up_button` |
| `AXTextField` | `text_field` |
| `AXTextArea` | `text_field` or text input fallback |

Selector click should not replace `accessibility_action` for known WeChat nodes.
It is less precise because it resolves by role and name in the current front
window rather than by a previously modeled element reference.

## WeChat Action Reference

Every executable thing exposed to applications should use a WeChat action
reference. Applications pass this reference back to `wechat.execute_action`.

```json
{
  "schema": "wechat.action_ref.v1",
  "id": "nav.contacts.press",
  "kind": "navigation.switch",
  "snapshotId": "frontmost:WeChat:微信 (聊天):...",
  "preferredMethod": "accessibility_action",
  "target": {
    "axPath": "0/2",
    "role": "AXRadioButton",
    "label": "通讯录",
    "actions": ["AXPress"]
  },
  "action": "AXPress",
  "preconditions": {
    "roleIn": ["AXRadioButton"],
    "labelIn": ["通讯录", "Contacts"],
    "enabled": true,
    "actionIn": ["AXPress"]
  },
  "fallbacks": [
    {
      "method": "selector_click",
      "selector": {
        "role": "radio_button",
        "name": "通讯录"
      }
    }
  ],
  "risk": "low",
  "targetSummary": "Switch to Contacts navigation item",
  "expiresInMs": 5000
}
```

`actionRef` is intentionally not just `axPath`. It includes:

- semantic action kind;
- snapshot identity;
- target facts;
- action name;
- preconditions;
- fallback hints;
- risk metadata;
- human-readable target summary.

The WeChat tool may include coordinate fallback internally only when explicitly
enabled by configuration or when the caller accepts that fallback policy.
Coordinates should not be the normal public action contract.

## Public API: `inspect_window`

Purpose: return a fast summary of the current WeChat window and what the agent
can do next.

Suggested response schema: `wechat.window.v2`.

```json
{
  "schema": "wechat.window.v2",
  "snapshot": {
    "id": "frontmost:WeChat:微信 (聊天):...",
    "capturedAt": "2026-07-03T10:00:00Z",
    "ttlMs": 5000,
    "source": "accessibility_query"
  },
  "app": {
    "name": "WeChat",
    "bundleId": "com.tencent.xinWeChat"
  },
  "window": {
    "title": "微信 (聊天)",
    "activeSection": "chats"
  },
  "navigation": [
    {
      "id": "nav.chats",
      "key": "chats",
      "label": "聊天",
      "selected": true,
      "status": "available",
      "actionId": "nav.chats.press"
    },
    {
      "id": "nav.contacts",
      "key": "contacts",
      "label": "通讯录",
      "selected": false,
      "status": "available",
      "actionId": "nav.contacts.press"
    }
  ],
  "regions": {
    "mainContent": {
      "id": "main-content",
      "available": true
    },
    "searchBox": {
      "id": "search.focus",
      "available": true,
      "actionId": "search.focus"
    },
    "composer": {
      "id": "composer.focus",
      "available": true,
      "actionId": "composer.focus"
    }
  },
  "actions": [
    {
      "id": "nav.contacts.press",
      "kind": "navigation.switch",
      "status": "available",
      "risk": "low",
      "targetSummary": "Switch to Contacts navigation item",
      "actionRef": {
        "schema": "wechat.action_ref.v1",
        "id": "nav.contacts.press"
      }
    }
  ],
  "availableOperations": [
    {
      "id": "wechat.list_contacts",
      "status": "available",
      "risk": "changes_section"
    },
    {
      "id": "wechat.open_contact",
      "status": "needs_input",
      "risk": "changes_current_chat"
    },
    {
      "id": "wechat.read_visible_messages",
      "status": "available",
      "risk": "read_only"
    }
  ],
  "diagnostics": {
    "normalization": "ok",
    "queryCount": 2,
    "durationMs": 380,
    "truncated": false
  }
}
```

### `inspect_window` Query Strategy

1. Open or focus WeChat.
2. Query focused window children with `maxDepth=1`.
3. Detect navigation by `AXRadioButton` plus localized labels:
   - Chinese: `聊天`, `通讯录`, `收藏`;
   - English placeholders: `Chats`, `Contacts`, `Favorites`.
4. Detect the main content `AXSplitGroup`.
5. Query main content children with `maxDepth=1`.
6. Detect search box, conversation list, chat panel, and composer.
7. Build actions with `accessibility_action` references whenever nodes expose
   `AXPress`.

## Public API: `list_contacts`

Purpose: switch to Contacts if needed and return visible contact rows.

```json
{
  "schema": "wechat.contacts.page.v1",
  "section": "contacts",
  "snapshot": {
    "id": "frontmost:WeChat:微信 (聊天):...",
    "capturedAt": "2026-07-03T10:00:01Z",
    "ttlMs": 5000
  },
  "items": [
    {
      "id": "contacts.visible.0",
      "displayName": "文件传输助手",
      "subtitle": null,
      "confidence": 0.95,
      "source": "visible_ax_row",
      "actions": [
        {
          "id": "contacts.visible.0.open",
          "kind": "contact.open",
          "status": "available",
          "risk": "changes_current_chat",
          "targetSummary": "Open contact 文件传输助手",
          "actionRef": {
            "schema": "wechat.action_ref.v1",
            "id": "contacts.visible.0.open"
          }
        }
      ]
    }
  ],
  "pagination": {
    "limit": 30,
    "hasMore": "unknown",
    "nextPageToken": null
  },
  "diagnostics": {
    "switchedSection": true,
    "queryCount": 3,
    "durationMs": 650
  }
}
```

Important behavior:

- This API may change the selected WeChat section.
- It returns visible or loaded contacts only.
- It should cap rows to `limit`.
- It should expose one open action per confidently parsed row.
- It should not expose raw children for every row unless debug mode is enabled.

## Public API: `list_conversations`

Purpose: switch to Chats if needed and return visible conversation rows.

```json
{
  "schema": "wechat.conversations.page.v1",
  "section": "chats",
  "items": [
    {
      "id": "chats.visible.0",
      "displayName": "文件传输助手",
      "preview": "hello",
      "timestamp": "09:00",
      "badges": ["置顶"],
      "pinned": true,
      "muted": false,
      "confidence": 0.85,
      "source": "visible_ax_row",
      "actions": [
        {
          "id": "chats.visible.0.open",
          "kind": "conversation.open",
          "status": "available",
          "risk": "changes_current_chat",
          "actionRef": {
            "schema": "wechat.action_ref.v1",
            "id": "chats.visible.0.open"
          }
        }
      ]
    }
  ],
  "pagination": {
    "limit": 30,
    "hasMore": "unknown",
    "nextPageToken": null
  }
}
```

## Public API: `open_contact`

Purpose: search or select a contact/conversation and make it the active chat.

Input:

```json
{
  "contact": "文件传输助手",
  "matchMode": "exact_or_best",
  "allowDisambiguation": true
}
```

Response:

```json
{
  "schema": "wechat.open_contact.v1",
  "status": "ok",
  "contact": {
    "requested": "文件传输助手",
    "matched": "文件传输助手",
    "confidence": 0.95
  },
  "chat": {
    "title": "文件传输助手",
    "active": true
  },
  "actions": [
    {
      "id": "wechat.read_visible_messages",
      "kind": "wechat_operation",
      "status": "available",
      "risk": "read_only"
    }
  ],
  "diagnostics": {
    "method": "search_result_axpress",
    "queryCount": 4,
    "durationMs": 900
  }
}
```

If multiple matches are found:

```json
{
  "schema": "wechat.open_contact.v1",
  "status": "needs_disambiguation",
  "candidates": [
    {
      "id": "search.result.0",
      "displayName": "文件传输助手",
      "confidence": 0.92,
      "actionId": "search.result.0.open"
    }
  ]
}
```

## Public API: `read_visible_messages`

Purpose: return normalized visible messages in the current chat.

```json
{
  "schema": "wechat.messages.visible.v1",
  "chat": {
    "title": "文件传输助手",
    "confidence": 0.9
  },
  "messages": [
    {
      "id": "messages.visible.0",
      "kind": "text",
      "direction": "incoming",
      "sender": null,
      "text": "hello",
      "timestamp": null,
      "confidence": 0.8,
      "source": "visible_ax_row"
    }
  ],
  "pagination": {
    "visibleOnly": true,
    "limit": 30,
    "canLoadOlder": "unknown"
  },
  "diagnostics": {
    "queryCount": 2,
    "durationMs": 420
  }
}
```

Message parsing should be conservative. If direction, sender, or timestamp
cannot be proven from Accessibility data, return `unknown` or `null` rather
than inventing values.

## Public API: `read_contact_messages`

Purpose: compose `open_contact` and `read_visible_messages`.

```json
{
  "schema": "wechat.contact_messages.v1",
  "contact": {
    "requested": "文件传输助手",
    "matched": "文件传输助手"
  },
  "messages": [],
  "steps": {
    "openContact": {
      "status": "ok"
    },
    "readVisibleMessages": {
      "status": "ok"
    }
  }
}
```

This API is useful for application tests, but lower-level APIs should remain
available so agents can reason step by step.

## Public API: `execute_action`

Purpose: execute an action reference returned by another WeChat API.

Input:

```json
{
  "actionRef": {
    "schema": "wechat.action_ref.v1",
    "id": "nav.contacts.press",
    "snapshotId": "frontmost:WeChat:微信 (聊天):...",
    "preferredMethod": "accessibility_action",
    "target": {
      "axPath": "0/2",
      "role": "AXRadioButton",
      "label": "通讯录"
    },
    "action": "AXPress",
    "preconditions": {
      "roleIn": ["AXRadioButton"],
      "labelIn": ["通讯录", "Contacts"],
      "actionIn": ["AXPress"]
    }
  }
}
```

Response:

```json
{
  "schema": "wechat.execute_action.v1",
  "status": "ok",
  "actionId": "nav.contacts.press",
  "method": "accessibility_action",
  "result": {
    "schema": "macos.accessibility.action.result.v1",
    "status": "ok"
  }
}
```

Execution priority:

1. `accessibility_action` when `actionRef.target.axPath` and `AXPress` are
   present.
2. `selector_click` when a role and label can be normalized.
3. coordinate fallback only when explicitly allowed by policy/configuration.

## Safety and Policy

- Raw coordinate click remains disabled by default.
- `accessibility_action` should allowlist safe AX actions. Initial allowlist:
  `AXPress`.
- WeChat actions must include risk labels:
  - `read_only`
  - `low`
  - `changes_section`
  - `changes_current_chat`
  - `types_text`
  - `sends_message`
  - `may_open_panel`
- Message sending remains a higher-risk operation and should keep the existing
  explicit send-message flow.
- Precondition failures should block execution instead of silently clicking a
  different UI element.

## Performance Strategy

Do not dump the full tree for normal APIs.

Recommended query budgets:

| API | Query Pattern | Target Duration |
|---|---|---:|
| `inspect_window` | focused window children + main content children | 200-500 ms |
| `list_contacts` | inspect + switch if needed + rows under main content | 500-1000 ms |
| `list_conversations` | inspect + switch if needed + rows under main content | 500-1000 ms |
| `open_contact` | inspect + search focus + search results + verification | 800-1500 ms |
| `read_visible_messages` | chat panel + visible rows | 300-800 ms |

Implementation notes:

- Use `maxDepth=1` for fixed regions.
- Use role filters for rows and text nodes.
- Include `actions=true` only when action construction is needed.
- Keep per-query `timeBudgetMs` small.
- Cache snapshot-local action references only for a short TTL.
- Treat `axPath` as invalid after major UI changes such as switching tabs,
  opening another contact, or search result selection.

## Testing Plan

### Unit Tests With Fake App-Control Service

Each public WeChat API should have at least one fake-service test:

- `inspect_window`: returns navigation, regions, and action references.
- `list_contacts`: switches to contacts via `accessibility_action`, then returns
  visible contact rows.
- `list_conversations`: switches to chats via `accessibility_action`, then
  returns visible conversation rows.
- `open_contact`: focuses search, types query, opens a result, verifies chat
  title.
- `read_visible_messages`: parses visible message rows conservatively.
- `execute_action`: prefers `accessibility_action` and falls back only when
  configured.

The fake app-control service should return shaped Accessibility query payloads,
not full fixture dumps. Each fixture should include only the nodes needed for the
API under test:

| Test Fixture | Required Fake macOS Data | Contract Assertions |
|---|---|---|
| Navigation fixture | `AXRadioButton` nodes with `AXDescription` for chats, contacts, favorites, selected state, and `AXPress`. | `navigation[]` has stable keys, localized labels, selected state, and `actionRef`. |
| Main content fixture | `AXSplitGroup` plus shallow children for search, list, chat panel, and composer. | `regions` and `availableOperations` are present without exposing raw `attributeNames`. |
| Contact rows fixture | visible `AXRow` nodes with display names and `AXPress`. | `items[].displayName`, confidence, pagination, and open `actionRef` are populated. |
| Conversation rows fixture | visible `AXRow` nodes with title, preview, timestamp, badge text, and `AXPress`. | preview metadata is best-effort and no raw recursive tree is returned. |
| Message rows fixture | visible text/message rows with ambiguous metadata. | unknown sender/direction/timestamp remain `null` or `unknown` instead of invented. |
| Action failure fixture | `accessibility_action` failures such as stale path or precondition mismatch. | `execute_action` returns structured failure or uses only allowed fallback. |

Tests should assert the exact app-control operation sequence. For example,
`list_contacts` should call `accessibility_query`, then
`accessibility_action` when switching to Contacts, then a scoped
`accessibility_query` for rows. It should not call coordinate click unless a
test explicitly enables coordinate fallback.

### Generic `computer-use-macos` Tests

- `accessibility_action` builds and handles the command.
- missing Accessibility permission returns `missing_accessibility`.
- unsupported action returns `unsupported_accessibility_action`.
- precondition mismatch returns `precondition_failed`.
- stale or missing `axPath` returns a structured failure.

### Real Example Tests

Add examples that can run against local WeChat:

- inspect window and write `wechat-window-inspect.json`;
- list contacts and write `wechat-contacts.json`;
- switch to File Transfer Assistant and send a test message;
- read recent visible messages for selected contacts.

Real examples should write JSON result files and include enough diagnostics to
debug which query or action failed.

## Migration Plan

1. Add `ComputerUseOperation.ACCESSIBILITY_ACTION`.
2. Add protocol command builder: `accessibility_action_command`.
3. Implement direct backend with PyObjC:
   - resolve target app;
   - resolve focused window;
   - traverse `axPath`;
   - validate preconditions;
   - call `AXUIElementPerformAction`.
4. Implement helper backend support or return a clear unsupported failure until
   the helper template is updated.
5. Enhance selector normalization to accept raw AX roles.
6. Change WeChat `_click_node_phase` to:
   - prefer `AXPress` through `accessibility_action`;
   - then selector click;
   - then coordinate fallback only if allowed.
7. Add `actionRef` to `inspect_window`, `list_contacts`, and
   `list_conversations`.
8. Add `execute_action`.
9. Update API docs and examples.
10. Run unit tests and real smoke tests.

## Compatibility

Existing operations can continue to work:

- `focus_contact`
- `draft_message`
- `submit_draft`
- `send_message`

They should gradually migrate from keyboard/search-only flows to the new
read-model and action-ref flow where practical.

Existing `inspect_window` callers should remain compatible if `wechat.window.v1`
fields are kept during a transition. New fields can be added under:

- `snapshot`
- `actions`
- `availableOperations`
- `diagnostics`

## Open Questions

- Whether helper backend should support `accessibility_action` immediately or
  initially return `unsupported_operation`.
- How long `snapshotId` should remain valid in practice.
- Whether row `AXPress` works reliably for every visible WeChat contact and
  conversation row.
- Whether English WeChat labels should be confirmed from a real English client
  instead of placeholders.
- Whether pagination should scroll internally or remain visible-row only in the
  first version.
