"""Typed models for WeChat Desktop semantic operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from app_control_protocol import AppControlConfig

WeChatOperation = Literal[
    "open_wechat",
    "inspect_window",
    "list_contacts",
    "list_conversations",
    "open_contact",
    "execute_action",
    "focus_contact",
    "observe_current_chat",
    "read_visible_messages",
    "read_contact_messages",
    "draft_message",
    "submit_draft",
    "send_message",
]

WECHAT_WINDOW_SCHEMA = "wechat.window.v1"

WeChatActionableKind = Literal[
    "navigation_item",
    "search_box",
    "conversation_row",
    "message_row",
    "toolbar_button",
    "composer",
    "scroll_region",
    "window_button",
    "unknown",
]

WeChatAvailableActionKind = Literal[
    "wechat_operation",
    "ui_element",
    "diagnostic",
]

WeChatAvailableActionStatus = Literal[
    "available",
    "needs_input",
    "blocked",
]

WeChatScrollRegionKind = Literal[
    "conversation_list",
    "message_list",
    "composer",
    "unknown",
]


@dataclass(frozen=True)
class WeChatDesktopConfig:
    app_name: str = "WeChat"
    bundle_id: str | None = "com.tencent.xinWeChat"
    app_control_tool: str = "macos.computer_use"
    selector_profile_path: str | None = None
    search_hotkey: tuple[str, ...] = ("Command", "F")
    search_clear_hotkey: tuple[str, ...] = ("Command", "A")
    clear_key: str = "Delete"
    submit_key: str = "Return"
    default_timeout_ms: int = 30_000
    max_message_chars: int = 2_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_name", _non_empty(self.app_name, "app_name"))
        if self.bundle_id is not None:
            object.__setattr__(
                self,
                "bundle_id",
                _non_empty(self.bundle_id, "bundle_id"),
            )
        object.__setattr__(
            self,
            "app_control_tool",
            _non_empty(self.app_control_tool, "app_control_tool"),
        )
        object.__setattr__(
            self,
            "selector_profile_path",
            _optional_non_empty(
                self.selector_profile_path,
                "selector_profile_path",
            ),
        )
        object.__setattr__(
            self,
            "search_hotkey",
            _string_tuple(self.search_hotkey, "search_hotkey"),
        )
        object.__setattr__(
            self,
            "search_clear_hotkey",
            _string_tuple(self.search_clear_hotkey, "search_clear_hotkey"),
        )
        object.__setattr__(
            self,
            "clear_key",
            _non_empty(self.clear_key, "clear_key"),
        )
        object.__setattr__(
            self,
            "submit_key",
            _non_empty(self.submit_key, "submit_key"),
        )
        if self.default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms must be positive")
        if self.max_message_chars <= 0:
            raise ValueError("max_message_chars must be positive")

    @classmethod
    def from_app_control_config(
        cls,
        config: "AppControlConfig | Mapping[str, Any] | str | Path | None" = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> "WeChatDesktopConfig":
        app_config = _load_app_control_config(config, env=env)
        wechat = app_config.wechat
        return cls(
            app_name=wechat.app_name,
            bundle_id=wechat.bundle_id,
            app_control_tool=wechat.app_control_tool,
            selector_profile_path=wechat.selector_profile_path,
            search_hotkey=wechat.search_hotkey,
            search_clear_hotkey=wechat.search_clear_hotkey,
            clear_key=wechat.clear_key,
            submit_key=wechat.submit_key,
            default_timeout_ms=wechat.default_timeout_ms,
            max_message_chars=wechat.max_message_chars,
        )


@dataclass(frozen=True)
class WeChatVisibleMessage:
    text: str
    direction: str = "unknown"
    visible_timestamp: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _non_empty(self.text, "text"))
        object.__setattr__(
            self,
            "direction",
            _non_empty(self.direction, "direction"),
        )

    def to_dict(self) -> dict[str, str]:
        payload = {
            "direction": self.direction,
            "text": self.text,
        }
        if self.visible_timestamp is not None:
            payload["visibleTimestamp"] = self.visible_timestamp
        return payload


@dataclass(frozen=True)
class WeChatFrame:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _number(self.x, "x"))
        object.__setattr__(self, "y", _number(self.y, "y"))
        object.__setattr__(self, "width", _non_negative_number(self.width, "width"))
        object.__setattr__(self, "height", _non_negative_number(self.height, "height"))

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def to_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class WeChatElementRef:
    ax_path: str
    role: str
    frame: WeChatFrame | None = None
    label: str | None = None
    value: str | int | float | bool | None = None
    actions: tuple[str, ...] = ()
    enabled: bool | None = None
    focused: bool | None = None
    attribute_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ax_path", _non_empty(self.ax_path, "ax_path"))
        object.__setattr__(self, "role", _non_empty(self.role, "role"))
        object.__setattr__(self, "label", _optional_non_empty(self.label, "label"))
        object.__setattr__(
            self,
            "actions",
            _string_tuple(self.actions, "actions", allow_empty=True),
        )
        object.__setattr__(
            self,
            "attribute_names",
            _string_tuple(
                self.attribute_names,
                "attribute_names",
                allow_empty=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "axPath": self.ax_path,
            "role": self.role,
        }
        if self.frame is not None:
            payload["frame"] = self.frame.to_dict()
        if self.label is not None:
            payload["label"] = self.label
        if self.value is not None:
            payload["value"] = self.value
        if self.actions:
            payload["actions"] = list(self.actions)
        if self.enabled is not None:
            payload["enabled"] = self.enabled
        if self.focused is not None:
            payload["focused"] = self.focused
        return payload


@dataclass(frozen=True)
class WeChatActionableRegion:
    id: str
    kind: WeChatActionableKind
    element: WeChatElementRef
    label: str | None = None
    confidence: float = 1.0
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        object.__setattr__(self, "label", _optional_non_empty(self.label, "label"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "reason", _optional_non_empty(self.reason, "reason"))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "element": self.element.to_dict(),
            "confidence": self.confidence,
        }
        if self.label is not None:
            payload["label"] = self.label
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class WeChatAvailableAction:
    id: str
    kind: WeChatAvailableActionKind
    status: WeChatAvailableActionStatus
    label: str
    tool: str | None = None
    operation: str | None = None
    description: str | None = None
    input_schema: Mapping[str, Any] | None = None
    input_template: Mapping[str, Any] | None = None
    action_ref: Mapping[str, Any] | None = None
    actionable_id: str | None = None
    target_element: WeChatElementRef | None = None
    risk: str | None = None
    reason: str | None = None
    recovery_hint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        object.__setattr__(self, "label", _non_empty(self.label, "label"))
        object.__setattr__(self, "tool", _optional_non_empty(self.tool, "tool"))
        object.__setattr__(
            self,
            "operation",
            _optional_non_empty(self.operation, "operation"),
        )
        object.__setattr__(
            self,
            "description",
            _optional_non_empty(self.description, "description"),
        )
        object.__setattr__(
            self,
            "actionable_id",
            _optional_non_empty(self.actionable_id, "actionable_id"),
        )
        object.__setattr__(self, "risk", _optional_non_empty(self.risk, "risk"))
        object.__setattr__(self, "reason", _optional_non_empty(self.reason, "reason"))
        object.__setattr__(
            self,
            "recovery_hint",
            _optional_non_empty(self.recovery_hint, "recovery_hint"),
        )
        if self.input_schema is not None:
            object.__setattr__(self, "input_schema", dict(self.input_schema))
        if self.input_template is not None:
            object.__setattr__(self, "input_template", dict(self.input_template))
        if self.action_ref is not None:
            object.__setattr__(self, "action_ref", dict(self.action_ref))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "label": self.label,
        }
        if self.tool is not None:
            payload["tool"] = self.tool
        if self.operation is not None:
            payload["operation"] = self.operation
        if self.description is not None:
            payload["description"] = self.description
        if self.input_schema is not None:
            payload["inputSchema"] = dict(self.input_schema)
        if self.input_template is not None:
            payload["inputTemplate"] = dict(self.input_template)
        if self.action_ref is not None:
            payload["actionRef"] = dict(self.action_ref)
        if self.actionable_id is not None:
            payload["actionableId"] = self.actionable_id
        if self.target_element is not None:
            payload["targetElement"] = self.target_element.to_dict()
        if self.risk is not None:
            payload["risk"] = self.risk
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.recovery_hint is not None:
            payload["recoveryHint"] = self.recovery_hint
        return payload


@dataclass(frozen=True)
class WeChatNavigationItem:
    id: str
    label: str
    selected: bool
    element: WeChatElementRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        object.__setattr__(self, "label", _non_empty(self.label, "label"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "selected": self.selected,
            "element": self.element.to_dict(),
        }


@dataclass(frozen=True)
class WeChatSearchBox:
    element: WeChatElementRef
    placeholder: str | None = None
    value: str | None = None
    focused: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "placeholder",
            _optional_non_empty(self.placeholder, "placeholder"),
        )
        object.__setattr__(self, "value", _optional_string(self.value, "value"))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"element": self.element.to_dict()}
        if self.placeholder is not None:
            payload["placeholder"] = self.placeholder
        if self.value is not None:
            payload["value"] = self.value
        if self.focused is not None:
            payload["focused"] = self.focused
        return payload


@dataclass(frozen=True)
class WeChatScrollRegion:
    id: str
    kind: WeChatScrollRegionKind
    element: WeChatElementRef
    scroll_value: float | None = None
    total_children: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        if self.scroll_value is not None:
            object.__setattr__(
                self,
                "scroll_value",
                _number(self.scroll_value, "scroll_value"),
            )
        if self.total_children is not None and self.total_children < 0:
            raise ValueError("total_children must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "element": self.element.to_dict(),
        }
        if self.scroll_value is not None:
            payload["scrollValue"] = self.scroll_value
        if self.total_children is not None:
            payload["totalChildren"] = self.total_children
        return payload


@dataclass(frozen=True)
class WeChatConversationRow:
    id: str
    display_name: str
    element: WeChatElementRef
    preview: str | None = None
    timestamp: str | None = None
    unread_count: int | None = None
    pinned: bool = False
    muted: bool = False
    selected: bool | None = None
    badges: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        object.__setattr__(
            self,
            "display_name",
            _non_empty(self.display_name, "display_name"),
        )
        object.__setattr__(self, "preview", _optional_string(self.preview, "preview"))
        object.__setattr__(
            self,
            "timestamp",
            _optional_non_empty(self.timestamp, "timestamp"),
        )
        if self.unread_count is not None and self.unread_count < 0:
            raise ValueError("unread_count must be non-negative")
        object.__setattr__(
            self,
            "badges",
            _string_tuple(self.badges, "badges", allow_empty=True),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "displayName": self.display_name,
            "element": self.element.to_dict(),
            "pinned": self.pinned,
            "muted": self.muted,
        }
        if self.preview is not None:
            payload["preview"] = self.preview
        if self.timestamp is not None:
            payload["timestamp"] = self.timestamp
        if self.unread_count is not None:
            payload["unreadCount"] = self.unread_count
        if self.selected is not None:
            payload["selected"] = self.selected
        if self.badges:
            payload["badges"] = list(self.badges)
        return payload


@dataclass(frozen=True)
class WeChatConversationList:
    region: WeChatScrollRegion | None = None
    rows: tuple[WeChatConversationRow, ...] = ()
    total_rows: int | None = None

    def __post_init__(self) -> None:
        if self.total_rows is not None and self.total_rows < 0:
            raise ValueError("total_rows must be non-negative")
        object.__setattr__(self, "rows", tuple(self.rows))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rows": [row.to_dict() for row in self.rows],
        }
        if self.region is not None:
            payload["region"] = self.region.to_dict()
        if self.total_rows is not None:
            payload["totalRows"] = self.total_rows
        return payload


@dataclass(frozen=True)
class WeChatMessageRow:
    id: str
    element: WeChatElementRef
    text: str | None = None
    sender: str | None = None
    direction: str = "unknown"
    timestamp: str | None = None
    visible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        object.__setattr__(self, "text", _optional_string(self.text, "text"))
        object.__setattr__(self, "sender", _optional_non_empty(self.sender, "sender"))
        object.__setattr__(
            self,
            "direction",
            _non_empty(self.direction, "direction"),
        )
        object.__setattr__(
            self,
            "timestamp",
            _optional_non_empty(self.timestamp, "timestamp"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "direction": self.direction,
            "visible": self.visible,
            "element": self.element.to_dict(),
        }
        if self.text is not None:
            payload["text"] = self.text
        if self.sender is not None:
            payload["sender"] = self.sender
        if self.timestamp is not None:
            payload["timestamp"] = self.timestamp
        return payload


@dataclass(frozen=True)
class WeChatMessageList:
    region: WeChatScrollRegion | None = None
    rows: tuple[WeChatMessageRow, ...] = ()
    total_rows: int | None = None

    def __post_init__(self) -> None:
        if self.total_rows is not None and self.total_rows < 0:
            raise ValueError("total_rows must be non-negative")
        object.__setattr__(self, "rows", tuple(self.rows))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rows": [row.to_dict() for row in self.rows],
        }
        if self.region is not None:
            payload["region"] = self.region.to_dict()
        if self.total_rows is not None:
            payload["totalRows"] = self.total_rows
        return payload


@dataclass(frozen=True)
class WeChatToolbarButton:
    id: str
    label: str
    element: WeChatElementRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty(self.id, "id"))
        object.__setattr__(self, "label", _non_empty(self.label, "label"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "element": self.element.to_dict(),
        }


@dataclass(frozen=True)
class WeChatComposer:
    element: WeChatElementRef
    draft_text: str = ""
    target_title: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "draft_text",
            _optional_string(self.draft_text, "draft_text") or "",
        )
        object.__setattr__(
            self,
            "target_title",
            _optional_non_empty(self.target_title, "target_title"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "element": self.element.to_dict(),
            "draftText": self.draft_text,
        }
        if self.target_title is not None:
            payload["targetTitle"] = self.target_title
        return payload


@dataclass(frozen=True)
class WeChatChatPanel:
    element: WeChatElementRef | None = None
    title: str | None = None
    profile_button: WeChatActionableRegion | None = None
    message_list: WeChatMessageList | None = None
    toolbar_buttons: tuple[WeChatToolbarButton, ...] = ()
    composer: WeChatComposer | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _optional_non_empty(self.title, "title"))
        object.__setattr__(self, "toolbar_buttons", tuple(self.toolbar_buttons))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.element is not None:
            payload["element"] = self.element.to_dict()
        if self.title is not None:
            payload["title"] = self.title
        if self.profile_button is not None:
            payload["profileButton"] = self.profile_button.to_dict()
        if self.message_list is not None:
            payload["messageList"] = self.message_list.to_dict()
        if self.toolbar_buttons:
            payload["toolbarButtons"] = [
                button.to_dict() for button in self.toolbar_buttons
            ]
        if self.composer is not None:
            payload["composer"] = self.composer.to_dict()
        return payload


@dataclass(frozen=True)
class WeChatWindow:
    app_name: str
    bundle_id: str | None
    pid: int | None
    title: str
    element: WeChatElementRef
    snapshot_id: str | None = None
    active_section: str | None = None
    navigation: tuple[WeChatNavigationItem, ...] = ()
    search_box: WeChatSearchBox | None = None
    conversation_list: WeChatConversationList | None = None
    chat_panel: WeChatChatPanel | None = None
    actionables: tuple[WeChatActionableRegion, ...] = ()
    available_actions: tuple[WeChatAvailableAction, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_name", _non_empty(self.app_name, "app_name"))
        if self.bundle_id is not None:
            object.__setattr__(
                self,
                "bundle_id",
                _non_empty(self.bundle_id, "bundle_id"),
            )
        if self.pid is not None and self.pid <= 0:
            raise ValueError("pid must be positive")
        object.__setattr__(self, "title", _non_empty(self.title, "title"))
        object.__setattr__(
            self,
            "snapshot_id",
            _optional_non_empty(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(
            self,
            "active_section",
            _optional_non_empty(self.active_section, "active_section"),
        )
        object.__setattr__(self, "navigation", tuple(self.navigation))
        object.__setattr__(self, "actionables", tuple(self.actionables))
        object.__setattr__(
            self,
            "available_actions",
            tuple(self.available_actions),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "appName": self.app_name,
            "title": self.title,
            "element": self.element.to_dict(),
            "navigation": [item.to_dict() for item in self.navigation],
            "actionables": [item.to_dict() for item in self.actionables],
            "availableActions": [
                item.to_dict() for item in self.available_actions
            ],
        }
        if self.bundle_id is not None:
            payload["bundleId"] = self.bundle_id
        if self.pid is not None:
            payload["pid"] = self.pid
        if self.snapshot_id is not None:
            payload["snapshotId"] = self.snapshot_id
        if self.active_section is not None:
            payload["activeSection"] = self.active_section
        if self.search_box is not None:
            payload["searchBox"] = self.search_box.to_dict()
        if self.conversation_list is not None:
            payload["conversationList"] = self.conversation_list.to_dict()
        if self.chat_panel is not None:
            payload["chatPanel"] = self.chat_panel.to_dict()
        return payload


def wechat_message_hash(message: str) -> str:
    return "sha256:" + sha256(message.encode("utf-8")).hexdigest()


def _number(value: object, field_name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number")
    return float(value)


def _non_negative_number(value: object, field_name: str) -> float:
    number = _number(value, field_name)
    if number < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


def _confidence(value: object) -> float:
    number = _number(value, "confidence")
    if number < 0 or number > 1:
        raise ValueError("confidence must be between 0 and 1")
    return number


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_non_empty(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty(value, field_name)


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


def _string_tuple(
    value: object,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, tuple | list):
        raise TypeError(f"{field_name} must be a string sequence")
    items = tuple(_non_empty(item, field_name) for item in value)
    if not items and not allow_empty:
        raise ValueError(f"{field_name} must not be empty")
    return items


def _load_app_control_config(
    config: "AppControlConfig | Mapping[str, Any] | str | Path | None",
    *,
    env: Mapping[str, str] | None,
) -> "AppControlConfig":
    from app_control_protocol import AppControlConfig, load_app_control_config

    if config is None or isinstance(config, str | Path):
        return load_app_control_config(config, env=env)
    if isinstance(config, AppControlConfig):
        return config
    if isinstance(config, Mapping):
        return AppControlConfig.from_dict(config)
    raise TypeError("config must be an AppControlConfig, mapping, path, or None")
