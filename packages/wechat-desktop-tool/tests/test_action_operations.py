from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from _tool_test_support import (
    failed_accessibility_action_response,
    predispatch_accessibility_action_response,
)
from app_control_protocol import ToolCommand, ToolObservation

from wechat_desktop_tool._action_operations import (
    _click_node_phase,
    _execute_action,
    _execute_action_ref,
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
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary="ok",
        )


def _action_ref(**updates: Any) -> dict[str, Any]:
    action_ref: dict[str, Any] = {
        "schema": "wechat.action_ref.v1",
        "id": "nav.contacts.press",
        "kind": "ui.press",
        "action": "AXPress",
        "target": {
            "axPath": "0/2",
            "role": "AXRadioButton",
            "label": "通讯录",
        },
        "preconditions": {"roleIn": ["AXRadioButton"]},
        "fallbacks": [
            {
                "method": "selector_click",
                "selector": {"role": "AXRadioButton", "name": "通讯录"},
            }
        ],
    }
    action_ref.update(updates)
    return action_ref


class ActionOperationTests(unittest.TestCase):
    def test_execute_action_success_keeps_result_and_child_command(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)
        command = wechat_command(
            "execute_action",
            {"actionRef": _action_ref()},
            command_id="wechat-action",
        )

        result = _execute_action(runtime, command)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["schema"], "wechat.execute_action.v1")
        self.assertEqual(result.observation["actionId"], "nav.contacts.press")
        self.assertEqual(result.observation["method"], "accessibility_action")
        self.assertEqual(len(app_control.commands), 1)
        child = app_control.commands[0]
        self.assertEqual(child.command_id, "wechat-action:execute_action")
        self.assertEqual(child.operation, "accessibility_action")
        self.assertEqual(child.input["target"], {"kind": "axPath", "axPath": "0/2"})

    def test_expired_action_ref_fails_without_backend_dispatch(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)
        command = wechat_command("execute_action", command_id="expired")
        evidence: dict[str, Any] = {}

        result = _execute_action_ref(
            runtime,
            command,
            _action_ref(expiresAt="2000-01-01T00:00:00Z"),
            phase="execute_action",
            evidence=evidence,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_ref_expired")
        self.assertEqual(app_control.commands, [])
        self.assertEqual(
            evidence["execute_action"]["failureKind"], "action_ref_expired"
        )

    def test_predispatch_failure_allows_one_selector_fallback(self) -> None:
        app_control = _RecordingAppControl(
            [predispatch_accessibility_action_response()]
        )
        runtime = WeChatToolRuntime.create(app_control)

        result = _execute_action_ref(
            runtime,
            wechat_command("execute_action", command_id="fallback"),
            _action_ref(),
            phase="execute_action",
            evidence={},
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )
        self.assertEqual(
            app_control.commands[1].command_id,
            "fallback:execute_action:selector_fallback",
        )

    def test_unknown_mutation_result_never_replays_or_falls_back(self) -> None:
        app_control = _RecordingAppControl([failed_accessibility_action_response()])
        runtime = WeChatToolRuntime.create(app_control)

        result = _execute_action_ref(
            runtime,
            wechat_command("execute_action", command_id="unknown"),
            _action_ref(),
            phase="execute_action",
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_unlabeled_row_is_rejected_before_any_action(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)

        result = _click_node_phase(
            runtime,
            wechat_command("open_contact", command_id="row"),
            {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "frame": {"x": 100, "y": 100, "width": 200, "height": 40},
            },
            phase="open_visible_contact",
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_target_unverified")
        self.assertEqual(app_control.commands, [])

    def test_row_without_axpress_uses_current_ax_frame_coordinates(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)

        result = _click_node_phase(
            runtime,
            wechat_command("open_contact", command_id="coordinate"),
            {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "label": "Ada",
                "actions": [],
                "frame": {"x": 100, "y": 80, "width": 200, "height": 40},
            },
            phase="open_visible_contact",
            evidence={},
        )

        self.assertTrue(result.success)
        self.assertEqual(len(app_control.commands), 1)
        child = app_control.commands[0]
        self.assertEqual(child.operation, "click")
        self.assertEqual(child.input["coordinates"], {"x": 200, "y": 100})
        self.assertEqual(
            child.metadata["coordinateSource"],
            "accessibility_frame",
        )


if __name__ == "__main__":
    unittest.main()
