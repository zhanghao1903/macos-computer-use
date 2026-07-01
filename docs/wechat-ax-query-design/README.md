# WeChat AX Query Technical Design

This document describes the next-step design for the WeChat desktop toolkit.
The core change is to stop collecting a full Accessibility tree first and then
parsing it locally. Instead, `computer-use-macos` should expose targeted
Accessibility queries, and `wechat-desktop-tool` should compose those queries
into clear application-facing APIs.

The raw reference sample is `examples/window.json.bak`. It is useful for
understanding WeChat's macOS Accessibility shape, but it is not the public API.

## Background

The current `inspect_window` path asks `macos.computer_use.observe` for
`includeAccessibilityTree=true`. That creates a focused-window tree dump, then
the WeChat layer normalizes the returned tree.

This has three problems:

- Performance is bounded by full-tree collection, not by what the caller needs.
- A partial failure in tree collection can remove all useful WeChat context.
- The public API risks drifting toward raw AX data instead of clean action and
  information lists.

The target design is:

```text
application
  -> wechat-desktop-tool semantic API
     -> computer-use-macos accessibility_query
        -> targeted macOS AX reads
```

## Goals

- Expose clear WeChat-specific information and action lists to applications.
- Support fast `inspect_window` by querying only top-level controls and key
  regions.
- Add APIs for contact list, contact switching, visible chat messages, and
  contact message reading.
- Preserve enough element identity for follow-up actions without exposing raw
  `attributeNames` or full AX trees.
- Keep predictable performance through limits, time budgets, pagination, and
  scoped queries.

## Non-Goals

- Do not expose full raw AX trees as the normal application contract.
- Do not guarantee full historical chat export. macOS AX normally exposes
  visible or loaded rows, not the complete database.
- Do not make application callers reason about WeChat AX paths such as
  `0/11/1/0/N`.
- Do not execute risky actions implicitly during read-only list APIs.

## Reference AX Shape

Important nodes observed in `examples/window.json.bak`:

```text
0
  AXWindow

0/1  AXRadioButton  AXDescription: 聊天   -> chats
0/2  AXRadioButton  AXDescription: 通讯录 -> contacts
0/3  AXRadioButton  AXDescription: 收藏   -> favorites
0/11 AXSplitGroup   main content area

0/11/0 AXTextArea   search box
0/11/1 AXScrollArea conversation list
0/11/2 AXButton     start group chat
0/11/4 AXSplitGroup chat panel

0/11/1/0     AXTable conversation rows
0/11/1/0/N   AXRow
0/11/1/0/N/0 AXCell row label/preview/timestamp/badges

0/11/4/0  AXScrollArea message list viewport
0/11/4/2  AXStaticText current chat title
0/11/4/11 AXScrollArea composer viewport
0/11/4/11/0 AXTextArea draft input
```

Paths are snapshot-local hints. Fixed controls must still be validated by
roles, descriptions, values, actions, and frame relationships.

## Upstream API: `accessibility_query`

Add a generic operation to `macos.computer_use`:

```text
tool: macos.computer_use
operation: accessibility_query
```

Example input:

```json
{
  "targetApp": "WeChat",
  "bundleId": "com.tencent.xinWeChat",
  "root": {"kind": "focusedWindow"},
  "query": {
    "scope": "children",
    "maxDepth": 1,
    "limit": 50,
    "timeBudgetMs": 500,
    "attributes": [
      "AXRole",
      "AXSubrole",
      "AXTitle",
      "AXValue",
      "AXDescription",
      "AXEnabled",
      "AXFocused",
      "AXPosition",
      "AXSize",
      "AXFrame"
    ],
    "actions": true,
    "match": {
      "roleIn": ["AXRadioButton", "AXSplitGroup", "AXTextArea", "AXScrollArea"]
    }
  }
}
```

Example output:

```json
{
  "schema": "macos.accessibility.query.v1",
  "snapshotId": "frontmost:WeChat:微信 (聊天):...",
  "app": {
    "name": "WeChat",
    "bundleId": "com.tencent.xinWeChat",
    "pid": 60088
  },
  "window": {
    "title": "微信 (聊天)",
    "role": "AXWindow"
  },
  "nodes": [
    {
      "axPath": "0/2",
      "role": "AXRadioButton",
      "description": "通讯录",
      "value": 0,
      "frame": {"x": 268, "y": 207, "width": 62, "height": 34},
      "actions": ["AXPress"],
      "enabled": true,
      "focused": false
    }
  ],
  "diagnostics": {
    "durationMs": 180,
    "truncated": false,
    "nodeCount": 15
  }
}
```

### Query Root

Supported roots:

- `{"kind": "focusedWindow"}`: currently focused window of the target app.
- `{"kind": "axPath", "snapshotId": "...", "axPath": "0/11"}`: a node from a
  previous snapshot.
- `{"kind": "semantic", "name": "mainContent"}`: optional future shortcut owned
  by `wechat-desktop-tool`, not required in the generic layer.

`axPath` is valid only for the snapshot that produced it. The caller must pass
`snapshotId` when using `axPath`.

### Query Scope

Supported scopes:

- `self`: return only the root node.
- `children`: return direct children.
- `descendants`: bounded recursive search. Requires `maxDepth`, `limit`, and
  `timeBudgetMs`.

Default behavior should be conservative:

- `maxDepth`: 1 for `children`, required for `descendants`.
- `limit`: 50.
- `timeBudgetMs`: 500 for lightweight queries, 1500 for list queries.
- `attributes`: safe allowlist only.
- `actions`: false unless requested.

### Match Filters

Initial filters:

- `role`
- `roleIn`
- `description`
- `descriptionIn`
- `descriptionContains`
- `titleContains`
- `valueEquals`
- `enabled`
- `focused`

Filters are applied while traversing. Nodes that do not match are not returned,
but traversal may continue through them when `scope=descendants`.

### Output Node Shape

Normalize AX names before returning:

```json
{
  "axPath": "0/11/1",
  "role": "AXScrollArea",
  "subrole": null,
  "title": null,
  "description": "搜索",
  "value": "",
  "frame": {},
  "actions": ["AXPress"],
  "enabled": true,
  "focused": false,
  "childrenCount": 1
}
```

Do not expose `attributeNames` in normal query output. Raw debug output can
exist behind an explicit `includeRaw=true`.

### Query Engine

The current implementation starts a Python subprocess for the tree snapshot.
That is acceptable for a first version of `accessibility_query`, but the target
implementation should use one of these:

- A long-lived in-process `AXQueryEngine` inside `computer-use-macos serve`.
- A long-lived worker subprocess if PyObjC isolation is needed.

The engine must:

- Locate the target process by `bundleId`, not by a second frontmost lookup.
- Resolve focused window once per query.
- Traverse only the requested scope.
- Read only requested safe attributes.
- Stop on `limit` or `timeBudgetMs`.
- Return partial data with `diagnostics.truncated=true` instead of timing out
  and returning no data.

## Optional Upstream API: `accessibility_action`

Most clicks can continue using the existing `click` operation with coordinates
or selectors. For elements that expose stable AX actions, add a small action
operation later:

```json
{
  "operation": "accessibility_action",
  "input": {
    "bundleId": "com.tencent.xinWeChat",
    "snapshotId": "...",
    "axPath": "0/2",
    "action": "AXPress"
  }
}
```

This allows WeChat navigation and visible rows to use `AXPress` when available,
with coordinate fallback only when required.

## WeChat Public APIs

`wechat-desktop-tool` should expose semantic operations. The application should
receive clean operation results, not AX trees.

Planned operations:

- `inspect_window`
- `list_contacts`
- `list_conversations`
- `open_contact`
- `read_visible_messages`
- `read_contact_messages`

Existing operations such as `draft_message`, `submit_draft`, and
`send_message` can continue to build on these primitives.

## API: `inspect_window`

Purpose: fast current-window summary and action menu.

Target flow:

1. Open or focus WeChat.
2. `accessibility_query(root=focusedWindow, scope=children, maxDepth=1)`.
3. Classify direct children:
   - `AXRadioButton + AXDescription=聊天` -> `nav.chats`
   - `AXRadioButton + AXDescription=通讯录` -> `nav.contacts`
   - `AXRadioButton + AXDescription=收藏` -> `nav.favorites`
   - largest/right-side `AXSplitGroup` -> `regions.mainContent`
4. Optionally query `mainContent.children` with `maxDepth=1` to detect
   `searchBox`, `conversationList`, and `chatPanel` availability.

Expected performance: 200-500 ms with a long-lived query engine.

Example output:

```json
{
  "schema": "wechat.window.v2",
  "appName": "WeChat",
  "bundleId": "com.tencent.xinWeChat",
  "title": "微信 (聊天)",
  "activeSection": "chats",
  "navigation": [
    {
      "id": "nav.chats",
      "label": "chats",
      "selected": true,
      "actionId": "nav.chats.press"
    },
    {
      "id": "nav.contacts",
      "label": "contacts",
      "selected": false,
      "actionId": "nav.contacts.press"
    }
  ],
  "regions": {
    "mainContent": {"id": "main-content", "available": true},
    "searchBox": {"id": "search.focus", "available": true}
  },
  "availableActions": [
    {"id": "wechat.list_contacts", "status": "available"},
    {"id": "wechat.open_contact", "status": "needs_input"},
    {"id": "wechat.read_visible_messages", "status": "available"}
  ]
}
```

## API: `list_contacts`

Purpose: return a visible page of contacts. Default limit: 30.

Input:

```json
{
  "limit": 30,
  "pageToken": null
}
```

Flow:

1. Ensure WeChat is open.
2. Query navigation. If contacts is not selected, press `nav.contacts`.
3. Query `mainContent.children` and locate the contacts list region.
4. Query only visible row nodes in the list region, limited by `limit`.
5. Parse each row into a contact item.
6. Return an opaque page token when scrolling can continue.

Output:

```json
{
  "schema": "wechat.contacts.v1",
  "section": "contacts",
  "items": [
    {
      "id": "contact.visible.0",
      "displayName": "张三",
      "kind": "contact",
      "actionId": "contact.visible.0.open",
      "confidence": 0.9
    }
  ],
  "pagination": {
    "limit": 30,
    "hasMore": true,
    "nextPageToken": "opaque-scroll-token"
  },
  "availableActions": [
    {"id": "wechat.open_contact", "status": "needs_input"},
    {"id": "wechat.contacts.next_page", "status": "available"}
  ]
}
```

Pagination should be scroll-based, not offset-based. WeChat may expose only
visible or loaded rows through AX. `pageToken` should encode enough internal
state to scroll the same region and re-query the next page, but it must not be
a public AX path contract.

## API: `list_conversations`

Purpose: return visible conversation rows from the chat section.

Flow is similar to `list_contacts`, but it switches to `nav.chats` and reads the
conversation list region:

```text
mainContent -> AXScrollArea -> AXTable -> AXRow -> AXCell
```

Output item fields:

- `displayName`
- `preview`
- `timestamp`
- `badges`
- `pinned`
- `muted`
- `actionId`

Expected performance: 500-1200 ms.

## API: `open_contact`

Purpose: switch WeChat to a target contact or conversation.

Input:

```json
{
  "contact": "张三",
  "strategy": "search"
}
```

Default flow:

1. Open or focus WeChat.
2. Locate and focus the search box with AX query. Fallback to configured
   search hotkey.
3. Insert the contact name using clipboard paste, not keyboard typing, to avoid
   IME issues.
4. Wait for search results.
5. Query visible result rows.
6. If exactly one confident match exists, open it using `AXPress` or click
   fallback.
7. Verify chat panel title equals or strongly matches the target.

Output:

```json
{
  "schema": "wechat.open_contact.v1",
  "target": "张三",
  "status": "opened",
  "currentChat": {
    "title": "张三"
  },
  "availableActions": [
    {"id": "wechat.read_visible_messages", "status": "available"},
    {"id": "wechat.draft_message", "status": "needs_input"}
  ]
}
```

Ambiguous result:

```json
{
  "schema": "wechat.open_contact.v1",
  "target": "张三",
  "status": "needs_disambiguation",
  "candidates": [
    {
      "id": "search.result.0",
      "displayName": "张三",
      "actionId": "search.result.0.open"
    }
  ]
}
```

Expected performance: 1500-3000 ms.

## API: `read_visible_messages`

Purpose: read visible or loaded message rows in the current chat.

Input:

```json
{
  "limit": 30,
  "pageToken": null
}
```

Flow:

1. Query `mainContent.children` and locate the chat panel.
2. Query the chat panel's message list region:
   `AXScrollArea -> AXTable -> AXRow`.
3. Filter rows by viewport intersection.
4. Extract message text from `AXCell`, `AXStaticText`, `AXDescription`, or
   `AXValue`.
5. Return visible rows and an older-page token when scroll-up is possible.

Output:

```json
{
  "schema": "wechat.messages.v1",
  "chat": {
    "title": "张三"
  },
  "messages": [
    {
      "id": "message.visible.0",
      "direction": "unknown",
      "text": "你好",
      "timestamp": null,
      "visible": true
    }
  ],
  "pagination": {
    "limit": 30,
    "canReadOlder": true,
    "olderPageToken": "opaque-scroll-up-token"
  }
}
```

Expected performance: 600-1500 ms.

## API: `read_contact_messages`

Purpose: open a contact and then read visible messages.

Flow:

```text
open_contact(contact)
read_visible_messages(limit)
```

This should return both the contact-opening result and message list diagnostics
so the caller can tell whether failure happened during navigation or reading.

Expected performance: 2500-4500 ms.

## Performance Budget

Target budgets with a long-lived AX query engine:

| Operation | Target | Notes |
| --- | ---: | --- |
| `inspect_window` | 200-500 ms | top-level children plus optional main-content children |
| `list_contacts` | 500-1200 ms | visible page only |
| `list_conversations` | 500-1200 ms | visible page only |
| `open_contact` | 1500-3000 ms | includes search input and verification |
| `read_visible_messages` | 600-1500 ms | visible rows only |
| `read_contact_messages` | 2500-4500 ms | composed operation |

Current full-tree `inspect_window` can be around 1.8-2.2 seconds when it works
and can hit 15 seconds in timeout cases. The new design should make full-tree
dump a debug path only.

## Error Handling

Common failure kinds:

- `missing_accessibility`: macOS Accessibility permission is not available.
- `target_app_not_running`: WeChat is not running and cannot be opened.
- `target_app_not_frontmost`: WeChat could not be focused when required.
- `query_timeout`: query exceeded `timeBudgetMs`; partial results may exist.
- `query_truncated`: `limit` or traversal budget stopped the query.
- `wechat_logged_out`: WeChat shows login-required UI.
- `contact_not_found`: search or visible list did not find the contact.
- `needs_disambiguation`: multiple search results matched.
- `message_region_not_found`: current window does not expose a chat panel.

Every semantic API should return `availableActions` where useful. A blocked
diagnostic action is better than an empty action list when recovery is possible.

## Privacy And Logging

- Normal API responses should not include raw AX trees or `attributeNames`.
- `includeRaw=true` should be explicit and intended for debugging only.
- Message and contact text may be private; rawdata logs should be configurable
  and off or redacted by default for application integrators.
- Clipboard-based input should restore the previous clipboard when possible.

## Implementation Plan

1. Add `macos.computer_use/accessibility_query` command model, CLI plumbing, and
   service protocol support.
2. Implement a subprocess-based first version of `AXQueryEngine` using scoped
   traversal, safe attribute reads, match filters, limits, and time budgets.
3. Convert `wechat.inspect_window` to use scoped queries instead of full tree
   dump.
4. Add tests around navigation extraction from top-level children and no
   `attributeNames` exposure.
5. Implement `wechat.list_conversations`.
6. Implement `wechat.list_contacts` with visible-page support and scroll-based
   page tokens.
7. Implement `wechat.open_contact` using search, clipboard paste, candidate
   matching, and chat-title verification.
8. Implement `wechat.read_visible_messages` and `wechat.read_contact_messages`.
9. Replace per-query subprocess startup with a long-lived engine or worker.
10. Add performance metrics to every phase: open/focus, query, parse, action,
    verify.

## Test Strategy

All WeChat semantic APIs must be tested with stubs before they are validated
against a real WeChat client. This follows the existing `inspect_window` test
style: the WeChat layer receives deterministic fake `macos.computer_use`
observations or fake `accessibility_query` results, then the test asserts the
normalized public response.

Each public API must have at least one dedicated test case. Shared fixtures are
allowed, but one broad end-to-end test is not enough.

- Unit tests for query request validation and output normalization.
- Fixture tests using `examples/window.json.bak` for WeChat locator behavior.
- Fake AX tree tests for contact list pagination and message row parsing.
- Integration example that opens WeChat, calls each read-only API, and writes
  JSON output.
- Smoke tests for `open_contact` against File Transfer or a configured safe
  test contact.
- Performance assertions in examples: log per-phase duration and warn when
  `inspect_window` exceeds 1 second after the scoped-query migration.

### Required Stub Test Cases

| API | Minimum stub test |
| --- | --- |
| `inspect_window` | Fake top-level focused-window children include `AXRadioButton` navigation nodes and `AXSplitGroup` main content. Assert `navigation`, `regions`, and `availableActions` are returned without raw `attributeNames`. |
| `list_contacts` | Fake contacts navigation plus visible contact rows. Assert the first page returns at most `limit` items, includes stable `actionId`s, and returns pagination metadata. |
| `list_conversations` | Fake chats navigation plus visible conversation rows. Assert display name, preview, timestamp, badges, pinned/muted flags, and row open actions are normalized. |
| `open_contact` | Fake search-box focus, search result rows, row open action, and chat-title verification. Assert success for one exact match and `needs_disambiguation` for multiple matches. |
| `read_visible_messages` | Fake chat panel and message-list rows. Assert visible filtering, text extraction, chat title, and older-page token behavior. |
| `read_contact_messages` | Compose fake `open_contact` success with fake `read_visible_messages`. Assert the response reports both navigation and message-read phases. |

### Stub Design

Tests should use a fake app-control client rather than launching WeChat. The fake
client records commands and returns planned observations per phase.

Recommended fixtures:

- `focused_window_top_level`: focused window children containing navigation and
  main content candidates.
- `main_content_children`: search box, conversation/contact list region, and
  chat panel candidates.
- `contact_rows_page_1`: visible contacts with more pages available.
- `conversation_rows_page_1`: visible chats with preview and badges.
- `search_results_single_match`: one exact contact result.
- `search_results_multiple_matches`: ambiguous contact results.
- `message_rows_visible`: visible message rows inside a message-list viewport.

Each stub test should assert both:

- The app-control commands sent by `wechat-desktop-tool`, including operation
  names and scoped-query inputs.
- The public WeChat response shape returned to applications.

## Open Questions

- Whether WeChat exposes enough contact-list rows in contacts mode for reliable
  scroll pagination across versions.
- Whether search result row semantics differ between Chinese and English UI.
- Whether `AXPress` works reliably on contact/conversation rows, or coordinate
  fallback remains necessary.
- Whether the long-lived AX engine should live in the service process or a
  dedicated worker process for isolation.
