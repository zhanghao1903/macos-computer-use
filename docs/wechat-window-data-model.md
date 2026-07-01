# WeChat Window Data Model

This document defines the first-pass data model for projecting a raw macOS
Accessibility element tree into a WeChat-specific window model.

The source sample is `examples/window.json.bak`. That file is useful as raw
debug evidence, but it is not the application-facing contract. The application
contract should expose only the normalized data that an agent needs to reason
about the current WeChat window and perform bounded follow-up actions.

## Goals

- Preserve enough element identity to click, scroll, or focus a target later.
- Reduce the raw AX tree into WeChat concepts: navigation, search,
  conversation list, chat panel, message list, toolbar, and composer.
- Keep the model stable across WeChat layout changes by relying on role,
  label, frame, and hierarchy together, not a single hard-coded path.
- Keep raw private data out of normal logs and responses unless the caller
  explicitly asks for raw debug output.

## Non-Goals

- Do not expose the full AX tree as the main agent interface.
- Do not parse the complete historical chat record. The AX tree only contains
  visible or loaded rows.
- Do not treat every AX action as safe to execute. The model describes
  actionable regions; policy and confirmation still belong to the caller.
- Do not make row parsing depend on one exact WeChat version or one exact path.

## Raw Tree Shape

The sample has this top-level shape:

```json
{
  "app": {
    "name": "WeChat app name",
    "bundle_id": "com.tencent.xinWeChat",
    "pid": 60088
  },
  "focused_window": {
    "path": "0",
    "AXRole": "AXWindow",
    "AXTitle": "WeChat window title",
    "children": []
  }
}
```

Each AX node may contain:

- `path`: stable within one snapshot, used to locate the same node inside that
  snapshot.
- `attribute_names`: names returned by `AXUIElementCopyAttributeNames`.
- `AXRole`, `AXSubrole`, `AXTitle`, `AXDescription`, `AXValue`.
- `AXPosition`, `AXSize`, or `AXFrame`.
- `actions`: actions returned by `AXUIElementCopyActionNames`.
- `children_count` and `children`.

The raw attributes are dynamic. The dumper should read attribute names at
runtime instead of maintaining a hand-written complete attribute list.

## Layer Samples

The following samples show the important parts of `window.json.bak` without
copying the whole private tree.

Top window:

```text
0
  role: AXWindow
  title: WeChat window title
  frame: whole WeChat window
  actions: AXRaise
```

Primary children under the window:

```text
0/1  AXRadioButton  AXDescription: 聊天   -> chats     selected: true   action: AXPress
0/2  AXRadioButton  AXDescription: 通讯录 -> contacts  selected: false  action: AXPress
0/3  AXRadioButton  AXDescription: 收藏   -> favorites selected: false  action: AXPress
0/11 AXSplitGroup   main content area
```

Main content split group:

```text
0/11/0 AXTextArea   search box
0/11/1 AXScrollArea conversation list
0/11/2 AXButton     start group chat
0/11/4 AXSplitGroup chat panel
```

Conversation list:

```text
0/11/1       AXScrollArea  conversation list viewport
0/11/1/0     AXTable       conversation rows
0/11/1/0/N   AXRow         one row frame
0/11/1/0/N/0 AXCell        row label/preview/timestamp/badges
```

Chat panel:

```text
0/11/4/0  AXScrollArea  message list viewport
0/11/4/2  AXStaticText  current chat title
0/11/4/4  AXButton      emoji
0/11/4/5  AXButton      screenshot
0/11/4/7  AXButton      search chat content
0/11/4/10 AXButton      attachment
0/11/4/11 AXScrollArea  composer viewport
```

Composer:

```text
0/11/4/11/0 AXTextArea draft text input
```

## Locator Strategy

AX paths and child indexes are useful for explaining the sample tree and for
referring back to an element within one snapshot. They should not be the only
way to identify fixed WeChat elements.

Use this order when locating semantic regions:

1. Generate candidates from coarse hierarchy and geometry.
2. Verify candidates with AX semantics such as `AXRole`, `AXDescription`,
   `AXTitle`, `AXValue`, selected/focused flags, and available actions.
3. Use frame relationships to reject lookalikes, for example top search input
   versus bottom composer input.
4. Store the chosen node's `axPath` only after the semantic match succeeds.

For fixed controls, the semantic check is mandatory. For example, the search
box can be near `0/11/0` in the current sample, but the parser should verify
that the candidate is a text input whose label or description is search-like
before classifying it as `searchBox`.

### Navigation Locators

The top-level navigation entries are direct children of the focused window in
the current WeChat app structure. That level is stable enough to use as the
candidate scope, but the final match should be based on `AXDescription`.

The parser should scan the focused window's direct children and classify
navigation candidates with this priority:

1. `AXRole == "AXRadioButton"`.
2. `AXDescription` matches one of the known localized labels.
3. `AXValue` determines the selected state.
4. `actions` containing `AXPress` raises confidence, but absence of `AXPress`
   should not by itself remove a semantically matched item.

Localized navigation labels:

| Semantic key | Chinese `AXDescription` | English placeholder |
| --- | --- | --- |
| `chats` | `聊天` | `__EN_CHATS_PLACEHOLDER__` |
| `contacts` | `通讯录` | `__EN_CONTACTS_PLACEHOLDER__` |
| `favorites` | `收藏` | `__EN_FAVORITES_PLACEHOLDER__` |

For example, locating the contacts tab should mean:

```text
scope: focused_window.children
match:
  AXRole == "AXRadioButton"
  AXDescription in {"通讯录", "__EN_CONTACTS_PLACEHOLDER__"}
normalize:
  id = "nav.contacts"
  label = "contacts"
  selected = bool_or_numeric(AXValue)
```

The sample path `0/2` can be stored in `element.axPath` after this match, but
the parser should not select contacts only because a node is at child index 2.

## Normalized Model

The normalized model is called `WeChatWindow`.

```text
WeChatWindow
  appName
  bundleId
  pid
  title
  snapshotId
  element
  activeSection
  navigation[]
  searchBox
  conversationList
  chatPanel
  actionables[]
  availableActions[]
```

### Element Reference

Every object that may be clicked, focused, or scrolled keeps an
`ElementRef`.

```json
{
  "axPath": "0/11/1/0/3",
  "role": "AXRow",
  "label": "conversation row label",
  "frame": {"x": 329, "y": 296, "width": 271, "height": 68},
  "actions": [],
  "enabled": true,
  "focused": false
}
```

Rules:

- `axPath` is valid only for the snapshot that produced it.
- `frame` is screen-coordinate based and can be used for coordinate fallback.
- `actions` is advisory. Many useful WeChat rows do not expose `AXPress`.
- `label` should use the best available `AXTitle`, `AXDescription`, or parsed
  semantic label.
- Raw AX attribute names are debug data and are not exposed through the normal
  application-facing window model.

### Navigation

```json
{
  "id": "nav.chats",
  "label": "chats",
  "selected": true,
  "element": {}
}
```

Extraction:

- Source roles are usually `AXRadioButton`.
- The parser scans direct children of the focused window and treats child index
  only as a candidate hint.
- Labels come from localized `AXDescription` matches first, then `AXTitle`.
- Stable semantic labels are normalized to keys such as `chats`, `contacts`,
  and `favorites`.
- Selected state comes from boolean or numeric `AXValue`.

### Search Box

```json
{
  "placeholder": "search",
  "value": "",
  "focused": false,
  "element": {}
}
```

Extraction:

- Source role is usually `AXTextArea`.
- It is near the top of the main split group and has a search-like description.
- The parser must verify `AXDescription` first, then `AXTitle` or another label
  field, looking for search-like values such as `搜索` or `search`.
- The path or child index is only a candidate hint. A node at the expected
  sample path must still pass the semantic check before becoming `searchBox`.
- The candidate frame should be in the top-left search area and should not
  overlap the bottom composer region.
- The model should not assume it is focused after a hotkey. A later operation
  must verify focus before typing.

### Conversation List

```json
{
  "region": {
    "id": "conversation-list",
    "kind": "conversation_list",
    "element": {},
    "scrollValue": 0,
    "totalChildren": 414
  },
  "totalRows": 414,
  "rows": [
    {
      "id": "conversation.0",
      "displayName": "contact or group name",
      "preview": "last message preview",
      "timestamp": "2026/06/30",
      "unreadCount": null,
      "pinned": true,
      "muted": false,
      "selected": null,
      "badges": ["pinned"],
      "element": {}
    }
  ]
}
```

Extraction:

- The scroll region is an `AXScrollArea`.
- The table is usually the first child `AXTable`.
- Each useful row is an `AXRow` with non-zero height.
- Row text usually lives in the first `AXCell` `AXDescription`.
- The cell description is a compact string containing display name, preview,
  timestamp, and badges. Parsing is heuristic; keep the raw element reference
  and use confidence in actionables.
- Zero-height rows should normally be ignored as layout artifacts.

### Chat Panel

```json
{
  "title": "current chat title",
  "element": {},
  "profileButton": {},
  "messageList": {},
  "toolbarButtons": [],
  "composer": {}
}
```

Extraction:

- The right-side split group is the chat panel.
- The current chat title is an `AXStaticText` near the top of the panel.
- Profile/details is usually a top-right button.
- Toolbar buttons are `AXButton` nodes between the message list and composer.
- Composer is the lower `AXTextArea` inside the composer scroll area.

### Message List

```json
{
  "region": {
    "id": "message-list",
    "kind": "message_list",
    "element": {},
    "scrollValue": 0.91,
    "totalChildren": 46
  },
  "totalRows": 46,
  "rows": [
    {
      "id": "message.0",
      "direction": "unknown",
      "visible": true,
      "text": null,
      "sender": null,
      "timestamp": null,
      "element": {}
    }
  ]
}
```

Extraction:

- The message list viewport is an `AXScrollArea`.
- Its table rows may include offscreen rows with negative coordinates.
- Only rows intersecting the viewport should be marked `visible=true`.
- Text extraction from message rows is best-effort; the first model version can
  expose message row references even when text cannot be confidently parsed.

### Composer

```json
{
  "draftText": "",
  "targetTitle": "current chat title",
  "element": {}
}
```

Extraction:

- Source role is usually `AXTextArea`.
- Draft text comes from `AXValue`.
- Target title can come from `AXTitle` when WeChat exposes it, or from the chat
  panel title.

### Actionable Regions

`actionables` is the flattened list of UI regions that can be targeted by a
lower-level executor. It is not the agent decision surface by itself.

```json
{
  "id": "conversation.0.open",
  "kind": "conversation_row",
  "label": "contact or group name",
  "confidence": 0.86,
  "reason": "AXRow with non-empty cell description in conversation table",
  "element": {}
}
```

Allowed kinds:

- `navigation_item`
- `search_box`
- `conversation_row`
- `message_row`
- `toolbar_button`
- `composer`
- `scroll_region`
- `window_button`
- `unknown`

Action execution rules:

- Prefer `AXPress` or other explicit AX actions when available.
- If no AX action exists, coordinate fallback may use `frame.center`.
- Coordinate fallback must verify app identity, window title, and snapshot
  freshness before clicking.
- The action API should accept `snapshotId` plus actionable `id`, not raw
  coordinates from the caller.

### Available Actions

`availableActions` is the agent-facing next-action menu. It translates the
current window model into choices an agent can reason over without rereading the
entire tree.

```json
{
  "id": "ui.conversation.0.open",
  "kind": "ui_element",
  "status": "available",
  "label": "Open conversation: File Transfer",
  "tool": "macos.computer_use",
  "operation": "click",
  "description": "Open one visible conversation row from the conversation list.",
  "inputTemplate": {
    "targetApp": "WeChat",
    "bundleId": "com.tencent.xinWeChat",
    "snapshotId": "frontmost:WeChat:微信 (聊天)",
    "selector": {"role": "AXRow", "name": "File Transfer"},
    "coordinates": {"x": 464, "y": 330}
  },
  "actionableId": "conversation.0.open",
  "targetElement": {},
  "risk": "changes_current_chat"
}
```

Allowed statuses:

- `available`: the action can be attempted from the current model.
- `needs_input`: the action is valid, but the caller must provide input such as
  `contact` or `message`.
- `blocked`: the action cannot be performed from the current model; inspect
  `reason` and `recoveryHint`.

Allowed kinds:

- `wechat_operation`: a semantic `wechat.desktop` operation such as
  `focus_contact`, `draft_message`, or `read_visible_messages`.
- `ui_element`: a visible UI element action backed by an `actionables[]` entry.
- `diagnostic`: recovery guidance when the model cannot infer UI actions.

When Accessibility tree collection is missing, `availableActions` must not be
empty. It should include a blocked diagnostic action such as
`diagnostic.accessibility_tree_missing` plus a refresh action, so the caller can
distinguish "no actions exist" from "the backend did not return a tree".

## Data Kept vs Dropped

Keep:

- App identity: app name, bundle id, pid.
- Window identity: title, snapshot id, window frame.
- Element references for all semantic and actionable nodes.
- Labels, values, selected/focused/enabled flags.
- Conversation row summaries and visible message row references.
- Scroll regions and scrollbar values when available.

Drop from the normalized model by default:

- `AXParent`, `AXWindow`, `AXTopLevelUIElement`, and other object references.
- Full recursive child trees.
- Large raw text blobs beyond the semantic fields.
- Hidden layout artifacts with zero width or zero height unless needed for
  diagnostics.

Keep raw data only in explicit debug output or raw-data logs.

## Snapshot Freshness

All `axPath` values and frames are snapshot-local. Any mutating operation that
uses this model should require:

- `snapshotId`
- target actionable `id`
- expected app bundle id
- expected window title or window identity

If a fresh observation no longer matches, the operation should fail with a
stale-snapshot or target-not-found error instead of clicking.

## Versioning

The first contract version should be named:

```text
wechat.window.v1
```

Future versions can add fields, but should avoid changing the meaning of:

- `element.axPath`
- `element.frame`
- `actionables[].id`
- `conversationList.rows[].id`
- `chatPanel.composer.element`

## Proposed Read APIs

The model is intended to support these read-only APIs first:

```text
inspect_window(includeRaw=false, includeActionables=true) -> WeChatWindow
list_actionable_regions() -> actionables[]
list_conversations() -> conversationList.rows[]
read_visible_messages() -> chatPanel.messageList.rows[]
get_current_conversation() -> chatPanel.title
```

Mutating APIs should be added only after the read model is stable:

```text
open_conversation(actionableId, snapshotId)
open_conversation_by_name(name)
focus_search(snapshotId)
scroll_region(regionId, direction, snapshotId)
focus_composer(snapshotId)
```
