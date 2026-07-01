"""Normalize raw Accessibility trees into WeChat window models."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

from app_control_protocol import ToolObservation
from app_control_protocol.json_types import JsonValue

from .models import (
    WeChatActionableRegion,
    WeChatChatPanel,
    WeChatComposer,
    WeChatConversationList,
    WeChatConversationRow,
    WeChatDesktopConfig,
    WeChatElementRef,
    WeChatFrame,
    WeChatMessageList,
    WeChatMessageRow,
    WeChatNavigationItem,
    WeChatScrollRegion,
    WeChatSearchBox,
    WeChatToolbarButton,
    WeChatWindow,
)

_AX_VALUE_NUMBER_RE = re.compile(r"([xywh]):(-?\d+(?:\.\d+)?)")

_NAV_LABELS: dict[str, tuple[str, ...]] = {
    "chats": ("聊天", "__EN_CHATS_PLACEHOLDER__"),
    "contacts": ("通讯录", "__EN_CONTACTS_PLACEHOLDER__"),
    "favorites": ("收藏", "__EN_FAVORITES_PLACEHOLDER__"),
}
_SEARCH_LABELS = ("搜索", "search", "__EN_SEARCH_PLACEHOLDER__")
_PINNED_MARKERS = ("置顶", "pinned", "__EN_PINNED_PLACEHOLDER__")
_MUTED_MARKERS = ("消息免打扰", "muted", "__EN_MUTED_PLACEHOLDER__")


def build_wechat_window_model(
    config: WeChatDesktopConfig,
    observation: ToolObservation,
    *,
    include_actionables: bool = True,
) -> tuple[WeChatWindow, dict[str, JsonValue]]:
    tree = _focused_window_tree(observation)
    if tree is None:
        return (
            _window_shell(config, observation),
            {
                "status": "unavailable",
                "reason": "accessibility_tree_missing",
            },
        )

    context = _BuildContext()
    window = _build_window_from_tree(
        config,
        observation,
        tree,
        include_actionables=include_actionables,
        context=context,
    )
    return (
        window,
        {
            "status": "normalized",
            "reason": "accessibility_tree_normalized",
            "actionableCount": len(window.actionables),
            "conversationRowCount": (
                len(window.conversation_list.rows)
                if window.conversation_list is not None
                else 0
            ),
            "messageRowCount": (
                len(window.chat_panel.message_list.rows)
                if (
                    window.chat_panel is not None
                    and window.chat_panel.message_list is not None
                )
                else 0
            ),
        },
    )


class _BuildContext:
    def __init__(self) -> None:
        self.actionables: list[WeChatActionableRegion] = []

    def add_actionable(
        self,
        *,
        id: str,
        kind: str,
        element: WeChatElementRef,
        label: str | None = None,
        confidence: float = 1.0,
        reason: str | None = None,
    ) -> None:
        self.actionables.append(
            WeChatActionableRegion(
                id=id,
                kind=kind,  # type: ignore[arg-type]
                element=element,
                label=label,
                confidence=confidence,
                reason=reason,
            )
        )


def _build_window_from_tree(
    config: WeChatDesktopConfig,
    observation: ToolObservation,
    tree: Mapping[str, Any],
    *,
    include_actionables: bool,
    context: _BuildContext,
) -> WeChatWindow:
    window_title = _string_from_observation(
        observation,
        "windowTitle",
        "window_title",
        "title",
    ) or _node_title(tree) or config.app_name
    app_name = _string_from_observation(
        observation,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    ) or config.app_name
    bundle_id = _string_from_observation(
        observation,
        "frontmostBundleId",
        "frontmost_bundle_id",
        "bundleId",
        "bundle_id",
    ) or config.bundle_id
    snapshot_id = _string_from_observation(observation, "snapshotId", "snapshot_id")
    window_element = _element_ref(tree, fallback_role="AXWindow", label=window_title)

    children = _children(tree)
    navigation = _navigation_items(children, context=context)
    main_split = _main_split_group(children)
    search_box = None
    conversation_list = None
    chat_panel = None
    if main_split is not None:
        main_children = _children(main_split)
        search_box = _search_box(main_children, context=context)
        conversation_list = _conversation_list(main_children, context=context)
        chat_panel = _chat_panel(main_children, context=context)

    active_section = next((item.label for item in navigation if item.selected), None)
    return WeChatWindow(
        app_name=app_name,
        bundle_id=bundle_id,
        pid=_int_from_observation(observation, "pid", "processId", "process_id"),
        title=window_title,
        snapshot_id=snapshot_id,
        active_section=active_section,
        element=window_element,
        navigation=tuple(navigation),
        search_box=search_box,
        conversation_list=conversation_list,
        chat_panel=chat_panel,
        actionables=tuple(context.actionables) if include_actionables else (),
    )


def _window_shell(
    config: WeChatDesktopConfig,
    observation: ToolObservation,
) -> WeChatWindow:
    window_title = _string_from_observation(
        observation,
        "windowTitle",
        "window_title",
        "title",
    )
    frontmost_app = _string_from_observation(
        observation,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    )
    bundle_id = _string_from_observation(
        observation,
        "frontmostBundleId",
        "frontmost_bundle_id",
        "bundleId",
        "bundle_id",
    )
    snapshot_id = _string_from_observation(observation, "snapshotId", "snapshot_id")
    return WeChatWindow(
        app_name=frontmost_app or config.app_name,
        bundle_id=bundle_id or config.bundle_id,
        pid=_int_from_observation(observation, "pid", "processId", "process_id"),
        title=window_title or config.app_name,
        snapshot_id=snapshot_id,
        element=WeChatElementRef(
            ax_path="0",
            role="AXWindow",
            label=window_title or config.app_name,
        ),
    )


def _focused_window_tree(observation: ToolObservation) -> Mapping[str, Any] | None:
    for payload in (observation.observation, observation.evidence):
        tree = _tree_from_mapping(payload)
        if tree is not None:
            return tree
    return None


def _tree_from_mapping(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = _mapping_value(payload.get("focused_window"))
    if direct is not None:
        return direct
    accessibility = _mapping_value(payload.get("accessibility"))
    if accessibility is not None:
        for key in (
            "focusedWindow",
            "focused_window",
            "windowTree",
            "window_tree",
            "elementTree",
            "element_tree",
        ):
            tree = _mapping_value(accessibility.get(key))
            if tree is not None:
                return tree
    raw = _mapping_value(payload.get("rawObservation"))
    if raw is not None:
        return _tree_from_mapping(raw)
    return None


def _navigation_items(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> tuple[WeChatNavigationItem, ...]:
    items: list[WeChatNavigationItem] = []
    for child in children:
        if _role(child) != "AXRadioButton":
            continue
        semantic = _navigation_key(child)
        if semantic is None:
            continue
        element = _element_ref(child, fallback_role="AXRadioButton", label=semantic)
        item = WeChatNavigationItem(
            id=f"nav.{semantic}",
            label=semantic,
            selected=_selected(child),
            element=element,
        )
        items.append(item)
        context.add_actionable(
            id=f"nav.{semantic}.press",
            kind="navigation_item",
            label=semantic,
            element=element,
            reason="direct AXRadioButton child matched localized AXDescription",
        )
    return tuple(items)


def _navigation_key(node: Mapping[str, Any]) -> str | None:
    description = _node_description(node)
    if description is None:
        return None
    normalized = description.casefold()
    for key, labels in _NAV_LABELS.items():
        if normalized in {label.casefold() for label in labels}:
            return key
    return None


def _main_split_group(
    children: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    candidates = [child for child in children if _role(child) == "AXSplitGroup"]
    if not candidates:
        return None
    return max(candidates, key=lambda item: len(_children(item)))


def _search_box(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> WeChatSearchBox | None:
    for child in children:
        if _role(child) not in {"AXTextArea", "AXTextField"}:
            continue
        label = _label(child)
        if label is None or not _contains_any(label, _SEARCH_LABELS):
            continue
        element = _element_ref(child, fallback_role=_role(child) or "AXTextArea")
        context.add_actionable(
            id="search.focus",
            kind="search_box",
            label="search",
            element=element,
            reason="text input matched search-like AXDescription",
        )
        return WeChatSearchBox(
            element=element,
            placeholder=label,
            value=_string_value(_value(child)),
            focused=_bool_value(_attr(child, "AXFocused", "focused")),
        )
    return None


def _conversation_list(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> WeChatConversationList | None:
    for child in children:
        if _role(child) != "AXScrollArea":
            continue
        table = _first_child_with_role(child, "AXTable")
        if table is None:
            continue
        rows = _conversation_rows(
            table,
            viewport=_frame(child),
            context=context,
        )
        if not rows:
            continue
        region_element = _element_ref(child, fallback_role="AXScrollArea")
        region = WeChatScrollRegion(
            id="conversation-list",
            kind="conversation_list",
            element=region_element,
            total_children=_children_count(table),
        )
        context.add_actionable(
            id="conversation-list.scroll",
            kind="scroll_region",
            label="conversation_list",
            element=region_element,
            reason="AXScrollArea containing AXTable conversation rows",
        )
        return WeChatConversationList(
            region=region,
            rows=tuple(rows),
            total_rows=_children_count(table),
        )
    return None


def _conversation_rows(
    table: Mapping[str, Any],
    *,
    viewport: WeChatFrame | None,
    context: _BuildContext,
) -> list[WeChatConversationRow]:
    rows: list[WeChatConversationRow] = []
    for row in _children(table):
        if _role(row) != "AXRow":
            continue
        row_frame = _frame(row)
        if row_frame is not None and row_frame.height <= 0:
            continue
        if viewport is not None and row_frame is not None:
            if not _frames_intersect(viewport, row_frame):
                continue
        description = _first_cell_description(row)
        if not description:
            continue
        parsed = _parse_conversation_description(description)
        if parsed is None:
            continue
        row_id = f"conversation.{len(rows)}"
        element = _element_ref(row, fallback_role="AXRow", label=parsed["displayName"])
        badges = tuple(parsed["badges"])
        item = WeChatConversationRow(
            id=row_id,
            display_name=parsed["displayName"],
            element=element,
            preview=parsed.get("preview"),
            timestamp=parsed.get("timestamp"),
            pinned=any(_contains_any(badge, _PINNED_MARKERS) for badge in badges),
            muted=any(_contains_any(badge, _MUTED_MARKERS) for badge in badges),
            badges=badges,
        )
        rows.append(item)
        context.add_actionable(
            id=f"{row_id}.open",
            kind="conversation_row",
            label=item.display_name,
            element=element,
            confidence=0.88,
            reason="visible AXRow with non-empty conversation AXCell description",
        )
    return rows


def _chat_panel(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> WeChatChatPanel | None:
    split_groups = [child for child in children if _role(child) == "AXSplitGroup"]
    if not split_groups:
        return None
    panel = max(
        split_groups,
        key=lambda item: (_frame(item).width if _frame(item) else 0),
    )
    panel_children = _children(panel)
    title = _chat_title(panel_children)
    message_list = _message_list(panel_children, context=context)
    composer = _composer(panel_children, target_title=title, context=context)
    toolbar_buttons = _toolbar_buttons(panel_children, context=context)
    profile_button = _profile_button(panel_children, context=context)
    return WeChatChatPanel(
        element=_element_ref(panel, fallback_role="AXSplitGroup", label=title),
        title=title,
        profile_button=profile_button,
        message_list=message_list,
        toolbar_buttons=tuple(toolbar_buttons),
        composer=composer,
    )


def _chat_title(children: Iterable[Mapping[str, Any]]) -> str | None:
    for child in children:
        if _role(child) == "AXStaticText":
            value = _string_value(_value(child))
            if value:
                return value
    return None


def _message_list(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> WeChatMessageList | None:
    candidates = []
    for child in children:
        if _role(child) != "AXScrollArea":
            continue
        table = _first_child_with_role(child, "AXTable")
        if table is not None:
            candidates.append((child, table))
    if not candidates:
        return None
    scroll_area, table = max(
        candidates,
        key=lambda pair: (_frame(pair[0]).height if _frame(pair[0]) else 0),
    )
    viewport = _frame(scroll_area)
    rows: list[WeChatMessageRow] = []
    for row in _children(table):
        if _role(row) != "AXRow":
            continue
        row_frame = _frame(row)
        visible = not (
            viewport is not None
            and row_frame is not None
            and not _frames_intersect(viewport, row_frame)
        )
        if not visible:
            continue
        text = _first_cell_description(row)
        row_id = f"message.{len(rows)}"
        element = _element_ref(row, fallback_role="AXRow", label=text)
        rows.append(
            WeChatMessageRow(
                id=row_id,
                element=element,
                text=text,
                visible=visible,
            )
        )
        context.add_actionable(
            id=f"{row_id}.inspect",
            kind="message_row",
            label=text,
            element=element,
            confidence=0.55,
            reason="visible AXRow inside message table",
        )
    region_element = _element_ref(scroll_area, fallback_role="AXScrollArea")
    context.add_actionable(
        id="message-list.scroll",
        kind="scroll_region",
        label="message_list",
        element=region_element,
        reason="AXScrollArea containing message AXTable",
    )
    return WeChatMessageList(
        region=WeChatScrollRegion(
            id="message-list",
            kind="message_list",
            element=region_element,
            total_children=_children_count(table),
        ),
        rows=tuple(rows),
        total_rows=_children_count(table),
    )


def _composer(
    children: Iterable[Mapping[str, Any]],
    *,
    target_title: str | None,
    context: _BuildContext,
) -> WeChatComposer | None:
    candidates: list[Mapping[str, Any]] = []
    for child in children:
        if _role(child) != "AXScrollArea":
            continue
        text_area = _first_child_with_role(child, "AXTextArea")
        if text_area is not None:
            candidates.append(text_area)
    if not candidates:
        return None
    composer_node = max(
        candidates,
        key=lambda item: (_frame(item).y if _frame(item) is not None else 0),
    )
    element = _element_ref(
        composer_node,
        fallback_role="AXTextArea",
        label=target_title,
    )
    context.add_actionable(
        id="composer.focus",
        kind="composer",
        label="composer",
        element=element,
        reason="bottom AXTextArea inside chat panel",
    )
    return WeChatComposer(
        element=element,
        draft_text=_string_value(_value(composer_node)) or "",
        target_title=target_title or _node_title(composer_node),
    )


def _toolbar_buttons(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> list[WeChatToolbarButton]:
    buttons: list[WeChatToolbarButton] = []
    for child in children:
        if _role(child) != "AXButton":
            continue
        label = _label(child)
        frame = _frame(child)
        if not label or frame is None:
            continue
        if frame.y < 100:
            continue
        button_id = f"toolbar.{_stable_id(label, len(buttons))}"
        element = _element_ref(child, fallback_role="AXButton", label=label)
        buttons.append(
            WeChatToolbarButton(
                id=button_id,
                label=label,
                element=element,
            )
        )
        context.add_actionable(
            id=f"{button_id}.press",
            kind="toolbar_button",
            label=label,
            element=element,
            reason="AXButton in chat toolbar area",
        )
    return buttons


def _profile_button(
    children: Iterable[Mapping[str, Any]],
    *,
    context: _BuildContext,
) -> WeChatActionableRegion | None:
    for child in children:
        if _role(child) != "AXButton":
            continue
        label = _label(child)
        if label != "个人卡片":
            continue
        element = _element_ref(child, fallback_role="AXButton", label=label)
        region = WeChatActionableRegion(
            id="profile.open",
            kind="toolbar_button",
            label=label,
            element=element,
            reason="top-right profile card button",
        )
        context.actionables.append(region)
        return region
    return None


def _parse_conversation_description(text: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in text.split(",")]
    if not parts or not parts[0]:
        return None
    payload: dict[str, Any] = {"displayName": parts[0], "badges": []}
    if len(parts) > 1 and parts[1]:
        payload["preview"] = parts[1]
    if len(parts) > 2 and parts[2]:
        payload["timestamp"] = parts[2]
    if len(parts) > 3:
        payload["badges"] = [part for part in parts[3:] if part]
    return payload


def _first_cell_description(node: Mapping[str, Any]) -> str | None:
    for child in _children(node):
        if _role(child) != "AXCell":
            continue
        label = _label(child)
        if label:
            return label
        for grandchild in _children(child):
            nested = _label(grandchild)
            if nested:
                return nested
    return None


def _first_child_with_role(
    node: Mapping[str, Any],
    role: str,
) -> Mapping[str, Any] | None:
    for child in _children(node):
        if _role(child) == role:
            return child
    return None


def _element_ref(
    node: Mapping[str, Any],
    *,
    fallback_role: str,
    label: str | None = None,
) -> WeChatElementRef:
    return WeChatElementRef(
        ax_path=_string_value(node.get("path")) or "0",
        role=_role(node) or fallback_role,
        frame=_frame(node),
        label=label or _label(node),
        value=_json_scalar(_value(node)),
        actions=tuple(_string_items(node.get("actions"))),
        enabled=_bool_value(_attr(node, "AXEnabled", "enabled")),
        focused=_bool_value(_attr(node, "AXFocused", "focused")),
        attribute_names=tuple(_string_items(node.get("attribute_names"))),
    )


def _frame(node: Mapping[str, Any]) -> WeChatFrame | None:
    frame = _mapping_value(_attr(node, "frame", "AXFrame"))
    if frame is not None:
        x = _number_value(frame.get("x"))
        y = _number_value(frame.get("y"))
        width = _number_value(frame.get("width") or frame.get("w"))
        height = _number_value(frame.get("height") or frame.get("h"))
        if None not in (x, y, width, height):
            return WeChatFrame(x=x, y=y, width=width, height=height)

    position = _mapping_value(_attr(node, "position", "AXPosition"))
    size = _mapping_value(_attr(node, "size", "AXSize"))
    if position is not None and size is not None:
        x = _number_value(position.get("x"))
        y = _number_value(position.get("y"))
        width = _number_value(size.get("width") or size.get("w"))
        height = _number_value(size.get("height") or size.get("h"))
        if None not in (x, y, width, height):
            return WeChatFrame(x=x, y=y, width=width, height=height)

    position_numbers = _numbers_from_ax_value(_attr(node, "AXPosition", "position"))
    size_numbers = _numbers_from_ax_value(_attr(node, "AXSize", "size"))
    if {"x", "y"} <= position_numbers.keys() and {"w", "h"} <= size_numbers.keys():
        return WeChatFrame(
            x=position_numbers["x"],
            y=position_numbers["y"],
            width=size_numbers["w"],
            height=size_numbers["h"],
        )

    x = _number_value(node.get("x"))
    y = _number_value(node.get("y"))
    width = _number_value(node.get("width"))
    height = _number_value(node.get("height"))
    if None not in (x, y, width, height):
        return WeChatFrame(x=x, y=y, width=width, height=height)
    return None


def _numbers_from_ax_value(value: object) -> dict[str, float]:
    if not isinstance(value, str):
        return {}
    return {key: float(raw) for key, raw in _AX_VALUE_NUMBER_RE.findall(value)}


def _frames_intersect(a: WeChatFrame, b: WeChatFrame) -> bool:
    return (
        a.x < b.x + b.width
        and a.x + a.width > b.x
        and a.y < b.y + b.height
        and a.y + a.height > b.y
    )


def _role(node: Mapping[str, Any]) -> str | None:
    return _string_value(_attr(node, "AXRole", "role"))


def _node_title(node: Mapping[str, Any]) -> str | None:
    return _string_value(_attr(node, "AXTitle", "title", "name"))


def _node_description(node: Mapping[str, Any]) -> str | None:
    return _string_value(_attr(node, "AXDescription", "description"))


def _value(node: Mapping[str, Any]) -> object:
    return _attr(node, "AXValue", "value")


def _label(node: Mapping[str, Any]) -> str | None:
    return (
        _node_description(node)
        or _node_title(node)
        or _string_value(_attr(node, "name"))
        or _string_value(_value(node))
    )


def _selected(node: Mapping[str, Any]) -> bool:
    value = _value(node)
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return False


def _children(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = node.get("children")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _children_count(node: Mapping[str, Any]) -> int:
    value = node.get("children_count") or node.get("childrenCount")
    if isinstance(value, int) and value >= 0:
        return value
    return len(_children(node))


def _attr(node: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in node:
            return node[key]
    return None


def _mapping_value(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _json_scalar(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _contains_any(value: str, markers: Iterable[str]) -> bool:
    normalized = value.casefold()
    return any(marker.casefold() in normalized for marker in markers)


def _stable_id(label: str, fallback_index: int) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", label.strip().casefold()).strip("-")
    return normalized or str(fallback_index)


def _string_from_observation(
    observation: ToolObservation,
    *keys: str,
) -> str | None:
    for payload in (observation.observation, observation.evidence):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _int_from_observation(
    observation: ToolObservation,
    *keys: str,
) -> int | None:
    for payload in (observation.observation, observation.evidence):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
    return None
