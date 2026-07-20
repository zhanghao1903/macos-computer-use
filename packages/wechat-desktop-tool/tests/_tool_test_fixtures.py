from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import redirect_stdout
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from importlib import resources
from io import StringIO
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import _tool_test_support as tool_test_support
from app_control_protocol import (
    AppControlConfig,
    LoggingConfig,
    LoggingToolObserver,
    ToolCommand,
    ToolError,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolStatus,
    validate_protocol_payload,
)
from computer_use_macos import ComputerUseClient
from computer_use_macos.client import _AccessibilityWorker
from computer_use_macos.client import _accessibility_action_worker_script
from computer_use_macos.commands import CommandResult
import wechat_desktop_tool._action_operations as action_operations_module
import wechat_desktop_tool._action_safety as action_safety_module
import wechat_desktop_tool._contact_operations as contact_operations_module
import wechat_desktop_tool._contact_search as contact_search_module
import wechat_desktop_tool._query_mapping as query_mapping_module
import wechat_desktop_tool.cli as cli_module
from wechat_desktop_tool import (
    WECHAT_WINDOW_SCHEMA,
    WECHAT_TOOL,
    WeChatDesktopConfig,
    WeChatDesktopTool,
    WeChatWindow,
    build_wechat_tool,
    draft_message_command,
    execute_action_command,
    focus_contact_command,
    inspect_window_command,
    list_contacts_command,
    list_conversations_command,
    observe_current_chat_command,
    open_contact_command,
    open_wechat_command,
    read_contact_messages_command,
    read_visible_messages_command,
    send_message,
    send_message_command,
    submit_draft_command,
    wechat_command,
    wechat_message_hash,
)
from wechat_desktop_tool.cli import LocalServiceAppControl
from wechat_desktop_tool.cli import _app_control_for_args
from wechat_desktop_tool.cli import main as cli_main
from wechat_desktop_tool.window_model import build_wechat_window_model


_accessibility_action_failure_with_observation = (
    tool_test_support.accessibility_action_failure_with_observation
)
_contradictory_predispatch_action_response = (
    tool_test_support.contradictory_predispatch_action_response
)
_definite_unsupported_accessibility_action_response = (
    tool_test_support.definite_unsupported_accessibility_action_response
)
_failed_accessibility_action_response = (
    tool_test_support.failed_accessibility_action_response
)
_predispatch_accessibility_action_response = (
    tool_test_support.predispatch_accessibility_action_response
)


class FakeAppControl:
    def __init__(self, responses: list[dict[str, Any] | ToolObservation] | None = None):
        self.commands: list[ToolCommand] = []
        self._responses = list(responses or [])
        self._last_typed_text: str | None = None

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = (
            ToolCommand.from_dict(dict(command))
            if isinstance(command, Mapping)
            else command
        )
        self.commands.append(tool_command)
        if tool_command.operation == "type_text":
            text = tool_command.input.get("text")
            if isinstance(text, str) and text:
                self._last_typed_text = text
        if tool_command.operation == "observe" and (
            not self._responses or not _is_explicit_observe_response(self._responses[0])
        ):
            if self._responses and self._responses[0] == {}:
                self._responses.pop(0)
            return _default_observe_response(
                tool_command,
                current_contact=self._last_typed_text,
            )
        phase = tool_command.metadata.get("phase") if tool_command.metadata else None
        if (
            tool_command.operation == "accessibility_query"
            and isinstance(phase, str)
            and phase.startswith("verify_search_focus")
            and (not self._responses or self._responses[0] == {})
        ):
            if self._responses and self._responses[0] == {}:
                self._responses.pop(0)
            return _default_search_focus_query_response(tool_command)
        if self._responses:
            response = self._responses.pop(0)
            if isinstance(response, ToolObservation):
                return response
            return ToolObservation.ok(
                command_id=tool_command.command_id,
                tool=tool_command.tool,
                operation=tool_command.operation,
                summary=response.get("summary", "app-control ok"),
                observation=response.get("observation", {}),
                evidence=response.get("evidence", {}),
            )
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary=f"app-control ok: {tool_command.operation}",
            observation={"input": tool_command.input},
        )


class CrossPackageActionAppControl:
    def __init__(self, client: ComputerUseClient) -> None:
        self.client = client
        self.commands: list[ToolCommand] = []
        self.observations: list[ToolObservation] = []

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = (
            ToolCommand.from_dict(dict(command))
            if isinstance(command, Mapping)
            else command
        )
        self.commands.append(tool_command)
        if tool_command.operation == "accessibility_action":
            result = self.client.run_command(tool_command)
            self.observations.append(result)
            return result
        phase = tool_command.metadata.get("phase") if tool_command.metadata else None
        if (
            tool_command.operation == "accessibility_query"
            and isinstance(phase, str)
            and phase.startswith("verify_search_focus")
        ):
            result = _default_search_focus_query_response(tool_command)
            self.observations.append(result)
            return result
        result = ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary=f"synthetic fallback ok: {tool_command.operation}",
            observation={"input": tool_command.input},
        )
        self.observations.append(result)
        return result


class CrossPackageProbe:
    def platform_name(self) -> str:
        return "Darwin"

    def accessibility_trusted(self) -> bool:
        return True

    def screen_recording_available(self) -> bool:
        return True

    def apple_events_available(self) -> bool:
        return True


class NoFallbackRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        args: list[str] | tuple[str, ...],
        *,
        timeout: float,
    ) -> CommandResult:
        del timeout
        self.calls.append(tuple(args))
        return CommandResult(0, "", "")


def _cross_package_action_worker_script(mode: str, log_path: Path) -> str:
    return r"""
import json
from pathlib import Path
import sys
import time

MODE = __MODE__
LOG_PATH = Path(__LOG_PATH__)

print(
    json.dumps({"workerReady": True, "status": "ok", "message": ""}),
    flush=True,
)
for line in sys.stdin:
    request = json.loads(line)
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(request) + "\n")
    if MODE == "eof":
        sys.exit(0)
    if MODE == "timeout":
        time.sleep(10)
    elif MODE == "malformed":
        print("{not-json", flush=True)
    else:
        action = request["action"]
        native_unsupported_modes = {
            "native_unsupported",
            "native_unsupported_contradictory",
            "native_unsupported_missing_effect",
            "native_unsupported_cannot_complete",
            "native_unsupported_wrong_code",
            "native_unsupported_missing_code",
            "native_unsupported_missing_action",
            "native_unsupported_attempted_false",
            "native_unsupported_invalid_effect",
            "native_unsupported_empty_effect",
            "native_unsupported_non_int_code",
        }
        attempted = (
            MODE in {"native_failure", "legacy_unsupported_attempted"}
            or (
                MODE in native_unsupported_modes
                and MODE != "native_unsupported_attempted_false"
            )
        )
        if MODE == "native_failure":
            failure_kind = "accessibility_action_failed"
            action_effect = "unknown"
            native_error_code = -25204
        elif MODE in native_unsupported_modes:
            failure_kind = "accessibility_action_unsupported"
            if MODE == "native_unsupported_contradictory":
                action_effect = "unknown"
            elif MODE == "native_unsupported_missing_effect":
                action_effect = None
            elif MODE == "native_unsupported_invalid_effect":
                action_effect = {"value": "none"}
            elif MODE == "native_unsupported_empty_effect":
                action_effect = ""
            else:
                action_effect = "none"
            native_error_code = -25205 if action == "AXSetFocus" else -25206
            if MODE == "native_unsupported_cannot_complete":
                native_error_code = -25204
            elif MODE == "native_unsupported_wrong_code":
                native_error_code = -25206 if action == "AXSetFocus" else -25205
            elif MODE == "native_unsupported_missing_code":
                native_error_code = None
            elif MODE == "native_unsupported_non_int_code":
                native_error_code = str(native_error_code)
        elif MODE == "legacy_unsupported_attempted":
            failure_kind = "unsupported_accessibility_action"
            action_effect = "none"
            native_error_code = -25206
        else:
            failure_kind = "unsupported_accessibility_action"
            action_effect = None
            native_error_code = None
        payload = {
            "schema": "macos.accessibility.action.result.v1",
            "available": False,
            "status": "failed",
            "failureKind": failure_kind,
            "message": failure_kind,
            "actionAttempted": attempted,
            "target": {
                "axPath": request["target"]["axPath"],
                "role": "AXTextArea" if action == "AXSetFocus" else "AXRow",
                "label": "Search" if action == "AXSetFocus" else "File Transfer",
                "actions": [] if action == "AXSetFocus" else ["AXPress"],
            },
        }
        if MODE != "native_unsupported_missing_action":
            payload["action"] = action
        if action_effect is not None:
            payload["actionEffect"] = action_effect
        if native_error_code is not None:
            payload["nativeErrorCode"] = native_error_code
        print(
            json.dumps(payload),
            flush=True,
        )
""".replace(
        "__MODE__", repr(mode)
    ).replace(
        "__LOG_PATH__", repr(str(log_path))
    )


def _cross_package_action_fixture(
    mode: str,
    log_path: Path,
    *,
    timeout_ms: int,
) -> tuple[
    ComputerUseClient,
    _AccessibilityWorker,
    CrossPackageActionAppControl,
    NoFallbackRunner,
    WeChatDesktopTool,
]:
    runner = NoFallbackRunner()
    client = ComputerUseClient.from_config(
        {
            "computer_use": {
                "backend": "direct",
                "allowed_apps": ["WeChat"],
                "allowed_app_bundle_ids": {"WeChat": "com.tencent.xinWeChat"},
            }
        },
        probe=CrossPackageProbe(),
        runner=runner,
    )
    worker = _AccessibilityWorker(
        worker_name="action",
        worker_script=_cross_package_action_worker_script(mode, log_path),
    )
    app_control = CrossPackageActionAppControl(client)
    tool = WeChatDesktopTool(
        app_control,
        WeChatDesktopConfig(default_timeout_ms=timeout_ms),
    )
    return client, worker, app_control, runner, tool


def _production_action_fixture(
    *,
    timeout_ms: int,
) -> tuple[
    ComputerUseClient,
    _AccessibilityWorker,
    CrossPackageActionAppControl,
    NoFallbackRunner,
    WeChatDesktopTool,
]:
    runner = NoFallbackRunner()
    client = ComputerUseClient.from_config(
        {
            "computer_use": {
                "backend": "direct",
                "allowed_apps": ["WeChat"],
                "allowed_app_bundle_ids": {"WeChat": "com.tencent.xinWeChat"},
            }
        },
        probe=CrossPackageProbe(),
        runner=runner,
    )
    worker = _AccessibilityWorker(
        worker_name="action",
        worker_script=_accessibility_action_worker_script(),
    )
    app_control = CrossPackageActionAppControl(client)
    tool = WeChatDesktopTool(
        app_control,
        WeChatDesktopConfig(default_timeout_ms=timeout_ms),
    )
    return client, worker, app_control, runner, tool


def _write_fake_accessibility_modules(directory: Path) -> None:
    (directory / "objc.py").write_text(
        """
class _Application:
    def bundleIdentifier(self):
        return "com.tencent.xinWeChat"

    def localizedName(self):
        return "WeChat"

    def isTerminated(self):
        return False

    def isHidden(self):
        return False

    def isActive(self):
        return True

    def processIdentifier(self):
        return 123


_APPLICATION = _Application()


class _WorkspaceInstance:
    def frontmostApplication(self):
        return _APPLICATION


class _Workspace:
    @classmethod
    def sharedWorkspace(cls):
        return _WorkspaceInstance()


class _RunningApplication:
    @classmethod
    def runningApplicationsWithBundleIdentifier_(cls, bundle_id):
        return [_APPLICATION]


def loadBundle(name, namespace, bundle_path):
    return None


def lookUpClass(name):
    if name == "NSWorkspace":
        return _Workspace
    if name == "NSRunningApplication":
        return _RunningApplication
    raise LookupError(name)
""".lstrip(),
        encoding="utf-8",
    )
    (directory / "ApplicationServices.py").write_text(
        """
import os

kAXErrorActionUnsupported = -25206
kAXErrorAttributeUnsupported = -25205
kAXFocusedWindowAttribute = "AXFocusedWindow"

_ACTION = os.environ.get("FAKE_AX_ACTION", "AXPress")
_TARGET = {
    "AXRole": "AXTextArea" if _ACTION == "AXSetFocus" else "AXRow",
    "AXDescription": "Search" if _ACTION == "AXSetFocus" else "File Transfer",
    "AXEnabled": True,
    "AXChildren": [],
    "AXActions": [] if _ACTION == "AXSetFocus" else ["AXPress"],
}
_WINDOW = {
    "AXRole": "AXWindow",
    "AXTitle": "微信 (聊天)",
    "AXChildren": [_TARGET],
}
_APPLICATION = {"AXFocusedWindow": _WINDOW, "AXWindows": [_WINDOW]}


def AXIsProcessTrusted():
    return True


def AXUIElementCreateApplication(pid):
    return _APPLICATION


def AXUIElementCopyAttributeValue(element, attribute, unused):
    return 0, element.get(attribute)


def AXUIElementCopyActionNames(element, unused):
    return 0, element.get("AXActions", [])


def AXUIElementPerformAction(element, action):
    return kAXErrorActionUnsupported


def AXUIElementSetAttributeValue(element, attribute, value):
    return kAXErrorAttributeUnsupported
""".lstrip(),
        encoding="utf-8",
    )


def _click_node_phase_for_test(
    tool: WeChatDesktopTool,
    *args: Any,
    **kwargs: Any,
) -> ToolObservation:
    return action_operations_module._click_node_phase(
        tool._runtime,
        *args,
        **kwargs,
    )


def _open_visible_contact_for_test(
    tool: WeChatDesktopTool,
    *args: Any,
    **kwargs: Any,
) -> ToolObservation | None:
    return contact_operations_module._open_visible_contact_phase(
        tool._runtime,
        *args,
        **kwargs,
    )


def _open_visible_contact_with_control_map_for_test(
    tool: WeChatDesktopTool,
    *args: Any,
    **kwargs: Any,
) -> ToolObservation | None:
    return contact_operations_module._open_visible_contact_with_control_map(
        tool._runtime,
        *args,
        **kwargs,
    )


def _cross_package_click_node(
    tool: WeChatDesktopTool,
    *,
    ax_path: str = "0/11/1/0/0",
) -> ToolObservation:
    return _click_node_phase_for_test(
        tool,
        wechat_command("open_contact", {"contact": "File Transfer"}),
        _normalized_row(ax_path, "File Transfer"),
        phase="open_visible_contact",
        evidence={},
        snapshot_id="frontmost:WeChat:微信 (聊天)",
    )


def _cross_package_focus_search(
    tool: WeChatDesktopTool,
    *,
    ax_path: str = "0/11/0",
) -> ToolObservation:
    search_element = argparse.Namespace(
        role="AXTextArea",
        label="Search",
        actions=(),
        element_ref=argparse.Namespace(
            ax_path=ax_path,
            snapshot_id="frontmost:WeChat:微信 (聊天)",
        ),
        frame=None,
    )
    return _focus_search_box_for_test(
        tool,
        wechat_command("open_contact", {"contact": "File Transfer"}),
        contact="File Transfer",
        search_box=argparse.Namespace(elements=[search_element]),
        evidence={},
    )


def _focus_search_box_for_test(
    tool: WeChatDesktopTool,
    *args: Any,
    **kwargs: Any,
) -> ToolObservation:
    return contact_search_module._focus_search_box_phase(
        tool._runtime,
        *args,
        **kwargs,
    )


def _is_explicit_observe_response(response: dict[str, Any] | ToolObservation) -> bool:
    if isinstance(response, ToolObservation):
        return response.operation == "observe"
    if not response:
        return False
    observation = response.get("observation")
    if not isinstance(observation, Mapping):
        return False
    return any(
        key in observation
        for key in (
            "frontmostApp",
            "frontmostBundleId",
            "windowTitle",
            "textExtract",
            "accessibility",
        )
    )


def _default_observe_response(
    command: ToolCommand,
    *,
    current_contact: str | None = None,
) -> ToolObservation:
    target_app = str(
        command.input.get("targetApp") or command.input.get("app") or "WeChat"
    )
    bundle_id = str(
        command.input.get("bundleId")
        or command.input.get("bundle_id")
        or "com.tencent.xinWeChat"
    )
    observation: dict[str, Any] = {
        "frontmostApp": target_app,
        "frontmostBundleId": bundle_id,
        "windowTitle": "微信 (聊天)",
    }
    phase = command.metadata.get("phase") if command.metadata else None
    if isinstance(phase, str) and phase.startswith("verify_search_focus"):
        observation["accessibility"] = {
            "available": True,
            "focusedElement": {
                "role": "AXTextField",
                "roleDescription": "search field",
                "description": "搜索",
                "frame": {
                    "x": 80,
                    "y": 120,
                    "width": 240,
                    "height": 28,
                },
            },
        }
    elif phase == "verify_contact" and current_contact is not None:
        observation["windowTitle"] = f"{current_contact} - WeChat"
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        summary=f"Frontmost app: {target_app}. Window: 微信 (聊天).",
        observation=observation,
    )


def _default_search_focus_query_response(command: ToolCommand) -> ToolObservation:
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        summary="Focused WeChat search element.",
        observation=_accessibility_query_response(
            [
                _normalized_node(
                    "0/11/0",
                    "AXTextArea",
                    description="搜索",
                    focused=True,
                    x=345,
                    y=50,
                    width=205,
                    height=26,
                )
            ]
        )["observation"],
    )


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[ToolEvent] = []

    def on_event(self, event: ToolEvent) -> None:
        self.events.append(event)


def _wechat_window_tree_fixture() -> dict[str, Any]:
    def node(
        path: str,
        role: str,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        description: str | None = None,
        title: str | None = None,
        value: object | None = None,
        actions: list[str] | None = None,
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": path,
            "AXRole": role,
            "AXPosition": {"x": x, "y": y},
            "AXSize": {"width": width, "height": height},
            "children_count": len(children or []),
        }
        if description is not None:
            payload["AXDescription"] = description
        if title is not None:
            payload["AXTitle"] = title
        if value is not None:
            payload["AXValue"] = value
        if actions:
            payload["actions"] = actions
        if children is not None:
            payload["children"] = children
        return payload

    def conversation_row(
        index: int,
        y: float,
        description: str,
    ) -> dict[str, Any]:
        return node(
            f"0/11/1/0/{index}",
            "AXRow",
            x=329,
            y=y,
            width=271,
            height=68,
            actions=["AXPress"],
            children=[
                node(
                    f"0/11/1/0/{index}/0",
                    "AXCell",
                    x=329,
                    y=y,
                    width=271,
                    height=68,
                    description=description,
                    children=[],
                )
            ],
        )

    def message_row(index: int, y: float, text: str) -> dict[str, Any]:
        return node(
            f"0/11/4/0/0/{index}",
            "AXRow",
            x=599,
            y=y,
            width=977,
            height=60,
            children=[
                node(
                    f"0/11/4/0/0/{index}/0",
                    "AXCell",
                    x=620,
                    y=y + 8,
                    width=320,
                    height=40,
                    description=text,
                    children=[],
                )
            ],
        )

    conversation_table = node(
        "0/11/1/0",
        "AXTable",
        x=328,
        y=91,
        width=273,
        height=1000,
        children=[
            conversation_row(
                0,
                92,
                "文件传输助手,hello,09:00,置顶",
            ),
            conversation_row(
                1,
                160,
                "目标联系人,最近消息,10:00,消息免打扰",
            ),
            conversation_row(
                2,
                1400,
                "屏幕外联系人,不可见,10:30",
            ),
        ],
    )
    message_table = node(
        "0/11/4/0/0",
        "AXTable",
        x=598,
        y=123,
        width=979,
        height=700,
        children=[
            message_row(0, 160, "你好"),
            message_row(1, 230, "收到"),
        ],
    )
    chat_panel = node(
        "0/11/4",
        "AXSplitGroup",
        x=599,
        y=32,
        width=977,
        height=965,
        children=[
            node(
                "0/11/4/0",
                "AXScrollArea",
                x=599,
                y=123,
                width=977,
                height=659,
                actions=["AXScrollDownByPage"],
                children=[message_table],
            ),
            node(
                "0/11/4/1",
                "AXButton",
                x=1535,
                y=49,
                width=26,
                height=26,
                description="个人卡片",
                actions=["AXPress"],
                children=[],
            ),
            node(
                "0/11/4/2",
                "AXStaticText",
                x=624,
                y=51,
                width=111,
                height=21,
                value="目标联系人",
                children=[],
            ),
            node(
                "0/11/4/4",
                "AXButton",
                x=614,
                y=818,
                width=26,
                height=26,
                title="表情",
                actions=["AXPress"],
                children=[],
            ),
            node(
                "0/11/4/10",
                "AXButton",
                x=654,
                y=818,
                width=26,
                height=26,
                title="附件",
                actions=["AXPress"],
                children=[],
            ),
            node(
                "0/11/4/11",
                "AXScrollArea",
                x=605,
                y=858,
                width=965,
                height=133,
                children=[
                    node(
                        "0/11/4/11/0",
                        "AXTextArea",
                        x=605,
                        y=858,
                        width=965,
                        height=133,
                        title="目标联系人",
                        value="草稿",
                        actions=["AXShowMenu"],
                        children=[],
                    )
                ],
            ),
        ],
    )
    main_split = node(
        "0/11",
        "AXSplitGroup",
        x=329,
        y=32,
        width=1247,
        height=965,
        children=[
            node(
                "0/11/0",
                "AXTextArea",
                x=345,
                y=50,
                width=205,
                height=26,
                description="搜索",
                children=[],
            ),
            node(
                "0/11/1",
                "AXScrollArea",
                x=329,
                y=92,
                width=271,
                height=905,
                actions=["AXScrollDownByPage"],
                children=[conversation_table],
            ),
            node(
                "0/11/2",
                "AXButton",
                x=557,
                y=49,
                width=28,
                height=28,
                description="发起群聊",
                actions=["AXPress"],
                children=[],
            ),
            chat_panel,
        ],
    )
    return node(
        "0",
        "AXWindow",
        x=269,
        y=32,
        width=1307,
        height=965,
        title="微信 (聊天)",
        actions=["AXRaise"],
        children=[
            node(
                "0/1",
                "AXRadioButton",
                x=268,
                y=159,
                width=62,
                height=34,
                description="聊天",
                value=1,
                actions=["AXPress"],
                children=[],
            ),
            node(
                "0/2",
                "AXRadioButton",
                x=268,
                y=207,
                width=62,
                height=34,
                description="通讯录",
                value=0,
                actions=["AXPress"],
                children=[],
            ),
            node(
                "0/3",
                "AXRadioButton",
                x=268,
                y=255,
                width=62,
                height=34,
                description="收藏",
                value=0,
                actions=["AXPress"],
                children=[],
            ),
            main_split,
        ],
    )


def _query_node_from_tree(node: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "axPath": node.get("path", "0"),
        "role": node.get("AXRole", "AXUnknown"),
        "childrenCount": node.get("children_count", 0),
    }
    if "AXDescription" in node:
        payload["description"] = node["AXDescription"]
    if "AXTitle" in node:
        payload["title"] = node["AXTitle"]
    if "AXValue" in node:
        payload["value"] = node["AXValue"]
    if "actions" in node:
        payload["actions"] = node["actions"]
    position = node.get("AXPosition")
    size = node.get("AXSize")
    if isinstance(position, Mapping) and isinstance(size, Mapping):
        payload["frame"] = {
            "x": position.get("x", 0),
            "y": position.get("y", 0),
            "width": size.get("width", 0),
            "height": size.get("height", 0),
        }
    return payload


def _find_tree_node(root: Mapping[str, Any], ax_path: str) -> Mapping[str, Any]:
    if root.get("path") == ax_path:
        return root
    for child in root.get("children", []):
        if isinstance(child, Mapping):
            try:
                return _find_tree_node(child, ax_path)
            except KeyError:
                pass
    raise KeyError(ax_path)


def _tree_children_query_response(
    root: Mapping[str, Any],
    ax_path: str,
    *,
    include_raw: bool = False,
) -> dict[str, Any]:
    target = _find_tree_node(root, ax_path)
    nodes = [
        _query_node_from_tree(child)
        for child in target.get("children", [])
        if isinstance(child, Mapping)
    ]
    return _accessibility_query_response(nodes, include_raw=include_raw)


def _accessibility_query_response(
    nodes: list[dict[str, Any]],
    *,
    available: bool = True,
    truncated: bool = False,
    truncation_reason: str | None = None,
    include_raw: bool = False,
    snapshot_id: str = "frontmost:WeChat:微信 (聊天)",
    window_title: str = "微信 (聊天)",
    include_window_frame: bool = True,
    app_bundle_id: str = "com.tencent.xinWeChat",
) -> dict[str, Any]:
    window: dict[str, Any] = {
        "title": window_title,
        "role": "AXWindow",
    }
    if include_window_frame:
        window["frame"] = {
            "x": 0,
            "y": 0,
            "width": 1_440,
            "height": 900,
        }
    payload: dict[str, Any] = {
        "schema": "macos.accessibility.query.v1",
        "available": available,
        "snapshotId": snapshot_id,
        "app": {
            "name": "WeChat",
            "bundleId": app_bundle_id,
            "pid": 123,
        },
        "window": window,
        "root": {"kind": "focusedWindow", "axPath": "0"},
        "nodes": nodes,
        "diagnostics": {
            "returnedNodes": len(nodes),
            "truncated": truncated,
        },
    }
    if truncation_reason is not None:
        payload["diagnostics"]["truncationReason"] = truncation_reason
    if include_raw:
        payload["raw"] = {"nodeCount": len(nodes)}
    return {"observation": {"accessibilityQuery": payload}}


def _accessibility_action_response(
    *,
    ax_path: str = "0/2",
    role: str = "AXRadioButton",
    label: str = "通讯录",
) -> dict[str, Any]:
    payload = {
        "schema": "macos.accessibility.action.result.v1",
        "available": True,
        "status": "ok",
        "operation": "accessibility_action",
        "method": "AXUIElementPerformAction",
        "snapshotId": "frontmost:WeChat:微信 (聊天)",
        "action": "AXPress",
        "actionAttempted": True,
        "target": {
            "axPath": ax_path,
            "role": role,
            "label": label,
            "actions": ["AXPress"],
        },
        "diagnostics": {
            "durationMs": 10,
            "verifiedPreconditions": True,
        },
    }
    return {
        "observation": {
            "accessibilityAction": payload,
            "actionAttempted": True,
        }
    }


def _mapped_navigation_frame_response(
    *,
    ax_path: str = "0/2",
    label: str = "通讯录",
    x: float = 10,
    y: float = 20,
    width: float = 40,
    height: float = 30,
    actionable: bool = True,
    selected: bool = False,
    enabled: bool = True,
    include_window_frame: bool = True,
    app_bundle_id: str = "com.tencent.xinWeChat",
) -> dict[str, Any]:
    return _accessibility_query_response(
        [
            _normalized_node(
                ax_path,
                "AXRadioButton",
                description=label,
                x=x,
                y=y,
                width=width,
                height=height,
                value=1 if selected else 0,
                actions=["AXPress"] if actionable else None,
                enabled=enabled,
            )
        ],
        include_window_frame=include_window_frame,
        app_bundle_id=app_bundle_id,
    )


def _coordinate_click_disabled_response() -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_click",
        tool="macos.computer_use",
        operation="click",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="coordinate_click_disabled",
            message="Raw coordinate click is disabled by default.",
            retryable=False,
        ),
        summary="Raw coordinate click is disabled by default.",
        observation={
            "metadata": {
                "coordinateClick": True,
                "x": 30,
                "y": 35,
            }
        },
    )


def _coordinate_click_response() -> dict[str, Any]:
    return {"observation": {"metadata": {"coordinateClick": True}}}


def _failed_click_response() -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_click",
        tool="macos.computer_use",
        operation="click",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="click_failed",
            message="Click outcome is unknown.",
            retryable=False,
        ),
        summary="Click outcome is unknown.",
        observation={"actionAttempted": True},
    )


def _unsupported_accessibility_action_response() -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="unsupported_operation",
            message="accessibility_action is not supported by this backend",
            retryable=False,
        ),
    )


def _precondition_failed_accessibility_action_response() -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="precondition_failed",
            message="label did not match preconditions.labelIn",
            retryable=True,
        ),
        summary="label did not match preconditions.labelIn",
        observation={
            "accessibilityAction": {
                "failureKind": "precondition_failed",
                "message": "label did not match preconditions.labelIn",
            }
        },
    )


def _definite_unsupported_action_proof(
    *,
    action: str = "AXPress",
) -> dict[str, Any]:
    return {
        "failureKind": "accessibility_action_unsupported",
        "action": action,
        "actionAttempted": True,
        "actionEffect": "none",
        "nativeErrorCode": -25205 if action == "AXSetFocus" else -25206,
        "requestDispatched": True,
    }


def _unsupported_action_response_at_proof_location(
    location: str,
    *,
    proof_updates: Mapping[str, Any] | None = None,
    include_direct_proof: bool = False,
    malformed: bool = False,
) -> ToolObservation:
    proof = _definite_unsupported_action_proof()
    proof.update(proof_updates or {})
    proof_container: Any = [] if malformed else proof
    observation: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    result_evidence: dict[str, Any] = {}
    error_evidence: dict[str, Any] = {}
    if include_direct_proof:
        observation["accessibilityAction"] = _definite_unsupported_action_proof()

    if location == "observation_action":
        observation["accessibilityAction"] = proof_container
    elif location == "observation_diagnostics":
        observation["diagnostics"] = proof_container
    elif location == "observation_transport":
        observation["diagnostics"] = {"transport": proof_container}
    elif location == "metadata_transport":
        metadata["accessibilityActionTransport"] = proof_container
    elif location == "result_evidence":
        result_evidence["accessibilityAction"] = proof_container
    elif location == "error_evidence":
        error_evidence["accessibilityAction"] = proof_container
    else:
        raise ValueError(f"unknown proof location: {location}")

    error = ToolError(
        failure_kind="accessibility_action_unsupported",
        message="native action is unsupported",
        retryable=False,
        evidence=error_evidence,
    )
    return ToolObservation(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        success=False,
        summary=error.message,
        observation=observation,
        evidence=result_evidence,
        failure_kind=error.failure_kind,
        message=error.message,
        retryable=error.retryable,
        error=error,
        metadata=metadata,
    )


def _contradictory_unsupported_accessibility_action_response() -> ToolObservation:
    return _mutated_unsupported_accessibility_action_response(
        nested_updates={"actionEffect": "unknown"},
    )


def _mutated_unsupported_accessibility_action_response(
    *,
    action: str = "AXPress",
    top_updates: Mapping[str, Any] | None = None,
    metadata_updates: Mapping[str, Any] | None = None,
    nested_updates: Mapping[str, Any] | None = None,
    remove_top: tuple[str, ...] = (),
    remove_metadata: tuple[str, ...] = (),
    remove_nested: tuple[str, ...] = (),
) -> ToolObservation:
    result = _definite_unsupported_accessibility_action_response(action=action)
    observation = dict(result.observation)
    metadata = dict(observation["metadata"])
    nested = dict(observation["accessibilityAction"])

    observation.update(top_updates or {})
    metadata.update(metadata_updates or {})
    nested.update(nested_updates or {})
    for key in remove_top:
        observation.pop(key, None)
    for key in remove_metadata:
        metadata.pop(key, None)
    for key in remove_nested:
        nested.pop(key, None)

    observation["metadata"] = metadata
    observation["accessibilityAction"] = nested
    return ToolObservation.failure(
        command_id=result.command_id,
        tool=result.tool,
        operation=result.operation,
        status=result.status,
        error=result.error,
        summary=result.summary,
        observation=observation,
    )


def _legacy_unsupported_action_response(
    *,
    observation: Mapping[str, Any] | None = None,
    result_evidence: Mapping[str, Any] | None = None,
    error_evidence: Mapping[str, Any] | None = None,
) -> ToolObservation:
    error = ToolError(
        failure_kind="unsupported_operation",
        message="accessibility_action is not supported by this backend",
        retryable=False,
        evidence=dict(error_evidence or {}),
    )
    return ToolObservation(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        success=False,
        summary=error.message,
        observation=dict(observation or {}),
        evidence=dict(result_evidence or {}),
        failure_kind=error.failure_kind,
        message=error.message,
        retryable=error.retryable,
        error=error,
    )


def _failed_accessibility_query_response(
    failure_kind: str,
    message: str,
    *,
    retryable: bool,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_query",
        tool="macos.computer_use",
        operation="accessibility_query",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind=failure_kind,
            message=message,
            retryable=retryable,
        ),
        summary=message,
    )


def _normalized_node(
    ax_path: str,
    role: str,
    *,
    label: str | None = None,
    description: str | None = None,
    title: str | None = None,
    value: object | None = None,
    actions: list[str] | None = None,
    x: float = 100,
    y: float = 100,
    width: float = 100,
    height: float = 24,
    enabled: bool | None = None,
    focused: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "axPath": ax_path,
        "role": role,
        "frame": {"x": x, "y": y, "width": width, "height": height},
        "childrenCount": 0,
    }
    if label is not None:
        payload["description"] = label
    if description is not None:
        payload["description"] = description
    if title is not None:
        payload["title"] = title
    if value is not None:
        payload["value"] = value
    if actions:
        payload["actions"] = actions
    if enabled is not None:
        payload["enabled"] = enabled
    if focused is not None:
        payload["focused"] = focused
    return payload


def _normalized_row(
    ax_path: str,
    label: str,
    *,
    y: float = 120,
) -> dict[str, Any]:
    return _normalized_node(
        ax_path,
        "AXRow",
        description=label,
        actions=["AXPress"],
        x=330,
        y=y,
        width=270,
        height=64,
    )


def _visible_open_contact_responses(
    contact: str,
    *,
    app_bundle_id: str = "com.tencent.xinWeChat",
) -> list[dict[str, Any]]:
    row_label = f"{contact},hello,09:00"
    return [
        {},
        _accessibility_query_response(
            [_normalized_row("0/12/1/0/0", row_label)],
            app_bundle_id=app_bundle_id,
        ),
        _accessibility_action_response(
            ax_path="0/12/1/0/0",
            role="AXRow",
            label=row_label,
        ),
        _accessibility_query_response(
            [
                _normalized_node(
                    "0/12/4/2",
                    "AXStaticText",
                    value=contact,
                )
            ],
            app_bundle_id=app_bundle_id,
        ),
    ]


def _top_level_query_response(
    *,
    chats_selected: bool = True,
    contacts_selected: bool = False,
) -> dict[str, Any]:
    return _accessibility_query_response(
        [
            _normalized_node(
                "0/1",
                "AXRadioButton",
                description="聊天",
                value=1 if chats_selected else 0,
                actions=["AXPress"],
                x=268,
                y=159,
                width=62,
                height=34,
            ),
            _normalized_node(
                "0/2",
                "AXRadioButton",
                description="通讯录",
                value=1 if contacts_selected else 0,
                actions=["AXPress"],
                x=268,
                y=207,
                width=62,
                height=34,
            ),
            _normalized_node(
                "0/3",
                "AXRadioButton",
                description="收藏",
                value=0,
                actions=["AXPress"],
                x=268,
                y=255,
                width=62,
                height=34,
            ),
            _normalized_node(
                "0/11",
                "AXSplitGroup",
                label="main-content",
                x=329,
                y=32,
                width=1247,
                height=965,
            ),
        ]
    )


def _main_children_query_response() -> dict[str, Any]:
    return _accessibility_query_response(
        [
            _normalized_node(
                "0/11/0",
                "AXTextArea",
                description="搜索",
                x=345,
                y=50,
                width=205,
                height=26,
            ),
            _normalized_node(
                "0/11/1",
                "AXScrollArea",
                actions=["AXScrollDownByPage"],
                x=329,
                y=92,
                width=271,
                height=905,
            ),
            _normalized_node(
                "0/11/4",
                "AXSplitGroup",
                label="chat-panel",
                x=599,
                y=32,
                width=977,
                height=965,
            ),
        ]
    )


def _load_wechat_smoke_module() -> Any:
    example_path = (
        Path(__file__).parents[1]
        / "src"
        / "wechat_desktop_tool"
        / "examples"
        / "wechat_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("wechat_smoke_example", example_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_wechat_window_inspect_module() -> Any:
    example_path = (
        Path(__file__).parents[1]
        / "src"
        / "wechat_desktop_tool"
        / "examples"
        / "wechat_window_inspect.py"
    )
    spec = importlib.util.spec_from_file_location(
        "wechat_window_inspect_example",
        example_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_observation_timing(observation: ToolObservation) -> None:
    started_at = observation.timing["startedAt"]
    duration_ms = observation.timing["durationMs"]
    if not isinstance(started_at, str) or not started_at.endswith("Z"):
        raise AssertionError("timing.startedAt must be a UTC timestamp")
    if not isinstance(duration_ms, int) or duration_ms < 0:
        raise AssertionError("timing.durationMs must be a non-negative integer")


def _pythonpath(*parts: str) -> str:
    root = Path(__file__).resolve().parents[3]
    values = [str(root / part) for part in parts]
    current = os.environ.get("PYTHONPATH")
    if current:
        values.append(current)
    return os.pathsep.join(values)


__all__ = (
    "Any",
    "AppControlConfig",
    "FakeAppControl",
    "LocalServiceAppControl",
    "LoggingConfig",
    "LoggingToolObserver",
    "Path",
    "RecordingObserver",
    "SimpleNamespace",
    "StringIO",
    "ToolCommand",
    "ToolError",
    "ToolEventType",
    "ToolObservation",
    "ToolStatus",
    "WECHAT_TOOL",
    "WECHAT_WINDOW_SCHEMA",
    "WeChatDesktopConfig",
    "WeChatDesktopTool",
    "WeChatWindow",
    "_accessibility_action_failure_with_observation",
    "_accessibility_action_response",
    "_accessibility_query_response",
    "_app_control_for_args",
    "_assert_observation_timing",
    "_click_node_phase_for_test",
    "_contradictory_predispatch_action_response",
    "_contradictory_unsupported_accessibility_action_response",
    "_coordinate_click_disabled_response",
    "_coordinate_click_response",
    "_cross_package_action_fixture",
    "_cross_package_click_node",
    "_cross_package_focus_search",
    "_definite_unsupported_accessibility_action_response",
    "_failed_accessibility_action_response",
    "_failed_accessibility_query_response",
    "_failed_click_response",
    "_focus_search_box_for_test",
    "_legacy_unsupported_action_response",
    "_load_wechat_smoke_module",
    "_load_wechat_window_inspect_module",
    "_main_children_query_response",
    "_mapped_navigation_frame_response",
    "_mutated_unsupported_accessibility_action_response",
    "_normalized_node",
    "_normalized_row",
    "_open_visible_contact_for_test",
    "_open_visible_contact_with_control_map_for_test",
    "_precondition_failed_accessibility_action_response",
    "_predispatch_accessibility_action_response",
    "_production_action_fixture",
    "_pythonpath",
    "_top_level_query_response",
    "_tree_children_query_response",
    "_unsupported_accessibility_action_response",
    "_unsupported_action_response_at_proof_location",
    "_visible_open_contact_responses",
    "_wechat_window_tree_fixture",
    "_write_fake_accessibility_modules",
    "action_safety_module",
    "argparse",
    "build_wechat_tool",
    "build_wechat_window_model",
    "cli_main",
    "cli_module",
    "contact_search_module",
    "datetime",
    "draft_message_command",
    "execute_action_command",
    "focus_contact_command",
    "inspect_window_command",
    "json",
    "list_contacts_command",
    "list_conversations_command",
    "observe_current_chat_command",
    "open_contact_command",
    "open_wechat_command",
    "os",
    "patch",
    "query_mapping_module",
    "read_contact_messages_command",
    "read_visible_messages_command",
    "redirect_stderr",
    "redirect_stdout",
    "resources",
    "send_message",
    "send_message_command",
    "submit_draft_command",
    "subprocess",
    "sys",
    "tempfile",
    "timedelta",
    "timezone",
    "validate_protocol_payload",
    "wechat_command",
    "wechat_message_hash",
)
