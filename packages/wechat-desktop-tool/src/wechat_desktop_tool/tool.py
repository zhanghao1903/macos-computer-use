"""Protocol-first WeChat Desktop tool."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from app_control_protocol import (
    AppControlClient,
    ToolCommand,
    ToolError,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolObserver,
    ToolStatus,
)
from app_control_protocol.json_types import JsonValue

from ._diagnostics import (
    _CHAT_INPUT_MARKERS,
    _SEARCH_FOCUS_MARKERS,
    _action_ref_input,
    _bool_input,
    _duration_ms,
    _emit,
    _event,
    _executed_action_method,
    _failure,
    _mapping_from_observation,
    _mapping_value,
    _nested_failure,
    _observation_indicates_input_not_focused,
    _observation_indicates_login_required,
    _optional_string_from_mapping,
    _optional_string_input,
    _positive_int,
    _redact_input_text,
    _required_input,
    _safe_accessibility_status,
    _safe_app_control_envelope,
    _safe_app_control_event_summary,
    _send_unverified,
    _string_from_observation,
    _string_input,
    _string_value,
    _utc_now,
    _wechat_environment,
    _wechat_not_ready_failure,
    _wechat_observation_has_window_title,
    _with_timing,
)

from ._query_mapping import (
    _accessibility_element_contains,
    _action_ref_from_node,
    _coordinate_click_disabled,
    _failure_from_collection_result,
    _failure_from_selector_query,
    _failure_from_selector_result,
    _first_concrete_label,
    _focused_text_field_position,
    _is_text_like_accessibility_element,
    _main_content_node,
    _mapped_control_node_matches,
    _navigation_from_query_nodes,
    _node_actions,
    _node_ax_path,
    _node_center_coordinates,
    _node_frame_within_query_window,
    _node_from_selector_element,
    _node_label,
    _node_selected,
    _public_accessibility_element,
    _query_matches_target_app_window,
    _query_nodes,
    _query_normalization_reason,
    _query_payload,
    _query_snapshot_id,
    _query_truncated,
    _root_resolver_payload,
    _selector_element_center_coordinates,
    _selector_element_selected,
    _utc_now_datetime,
    _wechat_environment_from_query,
    _window_from_query,
    _window_title_matches_navigation,
)

from ._row_parsing import (
    _chat_title_from_query_nodes,
    _collection_extraction_limit,
    _collection_has_more,
    _contact_ambiguity_failure,
    _contact_candidates_ambiguity_failure,
    _contact_confidence,
    _conversation_rows_from_cells,
    _current_chat_title,
    _message_observed,
    _messages_from_observation,
    _messages_from_query_nodes,
    _next_page_token,
    _row_items_from_collection_items,
    _row_items_from_nodes,
    _search_candidates_from_nodes,
    _visible_contact_candidates_from_nodes,
)

from .commands import WECHAT_TOOL, wechat_command
from .control_map import WeChatMappedCollection
from .control_map import WeChatMappedControl
from .control_map import WeChatRootResolver
from .models import (
    WECHAT_WINDOW_SCHEMA,
    WeChatDesktopConfig,
    WeChatOperation,
    wechat_message_hash,
)
from .profiles import build_packaged_collection_extractor
from .profiles import build_packaged_selector_resolver
from .profiles import load_selector_assets

if TYPE_CHECKING:
    from app_control_protocol import AppControlConfig


_MAPPED_NAVIGATION_ACTION_TIMEOUT_MS = 2_000
_MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS = 800
_MAPPED_NAVIGATION_CLICK_TIMEOUT_MS = 1_200
_MAPPED_CONVERSATION_TARGET_QUERY_TIMEOUT_MS = 450
_SEARCH_FOCUS_QUERY_TIMEOUT_MS = 500
_DEFINITE_UNSUPPORTED_NATIVE_ERRORS = {
    "AXPress": -25206,
    "AXSetFocus": -25205,
}


@dataclass(frozen=True)
class _BooleanEvidence:
    present: bool
    valid: bool
    value: bool | None = None


@dataclass(frozen=True)
class _StringEvidence:
    present: bool
    valid: bool
    value: str | None = None


@dataclass(frozen=True)
class _IntegerEvidence:
    present: bool
    valid: bool
    value: int | None = None


@dataclass(frozen=True)
class _ContactQueryFailureContext:
    failure_kind: str
    cause_failure_kind: str
    message: str
    retryable: bool | None


_QUERY_ATTRIBUTES: list[str] = [
    "AXRole",
    "AXSubrole",
    "AXTitle",
    "AXValue",
    "AXDescription",
    "AXHelp",
    "AXEnabled",
    "AXFocused",
    "AXSelected",
    "AXPosition",
    "AXSize",
    "AXFrame",
    "AXPlaceholderValue",
]


class WeChatDesktopTool:
    """Semantic WeChat Desktop tool built on an app-control client."""

    def __init__(
        self,
        app_control: AppControlClient,
        config: WeChatDesktopConfig | None = None,
    ) -> None:
        self._app_control = app_control
        self._config = config or WeChatDesktopConfig()
        if self._config.computer_use_backend.casefold() == "helper":
            raise ValueError(
                "wechat-desktop-tool selector APIs do not support "
                "computer_use.backend=helper in version 0.3.0; use direct or "
                "a direct-backed local service"
            )
        self._selector_assets = load_selector_assets(
            self._config.selector_profile_path
        )
        self._control_map = self._selector_assets.control_map
        self._selector_profile = self._selector_assets.selector_profile

    @classmethod
    def from_config(
        cls,
        app_control: AppControlClient,
        config: "AppControlConfig | Mapping[str, Any] | str | Path | None" = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> "WeChatDesktopTool":
        """Build a WeChat tool from shared app-control configuration."""

        return cls(
            app_control,
            config=WeChatDesktopConfig.from_app_control_config(config, env=env),
        )

    @property
    def config(self) -> WeChatDesktopConfig:
        return self._config

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: ToolObserver | None = None,
    ) -> ToolObservation:
        tool_command = _coerce_command(command)
        started_at = _utc_now()
        started_monotonic = time.monotonic()
        _emit(observer, _event(tool_command, 0, ToolEventType.STARTED))
        phase_events = _PhaseEventCollector(tool_command, observer=observer)
        observation = self._execute(tool_command, phase_events=phase_events)
        observation = _with_timing(
            observation,
            started_at=started_at,
            duration_ms=_duration_ms(started_monotonic),
        )
        _emit(
            observer,
            _event(
                tool_command,
                phase_events.next_seq(),
                ToolEventType.OBSERVATION,
                observation,
            ),
        )
        return observation

    def run_stream(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: ToolObserver | None = None,
    ) -> Iterator[ToolEvent]:
        tool_command = _coerce_command(command)
        started_at = _utc_now()
        started_monotonic = time.monotonic()
        started = _event(tool_command, 0, ToolEventType.STARTED)
        _emit(observer, started)
        yield started
        phase_events = _PhaseEventCollector(tool_command, observer=observer)
        observation = self._execute(tool_command, phase_events=phase_events)
        observation = _with_timing(
            observation,
            started_at=started_at,
            duration_ms=_duration_ms(started_monotonic),
        )
        yield from phase_events.events
        final = _event(
            tool_command,
            phase_events.next_seq(),
            ToolEventType.OBSERVATION,
            observation,
        )
        _emit(observer, final)
        yield final

    def open_wechat(self) -> ToolObservation:
        command = self._command("open_wechat")
        return self.run_command(command)

    def inspect_window(
        self,
        *,
        include_raw: bool = False,
        include_actionables: bool = True,
    ) -> ToolObservation:
        command = self._command(
            "inspect_window",
            {
                "includeRaw": include_raw,
                "includeActionables": include_actionables,
            },
        )
        return self.run_command(command)

    def list_contacts(
        self,
        *,
        limit: int = 30,
        page_token: str | None = None,
    ) -> ToolObservation:
        payload: dict[str, JsonValue] = {"limit": limit}
        if page_token is not None:
            payload["pageToken"] = page_token
        command = self._command("list_contacts", payload)
        return self.run_command(command)

    def list_conversations(
        self,
        *,
        limit: int = 30,
        page_token: str | None = None,
    ) -> ToolObservation:
        payload: dict[str, JsonValue] = {"limit": limit}
        if page_token is not None:
            payload["pageToken"] = page_token
        command = self._command("list_conversations", payload)
        return self.run_command(command)

    def open_contact(self, contact: str) -> ToolObservation:
        command = self._command("open_contact", {"contact": contact})
        return self.run_command(command)

    def execute_action(self, action_ref: Mapping[str, JsonValue]) -> ToolObservation:
        command = self._command("execute_action", {"actionRef": dict(action_ref)})
        return self.run_command(command)

    def focus_contact(self, contact: str) -> ToolObservation:
        command = self._command("focus_contact", {"contact": contact})
        return self.run_command(command)

    def observe_current_chat(
        self,
        *,
        include_visible_messages: bool = True,
    ) -> ToolObservation:
        command = self._command(
            "observe_current_chat",
            {"includeVisibleMessages": include_visible_messages},
        )
        return self.run_command(command)

    def read_visible_messages(self, *, limit: int = 20) -> ToolObservation:
        command = self._command("read_visible_messages", {"limit": limit})
        return self.run_command(command)

    def read_contact_messages(
        self,
        contact: str,
        *,
        limit: int = 30,
    ) -> ToolObservation:
        command = self._command(
            "read_contact_messages",
            {"contact": contact, "limit": limit},
        )
        return self.run_command(command)

    def draft_message(self, message: str) -> ToolObservation:
        command = self._command("draft_message", {"message": message})
        return self.run_command(command)

    def submit_draft(self, *, method: str = "keyboard_return") -> ToolObservation:
        command = self._command("submit_draft", {"method": method})
        return self.run_command(command)

    def send_message(
        self,
        *,
        contact: str,
        message: str,
        verify_after_submit: bool = False,
        verify_limit: int = 20,
    ) -> ToolObservation:
        command = self._command(
            "send_message",
            {
                "contact": contact,
                "message": message,
                "verifyAfterSubmit": verify_after_submit,
                "verifyLimit": verify_limit,
            },
        )
        return self.run_command(command)

    def _execute(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        try:
            if command.tool != WECHAT_TOOL:
                return _failure(
                    command,
                    status=ToolStatus.FAILED,
                    failure_kind="unsupported_tool",
                    message=f"wechat-desktop-tool cannot execute {command.tool}",
                )
            operation = command.operation
            if operation == "open_wechat":
                return self._open_wechat(command, phase_events=phase_events)
            if operation == "inspect_window":
                return self._inspect_window(command, phase_events=phase_events)
            if operation == "list_contacts":
                return self._list_contacts(command, phase_events=phase_events)
            if operation == "list_conversations":
                return self._list_conversations(command, phase_events=phase_events)
            if operation == "open_contact":
                return self._open_contact(command, phase_events=phase_events)
            if operation == "execute_action":
                return self._execute_action(command, phase_events=phase_events)
            if operation == "focus_contact":
                return self._focus_contact(command, phase_events=phase_events)
            if operation == "observe_current_chat":
                return self._observe_current_chat(command, phase_events=phase_events)
            if operation == "read_visible_messages":
                return self._read_visible_messages(command, phase_events=phase_events)
            if operation == "read_contact_messages":
                return self._read_contact_messages(command, phase_events=phase_events)
            if operation == "draft_message":
                return self._draft_message(command, phase_events=phase_events)
            if operation == "submit_draft":
                return self._submit_draft(command, phase_events=phase_events)
            if operation == "send_message":
                return self._send_message(command, phase_events=phase_events)
            return _failure(
                command,
                status=ToolStatus.FAILED,
                failure_kind="unsupported_operation",
                message=f"unsupported WeChat operation: {operation}",
            )
        except (TypeError, ValueError) as exc:
            return _failure(
                command,
                status=ToolStatus.FAILED,
                failure_kind="invalid_input",
                message=str(exc),
            )

    def _open_wechat(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        evidence: dict[str, JsonValue] = {}
        observed = self._open_wechat_phase(
            command,
            evidence,
            phase_events=phase_events,
        )
        if not observed.success:
            return _open_wechat_phase_failure(command, observed, evidence)
        identity_failure = _wechat_identity_failure(
            command,
            self._config,
            observed,
            evidence=evidence,
        )
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(
            command,
            self._config,
            observed,
            evidence=evidence,
        )
        if login_failure is not None:
            return login_failure
        window_title = _string_from_observation(
            observed,
            "windowTitle",
            "window_title",
            "title",
        )
        frontmost_app = _string_from_observation(
            observed,
            "frontmostApp",
            "frontmost_app",
            "appName",
            "app_name",
        )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Opened or focused WeChat Desktop.",
            observation={
                "appName": self._config.app_name,
                "bundleId": self._config.bundle_id,
                "frontmostApp": frontmost_app or self._config.app_name,
                "windowTitle": window_title,
                "currentChatTitle": _current_chat_title(
                    window_title,
                    self._config.app_name,
                ),
                "wechatEnvironment": _wechat_environment(self._config, observed),
                "windowReady": True,
                "appControlObservation": evidence.get("open_wechat"),
                "observeObservation": _safe_app_control_observation(observed),
            },
            evidence=evidence,
        )

    def _inspect_window(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        include_raw = _bool_input(command, "includeRaw", "include_raw", default=False)
        include_actionables = _bool_input(
            command,
            "includeActionables",
            "include_actionables",
            default=True,
        )
        evidence: dict[str, JsonValue] = {}
        opened = self._open_wechat_phase(command, evidence, phase_events=phase_events)
        if not opened.success:
            return _open_wechat_phase_failure(command, opened, evidence)
        top_level = self._app_control_command(
            command,
            phase="inspect_window",
            operation="accessibility_query",
            input=self._accessibility_query_input(
                root={"kind": "focusedWindow"},
                query={
                    "scope": "children",
                    "maxDepth": 1,
                    "limit": 80,
                    "timeBudgetMs": 10_000,
                    "attributes": _QUERY_ATTRIBUTES,
                    "actions": True,
                    "includeChildrenCount": False,
                },
                include_raw=include_raw,
            ),
            phase_events=phase_events,
        )
        evidence["inspect_window"] = _safe_app_control_observation(top_level)
        if not top_level.success:
            return _from_app_control_failure(
                command,
                "wechat_not_ready",
                top_level,
                evidence=evidence,
            )
        top_query = _query_payload(top_level)
        top_nodes = _query_nodes(top_level)
        top_snapshot_id = _query_snapshot_id(top_query)
        navigation = _navigation_from_query_nodes(
            top_nodes,
            snapshot_id=top_snapshot_id,
        )
        main_content = _main_content_node(top_nodes)
        main_nodes: list[dict[str, Any]] = []
        if main_content is not None:
            main_query_result = self._app_control_command(
                command,
                phase="inspect_window:main_content",
                operation="accessibility_query",
                input=self._accessibility_query_input(
                    root={
                        "kind": "axPath",
                        "snapshotId": _query_snapshot_id(top_query),
                        "axPath": main_content["axPath"],
                    },
                    query={
                        "scope": "children",
                        "maxDepth": 1,
                        "limit": 80,
                        "timeBudgetMs": 2_000,
                        "attributes": _QUERY_ATTRIBUTES,
                        "actions": True,
                        "includeChildrenCount": False,
                    },
                    include_raw=include_raw,
                ),
                phase_events=phase_events,
            )
            evidence["main_content"] = _safe_app_control_observation(main_query_result)
            if main_query_result.success:
                main_nodes = _query_nodes(main_query_result)
        window = _window_from_query(
            self._config,
            top_query,
            navigation=navigation,
            main_content=main_content,
            main_nodes=main_nodes,
            include_actionables=include_actionables,
        )
        normalization_reason = _query_normalization_reason(
            top_query,
            top_nodes=top_nodes,
            main_content=main_content,
        )
        if normalization_reason != "accessibility_query_normalized":
            available_actions = window.get("availableActions")
            if isinstance(available_actions, list):
                available_actions.append(
                    {
                        "id": f"diagnostic.{normalization_reason}",
                        "kind": "diagnostic",
                        "status": "blocked",
                        "operation": "inspect_window",
                        "recoveryHint": (
                            "Retry inspect_window after confirming macOS "
                            "Accessibility permission and a focused WeChat window."
                        ),
                    }
                )
        normalization = {
            "status": "normalized",
            "reason": normalization_reason,
            "actionableCount": len(window.get("actionables", [])),
            "availableActionCount": len(window.get("availableActions", [])),
            "queryMode": "scoped",
        }
        payload: dict[str, JsonValue] = {
            "schema": WECHAT_WINDOW_SCHEMA,
            "window": window,
            "includeRaw": include_raw,
            "includeActionables": include_actionables,
            "normalization": normalization,
            "wechatEnvironment": _wechat_environment_from_query(self._config, top_query),
        }
        if include_raw:
            payload["rawQueries"] = {
                "topLevel": top_query,
                "mainContent": main_nodes,
            }
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Inspected WeChat window.",
            observation=payload,
            evidence=evidence,
        )

    def _list_contacts(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        return self._list_row_items_with_selector_profile(
            command,
            section="contacts",
            schema="wechat.contacts.v1",
            collection_id="contacts",
            navigation_selector_id="navigation.contacts",
            summary="Listed visible WeChat contacts.",
            phase_events=phase_events,
        )

    def _list_conversations(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        return self._list_row_items_with_selector_profile(
            command,
            section="chats",
            schema="wechat.conversations.v1",
            collection_id="conversations",
            navigation_selector_id="navigation.chats",
            summary="Listed visible WeChat conversations.",
            phase_events=phase_events,
        )

    def _list_row_items_with_selector_profile(
        self,
        command: ToolCommand,
        *,
        section: str,
        schema: str,
        collection_id: str,
        navigation_selector_id: str,
        summary: str,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        limit = _positive_int(command.input.get("limit"), default=30)
        page_token = _optional_string_input(command, "pageToken", "page_token")
        if page_token is not None:
            return _failure(
                command,
                status=ToolStatus.FAILED,
                failure_kind="pagination_not_supported",
                message=(
                    "WeChat visible-window lists do not support continuation "
                    "page tokens. Request a larger limit or refresh the list."
                ),
                recovery_hint="Retry without pageToken.",
                retryable=False,
                observation={
                    "schema": schema,
                    "section": section,
                    "pagination": {
                        "mode": "visibleWindow",
                        "limit": limit,
                        "pageToken": page_token,
                        "hasMore": False,
                        "nextPageToken": None,
                    },
                },
            )
        evidence: dict[str, JsonValue] = {}
        opened = self._open_wechat_phase(command, evidence, phase_events=phase_events)
        if not opened.success:
            return _open_wechat_phase_failure(command, opened, evidence)

        fast_result = self._list_row_items_with_control_map(
            command,
            section=section,
            schema=schema,
            collection_id=collection_id,
            summary=summary,
            limit=limit,
            page_token=page_token,
            active_window_title=_string_from_observation(
                opened,
                "windowTitle",
                "window_title",
                "title",
            ),
            evidence=evidence,
            phase_events=phase_events,
        )
        if fast_result is not None:
            return fast_result

        selector_runner = _WeChatSelectorQueryRunner(
            self,
            command,
            evidence=evidence,
            phase_prefix=f"selectors.{section}",
            phase_events=phase_events,
        )
        resolver = build_packaged_selector_resolver(
            selector_runner,
            app_bundle_id=self._config.bundle_id or "",
            selector_profile=self._selector_profile,
        )
        navigation = resolver.resolve(navigation_selector_id)
        if navigation.status != "resolved" or not navigation.elements:
            return _failure_from_selector_result(
                command,
                navigation,
                failure_kind="wechat_navigation_failed",
                message=f"Could not locate WeChat {section} navigation item.",
                evidence=evidence,
            )
        if not _selector_element_selected(navigation.elements[0]):
            clicked = self._click_node_phase(
                command,
                _node_from_selector_element(navigation.elements[0]),
                phase=f"switch_{section}",
                evidence=evidence,
                snapshot_id=navigation.snapshot_id,
                phase_events=phase_events,
            )
            if not clicked.success:
                return _from_app_control_failure(
                    command,
                    "wechat_navigation_failed",
                    clicked,
                    evidence=evidence,
                )

        collection_limit = _collection_extraction_limit(section, limit)
        collection = build_packaged_collection_extractor(resolver).extract(
            collection_id,
            limit=collection_limit,
        )
        if collection.status == "failed":
            return _failure_from_collection_result(
                command,
                collection,
                failure_kind="wechat_list_failed",
                message=f"Could not list WeChat {section} items.",
                evidence=evidence,
            )
        page_rows = _row_items_from_collection_items(
            collection.items,
            section=section,
            limit=limit + 1,
            snapshot_id=collection.snapshot_id,
        )
        rows = page_rows[:limit]
        semantic_has_more = len(page_rows) > limit
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary=summary,
            observation={
                "schema": schema,
                "section": section,
                "items": rows,
                "pagination": {
                    "mode": "visibleWindow",
                    "limit": limit,
                    "pageToken": page_token,
                    "hasMore": semantic_has_more or _collection_has_more(collection),
                    "nextPageToken": None,
                },
                "availableActions": [
                    {
                        "id": "wechat.open_contact",
                        "status": "needs_input",
                        "operation": "open_contact",
                    }
                ],
            },
            evidence=evidence,
        )

    def _list_row_items_with_control_map(
        self,
        command: ToolCommand,
        *,
        section: str,
        schema: str,
        collection_id: str,
        summary: str,
        limit: int,
        page_token: str | None,
        active_window_title: str | None,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        navigation_key = "contacts" if section == "contacts" else "chats"
        switched = self._press_mapped_navigation(
            command,
            navigation_key,
            active_window_title=active_window_title,
            evidence=evidence,
            phase_events=phase_events,
        )
        if switched is None:
            return None
        if not switched.success:
            return _from_app_control_failure(
                command,
                "wechat_navigation_failed",
                switched,
                evidence=evidence,
            )
        collection_query = self._query_mapped_collection(
            command,
            collection_id,
            semantic_limit=limit + 1,
            evidence=evidence,
            phase_events=phase_events,
        )
        if collection_query is None:
            return None
        query_result, collection, nodes = collection_query
        page_rows = _row_items_from_nodes(
            nodes,
            section=section,
            limit=limit + 1,
            snapshot_id=_query_snapshot_id(_query_payload(query_result)),
        )
        if not page_rows and nodes:
            return None
        rows = page_rows[:limit]
        semantic_has_more = len(page_rows) > limit
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary=summary,
            observation={
                "schema": schema,
                "section": section,
                "items": rows,
                "pagination": {
                    "mode": "visibleWindow",
                    "limit": limit,
                    "pageToken": page_token,
                    "hasMore": semantic_has_more or _query_truncated(query_result),
                    "nextPageToken": None,
                },
                "source": {
                    "mode": "control_map",
                    "mapId": self._control_map.map_id,
                    "mapVersion": self._control_map.map_version,
                    "collection": collection.collection_id,
                },
                "availableActions": [
                    {
                        "id": "wechat.open_contact",
                        "status": "needs_input",
                        "operation": "open_contact",
                    }
                ],
            },
            evidence=evidence,
        )

    def _press_mapped_navigation(
        self,
        command: ToolCommand,
        navigation_key: str,
        *,
        active_window_title: str | None = None,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        control = self._control_map.navigation.get(navigation_key)
        if control is None:
            return None
        if _window_title_matches_navigation(active_window_title, control):
            phase = f"control_map_switch_{navigation_key}_skipped"
            skipped = ToolObservation.ok(
                command_id=f"{command.command_id}:{phase}",
                tool=WECHAT_TOOL,
                operation=command.operation,
                summary=f"WeChat is already on {navigation_key}.",
                observation={
                    "schema": "wechat.control_map.navigation.v1",
                    "status": "already_selected",
                    "navigation": navigation_key,
                    "control": control.control_id,
                    "source": {
                        "mode": "control_map",
                        "mapId": self._control_map.map_id,
                        "mapVersion": self._control_map.map_version,
                    },
                },
            )
            evidence[phase] = _safe_app_control_observation(skipped)
            return skipped
        return self._execute_mapped_control(
            command,
            control,
            action_id=f"nav.{navigation_key}.press",
            target_summary=f"Switch to {navigation_key}",
            phase=f"control_map_switch_{navigation_key}",
            evidence=evidence,
            phase_events=phase_events,
        )

    def _execute_mapped_control(
        self,
        command: ToolCommand,
        control: WeChatMappedControl,
        *,
        action_id: str,
        target_summary: str,
        phase: str,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        for index, ax_path in enumerate(control.ax_paths):
            query_phase = f"{phase}:target_{index}"
            target_query = self._app_control_command(
                command,
                phase=query_phase,
                operation="accessibility_query",
                input=self._accessibility_query_input(
                    root={"kind": "axPath", "axPath": ax_path},
                    query={
                        "scope": "self",
                        "maxDepth": 0,
                        "limit": 1,
                        "timeBudgetMs": _MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
                        "attributes": [
                            "AXRole",
                            "AXDescription",
                            "AXTitle",
                            "AXValue",
                            "AXEnabled",
                            "AXSelected",
                            "AXFrame",
                            "AXPosition",
                            "AXSize",
                        ],
                        "actions": True,
                        "includeChildrenCount": False,
                        "match": {"roleIn": [control.role]},
                    },
                ),
                timeout_ms=_MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
                phase_events=phase_events,
            )
            evidence[query_phase] = _safe_app_control_observation(target_query)
            if not target_query.success:
                continue
            if not _query_matches_target_app_window(target_query, self._config):
                continue
            nodes = _query_nodes(target_query)
            if not nodes:
                continue
            target_node = nodes[0]
            if not _mapped_control_node_matches(target_node, control):
                continue
            if not _node_frame_within_query_window(target_node, target_query):
                continue
            if _node_selected(target_node):
                selected_phase = f"{phase}:already_selected_{index}"
                selected = ToolObservation.ok(
                    command_id=f"{command.command_id}:{selected_phase}",
                    tool=WECHAT_TOOL,
                    operation=command.operation,
                    summary=(
                        f"WeChat navigation control {control.control_id} "
                        "is already selected."
                    ),
                    observation={
                        "schema": "wechat.control_map.navigation.v1",
                        "status": "already_selected",
                        "control": control.control_id,
                        "axPath": ax_path,
                    },
                )
                evidence[selected_phase] = _safe_app_control_observation(selected)
                return selected

            if control.action in _node_actions(target_node):
                action_ref = _action_ref_from_node(
                    target_node,
                    action_id=action_id,
                    kind=control.kind,
                    risk=control.risk,
                    target_summary=target_summary,
                    snapshot_id=_query_snapshot_id(_query_payload(target_query)),
                )
                if action_ref is not None:
                    action_result = self._execute_action_ref(
                        command,
                        action_ref,
                        phase=f"{phase}:action_{index}",
                        evidence=evidence,
                        timeout_ms=_MAPPED_NAVIGATION_ACTION_TIMEOUT_MS,
                        phase_events=phase_events,
                    )
                    if action_result.success:
                        return self._verify_mapped_navigation_postcondition(
                            command,
                            control,
                            ax_path=ax_path,
                            phase=f"{phase}:verify_{index}",
                            evidence=evidence,
                            phase_events=phase_events,
                        )
                    if not _should_try_coordinate_click_after_accessibility_action(
                        action_result,
                        expected_action=(
                            _optional_string_from_mapping(action_ref, "action")
                            or control.action
                        ),
                    ):
                        return action_result

            coordinates = _node_center_coordinates(target_node)
            if coordinates is None:
                continue
            coordinate_phase = f"{phase}:coordinate_{index}"
            coordinate_result = self._app_control_command(
                command,
                phase=coordinate_phase,
                operation="click",
                input=self._target_app_input(coordinates=coordinates),
                timeout_ms=_MAPPED_NAVIGATION_CLICK_TIMEOUT_MS,
                command_metadata={
                    "coordinateSource": "accessibility_frame",
                },
                phase_events=phase_events,
            )
            evidence[coordinate_phase] = _safe_app_control_observation(
                coordinate_result
            )
            if coordinate_result.success:
                return self._verify_mapped_navigation_postcondition(
                    command,
                    control,
                    ax_path=ax_path,
                    phase=f"{phase}:verify_{index}",
                    evidence=evidence,
                    phase_events=phase_events,
                )
            if not _coordinate_click_disabled(coordinate_result):
                return coordinate_result

        return _failure(
            command,
            status=ToolStatus.FAILED,
            failure_kind="wechat_navigation_target_unverified",
            message=(
                "Could not verify a current Accessibility target for "
                f"WeChat navigation control {control.control_id}."
            ),
            recovery_hint="Refresh the WeChat window and retry navigation.",
            retryable=True,
            evidence=evidence,
        )

    def _verify_mapped_navigation_postcondition(
        self,
        command: ToolCommand,
        control: WeChatMappedControl,
        *,
        ax_path: str,
        phase: str,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        verification = self._app_control_command(
            command,
            phase=phase,
            operation="accessibility_query",
            input=self._accessibility_query_input(
                root={"kind": "axPath", "axPath": ax_path},
                query={
                    "scope": "self",
                    "maxDepth": 0,
                    "limit": 1,
                    "timeBudgetMs": _MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
                    "attributes": [
                        "AXRole",
                        "AXDescription",
                        "AXTitle",
                        "AXValue",
                        "AXEnabled",
                        "AXSelected",
                    ],
                    "actions": False,
                    "includeChildrenCount": False,
                    "match": {"roleIn": [control.role]},
                },
            ),
            timeout_ms=_MAPPED_NAVIGATION_FRAME_QUERY_TIMEOUT_MS,
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(verification)
        nodes = _query_nodes(verification) if verification.success else []
        if _query_matches_target_app_window(
            verification,
            self._config,
        ) and nodes and _mapped_control_node_matches(
            nodes[0],
            control,
        ) and _node_selected(nodes[0]):
            return ToolObservation.ok(
                command_id=f"{command.command_id}:{phase}",
                tool=WECHAT_TOOL,
                operation=command.operation,
                summary=f"Selected WeChat navigation control {control.control_id}.",
                observation={
                    "schema": "wechat.control_map.navigation.v1",
                    "status": "selected",
                    "control": control.control_id,
                    "axPath": ax_path,
                },
                evidence=evidence,
            )
        return _failure(
            command,
            status=ToolStatus.FAILED,
            failure_kind="wechat_navigation_postcondition_failed",
            message=(
                f"WeChat navigation control {control.control_id} is not "
                "selected after the action."
            ),
            recovery_hint="Restore the expected WeChat view and retry.",
            retryable=True,
            evidence=evidence,
        )

    def _query_mapped_collection(
        self,
        command: ToolCommand,
        collection_id: str,
        *,
        semantic_limit: int,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> tuple[ToolObservation, WeChatMappedCollection, list[dict[str, Any]]] | None:
        collection = self._control_map.collections.get(collection_id)
        if collection is None:
            return None
        query_limit = max(
            collection.minimum_limit,
            semantic_limit * collection.limit_multiplier,
        )
        for index, root_ax_path in enumerate(collection.root_ax_paths):
            result = self._query_accessibility_nodes(
                command,
                root_node={"axPath": root_ax_path},
                phase=f"control_map_{collection_id}_{index}",
                scope="descendants",
                max_depth=collection.max_depth,
                role_in=list(collection.roles),
                limit=query_limit,
                time_budget_ms=collection.time_budget_ms,
                attributes=list(collection.attributes) or None,
                actions=collection.actions,
                root_resolver=collection.root_resolvers.get(root_ax_path),
                prefer_visible_rows=collection.prefer_visible_rows,
                evidence=evidence,
                phase_events=phase_events,
            )
            if not result.success:
                continue
            nodes = _query_nodes(result)
            if nodes:
                return result, collection, nodes
        return None

    def _query_mapped_conversation_target(
        self,
        command: ToolCommand,
        contact: str,
        *,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> tuple[ToolObservation, WeChatMappedCollection, list[dict[str, Any]]] | None:
        collection = self._control_map.collections.get("conversations")
        if collection is None:
            return None
        successful_query: tuple[
            ToolObservation,
            WeChatMappedCollection,
            list[dict[str, Any]],
        ] | None = None
        for index, root_ax_path in enumerate(collection.root_ax_paths):
            result = self._query_accessibility_nodes(
                command,
                root_node={"axPath": root_ax_path},
                phase=f"control_map_conversation_target_{index}",
                scope="descendants",
                max_depth=2,
                role_in=["AXCell"],
                limit=2,
                time_budget_ms=min(
                    collection.time_budget_ms,
                    _MAPPED_CONVERSATION_TARGET_QUERY_TIMEOUT_MS,
                ),
                attributes=[
                    "AXRole",
                    "AXDescription",
                    "AXPosition",
                    "AXSize",
                    "AXFrame",
                ],
                actions=False,
                match={"descriptionContains": f"{contact},"},
                prefer_visible_rows=True,
                evidence=evidence,
                phase_events=phase_events,
            )
            query_issue = _contact_target_query_issue(result)
            if (
                query_issue is not None
                and query_issue[0] == "failed"
                and result.failure_kind == "accessibility_query_root_not_found"
            ):
                continue
            if query_issue is not None:
                return result, collection, []
            rows = _conversation_rows_from_cells(_query_nodes(result))
            if rows:
                return result, collection, rows
            successful_query = (result, collection, [])
        return successful_query

    def _mapped_region_node(
        self,
        region_id: str,
        *,
        reference_ax_path: str | None = None,
    ) -> dict[str, Any] | None:
        region = self._control_map.regions.get(region_id)
        if region is None or not region.ax_paths:
            return None
        ax_path = region.ax_paths[0]
        if reference_ax_path is not None:
            reference_root = "/".join(reference_ax_path.split("/")[:2])
            ax_path = next(
                (
                    candidate
                    for candidate in region.ax_paths
                    if "/".join(candidate.split("/")[:2]) == reference_root
                ),
                ax_path,
            )
        node: dict[str, Any] = {
            "axPath": ax_path,
            "role": region.role,
        }
        label = _first_concrete_label(region.labels)
        if label is not None:
            node["label"] = label
        return node

    def _open_contact(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        contact = _required_input(command, "contact")
        evidence: dict[str, JsonValue] = {}
        opened = self._open_wechat_phase(command, evidence, phase_events=phase_events)
        if not opened.success:
            return _open_wechat_phase_failure(command, opened, evidence)
        chats_ready = self._press_mapped_navigation(
            command,
            "chats",
            active_window_title=_string_from_observation(
                opened,
                "windowTitle",
                "window_title",
                "title",
            ),
            evidence=evidence,
            phase_events=phase_events,
        )
        if chats_ready is not None and not chats_ready.success:
            return _from_app_control_failure(
                command,
                "wechat_navigation_failed",
                chats_ready,
                evidence=evidence,
            )
        visible_opened = self._open_visible_contact_with_control_map(
            command,
            contact=contact,
            evidence=evidence,
            phase_events=phase_events,
        )
        if visible_opened is not None:
            return visible_opened
        selector_runner = _WeChatSelectorQueryRunner(
            self,
            command,
            evidence=evidence,
            phase_prefix="selectors.open_contact",
            phase_events=phase_events,
        )
        resolver = build_packaged_selector_resolver(
            selector_runner,
            app_bundle_id=self._config.bundle_id or "",
            selector_profile=self._selector_profile,
        )
        main_content = resolver.resolve("regions.mainContent")
        if main_content.status != "resolved" or not main_content.elements:
            return _failure_from_selector_result(
                command,
                main_content,
                failure_kind="main_content_not_found",
                message="Could not locate WeChat main content region.",
                evidence=evidence,
            )
        visible_opened = self._open_visible_contact_phase(
            command,
            contact=contact,
            main_content=_node_from_selector_element(main_content.elements[0]),
            evidence=evidence,
            phase_events=phase_events,
        )
        if visible_opened is not None:
            return visible_opened
        search_box = resolver.resolve("regions.searchBox")
        if search_box.status != "resolved" or not search_box.elements:
            return _failure_from_selector_result(
                command,
                search_box,
                failure_kind="search_focus_failed",
                message="Could not locate WeChat search box.",
                evidence=evidence,
            )
        verified_search = self._focus_search_box_phase(
            command,
            contact=contact,
            search_box=search_box,
            evidence=evidence,
            phase_events=phase_events,
        )
        if not verified_search.success:
            return verified_search
        selected_search_text = self._app_control_command(
            command,
            phase="select_search_text",
            operation="hotkey",
            input=self._target_app_input(keys=["Command", "A"]),
            phase_events=phase_events,
        )
        evidence["select_search_text"] = _safe_app_control_observation(
            selected_search_text
        )
        if not selected_search_text.success:
            return _from_app_control_failure(
                command,
                "contact_search_failed",
                selected_search_text,
                evidence=evidence,
            )
        typed = self._app_control_command(
            command,
            phase="type_contact",
            operation="type_text",
            input=self._target_app_input(text=contact),
            phase_events=phase_events,
        )
        evidence["type_contact"] = _safe_app_control_observation(typed)
        if not typed.success:
            return _from_app_control_failure(
                command,
                "contact_search_failed",
                typed,
                evidence=evidence,
            )
        results = self._query_accessibility_nodes(
            command,
            root_node=_node_from_selector_element(main_content.elements[0]),
            phase="search_results",
            scope="descendants",
            max_depth=4,
            role_in=["AXRow", "AXCell", "AXStaticText"],
            limit=40,
            time_budget_ms=350,
            prefer_visible_rows=True,
            evidence=evidence,
            phase_events=phase_events,
        )
        query_failure = _contact_target_query_validation_failure(
            command,
            contact,
            results,
            evidence=evidence,
        )
        if query_failure is not None:
            return query_failure
        candidates = _search_candidates_from_nodes(
            _query_nodes(results),
            contact,
            snapshot_id=_query_snapshot_id(_query_payload(results)),
        )
        if len(candidates) > 1:
            return _contact_candidates_ambiguity_failure(
                command,
                contact,
                candidates,
                evidence=evidence,
            )
        if not candidates:
            return _contact_target_not_found_failure(
                command,
                contact,
                evidence=evidence,
            )
        element = candidates[0].get("element")
        if not isinstance(element, Mapping) or not _node_frame_within_query_window(
            element,
            results,
        ):
            return _contact_target_unverified_failure(
                command,
                contact,
                reason="search_candidate_frame_invalid",
                evidence=evidence,
            )
        selected = self._click_node_phase(
            command,
            element,
            phase="open_search_result",
            evidence=evidence,
            snapshot_id=_query_snapshot_id(_query_payload(results)),
            phase_events=phase_events,
        )
        if not selected.success and _should_press_return_for_search_result(
            selected,
            expected_action="AXPress",
        ):
            return_selected = self._app_control_command(
                command,
                phase="open_search_result:return_fallback",
                operation="press_key",
                input=self._target_app_input(key=self._config.submit_key),
                phase_events=phase_events,
            )
            evidence["open_search_result:return_fallback"] = (
                _safe_app_control_observation(return_selected)
            )
            if return_selected.success:
                selected = return_selected
        if not selected.success:
            return _from_app_control_failure(
                command,
                "contact_not_found",
                selected,
                evidence=evidence,
            )
        return self._opened_contact_observation(
            command,
            contact=contact,
            main_content=(
                self._mapped_region_node(
                    "chatPanel",
                    reference_ax_path=_node_ax_path(
                        _node_from_selector_element(main_content.elements[0])
                    ),
                )
                or _node_from_selector_element(main_content.elements[0])
            ),
            open_method="search",
            evidence=evidence,
            phase_events=phase_events,
        )

    def _open_visible_contact_phase(
        self,
        command: ToolCommand,
        *,
        contact: str,
        main_content: Mapping[str, Any],
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        visible_rows = self._query_accessibility_nodes(
            command,
            root_node=main_content,
            phase="visible_contact_rows",
            scope="descendants",
            max_depth=4,
            role_in=["AXRow", "AXCell", "AXStaticText"],
            limit=40,
            time_budget_ms=350,
            prefer_visible_rows=True,
            evidence=evidence,
            phase_events=phase_events,
        )
        query_failure = _contact_target_query_validation_failure(
            command,
            contact,
            visible_rows,
            evidence=evidence,
        )
        if query_failure is not None:
            return query_failure
        candidates = _visible_contact_candidates_from_nodes(
            _query_nodes(visible_rows),
            contact,
            snapshot_id=_query_snapshot_id(_query_payload(visible_rows)),
        )
        if len(candidates) > 1:
            return _contact_candidates_ambiguity_failure(
                command,
                contact,
                candidates,
                evidence=evidence,
            )
        if not candidates:
            return None
        element = candidates[0].get("element")
        if not isinstance(element, Mapping):
            return _contact_target_unverified_failure(
                command,
                contact,
                reason="visible_candidate_element_invalid",
                evidence=evidence,
            )
        if not _node_frame_within_query_window(element, visible_rows):
            return _contact_target_unverified_failure(
                command,
                contact,
                reason="visible_candidate_frame_invalid",
                evidence=evidence,
            )
        action_ref = candidates[0].get("actionRef")
        expected_action = "AXPress"
        if isinstance(action_ref, Mapping):
            expected_action = (
                _optional_string_from_mapping(action_ref, "action") or "AXPress"
            )
            opened = self._execute_action_ref(
                command,
                action_ref,
                phase="open_visible_contact",
                evidence=evidence,
                phase_events=phase_events,
            )
        else:
            opened = self._click_node_phase(
                command,
                element,
                phase="open_visible_contact",
                evidence=evidence,
                snapshot_id=_query_snapshot_id(_query_payload(visible_rows)),
                phase_events=phase_events,
            )
        if not opened.success:
            if _should_fallback_from_accessibility_action(
                opened,
                expected_action=expected_action,
            ):
                return None
            if opened.tool == WECHAT_TOOL:
                return opened
            return _from_app_control_failure(
                command,
                _execute_action_failure_kind(opened),
                opened,
                evidence=evidence,
            )
        return self._opened_contact_observation(
            command,
            contact=contact,
            main_content=(
                self._mapped_region_node(
                    "chatPanel",
                    reference_ax_path=_node_ax_path(main_content),
                )
                or main_content
            ),
            open_method="visible_action_ref",
            evidence=evidence,
            phase_events=phase_events,
        )

    def _open_visible_contact_with_control_map(
        self,
        command: ToolCommand,
        *,
        contact: str,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        collection_query = self._query_mapped_conversation_target(
            command,
            contact,
            evidence=evidence,
            phase_events=phase_events,
        )
        if collection_query is None:
            return None
        query_result, _collection, nodes = collection_query
        query_failure = _contact_target_query_validation_failure(
            command,
            contact,
            query_result,
            evidence=evidence,
        )
        if query_failure is not None:
            return query_failure
        candidates = _visible_contact_candidates_from_nodes(
            nodes,
            contact,
            snapshot_id=_query_snapshot_id(_query_payload(query_result)),
        )
        if len(candidates) > 1:
            return _contact_candidates_ambiguity_failure(
                command,
                contact,
                candidates,
                evidence=evidence,
                source={
                    "mode": "control_map",
                    "mapId": self._control_map.map_id,
                    "mapVersion": self._control_map.map_version,
                },
            )
        if not candidates:
            return None
        element = candidates[0].get("element")
        if not isinstance(element, Mapping):
            return _contact_target_unverified_failure(
                command,
                contact,
                reason="mapped_candidate_element_invalid",
                evidence=evidence,
            )
        if not _node_frame_within_query_window(element, query_result):
            return _contact_target_unverified_failure(
                command,
                contact,
                reason="mapped_candidate_frame_invalid",
                evidence=evidence,
            )
        action_ref = candidates[0].get("actionRef")
        expected_action = "AXPress"
        if isinstance(action_ref, Mapping):
            expected_action = (
                _optional_string_from_mapping(action_ref, "action") or "AXPress"
            )
            opened = self._execute_action_ref(
                command,
                action_ref,
                phase="control_map_open_visible_contact",
                evidence=evidence,
                phase_events=phase_events,
            )
        else:
            opened = self._click_node_phase(
                command,
                element,
                phase="control_map_open_visible_contact",
                evidence=evidence,
                snapshot_id=_query_snapshot_id(_query_payload(query_result)),
                phase_events=phase_events,
            )
        if not opened.success:
            if _should_fallback_from_accessibility_action(
                opened,
                expected_action=expected_action,
            ):
                return None
            if opened.tool == WECHAT_TOOL:
                return opened
            return _from_app_control_failure(
                command,
                _execute_action_failure_kind(opened),
                opened,
                evidence=evidence,
            )
        return self._opened_contact_observation(
            command,
            contact=contact,
            main_content=(
                self._mapped_region_node(
                    "chatPanel",
                    reference_ax_path=_node_ax_path(element),
                )
                or {"axPath": "0/12/4"}
            ),
            open_method="control_map_visible_action_ref",
            evidence=evidence,
            phase_events=phase_events,
        )

    def _opened_contact_observation(
        self,
        command: ToolCommand,
        *,
        contact: str,
        main_content: Mapping[str, Any],
        open_method: str,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        verification_roots: list[dict[str, Any]] = [dict(main_content)]
        chat_panel = self._control_map.regions.get("chatPanel")
        known_paths = {_node_ax_path(main_content)}
        if chat_panel is not None:
            for ax_path in chat_panel.ax_paths:
                if ax_path in known_paths:
                    continue
                known_paths.add(ax_path)
                verification_roots.append(
                    {
                        "axPath": ax_path,
                        "role": chat_panel.role,
                    }
                )

        verification: ToolObservation | None = None
        successful_verification: ToolObservation | None = None
        chat_title: str | None = None
        for index, root_node in enumerate(verification_roots):
            phase = "verify_contact" if index == 0 else f"verify_contact:{index}"
            candidate = self._query_accessibility_nodes(
                command,
                root_node=root_node,
                phase=phase,
                scope="descendants",
                max_depth=2,
                role_in=["AXStaticText"],
                limit=20,
                time_budget_ms=1_200,
                attributes=[
                    "AXRole",
                    "AXDescription",
                    "AXTitle",
                    "AXValue",
                    "AXFrame",
                ],
                actions=False,
                evidence=evidence,
                phase_events=phase_events,
            )
            verification = candidate
            if not candidate.success:
                continue
            successful_verification = candidate
            chat_title = _chat_title_from_query_nodes(_query_nodes(candidate))
            if chat_title is not None:
                break

        verification = successful_verification or verification
        if verification is None or not verification.success:
            return _from_app_control_failure(
                command,
                "contact_not_found",
                verification
                or _failure(
                    command,
                    status=ToolStatus.NOT_FOUND,
                    failure_kind="query_root_not_found",
                    message="Could not locate a WeChat chat panel.",
                    retryable=True,
                ),
                evidence=evidence,
            )
        confidence = _contact_confidence(contact, chat_title)
        if chat_title is None or confidence < 0.9:
            actual_title = chat_title or "unknown"
            return _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="contact_not_found",
                message=(
                    "Verified WeChat chat title does not match requested contact: "
                    f"{actual_title}"
                ),
                recovery_hint=(
                    "Return to the WeChat chats view and retry opening the target "
                    "contact."
                ),
                retryable=True,
                observation={
                    "schema": "wechat.open_contact.v1",
                    "target": contact,
                    "status": "not_opened",
                    "openMethod": open_method,
                    "currentChat": {"title": chat_title},
                },
                evidence=evidence,
            )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Opened WeChat contact.",
            observation={
                "schema": "wechat.open_contact.v1",
                "target": contact,
                "status": "opened",
                "openMethod": open_method,
                "currentChat": {"title": chat_title},
                "confidence": confidence,
                "availableActions": [
                    {"id": "wechat.read_visible_messages", "status": "available"},
                    {"id": "wechat.draft_message", "status": "needs_input"},
                ],
            },
            evidence=evidence,
        )

    def _focus_search_box_phase(
        self,
        command: ToolCommand,
        *,
        contact: str,
        search_box: Any,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        search_element = search_box.elements[0]
        coordinate_verified = self._focus_search_box_coordinate_fallback(
            command,
            contact=contact,
            search_element=search_element,
            evidence=evidence,
            phase_events=phase_events,
        )
        if coordinate_verified is not None:
            return coordinate_verified

        action_verified = self._focus_search_box_accessibility_action(
            command,
            contact=contact,
            search_element=search_element,
            evidence=evidence,
            phase_events=phase_events,
        )
        if action_verified is not None:
            return action_verified

        clicked = self._app_control_command(
            command,
            phase="click_search_box",
            operation="click",
            input=self._target_app_input(
                selector={
                    "role": search_element.role,
                    "name": search_element.label or "搜索",
                },
            ),
            phase_events=phase_events,
        )
        evidence["click_search_box"] = _safe_app_control_observation(clicked)
        if clicked.success:
            verified_after_click = self._verify_search_focus_phase(
                command,
                phase="verify_search_focus_after_click",
                search_element=search_element,
                phase_events=phase_events,
            )
            evidence["verify_search_focus_after_click"] = (
                _safe_app_control_observation(verified_after_click)
            )
            if verified_after_click.success:
                click_focus_failure = _search_focus_failure(
                    command,
                    contact,
                    verified_after_click,
                    evidence=evidence,
                )
                if click_focus_failure is None:
                    return verified_after_click
                return click_focus_failure
            return _from_app_control_failure(
                command,
                "search_focus_failed",
                verified_after_click,
                evidence=evidence,
            )
        return _from_app_control_failure(
            command,
            "search_focus_failed",
            clicked,
            evidence=evidence,
        )

    def _focus_search_box_accessibility_action(
        self,
        command: ToolCommand,
        *,
        contact: str,
        search_element: Any,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        element_ref = getattr(search_element, "element_ref", None)
        ax_path = getattr(element_ref, "ax_path", None)
        if not isinstance(ax_path, str) or not ax_path:
            return None
        preconditions: dict[str, JsonValue] = {
            "roleIn": [str(search_element.role)],
            "actionIn": ["AXSetFocus"],
        }
        if search_element.label:
            preconditions["labelIn"] = [str(search_element.label)]
        input_payload = self._target_app_input(
            target={"kind": "axPath", "axPath": ax_path},
            action="AXSetFocus",
            preconditions=preconditions,
        )
        snapshot_id = getattr(element_ref, "snapshot_id", None)
        if isinstance(snapshot_id, str) and snapshot_id:
            input_payload["snapshotId"] = snapshot_id
        focused = self._app_control_command(
            command,
            phase="focus_search_box_accessibility_action",
            operation="accessibility_action",
            input=input_payload,
            phase_events=phase_events,
        )
        evidence["focus_search_box_accessibility_action"] = (
            _safe_app_control_observation(focused)
        )
        if not focused.success:
            if _should_fallback_from_accessibility_action(
                focused,
                expected_action="AXSetFocus",
            ):
                return None
            return _from_app_control_failure(
                command,
                "search_focus_failed",
                focused,
                evidence=evidence,
            )
        verified = self._verify_search_focus_phase(
            command,
            phase="verify_search_focus_after_accessibility_action",
            search_element=search_element,
            phase_events=phase_events,
        )
        evidence["verify_search_focus_after_accessibility_action"] = (
            _safe_app_control_observation(verified)
        )
        if not verified.success:
            return _from_app_control_failure(
                command,
                "search_focus_failed",
                verified,
                evidence=evidence,
            )
        focus_failure = _search_focus_failure(
            command,
            contact,
            verified,
            evidence=evidence,
        )
        if focus_failure is not None:
            return focus_failure
        return verified

    def _focus_search_box_coordinate_fallback(
        self,
        command: ToolCommand,
        *,
        contact: str,
        search_element: Any,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        coordinates = _selector_element_center_coordinates(search_element)
        if coordinates is None:
            return None
        clicked = self._app_control_command(
            command,
            phase="click_search_box_coordinate",
            operation="click",
            input=self._target_app_input(coordinates=coordinates),
            command_metadata={
                "coordinateSource": "accessibility_frame",
            },
            phase_events=phase_events,
        )
        evidence["click_search_box_coordinate"] = _safe_app_control_observation(clicked)
        if not clicked.success:
            if _coordinate_click_disabled(clicked):
                return None
            return _from_app_control_failure(
                command,
                "search_focus_failed",
                clicked,
                evidence=evidence,
            )
        verified = self._verify_search_focus_phase(
            command,
            phase="verify_search_focus_after_coordinate",
            search_element=search_element,
            phase_events=phase_events,
        )
        evidence["verify_search_focus_after_coordinate"] = (
            _safe_app_control_observation(verified)
        )
        if not verified.success:
            return _from_app_control_failure(
                command,
                "search_focus_failed",
                verified,
                evidence=evidence,
            )
        coordinate_focus_failure = _search_focus_failure(
            command,
            contact,
            verified,
            evidence=evidence,
        )
        if coordinate_focus_failure is not None:
            return coordinate_focus_failure
        return verified

    def _verify_search_focus_phase(
        self,
        command: ToolCommand,
        *,
        phase: str,
        search_element: Any,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        element_ref = getattr(search_element, "element_ref", None)
        ax_path = getattr(element_ref, "ax_path", None)
        if isinstance(ax_path, str) and ax_path:
            return self._app_control_command(
                command,
                phase=phase,
                operation="accessibility_query",
                input=self._accessibility_query_input(
                    root={"kind": "axPath", "axPath": ax_path},
                    query={
                        "scope": "self",
                        "maxDepth": 0,
                        "limit": 1,
                        "timeBudgetMs": _SEARCH_FOCUS_QUERY_TIMEOUT_MS,
                        "attributes": [
                            "AXRole",
                            "AXDescription",
                            "AXTitle",
                            "AXValue",
                            "AXPlaceholderValue",
                            "AXFocused",
                            "AXEnabled",
                            "AXFrame",
                        ],
                        "actions": False,
                        "includeChildrenCount": False,
                        "match": {"roleIn": [str(search_element.role)]},
                    },
                ),
                timeout_ms=_SEARCH_FOCUS_QUERY_TIMEOUT_MS,
                phase_events=phase_events,
            )
        return self._app_control_command(
            command,
            phase=phase,
            operation="observe",
            input=self._target_app_input(
                includeAccessibility=True,
                includeVisibleText=True,
            ),
            phase_events=phase_events,
        )

    def _execute_action(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        action_ref = _action_ref_input(command)
        action_id = _optional_string_from_mapping(action_ref, "id") or "unknown"
        evidence: dict[str, JsonValue] = {}
        result = self._execute_action_ref(
            command,
            action_ref,
            phase="execute_action",
            evidence=evidence,
            phase_events=phase_events,
        )
        if not result.success:
            if result.tool == WECHAT_TOOL:
                return result
            return _from_app_control_failure(
                command,
                _execute_action_failure_kind(result),
                result,
                evidence=evidence,
            )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Executed WeChat action.",
            observation={
                "schema": "wechat.execute_action.v1",
                "status": "ok",
                "actionId": action_id,
                "method": _executed_action_method(action_ref, result),
                "result": _safe_executed_action_result(result),
            },
            evidence=evidence,
        )

    def _read_contact_messages(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        contact = _required_input(command, "contact")
        limit = _positive_int(command.input.get("limit"), default=30)
        opened = self._open_contact(
            self._command("open_contact", {"contact": contact}, parent=command),
            phase_events=phase_events,
        )
        if not opened.success:
            return _nested_failure(command, "open_contact", opened)
        messages = self._read_visible_messages(
            self._command(
                "read_visible_messages",
                {"limit": limit},
                parent=command,
            ),
            phase_events=phase_events,
        )
        if not messages.success:
            return _nested_failure(command, "read_visible_messages", messages)
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Opened WeChat contact and read visible messages.",
            observation={
                "schema": "wechat.contact_messages.v1",
                "target": contact,
                "openContact": opened.observation,
                "messages": messages.observation,
            },
            evidence={
                "openContact": opened.to_dict(),
                "readVisibleMessages": messages.to_dict(),
            },
        )

    def _focus_contact(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        contact = _required_input(command, "contact")
        opened = self._open_contact(
            self._command("open_contact", {"contact": contact}, parent=command),
            phase_events=phase_events,
        )
        if not opened.success:
            return _nested_failure(command, "open_contact", opened)

        current_chat = opened.observation.get("currentChat")
        current_chat_title = (
            _string_value(current_chat.get("title"))
            if isinstance(current_chat, Mapping)
            else None
        )
        confidence = opened.observation.get("confidence")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            confidence = _contact_confidence(contact, current_chat_title)
        environment: dict[str, JsonValue] = {
            "configuredAppName": self._config.app_name,
            "frontmostApp": self._config.app_name,
        }
        if self._config.bundle_id is not None:
            environment["configuredBundleId"] = self._config.bundle_id
            environment["frontmostBundleId"] = self._config.bundle_id
        if current_chat_title is not None:
            environment["windowTitle"] = current_chat_title

        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Focused WeChat contact through verified open_contact.",
            observation={
                "focusedContact": contact,
                "confidence": float(confidence),
                "appName": self._config.app_name,
                "bundleId": self._config.bundle_id,
                "frontmostApp": self._config.app_name,
                "windowTitle": current_chat_title,
                "currentChatTitle": current_chat_title,
                "wechatEnvironment": environment,
                "openContact": opened.observation,
            },
            evidence={"openContact": opened.to_dict()},
        )

    def _focus_contact_legacy(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        contact = _required_input(command, "contact")
        evidence: dict[str, JsonValue] = {}
        opened = self._app_control_command(
            command,
            phase="open_wechat",
            operation="open_app",
            input=self._open_app_input(),
            phase_events=phase_events,
        )
        evidence["open_wechat"] = _safe_app_control_observation(opened)
        if not opened.success:
            return _from_app_control_failure(
                command,
                "wechat_open_failed",
                opened,
                evidence=evidence,
            )
        ready = self._app_control_command(
            command,
            phase="verify_wechat_window",
            operation="observe",
            input=self._target_app_input(),
            phase_events=phase_events,
        )
        evidence["verify_wechat_window"] = _safe_app_control_observation(ready)
        if not ready.success:
            return _from_app_control_failure(
                command,
                "wechat_not_ready",
                ready,
                evidence=evidence,
            )
        identity_failure = _wechat_identity_failure(
            command,
            self._config,
            ready,
            evidence=evidence,
        )
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(
            command,
            self._config,
            ready,
            evidence=evidence,
        )
        if login_failure is not None:
            return login_failure
        phases = (
            (
                "focus_search",
                "hotkey",
                self._target_app_input(
                    keys=list(self._config.search_hotkey),
                ),
            ),
            (
                "verify_search_focus",
                "observe",
                self._target_app_input(
                    includeAccessibility=True,
                    includeVisibleText=True,
                ),
            ),
            (
                "select_search_text",
                "hotkey",
                self._target_app_input(
                    keys=list(self._config.search_clear_hotkey),
                ),
            ),
            (
                "clear_search_text",
                "press_key",
                self._target_app_input(key=self._config.clear_key),
            ),
            (
                "type_contact",
                "type_text",
                self._target_app_input(text=contact),
            ),
            (
                "select_contact",
                "press_key",
                self._target_app_input(key=self._config.submit_key),
            ),
        )
        for phase, operation, input_payload in phases:
            result = self._app_control_command(
                command,
                phase=phase,
                operation=operation,
                input=input_payload,
                phase_events=phase_events,
            )
            evidence[phase] = _safe_app_control_observation(result)
            if not result.success:
                return _from_app_control_failure(
                    command,
                    "contact_not_found",
                    result,
                    evidence=evidence,
                )
            if phase == "verify_search_focus":
                search_focus_failure = _search_focus_failure(
                    command,
                    contact,
                    result,
                    evidence=evidence,
                )
                if search_focus_failure is not None:
                    return search_focus_failure
            if phase in {"type_contact", "select_contact"}:
                ambiguity_failure = _contact_ambiguity_failure(
                    command,
                    contact,
                    result,
                    evidence=evidence,
                )
                if ambiguity_failure is not None:
                    return ambiguity_failure
        verification = self._app_control_command(
            command,
            phase="verify_contact",
            operation="observe",
            input=self._target_app_input(includeVisibleText=True),
            phase_events=phase_events,
        )
        evidence["verify_contact"] = _safe_app_control_observation(verification)
        if not verification.success:
            return _from_app_control_failure(
                command,
                "wechat_window_unavailable",
                verification,
                evidence=evidence,
            )
        identity_failure = _wechat_identity_failure(
            command,
            self._config,
            verification,
            evidence=evidence,
        )
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(
            command,
            self._config,
            verification,
            evidence=evidence,
        )
        if login_failure is not None:
            return login_failure
        ambiguity_failure = _contact_ambiguity_failure(
            command,
            contact,
            verification,
            evidence=evidence,
        )
        if ambiguity_failure is not None:
            return ambiguity_failure
        window_title = _string_from_observation(
            verification,
            "windowTitle",
            "window_title",
            "title",
        )
        frontmost_app = _string_from_observation(
            verification,
            "frontmostApp",
            "frontmost_app",
            "appName",
            "app_name",
        )
        current_chat_title = _current_chat_title(window_title, self._config.app_name)
        confidence = _contact_confidence(contact, current_chat_title)
        if current_chat_title is not None and confidence < 0.9:
            return _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="contact_not_found",
                message=(
                    "Verified WeChat chat title does not match requested contact: "
                    f"{current_chat_title}"
                ),
                retryable=True,
                evidence=evidence,
            )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Focused WeChat contact.",
            observation={
                "focusedContact": contact,
                "confidence": confidence,
                "appName": self._config.app_name,
                "bundleId": self._config.bundle_id,
                "frontmostApp": frontmost_app or self._config.app_name,
                "windowTitle": window_title or self._config.app_name,
                "currentChatTitle": current_chat_title,
                "wechatEnvironment": _wechat_environment(
                    self._config,
                    verification,
                ),
            },
            evidence=evidence,
        )

    def _observe_current_chat(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        include_visible_messages = _bool_input(
            command,
            "includeVisibleMessages",
            "include_visible_messages",
            default=True,
        )
        input_payload = self._target_app_input()
        if include_visible_messages:
            input_payload["includeVisibleText"] = True
        result = self._app_control_command(
            command,
            phase="observe_current_chat",
            operation="observe",
            input=input_payload,
            phase_events=phase_events,
        )
        if not result.success:
            return _from_app_control_failure(command, "wechat_not_ready", result)
        identity_failure = _wechat_identity_failure(command, self._config, result)
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(command, self._config, result)
        if login_failure is not None:
            return login_failure
        messages = _messages_from_observation(result, limit=20)
        window_title = _string_from_observation(
            result,
            "windowTitle",
            "window_title",
            "title",
        )
        frontmost_app = _string_from_observation(
            result,
            "frontmostApp",
            "frontmost_app",
            "appName",
            "app_name",
        )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Observed current WeChat chat.",
            observation={
                "appName": self._config.app_name,
                "bundleId": self._config.bundle_id,
                "frontmostApp": frontmost_app or self._config.app_name,
                "windowTitle": window_title,
                "currentChatTitle": _current_chat_title(
                    window_title,
                    self._config.app_name,
                ),
                "wechatEnvironment": _wechat_environment(self._config, result),
                "visibleMessages": [message.to_dict() for message in messages],
                "messageCount": len(messages),
                "appControlObservation": _safe_app_control_observation(result),
            },
            evidence={"observe": _safe_app_control_observation(result)},
        )

    def _read_visible_messages(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        limit = _positive_int(command.input.get("limit"), default=20)
        evidence: dict[str, JsonValue] = {}
        opened = self._open_wechat_phase(command, evidence, phase_events=phase_events)
        if not opened.success:
            return _open_wechat_phase_failure(command, opened, evidence)
        fast_messages = self._read_visible_messages_with_control_map(
            command,
            limit=limit,
            evidence=evidence,
            phase_events=phase_events,
        )
        if fast_messages is not None:
            return fast_messages
        selector_runner = _WeChatSelectorQueryRunner(
            self,
            command,
            evidence=evidence,
            phase_prefix="selectors.messages",
            phase_events=phase_events,
        )
        resolver = build_packaged_selector_resolver(
            selector_runner,
            app_bundle_id=self._config.bundle_id or "",
            selector_profile=self._selector_profile,
        )
        chat_panel = resolver.resolve("regions.chatPanel")
        if chat_panel.status != "resolved" or not chat_panel.elements:
            return _failure_from_selector_result(
                command,
                chat_panel,
                failure_kind="message_region_not_found",
                message="Could not locate WeChat chat panel region.",
                evidence=evidence,
            )
        messages_result = self._query_descendants(
            command,
            root_node=_node_from_selector_element(chat_panel.elements[0]),
            phase="read_visible_messages:rows",
            role_in=["AXRow", "AXCell", "AXStaticText"],
            limit=max(limit * 4, 80),
            evidence=evidence,
            phase_events=phase_events,
        )
        if not messages_result.success:
            return _from_app_control_failure(
                command,
                "message_region_not_found",
                messages_result,
                evidence=evidence,
            )
        query_nodes = _query_nodes(messages_result)
        messages = _messages_from_query_nodes(query_nodes, limit=limit)
        chat_title = _chat_title_from_query_nodes(query_nodes)
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Read visible WeChat messages.",
            observation={
                "schema": "wechat.messages.v1",
                "chat": {"title": chat_title},
                "messages": messages,
                "pagination": {
                    "limit": limit,
                    "canReadOlder": _query_truncated(messages_result),
                    "olderPageToken": _next_page_token(
                        "messages",
                        messages_result,
                        direction="older",
                    ),
                },
                "truncated": _query_truncated(messages_result),
            },
            evidence=evidence,
        )

    def _read_visible_messages_with_control_map(
        self,
        command: ToolCommand,
        *,
        limit: int,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation | None:
        collection_query = self._query_mapped_collection(
            command,
            "visibleMessages",
            semantic_limit=limit,
            evidence=evidence,
            phase_events=phase_events,
        )
        if collection_query is None:
            return None
        query_result, collection, nodes = collection_query
        messages = _messages_from_query_nodes(nodes, limit=limit)
        if not messages and nodes:
            return None
        chat_title = _chat_title_from_query_nodes(nodes)
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Read visible WeChat messages.",
            observation={
                "schema": "wechat.messages.v1",
                "chat": {"title": chat_title},
                "messages": messages,
                "pagination": {
                    "limit": limit,
                    "canReadOlder": _query_truncated(query_result),
                    "olderPageToken": _next_page_token(
                        "messages",
                        query_result,
                        direction="older",
                    ),
                },
                "source": {
                    "mode": "control_map",
                    "mapId": self._control_map.map_id,
                    "mapVersion": self._control_map.map_version,
                    "collection": collection.collection_id,
                },
                "truncated": _query_truncated(query_result),
            },
            evidence=evidence,
        )

    def _draft_message(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        message = _required_input(command, "message")
        if len(message) > self._config.max_message_chars:
            return _failure(
                command,
                status=ToolStatus.FAILED,
                failure_kind="draft_failed",
                message="message exceeds max_message_chars",
            )
        result = self._app_control_command(
            command,
            phase="draft_message",
            operation="type_text",
            input=self._target_app_input(text=message),
            phase_events=phase_events,
        )
        if not result.success:
            input_focus_failure = _input_focus_failure(command, result)
            if input_focus_failure is not None:
                return input_focus_failure
            return _from_app_control_failure(command, "draft_failed", result)
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Drafted WeChat message without submitting.",
            observation={
                "draftReady": True,
                "messageHash": wechat_message_hash(message),
                "messageChars": len(message),
            },
            evidence={"draft": _safe_app_control_observation(result)},
        )

    def _submit_draft(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        method = _string_input(command, "method", default="keyboard_return")
        if method != "keyboard_return":
            return _failure(
                command,
                status=ToolStatus.FAILED,
                failure_kind="submit_failed",
                message=f"unsupported submit method: {method}",
            )
        result = self._app_control_command(
            command,
            phase="submit_draft",
            operation="press_key",
            input=self._target_app_input(key=self._config.submit_key),
            phase_events=phase_events,
        )
        if not result.success:
            return _failure(
                command,
                status=ToolStatus.UNKNOWN,
                failure_kind="submit_unknown",
                message="WeChat submit result is unknown; review manually.",
                recovery_hint="Check WeChat manually before retrying.",
                retryable=False,
                observation={
                    "sendAttempted": True,
                    "method": method,
                },
                evidence={"submit": _safe_app_control_observation(result)},
            )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Submitted WeChat draft with keyboard Return.",
            observation={
                "submitted": True,
                "sendAttempted": True,
                "method": method,
            },
            evidence={"submit": _safe_app_control_observation(result)},
        )

    def _send_message(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        contact = _required_input(command, "contact")
        message = _required_input(command, "message")
        verify_after_submit = _bool_input(
            command,
            "verifyAfterSubmit",
            "verify_after_submit",
            default=False,
        )
        verify_limit = _positive_int(command.input.get("verifyLimit"), default=20)
        focus = self._focus_contact(
            self._command("focus_contact", {"contact": contact}, parent=command),
            phase_events=phase_events,
        )
        if not focus.success:
            return _nested_failure(command, "focus_contact", focus)
        draft = self._draft_message(
            self._command("draft_message", {"message": message}, parent=command),
            phase_events=phase_events,
        )
        if not draft.success:
            return _nested_failure(command, "draft_message", draft)
        submitted = self._submit_draft(
            self._command(
                "submit_draft",
                {"method": "keyboard_return"},
                parent=command,
            ),
            phase_events=phase_events,
        )
        if not submitted.success:
            return _nested_failure(command, "submit_draft", submitted)
        verification: ToolObservation | None = None
        verified = False
        if verify_after_submit:
            verification = self._read_visible_messages(
                self._command(
                    "read_visible_messages",
                    {"limit": verify_limit},
                    parent=command,
                ),
                phase_events=phase_events,
            )
            if not verification.success:
                return _send_unverified(
                    command,
                    contact=contact,
                    message=message,
                    focus=focus,
                    draft=draft,
                    submitted=submitted,
                    verification=verification,
                    reason=verification.summary,
                )
            verified = _message_observed(message, verification)
            if not verified:
                return _send_unverified(
                    command,
                    contact=contact,
                    message=message,
                    focus=focus,
                    draft=draft,
                    submitted=submitted,
                    verification=verification,
                    reason="Submitted message was not visible after send.",
                )
        evidence: dict[str, JsonValue] = {
            "focus": focus.to_dict(),
            "draft": draft.to_dict(),
            "submit": submitted.to_dict(),
        }
        if verification is not None:
            evidence["verification"] = verification.to_dict()
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Completed WeChat send-message convenience flow.",
            observation={
                "focusedContact": contact,
                "messageHash": wechat_message_hash(message),
                "submitted": True,
                "verified": verified,
                "verificationRequested": verify_after_submit,
            },
            evidence=evidence,
        )

    def _app_control_command(
        self,
        parent: ToolCommand,
        *,
        phase: str,
        operation: str,
        input: dict[str, JsonValue],
        timeout_ms: int | None = None,
        command_metadata: Mapping[str, JsonValue] | None = None,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        metadata: dict[str, JsonValue] = {
            "sourceTool": WECHAT_TOOL,
            "parentCommandId": parent.command_id,
            "phase": phase,
        }
        if command_metadata is not None:
            metadata.update(command_metadata)
        observation = self._app_control.run_command(
            ToolCommand(
                command_id=f"{parent.command_id}:{phase}",
                tool=self._config.app_control_tool,
                operation=operation,
                input=input,
                timeout_ms=(
                    timeout_ms
                    if timeout_ms is not None
                    else parent.timeout_ms or self._config.default_timeout_ms
                ),
                metadata=metadata,
            )
        )
        if phase_events is not None:
            phase_events.emit(
                parent=parent,
                phase=phase,
                operation=operation,
                observation=observation,
            )
        return observation

    def _open_wechat_phase(
        self,
        command: ToolCommand,
        evidence: dict[str, JsonValue],
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        opened = self._app_control_command(
            command,
            phase="open_wechat",
            operation="open_app",
            input=self._open_app_input(),
            phase_events=phase_events,
        )
        evidence["open_wechat"] = _safe_app_control_observation(opened)
        if not opened.success:
            return opened
        ready = self._app_control_command(
            command,
            phase="verify_wechat_window",
            operation="observe",
            input=self._target_app_input(),
            phase_events=phase_events,
        )
        evidence["verify_wechat_window"] = _safe_app_control_observation(ready)
        if not ready.success or not _wechat_observation_has_window_title(ready):
            focused = self._app_control_command(
                command,
                phase="focus_wechat",
                operation="focus_app",
                input=self._open_app_input(),
                phase_events=phase_events,
            )
            evidence["focus_wechat"] = _safe_app_control_observation(focused)
            if not focused.success:
                return focused
            ready = self._app_control_command(
                command,
                phase="verify_wechat_window_after_focus",
                operation="observe",
                input=self._target_app_input(),
                phase_events=phase_events,
            )
            evidence["verify_wechat_window_after_focus"] = (
                _safe_app_control_observation(ready)
            )
        if not ready.success:
            return ready
        if not _wechat_observation_has_window_title(ready):
            verified_window = self._app_control_command(
                command,
                phase="verify_wechat_accessibility_window",
                operation="accessibility_query",
                input=self._accessibility_query_input(
                    root={"kind": "focusedWindow"},
                    query={
                        "scope": "self",
                        "maxDepth": 0,
                        "limit": 1,
                        "timeBudgetMs": 2_000,
                        "attributes": ["AXRole", "AXTitle"],
                        "actions": False,
                        "includeChildrenCount": False,
                    },
                ),
                phase_events=phase_events,
            )
            evidence["verify_wechat_accessibility_window"] = (
                _safe_app_control_observation(verified_window)
            )
            ready = _ready_observation_with_accessibility_window_title(
                ready,
                verified_window,
                self._config.app_name,
            )
        if not _wechat_observation_has_window_title(ready):
            return _wechat_not_ready_failure(
                command,
                "WeChat is frontmost but no focused window is available.",
                evidence=evidence,
            )
        identity_failure = _wechat_identity_failure(
            command,
            self._config,
            ready,
            evidence=evidence,
        )
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(
            command,
            self._config,
            ready,
            evidence=evidence,
        )
        if login_failure is not None:
            return login_failure
        return ready

    def _accessibility_query_input(
        self,
        *,
        root: Mapping[str, JsonValue],
        query: Mapping[str, JsonValue],
        include_raw: bool = False,
    ) -> dict[str, JsonValue]:
        return self._target_app_input(
            root=dict(root),
            query=dict(query),
            includeRaw=include_raw,
        )

    def _query_top_level(
        self,
        command: ToolCommand,
        evidence: dict[str, JsonValue],
        *,
        phase: str = "query_top_level",
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        result = self._app_control_command(
            command,
            phase=phase,
            operation="accessibility_query",
            input=self._accessibility_query_input(
                root={"kind": "focusedWindow"},
                query={
                    "scope": "children",
                    "maxDepth": 1,
                    "limit": 80,
                    "timeBudgetMs": 10_000,
                    "attributes": _QUERY_ATTRIBUTES,
                    "actions": True,
                    "includeChildrenCount": False,
                },
            ),
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        return result

    def _query_children(
        self,
        command: ToolCommand,
        *,
        root_node: Mapping[str, Any],
        phase: str,
        role_in: list[str],
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        return self._query_accessibility_nodes(
            command,
            root_node=root_node,
            phase=phase,
            scope="children",
            max_depth=1,
            role_in=role_in,
            limit=80,
            evidence=evidence,
            phase_events=phase_events,
        )

    def _query_descendants(
        self,
        command: ToolCommand,
        *,
        root_node: Mapping[str, Any] | None,
        phase: str,
        role_in: list[str],
        limit: int,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        if root_node is None:
            return _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="query_root_not_found",
                message="Could not locate query root.",
                retryable=True,
                evidence=evidence,
            )
        return self._query_accessibility_nodes(
            command,
            root_node=root_node,
            phase=phase,
            scope="descendants",
            max_depth=4,
            role_in=role_in,
            limit=limit,
            evidence=evidence,
            phase_events=phase_events,
        )

    def _query_accessibility_nodes(
        self,
        command: ToolCommand,
        *,
        root_node: Mapping[str, Any],
        phase: str,
        scope: str,
        max_depth: int,
        role_in: list[str],
        limit: int,
        evidence: dict[str, JsonValue],
        time_budget_ms: int | None = None,
        attributes: list[str] | None = None,
        actions: bool = True,
        match: Mapping[str, JsonValue] | None = None,
        root_resolver: WeChatRootResolver | None = None,
        prefer_visible_rows: bool = False,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        ax_path = _node_ax_path(root_node)
        if ax_path is None:
            return _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="query_root_not_found",
                message="Query root does not have an axPath.",
                retryable=True,
                evidence=evidence,
            )
        root_payload: dict[str, JsonValue] = {"kind": "axPath", "axPath": ax_path}
        if root_resolver is not None:
            root_payload["resolver"] = _root_resolver_payload(root_resolver)
        query_attributes: list[JsonValue] = [
            str(attribute) for attribute in (attributes or _QUERY_ATTRIBUTES)
        ]
        query_roles: list[JsonValue] = [str(role) for role in role_in]
        query_match: dict[str, JsonValue] = {"roleIn": query_roles}
        if match is not None:
            query_match.update(dict(match))
        query_payload: dict[str, JsonValue] = {
            "scope": scope,
            "maxDepth": max_depth,
            "limit": limit,
            "timeBudgetMs": time_budget_ms
            if time_budget_ms is not None
            else (8_000 if scope == "descendants" else 5_000),
            "attributes": query_attributes,
            "actions": actions,
            "includeChildrenCount": False,
            "match": query_match,
        }
        if prefer_visible_rows:
            query_payload["preferVisibleRows"] = True
        result = self._app_control_command(
            command,
            phase=phase,
            operation="accessibility_query",
            input=self._accessibility_query_input(
                root=root_payload,
                query=query_payload,
            ),
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        return result

    def _click_node_phase(
        self,
        command: ToolCommand,
        node: Mapping[str, Any],
        *,
        phase: str,
        evidence: dict[str, JsonValue],
        snapshot_id: str | None = None,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        role = str(node.get("role") or "")
        node_label = _node_label(node)
        if role == "AXRow" and node_label is None:
            return _failure(
                command,
                status=ToolStatus.FAILED,
                failure_kind="wechat_action_target_unverified",
                message="Could not verify the identity of the WeChat row target.",
                recovery_hint="Refresh the WeChat list and retry the semantic action.",
                retryable=True,
                evidence=evidence,
            )
        if role == "AXRow" and "AXPress" not in _node_actions(node):
            coordinates = _node_center_coordinates(node)
            if coordinates is not None:
                coordinate_phase = f"{phase}:coordinate"
                coordinate_result = self._app_control_command(
                    command,
                    phase=coordinate_phase,
                    operation="click",
                    input=self._target_app_input(coordinates=coordinates),
                    command_metadata={
                        "coordinateSource": "accessibility_frame",
                    },
                    phase_events=phase_events,
                )
                evidence[coordinate_phase] = _safe_app_control_observation(
                    coordinate_result
                )
                if coordinate_result.success:
                    return coordinate_result
                if not _coordinate_click_disabled(coordinate_result):
                    return coordinate_result
        action_ref = _action_ref_from_node(node, snapshot_id=snapshot_id)
        if action_ref is not None:
            expected_action = (
                _optional_string_from_mapping(action_ref, "action") or "AXPress"
            )
            result = self._execute_action_ref(
                command,
                action_ref,
                phase=phase,
                evidence=evidence,
                phase_events=phase_events,
            )
            if result.success:
                return result
            if _should_try_coordinate_click_after_accessibility_action(
                result,
                expected_action=expected_action,
            ):
                coordinates = _node_center_coordinates(node)
                if coordinates is not None:
                    coordinate_phase = f"{phase}:coordinate_fallback"
                    coordinate_result = self._app_control_command(
                        command,
                        phase=coordinate_phase,
                        operation="click",
                        input=self._target_app_input(coordinates=coordinates),
                        command_metadata={
                            "coordinateSource": "accessibility_frame",
                        },
                        phase_events=phase_events,
                    )
                    evidence[coordinate_phase] = _safe_app_control_observation(
                        coordinate_result
                    )
                    if coordinate_result.success:
                        return coordinate_result
                    if not _coordinate_click_disabled(coordinate_result):
                        return coordinate_result
            if not _should_fallback_from_accessibility_action(
                result,
                expected_action=expected_action,
            ):
                return result

        input_payload = self._target_app_input()
        if node_label is not None:
            input_payload["selector"] = {
                "role": role,
                "name": node_label,
            }
        else:
            input_payload["selector"] = {
                "role": role,
                "index": 1,
            }
        result = self._app_control_command(
            command,
            phase=phase,
            operation="click",
            input=input_payload,
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        return result

    def _execute_action_ref(
        self,
        command: ToolCommand,
        action_ref: Mapping[str, Any],
        *,
        phase: str,
        evidence: dict[str, JsonValue],
        timeout_ms: int | None = None,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        expiry_failure = _action_ref_expiry_failure(command, action_ref)
        if expiry_failure is not None:
            evidence[phase] = {
                "failureKind": "action_ref_expired",
                "actionRefId": _optional_string_from_mapping(action_ref, "id"),
                "expiresAt": _action_ref_expiry_value(action_ref),
            }
            return expiry_failure
        identity_failure = _action_ref_identity_failure(command, action_ref)
        if identity_failure is not None:
            evidence[phase] = {
                "failureKind": "action_ref_identity_unverified",
                "actionRefId": _optional_string_from_mapping(action_ref, "id"),
            }
            return identity_failure
        input_payload = self._accessibility_action_input(action_ref)
        expected_action = str(input_payload["action"])
        result = self._app_control_command(
            command,
            phase=phase,
            operation="accessibility_action",
            input=input_payload,
            timeout_ms=timeout_ms,
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        if result.success or not _should_fallback_from_accessibility_action(
            result,
            expected_action=expected_action,
        ):
            return result
        selector = _selector_fallback_from_action_ref(action_ref)
        if selector is None:
            return result
        fallback_result = self._app_control_command(
            command,
            phase=f"{phase}:selector_fallback",
            operation="click",
            input=self._target_app_input(selector=selector),
            timeout_ms=timeout_ms,
            phase_events=phase_events,
        )
        evidence[f"{phase}:selector_fallback"] = _safe_app_control_observation(
            fallback_result
        )
        return fallback_result

    def _accessibility_action_input(
        self,
        action_ref: Mapping[str, Any],
    ) -> dict[str, JsonValue]:
        target = action_ref.get("target")
        if not isinstance(target, Mapping):
            raise ValueError("actionRef.target must be an object")
        ax_path = _optional_string_from_mapping(target, "axPath", "ax_path")
        if ax_path is None:
            raise ValueError("actionRef.target.axPath is required")
        action = _optional_string_from_mapping(action_ref, "action") or "AXPress"
        payload = self._target_app_input(
            target={"kind": "axPath", "axPath": ax_path},
            action=action,
        )
        snapshot_id = _optional_string_from_mapping(
            action_ref,
            "snapshotId",
            "snapshot_id",
        )
        if snapshot_id is not None:
            payload["snapshotId"] = snapshot_id
        preconditions = action_ref.get("preconditions")
        if isinstance(preconditions, Mapping):
            payload["preconditions"] = dict(preconditions)
        return payload

    def _open_app_input(self, **extra: JsonValue) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {"app": self._config.app_name}
        if self._config.bundle_id is not None:
            payload["bundleId"] = self._config.bundle_id
        payload.update(extra)
        return payload

    def _target_app_input(self, **extra: JsonValue) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {"targetApp": self._config.app_name}
        if self._config.bundle_id is not None:
            payload["bundleId"] = self._config.bundle_id
        payload.update(extra)
        return payload

    def _command(
        self,
        operation: WeChatOperation,
        input: dict[str, JsonValue] | None = None,
        *,
        parent: ToolCommand | None = None,
    ) -> ToolCommand:
        if parent is not None:
            timeout_ms = parent.timeout_ms
        else:
            timeout_ms = self._config.default_timeout_ms
        return wechat_command(
            operation,
            input or {},
            command_id=(
                f"{parent.command_id}:{operation}" if parent is not None else None
            ),
            timeout_ms=timeout_ms,
        )


class _WeChatSelectorQueryRunner:
    def __init__(
        self,
        tool: WeChatDesktopTool,
        command: ToolCommand,
        *,
        evidence: dict[str, JsonValue],
        phase_prefix: str,
        phase_events: "_PhaseEventCollector | None",
    ) -> None:
        self._tool = tool
        self._command = command
        self._evidence = evidence
        self._phase_prefix = phase_prefix
        self._phase_events = phase_events
        self._count = 0

    def __call__(
        self,
        *,
        root: Mapping[str, JsonValue],
        query: Mapping[str, JsonValue],
        include_raw: bool = False,
    ) -> Mapping[str, Any]:
        self._count += 1
        phase = f"{self._phase_prefix}:{self._count}"
        result = self._tool._app_control_command(
            self._command,
            phase=phase,
            operation="accessibility_query",
            input=self._tool._accessibility_query_input(
                root=root,
                query=query,
                include_raw=include_raw,
            ),
            phase_events=self._phase_events,
        )
        self._evidence[phase] = _safe_app_control_observation(result)
        if result.success:
            return _query_payload(result)
        return {
            "schema": "macos.accessibility.query.v1",
            "available": False,
            "failureKind": result.failure_kind or "accessibility_query_failed",
            "message": result.message or result.summary,
            "retryable": result.retryable,
            "nodes": [],
            "diagnostics": {
                "truncated": False,
                "failureKind": result.failure_kind or "accessibility_query_failed",
                "message": result.message or result.summary,
                "retryable": result.retryable,
            },
        }


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


def _action_ref_expiry_value(action_ref: Mapping[str, Any]) -> str | None:
    return _optional_string_from_mapping(action_ref, "expiresAt", "expires_at")


def _parse_action_ref_time(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _action_ref_expiry_failure(
    command: ToolCommand,
    action_ref: Mapping[str, Any],
) -> ToolObservation | None:
    raw_expires_at = _action_ref_expiry_value(action_ref)
    if raw_expires_at is None:
        return None
    expires_at = _parse_action_ref_time(raw_expires_at)
    if expires_at is not None and _utc_now_datetime() < expires_at:
        return None
    action_id = _optional_string_from_mapping(action_ref, "id") or "unknown"
    message = f"WeChat actionRef is expired or invalid: {action_id}"
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_action_ref_expired",
        message=message,
        recovery_hint="Re-run inspect_window or list operation to get a fresh actionRef.",
        retryable=True,
        observation={
            "schema": "wechat.execute_action.v1",
            "status": "failed",
            "actionId": action_id,
            "failureKind": "wechat_action_ref_expired",
            "expiresAt": raw_expires_at,
        },
        evidence={
            "actionRef": {
                "id": action_id,
                "expiresAt": raw_expires_at,
            }
        },
    )


def _action_ref_identity_failure(
    command: ToolCommand,
    action_ref: Mapping[str, Any],
) -> ToolObservation | None:
    target = action_ref.get("target")
    if not isinstance(target, Mapping):
        return None
    role = _optional_string_from_mapping(target, "role")
    if role is None or role.casefold() not in {"axrow", "row"}:
        return None
    target_label = _optional_string_from_mapping(target, "label", "name")
    preconditions = action_ref.get("preconditions")
    label_values = (
        preconditions.get("labelIn")
        if isinstance(preconditions, Mapping)
        else None
    )
    identity_verified = (
        target_label is not None
        and isinstance(label_values, list | tuple)
        and target_label in label_values
    )
    if identity_verified:
        return None

    action_id = _optional_string_from_mapping(action_ref, "id") or "unknown"
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_action_precondition_failed",
        message=(
            "WeChat row actionRef does not contain a verifiable target "
            f"identity: {action_id}"
        ),
        recovery_hint=(
            "Re-run list_conversations or use open_contact(displayName) to "
            "resolve the current row."
        ),
        retryable=True,
        observation={
            "schema": "wechat.execute_action.v1",
            "status": "failed",
            "actionId": action_id,
            "failureKind": "wechat_action_precondition_failed",
        },
    )


def _should_fallback_from_accessibility_action(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    if result.success or result.operation != "accessibility_action":
        return False
    if not _accessibility_action_proof_is_consistent(
        result,
        expected_action=expected_action,
    ):
        return False
    attempted = _accessibility_action_attempted(result)
    dispatched = _accessibility_action_request_dispatched(result)
    if not attempted.valid or not dispatched.valid:
        return False
    failure_kind = _accessibility_action_failure_kind(result)
    if failure_kind == "accessibility_action_unsupported":
        return _accessibility_action_has_definite_no_effect(
            result,
            expected_action=expected_action,
        )
    if not _accessibility_action_has_safe_non_native_effect(result):
        return False
    if attempted.value is True:
        return False
    unsupported = failure_kind in {
        "unsupported_operation",
        "unsupported_accessibility_action",
    }
    metadata = result.metadata if isinstance(result.metadata, Mapping) else {}
    legacy_status = metadata.get("legacyStatus")
    observation = result.observation
    if (
        not unsupported
        and legacy_status == "failed"
        and isinstance(observation, Mapping)
    ):
        nested = observation.get("accessibilityAction")
        if isinstance(nested, Mapping):
            nested_kind = nested.get("failureKind")
            unsupported = nested_kind in {
                "unsupported_operation",
                "unsupported_accessibility_action",
            }
    if unsupported:
        return True
    if result.retryable is not True:
        return False
    return dispatched.present and dispatched.value is False


def _should_try_coordinate_click_after_accessibility_action(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    return _should_fallback_from_accessibility_action(
        result,
        expected_action=expected_action,
    )


def _should_press_return_for_search_result(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    return _should_fallback_from_accessibility_action(
        result,
        expected_action=expected_action,
    )


def _accessibility_action_attempted(result: ToolObservation) -> _BooleanEvidence:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return _BooleanEvidence(present=True, valid=False)
    return _consistent_bool_evidence(
        payloads,
        ("actionAttempted", "action_attempted"),
    )


def _accessibility_action_has_definite_no_effect(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    if result.failure_kind != "accessibility_action_unsupported":
        return False
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return False
    failure_kind = _required_consistent_string_evidence(
        payloads,
        ("failureKind", "failure_kind"),
    )
    action = _required_consistent_string_evidence(payloads, ("action",))
    attempted = _required_consistent_bool_evidence(
        payloads,
        ("actionAttempted", "action_attempted"),
    )
    effect = _required_consistent_string_evidence(
        payloads,
        ("actionEffect", "action_effect"),
    )
    native_error_code = _required_consistent_int_evidence(
        payloads,
        ("nativeErrorCode", "native_error_code"),
    )
    expected_native_error = _DEFINITE_UNSUPPORTED_NATIVE_ERRORS.get(action or "")
    return (
        failure_kind == "accessibility_action_unsupported"
        and action == expected_action
        and expected_native_error is not None
        and attempted is True
        and effect == "none"
        and native_error_code == expected_native_error
    )


def _accessibility_action_has_safe_non_native_effect(
    result: ToolObservation,
) -> bool:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return False
    effect = _consistent_string_evidence(
        payloads,
        ("actionEffect", "action_effect"),
    )
    native_error_code = _consistent_int_evidence(
        payloads,
        ("nativeErrorCode", "native_error_code"),
    )
    if not effect.valid or not native_error_code.valid:
        return False
    if effect.present and effect.value != "none":
        return False
    # A native code means the request reached native action evaluation. Only
    # the complete action-bound unsupported proof above can establish no effect.
    return not native_error_code.present


def _accessibility_action_proof_payloads(
    result: ToolObservation,
) -> tuple[Mapping[str, Any], ...] | None:
    if not all(
        isinstance(payload, Mapping)
        for payload in (result.metadata, result.observation, result.evidence)
    ):
        return None

    top_level: dict[str, Any] = {}
    if result.failure_kind is not None:
        top_level["failureKind"] = result.failure_kind
    if result.retryable is not None:
        top_level["retryable"] = result.retryable

    roots: list[Mapping[str, Any]] = [
        top_level,
        result.metadata,
        result.observation,
        result.evidence,
    ]
    if result.error is not None:
        if isinstance(result.error, ToolError):
            roots.append(result.error.to_dict())
            roots.append(result.error.evidence)
        elif isinstance(result.error, Mapping):
            roots.append(result.error)
            if "evidence" in result.error:
                error_evidence = result.error.get("evidence")
                if not isinstance(error_evidence, Mapping):
                    return None
                roots.append(error_evidence)
        else:
            return None

    nested_container_keys = (
        "metadata",
        "accessibilityAction",
        "accessibility_action",
        "diagnostics",
        "transport",
        "accessibilityActionTransport",
        "accessibility_action_transport",
    )
    payloads: list[Mapping[str, Any]] = []
    pending = list(roots)
    seen: set[int] = set()
    while pending:
        payload = pending.pop(0)
        identity = id(payload)
        if identity in seen:
            continue
        seen.add(identity)
        payloads.append(payload)
        for key in nested_container_keys:
            if key not in payload:
                continue
            nested = payload.get(key)
            if not isinstance(nested, Mapping):
                return None
            pending.append(nested)
    return tuple(payloads)


def _required_consistent_string_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> str | None:
    evidence = _consistent_string_evidence(payloads, keys)
    if not evidence.present or not evidence.valid:
        return None
    return evidence.value


def _consistent_string_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> _StringEvidence:
    values: list[str] = []
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                return _StringEvidence(present=True, valid=False)
            values.append(value)
    if not values:
        return _StringEvidence(present=False, valid=True)
    if any(value != values[0] for value in values[1:]):
        return _StringEvidence(present=True, valid=False)
    return _StringEvidence(present=True, valid=True, value=values[0])


def _required_consistent_bool_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> bool | None:
    evidence = _consistent_bool_evidence(payloads, keys)
    if not evidence.present or not evidence.valid:
        return None
    return evidence.value


def _consistent_bool_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> _BooleanEvidence:
    values: list[bool] = []
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if not isinstance(value, bool):
                return _BooleanEvidence(present=True, valid=False)
            values.append(value)
    if not values:
        return _BooleanEvidence(present=False, valid=True)
    if any(value is not values[0] for value in values[1:]):
        return _BooleanEvidence(present=True, valid=False)
    return _BooleanEvidence(present=True, valid=True, value=values[0])


def _required_consistent_int_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> int | None:
    evidence = _consistent_int_evidence(payloads, keys)
    if not evidence.present or not evidence.valid:
        return None
    return evidence.value


def _consistent_int_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> _IntegerEvidence:
    values: list[int] = []
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if not isinstance(value, int) or isinstance(value, bool):
                return _IntegerEvidence(present=True, valid=False)
            values.append(value)
    if not values:
        return _IntegerEvidence(present=False, valid=True)
    if any(value != values[0] for value in values[1:]):
        return _IntegerEvidence(present=True, valid=False)
    return _IntegerEvidence(present=True, valid=True, value=values[0])


def _accessibility_action_proof_is_consistent(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return False
    failure_kind = _consistent_string_evidence(
        payloads,
        ("failureKind", "failure_kind"),
    )
    action = _consistent_string_evidence(payloads, ("action",))
    effect = _consistent_string_evidence(
        payloads,
        ("actionEffect", "action_effect"),
    )
    native_error_code = _consistent_int_evidence(
        payloads,
        ("nativeErrorCode", "native_error_code"),
    )
    attempted = _consistent_bool_evidence(
        payloads,
        ("actionAttempted", "action_attempted"),
    )
    dispatched = _consistent_bool_evidence(
        payloads,
        ("requestDispatched", "request_dispatched"),
    )
    retryable = _consistent_bool_evidence(payloads, ("retryable",))
    if not all(
        item.valid
        for item in (
            failure_kind,
            action,
            effect,
            native_error_code,
            attempted,
            dispatched,
            retryable,
        )
    ):
        return False
    return not action.present or action.value == expected_action


def _accessibility_action_request_dispatched(
    result: ToolObservation,
) -> _BooleanEvidence:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return _BooleanEvidence(present=True, valid=False)
    return _consistent_bool_evidence(
        payloads,
        ("requestDispatched", "request_dispatched"),
    )


def _execute_action_failure_kind(result: ToolObservation) -> str:
    failure_kind = _accessibility_action_failure_kind(result)
    if failure_kind == "wechat_action_ref_expired":
        return "wechat_action_ref_expired"
    if failure_kind in {
        "precondition_failed",
        "wechat_action_precondition_failed",
    }:
        return "wechat_action_precondition_failed"
    return "wechat_action_failed"


def _accessibility_action_failure_kind(result: ToolObservation) -> str | None:
    if result.failure_kind is not None:
        return result.failure_kind
    observation = result.observation
    if isinstance(observation, Mapping):
        for key in ("accessibilityAction", "accessibility_action"):
            nested = observation.get(key)
            if not isinstance(nested, Mapping):
                continue
            failure_kind = nested.get("failureKind") or nested.get("failure_kind")
            if isinstance(failure_kind, str) and failure_kind:
                return failure_kind
    return None


def _selector_fallback_from_action_ref(
    action_ref: Mapping[str, Any],
) -> dict[str, JsonValue] | None:
    fallbacks = action_ref.get("fallbacks")
    if not isinstance(fallbacks, list):
        return None
    for fallback in fallbacks:
        if not isinstance(fallback, Mapping):
            continue
        if fallback.get("method") != "selector_click":
            continue
        selector = fallback.get("selector")
        if not isinstance(selector, Mapping):
            continue
        role = _optional_string_from_mapping(selector, "role")
        name = _optional_string_from_mapping(selector, "name", "title", "label")
        if role is None or name is None:
            continue
        return {"role": role, "name": name}
    return None


def _contact_target_query_issue(
    observation: ToolObservation,
) -> tuple[str, str | None] | None:
    if not observation.success:
        return "failed", None
    payload = _query_payload(observation)
    invalid_reason = _contact_target_query_invalid_reason(payload)
    if invalid_reason is not None:
        return "invalid", invalid_reason
    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, Mapping)
    if diagnostics["truncated"] is True:
        return "truncated", None
    return None


def _contact_target_query_invalid_reason(
    payload: Mapping[str, Any],
) -> str | None:
    if payload.get("schema") != "macos.accessibility.query.v1":
        return "schema_invalid"
    if payload.get("available") is not True:
        return "available_invalid"
    if "status" in payload and payload.get("status") != "ok":
        return "status_invalid"
    if any(key in payload for key in ("failureKind", "failure_kind", "error")):
        return "failure_evidence_conflict"
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return "nodes_invalid"
    if any(not isinstance(node, Mapping) for node in nodes):
        return "node_member_invalid"
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return "diagnostics_invalid"
    if "truncated" not in diagnostics or not isinstance(
        diagnostics.get("truncated"),
        bool,
    ):
        return "truncation_invalid"
    if any(
        key in diagnostics
        for key in ("failureKind", "failure_kind")
    ):
        return "diagnostics_failure_conflict"
    if "returnedNodes" in diagnostics:
        returned_nodes = diagnostics.get("returnedNodes")
        if (
            not isinstance(returned_nodes, int)
            or isinstance(returned_nodes, bool)
            or returned_nodes != len(nodes)
        ):
            return "returned_nodes_invalid"
    return None


def _contact_target_query_validation_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    issue = _contact_target_query_issue(observation)
    if issue is None:
        return None
    issue_kind, reason = issue
    if issue_kind == "failed":
        return _failure_from_contact_target_query(
            command,
            observation,
            evidence=evidence,
        )
    if issue_kind == "truncated":
        return _contact_target_query_truncation_failure(
            command,
            contact,
            observation,
            evidence=evidence,
        )
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="accessibility_query_failed",
        message=(
            "WeChat contact target query returned an invalid response and "
            "cannot establish a safe target."
        ),
        recovery_hint="Retry after WeChat and the local control service settle.",
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "query_invalid",
            "diagnostics": {"reason": reason or "query_invalid"},
        },
        evidence=evidence,
    )


def _failure_from_contact_target_query(
    command: ToolCommand,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    cause = observation.failure_kind or "accessibility_query_failed"
    message = observation.message or observation.summary
    selector_failure_kind = "selector_query_failed"
    diagnostics = _ContactQueryFailureContext(
        failure_kind=selector_failure_kind,
        cause_failure_kind=cause,
        message=message,
        retryable=observation.retryable,
    )
    return _failure_from_selector_query(
        command,
        diagnostics,
        message="WeChat contact target query failed.",
        observation_key="selector",
        semantic_payload={
            "id": "wechat.contactTarget",
            "status": "failed",
            "profileId": "wechat.contactTarget",
            "profileVersion": "1",
            "diagnostics": {
                "failureKind": selector_failure_kind,
                "causeFailureKind": cause,
                "retryable": (
                    observation.retryable
                    if observation.retryable is not None
                    else True
                ),
                "message": message,
            },
        },
        evidence=evidence,
    )


def _contact_target_query_truncation_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    issue = _contact_target_query_issue(observation)
    if issue is None or issue[0] != "truncated":
        return None
    raw_diagnostics = _query_payload(observation).get("diagnostics")
    diagnostics: dict[str, JsonValue] = {"truncated": True}
    if isinstance(raw_diagnostics, Mapping):
        returned_nodes = raw_diagnostics.get("returnedNodes")
        if isinstance(returned_nodes, int) and not isinstance(returned_nodes, bool):
            diagnostics["returnedNodes"] = returned_nodes
        truncation_reason = raw_diagnostics.get("truncationReason")
        if isinstance(truncation_reason, str) and truncation_reason:
            diagnostics["truncationReason"] = truncation_reason
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_query_truncated",
        message=(
            "WeChat contact target query was truncated before uniqueness could "
            "be established."
        ),
        recovery_hint=(
            "Retry after WeChat settles or use a narrower contact identifier."
        ),
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "query_truncated",
            "diagnostics": diagnostics,
        },
        evidence=evidence,
    )


def _contact_target_not_found_failure(
    command: ToolCommand,
    contact: str,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    return _failure(
        command,
        status=ToolStatus.NOT_FOUND,
        failure_kind="contact_not_found",
        message=f"Could not find a unique search result for {contact}.",
        recovery_hint="Use a contact name that produces one visible result.",
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "not_found",
        },
        evidence=evidence,
    )


def _contact_target_unverified_failure(
    command: ToolCommand,
    contact: str,
    *,
    reason: str,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_action_target_unverified",
        message="WeChat contact target geometry could not be verified.",
        recovery_hint="Restore the target row inside the visible WeChat window.",
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "target_unverified",
            "diagnostics": {"reason": reason},
        },
        evidence=evidence,
    )


def _safe_app_control_observation(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    if observation.operation == "accessibility_query":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Accessibility query completed."
                if observation.success
                else "Accessibility query failed."
            ),
        )
        payload["observation"] = {
            "accessibilityQuery": _safe_accessibility_query_payload(observation)
        }
        return payload
    if observation.operation == "accessibility_action":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Accessibility action completed."
                if observation.success
                else "Accessibility action failed."
            ),
        )
        payload["observation"] = {
            "accessibilityAction": _safe_accessibility_action_payload(observation)
        }
        return payload
    if observation.operation == "click":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Click completed." if observation.success else "Click failed."
            ),
        )
        payload["observation"] = {
            "action": {
                "operation": "click",
                "available": observation.success,
            }
        }
        return payload
    if observation.operation == "observe":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Observed application state."
                if observation.success
                else "Application observation failed."
            ),
        )
        safe_observation: dict[str, JsonValue] = {}
        for output_key, source_keys in (
            (
                "frontmostApp",
                ("frontmostApp", "frontmost_app", "appName", "app_name"),
            ),
            (
                "frontmostBundleId",
                (
                    "frontmostBundleId",
                    "frontmost_bundle_id",
                    "bundleId",
                    "bundle_id",
                ),
            ),
        ):
            value = _string_from_observation(observation, *source_keys)
            if value is not None:
                safe_observation[output_key] = value
        accessibility = _mapping_from_observation(observation, "accessibility")
        if accessibility is not None:
            safe_observation["accessibility"] = _safe_accessibility_status(
                accessibility
            )
        payload["observation"] = safe_observation
        return payload
    return _redact_input_text(observation.to_dict())


def _safe_accessibility_query_payload(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    source = _query_payload(observation)
    payload: dict[str, JsonValue] = {}
    schema = source.get("schema")
    if isinstance(schema, str):
        payload["schema"] = schema
    available = source.get("available")
    payload["available"] = (
        available if isinstance(available, bool) else observation.success
    )
    for key in ("status", "failureKind", "causeFailureKind"):
        value = source.get(key)
        if isinstance(value, str):
            payload[key] = value
    if "failureKind" not in payload and observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    retryable = source.get("retryable")
    if isinstance(retryable, bool):
        payload["retryable"] = retryable
    elif observation.retryable is not None:
        payload["retryable"] = observation.retryable

    diagnostics = source.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        safe_diagnostics: dict[str, JsonValue] = {}
        for key in (
            "returnedNodes",
            "visitedNodes",
            "matchedNodes",
            "queryCount",
            "nodeCount",
            "durationMs",
            "elapsedMs",
            "timeBudgetMs",
            "limit",
            "maxDepth",
            "truncated",
            "truncationReason",
            "failureKind",
            "causeFailureKind",
            "retryable",
            "cacheStatus",
            "preferVisibleRows",
        ):
            value = diagnostics.get(key)
            if isinstance(value, str | int | float | bool):
                safe_diagnostics[key] = value
        if safe_diagnostics:
            payload["diagnostics"] = safe_diagnostics
    return payload


def _safe_accessibility_action_payload(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    source = _mapping_from_observation(observation, "accessibilityAction") or {}
    payload: dict[str, JsonValue] = {}
    schema = source.get("schema")
    if isinstance(schema, str):
        payload["schema"] = schema
    available = source.get("available")
    payload["available"] = (
        available if isinstance(available, bool) else observation.success
    )
    status = source.get("status")
    if isinstance(status, str):
        payload["status"] = status

    proof_payloads = _accessibility_action_proof_payloads(observation)
    if proof_payloads is not None:
        for output_key, keys in (
            ("failureKind", ("failureKind", "failure_kind")),
            ("action", ("action",)),
            ("actionEffect", ("actionEffect", "action_effect")),
        ):
            evidence = _consistent_string_evidence(proof_payloads, keys)
            if evidence.present and evidence.valid and evidence.value is not None:
                payload[output_key] = evidence.value
        native_code = _consistent_int_evidence(
            proof_payloads,
            ("nativeErrorCode", "native_error_code"),
        )
        if native_code.present and native_code.valid and native_code.value is not None:
            payload["nativeErrorCode"] = native_code.value
        for output_key, keys in (
            ("actionAttempted", ("actionAttempted", "action_attempted")),
            ("requestDispatched", ("requestDispatched", "request_dispatched")),
            ("retryable", ("retryable",)),
        ):
            evidence = _consistent_bool_evidence(proof_payloads, keys)
            if evidence.present and evidence.valid and evidence.value is not None:
                payload[output_key] = evidence.value
    elif observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    return payload


def _safe_executed_action_result(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "operation": observation.operation,
        "status": observation.status.value,
        "success": observation.success,
    }
    if observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    if observation.operation == "accessibility_action":
        payload["accessibilityAction"] = _safe_accessibility_action_payload(
            observation
        )
    return payload


class _PhaseEventCollector:
    def __init__(
        self,
        command: ToolCommand,
        *,
        observer: ToolObserver | None,
    ) -> None:
        self._command = command
        self._observer = observer
        self._next_seq = 1
        self.events: list[ToolEvent] = []

    def emit(
        self,
        *,
        parent: ToolCommand,
        phase: str,
        operation: str,
        observation: ToolObservation,
    ) -> None:
        phase_name = phase
        if parent.command_id != self._command.command_id:
            phase_name = f"{parent.operation}.{phase}"
        safe_observation = _safe_app_control_observation(observation)
        event = ToolEvent(
            command_id=self._command.command_id,
            seq=self.next_seq(),
            event_type=ToolEventType.PROGRESS,
            phase=phase_name,
            status=observation.status,
            summary=_safe_app_control_event_summary(observation),
            data={
                "phase": phase_name,
                "appControlOperation": operation,
                "parentCommandId": parent.command_id,
                "appControlCommandId": observation.command_id,
                "appControlObservation": safe_observation,
            },
        )
        self.events.append(event)
        _emit(self._observer, event)

    def next_seq(self) -> int:
        seq = self._next_seq
        self._next_seq += 1
        return seq


def _wechat_identity_failure(
    command: ToolCommand,
    config: WeChatDesktopConfig,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation | None:
    frontmost_bundle_id = _string_from_observation(
        observation,
        "frontmostBundleId",
        "frontmost_bundle_id",
    )
    frontmost_app = _string_from_observation(
        observation,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    )
    if (
        config.bundle_id is not None
        and frontmost_bundle_id is not None
        and frontmost_bundle_id != config.bundle_id
    ):
        return _wechat_not_ready_failure(
            command,
            (
                "Observed frontmost app bundle id does not match WeChat: "
                f"expected {config.bundle_id}, got {frontmost_bundle_id}."
            ),
            evidence=evidence or {"observe": _safe_app_control_observation(observation)},
        )
    if frontmost_bundle_id is None and frontmost_app is not None:
        if frontmost_app.casefold() != config.app_name.casefold():
            return _wechat_not_ready_failure(
                command,
                (
                    "Observed frontmost app does not match WeChat: "
                    f"expected {config.app_name}, got {frontmost_app}."
                ),
                evidence=evidence or {"observe": _safe_app_control_observation(observation)},
            )
    return None


def _wechat_login_failure(
    command: ToolCommand,
    config: WeChatDesktopConfig,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation | None:
    del config
    if not _observation_indicates_login_required(observation):
        return None
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="wechat_not_logged_in",
        message="WeChat Desktop is open but not logged in.",
        recovery_hint="Log in to WeChat Desktop before running this command.",
        retryable=False,
        evidence=evidence or {"observe": _safe_app_control_observation(observation)},
    )


def _ready_observation_with_accessibility_window_title(
    ready: ToolObservation,
    accessibility_query: ToolObservation,
    app_name: str,
) -> ToolObservation:
    title = _accessibility_query_window_title(accessibility_query)
    if title is None:
        return ready
    observation = dict(ready.observation)
    observation["windowTitle"] = title
    observation["snapshotId"] = (
        _query_snapshot_id(_query_payload(accessibility_query))
        or observation.get("snapshotId")
        or f"frontmost:{app_name}:{title}"
    )
    metadata = observation.get("metadata")
    if isinstance(metadata, Mapping):
        updated_metadata = dict(metadata)
        updated_metadata["window_title"] = title
        observation["metadata"] = updated_metadata
    summary = f"Frontmost app: {observation.get('frontmostApp') or app_name}. Window: {title}."
    return ToolObservation.ok(
        command_id=ready.command_id,
        tool=ready.tool,
        operation=ready.operation,
        summary=summary,
        observation=observation,
        evidence=ready.evidence,
        timing=ready.timing,
        metadata=ready.metadata,
    )


def _accessibility_query_window_title(observation: ToolObservation) -> str | None:
    if not observation.success:
        return None
    payload = _query_payload(observation)
    window = payload.get("window")
    if not isinstance(window, Mapping):
        return None
    role = window.get("role")
    title = window.get("title")
    if role != "AXWindow" or not isinstance(title, str) or not title.strip():
        return None
    return title.strip()


def _search_focus_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    assessment = _search_focus_assessment(observation)
    state = assessment.get("state")
    if state == "verified":
        return None
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="search_not_focused",
        message=(
            "WeChat search field is not focused after the search hotkey; "
            "refusing to type the contact into the current chat."
        ),
        recovery_hint="Click WeChat search manually or adjust search_hotkey, then retry.",
        retryable=True,
        observation={
            "requestedContact": contact,
            "searchFocus": assessment,
        },
        evidence=evidence,
    )


def _search_focus_assessment(observation: ToolObservation) -> dict[str, JsonValue]:
    query_payload = _query_payload(observation)
    if query_payload:
        if query_payload.get("available") is False:
            payload: dict[str, JsonValue] = {
                "state": "unknown",
                "reason": "search_focus_query_unavailable",
            }
            failure_kind = query_payload.get("failureKind")
            if isinstance(failure_kind, str):
                payload["failureKind"] = failure_kind
            return payload
        nodes = _query_nodes(observation)
        if len(nodes) != 1:
            return {
                "state": "unknown",
                "reason": "search_focus_query_target_missing",
            }
        search_element = nodes[0]
        public_element = _public_accessibility_element(search_element)
        if not _is_text_like_accessibility_element(search_element):
            return {
                "state": "not_search",
                "reason": "search_focus_query_target_is_not_text_input",
                "focusedElement": public_element,
            }
        if not _accessibility_element_contains(
            search_element,
            _SEARCH_FOCUS_MARKERS,
        ):
            return {
                "state": "not_search",
                "reason": "search_focus_query_target_has_no_search_marker",
                "focusedElement": public_element,
            }
        focused = search_element.get("focused")
        if focused is True:
            return {
                "state": "verified",
                "reason": "targeted_search_element_focused",
                "focusedElement": public_element,
            }
        if focused is False:
            return {
                "state": "not_search",
                "reason": "targeted_search_element_not_focused",
                "focusedElement": public_element,
            }
        return {
            "state": "unknown",
            "reason": "targeted_search_element_focus_unknown",
            "focusedElement": public_element,
        }

    accessibility = _mapping_from_observation(observation, "accessibility")
    if accessibility is None:
        return {"state": "unknown", "reason": "no_accessibility_snapshot"}
    if accessibility.get("available") is False:
        payload: dict[str, JsonValue] = {
            "state": "unknown",
            "reason": "accessibility_snapshot_unavailable",
        }
        failure_kind = accessibility.get("failureKind")
        if isinstance(failure_kind, str):
            payload["failureKind"] = failure_kind
        message = accessibility.get("message")
        if isinstance(message, str):
            payload["message"] = message
        return payload
    focused = _mapping_value(accessibility.get("focusedElement"))
    if focused is None:
        return {"state": "unknown", "reason": "no_focused_element"}
    focused_payload = _public_accessibility_element(focused)
    if not _is_text_like_accessibility_element(focused):
        return {
            "state": "not_search",
            "reason": "focused_element_is_not_text_input",
            "focusedElement": focused_payload,
        }
    if _accessibility_element_contains(focused, _SEARCH_FOCUS_MARKERS):
        return {
            "state": "verified",
            "reason": "focused_element_has_search_marker",
            "focusedElement": focused_payload,
        }
    if _accessibility_element_contains(focused, _CHAT_INPUT_MARKERS):
        return {
            "state": "not_search",
            "reason": "focused_element_looks_like_chat_input",
            "focusedElement": focused_payload,
        }
    position = _focused_text_field_position(focused, accessibility)
    if position == "top":
        return {
            "state": "verified",
            "reason": "focused_text_field_is_top_candidate",
            "focusedElement": focused_payload,
        }
    if position == "bottom":
        return {
            "state": "not_search",
            "reason": "focused_text_field_is_bottom_candidate",
            "focusedElement": focused_payload,
        }
    return {
        "state": "unknown",
        "reason": "focused_text_field_is_not_identifiable",
        "focusedElement": focused_payload,
    }


def _input_focus_failure(
    command: ToolCommand,
    observation: ToolObservation,
) -> ToolObservation | None:
    if not _observation_indicates_input_not_focused(observation):
        return None
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="input_not_focused",
        message="WeChat chat input is not focused.",
        recovery_hint="Focus the chat input or rerun focus_contact before drafting.",
        retryable=True,
        observation={"draftReady": False, "inputFocused": False},
        evidence={"draft": _safe_app_control_observation(observation)},
    )


def _open_wechat_phase_failure(
    command: ToolCommand,
    result: ToolObservation,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    if result.tool == WECHAT_TOOL:
        return result
    failure_kind = (
        "wechat_not_ready"
        if result.operation in {"observe", "focus_app"}
        else "wechat_open_failed"
    )
    return _from_app_control_failure(
        command,
        failure_kind,
        result,
        evidence=evidence,
    )


def _from_app_control_failure(
    command: ToolCommand,
    failure_kind: str,
    result: ToolObservation,
    *,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation:
    return _failure(
        command,
        status=result.status if result.status != ToolStatus.OK else ToolStatus.FAILED,
        failure_kind=failure_kind,
        message=result.summary,
        retryable=result.retryable if result.retryable is not None else True,
        evidence=evidence or {"appControlObservation": _safe_app_control_observation(result)},
    )
