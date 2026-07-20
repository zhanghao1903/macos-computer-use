from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from app_control_protocol import ToolCommand, ToolError, ToolObservation, ToolStatus

from wechat_desktop_tool._runtime import WeChatToolRuntime
from wechat_desktop_tool._window_operations import _inspect_window, _open_wechat
from wechat_desktop_tool.commands import wechat_command


class _RecordingAppControl:
    def __init__(self, responses: list[ToolObservation]) -> None:
        self.commands: list[ToolCommand] = []
        self._responses = list(responses)

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
        if not self._responses:
            raise AssertionError(f"unexpected command: {tool_command.operation}")
        return self._responses.pop(0)


def _ok(operation: str) -> ToolObservation:
    return ToolObservation.ok(
        command_id=operation,
        tool="macos.computer_use",
        operation=operation,
        summary=f"{operation} ok",
    )


def _ready() -> ToolObservation:
    return ToolObservation.ok(
        command_id="observe",
        tool="macos.computer_use",
        operation="observe",
        summary="Frontmost app: WeChat. Window: 微信 (聊天).",
        observation={
            "frontmostApp": "WeChat",
            "frontmostBundleId": "com.tencent.xinWeChat",
            "windowTitle": "微信 (聊天)",
            "snapshotId": "frontmost:WeChat:微信 (聊天)",
        },
    )


def _top_nodes(*, include_main: bool = True) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = [
        {
            "axPath": "0/1",
            "role": "AXRadioButton",
            "description": "聊天",
            "selected": True,
            "enabled": True,
            "actions": ["AXPress"],
            "frame": {"x": 20, "y": 100, "width": 40, "height": 40},
        }
    ]
    if include_main:
        nodes.append(
            {
                "axPath": "0/12",
                "role": "AXSplitGroup",
                "description": "main-content",
                "frame": {"x": 70, "y": 0, "width": 1130, "height": 900},
            }
        )
    return nodes


def _query_response(
    nodes: list[dict[str, Any]],
    *,
    raw: dict[str, Any] | None = None,
) -> ToolObservation:
    payload: dict[str, Any] = {
        "schema": "macos.accessibility.query.v1",
        "available": True,
        "status": "ok",
        "snapshotId": "frontmost:WeChat:微信 (聊天)",
        "app": {"name": "WeChat", "bundleId": "com.tencent.xinWeChat"},
        "window": {
            "role": "AXWindow",
            "title": "微信 (聊天)",
            "frame": {"x": 0, "y": 0, "width": 1200, "height": 900},
        },
        "nodes": nodes,
        "diagnostics": {"truncated": False, "returnedNodes": len(nodes)},
    }
    if raw is not None:
        payload["raw"] = raw
    return ToolObservation.ok(
        command_id="query",
        tool="macos.computer_use",
        operation="accessibility_query",
        summary="query ok",
        observation={"accessibilityQuery": payload},
    )


def _runtime_with(*responses: ToolObservation) -> tuple[WeChatToolRuntime, Any]:
    app_control = _RecordingAppControl(list(responses))
    return WeChatToolRuntime.create(app_control), app_control


class WindowOperationTests(unittest.TestCase):
    def test_open_wechat_preserves_two_phase_ready_flow(self) -> None:
        runtime, app_control = _runtime_with(_ok("open_app"), _ready())

        result = _open_wechat(
            runtime,
            wechat_command("open_wechat", command_id="open"),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["appName"], "WeChat")
        self.assertEqual(result.observation["bundleId"], "com.tencent.xinWeChat")
        self.assertEqual(result.observation["windowReady"], True)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe"],
        )

    def test_inspect_window_keeps_scoped_query_sequence(self) -> None:
        runtime, app_control = _runtime_with(
            _ok("open_app"),
            _ready(),
            _query_response(_top_nodes()),
            _query_response([]),
        )

        result = _inspect_window(
            runtime,
            wechat_command("inspect_window", command_id="inspect"),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["schema"], "wechat.window.v1")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["root"]["kind"], "focusedWindow")
        self.assertEqual(app_control.commands[2].input["query"]["maxDepth"], 1)
        self.assertEqual(app_control.commands[3].input["root"]["axPath"], "0/12")

    def test_include_raw_returns_only_explicit_raw_query_payload(self) -> None:
        runtime, _ = _runtime_with(
            _ok("open_app"),
            _ready(),
            _query_response(_top_nodes(), raw={"nodeCount": 2}),
            _query_response([], raw={"nodeCount": 0}),
        )
        command = wechat_command(
            "inspect_window",
            {"includeRaw": True},
            command_id="raw",
        )

        result = _inspect_window(runtime, command)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["includeRaw"], True)
        self.assertEqual(
            result.observation["rawQueries"]["topLevel"]["raw"],
            {"nodeCount": 2},
        )
        self.assertNotIn(
            "raw",
            result.evidence["inspect_window"]["observation"]["accessibilityQuery"],
        )

    def test_include_actionables_false_omits_element_actionables(self) -> None:
        runtime, _ = _runtime_with(
            _ok("open_app"),
            _ready(),
            _query_response(_top_nodes()),
            _query_response([]),
        )
        command = wechat_command(
            "inspect_window",
            {"includeActionables": False},
            command_id="no-actions",
        )

        result = _inspect_window(runtime, command)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["includeActionables"], False)
        self.assertEqual(result.observation["window"]["actionables"], [])

    def test_top_level_query_failure_keeps_wechat_not_ready_translation(self) -> None:
        query_failure = ToolObservation.failure(
            command_id="query",
            tool="macos.computer_use",
            operation="accessibility_query",
            status=ToolStatus.TIMEOUT,
            error=ToolError(
                failure_kind="accessibility_query_timeout",
                message="query timed out",
                retryable=True,
            ),
        )
        runtime, app_control = _runtime_with(
            _ok("open_app"),
            _ready(),
            query_failure,
        )

        result = _inspect_window(
            runtime,
            wechat_command("inspect_window", command_id="failed"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertEqual(result.retryable, True)
        self.assertEqual(len(app_control.commands), 3)

    def test_missing_main_content_is_reported_as_diagnostic_action(self) -> None:
        runtime, app_control = _runtime_with(
            _ok("open_app"),
            _ready(),
            _query_response(_top_nodes(include_main=False)),
        )

        result = _inspect_window(
            runtime,
            wechat_command("inspect_window", command_id="diagnostic"),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["normalization"]["reason"],
            "main_content_missing",
        )
        action_ids = {
            item["id"] for item in result.observation["window"]["availableActions"]
        }
        self.assertIn("diagnostic.main_content_missing", action_ids)
        self.assertEqual(len(app_control.commands), 3)


if __name__ == "__main__":
    unittest.main()
