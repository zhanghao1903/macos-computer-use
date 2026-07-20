from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from _tool_test_support import failed_accessibility_action_response
from app_control_protocol import ToolCommand, ToolObservation

from wechat_desktop_tool._mapped_controls import (
    _execute_mapped_control,
    _mapped_region_node,
    _press_mapped_navigation,
    _query_mapped_collection,
    _query_mapped_conversation_target,
)
from wechat_desktop_tool._runtime import WeChatToolRuntime
from wechat_desktop_tool.commands import wechat_command


class _RecordingAppControl:
    def __init__(self, responses: list[ToolObservation] | None = None) -> None:
        self.commands: list[ToolCommand] = []
        self._responses = list(responses or [])

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
        if self._responses:
            return self._responses.pop(0)
        return _query_response([])


def _query_response(nodes: list[dict[str, Any]]) -> ToolObservation:
    return ToolObservation.ok(
        command_id="query",
        tool="macos.computer_use",
        operation="accessibility_query",
        summary="query ok",
        observation={
            "accessibilityQuery": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "status": "ok",
                "snapshotId": "frontmost:WeChat:微信 (聊天)",
                "app": {
                    "name": "WeChat",
                    "bundleId": "com.tencent.xinWeChat",
                },
                "window": {
                    "role": "AXWindow",
                    "title": "微信 (聊天)",
                    "frame": {
                        "x": 0,
                        "y": 0,
                        "width": 1200,
                        "height": 900,
                    },
                },
                "nodes": nodes,
                "diagnostics": {
                    "truncated": False,
                    "returnedNodes": len(nodes),
                },
            }
        },
    )


def _navigation_node(*, selected: bool) -> dict[str, Any]:
    return {
        "axPath": "0/2",
        "role": "AXRadioButton",
        "description": "通讯录",
        "enabled": True,
        "selected": selected,
        "actions": ["AXPress"],
        "frame": {"x": 20, "y": 100, "width": 40, "height": 40},
    }


class MappedControlTests(unittest.TestCase):
    def test_active_navigation_title_skips_backend_action(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)
        evidence: dict[str, Any] = {}

        result = _press_mapped_navigation(
            runtime,
            wechat_command("list_contacts", command_id="skip"),
            "contacts",
            active_window_title="微信 - 通讯录",
            evidence=evidence,
        )

        assert result is not None
        self.assertTrue(result.success)
        self.assertEqual(result.observation["status"], "already_selected")
        self.assertEqual(app_control.commands, [])
        self.assertIn("control_map_switch_contacts_skipped", evidence)

    def test_unknown_navigation_key_returns_none_without_backend(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)

        result = _press_mapped_navigation(
            runtime,
            wechat_command("list_contacts"),
            "missing",
            evidence={},
        )

        self.assertIsNone(result)
        self.assertEqual(app_control.commands, [])

    def test_mapped_region_prefers_path_with_reference_root(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())

        node = _mapped_region_node(
            runtime,
            "mainContent",
            reference_ax_path="0/11/1/0",
        )

        self.assertEqual(
            node,
            {
                "axPath": "0/11",
                "role": "AXSplitGroup",
                "label": "main-content",
            },
        )

    def test_collection_query_keeps_configured_bounds_and_root(self) -> None:
        nodes = [
            {
                "axPath": "0/12/2/0/0",
                "role": "AXStaticText",
                "value": "Ada",
            }
        ]
        app_control = _RecordingAppControl([_query_response(nodes)])
        runtime = WeChatToolRuntime.create(app_control)

        result = _query_mapped_collection(
            runtime,
            wechat_command("list_contacts", command_id="contacts"),
            "contacts",
            semantic_limit=30,
            evidence={},
        )

        assert result is not None
        self.assertEqual(result[2], nodes)
        child = app_control.commands[0]
        self.assertEqual(child.input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(child.input["query"]["limit"], 60)
        self.assertEqual(child.input["query"]["timeBudgetMs"], 1_200)
        self.assertEqual(child.input["query"]["preferVisibleRows"], True)

    def test_unknown_action_result_never_reaches_coordinate_fallback(self) -> None:
        app_control = _RecordingAppControl(
            [
                _query_response([_navigation_node(selected=False)]),
                failed_accessibility_action_response(),
            ]
        )
        runtime = WeChatToolRuntime.create(app_control)
        control = runtime.control_map.navigation["contacts"]

        result = _execute_mapped_control(
            runtime,
            wechat_command("list_contacts", command_id="unknown"),
            control,
            action_id="nav.contacts.press",
            target_summary="Switch to contacts",
            phase="control_map_switch_contacts",
            evidence={},
        )

        assert result is not None
        self.assertFalse(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_query", "accessibility_action"],
        )

    def test_successful_navigation_requires_selected_postcondition(self) -> None:
        action_ok = ToolObservation.ok(
            command_id="action",
            tool="macos.computer_use",
            operation="accessibility_action",
            summary="action ok",
        )
        app_control = _RecordingAppControl(
            [
                _query_response([_navigation_node(selected=False)]),
                action_ok,
                _query_response([_navigation_node(selected=True)]),
            ]
        )
        runtime = WeChatToolRuntime.create(app_control)
        control = runtime.control_map.navigation["contacts"]

        result = _execute_mapped_control(
            runtime,
            wechat_command("list_contacts", command_id="selected"),
            control,
            action_id="nav.contacts.press",
            target_summary="Switch to contacts",
            phase="control_map_switch_contacts",
            evidence={},
        )

        assert result is not None
        self.assertTrue(result.success)
        self.assertEqual(result.observation["status"], "selected")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_query", "accessibility_action", "accessibility_query"],
        )

    def test_conversation_target_query_stays_bounded_to_two_nodes(self) -> None:
        app_control = _RecordingAppControl([_query_response([]), _query_response([])])
        runtime = WeChatToolRuntime.create(app_control)

        result = _query_mapped_conversation_target(
            runtime,
            wechat_command("open_contact", command_id="conversation"),
            "Ada",
            evidence={},
        )

        assert result is not None
        self.assertEqual(result[2], [])
        self.assertEqual(len(app_control.commands), 2)
        for child in app_control.commands:
            self.assertEqual(child.input["query"]["limit"], 2)
            self.assertEqual(child.input["query"]["maxDepth"], 2)
            self.assertEqual(
                child.input["query"]["match"],
                {"roleIn": ["AXCell"], "descriptionContains": "Ada,"},
            )


if __name__ == "__main__":
    unittest.main()
