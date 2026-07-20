from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any
import unittest

from app_control_protocol import ToolCommand, ToolError, ToolObservation, ToolStatus

from wechat_desktop_tool._contact_search import (
    _focus_contact_legacy,
    _focus_search_box_phase,
    _search_focus_assessment,
    _verify_search_focus_phase,
)
from wechat_desktop_tool._runtime import WeChatToolRuntime
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
        summary="ok",
    )


def _failure(operation: str, failure_kind: str) -> ToolObservation:
    return ToolObservation.failure(
        command_id=operation,
        tool="macos.computer_use",
        operation=operation,
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind=failure_kind,
            message=failure_kind,
            retryable=False,
        ),
    )


def _search_query(focused: bool | None = True) -> ToolObservation:
    node: dict[str, Any] = {
        "axPath": "0/12/0",
        "role": "AXTextArea",
        "description": "搜索",
        "enabled": True,
        "frame": {"x": 383, "y": 49, "width": 205, "height": 26},
    }
    if focused is not None:
        node["focused"] = focused
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
                "snapshotId": "snapshot-search",
                "nodes": [node],
                "diagnostics": {"truncated": False, "returnedNodes": 1},
            }
        },
    )


def _search_element(*, with_frame: bool = True) -> SimpleNamespace:
    frame = SimpleNamespace(x=383, y=49, width=205, height=26) if with_frame else None
    return SimpleNamespace(
        role="AXTextArea",
        label="搜索",
        actions=(),
        element_ref=SimpleNamespace(
            ax_path="0/12/0",
            snapshot_id="snapshot-search",
        ),
        frame=frame,
    )


def _ready() -> ToolObservation:
    return ToolObservation.ok(
        command_id="ready",
        tool="macos.computer_use",
        operation="observe",
        summary="WeChat ready",
        observation={
            "frontmostApp": "WeChat",
            "frontmostBundleId": "com.tencent.xinWeChat",
            "windowTitle": "微信 (聊天)",
        },
    )


class ContactSearchTests(unittest.TestCase):
    def test_query_focus_assessment_preserves_three_states(self) -> None:
        cases = {
            True: ("verified", "targeted_search_element_focused"),
            False: ("not_search", "targeted_search_element_not_focused"),
            None: ("unknown", "targeted_search_element_focus_unknown"),
        }

        for focused, expected in cases.items():
            with self.subTest(focused=focused):
                assessment = _search_focus_assessment(_search_query(focused))
                self.assertEqual(
                    (assessment["state"], assessment["reason"]),
                    expected,
                )

    def test_verify_focus_uses_exact_ax_path_and_500ms_budget(self) -> None:
        app_control = _RecordingAppControl([_search_query()])
        runtime = WeChatToolRuntime.create(app_control)

        result = _verify_search_focus_phase(
            runtime,
            wechat_command("open_contact", {"contact": "Ada"}),
            phase="verify_search_focus",
            search_element=_search_element(),
        )

        self.assertTrue(result.success)
        child = app_control.commands[0]
        self.assertEqual(child.operation, "accessibility_query")
        self.assertEqual(
            child.input["root"],
            {"kind": "axPath", "axPath": "0/12/0"},
        )
        self.assertEqual(child.input["query"]["timeBudgetMs"], 500)
        self.assertEqual(child.timeout_ms, 500)

    def test_focus_uses_current_frame_before_ax_set_focus(self) -> None:
        app_control = _RecordingAppControl([_ok("click"), _search_query()])
        runtime = WeChatToolRuntime.create(app_control)

        result = _focus_search_box_phase(
            runtime,
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=SimpleNamespace(elements=[_search_element()]),
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

    def test_disabled_coordinate_click_falls_back_to_ax_set_focus(self) -> None:
        app_control = _RecordingAppControl(
            [
                _failure("click", "coordinate_click_disabled"),
                _ok("accessibility_action"),
                _search_query(),
            ]
        )
        runtime = WeChatToolRuntime.create(app_control)

        result = _focus_search_box_phase(
            runtime,
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=SimpleNamespace(elements=[_search_element()]),
            evidence={},
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["click", "accessibility_action", "accessibility_query"],
        )

    def test_unknown_ax_set_focus_failure_is_not_replayed(self) -> None:
        app_control = _RecordingAppControl(
            [_failure("accessibility_action", "accessibility_action_result_unknown")]
        )
        runtime = WeChatToolRuntime.create(app_control)

        result = _focus_search_box_phase(
            runtime,
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            search_box=SimpleNamespace(elements=[_search_element(with_frame=False)]),
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "search_focus_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_legacy_focus_refuses_to_type_when_search_is_unverified(self) -> None:
        focus_observation = ToolObservation.ok(
            command_id="focus",
            tool="macos.computer_use",
            operation="observe",
            summary="chat input focused",
            observation={
                "accessibility": {
                    "available": True,
                    "focusedElement": {
                        "role": "AXTextArea",
                        "description": "消息",
                    },
                }
            },
        )
        app_control = _RecordingAppControl(
            [_ok("open_app"), _ready(), _ok("hotkey"), focus_observation]
        )
        runtime = WeChatToolRuntime.create(app_control)

        result = _focus_contact_legacy(
            runtime,
            wechat_command("focus_contact", {"contact": "Ada"}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "search_not_focused")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "hotkey", "observe"],
        )
        self.assertNotIn(
            "type_text",
            [command.operation for command in app_control.commands],
        )


if __name__ == "__main__":
    unittest.main()
