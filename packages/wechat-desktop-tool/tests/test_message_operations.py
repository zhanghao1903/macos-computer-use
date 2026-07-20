from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import patch

from app_control_protocol import ToolCommand, ToolError, ToolObservation, ToolStatus

import wechat_desktop_tool._message_operations as message_module
from wechat_desktop_tool._message_operations import (
    _draft_message,
    _observe_current_chat,
    _read_contact_messages,
    _read_visible_messages_with_control_map,
    _send_message,
    _submit_draft,
)
from wechat_desktop_tool._runtime import WeChatToolRuntime
from wechat_desktop_tool.commands import WECHAT_TOOL, wechat_command
from wechat_desktop_tool.models import WeChatDesktopConfig, wechat_message_hash


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


def _ok(operation: str, **observation: Any) -> ToolObservation:
    return ToolObservation.ok(
        command_id=operation,
        tool="macos.computer_use",
        operation=operation,
        summary="ok",
        observation=observation,
    )


def _wechat_ok(operation: str, observation: dict[str, Any]) -> ToolObservation:
    return ToolObservation.ok(
        command_id=operation,
        tool=WECHAT_TOOL,
        operation=operation,
        summary="ok",
        observation=observation,
    )


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
                "snapshotId": "snapshot-messages",
                "nodes": nodes,
                "diagnostics": {
                    "truncated": truncated,
                    "returnedNodes": len(nodes),
                },
            }
        },
    )


class MessageOperationTests(unittest.TestCase):
    def test_observe_current_chat_maps_semantic_fields(self) -> None:
        app_control = _RecordingAppControl(
            [
                _ok(
                    "observe",
                    frontmostApp="WeChat",
                    frontmostBundleId="com.tencent.xinWeChat",
                    windowTitle="Ada - WeChat",
                    messages=[{"direction": "incoming", "text": "hi"}],
                )
            ]
        )
        runtime = WeChatToolRuntime.create(app_control)

        result = _observe_current_chat(
            runtime,
            wechat_command(
                "observe_current_chat",
                {"includeVisibleMessages": True},
            ),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["currentChatTitle"], "Ada")
        self.assertEqual(result.observation["messageCount"], 1)
        self.assertEqual(
            result.observation["visibleMessages"],
            [{"direction": "incoming", "text": "hi"}],
        )
        self.assertEqual(app_control.commands[0].input["includeVisibleText"], True)

    def test_read_contact_messages_composes_verified_child_operations(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())
        opened = _wechat_ok(
            "open_contact",
            {"schema": "wechat.open_contact.v1", "status": "opened"},
        )
        messages = _wechat_ok(
            "read_visible_messages",
            {"schema": "wechat.messages.v1", "messages": [{"text": "hello"}]},
        )

        with (
            patch.object(
                message_module, "_open_contact", return_value=opened
            ) as open_call,
            patch.object(
                message_module,
                "_read_visible_messages",
                return_value=messages,
            ) as read_call,
        ):
            result = _read_contact_messages(
                runtime,
                wechat_command(
                    "read_contact_messages",
                    {"contact": "Ada", "limit": 5},
                ),
            )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["target"], "Ada")
        self.assertEqual(open_call.call_args.args[1].operation, "open_contact")
        self.assertEqual(
            read_call.call_args.args[1].input,
            {"limit": 5},
        )

    def test_control_map_messages_keep_source_and_pagination(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())
        query = _query_response(
            [
                {
                    "axPath": "0/12/4/0/0/0",
                    "role": "AXRow",
                    "description": "hello",
                    "frame": {"x": 500, "y": 200, "width": 300, "height": 40},
                }
            ],
            truncated=True,
        )

        with patch.object(
            message_module,
            "_query_mapped_collection",
            return_value=(
                query,
                SimpleNamespace(collection_id="visibleMessages"),
                query.observation["accessibilityQuery"]["nodes"],
            ),
        ):
            result = _read_visible_messages_with_control_map(
                runtime,
                wechat_command("read_visible_messages", {"limit": 20}),
                limit=20,
                evidence={},
            )

        assert result is not None
        self.assertTrue(result.success)
        self.assertEqual(result.observation["messages"][0]["text"], "hello")
        self.assertEqual(result.observation["source"]["mode"], "control_map")
        self.assertEqual(result.observation["pagination"]["canReadOlder"], True)

    def test_draft_message_enforces_configured_limit_before_io(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(
            app_control,
            WeChatDesktopConfig(max_message_chars=4),
        )

        result = _draft_message(
            runtime,
            wechat_command("draft_message", {"message": "hello"}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "draft_failed")
        self.assertEqual(app_control.commands, [])

    def test_draft_message_preserves_input_focus_guard(self) -> None:
        failure = ToolObservation.failure(
            command_id="type",
            tool="macos.computer_use",
            operation="type_text",
            status=ToolStatus.NOT_READY,
            error=ToolError(
                failure_kind="input_not_focused",
                message="input not focused",
                retryable=True,
            ),
        )
        app_control = _RecordingAppControl([failure])
        runtime = WeChatToolRuntime.create(app_control)

        result = _draft_message(
            runtime,
            wechat_command("draft_message", {"message": "hello"}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "input_not_focused")
        self.assertEqual(result.observation["inputFocused"], False)

    def test_submit_failure_is_unknown_and_never_replayed(self) -> None:
        failure = ToolObservation.failure(
            command_id="submit",
            tool="macos.computer_use",
            operation="press_key",
            status=ToolStatus.FAILED,
            error=ToolError(
                failure_kind="press_key_failed",
                message="press key failed",
                retryable=True,
            ),
        )
        app_control = _RecordingAppControl([failure])
        runtime = WeChatToolRuntime.create(app_control)

        result = _submit_draft(
            runtime,
            wechat_command("submit_draft", {"method": "keyboard_return"}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.UNKNOWN)
        self.assertEqual(result.failure_kind, "submit_unknown")
        self.assertEqual(result.observation["sendAttempted"], True)
        self.assertEqual(len(app_control.commands), 1)

    def test_send_message_composes_focus_draft_submit_and_verification(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())
        focus = _wechat_ok("focus_contact", {"focusedContact": "Ada"})
        draft = _wechat_ok(
            "draft_message",
            {"draftReady": True, "messageHash": wechat_message_hash("hello")},
        )
        submitted = _wechat_ok(
            "submit_draft",
            {"submitted": True, "sendAttempted": True},
        )
        verification = _wechat_ok(
            "read_visible_messages",
            {"messages": [{"text": "hello"}]},
        )

        with (
            patch.object(
                message_module, "_focus_contact", return_value=focus
            ) as focus_call,
            patch.object(
                message_module, "_draft_message", return_value=draft
            ) as draft_call,
            patch.object(
                message_module,
                "_submit_draft",
                return_value=submitted,
            ) as submit_call,
            patch.object(
                message_module,
                "_read_visible_messages",
                return_value=verification,
            ) as verify_call,
        ):
            result = _send_message(
                runtime,
                wechat_command(
                    "send_message",
                    {
                        "contact": "Ada",
                        "message": "hello",
                        "verifyAfterSubmit": True,
                        "verifyLimit": 7,
                    },
                ),
            )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["submitted"], True)
        self.assertEqual(result.observation["verified"], True)
        self.assertEqual(focus_call.call_args.args[1].input, {"contact": "Ada"})
        self.assertEqual(draft_call.call_args.args[1].input, {"message": "hello"})
        self.assertEqual(
            submit_call.call_args.args[1].input,
            {"method": "keyboard_return"},
        )
        self.assertEqual(verify_call.call_args.args[1].input, {"limit": 7})


if __name__ == "__main__":
    unittest.main()
