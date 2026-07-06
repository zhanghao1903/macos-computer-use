# wechat-desktop-tool Architecture

`wechat-desktop-tool` is the WeChat Desktop semantic adapter in the app-control
package suite. It converts WeChat-specific operations into generic
`macos.computer_use` commands and maps low-level observations back into clean
WeChat models for application developers.

It does not execute macOS APIs directly. It depends on an
`app_control_protocol.AppControlClient` implementation, normally provided by
`computer-use-macos`.

## Position In The Stack

```text
Application / Agent runtime
  -> wechat-desktop-tool semantic API
    -> app-control-protocol ToolCommand / ToolObservation
      -> AppControlClient
        -> computer-use-macos
          -> macOS Accessibility and desktop primitives
```

The stable tool name is `wechat.desktop`. Public callers should use
`WeChatDesktopTool`, command builders, or recipes such as `send_message`.

## Public Surfaces

The package exposes:

- `build_wechat_tool(app_control_client)` for constructing the semantic tool.
- `WeChatDesktopTool` methods such as `inspect_window`, `list_contacts`,
  `open_contact`, `read_visible_messages`, and `send_message`.
- Command builders such as `inspect_window_command`, `list_contacts_command`,
  and `execute_action_command`.
- WeChat dataclasses and normalized window models.
- Convenience recipes for common flows.
- CLI examples for inspect-window and send-message smoke checks.

All public operations return `ToolObservation` payloads with WeChat-owned
schemas and failure kinds.

## Component Map

- `adapter.py`: builds a `WeChatDesktopTool` from an app-control client.
- `commands.py`: protocol command builders for the `wechat.desktop` tool.
- `tool.py`: operation dispatcher, workflow orchestration, phase evidence,
  WeChat normalization, and semantic failure handling.
- `window_model.py`: normalization from scoped Accessibility query results into
  `wechat.window.v1`.
- `models.py`: public dataclasses, enums, and message/window model helpers.
- `recipes.py`: higher-level convenience flows.
- `observations.py`: WeChat observation helpers.
- `errors.py`: stable WeChat failure kinds.
- `cli.py`: package CLI and example runners.

## Operation Lifecycle

1. A caller invokes a method or builds a `wechat.desktop` command.
2. `WeChatDesktopTool` opens or verifies the WeChat window when required.
3. The tool runs one or more app-control phases, such as `open_app`,
   `accessibility_query`, `accessibility_action`, `hotkey`, `type_text`, or
   `press_key`.
4. Each phase stores bounded evidence for diagnostics.
5. The tool maps phase observations into a WeChat schema such as
   `wechat.window.v1`, `wechat.contacts.v1`, or `wechat.messages.v1`.
6. The caller receives a semantic observation with clean items, action
   references, pagination metadata, and failure details.

The application should consume the WeChat model, not raw macOS Accessibility
nodes.

## Semantic Model

The main read model is `wechat.window.v1`. It contains:

- app and window identity;
- normalized navigation items;
- named regions such as search box, main content, conversation list, message
  list, chat panel, and composer;
- actionable regions and available semantic actions;
- element references for follow-up actions.

List APIs return domain-specific items:

- contacts with display names and row open actions;
- conversations with preview, timestamp, badges, pinned and muted flags;
- visible messages with sender, direction, timestamp, text, and stable hashes
  where available.

Raw Accessibility payloads are debug evidence, not the package consumer
contract.

## Accessibility Search Strategy

WeChat UI discovery is a graph search problem. Absolute paths such as
`0/12/2/0/353/0/1` are useful diagnostics and cache hints, but they are not
stable enough to be public contracts.

The adapter should find UI regions by selectors that combine:

- AX role, such as `AXRadioButton`, `AXSplitGroup`, `AXTable`, `AXRow`, and
  `AXStaticText`;
- localized attributes, such as `AXDescription = "通讯录"` or English
  equivalents;
- available actions, such as `AXPress`;
- structural constraints, such as a table containing many rows;
- relative anchors, such as searching for the contacts table inside the main
  content region;
- geometry and visibility constraints when needed.

The WeChat package owns the semantic selector profile. The lower
`computer-use-macos` package should own generic selector resolution, path hint
validation, bounded traversal, and action execution.

## Selector Profile Direction

The intended long-term structure is a configurable selector profile:

```toml
[selectors.navigation.contacts]
role = "AXRadioButton"
description_any = ["通讯录", "__CONTACTS_EN__"]
actions_include = ["AXPress"]

[selectors.contacts.table]
from = "regions.mainContent"
role = "AXTable"
children_role_include = "AXRow"

[selectors.contacts.row.display_name]
from = "contacts.row"
descendant_role = "AXStaticText"
value_source = "AXValue"
```

The packaged default profile should cover supported WeChat versions and
locales. Applications may override it through configuration when a WeChat UI
change only affects locator rules. Code remains responsible for mapping found
nodes into WeChat concepts.

## Read APIs

Read APIs should be structured around small, targeted queries:

- `inspect_window`: discover stable top-level regions and actions.
- `list_contacts`: switch to contacts, find the contacts table, and page
  visible rows.
- `list_conversations`: find visible conversation rows and parse their labels.
- `read_visible_messages`: find loaded message rows in the current chat.
- `read_contact_messages`: compose contact opening and visible message reading.

These APIs should return enough action references for an Agent application to
decide its next step without reading raw AX trees.

## Action APIs

Action APIs should prefer semantic actions or validated Accessibility actions:

- `open_contact`: locate and open one contact, returning disambiguation instead
  of selecting implicitly when multiple candidates match.
- `execute_action`: run a returned `actionRef` after validating its target and
  preconditions.
- `draft_message`, `submit_draft`, and `send_message`: mutate the desktop and
  therefore must remain explicit in naming and audit evidence.

Message sending is not a business authorization system. The caller remains
responsible for user confirmation, allowed recipients, allowed content, and
audit retention.

## Performance Principles

- Open/focus WeChat once per operation and reuse phase evidence where possible.
- Query top-level navigation and main regions first.
- Anchor later queries to the smallest relevant region, such as the contacts
  `AXTable` instead of the entire main content split group.
- Bound every query by depth, limit, and time budget.
- Treat truncation as a diagnostic signal and expose pagination metadata for
  list APIs.

## Failure And Diagnostics

Failures should be semantic and recoverable:

- `wechat_not_ready` when WeChat cannot be focused or verified.
- `main_content_not_found` when the window shape cannot be normalized.
- `wechat_list_failed` when a scoped query fails.
- `contact_not_found` or `needs_disambiguation` for contact search outcomes.
- `send_unverified` when submit occurred but the message cannot be confirmed.

Phase evidence should include enough lower-level observations for debugging,
but public results should prefer normalized fields and concise diagnostics over
full raw tree exposure.

## Package Boundary

`wechat-desktop-tool` must not import macOS-specific implementation modules
directly. It depends on `app-control-protocol` and a compatible app-control
client. It owns WeChat operation names, WeChat configuration, semantic schemas,
selector profiles, and WeChat-specific normalization.

It must not own application UI, LLM provider integrations, durable task state,
business authorization, or global audit storage.
