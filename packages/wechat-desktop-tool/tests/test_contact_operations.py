from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest
from unittest.mock import patch

from app_control_protocol import ToolCommand, ToolObservation

import wechat_desktop_tool._contact_operations as contact_module
from wechat_desktop_tool._contact_operations import (
    _contact_target_query_validation_failure,
    _focus_contact,
    _open_visible_contact_with_control_map,
    _opened_contact_observation,
)
from wechat_desktop_tool._runtime import WeChatToolRuntime
from wechat_desktop_tool.commands import WECHAT_TOOL, wechat_command


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
        if not self._responses:
            raise AssertionError(f"unexpected command: {tool_command.operation}")
        return self._responses.pop(0)


def _query_response(
    nodes: list[dict[str, Any]],
    *,
    truncated: bool = False,
) -> ToolObservation:
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
                "snapshotId": "snapshot-contact",
                "app": {
                    "name": "WeChat",
                    "bundleId": "com.tencent.xinWeChat",
                },
                "window": {
                    "role": "AXWindow",
                    "title": "微信",
                    "frame": {"x": 0, "y": 0, "width": 1200, "height": 900},
                },
                "nodes": nodes,
                "diagnostics": {
                    "truncated": truncated,
                    "returnedNodes": len(nodes),
                },
            }
        },
    )


def _title_node(title: str) -> dict[str, Any]:
    return {
        "axPath": "0/12/4/0",
        "role": "AXStaticText",
        "value": title,
        "frame": {"x": 500, "y": 80, "width": 200, "height": 24},
    }


class ContactOperationTests(unittest.TestCase):
    def test_opened_contact_accepts_matching_verified_title(self) -> None:
        app_control = _RecordingAppControl([_query_response([_title_node("Ada")])])
        runtime = WeChatToolRuntime.create(app_control)

        result = _opened_contact_observation(
            runtime,
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            main_content={"axPath": "0/12/4", "role": "AXGroup"},
            open_method="control_map_visible_action_ref",
            evidence={},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["status"], "opened")
        self.assertEqual(result.observation["currentChat"], {"title": "Ada"})
        self.assertEqual(result.observation["confidence"], 0.95)
        self.assertEqual(len(app_control.commands), 1)

    def test_opened_contact_rejects_mismatched_verified_title(self) -> None:
        app_control = _RecordingAppControl([_query_response([_title_node("Bob")])])
        runtime = WeChatToolRuntime.create(app_control)

        result = _opened_contact_observation(
            runtime,
            wechat_command("open_contact", {"contact": "Ada"}),
            contact="Ada",
            main_content={"axPath": "0/12/4", "role": "AXGroup"},
            open_method="search",
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "contact_not_found")
        self.assertEqual(result.observation["currentChat"], {"title": "Bob"})

    def test_truncated_target_query_fails_before_any_action(self) -> None:
        app_control = _RecordingAppControl()
        command = wechat_command("open_contact", {"contact": "Ada"})
        query = _query_response([], truncated=True)

        result = _contact_target_query_validation_failure(
            command,
            "Ada",
            query,
            evidence={},
        )

        assert result is not None
        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_query_truncated")
        self.assertEqual(app_control.commands, [])

    def test_complete_target_query_has_no_validation_failure(self) -> None:
        result = _contact_target_query_validation_failure(
            wechat_command("open_contact", {"contact": "Ada"}),
            "Ada",
            _query_response([]),
            evidence={},
        )

        self.assertIsNone(result)

    def test_missing_control_map_target_preserves_selector_fallback(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())

        with patch.object(
            contact_module,
            "_query_mapped_conversation_target",
            return_value=None,
        ):
            result = _open_visible_contact_with_control_map(
                runtime,
                wechat_command("open_contact", {"contact": "Ada"}),
                contact="Ada",
                evidence={},
            )

        self.assertIsNone(result)

    def test_focus_contact_delegates_to_verified_open_contact(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())
        opened = ToolObservation.ok(
            command_id="child",
            tool=WECHAT_TOOL,
            operation="open_contact",
            summary="opened",
            observation={
                "schema": "wechat.open_contact.v1",
                "currentChat": {"title": "Ada"},
                "confidence": 1.0,
            },
        )

        with patch.object(contact_module, "_open_contact", return_value=opened) as call:
            result = _focus_contact(
                runtime,
                wechat_command("focus_contact", {"contact": "Ada"}),
            )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["focusedContact"], "Ada")
        self.assertEqual(result.observation["currentChatTitle"], "Ada")
        child_command = call.call_args.args[1]
        self.assertEqual(child_command.operation, "open_contact")
        self.assertEqual(child_command.input, {"contact": "Ada"})


if __name__ == "__main__":
    unittest.main()
