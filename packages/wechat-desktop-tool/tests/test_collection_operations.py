from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest
from unittest.mock import patch

from app_control_protocol import ToolCommand, ToolError, ToolObservation, ToolStatus

import wechat_desktop_tool._collection_operations as collection_module
from wechat_desktop_tool._collection_operations import (
    _list_contacts,
    _list_conversations,
    _list_row_items_with_control_map,
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
        if not self._responses:
            raise AssertionError(f"unexpected command: {tool_command.operation}")
        return self._responses.pop(0)


def _open_ok() -> ToolObservation:
    return ToolObservation.ok(
        command_id="open",
        tool="macos.computer_use",
        operation="open_app",
        summary="open ok",
    )


def _ready(title: str) -> ToolObservation:
    return ToolObservation.ok(
        command_id="observe",
        tool="macos.computer_use",
        operation="observe",
        summary=f"Frontmost app: WeChat. Window: {title}.",
        observation={
            "frontmostApp": "WeChat",
            "frontmostBundleId": "com.tencent.xinWeChat",
            "windowTitle": title,
        },
    )


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
                "snapshotId": "snapshot-list",
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
                    "truncated": False,
                    "returnedNodes": len(nodes),
                },
            }
        },
    )


def _contact_nodes(names: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "axPath": f"0/12/2/0/{index}/0/1",
            "role": "AXStaticText",
            "value": name,
            "frame": {
                "x": 295,
                "y": 200 + index * 40,
                "width": 175,
                "height": 23,
            },
        }
        for index, name in enumerate(names)
    ]


def _runtime_with(
    *responses: ToolObservation,
) -> tuple[WeChatToolRuntime, _RecordingAppControl]:
    app_control = _RecordingAppControl(list(responses))
    return WeChatToolRuntime.create(app_control), app_control


class CollectionOperationTests(unittest.TestCase):
    def test_page_token_is_rejected_before_opening_wechat(self) -> None:
        runtime, app_control = _runtime_with()
        command = wechat_command(
            "list_contacts",
            {"limit": 30, "pageToken": "contacts:next:snapshot"},
        )

        result = _list_contacts(runtime, command)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "pagination_not_supported")
        self.assertEqual(result.retryable, False)
        self.assertEqual(app_control.commands, [])

    def test_contacts_use_control_map_fast_path_and_semantic_limit(self) -> None:
        runtime, app_control = _runtime_with(
            _open_ok(),
            _ready("微信 - 通讯录"),
            _query_response(_contact_nodes(["Ada", "Bob", "Carol"])),
        )
        command = wechat_command("list_contacts", {"limit": 2})

        result = _list_contacts(runtime, command)

        self.assertTrue(result.success)
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada", "Bob"],
        )
        self.assertEqual(result.observation["pagination"]["hasMore"], True)
        self.assertEqual(result.observation["source"]["mode"], "control_map")
        self.assertEqual(
            [item.operation for item in app_control.commands],
            ["open_app", "observe", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[-1].input["query"]["limit"], 60)

    def test_conversations_use_control_map_fast_path(self) -> None:
        nodes = [
            {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "description": "Ada,hello,09:00",
                "actions": ["AXPress"],
                "frame": {"x": 80, "y": 100, "width": 260, "height": 60},
            }
        ]
        runtime, _ = _runtime_with(
            _open_ok(),
            _ready("微信 - 聊天"),
            _query_response(nodes),
        )

        result = _list_conversations(
            runtime,
            wechat_command("list_conversations", {"limit": 30}),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.observation["section"], "chats")
        self.assertEqual(result.observation["items"][0]["displayName"], "Ada")
        self.assertEqual(result.observation["items"][0]["preview"], "hello")

    def test_missing_mapped_navigation_returns_none_for_selector_fallback(self) -> None:
        runtime, app_control = _runtime_with()

        with patch.object(
            collection_module,
            "_press_mapped_navigation",
            return_value=None,
        ):
            result = _list_row_items_with_control_map(
                runtime,
                wechat_command("list_contacts"),
                section="contacts",
                schema="wechat.contacts.v1",
                collection_id="contacts",
                summary="Listed visible WeChat contacts.",
                limit=30,
                page_token=None,
                active_window_title=None,
                evidence={},
            )

        self.assertIsNone(result)
        self.assertEqual(app_control.commands, [])

    def test_navigation_failure_keeps_wechat_failure_translation(self) -> None:
        runtime, _ = _runtime_with()
        navigation_failure = ToolObservation.failure(
            command_id="navigation",
            tool="macos.computer_use",
            operation="accessibility_action",
            status=ToolStatus.FAILED,
            error=ToolError(
                failure_kind="accessibility_action_failed",
                message="navigation failed",
                retryable=False,
            ),
        )

        with patch.object(
            collection_module,
            "_press_mapped_navigation",
            return_value=navigation_failure,
        ):
            result = _list_row_items_with_control_map(
                runtime,
                wechat_command("list_contacts"),
                section="contacts",
                schema="wechat.contacts.v1",
                collection_id="contacts",
                summary="Listed visible WeChat contacts.",
                limit=30,
                page_token=None,
                active_window_title=None,
                evidence={},
            )

        assert result is not None
        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_navigation_failed")
        self.assertEqual(result.retryable, False)

    def test_missing_mapped_collection_returns_none_for_selector_fallback(self) -> None:
        runtime, _ = _runtime_with()
        navigation_ok = ToolObservation.ok(
            command_id="navigation",
            tool="wechat.desktop",
            operation="list_contacts",
            summary="navigation ok",
        )

        with (
            patch.object(
                collection_module,
                "_press_mapped_navigation",
                return_value=navigation_ok,
            ),
            patch.object(
                collection_module,
                "_query_mapped_collection",
                return_value=None,
            ),
        ):
            result = _list_row_items_with_control_map(
                runtime,
                wechat_command("list_contacts"),
                section="contacts",
                schema="wechat.contacts.v1",
                collection_id="contacts",
                summary="Listed visible WeChat contacts.",
                limit=30,
                page_token=None,
                active_window_title=None,
                evidence={},
            )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
