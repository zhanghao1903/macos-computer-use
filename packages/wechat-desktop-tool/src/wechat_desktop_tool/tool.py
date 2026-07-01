"""Protocol-first WeChat Desktop tool."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
import re
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

from .commands import WECHAT_TOOL, wechat_command
from .models import (
    WECHAT_WINDOW_SCHEMA,
    WeChatDesktopConfig,
    WeChatOperation,
    WeChatVisibleMessage,
    wechat_message_hash,
)
from .window_model import build_wechat_window_model

if TYPE_CHECKING:
    from app_control_protocol import AppControlConfig

_TEXT_LINE_RE = re.compile(
    r"^(?:(?:\[(?P<bracket_ts>[^\]]+)\]|(?P<plain_ts>\d{1,2}:\d{2}))\s+)?"
    r"(?:(?P<label>incoming|outgoing|received|sent|me|you)\s*:\s*)?"
    r"(?P<text>.+)$",
    re.IGNORECASE,
)
_INCOMING_LABELS = {"incoming", "received", "you"}
_OUTGOING_LABELS = {"outgoing", "sent", "me"}
_REDACTED = "[redacted]"
_SENSITIVE_INPUT_KEYS = {"text", "message"}
_LOGIN_REQUIRED_MARKERS = (
    "not logged in",
    "log in to wechat",
    "login to wechat",
    "sign in to wechat",
    "scan qr code",
)
_INPUT_NOT_FOCUSED_MARKERS = (
    "input not focused",
    "text field not focused",
    "no focused input",
    "editable target is not focused",
)
_SEARCH_FOCUS_MARKERS = (
    "search",
    "axsearch",
    "搜索",
    "搜一搜",
    "查找",
)
_CHAT_INPUT_MARKERS = (
    "message input",
    "chat input",
    "type a message",
    "send message",
    "输入消息",
    "聊天输入",
    "消息输入",
)


class WeChatDesktopTool:
    """Semantic WeChat Desktop tool built on an app-control client."""

    def __init__(
        self,
        app_control: AppControlClient,
        config: WeChatDesktopConfig | None = None,
    ) -> None:
        self._app_control = app_control
        self._config = config or WeChatDesktopConfig()

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
            if operation == "focus_contact":
                return self._focus_contact(command, phase_events=phase_events)
            if operation == "observe_current_chat":
                return self._observe_current_chat(command, phase_events=phase_events)
            if operation == "read_visible_messages":
                return self._read_visible_messages(command, phase_events=phase_events)
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
        opened = self._app_control_command(
            command,
            phase="open_wechat",
            operation="open_app",
            input=self._open_app_input(),
            phase_events=phase_events,
        )
        if not opened.success:
            return _from_app_control_failure(command, "wechat_open_failed", opened)
        observed = self._app_control_command(
            command,
            phase="verify_wechat_window",
            operation="observe",
            input=self._target_app_input(),
            phase_events=phase_events,
        )
        evidence: dict[str, JsonValue] = {
            "open": _safe_app_control_observation(opened),
            "observe": _safe_app_control_observation(observed),
        }
        if not observed.success:
            return _from_app_control_failure(
                command,
                "wechat_not_ready",
                observed,
                evidence=evidence,
            )
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
                "appControlObservation": _safe_app_control_observation(opened),
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
        opened = self._app_control_command(
            command,
            phase="open_wechat",
            operation="open_app",
            input=self._open_app_input(),
            phase_events=phase_events,
        )
        evidence["open_wechat"] = _inspect_window_observe_evidence(
            opened,
            include_raw=False,
        )
        if not opened.success:
            return _from_app_control_failure(
                command,
                "wechat_open_failed",
                opened,
                evidence=evidence,
            )
        observed = self._app_control_command(
            command,
            phase="inspect_window",
            operation="observe",
            input=self._target_app_input(
                includeAccessibility=True,
                includeAccessibilityTree=True,
                includeVisibleText=True,
            ),
            phase_events=phase_events,
        )
        evidence["observe"] = _inspect_window_observe_evidence(
            observed,
            include_raw=include_raw,
        )
        if not observed.success:
            return _from_app_control_failure(
                command,
                "wechat_not_ready",
                observed,
                evidence=evidence,
            )
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
        window, normalization = build_wechat_window_model(
            self._config,
            observed,
            include_actionables=include_actionables,
        )
        payload: dict[str, JsonValue] = {
            "schema": WECHAT_WINDOW_SCHEMA,
            "window": window.to_dict(),
            "includeRaw": include_raw,
            "includeActionables": include_actionables,
            "normalization": normalization,
            "wechatEnvironment": _wechat_environment(self._config, observed),
        }
        if include_raw:
            payload["rawObservation"] = observed.observation
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Inspected WeChat window.",
            observation=payload,
            evidence=evidence,
        )

    def _focus_contact(
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
        observed = self._app_control_command(
            command,
            phase="read_visible_messages",
            operation="observe",
            input=self._target_app_input(includeVisibleText=True, limit=limit),
            phase_events=phase_events,
        )
        if not observed.success:
            return _from_app_control_failure(command, "wechat_not_ready", observed)
        identity_failure = _wechat_identity_failure(command, self._config, observed)
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(command, self._config, observed)
        if login_failure is not None:
            return login_failure
        messages, truncated = _messages_from_observation_with_truncation(
            observed,
            limit=limit,
        )
        return ToolObservation.ok(
            command_id=command.command_id,
            tool=WECHAT_TOOL,
            operation=command.operation,
            summary="Read visible WeChat messages.",
            observation={
                "messages": [message.to_dict() for message in messages],
                "truncated": truncated,
                "wechatEnvironment": _wechat_environment(self._config, observed),
            },
            evidence={"observe": _safe_app_control_observation(observed)},
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
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        observation = self._app_control.run_command(
            ToolCommand(
                command_id=f"{parent.command_id}:{phase}",
                tool=self._config.app_control_tool,
                operation=operation,
                input=input,
                timeout_ms=parent.timeout_ms or self._config.default_timeout_ms,
                metadata={
                    "sourceTool": WECHAT_TOOL,
                    "parentCommandId": parent.command_id,
                    "phase": phase,
                },
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


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _duration_ms(started_monotonic: float) -> int:
    return max(0, int(round((time.monotonic() - started_monotonic) * 1000)))


def _with_timing(
    observation: ToolObservation,
    *,
    started_at: str,
    duration_ms: int,
) -> ToolObservation:
    payload = observation.to_dict()
    timing = dict(payload.get("timing", {}))
    timing.setdefault("startedAt", started_at)
    timing.setdefault("durationMs", duration_ms)
    payload["timing"] = timing
    return ToolObservation.from_dict(payload)


def _inspect_window_observe_evidence(
    observation: ToolObservation,
    *,
    include_raw: bool,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "commandId": observation.command_id,
        "tool": observation.tool,
        "operation": observation.operation,
        "status": observation.status.value,
        "success": observation.success,
        "summary": observation.summary,
    }
    if observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    if include_raw:
        payload["observation"] = observation.observation
        if observation.evidence:
            payload["evidence"] = observation.evidence
        return payload

    for output_key, source_keys in (
        ("frontmostApp", ("frontmostApp", "frontmost_app", "appName", "app_name")),
        (
            "frontmostBundleId",
            ("frontmostBundleId", "frontmost_bundle_id", "bundleId", "bundle_id"),
        ),
        ("windowTitle", ("windowTitle", "window_title", "title")),
        ("snapshotId", ("snapshotId", "snapshot_id")),
    ):
        value = _string_from_observation(observation, *source_keys)
        if value is not None:
            payload[output_key] = value

    accessibility = _mapping_from_observation(observation, "accessibility")
    if accessibility is not None:
        payload["accessibility"] = _public_accessibility_status(accessibility)
    return payload


def _public_accessibility_status(
    accessibility: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    available = accessibility.get("available")
    if isinstance(available, bool):
        payload["available"] = available
    elif accessibility:
        payload["available"] = True
    for key in ("failureKind", "message", "timeoutSeconds"):
        value = accessibility.get(key)
        if isinstance(value, str | int | float | bool):
            payload[key] = value
    return payload


def _safe_app_control_observation(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    return _redact_input_text(observation.to_dict())


def _redact_input_text(value: JsonValue, *, in_input: bool = False) -> JsonValue:
    if isinstance(value, dict):
        redacted: dict[str, JsonValue] = {}
        for key, item in value.items():
            child_in_input = in_input or key == "input"
            if child_in_input and key in _SENSITIVE_INPUT_KEYS:
                redacted[key] = _REDACTED
            else:
                redacted[key] = _redact_input_text(
                    item,
                    in_input=child_in_input,
                )
        return redacted
    if isinstance(value, list):
        return [_redact_input_text(item, in_input=in_input) for item in value]
    return value


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
        event = ToolEvent(
            command_id=self._command.command_id,
            seq=self.next_seq(),
            event_type=ToolEventType.PROGRESS,
            phase=phase_name,
            status=observation.status,
            summary=observation.summary,
            data={
                "phase": phase_name,
                "appControlOperation": operation,
                "parentCommandId": parent.command_id,
                "appControlCommandId": observation.command_id,
                "appControlObservation": _safe_app_control_observation(observation),
            },
        )
        self.events.append(event)
        _emit(self._observer, event)

    def next_seq(self) -> int:
        seq = self._next_seq
        self._next_seq += 1
        return seq


def _required_input(command: ToolCommand, key: str) -> str:
    value = command.input.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _string_input(command: ToolCommand, key: str, *, default: str) -> str:
    value = command.input.get(key)
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _bool_input(command: ToolCommand, *keys: str, default: bool) -> bool:
    for key in keys:
        if key in command.input:
            value = command.input[key]
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
            return value
    return default


def _positive_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("limit must be a positive integer")
    return value


def _messages_from_observation(
    observation: ToolObservation,
    *,
    limit: int,
) -> tuple[WeChatVisibleMessage, ...]:
    messages, _truncated = _messages_from_observation_with_truncation(
        observation,
        limit=limit,
    )
    return messages


def _messages_from_observation_with_truncation(
    observation: ToolObservation,
    *,
    limit: int,
) -> tuple[tuple[WeChatVisibleMessage, ...], bool]:
    raw_messages = observation.observation.get("messages")
    if isinstance(raw_messages, list):
        messages: list[WeChatVisibleMessage] = []
        for item in raw_messages:
            message = _message_from_raw(item)
            if message is not None:
                messages.append(message)
            if len(messages) > limit:
                break
        return tuple(messages[:limit]), len(messages) > limit
    text_extract = observation.evidence.get(
        "textExtract"
    ) or observation.observation.get("textExtract")
    if isinstance(text_extract, str) and text_extract.strip():
        return _messages_from_text_extract_with_truncation(text_extract, limit=limit)
    return (), False


def _messages_from_text_extract(
    text_extract: str,
    *,
    limit: int,
) -> tuple[WeChatVisibleMessage, ...]:
    messages, _truncated = _messages_from_text_extract_with_truncation(
        text_extract,
        limit=limit,
    )
    return messages


def _messages_from_text_extract_with_truncation(
    text_extract: str,
    *,
    limit: int,
) -> tuple[tuple[WeChatVisibleMessage, ...], bool]:
    messages: list[WeChatVisibleMessage] = []
    for raw_line in text_extract.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        message = _message_from_text_line(line)
        if message is not None:
            messages.append(message)
        if len(messages) > limit:
            break
    return tuple(messages[:limit]), len(messages) > limit


def _message_from_text_line(line: str) -> WeChatVisibleMessage | None:
    match = _TEXT_LINE_RE.match(line)
    if match is None:
        return WeChatVisibleMessage(text=line)
    text = match.group("text").strip()
    if not text:
        return None
    return WeChatVisibleMessage(
        text=text,
        direction=_direction_from_text_label(match.group("label")),
        visible_timestamp=match.group("bracket_ts") or match.group("plain_ts"),
    )


def _direction_from_text_label(label: str | None) -> str:
    if label is None:
        return "unknown"
    normalized = label.casefold()
    if normalized in _INCOMING_LABELS:
        return "incoming"
    if normalized in _OUTGOING_LABELS:
        return "outgoing"
    return "unknown"


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


def _wechat_environment(
    config: WeChatDesktopConfig,
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "configuredAppName": config.app_name,
    }
    if config.bundle_id is not None:
        payload["configuredBundleId"] = config.bundle_id
    field_map = (
        ("frontmostApp", ("frontmostApp", "frontmost_app", "appName", "app_name")),
        (
            "frontmostBundleId",
            ("frontmostBundleId", "frontmost_bundle_id", "bundleId", "bundle_id"),
        ),
        ("windowTitle", ("windowTitle", "window_title", "title")),
        (
            "appVersion",
            (
                "frontmostVersion",
                "frontmost_version",
                "appVersion",
                "app_version",
                "version",
            ),
        ),
    )
    for output_key, source_keys in field_map:
        value = _string_from_observation(observation, *source_keys)
        if value is not None:
            payload[output_key] = value
    return payload


def _current_chat_title(window_title: str | None, app_name: str) -> str | None:
    if not window_title:
        return None
    title = window_title.strip()
    for separator in (" - ", " — ", " – ", " | "):
        suffix = separator + app_name
        if title.endswith(suffix):
            return title[: -len(suffix)].strip() or None
    return title


def _contact_confidence(contact: str, current_chat_title: str | None) -> float:
    if current_chat_title is None:
        return 0.8
    normalized_contact = contact.casefold()
    normalized_title = current_chat_title.casefold()
    if normalized_contact == normalized_title:
        return 0.95
    if normalized_contact in normalized_title or normalized_title in normalized_contact:
        return 0.9
    return 0.75


def _message_observed(message: str, observation: ToolObservation) -> bool:
    expected = message.strip()
    if not expected:
        return False
    for visible_message in _messages_from_observation(observation, limit=100):
        if expected in visible_message.text:
            return True
    return False


def _message_from_raw(raw: object) -> WeChatVisibleMessage | None:
    if isinstance(raw, str):
        return WeChatVisibleMessage(text=raw) if raw.strip() else None
    if isinstance(raw, dict):
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        direction = raw.get("direction", "unknown")
        visible_timestamp = raw.get("visibleTimestamp") or raw.get("visible_timestamp")
        return WeChatVisibleMessage(
            text=text,
            direction=direction if isinstance(direction, str) else "unknown",
            visible_timestamp=(
                visible_timestamp if isinstance(visible_timestamp, str) else None
            ),
        )
    return None


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


def _observation_indicates_login_required(observation: ToolObservation) -> bool:
    truthy_fields = (
        "loginRequired",
        "login_required",
        "requiresLogin",
        "requires_login",
    )
    false_fields = (
        "loggedIn",
        "logged_in",
        "isLoggedIn",
        "is_logged_in",
        "authenticated",
        "isAuthenticated",
    )
    for payload in (observation.observation, observation.evidence):
        for key in truthy_fields:
            if payload.get(key) is True:
                return True
        for key in false_fields:
            if payload.get(key) is False:
                return True
        status = payload.get("loginStatus") or payload.get("login_status")
        if isinstance(status, str) and status.strip().casefold() in {
            "logged_out",
            "login_required",
            "not_logged_in",
        }:
            return True
    text = _string_from_observation(
        observation,
        "textExtract",
        "visibleText",
        "windowTitle",
        "window_title",
        "title",
    )
    if text is None:
        return False
    normalized = text.casefold()
    return any(marker in normalized for marker in _LOGIN_REQUIRED_MARKERS)


def _contact_ambiguity_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    matches = _contact_matches_from_observation(observation)
    ambiguous = _bool_from_observation(
        observation,
        "contactAmbiguous",
        "contact_ambiguous",
        "ambiguous",
    )
    if ambiguous is not True and len(matches) <= 1:
        return None
    observation_payload: dict[str, JsonValue] = {
        "requestedContact": contact,
        "candidateContacts": matches,
    }
    return _failure(
        command,
        status=ToolStatus.NOT_FOUND,
        failure_kind="contact_ambiguous",
        message="Multiple WeChat contacts matched the requested contact.",
        recovery_hint="Use a more specific contact display name before retrying.",
        retryable=True,
        observation=observation_payload,
        evidence=evidence,
    )


def _search_focus_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    assessment = _search_focus_assessment(observation)
    state = assessment.get("state")
    if state in {"verified", "unknown"}:
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


def _mapping_from_observation(
    observation: ToolObservation,
    key: str,
) -> dict[str, JsonValue] | None:
    for payload in (observation.observation, observation.evidence):
        mapped = _mapping_value(payload.get(key))
        if mapped is not None:
            return mapped
    return None


def _mapping_value(value: object) -> dict[str, JsonValue] | None:
    return value if isinstance(value, dict) else None


def _public_accessibility_element(
    element: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    for key in (
        "role",
        "roleDescription",
        "name",
        "description",
        "title",
        "focused",
        "frame",
    ):
        value = element.get(key)
        if isinstance(value, str | bool | dict):
            payload[key] = value
    index = element.get("index")
    if isinstance(index, int) and not isinstance(index, bool):
        payload["index"] = index
    return payload


def _is_text_like_accessibility_element(element: dict[str, JsonValue]) -> bool:
    text = _accessibility_element_text(element)
    return any(
        marker in text
        for marker in (
            "text",
            "edit",
            "search",
            "axtextfield",
            "axtextarea",
            "axsearchfield",
            "文本",
            "输入",
            "搜索",
        )
    )


def _accessibility_element_contains(
    element: dict[str, JsonValue],
    markers: tuple[str, ...],
) -> bool:
    text = _accessibility_element_text(element)
    return any(marker.casefold() in text for marker in markers)


def _accessibility_element_text(element: dict[str, JsonValue]) -> str:
    parts: list[str] = []
    for key in ("role", "roleDescription", "name", "description", "title", "value"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts).casefold()


def _focused_text_field_position(
    focused: dict[str, JsonValue],
    accessibility: dict[str, JsonValue],
) -> str | None:
    focused_y = _element_frame_int(focused, "y")
    if focused_y is None:
        return None
    raw_fields = accessibility.get("textFields")
    if not isinstance(raw_fields, list):
        return None
    y_values = [
        y
        for item in raw_fields
        if isinstance(item, dict)
        for y in [_element_frame_int(item, "y")]
        if y is not None
    ]
    if len(y_values) < 2:
        return None
    top = min(y_values)
    bottom = max(y_values)
    if bottom <= top:
        return None
    threshold = max(20, int(round((bottom - top) * 0.25)))
    if focused_y <= top + threshold:
        return "top"
    if focused_y >= bottom - threshold:
        return "bottom"
    return None


def _element_frame_int(element: Mapping[str, JsonValue], key: str) -> int | None:
    frame = element.get("frame")
    if not isinstance(frame, dict):
        return None
    value = frame.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _contact_matches_from_observation(
    observation: ToolObservation,
) -> list[str]:
    matches: list[str] = []
    for payload in (observation.observation, observation.evidence):
        for key in (
            "contactMatches",
            "contact_matches",
            "candidateContacts",
            "candidate_contacts",
            "searchResults",
            "search_results",
        ):
            raw_matches = payload.get(key)
            matches.extend(_contact_match_names(raw_matches))
    return _dedupe_strings(matches)


def _contact_match_names(raw_matches: JsonValue | None) -> list[str]:
    if not isinstance(raw_matches, list):
        return []
    matches: list[str] = []
    for item in raw_matches:
        if isinstance(item, str) and item.strip():
            matches.append(item.strip())
        elif isinstance(item, dict):
            for key in ("name", "displayName", "display_name", "contact", "title"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    matches.append(value.strip())
                    break
    return matches


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _bool_from_observation(
    observation: ToolObservation,
    *keys: str,
) -> bool | None:
    for payload in (observation.observation, observation.evidence):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                return value
    return None


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


def _observation_indicates_input_not_focused(observation: ToolObservation) -> bool:
    if observation.failure_kind in {
        "input_not_focused",
        "target_not_focused",
        "focus_failed",
    }:
        return True
    explicit_focus = _bool_from_observation(
        observation,
        "inputFocused",
        "input_focused",
        "focusedInput",
        "focused_input",
        "textInputFocused",
        "text_input_focused",
    )
    if explicit_focus is False:
        return True
    diagnostics = " ".join(
        part
        for part in (observation.summary, observation.message)
        if isinstance(part, str)
    ).casefold()
    return any(marker in diagnostics for marker in _INPUT_NOT_FOCUSED_MARKERS)


def _wechat_not_ready_failure(
    command: ToolCommand,
    message: str,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="wechat_not_ready",
        message=message,
        retryable=True,
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


def _nested_failure(
    command: ToolCommand,
    phase: str,
    result: ToolObservation,
) -> ToolObservation:
    observation = dict(result.observation)
    observation.setdefault("failedPhase", phase)
    return _failure(
        command,
        status=result.status,
        failure_kind=result.failure_kind or f"{phase}_failed",
        message=result.summary,
        recovery_hint=result.recovery_hint,
        retryable=result.retryable if result.retryable is not None else False,
        observation=observation,
        evidence={phase: result.to_dict()},
    )


def _send_unverified(
    command: ToolCommand,
    *,
    contact: str,
    message: str,
    focus: ToolObservation,
    draft: ToolObservation,
    submitted: ToolObservation,
    verification: ToolObservation,
    reason: str,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        status=ToolStatus.UNKNOWN,
        error=ToolError(
            failure_kind="send_unverified",
            message=reason,
            recovery_hint="Check WeChat manually before retrying.",
            retryable=False,
            phase="verification",
            operation=command.operation,
            evidence={
                "focus": focus.to_dict(),
                "draft": draft.to_dict(),
                "submit": submitted.to_dict(),
                "verification": verification.to_dict(),
            },
        ),
        summary=reason,
        observation={
            "focusedContact": contact,
            "messageHash": wechat_message_hash(message),
            "submitted": True,
            "verified": False,
            "verificationRequested": True,
        },
    )


def _failure(
    command: ToolCommand,
    *,
    status: ToolStatus,
    failure_kind: str,
    message: str,
    recovery_hint: str | None = None,
    retryable: bool = False,
    observation: dict[str, JsonValue] | None = None,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        status=status,
        error=ToolError(
            failure_kind=failure_kind,
            message=message,
            recovery_hint=recovery_hint,
            retryable=retryable,
            phase=command.operation,
            operation=command.operation,
            evidence=evidence or {},
        ),
        summary=message,
        observation=observation,
    )


def _event(
    command: ToolCommand,
    seq: int,
    event_type: ToolEventType,
    observation: ToolObservation | None = None,
) -> ToolEvent:
    return ToolEvent(
        command_id=command.command_id,
        seq=seq,
        event_type=event_type,
        phase=command.operation,
        status=observation.status if observation else None,
        summary=observation.summary if observation else f"Started {command.operation}.",
        data={"observation": observation.to_dict()} if observation else {},
    )


def _emit(observer: ToolObserver | None, event: ToolEvent) -> None:
    if observer is not None:
        observer.on_event(event)
