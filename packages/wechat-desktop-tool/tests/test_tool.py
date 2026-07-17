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
import unittest
from unittest.mock import patch

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
import wechat_desktop_tool.cli as cli_module
import wechat_desktop_tool.tool as tool_module
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
    return (
        r'''
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
'''
        .replace("__MODE__", repr(mode))
        .replace("__LOG_PATH__", repr(str(log_path)))
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
                "allowed_app_bundle_ids": {
                    "WeChat": "com.tencent.xinWeChat"
                },
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
                "allowed_app_bundle_ids": {
                    "WeChat": "com.tencent.xinWeChat"
                },
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
        '''
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
'''.lstrip(),
        encoding="utf-8",
    )
    (directory / "ApplicationServices.py").write_text(
        '''
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
'''.lstrip(),
        encoding="utf-8",
    )


def _cross_package_click_node(
    tool: WeChatDesktopTool,
    *,
    ax_path: str = "0/11/1/0/0",
) -> ToolObservation:
    return tool._click_node_phase(
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
    return tool._focus_search_box_phase(
        wechat_command("open_contact", {"contact": "File Transfer"}),
        contact="File Transfer",
        search_box=argparse.Namespace(elements=[search_element]),
        evidence={},
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
    target_app = str(command.input.get("targetApp") or command.input.get("app") or "WeChat")
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


def _failed_accessibility_action_response() -> ToolObservation:
    transport = {
        "mode": "worker",
        "fallback": False,
        "requestDispatched": True,
    }
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="accessibility_action_failed",
            message="AXUIElementPerformAction returned error: -25204",
            retryable=False,
        ),
        summary="AXUIElementPerformAction returned error: -25204",
        observation={
            "actionAttempted": True,
            "actionEffect": "unknown",
            "nativeErrorCode": -25204,
            "metadata": {
                "action_attempted": True,
                "action_effect": "unknown",
                "native_error_code": -25204,
                "accessibility_action_transport": transport,
            },
            "accessibilityAction": {
                "failureKind": "accessibility_action_failed",
                "message": "AXUIElementPerformAction returned error: -25204",
                "actionAttempted": True,
                "actionEffect": "unknown",
                "nativeErrorCode": -25204,
                "diagnostics": {"transport": transport},
            }
        },
    )


def _definite_unsupported_accessibility_action_response(
    *,
    action: str = "AXPress",
) -> ToolObservation:
    native_error_code = -25205 if action == "AXSetFocus" else -25206
    method = (
        "AXUIElementSetAttributeValue"
        if action == "AXSetFocus"
        else "AXUIElementPerformAction"
    )
    transport = {
        "mode": "worker",
        "fallback": False,
        "requestDispatched": True,
    }
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind="accessibility_action_unsupported",
            message=f"{method} returned unsupported error: {native_error_code}",
            retryable=False,
        ),
        summary=f"{method} returned unsupported error: {native_error_code}",
        observation={
            "actionAttempted": True,
            "actionEffect": "none",
            "nativeErrorCode": native_error_code,
            "metadata": {
                "action_attempted": True,
                "action_effect": "none",
                "native_error_code": native_error_code,
                "accessibility_action_transport": transport,
            },
            "accessibilityAction": {
                "failureKind": "accessibility_action_unsupported",
                "message": (
                    f"{method} returned unsupported error: {native_error_code}"
                ),
                "action": action,
                "actionAttempted": True,
                "actionEffect": "none",
                "nativeErrorCode": native_error_code,
                "diagnostics": {"transport": transport},
            },
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


def _predispatch_accessibility_action_response() -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=ToolStatus.TIMEOUT,
        error=ToolError(
            failure_kind="accessibility_action_timeout",
            message="Timed out before dispatch.",
            retryable=True,
        ),
        summary="Timed out before dispatch.",
        observation={
            "metadata": {
                "accessibility_action_transport": {
                    "mode": "worker",
                    "fallback": False,
                    "requestDispatched": False,
                }
            }
        },
    )


def _accessibility_action_failure_with_observation(
    observation: dict[str, Any],
    *,
    failure_kind: str = "unsupported_operation",
    retryable: bool = False,
    status: ToolStatus = ToolStatus.FAILED,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id="cmd_accessibility_action",
        tool="macos.computer_use",
        operation="accessibility_action",
        status=status,
        error=ToolError(
            failure_kind=failure_kind,
            message=failure_kind,
            retryable=retryable,
        ),
        summary=failure_kind,
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


def _contradictory_predispatch_action_response() -> ToolObservation:
    return _accessibility_action_failure_with_observation(
        {
            "actionAttempted": False,
            "actionEffect": "performed",
            "nativeErrorCode": -25204,
            "metadata": {
                "accessibility_action_transport": {
                    "requestDispatched": False,
                }
            },
        },
        failure_kind="accessibility_action_timeout",
        retryable=True,
        status=ToolStatus.TIMEOUT,
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


class WeChatDesktopToolTests(unittest.TestCase):
    def test_command_builders_create_protocol_envelopes(self) -> None:
        commands = [
            open_wechat_command(command_id="cmd_open"),
            focus_contact_command("Ada", command_id="cmd_focus"),
            observe_current_chat_command(command_id="cmd_observe"),
            read_visible_messages_command(limit=5, command_id="cmd_read"),
            draft_message_command("hello", command_id="cmd_draft"),
            submit_draft_command(command_id="cmd_submit"),
            send_message_command(
                contact="Ada",
                message="hello",
                verify_after_submit=True,
                command_id="cmd_send",
            ),
            wechat_command(
                "draft_message",
                {"message": "custom"},
                command_id="cmd_custom",
                timeout_ms=1234,
                metadata={"caller": "unit-test"},
            ),
            inspect_window_command(command_id="cmd_inspect"),
            list_contacts_command(limit=10, command_id="cmd_contacts"),
            list_conversations_command(limit=11, command_id="cmd_conversations"),
            open_contact_command("Ada", command_id="cmd_open_contact"),
            execute_action_command(
                {
                    "schema": "wechat.action_ref.v1",
                    "id": "nav.contacts.press",
                    "target": {"axPath": "0/2"},
                    "action": "AXPress",
                },
                command_id="cmd_execute_action",
            ),
            read_contact_messages_command(
                "Ada",
                limit=12,
                command_id="cmd_contact_messages",
            ),
        ]

        for command in commands:
            with self.subTest(operation=command.operation):
                self.assertEqual(command.tool, WECHAT_TOOL)
                validate_protocol_payload("command", command.to_dict())
        self.assertEqual(commands[1].input["contact"], "Ada")
        self.assertEqual(commands[3].input["limit"], 5)
        self.assertEqual(commands[6].input["verifyAfterSubmit"], True)
        self.assertEqual(commands[7].timeout_ms, 1234)
        self.assertEqual(commands[8].operation, "inspect_window")
        self.assertEqual(commands[8].input["includeRaw"], False)
        self.assertEqual(commands[8].input["includeActionables"], True)
        self.assertEqual(commands[9].operation, "list_contacts")
        self.assertEqual(commands[9].input["limit"], 10)
        self.assertEqual(commands[10].operation, "list_conversations")
        self.assertEqual(commands[10].input["limit"], 11)
        self.assertEqual(commands[11].operation, "open_contact")
        self.assertEqual(commands[11].input["contact"], "Ada")
        self.assertEqual(commands[12].operation, "execute_action")
        self.assertEqual(commands[12].input["actionRef"]["id"], "nav.contacts.press")
        self.assertEqual(commands[13].operation, "read_contact_messages")
        self.assertEqual(commands[13].input["limit"], 12)

    def test_command_builder_output_runs_through_tool(self) -> None:
        tool = WeChatDesktopTool(FakeAppControl())

        result = tool.run_command(draft_message_command("hello"))

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "draft_message")

    def test_developer_entrypoint_modules_are_available(self) -> None:
        from wechat_desktop_tool import WeChatVisibleMessage
        from wechat_desktop_tool import adapter, observations, recipes
        from wechat_desktop_tool.models import WeChatWindow as ModelWeChatWindow

        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada") + [{}, {}]
        )
        tool = build_wechat_tool(app_control)

        self.assertIsInstance(tool, WeChatDesktopTool)
        self.assertIs(WeChatWindow, ModelWeChatWindow)
        self.assertIs(adapter.build_wechat_tool, build_wechat_tool)
        self.assertIs(observations.WeChatVisibleMessage, WeChatVisibleMessage)
        self.assertIs(observations.ToolObservation, ToolObservation)
        self.assertIs(recipes.send_message, send_message)
        result = send_message(
            tool,
            contact="Ada",
            message="hello",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "send_message")

    def test_open_wechat_sends_open_app(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {"observation": {"frontmostApp": "WeChat", "windowTitle": "WeChat"}},
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertTrue(result.success)
        self.assertEqual(result.tool, WECHAT_TOOL)
        self.assertEqual(app_control.commands[0].operation, "open_app")
        self.assertEqual(app_control.commands[0].input["app"], "WeChat")
        self.assertEqual(
            app_control.commands[0].input["bundleId"],
            "com.tencent.xinWeChat",
        )
        self.assertEqual(app_control.commands[1].operation, "observe")
        self.assertEqual(app_control.commands[1].input["targetApp"], "WeChat")
        self.assertEqual(
            app_control.commands[1].input["bundleId"],
            "com.tencent.xinWeChat",
        )
        self.assertEqual(result.observation["windowReady"], True)
        self.assertEqual(result.observation["bundleId"], "com.tencent.xinWeChat")
        self.assertEqual(result.observation["frontmostApp"], "WeChat")
        self.assertEqual(result.observation["windowTitle"], "WeChat")
        _assert_observation_timing(result)

    def test_open_wechat_fails_when_focus_retry_has_no_window_title(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertIn("no focused window", result.message)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "focus_app", "observe", "accessibility_query"],
        )

    def test_open_wechat_uses_accessibility_window_when_observe_title_is_empty(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                _accessibility_query_response([], window_title="微信 (通讯录)"),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertTrue(result.success)
        self.assertEqual(result.observation["windowTitle"], "微信 (通讯录)")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "focus_app", "observe", "accessibility_query"],
        )

    def test_inspect_window_observes_accessibility_without_raw_by_default(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _top_level_query_response(),
                _main_children_query_response(),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window()

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "inspect_window")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["root"]["kind"], "focusedWindow")
        self.assertEqual(app_control.commands[2].input["query"]["scope"], "children")
        self.assertEqual(app_control.commands[2].input["query"]["timeBudgetMs"], 10_000)
        self.assertIn("AXDescription", app_control.commands[2].input["query"]["attributes"])
        self.assertEqual(app_control.commands[3].input["root"]["kind"], "axPath")
        self.assertEqual(app_control.commands[3].input["root"]["axPath"], "0/11")
        self.assertEqual(result.observation["schema"], WECHAT_WINDOW_SCHEMA)
        self.assertEqual(result.observation["includeRaw"], False)
        self.assertNotIn("rawObservation", result.observation)
        self.assertNotIn("rawQueries", result.observation)
        window = result.observation["window"]
        self.assertEqual(window["appName"], "WeChat")
        self.assertEqual(
            window["bundleId"],
            "com.tencent.xinWeChat",
        )
        self.assertEqual(window["title"], "微信 (聊天)")
        self.assertEqual(
            window["snapshotId"],
            "frontmost:WeChat:微信 (聊天)",
        )
        self.assertEqual(window["element"]["axPath"], "0")
        self.assertEqual(window["element"]["role"], "AXWindow")
        self.assertEqual(window["activeSection"], "chats")
        self.assertEqual(
            [item["label"] for item in window["navigation"]],
            ["chats", "contacts", "favorites"],
        )
        self.assertEqual(window["navigation"][1]["id"], "nav.contacts")
        self.assertEqual(window["navigation"][1]["element"]["axPath"], "0/2")
        self.assertNotIn("attributeNames", window["element"])
        self.assertNotIn("attributeNames", window["navigation"][1]["element"])
        self.assertEqual(
            window["regions"]["searchBox"]["element"]["axPath"],
            "0/11/0",
        )
        self.assertEqual(
            window["regions"]["mainContent"]["element"]["axPath"],
            "0/11",
        )
        actionable_ids = {item["id"] for item in window["actionables"]}
        self.assertIn("nav.contacts.press", actionable_ids)
        self.assertIn("search.focus", actionable_ids)
        nav_contacts = next(
            item for item in window["actionables"] if item["id"] == "nav.contacts.press"
        )
        self.assertEqual(nav_contacts["actionRef"]["action"], "AXPress")
        self.assertIn("createdAt", nav_contacts["actionRef"])
        self.assertIn("expiresAt", nav_contacts["actionRef"])
        self.assertEqual(
            nav_contacts["actionRef"]["target"]["axPath"],
            "0/2",
        )
        available_actions = {item["id"]: item for item in window["availableActions"]}
        self.assertEqual(
            available_actions["wechat.open_contact"]["status"],
            "needs_input",
        )
        self.assertEqual(
            available_actions["wechat.list_contacts"]["operation"],
            "list_contacts",
        )
        self.assertEqual(result.observation["normalization"]["status"], "normalized")
        self.assertGreater(
            result.observation["normalization"]["availableActionCount"],
            0,
        )
        self.assertEqual(
            result.evidence["inspect_window"]["observation"]["accessibilityQuery"][
                "available"
            ],
            True,
        )

    def test_inspect_window_stops_when_wechat_has_no_focused_window(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "focus_app", "observe", "accessibility_query"],
        )

    def test_inspect_window_can_include_raw_observation(self) -> None:
        tree = _wechat_window_tree_fixture()
        app_control = FakeAppControl(
            [
                {},
                _tree_children_query_response(tree, "0", include_raw=True),
                _tree_children_query_response(tree, "0/11", include_raw=True),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window(include_raw=True)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["includeRaw"], True)
        self.assertIn("rawQueries", result.observation)
        self.assertEqual(
            result.observation["rawQueries"]["topLevel"]["raw"],
            {"nodeCount": 4},
        )
        self.assertNotIn(
            "raw",
            result.evidence["inspect_window"]["observation"][
                "accessibilityQuery"
            ],
        )

    def test_raw_tree_window_model_uses_action_refs_for_ui_actions(self) -> None:
        tree = _wechat_window_tree_fixture()
        observation = ToolObservation.ok(
            command_id="cmd_observe",
            tool="macos.computer_use",
            operation="observe",
            summary="Frontmost app: WeChat. Window: 微信 (聊天).",
            observation={
                "frontmostApp": "WeChat",
                "frontmostBundleId": "com.tencent.xinWeChat",
                "windowTitle": "微信 (聊天)",
                "snapshotId": "frontmost:WeChat:微信 (聊天)",
                "accessibility": {"focusedWindow": tree},
            },
        )

        window, normalization = build_wechat_window_model(
            WeChatDesktopConfig(),
            observation,
        )

        self.assertEqual(normalization["status"], "normalized")
        available_actions = {
            item["id"]: item for item in window.to_dict()["availableActions"]
        }
        nav_action = available_actions["ui.nav.contacts.press"]
        self.assertEqual(nav_action["operation"], "execute_action")
        self.assertEqual(nav_action["inputTemplate"]["actionRef"]["action"], "AXPress")
        self.assertIn("createdAt", nav_action["inputTemplate"]["actionRef"])
        self.assertIn("expiresAt", nav_action["inputTemplate"]["actionRef"])
        self.assertEqual(
            nav_action["inputTemplate"]["actionRef"]["target"]["axPath"],
            "0/2",
        )
        self.assertNotIn("coordinates", nav_action["inputTemplate"])

        row_action = available_actions["ui.conversation.0.open"]
        self.assertEqual(row_action["operation"], "execute_action")
        self.assertEqual(
            row_action["actionRef"]["kind"],
            "conversation.open",
        )
        self.assertNotIn("coordinates", row_action["inputTemplate"])

    def test_inspect_window_reports_action_guidance_when_tree_is_missing(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([], available=False),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window()

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["normalization"]["reason"],
            "accessibility_query_missing",
        )
        window = result.observation["window"]
        self.assertEqual(window["actionables"], [])
        available_actions = {item["id"]: item for item in window["availableActions"]}
        self.assertEqual(
            available_actions["diagnostic.accessibility_query_missing"]["status"],
            "blocked",
        )
        self.assertIn(
            "Accessibility",
            available_actions["diagnostic.accessibility_query_missing"][
                "recoveryHint"
            ],
        )
        self.assertEqual(
            available_actions["wechat.inspect_window.refresh"]["operation"],
            "inspect_window",
        )
        self.assertEqual(
            result.evidence["inspect_window"]["observation"]["accessibilityQuery"][
                "available"
            ],
            False,
        )

    def test_list_contacts_uses_packaged_control_map_fast_path(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _accessibility_action_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                            x=295,
                            y=132,
                        ),
                        _normalized_node(
                            "0/12/2/0/1/0/1",
                            "AXStaticText",
                            value="Bob",
                            x=295,
                            y=202,
                        ),
                        _normalized_node(
                            "0/12/2/0/2/0/1",
                            "AXStaticText",
                            value="Charlie",
                            x=295,
                            y=272,
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "list_contacts")
        self.assertEqual(result.observation["schema"], "wechat.contacts.v1")
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada", "Bob"],
        )
        self.assertEqual(result.observation["items"][0]["kind"], "contact")
        self.assertEqual(
            result.observation["items"][0]["actionId"],
            "contacts.visible.0.open",
        )
        self.assertNotIn("actionRef", result.observation["items"][0])
        self.assertEqual(
            result.observation["items"][0]["element"]["role"],
            "AXRow",
        )
        self.assertEqual(result.observation["pagination"]["limit"], 2)
        self.assertEqual(
            result.observation["pagination"]["mode"],
            "visibleWindow",
        )
        self.assertEqual(result.observation["pagination"]["hasMore"], True)
        self.assertIsNone(result.observation["pagination"]["nextPageToken"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/2")
        self.assertTrue(app_control.commands[2].input["query"]["actions"])
        self.assertEqual(app_control.commands[3].operation, "accessibility_action")
        self.assertEqual(app_control.commands[4].input["root"]["axPath"], "0/2")
        self.assertEqual(app_control.commands[5].input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(
            app_control.commands[5].input["root"]["resolver"],
            {
                "strategy": "attributePath",
                "steps": [
                    {"attribute": "AXChildren", "index": 12},
                    {"attribute": "AXChildren", "index": 2},
                    {"attribute": "AXContents", "index": 0, "pathIndex": 0},
                ],
            },
        )
        self.assertLessEqual(
            app_control.commands[5].input["query"]["timeBudgetMs"],
            1_200,
        )
        self.assertEqual(
            app_control.commands[5].input["query"]["match"]["roleIn"],
            ["AXStaticText"],
        )
        self.assertFalse(app_control.commands[5].input["query"]["actions"])
        self.assertEqual(
            app_control.commands[5].input["query"]["attributes"],
            ["AXRole", "AXValue", "AXPosition", "AXSize", "AXFrame"],
        )
        self.assertEqual(
            app_control.commands[5].input["query"]["preferVisibleRows"],
            True,
        )
        self.assertNotIn(
            "click",
            [command.operation for command in app_control.commands],
        )
        self.assertEqual(result.observation["source"]["mode"], "control_map")

    def test_list_contacts_skips_special_and_section_rows_before_limit(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "微信 (通讯录)",
                    }
                },
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="新的朋友",
                        ),
                        _normalized_node(
                            "0/12/2/0/1/0/1",
                            "AXStaticText",
                            value="A",
                        ),
                        _normalized_node(
                            "0/12/2/0/2/0/1",
                            "AXStaticText",
                            value="联系人",
                        ),
                        _normalized_node(
                            "0/12/2/0/3/0/1",
                            "AXStaticText",
                            value="Ada",
                            x=295,
                            y=213,
                        ),
                        _normalized_node(
                            "0/12/2/0/4/0/1",
                            "AXStaticText",
                            value="已添加",
                            x=428,
                            y=281,
                        ),
                        _normalized_node(
                            "0/12/2/0/4/0/2",
                            "AXStaticText",
                            value="Bob",
                            x=295,
                            y=282,
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada", "Bob"],
        )
        self.assertEqual(result.observation["pagination"]["limit"], 2)
        self.assertEqual(app_control.commands[2].input["query"]["limit"], 60)
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(
            app_control.commands[2].input["query"]["preferVisibleRows"],
            True,
        )

    def test_list_contacts_skips_navigation_when_contacts_window_active(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "微信 (通讯录)",
                    }
                },
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["items"][0]["displayName"], "Ada")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(
            app_control.commands[2].input["query"]["preferVisibleRows"],
            True,
        )

    def test_semantic_list_limits_do_not_leak_raw_ax_content_to_observability(
        self,
    ) -> None:
        canary = "PRIVATE_CANARY_CHARLIE"
        contacts_query = _accessibility_query_response(
            [
                _normalized_node(
                    "0/12/2/0/0/0/1",
                    "AXStaticText",
                    value="Ada",
                ),
                _normalized_node(
                    "0/12/2/0/1/0/1",
                    "AXStaticText",
                    value="Bob",
                ),
                _normalized_node(
                    "0/12/2/0/2/0/1",
                    "AXStaticText",
                    value=canary,
                ),
            ]
        )
        contacts_query["summary"] = f"query observed {canary}"
        conversations_query = _accessibility_query_response(
            [
                _normalized_row("0/12/1/0/0", "Ada,first,09:00"),
                _normalized_row("0/12/1/0/1", "Bob,second,10:00", y=184),
                _normalized_row(
                    "0/12/1/0/2",
                    f"Charlie,{canary},11:00",
                    y=248,
                ),
            ]
        )
        conversations_query["summary"] = f"query observed {canary}"
        messages_query = _accessibility_query_response(
            [
                _normalized_node("0/11/4/2", "AXStaticText", value="Ada"),
                _normalized_row("0/11/4/0/0/0", "one"),
                _normalized_row("0/11/4/0/0/1", "two", y=184),
                _normalized_row("0/11/4/0/0/2", canary, y=248),
            ]
        )
        messages_query["summary"] = f"query observed {canary}"
        cases = (
            (
                "contacts",
                list_contacts_command(limit=2, command_id="cmd_contacts_privacy"),
                [
                    {},
                    {
                        "observation": {
                            "frontmostApp": "WeChat",
                            "frontmostBundleId": "com.tencent.xinWeChat",
                            "windowTitle": "微信 (通讯录)",
                        }
                    },
                    contacts_query,
                ],
                lambda result: [
                    item["displayName"] for item in result.observation["items"]
                ],
                ["Ada", "Bob"],
            ),
            (
                "conversations",
                list_conversations_command(
                    limit=2,
                    command_id="cmd_conversations_privacy",
                ),
                [{}, conversations_query],
                lambda result: [
                    item["preview"] for item in result.observation["items"]
                ],
                ["first", "second"],
            ),
            (
                "messages",
                read_visible_messages_command(
                    limit=2,
                    command_id="cmd_messages_privacy",
                ),
                [{}, messages_query],
                lambda result: [
                    item["text"] for item in result.observation["messages"]
                ],
                ["one", "two"],
            ),
        )

        for label, command, responses, semantic_values, expected in cases:
            with self.subTest(label=label):
                observer = RecordingObserver()
                result = WeChatDesktopTool(FakeAppControl(responses)).run_command(
                    command,
                    observer=observer,
                )

                self.assertTrue(result.success)
                self.assertEqual(semantic_values(result), expected)
                serialized_result_evidence = json.dumps(
                    result.evidence,
                    ensure_ascii=False,
                )
                serialized_events = json.dumps(
                    [event.to_dict() for event in observer.events],
                    ensure_ascii=False,
                )
                log_stream = StringIO()
                logging_observer = LoggingToolObserver(
                    config=LoggingConfig(json=True, redact_text=True),
                    stream=log_stream,
                )
                for event in observer.events:
                    logging_observer.on_event(event)

                self.assertNotIn(canary, serialized_result_evidence)
                self.assertNotIn(canary, serialized_events)
                self.assertNotIn(canary, log_stream.getvalue())

    def test_row_without_axpress_does_not_publish_unexecutable_axpress_action_ref(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "微信 (通讯录)",
                    }
                },
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertNotIn("actionRef", result.observation["items"][0])
        self.assertNotIn(
            "AXPress",
            result.observation["items"][0]["element"].get("actions", []),
        )

    def test_list_contacts_stops_after_dispatched_action_failure(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _failed_accessibility_action_response(),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=2)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.FAILED)
        self.assertEqual(result.failure_kind, "wechat_navigation_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
            ],
        )
        self.assertEqual(app_control.commands[2].timeout_ms, 800)
        self.assertEqual(app_control.commands[3].timeout_ms, 2_000)

    def test_list_contacts_falls_back_once_for_definite_unsupported_action(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _definite_unsupported_accessibility_action_response(),
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["items"][0]["displayName"], "Ada")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "click",
                "accessibility_query",
                "accessibility_query",
            ],
        )

    def test_list_contacts_preserves_selector_permission_failure(self) -> None:
        permission_failure = _failed_accessibility_query_response(
            "missing_accessibility",
            "Accessibility permission is required",
            retryable=False,
        )
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "微信 (通讯录)",
                    }
                },
                permission_failure,
                permission_failure,
                permission_failure,
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "missing_accessibility")
        self.assertFalse(result.retryable)
        self.assertIn("Grant Accessibility permission", result.recovery_hint)
        diagnostics = result.observation["selector"]["diagnostics"]
        self.assertEqual(diagnostics["failureKind"], "selector_query_failed")
        self.assertEqual(
            diagnostics["causeFailureKind"],
            "missing_accessibility",
        )

    def test_mapped_navigation_click_uses_current_validated_frame_center(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    x=10,
                    y=20,
                    width=40,
                    height=30,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[3].operation, "click")
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 30, "y": 35},
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/2")

    def test_mapped_navigation_accepts_one_point_window_edge_rounding(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    x=-1,
                    y=20,
                    width=40,
                    height=30,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[3].operation, "click")
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 19, "y": 35},
        )

    def test_mapped_navigation_ignores_packaged_screen_coordinates(self) -> None:
        profile_text = (
            resources.files("wechat_desktop_tool")
            .joinpath("profiles/wechat-macos.toml")
            .read_text(encoding="utf-8")
        )
        profile_text = profile_text.replace(
            'labels = ["通讯录", "__EN_CONTACTS_PLACEHOLDER__"]',
            (
                'labels = ["通讯录", "__EN_CONTACTS_PLACEHOLDER__"]\n'
                "screen_coordinates = [{ x = 999, y = 999 }]"
            ),
            1,
        )
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    x=10,
                    y=20,
                    width=40,
                    height=30,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "wechat-with-legacy-coordinate.toml"
            profile_path.write_text(profile_text, encoding="utf-8")
            tool = WeChatDesktopTool(
                app_control,
                WeChatDesktopConfig(selector_profile_path=str(profile_path)),
            )

            result = tool.list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[3].operation, "click")
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 30, "y": 35},
        )
        self.assertNotEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 999, "y": 999},
        )

    def test_mapped_navigation_missing_or_stale_frame_fails_closed(self) -> None:
        unsafe_targets = {
            "missing_window_frame": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                include_window_frame=False,
            ),
            "outside_window": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                x=2_000,
                y=20,
            ),
            "outside_window_edge_tolerance": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                x=-1.1,
                y=20,
            ),
            "empty_target_frame": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                width=0,
            ),
            "disabled_target": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                enabled=False,
            ),
            "wrong_app": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                app_bundle_id="com.example.NotWeChat",
            ),
        }
        for name, target_response in unsafe_targets.items():
            with self.subTest(name=name):
                app_control = FakeAppControl([{}, target_response])

                result = WeChatDesktopTool(app_control).list_contacts(limit=1)

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "wechat_navigation_failed")
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["open_app", "observe", "accessibility_query"],
                )

    def test_mapped_navigation_requires_semantic_postcondition(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _accessibility_action_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=False,
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_navigation_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
            ],
        )

    def test_list_conversations_uses_packaged_control_map_fast_path(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/1/0/0",
                            "AXRow",
                            description="文件传输助手,hello,09:00,置顶",
                            x=330,
                            y=120,
                            width=270,
                            height=64,
                            actions=["AXPress"],
                        ),
                        _normalized_node(
                            "0/11/1/0/1",
                            "AXRow",
                            description="目标联系人,最近消息,10:00,消息免打扰",
                            x=330,
                            y=184,
                            width=270,
                            height=64,
                            actions=["AXPress"],
                        ),
                        _normalized_node(
                            "0/11/1/0/0/0",
                            "AXCell",
                            description="文件传输助手,hello,09:00,置顶",
                        ),
                        _normalized_node(
                            "0/11/1/0/1/0",
                            "AXCell",
                            description="目标联系人,最近消息,10:00,消息免打扰",
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_conversations(limit=30)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "list_conversations")
        self.assertEqual(result.observation["schema"], "wechat.conversations.v1")
        rows = result.observation["items"]
        self.assertEqual(rows[0]["displayName"], "文件传输助手")
        self.assertEqual(rows[0]["preview"], "hello")
        self.assertEqual(rows[0]["timestamp"], "09:00")
        self.assertEqual(rows[0]["pinned"], True)
        self.assertEqual(rows[0]["element"]["label"], "文件传输助手")
        self.assertEqual(rows[0]["actionRef"]["action"], "AXPress")
        self.assertEqual(rows[0]["actionRef"]["target"]["role"], "AXRow")
        self.assertEqual(rows[0]["actionRef"]["target"]["actions"], ["AXPress"])
        self.assertEqual(
            rows[0]["actionRef"]["preconditions"]["labelIn"],
            ["文件传输助手,hello,09:00,置顶"],
        )
        self.assertIn("createdAt", rows[0]["actionRef"])
        self.assertIn("expiresAt", rows[0]["actionRef"])
        self.assertEqual(rows[1]["displayName"], "目标联系人")
        self.assertEqual(rows[1]["muted"], True)
        self.assertEqual(rows[1]["actionRef"]["action"], "AXPress")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/1/0")
        self.assertEqual(app_control.commands[2].input["query"]["timeBudgetMs"], 2_200)
        self.assertEqual(
            app_control.commands[2].input["query"]["preferVisibleRows"],
            True,
        )
        self.assertEqual(
            app_control.commands[2].input["query"]["match"]["roleIn"],
            ["AXRow", "AXCell", "AXStaticText"],
        )
        self.assertEqual(result.observation["source"]["mode"], "control_map")

    def test_visible_window_list_does_not_publish_false_continuation_token(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/11/1/0/0",
                            "Ada,first,09:00",
                        ),
                        _normalized_row(
                            "0/11/1/0/1",
                            "Bob,second,09:01",
                            y=184,
                        ),
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_conversations(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["pagination"],
            {
                "mode": "visibleWindow",
                "limit": 1,
                "pageToken": None,
                "hasMore": True,
                "nextPageToken": None,
            },
        )
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada"],
        )

    def test_visible_window_list_rejects_unsupported_page_token(self) -> None:
        app_control = FakeAppControl()

        result = WeChatDesktopTool(app_control).list_contacts(
            limit=30,
            page_token="contacts:next:stale",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "pagination_not_supported")
        self.assertEqual(result.recovery_hint, "Retry without pageToken.")
        self.assertEqual(result.observation["pagination"]["nextPageToken"], None)
        self.assertEqual(app_control.commands, [])

    def test_list_conversations_skips_press_when_current_nav_node_is_selected(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "Window",
                    }
                },
                _mapped_navigation_frame_response(
                    ax_path="0/1",
                    label="聊天",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/12/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_conversations(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
            ],
        )
        self.assertNotIn(
            "accessibility_action",
            [command.operation for command in app_control.commands],
        )

    def test_list_conversations_tries_second_mapped_root_after_empty_first(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/11/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_conversations(limit=30)

        self.assertTrue(result.success)
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["文件传输助手"],
        )
        self.assertEqual(
            [
                command.input["root"]["axPath"]
                for command in app_control.commands
                if command.operation == "accessibility_query"
            ],
            ["0/12/1/0", "0/11/1/0"],
        )

    def test_execute_action_runs_accessibility_action_ref(self) -> None:
        app_control = FakeAppControl([_accessibility_action_response()])
        tool = WeChatDesktopTool(app_control)
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "nav.contacts.press",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": "通讯录",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": ["通讯录"],
                "actionIn": ["AXPress"],
            },
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "execute_action")
        self.assertEqual(result.observation["schema"], "wechat.execute_action.v1")
        self.assertEqual(result.observation["actionId"], "nav.contacts.press")
        self.assertEqual(app_control.commands[0].operation, "accessibility_action")
        self.assertEqual(app_control.commands[0].input["target"]["axPath"], "0/2")
        self.assertEqual(
            app_control.commands[0].input["preconditions"]["labelIn"],
            ["通讯录"],
        )

    def test_execute_action_uses_selector_fallback_when_backend_unsupported(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _unsupported_accessibility_action_response(),
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "nav.contacts.press",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": "通讯录",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": ["通讯录"],
                "actionIn": ["AXPress"],
            },
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["method"], "selector_click")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )
        self.assertEqual(
            app_control.commands[1].input["selector"],
            {"role": "radio_button", "name": "通讯录"},
        )
        self.assertIn("execute_action:selector_fallback", result.evidence)

    def test_execute_action_does_not_republish_low_level_target_content(self) -> None:
        canary = "PRIVATE_ACTION_TARGET_CANARY"
        app_control = FakeAppControl(
            [
                _accessibility_action_response(
                    ax_path="0/2",
                    role="AXRadioButton",
                    label=canary,
                )
            ]
        )
        observer = RecordingObserver()
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "privacy.action",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": canary,
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": [canary],
                "actionIn": ["AXPress"],
            },
        }

        result = WeChatDesktopTool(app_control).run_command(
            execute_action_command(
                action_ref,
                command_id="cmd_action_privacy",
            ),
            observer=observer,
        )

        self.assertTrue(result.success)
        serialized = json.dumps(
            {
                "result": result.to_dict(),
                "events": [event.to_dict() for event in observer.events],
            },
            ensure_ascii=False,
        )
        log_stream = StringIO()
        logging_observer = LoggingToolObserver(
            config=LoggingConfig(json=True, redact_text=True),
            stream=log_stream,
        )
        for event in observer.events:
            logging_observer.on_event(event)

        self.assertNotIn(canary, serialized)
        self.assertNotIn(canary, log_stream.getvalue())

    def test_execute_action_uses_one_fallback_for_definite_native_unsupported(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _definite_unsupported_accessibility_action_response(),
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "nav.contacts.press",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": "通讯录",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": ["通讯录"],
                "actionIn": ["AXPress"],
            },
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["method"], "selector_click")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )

    def test_execute_action_blocks_contradictory_unsupported_effect(self) -> None:
        app_control = FakeAppControl(
            [_contradictory_unsupported_accessibility_action_response()]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "nav.contacts.press",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": "通讯录",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": ["通讯录"],
                "actionIn": ["AXPress"],
            },
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertFalse(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_click_node_blocks_every_invalid_unsupported_action_proof(
        self,
    ) -> None:
        cases = (
            (
                "set_focus_proof_for_press_request",
                _definite_unsupported_accessibility_action_response(
                    action="AXSetFocus"
                ),
            ),
            (
                "cannot_complete_code",
                _mutated_unsupported_accessibility_action_response(
                    top_updates={"nativeErrorCode": -25204},
                    metadata_updates={"native_error_code": -25204},
                    nested_updates={"nativeErrorCode": -25204},
                ),
            ),
            (
                "wrong_action_code_pair",
                _mutated_unsupported_accessibility_action_response(
                    top_updates={"nativeErrorCode": -25205},
                    metadata_updates={"native_error_code": -25205},
                    nested_updates={"nativeErrorCode": -25205},
                ),
            ),
            (
                "missing_native_code",
                _mutated_unsupported_accessibility_action_response(
                    remove_top=("nativeErrorCode",),
                    remove_metadata=("native_error_code",),
                    remove_nested=("nativeErrorCode",),
                ),
            ),
            (
                "missing_action",
                _mutated_unsupported_accessibility_action_response(
                    remove_nested=("action",),
                ),
            ),
            (
                "missing_attempted",
                _mutated_unsupported_accessibility_action_response(
                    remove_top=("actionAttempted",),
                    remove_metadata=("action_attempted",),
                    remove_nested=("actionAttempted",),
                ),
            ),
            (
                "non_string_effect_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"actionEffect": {"value": "none"}},
                ),
            ),
            (
                "empty_effect_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"actionEffect": ""},
                ),
            ),
            (
                "contradictory_attempted_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"actionAttempted": False},
                ),
            ),
            (
                "non_integer_code_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"nativeErrorCode": "-25206"},
                ),
            ),
            (
                "contradictory_failure_kind",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={
                        "failureKind": "accessibility_action_failed",
                    },
                ),
            ),
            (
                "contradictory_action_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    top_updates={"action": "AXSetFocus"},
                ),
            ),
        )

        for label, response in cases:
            with self.subTest(label=label):
                app_control = FakeAppControl([response])
                tool = WeChatDesktopTool(app_control)

                result = tool._click_node_phase(
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_click_node_blocks_malformed_attempt_and_dispatch_evidence(
        self,
    ) -> None:
        cases = (
            (
                "truthy_attempted_string",
                _accessibility_action_failure_with_observation(
                    {"actionAttempted": "true"}
                ),
            ),
            (
                "falsey_attempted_string",
                _accessibility_action_failure_with_observation(
                    {"actionAttempted": ""}
                ),
            ),
            (
                "conflicting_attempted_aliases",
                _accessibility_action_failure_with_observation(
                    {
                        "actionAttempted": False,
                        "action_attempted": True,
                    }
                ),
            ),
            (
                "malformed_action_container",
                _accessibility_action_failure_with_observation(
                    {"accessibilityAction": []}
                ),
            ),
            (
                "malformed_metadata_container",
                _accessibility_action_failure_with_observation({"metadata": []}),
            ),
            (
                "malformed_dispatch_duplicate",
                _accessibility_action_failure_with_observation(
                    {
                        "metadata": {
                            "accessibility_action_transport": {
                                "requestDispatched": False,
                            }
                        },
                        "accessibilityAction": {
                            "diagnostics": {
                                "transport": {"request_dispatched": "true"}
                            }
                        },
                    },
                    failure_kind="accessibility_action_timeout",
                    retryable=True,
                    status=ToolStatus.TIMEOUT,
                ),
            ),
            (
                "conflicting_dispatch_duplicate",
                _accessibility_action_failure_with_observation(
                    {
                        "metadata": {
                            "accessibility_action_transport": {
                                "requestDispatched": False,
                            }
                        },
                        "accessibilityAction": {
                            "diagnostics": {
                                "transport": {"request_dispatched": True}
                            }
                        },
                    },
                    failure_kind="accessibility_action_timeout",
                    retryable=True,
                    status=ToolStatus.TIMEOUT,
                ),
            ),
        )

        for label, response in cases:
            with self.subTest(label=label):
                app_control = FakeAppControl([response])
                result = WeChatDesktopTool(app_control)._click_node_phase(
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_click_node_accepts_complete_proof_from_each_known_container(
        self,
    ) -> None:
        locations = (
            "observation_action",
            "observation_diagnostics",
            "observation_transport",
            "metadata_transport",
            "result_evidence",
            "error_evidence",
        )
        for location in locations:
            with self.subTest(location=location):
                app_control = FakeAppControl(
                    [
                        _unsupported_action_response_at_proof_location(location),
                        {},
                    ]
                )
                result = WeChatDesktopTool(app_control)._click_node_phase(
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertTrue(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action", "click"],
                )

    def test_click_node_blocks_conflicts_in_every_known_proof_container(
        self,
    ) -> None:
        locations = (
            "observation_diagnostics",
            "observation_transport",
            "metadata_transport",
            "result_evidence",
            "error_evidence",
        )
        conflicting_updates = (
            {"action": "AXSetFocus"},
            {"actionAttempted": False},
            {"actionEffect": "performed"},
            {"nativeErrorCode": -25204},
            {"requestDispatched": False},
        )
        for location in locations:
            for updates in conflicting_updates:
                with self.subTest(location=location, updates=updates):
                    app_control = FakeAppControl(
                        [
                            _unsupported_action_response_at_proof_location(
                                location,
                                proof_updates=updates,
                                include_direct_proof=True,
                            )
                        ]
                    )
                    result = WeChatDesktopTool(app_control)._click_node_phase(
                        wechat_command("open_contact", {"contact": "Ada"}),
                        _normalized_row("0/11/1/0/0", "Ada"),
                        phase="open_visible_contact",
                        evidence={},
                        snapshot_id="frontmost:WeChat:微信 (聊天)",
                    )

                    self.assertFalse(result.success)
                    self.assertEqual(
                        [command.operation for command in app_control.commands],
                        ["accessibility_action"],
                    )

    def test_click_node_blocks_malformed_known_proof_containers(self) -> None:
        locations = (
            "observation_action",
            "observation_diagnostics",
            "observation_transport",
            "metadata_transport",
            "result_evidence",
            "error_evidence",
        )
        for location in locations:
            with self.subTest(location=location):
                app_control = FakeAppControl(
                    [
                        _unsupported_action_response_at_proof_location(
                            location,
                            include_direct_proof=location != "observation_action",
                            malformed=True,
                        )
                    ]
                )
                result = WeChatDesktopTool(app_control)._click_node_phase(
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_execute_action_precondition_failure_does_not_use_selector_fallback(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _precondition_failed_accessibility_action_response(),
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "nav.contacts.press",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": "通讯录",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": ["通讯录"],
                "actionIn": ["AXPress"],
            },
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_precondition_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )
        self.assertIn("execute_action", result.error.evidence)
        self.assertNotIn("execute_action:selector_fallback", result.error.evidence)

    def test_execute_action_rejects_row_without_identity_precondition(
        self,
    ) -> None:
        app_control = FakeAppControl([_accessibility_action_response()])
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "chats.visible.0.open",
            "kind": "chats.open",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "label": "Ada,hello,09:00",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRow"],
                "actionIn": ["AXPress"],
            },
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {"role": "AXRow", "name": "Ada,hello,09:00"},
                }
            ],
        }

        result = WeChatDesktopTool(app_control).execute_action(action_ref)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_precondition_failed")
        self.assertEqual(result.observation["actionId"], "chats.visible.0.open")
        self.assertEqual(app_control.commands, [])

    def test_execute_action_accepts_row_with_matching_identity_precondition(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _accessibility_action_response(
                    ax_path="0/12/1/0/0",
                    role="AXRow",
                    label="Ada,hello,09:00",
                )
            ]
        )
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "chats.visible.0.open",
            "kind": "chats.open",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "label": "Ada,hello,09:00",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRow"],
                "labelIn": ["Ada,hello,09:00"],
                "actionIn": ["AXPress"],
            },
        }

        result = WeChatDesktopTool(app_control).execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(
            app_control.commands[0].input["preconditions"]["labelIn"],
            ["Ada,hello,09:00"],
        )

    def test_execute_action_rejects_expired_action_ref_before_backend(self) -> None:
        expired_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat().replace("+00:00", "Z")
        for expires_at in (expired_at, "not-a-date"):
            with self.subTest(expires_at=expires_at):
                app_control = FakeAppControl([_accessibility_action_response()])
                tool = WeChatDesktopTool(app_control)
                action_ref = {
                    "schema": "wechat.action_ref.v1",
                    "id": "nav.contacts.press",
                    "kind": "navigation.switch",
                    "preferredMethod": "accessibility_action",
                    "target": {
                        "axPath": "0/2",
                        "role": "AXRadioButton",
                        "label": "通讯录",
                        "actions": ["AXPress"],
                    },
                    "action": "AXPress",
                    "preconditions": {
                        "roleIn": ["AXRadioButton"],
                        "labelIn": ["通讯录"],
                        "actionIn": ["AXPress"],
                    },
                    "expiresAt": expires_at,
                    "fallbacks": [
                        {
                            "method": "selector_click",
                            "selector": {
                                "role": "radio_button",
                                "name": "通讯录",
                            },
                        }
                    ],
                }

                result = tool.execute_action(action_ref)

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "wechat_action_ref_expired")
                self.assertEqual(result.observation["schema"], "wechat.execute_action.v1")
                self.assertEqual(result.observation["actionId"], "nav.contacts.press")
                self.assertEqual(app_control.commands, [])
                self.assertIn("actionRef", result.error.evidence)

    def test_execute_action_accepts_unexpired_action_ref(self) -> None:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=60)
        ).isoformat().replace("+00:00", "Z")
        app_control = FakeAppControl([_accessibility_action_response()])
        tool = WeChatDesktopTool(app_control)
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "nav.contacts.press",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": "通讯录",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": ["通讯录"],
                "actionIn": ["AXPress"],
            },
            "expiresAt": expires_at,
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["method"], "accessibility_action")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_click_node_phase_does_not_generate_coordinate_fallback(self) -> None:
        app_control = FakeAppControl([{}])
        tool = WeChatDesktopTool(app_control)
        command = wechat_command("open_contact", {"contact": "Ada"})
        evidence: dict[str, Any] = {}

        result = tool._click_node_phase(
            command,
            {
                "axPath": "0/11/2",
                "role": "AXButton",
                "frame": {"x": 557, "y": 49, "width": 28, "height": 28},
            },
            phase="fallback_click",
            evidence=evidence,
        )

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[0].operation, "click")
        self.assertEqual(
            app_control.commands[0].input["selector"],
            {"role": "AXButton", "index": 1},
        )
        self.assertNotIn("coordinates", app_control.commands[0].input)

    def test_click_node_phase_rejects_unlabeled_row_before_coordinate(self) -> None:
        app_control = FakeAppControl()
        tool = WeChatDesktopTool(app_control)
        command = wechat_command("open_contact", {"contact": "Ada"})

        result = tool._click_node_phase(
            command,
            {
                "axPath": "0/11/1/0/0",
                "role": "AXRow",
                "frame": {"x": 330, "y": 120, "width": 270, "height": 64},
            },
            phase="open_unlabeled_row",
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_target_unverified")
        self.assertEqual(app_control.commands, [])

    def test_click_node_phase_allows_explicit_predispatch_fallback(self) -> None:
        app_control = FakeAppControl(
            [_predispatch_accessibility_action_response(), {}]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool._click_node_phase(
            wechat_command("open_contact", {"contact": "Ada"}),
            _normalized_row("0/11/1/0/0", "Ada"),
            phase="open_visible_contact",
            evidence={},
            snapshot_id="frontmost:WeChat:微信 (聊天)",
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )

    def test_legacy_and_predispatch_contradictions_never_replay(self) -> None:
        cases = (
            (
                "legacy_result_evidence_performed",
                _legacy_unsupported_action_response(
                    result_evidence={"actionEffect": "performed"},
                ),
            ),
            (
                "legacy_error_evidence_unknown",
                _legacy_unsupported_action_response(
                    error_evidence={"actionEffect": "unknown"},
                ),
            ),
            (
                "legacy_nested_cannot_complete",
                _legacy_unsupported_action_response(
                    observation={
                        "accessibilityAction": {"nativeErrorCode": -25204},
                    },
                ),
            ),
            (
                "predispatch_contradictory_effect_and_code",
                _contradictory_predispatch_action_response(),
            ),
        )
        policy_functions = (
            tool_module._should_fallback_from_accessibility_action,
            tool_module._should_try_coordinate_click_after_accessibility_action,
            tool_module._should_press_return_for_search_result,
        )

        for label, response in cases:
            for policy in policy_functions:
                with self.subTest(label=label, policy=policy.__name__):
                    self.assertFalse(policy(response, expected_action="AXPress"))

            with self.subTest(label=label, caller="click_node"):
                app_control = FakeAppControl([response, {}])
                result = WeChatDesktopTool(app_control)._click_node_phase(
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_click_node_phase_does_not_replay_failed_selector_fallback(self) -> None:
        app_control = FakeAppControl(
            [_unsupported_accessibility_action_response(), _failed_click_response()]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool._click_node_phase(
            wechat_command("open_contact", {"contact": "Ada"}),
            _normalized_row("0/11/1/0/0", "Ada"),
            phase="open_visible_contact",
            evidence={},
            snapshot_id="frontmost:WeChat:微信 (聊天)",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "click_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )

    def test_cross_package_dispatched_action_failures_do_not_mutate_again(
        self,
    ) -> None:
        for mode in (
            "eof",
            "timeout",
            "malformed",
            "native_failure",
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
            "legacy_unsupported_attempted",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                log_path = Path(temp_dir) / "requests.jsonl"
                client, worker, app_control, runner, tool = (
                    _cross_package_action_fixture(
                        mode,
                        log_path,
                        timeout_ms=200,
                    )
                )

                try:
                    worker.start()
                    client._accessibility_action_worker = worker
                    result = _cross_package_click_node(tool)
                finally:
                    worker.stop()

                requests = [
                    json.loads(line)
                    for line in log_path.read_text(encoding="utf-8").splitlines()
                ]
                self.assertFalse(result.success)
                self.assertEqual(result.retryable, False)
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["action"], "AXPress")
                dispatch = tool_module._accessibility_action_request_dispatched(
                    result
                )
                self.assertTrue(dispatch.present)
                self.assertTrue(dispatch.valid)
                self.assertIs(dispatch.value, True)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )
                self.assertEqual(runner.calls, [])

    def test_cross_package_predispatch_failure_allows_one_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "requests.jsonl"
            client, worker, app_control, runner, tool = (
                _cross_package_action_fixture(
                    "timeout",
                    log_path,
                    timeout_ms=100,
                )
            )

            try:
                worker.start()
                client._accessibility_action_worker = worker
                worker._lock.acquire()
                try:
                    result = _cross_package_click_node(tool)
                finally:
                    worker._lock.release()
            finally:
                worker.stop()

            self.assertTrue(result.success)
            self.assertFalse(log_path.exists())
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click"],
            )
            self.assertEqual(runner.calls, [])

    def test_cross_package_unsupported_action_allows_one_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "requests.jsonl"
            client, worker, app_control, runner, tool = (
                _cross_package_action_fixture(
                    "unsupported",
                    log_path,
                    timeout_ms=200,
                )
            )

            try:
                worker.start()
                client._accessibility_action_worker = worker
                result = _cross_package_click_node(tool)
            finally:
                worker.stop()

            self.assertTrue(result.success)
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click"],
            )
            self.assertEqual(runner.calls, [])

    def test_cross_package_native_unsupported_press_allows_one_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir)
            _write_fake_accessibility_modules(module_dir)
            python_path = os.pathsep.join(
                item
                for item in (str(module_dir), os.environ.get("PYTHONPATH", ""))
                if item
            )
            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": python_path,
                    "FAKE_AX_ACTION": "AXPress",
                },
            ):
                client, worker, app_control, runner, tool = (
                    _production_action_fixture(timeout_ms=500)
                )
                try:
                    worker.start()
                    client._accessibility_action_worker = worker
                    result = _cross_package_click_node(tool, ax_path="0/0")
                finally:
                    worker.stop()

            self.assertTrue(result.success)
            native_result = app_control.observations[0]
            native_payload = native_result.observation["accessibilityAction"]
            self.assertEqual(native_payload["action"], "AXPress")
            self.assertEqual(native_payload["nativeErrorCode"], -25206)
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click"],
            )
            self.assertEqual(runner.calls, [])

    def test_cross_package_native_unsupported_focus_allows_one_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir)
            _write_fake_accessibility_modules(module_dir)
            python_path = os.pathsep.join(
                item
                for item in (str(module_dir), os.environ.get("PYTHONPATH", ""))
                if item
            )
            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": python_path,
                    "FAKE_AX_ACTION": "AXSetFocus",
                },
            ):
                client, worker, app_control, runner, tool = (
                    _production_action_fixture(timeout_ms=500)
                )
                try:
                    worker.start()
                    client._accessibility_action_worker = worker
                    result = _cross_package_focus_search(tool, ax_path="0/0")
                finally:
                    worker.stop()

            self.assertTrue(result.success)
            native_result = app_control.observations[0]
            native_payload = native_result.observation["accessibilityAction"]
            self.assertEqual(native_payload["action"], "AXSetFocus")
            self.assertEqual(native_payload["nativeErrorCode"], -25205)
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click", "accessibility_query"],
            )
            self.assertEqual(runner.calls, [])

    def test_open_contact_uses_packaged_selector_profile(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _main_children_query_response(),
                {},
                {},
                {},
                {},
                _accessibility_query_response(
                    [_normalized_row("0/11/search/0", "Ada Lovelace")]
                ),
                {},
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/4/2",
                            "AXStaticText",
                            value="Ada Lovelace",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("Ada")

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "open_contact")
        self.assertEqual(result.observation["schema"], "wechat.open_contact.v1")
        self.assertEqual(result.observation["status"], "opened")
        self.assertEqual(result.observation["currentChat"]["title"], "Ada Lovelace")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "click",
                "accessibility_query",
                "hotkey",
                "type_text",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/1/0")
        self.assertEqual(app_control.commands[3].input["root"]["axPath"], "0/11/1/0")
        self.assertEqual(app_control.commands[4].input["query"]["timeBudgetMs"], 2_500)
        self.assertEqual(app_control.commands[5].input["query"]["timeBudgetMs"], 350)
        self.assertEqual(app_control.commands[6].input["query"]["timeBudgetMs"], 2_500)
        self.assertEqual(app_control.commands[7].input["query"]["timeBudgetMs"], 2_000)
        self.assertEqual(app_control.commands[11].input["text"], "Ada")
        self.assertEqual(
            app_control.commands[8].metadata["coordinateSource"],
            "accessibility_frame",
        )
        self.assertEqual(app_control.commands[9].input["root"]["axPath"], "0/11/0")
        self.assertEqual(app_control.commands[9].input["query"]["scope"], "self")
        self.assertEqual(app_control.commands[9].input["query"]["timeBudgetMs"], 500)
        self.assertIn(
            "AXFocused",
            app_control.commands[9].input["query"]["attributes"],
        )

    def test_open_contact_stops_when_search_row_action_was_dispatched(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _main_children_query_response(),
                {},
                {},
                {},
                {},
                _accessibility_query_response(
                    [_normalized_row("0/11/search/0", "Ada Lovelace")]
                ),
                _failed_accessibility_action_response(),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "contact_not_found")
        self.assertEqual(result.retryable, False)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "click",
                "accessibility_query",
                "hotkey",
                "type_text",
                "accessibility_query",
                "accessibility_action",
            ],
        )

    def test_open_contact_stops_after_dispatched_visible_row_action(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [_normalized_row("0/12/1/0/0", "File Transfer")]
                ),
                _failed_accessibility_action_response(),
            ]
        )

        result = WeChatDesktopTool(app_control).open_contact("File Transfer")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_failed")
        self.assertEqual(result.retryable, False)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query", "accessibility_action"],
        )

    def test_selector_visible_contact_stops_after_dispatched_action(self) -> None:
        app_control = FakeAppControl(
            [
                _accessibility_query_response(
                    [_normalized_row("0/11/1/0/0", "File Transfer")]
                ),
                _failed_accessibility_action_response(),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool._open_visible_contact_phase(
            wechat_command("open_contact", {"contact": "File Transfer"}),
            contact="File Transfer",
            main_content={"axPath": "0/11", "role": "AXSplitGroup"},
            evidence={},
        )

        assert result is not None
        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_query", "accessibility_action"],
        )

    def test_open_contact_uses_visible_row_action_ref_before_search(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/11/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
                _accessibility_action_response(
                    ax_path="0/11/1/0/0",
                    role="AXRow",
                    label="文件传输助手,hello,09:00,置顶",
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/4/2",
                            "AXStaticText",
                            value="文件传输助手",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("文件传输助手")

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "open_contact")
        self.assertEqual(result.observation["schema"], "wechat.open_contact.v1")
        self.assertEqual(result.observation["status"], "opened")
        self.assertEqual(
            result.observation["openMethod"],
            "control_map_visible_action_ref",
        )
        self.assertEqual(
            result.observation["currentChat"]["title"],
            "文件传输助手",
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/1/0")
        self.assertEqual(app_control.commands[3].input["action"], "AXPress")
        self.assertEqual(
            app_control.commands[3].input["preconditions"]["labelIn"],
            ["文件传输助手,hello,09:00,置顶"],
        )
        self.assertNotIn(
            "type_text",
            [command.operation for command in app_control.commands],
        )

    def test_open_contact_tries_second_mapped_root_after_empty_first(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/11/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
                _accessibility_action_response(
                    ax_path="0/11/1/0/0",
                    role="AXRow",
                    label="文件传输助手,hello,09:00,置顶",
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/4/2",
                            "AXStaticText",
                            value="文件传输助手",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("文件传输助手")

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["currentChat"]["title"],
            "文件传输助手",
        )
        self.assertEqual(
            [
                command.input["root"]["axPath"]
                for command in app_control.commands
                if command.operation == "accessibility_query"
            ],
            ["0/12/1/0", "0/11/1/0", "0/11/4"],
        )

    def test_open_contact_retries_chat_panel_after_layout_path_changes(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/12/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
                _accessibility_action_response(
                    ax_path="0/12/1/0/0",
                    role="AXRow",
                    label="文件传输助手,hello,09:00,置顶",
                ),
                _failed_accessibility_query_response(
                    "accessibility_query_root_not_found",
                    "Could not resolve query root.",
                    retryable=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/4/2",
                            "AXStaticText",
                            value="文件传输助手",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).open_contact("文件传输助手")

        self.assertTrue(result.success)
        self.assertEqual(
            [
                command.input["root"]["axPath"]
                for command in app_control.commands
                if command.operation == "accessibility_query"
            ],
            ["0/12/1/0", "0/12/4", "0/11/4"],
        )

    def test_open_contact_uses_current_frames_for_unsupported_navigation_and_row(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "微信 (通讯录)",
                    }
                },
                _mapped_navigation_frame_response(
                    ax_path="0/1",
                    label="聊天",
                    x=234,
                    y=162,
                    width=60,
                    height=34,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/1",
                    label="聊天",
                    x=234,
                    y=162,
                    width=60,
                    height=34,
                    actionable=False,
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/1/0/0",
                            "AXRow",
                            description="文件传输助手,hello,09:00,置顶",
                            x=294,
                            y=95,
                            width=271,
                            height=68,
                        )
                    ]
                ),
                _coordinate_click_response(),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/4/2",
                            "AXStaticText",
                            value="文件传输助手",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("文件传输助手")

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["currentChat"]["title"],
            "文件传输助手",
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "click",
                "accessibility_query",
                "accessibility_query",
                "click",
                "accessibility_query",
            ],
        )
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 264, "y": 179},
        )
        self.assertEqual(
            app_control.commands[6].input["coordinates"],
            {"x": 430, "y": 129},
        )
        self.assertEqual(
            app_control.commands[3].metadata["coordinateSource"],
            "accessibility_frame",
        )
        self.assertEqual(
            app_control.commands[6].metadata["coordinateSource"],
            "accessibility_frame",
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/1")

    def test_targeted_search_focus_assessment_requires_focused_search_node(
        self,
    ) -> None:
        def assessment(focused: bool | None) -> dict[str, Any]:
            node = _normalized_node(
                "0/12/0",
                "AXTextArea",
                description="搜索",
                focused=focused,
            )
            response = _accessibility_query_response([node])
            observation = ToolObservation.ok(
                command_id="cmd_search_focus",
                tool="macos.computer_use",
                operation="accessibility_query",
                summary="queried search focus",
                observation=response["observation"],
            )
            return tool_module._search_focus_assessment(observation)

        self.assertEqual(assessment(True)["state"], "verified")
        self.assertEqual(
            assessment(False)["reason"],
            "targeted_search_element_not_focused",
        )
        self.assertEqual(
            assessment(None)["reason"],
            "targeted_search_element_focus_unknown",
        )

    def test_search_focus_uses_current_frame_before_ax_set_focus(self) -> None:
        def focus_response(focused: bool) -> dict[str, Any]:
            return _accessibility_query_response(
                [
                    _normalized_node(
                        "0/12/0",
                        "AXTextArea",
                        description="搜索",
                        focused=focused,
                    )
                ]
            )

        app_control = FakeAppControl([{}, focus_response(True)])
        tool = WeChatDesktopTool(app_control)
        search_element = argparse.Namespace(
            role="AXTextArea",
            label="搜索",
            actions=(),
            element_ref=argparse.Namespace(
                ax_path="0/12/0",
                snapshot_id="frontmost:WeChat:微信 (聊天)",
            ),
            frame=argparse.Namespace(x=383, y=49, width=205, height=26),
        )

        result = tool._focus_search_box_phase(
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=argparse.Namespace(elements=[search_element]),
            evidence={},
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["click", "accessibility_query"],
        )
        self.assertEqual(
            app_control.commands[0].metadata["coordinateSource"],
            "accessibility_frame",
        )
        self.assertNotIn(
            "accessibility_action",
            [command.operation for command in app_control.commands],
        )

    def test_search_focus_stops_after_dispatched_ax_set_focus_failure(self) -> None:
        app_control = FakeAppControl([_failed_accessibility_action_response()])
        tool = WeChatDesktopTool(app_control)
        search_element = argparse.Namespace(
            role="AXTextArea",
            label="搜索",
            actions=(),
            element_ref=argparse.Namespace(
                ax_path="0/12/0",
                snapshot_id="frontmost:WeChat:微信 (聊天)",
            ),
            frame=None,
        )

        result = tool._focus_search_box_phase(
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=argparse.Namespace(elements=[search_element]),
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "search_focus_failed")
        self.assertEqual(result.retryable, False)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_search_focus_blocks_press_proof_for_set_focus_request(self) -> None:
        app_control = FakeAppControl(
            [_definite_unsupported_accessibility_action_response(action="AXPress")]
        )
        tool = WeChatDesktopTool(app_control)
        search_element = argparse.Namespace(
            role="AXTextArea",
            label="搜索",
            actions=(),
            element_ref=argparse.Namespace(
                ax_path="0/12/0",
                snapshot_id="frontmost:WeChat:微信 (聊天)",
            ),
            frame=None,
        )

        result = tool._focus_search_box_phase(
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=argparse.Namespace(elements=[search_element]),
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "search_focus_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_search_focus_stops_after_failed_coordinate_click(self) -> None:
        app_control = FakeAppControl([_failed_click_response()])
        tool = WeChatDesktopTool(app_control)
        search_element = argparse.Namespace(
            role="AXTextArea",
            label="搜索",
            actions=(),
            element_ref=argparse.Namespace(
                ax_path="0/12/0",
                snapshot_id="frontmost:WeChat:微信 (聊天)",
            ),
            frame=argparse.Namespace(x=383, y=49, width=205, height=26),
        )

        result = tool._focus_search_box_phase(
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=argparse.Namespace(elements=[search_element]),
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "search_focus_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["click"],
        )

    def test_open_contact_ignores_offscreen_search_candidate_and_uses_return(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _main_children_query_response(),
                {},
                {},
                {},
                {},
                _accessibility_query_response(
                    [_normalized_row("0/11/search/0", "Ada", y=-200)]
                ),
                {},
                _accessibility_query_response(
                    [_normalized_node("0/11/4/2", "AXStaticText", value="Ada")]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).open_contact("Ada")

        self.assertTrue(result.success)
        self.assertEqual(result.observation["currentChat"]["title"], "Ada")
        self.assertIn(
            "press_key",
            [command.operation for command in app_control.commands],
        )
        self.assertNotIn(
            "coordinates",
            app_control.commands[-2].input,
        )

    def test_read_contact_messages_stops_when_opened_chat_title_mismatches(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/12/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
                _accessibility_action_response(
                    ax_path="0/12/1/0/0",
                    role="AXRow",
                    label="文件传输助手,hello,09:00,置顶",
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/4/2",
                            "AXStaticText",
                            value="其他会话(145)",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_contact_messages("文件传输助手", limit=30)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "contact_not_found")
        self.assertEqual(
            result.evidence["open_contact"]["failureKind"],
            "contact_not_found",
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
            ],
        )

    def test_open_contact_falls_back_to_ax_action_when_frame_click_fails(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _main_children_query_response(),
                _coordinate_click_disabled_response(),
                {},
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/0",
                            "AXTextArea",
                            description="搜索",
                            focused=True,
                        )
                    ]
                ),
                {},
                {},
                _accessibility_query_response(
                    [_normalized_row("0/11/search/0", "Ada Lovelace")]
                ),
                {},
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/4/2",
                            "AXStaticText",
                            value="Ada Lovelace",
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("Ada")

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "click",
                "accessibility_action",
                "accessibility_query",
                "hotkey",
                "type_text",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[9].input["action"], "AXSetFocus")
        self.assertEqual(app_control.commands[12].input["text"], "Ada")

    def test_open_contact_unknown_search_focus_never_types_or_presses_return(
        self,
    ) -> None:
        cases = {
            "no_accessibility_snapshot": {},
            "accessibility_snapshot_unavailable": {
                "accessibility": {
                    "available": False,
                    "failureKind": "accessibility_snapshot_timeout",
                }
            },
            "no_focused_element": {
                "accessibility": {
                    "available": True,
                }
            },
            "focused_text_field_is_not_identifiable": {
                "accessibility": {
                    "available": True,
                    "focusedElement": {
                        "role": "AXTextField",
                        "roleDescription": "text field",
                        "frame": {
                            "x": 400,
                            "y": 400,
                            "width": 240,
                            "height": 28,
                        },
                    },
                    "textFields": [],
                }
            },
        }
        for expected_reason, extra_observation in cases.items():
            with self.subTest(reason=expected_reason):
                unknown_focus = {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "微信 (聊天)",
                        **extra_observation,
                    }
                }
                app_control = FakeAppControl(
                    [
                        {},
                        _accessibility_query_response([]),
                        _accessibility_query_response([]),
                        _top_level_query_response(chats_selected=True),
                        _accessibility_query_response([]),
                        _top_level_query_response(chats_selected=True),
                        _main_children_query_response(),
                        {},
                        unknown_focus,
                        {},
                        unknown_focus,
                        {},
                        unknown_focus,
                        {},
                        unknown_focus,
                    ]
                )
                tool = WeChatDesktopTool(app_control)

                result = tool.open_contact("Ada")

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "search_not_focused")
                self.assertEqual(
                    result.observation["searchFocus"]["reason"],
                    expected_reason,
                )
                operations = [command.operation for command in app_control.commands]
                self.assertNotIn("type_text", operations)
                self.assertNotIn("press_key", operations)

    def test_open_contact_reports_disambiguation_from_query_stub(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _main_children_query_response(),
                {},
                {},
                {},
                {},
                _accessibility_query_response(
                    [
                        _normalized_row("0/11/search/0", "Ada"),
                        _normalized_row("0/11/search/1", "Ada Lovelace", y=184),
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.failure_kind, "contact_ambiguous")
        self.assertEqual(result.observation["status"], "needs_disambiguation")
        self.assertEqual(
            [item["displayName"] for item in result.observation["candidates"]],
            ["Ada", "Ada Lovelace"],
        )
        self.assertEqual(
            [item["rowIndex"] for item in result.observation["candidates"]],
            [0, 1],
        )
        self.assertTrue(
            all(
                "element" not in item
                for item in result.observation["candidates"]
            )
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "click",
                "accessibility_query",
                "hotkey",
                "type_text",
                "accessibility_query",
            ],
        )

    def test_open_contact_same_name_mapped_candidates_fail_before_action(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row("0/12/1/0/0", "Ada,first,09:00"),
                        _normalized_row("0/12/1/0/1", "Ada,second,09:01", y=184),
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "contact_ambiguous")
        self.assertEqual(result.observation["status"], "needs_disambiguation")
        self.assertEqual(
            [item["displayName"] for item in result.observation["candidates"]],
            ["Ada", "Ada"],
        )
        self.assertEqual(
            [item["rowIndex"] for item in result.observation["candidates"]],
            [0, 1],
        )
        self.assertEqual(app_control.commands[2].input["query"]["limit"], 2)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query"],
        )

    def test_open_contact_preserves_selector_query_failure_recovery(self) -> None:
        cases = (
            (
                "timeout",
                "accessibility_query_timeout",
                "Accessibility query timed out",
                "accessibility_query_timeout",
                ToolStatus.FAILED,
                "Retry",
            ),
            (
                "transport",
                "helper_transport_failed",
                "Helper socket unavailable",
                "app_control_transport_failed",
                ToolStatus.NOT_READY,
                "Restore",
            ),
        )
        for case, cause, message, expected_kind, expected_status, hint in cases:
            with self.subTest(case=case):
                query_failure = _failed_accessibility_query_response(
                    cause,
                    message,
                    retryable=True,
                )
                app_control = FakeAppControl(
                    [{}, query_failure, query_failure, query_failure]
                )

                result = WeChatDesktopTool(app_control).open_contact("Ada")

                self.assertFalse(result.success)
                self.assertEqual(result.status, expected_status)
                self.assertEqual(result.failure_kind, expected_kind)
                self.assertTrue(result.retryable)
                self.assertIn(hint, result.recovery_hint)
                diagnostics = result.observation["selector"]["diagnostics"]
                self.assertEqual(
                    diagnostics["failureKind"],
                    "selector_query_failed",
                )
                self.assertEqual(
                    diagnostics["causeFailureKind"],
                    cause,
                )

    def test_selector_failure_routing_prefers_structured_diagnostics(self) -> None:
        cases = (
            (
                "transport_over_permission_text",
                "selector_query_failed",
                "helper_transport_failed",
                "Permission denied while reading Accessibility",
                True,
                ToolStatus.NOT_READY,
                "app_control_transport_failed",
                "Restore",
            ),
            (
                "permission_over_timeout_text",
                "selector_query_failed",
                "missing_accessibility",
                "Helper socket timed out",
                False,
                ToolStatus.NOT_READY,
                "missing_accessibility",
                "Grant Accessibility permission",
            ),
            (
                "timeout_over_transport_text",
                "selector_query_failed",
                "accessibility_query_timeout",
                "Helper transport reported permission denied",
                True,
                ToolStatus.FAILED,
                "accessibility_query_timeout",
                "Retry",
            ),
            (
                "truncation_over_permission_text",
                "selector_query_truncated",
                None,
                "Permission denied while collecting more candidates",
                None,
                ToolStatus.FAILED,
                "wechat_query_truncated",
                "narrower selector",
            ),
        )
        for (
            label,
            failure_kind,
            cause,
            message,
            retryable,
            expected_status,
            expected_kind,
            expected_hint,
        ) in cases:
            with self.subTest(label=label):
                diagnostics = SimpleNamespace(
                    tried_selectors=("navigation.contacts",),
                    query_count=1,
                    node_count=0,
                    truncated=failure_kind == "selector_query_truncated",
                    truncation_reason=(
                        "limit" if failure_kind == "selector_query_truncated" else None
                    ),
                    cache_status="disabled",
                    failure_kind=failure_kind,
                    cause_failure_kind=cause,
                    retryable=retryable,
                    message=message,
                )
                diagnostic_payload = tool_module._selector_diagnostics_payload(
                    diagnostics
                )

                result = tool_module._failure_from_selector_query(
                    wechat_command("open_contact", {"contact": "Ada"}),
                    diagnostics,
                    message="selector failed",
                    observation_key="selector",
                    semantic_payload={"diagnostics": diagnostic_payload},
                    evidence={},
                )

                self.assertEqual(result.status, expected_status)
                self.assertEqual(result.failure_kind, expected_kind)
                self.assertEqual(
                    result.retryable,
                    retryable if retryable is not None else True,
                )
                self.assertIn(expected_hint, result.recovery_hint)
                nested = result.observation["selector"]["diagnostics"]
                self.assertEqual(nested["failureKind"], failure_kind)
                if cause is not None:
                    self.assertEqual(nested["causeFailureKind"], cause)

    def test_open_contact_maps_missing_search_box_to_wechat_failure(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/2",
                            "AXButton",
                            description="发起群聊",
                            actions=["AXPress"],
                        )
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.failure_kind, "search_focus_failed")
        self.assertEqual(result.observation["selector"]["id"], "regions.searchBox")
        self.assertEqual(result.observation["selector"]["status"], "not_found")
        self.assertEqual(
            result.observation["selector"]["diagnostics"]["failureKind"],
            "selector_not_found",
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
                "accessibility_query",
            ],
        )

    def test_read_contact_messages_composes_query_backed_apis(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([]),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _accessibility_query_response([]),
                _top_level_query_response(chats_selected=True),
                _main_children_query_response(),
                {},
                {},
                {},
                {},
                _accessibility_query_response(
                    [_normalized_row("0/11/search/0", "Ada")]
                ),
                {},
                _accessibility_query_response(
                    [_normalized_node("0/11/4/2", "AXStaticText", value="Ada")]
                ),
                {},
                _accessibility_query_response(
                    [
                        _normalized_node("0/11/4/2", "AXStaticText", value="Ada"),
                        _normalized_row("0/11/4/0/0/0", "hello"),
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_contact_messages("Ada", limit=5)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "read_contact_messages")
        self.assertEqual(result.observation["schema"], "wechat.contact_messages.v1")
        self.assertEqual(result.observation["target"], "Ada")
        self.assertEqual(result.observation["openContact"]["status"], "opened")
        self.assertEqual(
            result.observation["messages"]["messages"][0]["text"],
            "hello",
        )
        self.assertEqual(
            result.evidence["openContact"]["operation"],
            "open_contact",
        )
        self.assertEqual(
            result.evidence["readVisibleMessages"]["operation"],
            "read_visible_messages",
        )

    def test_open_wechat_reports_environment_diagnostics(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "File Transfer - WeChat",
                        "frontmostVersion": "3.9.12",
                    }
                },
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertTrue(result.success)
        environment = result.observation["wechatEnvironment"]
        self.assertEqual(environment["configuredAppName"], "WeChat")
        self.assertEqual(environment["configuredBundleId"], "com.tencent.xinWeChat")
        self.assertEqual(environment["frontmostApp"], "WeChat")
        self.assertEqual(environment["frontmostBundleId"], "com.tencent.xinWeChat")
        self.assertEqual(environment["windowTitle"], "File Transfer - WeChat")
        self.assertEqual(environment["appVersion"], "3.9.12")

    def test_open_wechat_rejects_mismatched_frontmost_bundle(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "TextEdit",
                        "frontmostBundleId": "com.apple.TextEdit",
                        "windowTitle": "Untitled",
                    }
                },
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertIn("com.apple.TextEdit", result.summary)
        self.assertIn("verify_wechat_window", result.evidence)

    def test_open_wechat_reports_not_logged_in(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "Log In - WeChat",
                        "loggedIn": False,
                    }
                },
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "wechat_not_logged_in")
        self.assertEqual(
            result.recovery_hint,
            "Log in to WeChat Desktop before running this command.",
        )

    def test_focus_contact_delegates_to_verified_open_contact(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses("File Transfer")
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.focus_contact("File Transfer")

        self.assertTrue(result.success)
        self.assertEqual(result.observation["focusedContact"], "File Transfer")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
            ],
        )
        self.assertEqual(result.observation["currentChatTitle"], "File Transfer")
        self.assertEqual(result.observation["confidence"], 0.95)
        self.assertEqual(result.observation["openContact"]["status"], "opened")
        self.assertNotIn(
            "hotkey",
            [command.operation for command in app_control.commands],
        )

    def test_focus_contact_propagates_open_contact_ambiguity(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row("0/12/1/0/0", "Ada,first,09:00"),
                        _normalized_row("0/12/1/0/1", "Ada,second,09:01", y=184),
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.focus_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.failure_kind, "contact_ambiguous")
        self.assertEqual(
            [item["displayName"] for item in result.observation["candidates"]],
            ["Ada", "Ada"],
        )
        self.assertEqual(result.observation["failedPhase"], "open_contact")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
            ],
        )

    def test_draft_message_types_without_submitting(self) -> None:
        app_control = FakeAppControl()
        tool = WeChatDesktopTool(app_control)

        result = tool.draft_message("hello")

        self.assertTrue(result.success)
        self.assertEqual(result.observation["draftReady"], True)
        self.assertEqual(
            result.observation["messageHash"],
            wechat_message_hash("hello"),
        )
        self.assertEqual(app_control.commands[0].operation, "type_text")
        self.assertEqual(app_control.commands[0].input["text"], "hello")

    def test_draft_message_redacts_echoed_input_text_from_events_and_evidence(
        self,
    ) -> None:
        tool = WeChatDesktopTool(FakeAppControl())
        observer = RecordingObserver()

        result = tool.run_command(
            draft_message_command("secret draft", command_id="cmd_draft"),
            observer=observer,
        )

        self.assertTrue(result.success)
        event_payload = observer.events[1].data["appControlObservation"]
        self.assertEqual(
            event_payload["observation"]["input"]["text"],
            "[redacted]",
        )
        self.assertEqual(
            result.evidence["draft"]["observation"]["input"]["text"],
            "[redacted]",
        )
        serialized = json.dumps(
            {
                "events": [event.to_dict() for event in observer.events],
                "result": result.to_dict(),
            },
            ensure_ascii=False,
        )
        self.assertNotIn("secret draft", serialized)

    def test_draft_message_enforces_configured_length(self) -> None:
        app_control = FakeAppControl()
        tool = WeChatDesktopTool(
            app_control,
            config=WeChatDesktopConfig(max_message_chars=4),
        )

        result = tool.draft_message("hello")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "draft_failed")
        self.assertEqual(app_control.commands, [])

    def test_draft_message_maps_input_not_focused_failure(self) -> None:
        app_control = FakeAppControl(
            [
                ToolObservation.failure(
                    command_id="cmd_lower",
                    tool="macos.computer_use",
                    operation="type_text",
                    status=ToolStatus.NOT_READY,
                    error=ToolError(
                        failure_kind="input_not_focused",
                        message="input not focused",
                        retryable=True,
                    ),
                )
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.draft_message("hello")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "input_not_focused")
        self.assertEqual(result.retryable, True)
        self.assertEqual(result.observation["draftReady"], False)
        self.assertEqual(result.observation["inputFocused"], False)
        self.assertIn("draft", result.evidence)
        self.assertIn("focus_contact", result.recovery_hint or "")

    def test_draft_message_maps_unfocused_input_diagnostics(self) -> None:
        app_control = FakeAppControl(
            [
                ToolObservation.failure(
                    command_id="cmd_lower",
                    tool="macos.computer_use",
                    operation="type_text",
                    status=ToolStatus.FAILED,
                    error=ToolError(
                        failure_kind="type_text_failed",
                        message="type text failed",
                        retryable=True,
                    ),
                    observation={"focusedInput": False},
                )
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.draft_message("hello")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "input_not_focused")
        self.assertEqual(result.observation["inputFocused"], False)

    def test_submit_draft_presses_return(self) -> None:
        app_control = FakeAppControl()
        tool = WeChatDesktopTool(app_control)

        result = tool.submit_draft()

        self.assertTrue(result.success)
        self.assertEqual(result.observation["submitted"], True)
        self.assertEqual(app_control.commands[0].operation, "press_key")
        self.assertEqual(app_control.commands[0].input["key"], "Return")

    def test_submit_draft_unknown_reports_attempted_send(self) -> None:
        app_control = FakeAppControl(
            [
                ToolObservation.failure(
                    command_id="cmd_lower",
                    tool="macos.computer_use",
                    operation="press_key",
                    status=ToolStatus.FAILED,
                    error=ToolError(
                        failure_kind="press_key_failed",
                        message="press key failed",
                        retryable=True,
                    ),
                )
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.submit_draft()

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.UNKNOWN)
        self.assertEqual(result.failure_kind, "submit_unknown")
        self.assertEqual(
            result.recovery_hint,
            "Check WeChat manually before retrying.",
        )
        self.assertEqual(result.retryable, False)
        self.assertEqual(
            result.observation,
            {
                "sendAttempted": True,
                "method": "keyboard_return",
            },
        )
        self.assertIn("submit", result.evidence)

    def test_send_message_runs_focus_draft_submit_flow(self) -> None:
        app_control = FakeAppControl(_visible_open_contact_responses("Ada"))
        tool = WeChatDesktopTool(app_control)

        result = tool.send_message(contact="Ada", message="hello")

        self.assertTrue(result.success)
        self.assertEqual(result.observation["focusedContact"], "Ada")
        self.assertEqual(result.observation["submitted"], True)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )
        self.assertNotIn(
            "hotkey",
            [command.operation for command in app_control.commands],
        )

    def test_send_message_preserves_submit_unknown_attempt_facts(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada")
            + [
                {},
                ToolObservation.failure(
                    command_id="cmd_lower",
                    tool="macos.computer_use",
                    operation="press_key",
                    status=ToolStatus.FAILED,
                    error=ToolError(
                        failure_kind="press_key_failed",
                        message="press key failed",
                        retryable=True,
                    ),
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.send_message(contact="Ada", message="hello")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.UNKNOWN)
        self.assertEqual(result.failure_kind, "submit_unknown")
        self.assertEqual(
            result.recovery_hint,
            "Check WeChat manually before retrying.",
        )
        self.assertEqual(result.observation["sendAttempted"], True)
        self.assertEqual(result.observation["method"], "keyboard_return")
        self.assertEqual(result.observation["failedPhase"], "submit_draft")
        self.assertIn("submit_draft", result.evidence)

    def test_send_message_can_verify_visible_message_after_submit(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada")
            + [{}, {}, {}]
            + [
                _accessibility_query_response(
                    [
                        _normalized_node("0/11/4/2", "AXStaticText", value="Ada"),
                        _normalized_row("0/11/4/0/0/0", "hello"),
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.send_message(
            contact="Ada",
            message="hello",
            verify_after_submit=True,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["verified"], True)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
                "open_app",
                "observe",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[-1].input["query"]["scope"], "descendants")

    def test_send_message_can_verify_visible_query_text_after_submit(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada")
            + [{}, {}, {}]
            + [
                _accessibility_query_response(
                    [
                        _normalized_node("0/11/4/2", "AXStaticText", value="Ada"),
                        _normalized_row("0/11/4/0/0/0", "seen"),
                        _normalized_row("0/11/4/0/0/1", "hello", y=184),
                    ]
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.send_message(
            contact="Ada",
            message="hello",
            verify_after_submit=True,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["verified"], True)
        self.assertEqual(app_control.commands[-1].operation, "accessibility_query")

    def test_send_message_returns_unknown_when_verification_misses(
        self,
    ) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada")
            + [{}, {}, {}]
            + [
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/4/2",
                            "AXStaticText",
                            value="Ada",
                        ),
                        _normalized_row("0/11/4/0/0/0", "hi"),
                    ]
                )
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.send_message(
            contact="Ada",
            message="hello",
            verify_after_submit=True,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.UNKNOWN)
        self.assertEqual(result.failure_kind, "send_unverified")
        self.assertEqual(
            result.recovery_hint,
            "Check WeChat manually before retrying.",
        )
        self.assertEqual(result.observation["submitted"], True)
        self.assertEqual(result.observation["verified"], False)

    def test_observe_current_chat_maps_semantic_fields(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "Ada - WeChat",
                        "messages": [{"direction": "incoming", "text": "hi"}],
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.observe_current_chat()

        self.assertTrue(result.success)
        self.assertEqual(result.observation["frontmostApp"], "WeChat")
        self.assertEqual(result.observation["currentChatTitle"], "Ada")
        self.assertEqual(result.observation["messageCount"], 1)
        self.assertEqual(
            result.observation["visibleMessages"],
            [{"direction": "incoming", "text": "hi"}],
        )
        self.assertEqual(app_control.commands[0].operation, "observe")
        self.assertEqual(app_control.commands[0].input["includeVisibleText"], True)

    def test_observe_current_chat_rejects_non_wechat_app_name(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "frontmostApp": "TextEdit",
                        "windowTitle": "Untitled",
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(
            app_control,
            config=WeChatDesktopConfig(bundle_id=None),
        )

        result = tool.observe_current_chat()

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertIn("TextEdit", result.summary)

    def test_read_visible_messages_uses_accessibility_query_stub(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_node("0/11/4/2", "AXStaticText", value="Ada"),
                        _normalized_row("0/11/4/0/0/0", "one"),
                        _normalized_row("0/11/4/0/0/1", "two", y=184),
                        _normalized_row("0/11/4/0/0/2", "three", y=248),
                    ],
                    truncated=True,
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["schema"], "wechat.messages.v1")
        self.assertEqual(result.observation["chat"]["title"], "Ada")
        self.assertEqual(
            [message["text"] for message in result.observation["messages"]],
            ["one", "two"],
        )
        self.assertEqual(result.observation["truncated"], True)
        self.assertEqual(result.observation["pagination"]["canReadOlder"], True)
        self.assertIsNotNone(result.observation["pagination"]["olderPageToken"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/4/0/0")
        self.assertEqual(app_control.commands[2].input["query"]["timeBudgetMs"], 2_200)
        self.assertEqual(
            app_control.commands[2].input["query"]["match"]["roleIn"],
            ["AXRow", "AXCell", "AXStaticText"],
        )
        self.assertEqual(result.observation["source"]["mode"], "control_map")

    def test_read_visible_messages_reports_missing_message_region(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/1",
                            "AXRadioButton",
                            description="聊天",
                            value=1,
                        )
                    ]
                ),
                _accessibility_query_response([]),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=10)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.failure_kind, "message_region_not_found")

    def test_run_command_rejects_unsupported_tool(self) -> None:
        tool = WeChatDesktopTool(FakeAppControl())

        result = tool.run_command(
            ToolCommand(
                command_id="cmd_1",
                tool="other.tool",
                operation="open_wechat",
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.tool, "other.tool")
        self.assertEqual(result.status, ToolStatus.FAILED)
        self.assertEqual(result.failure_kind, "unsupported_tool")

    def test_run_command_returns_invalid_input_failure(self) -> None:
        tool = WeChatDesktopTool(FakeAppControl())

        result = tool.run_command(
            ToolCommand(
                command_id="cmd_1",
                tool=WECHAT_TOOL,
                operation="focus_contact",
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.FAILED)
        self.assertEqual(result.failure_kind, "invalid_input")
        self.assertIn("contact is required", result.summary)

    def test_run_stream_yields_started_and_observation_events(self) -> None:
        tool = WeChatDesktopTool(FakeAppControl())
        observer = RecordingObserver()

        events = list(
            tool.run_stream(
                ToolCommand(
                    command_id="cmd_1",
                    tool=WECHAT_TOOL,
                    operation="open_wechat",
                ),
                observer=observer,
            )
        )

        self.assertEqual([event.event_type for event in events], [
            ToolEventType.STARTED,
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.OBSERVATION,
        ])
        self.assertEqual(
            [event.phase for event in events],
            [
                "open_wechat",
                "open_wechat",
                "verify_wechat_window",
                "open_wechat",
            ],
        )
        self.assertEqual(events[1].data["appControlOperation"], "open_app")
        self.assertEqual(events[2].data["appControlOperation"], "observe")
        self.assertEqual(observer.events, events)
        _assert_observation_timing(
            ToolObservation.from_dict(events[-1].data["observation"])
        )

    def test_run_command_observer_receives_progress_events(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses("File Transfer")
        )
        tool = WeChatDesktopTool(app_control)
        observer = RecordingObserver()

        result = tool.run_command(
            focus_contact_command("File Transfer", command_id="cmd_focus"),
            observer=observer,
        )

        self.assertTrue(result.success)
        self.assertEqual([event.event_type for event in observer.events], [
            ToolEventType.STARTED,
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.OBSERVATION,
        ])
        self.assertEqual(
            [event.phase for event in observer.events[1:-1]],
            [
                "open_contact.open_wechat",
                "open_contact.verify_wechat_window",
                "open_contact.control_map_conversation_target_0",
                "open_contact.control_map_open_visible_contact",
                "open_contact.verify_contact",
            ],
        )
        self.assertEqual(
            [event.seq for event in observer.events],
            list(range(len(observer.events))),
        )
        self.assertEqual(
            observer.events[3].data["appControlObservation"]["operation"],
            "accessibility_query",
        )

    def test_from_config_uses_shared_wechat_config(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses(
                "Ada",
                app_bundle_id="com.example.Weixin",
            )
        )
        config = AppControlConfig.from_dict(
            {
                "computer_use": {"backend": "direct"},
                "wechat": {
                    "app_name": "Weixin",
                    "bundle_id": "com.example.Weixin",
                    "app_control_tool": "custom.computer_use",
                    "selector_profile_path": "./profiles/wechat-local.toml",
                    "search_hotkey": ["Command", "K"],
                    "search_clear_hotkey": ["Command", "L"],
                    "clear_key": "Backspace",
                    "submit_key": "Enter",
                    "default_timeout_ms": 1234,
                    "max_message_chars": 5,
                }
            }
        )
        tool = WeChatDesktopTool.from_config(app_control, config)

        result = tool.focus_contact("Ada")

        self.assertTrue(result.success)
        self.assertEqual(tool.config.app_name, "Weixin")
        self.assertEqual(tool.config.bundle_id, "com.example.Weixin")
        self.assertEqual(tool.config.computer_use_backend, "direct")
        self.assertEqual(
            tool.config.selector_profile_path,
            "./profiles/wechat-local.toml",
        )
        self.assertEqual(app_control.commands[0].tool, "custom.computer_use")
        self.assertEqual(
            app_control.commands[0].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(app_control.commands[0].timeout_ms, 1234)
        self.assertEqual(
            app_control.commands[1].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(app_control.commands[2].operation, "accessibility_query")
        self.assertEqual(
            app_control.commands[2].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(app_control.commands[3].operation, "accessibility_action")
        self.assertEqual(app_control.commands[4].operation, "accessibility_query")
        self.assertEqual(
            app_control.commands[4].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(result.observation["bundleId"], "com.example.Weixin")

    def test_from_config_rejects_helper_backend_before_app_control(self) -> None:
        app_control = FakeAppControl()
        config = AppControlConfig.from_dict(
            {"computer_use": {"backend": "helper"}}
        )

        with self.assertRaisesRegex(
            ValueError,
            "computer_use.backend=helper",
        ):
            WeChatDesktopTool.from_config(app_control, config)

        self.assertEqual(app_control.commands, [])

    def test_direct_and_direct_backed_local_service_remain_constructible(
        self,
    ) -> None:
        config = AppControlConfig.from_dict(
            {"computer_use": {"backend": "direct"}}
        )
        clients = (
            FakeAppControl(),
            LocalServiceAppControl("/tmp/app-control-construction-test.sock"),
        )
        for client in clients:
            with self.subTest(client=type(client).__name__):
                tool = WeChatDesktopTool.from_config(client, config)

                self.assertEqual(tool.config.computer_use_backend, "direct")

    def test_package_boundary_has_no_product_or_backend_imports(self) -> None:
        package_dir = Path(__file__).parents[1] / "src" / "wechat_desktop_tool"
        allowed_selector_profile_import = package_dir / "profiles.py"
        lower_source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in package_dir.rglob("*.py")
        )

        for forbidden in (
            "taskweavn",
            "plato",
            "computer_use_macos.client",
            "computer_use_macos.service",
            "computer_use_macos.cli",
            "openai",
            "anthropic",
        ):
            self.assertNotIn(forbidden, lower_source)

        for path in package_dir.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "computer_use_macos" not in source:
                continue
            self.assertEqual(path, allowed_selector_profile_import)
            self.assertIn("computer_use_macos.selectors", source)


class WeChatDesktopCliTests(unittest.TestCase):
    def test_examples_send_message_dry_run_drafts_without_submit(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "examples",
                    "send-message",
                    "--contact",
                    "Ada",
                    "--message",
                    "hello",
                    "--dry-run",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertTrue(payload["draft"]["success"])
        self.assertEqual(
            [command["operation"] for command in payload["appControlCommands"]],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
            ],
        )

    def test_examples_send_message_live_default_does_not_auto_select_contact(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "微信 (聊天)",
                    }
                },
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["submitted"], False)
        self.assertEqual(payload["focus"]["failureKind"], "contact_not_focused")
        self.assertFalse(payload["draft"]["success"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe"],
        )

    def test_examples_send_message_live_allows_selector_backed_focus_select(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada") + [{}, {}]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--allow-focus-select",
                        "--submit",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )
        self.assertEqual(
            app_control.commands[2].input["query"]["match"]["descriptionContains"],
            "Ada,",
        )

    def test_examples_send_message_ignores_legacy_search_hotkey_for_visible_contact(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            _visible_open_contact_responses("Ada") + [{}, {}]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                "[wechat]\nsearch_hotkey = [\"Command\", \"F\"]\n",
                encoding="utf-8",
            )
            try:
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "examples",
                            "send-message",
                            "--contact",
                            "Ada",
                            "--message",
                            "hello",
                            "--socket-path",
                            "/tmp/app-control.sock",
                            "--config",
                            str(config_path),
                            "--allow-focus-select",
                            "--submit",
                        ]
                    )
            finally:
                cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )
        self.assertNotIn(
            "hotkey",
            [command.operation for command in app_control.commands],
        )

    def test_examples_send_message_live_default_drafts_current_chat(self) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "Ada - WeChat",
                    }
                },
                {},
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertTrue(payload["focus"]["success"])
        self.assertEqual(payload["focus"]["observation"]["autoSelectContact"], False)
        self.assertTrue(payload["draft"]["success"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "type_text"],
        )

    def test_examples_send_message_live_can_assume_current_chat(self) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "微信 (聊天)",
                    }
                },
                {},
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--assume-current-chat",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertTrue(payload["focus"]["success"])
        self.assertEqual(payload["focus"]["observation"]["assumedCurrentChat"], True)
        self.assertEqual(payload["focus"]["observation"]["autoSelectContact"], False)
        self.assertTrue(payload["draft"]["success"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "type_text"],
        )

    def test_examples_send_message_live_submit_wraps_current_chat_result(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "Ada - WeChat",
                    }
                },
                {},
                {},
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--submit",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["result"]["operation"], "send_message")
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
        self.assertEqual(
            payload["result"]["observation"]["autoSelectContact"],
            False,
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "type_text", "press_key"],
        )

    def test_examples_send_message_dry_run_requires_submit_flag(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "examples",
                    "send-message",
                    "--contact",
                    "Ada",
                    "--message",
                    "hello",
                    "--dry-run",
                    "--submit",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(
            [command["operation"] for command in payload["appControlCommands"]],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )

    def test_examples_inspect_window_writes_output_file(self) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                _top_level_query_response(),
                _main_children_query_response(),
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "wechat-window.json"
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "examples",
                            "inspect-window",
                            "--socket-path",
                            "/tmp/app-control.sock",
                            "--output",
                            str(output_path),
                        ]
                    )
                payload = json.loads(output_path.read_text(encoding="utf-8"))
        finally:
            cli_module._app_control_for_args = original

        status = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(status["output"], str(output_path))
        self.assertEqual(status["success"], True)
        self.assertEqual(payload["result"]["operation"], "inspect_window")
        self.assertEqual(
            payload["result"]["observation"]["schema"],
            WECHAT_WINDOW_SCHEMA,
        )
        self.assertEqual(
            payload["result"]["observation"]["window"]["navigation"][1]["label"],
            "contacts",
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["query"]["scope"], "children")


class WeChatDesktopSmokeScriptTests(unittest.TestCase):
    def test_module_entrypoint_runs_send_message_dry_run(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = _pythonpath(
            "packages/app-control-protocol/src",
            "packages/wechat-desktop-tool/src",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "wechat_desktop_tool",
                "examples",
                "send-message",
                "--contact",
                "Ada",
                "--message",
                "hello",
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertEqual(payload["focus"]["success"], True)
        self.assertEqual(payload["draft"]["success"], True)

    def test_smoke_script_dry_run_drafts_without_submit(self) -> None:
        module = _load_wechat_smoke_module()
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_DRY_RUN": "1",
                }
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertEqual(
            [command["operation"] for command in payload["appControlCommands"]],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
            ],
        )

    def test_smoke_script_accepts_allow_send_alias_for_submit_opt_in(self) -> None:
        module = _load_wechat_smoke_module()
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_DRY_RUN": "1",
                    "WECHAT_TOOL_ALLOW_SEND": "1",
                }
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(
            [command["operation"] for command in payload["appControlCommands"]],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )

    def test_smoke_script_dry_run_can_switch_contact_and_submit(self) -> None:
        module = _load_wechat_smoke_module()
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_DRY_RUN": "1",
                    "WECHAT_TOOL_ALLOW_SEND": "1",
                    "WECHAT_TOOL_ALLOW_FOCUS_SELECT": "1",
                }
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(payload["result"]["observation"]["focusedContact"], "Ada")
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
        self.assertEqual(
            [command["operation"] for command in payload["appControlCommands"]],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )
        self.assertEqual(
            payload["appControlCommands"][2]["input"]["query"]["match"][
                "descriptionContains"
            ],
            "Ada,",
        )
        self.assertEqual(payload["appControlCommands"][5]["input"]["text"], "hello")
        self.assertEqual(payload["appControlCommands"][6]["input"]["key"], "Return")

    def test_smoke_script_accepts_config_without_socket_path(self) -> None:
        module = _load_wechat_smoke_module()
        captured: list[list[str]] = []
        original_cli_main = module.wechat_cli_main
        module.wechat_cli_main = lambda argv: captured.append(list(argv)) or 0

        try:
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_CONFIG": "./app-control.toml",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            captured[0],
            [
                "examples",
                "send-message",
                "--contact",
                "Ada",
                "--message",
                "hello",
                "--config",
                "./app-control.toml",
            ],
        )

    def test_smoke_script_accepts_allow_focus_select_opt_in(self) -> None:
        module = _load_wechat_smoke_module()
        captured: list[list[str]] = []
        original_cli_main = module.wechat_cli_main
        module.wechat_cli_main = lambda argv: captured.append(list(argv)) or 0

        try:
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_CONFIG": "./app-control.toml",
                    "WECHAT_TOOL_ALLOW_FOCUS_SELECT": "1",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertIn("--allow-focus-select", captured[0])

    def test_smoke_script_accepts_switch_contact_submit_opt_in(self) -> None:
        module = _load_wechat_smoke_module()
        captured: list[list[str]] = []
        original_cli_main = module.wechat_cli_main
        module.wechat_cli_main = lambda argv: captured.append(list(argv)) or 0

        try:
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_CONFIG": "./app-control.toml",
                    "WECHAT_TOOL_ALLOW_SEND": "1",
                    "WECHAT_TOOL_ALLOW_FOCUS_SELECT": "1",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertIn("--submit", captured[0])
        self.assertIn("--allow-focus-select", captured[0])

    def test_smoke_script_accepts_assume_current_chat_opt_in(self) -> None:
        module = _load_wechat_smoke_module()
        captured: list[list[str]] = []
        original_cli_main = module.wechat_cli_main
        module.wechat_cli_main = lambda argv: captured.append(list(argv)) or 0

        try:
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_CONFIG": "./app-control.toml",
                    "WECHAT_TOOL_ASSUME_CURRENT_CHAT": "1",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertIn("--assume-current-chat", captured[0])

    def test_smoke_script_requires_socket_unless_dry_run(self) -> None:
        module = _load_wechat_smoke_module()
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                }
            )

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "WECHAT_TOOL_SOCKET_PATH or WECHAT_TOOL_CONFIG is required",
            stderr.getvalue(),
        )

    def test_window_inspect_script_accepts_config_and_output(self) -> None:
        module = _load_wechat_window_inspect_module()
        captured: list[list[str]] = []
        original_cli_main = module.wechat_cli_main
        module.wechat_cli_main = lambda argv: captured.append(list(argv)) or 0

        try:
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONFIG": "./app-control.toml",
                    "WECHAT_TOOL_OUTPUT": "./wechat-window.json",
                    "WECHAT_TOOL_INCLUDE_RAW": "1",
                    "WECHAT_TOOL_INCLUDE_ACTIONABLES": "0",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            captured[0],
            [
                "examples",
                "inspect-window",
                "--output",
                "./wechat-window.json",
                "--config",
                "./app-control.toml",
                "--include-raw",
                "--no-actionables",
            ],
        )

    def test_window_inspect_script_requires_socket_unless_dry_run(self) -> None:
        module = _load_wechat_window_inspect_module()
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = module.main({"WECHAT_TOOL_OUTPUT": "./wechat-window.json"})

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "WECHAT_TOOL_SOCKET_PATH or WECHAT_TOOL_CONFIG is required",
            stderr.getvalue(),
        )


class WeChatDesktopCliServiceClientTests(unittest.TestCase):
    def test_app_control_args_use_helper_endpoint_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[computer_use]",
                        "timeout_ms = 2500",
                        "",
                        "[helper]",
                        'transport = "unix_socket"',
                        'endpoint = "/tmp/config.sock"',
                        'token = "config-token"',
                    ]
                ),
                encoding="utf-8",
            )

            client = _app_control_for_args(
                argparse.Namespace(
                    config=str(config_path),
                    dry_run=False,
                    socket_path=None,
                    token=None,
                    token_file=None,
                ),
                argparse.ArgumentParser(),
            )

        self.assertIsInstance(client, LocalServiceAppControl)
        self.assertEqual(str(client._socket_path), "/tmp/config.sock")
        self.assertEqual(client._token, "config-token")
        self.assertEqual(client._timeout, 2.5)

    def test_app_control_args_prefer_cli_socket_and_token_over_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[computer_use]",
                        "timeout_ms = 2500",
                        "",
                        "[helper]",
                        'transport = "unix_socket"',
                        'endpoint = "/tmp/config.sock"',
                        'token = "config-token"',
                    ]
                ),
                encoding="utf-8",
            )

            client = _app_control_for_args(
                argparse.Namespace(
                    config=str(config_path),
                    dry_run=False,
                    socket_path="/tmp/cli.sock",
                    token="cli-token",
                    token_file=None,
                ),
                argparse.ArgumentParser(),
            )

        self.assertIsInstance(client, LocalServiceAppControl)
        self.assertEqual(str(client._socket_path), "/tmp/cli.sock")
        self.assertEqual(client._token, "cli-token")
        self.assertEqual(client._timeout, 2.5)

    def test_local_service_socket_timeout_covers_command_timeout(self) -> None:
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
            timeout_ms=30_000,
        )
        payload = {
            "schema": "app_control.service.request.v1",
            "action": "run",
            "command": command.to_dict(),
        }

        timeout = cli_module._socket_timeout_for_payload(payload, default=10.0)

        self.assertEqual(timeout, 35.0)

    def test_local_service_socket_timeout_does_not_shrink_config_timeout(self) -> None:
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
            timeout_ms=1_000,
        )
        payload = {
            "schema": "app_control.service.request.v1",
            "action": "run",
            "command": command.to_dict(),
        }

        timeout = cli_module._socket_timeout_for_payload(payload, default=10.0)

        self.assertEqual(timeout, 10.0)

    def test_local_service_client_validates_response_and_observation(self) -> None:
        client = LocalServiceAppControl("/tmp/app-control.sock")
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
        )
        observation = ToolObservation.ok(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
            summary="observed",
            observation={"frontmostApp": "WeChat"},
        )
        client._round_trip = lambda payload: {  # type: ignore[method-assign]
            "schema": "app_control.service.response.v1",
            "requestId": payload["requestId"],
            "status": "complete",
            "success": True,
            "observation": observation.to_dict(),
        }

        result = client.run_command(command)

        self.assertEqual(result.to_dict(), observation.to_dict())

    def test_local_service_client_rejects_invalid_service_response(self) -> None:
        client = LocalServiceAppControl("/tmp/app-control.sock")
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
        )
        client._round_trip = lambda payload: {  # type: ignore[method-assign]
            "schema": "app_control.service.response.v1",
            "success": True,
            "observation": {},
        }

        with self.assertRaisesRegex(RuntimeError, "invalid local service response"):
            client.run_command(command)

    def test_local_service_client_rejects_invalid_observation(self) -> None:
        client = LocalServiceAppControl("/tmp/app-control.sock")
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
        )
        client._round_trip = lambda payload: {  # type: ignore[method-assign]
            "schema": "app_control.service.response.v1",
            "requestId": payload["requestId"],
            "status": "complete",
            "success": True,
            "observation": {"schema": "app_control.observation.v1"},
        }

        with self.assertRaisesRegex(RuntimeError, "invalid local service observation"):
            client.run_command(command)


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


if __name__ == "__main__":
    unittest.main()
