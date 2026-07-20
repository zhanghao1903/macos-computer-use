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
    _duration_ms,
    _emit,
    _event,
    _failure,
    _utc_now,
    _with_timing,
)
from ._message_operations import (
    _draft_message,
    _observe_current_chat,
    _read_contact_messages,
    _read_visible_messages,
    _send_message,
    _submit_draft,
)
from ._runtime import (
    _PhaseEventCollector,
    WeChatToolRuntime,
)
from ._window_operations import _inspect_window, _open_wechat

from .commands import WECHAT_TOOL
from .control_map import WeChatControlMap
from .models import WeChatDesktopConfig
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
                return _observe_current_chat(
                    self._runtime, command, phase_events=phase_events
                )
            if operation == "read_visible_messages":
                return _read_visible_messages(
                    self._runtime, command, phase_events=phase_events
                )
            if operation == "read_contact_messages":
                return _read_contact_messages(
                    self._runtime, command, phase_events=phase_events
                )
            if operation == "draft_message":
                return _draft_message(self._runtime, command, phase_events=phase_events)
            if operation == "submit_draft":
                return _submit_draft(self._runtime, command, phase_events=phase_events)
            if operation == "send_message":
                return _send_message(self._runtime, command, phase_events=phase_events)
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


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command
