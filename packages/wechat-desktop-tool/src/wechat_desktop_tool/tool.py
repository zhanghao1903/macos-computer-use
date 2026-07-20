"""Protocol-first WeChat Desktop tool."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from app_control_protocol import (
    AppControlClient,
    ToolCommand,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolObserver,
    ToolStatus,
)
from app_control_protocol.json_types import JsonValue

from ._action_operations import _execute_action
from ._collection_operations import _list_contacts, _list_conversations
from ._contact_operations import _focus_contact, _open_contact

from ._diagnostics import (
    _bool_input,
    _duration_ms,
    _emit,
    _event,
    _failure,
    _nested_failure,
    _observation_indicates_input_not_focused,
    _positive_int,
    _required_input,
    _send_unverified,
    _string_from_observation,
    _string_input,
    _utc_now,
    _wechat_environment,
    _with_timing,
)

from ._mapped_controls import _query_mapped_collection

from ._query_mapping import (
    _failure_from_selector_result,
    _node_from_selector_element,
    _query_nodes,
    _query_truncated,
)

from ._row_parsing import (
    _chat_title_from_query_nodes,
    _current_chat_title,
    _message_observed,
    _messages_from_observation,
    _messages_from_query_nodes,
    _next_page_token,
)

from ._runtime import (
    _PhaseEventCollector,
    _WeChatSelectorQueryRunner,
    _from_app_control_failure,
    _open_wechat_phase_failure,
    _safe_app_control_observation,
    _wechat_identity_failure,
    _wechat_login_failure,
    WeChatToolRuntime,
)
from ._window_operations import _inspect_window, _open_wechat

from .commands import WECHAT_TOOL
from .control_map import WeChatControlMap
from .models import WeChatDesktopConfig, wechat_message_hash
from .profiles import build_packaged_selector_resolver
from .profiles import WeChatSelectorAssets

if TYPE_CHECKING:
    from app_control_protocol import AppControlConfig


class WeChatDesktopTool:
    """Semantic WeChat Desktop tool built on an app-control client."""

    def __init__(
        self,
        app_control: AppControlClient,
        config: WeChatDesktopConfig | None = None,
    ) -> None:
        self._runtime = WeChatToolRuntime.create(app_control, config)

    @property
    def _app_control(self) -> AppControlClient:
        return self._runtime.app_control

    @property
    def _config(self) -> WeChatDesktopConfig:
        return self._runtime.config

    @property
    def _selector_assets(self) -> WeChatSelectorAssets:
        return self._runtime.selector_assets

    @property
    def _control_map(self) -> WeChatControlMap:
        return self._runtime.control_map

    @property
    def _selector_profile(self) -> Any:
        return self._runtime.selector_profile

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
        command = self._runtime._command("open_wechat")
        return self.run_command(command)

    def inspect_window(
        self,
        *,
        include_raw: bool = False,
        include_actionables: bool = True,
    ) -> ToolObservation:
        command = self._runtime._command(
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
        command = self._runtime._command("list_contacts", payload)
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
        command = self._runtime._command("list_conversations", payload)
        return self.run_command(command)

    def open_contact(self, contact: str) -> ToolObservation:
        command = self._runtime._command("open_contact", {"contact": contact})
        return self.run_command(command)

    def execute_action(self, action_ref: Mapping[str, JsonValue]) -> ToolObservation:
        command = self._runtime._command(
            "execute_action",
            {"actionRef": dict(action_ref)},
        )
        return self.run_command(command)

    def focus_contact(self, contact: str) -> ToolObservation:
        command = self._runtime._command("focus_contact", {"contact": contact})
        return self.run_command(command)

    def observe_current_chat(
        self,
        *,
        include_visible_messages: bool = True,
    ) -> ToolObservation:
        command = self._runtime._command(
            "observe_current_chat",
            {"includeVisibleMessages": include_visible_messages},
        )
        return self.run_command(command)

    def read_visible_messages(self, *, limit: int = 20) -> ToolObservation:
        command = self._runtime._command("read_visible_messages", {"limit": limit})
        return self.run_command(command)

    def read_contact_messages(
        self,
        contact: str,
        *,
        limit: int = 30,
    ) -> ToolObservation:
        command = self._runtime._command(
            "read_contact_messages",
            {"contact": contact, "limit": limit},
        )
        return self.run_command(command)

    def draft_message(self, message: str) -> ToolObservation:
        command = self._runtime._command("draft_message", {"message": message})
        return self.run_command(command)

    def submit_draft(self, *, method: str = "keyboard_return") -> ToolObservation:
        command = self._runtime._command("submit_draft", {"method": method})
        return self.run_command(command)

    def send_message(
        self,
        *,
        contact: str,
        message: str,
        verify_after_submit: bool = False,
        verify_limit: int = 20,
    ) -> ToolObservation:
        command = self._runtime._command(
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
                return _open_wechat(self._runtime, command, phase_events=phase_events)
            if operation == "inspect_window":
                return _inspect_window(
                    self._runtime, command, phase_events=phase_events
                )
            if operation == "list_contacts":
                return _list_contacts(self._runtime, command, phase_events=phase_events)
            if operation == "list_conversations":
                return _list_conversations(
                    self._runtime, command, phase_events=phase_events
                )
            if operation == "open_contact":
                return _open_contact(self._runtime, command, phase_events=phase_events)
            if operation == "execute_action":
                return _execute_action(
                    self._runtime, command, phase_events=phase_events
                )
            if operation == "focus_contact":
                return _focus_contact(self._runtime, command, phase_events=phase_events)
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

    def _read_contact_messages(
        self,
        command: ToolCommand,
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        contact = _required_input(command, "contact")
        limit = _positive_int(command.input.get("limit"), default=30)
        opened = _open_contact(
            self._runtime,
            self._runtime._command(
                "open_contact",
                {"contact": contact},
                parent=command,
            ),
            phase_events=phase_events,
        )
        if not opened.success:
            return _nested_failure(command, "open_contact", opened)
        messages = self._read_visible_messages(
            self._runtime._command(
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
        input_payload = self._runtime._target_app_input()
        if include_visible_messages:
            input_payload["includeVisibleText"] = True
        result = self._runtime._app_control_command(
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
        opened = self._runtime._open_wechat_phase(
            command,
            evidence,
            phase_events=phase_events,
        )
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
            self._runtime,
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
        messages_result = self._runtime._query_descendants(
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
        collection_query = _query_mapped_collection(
            self._runtime,
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
        result = self._runtime._app_control_command(
            command,
            phase="draft_message",
            operation="type_text",
            input=self._runtime._target_app_input(text=message),
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
        result = self._runtime._app_control_command(
            command,
            phase="submit_draft",
            operation="press_key",
            input=self._runtime._target_app_input(key=self._config.submit_key),
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
        focus = _focus_contact(
            self._runtime,
            self._runtime._command(
                "focus_contact",
                {"contact": contact},
                parent=command,
            ),
            phase_events=phase_events,
        )
        if not focus.success:
            return _nested_failure(command, "focus_contact", focus)
        draft = self._draft_message(
            self._runtime._command(
                "draft_message",
                {"message": message},
                parent=command,
            ),
            phase_events=phase_events,
        )
        if not draft.success:
            return _nested_failure(command, "draft_message", draft)
        submitted = self._submit_draft(
            self._runtime._command(
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
                self._runtime._command(
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


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


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
