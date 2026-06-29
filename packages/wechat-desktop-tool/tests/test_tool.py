from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import redirect_stdout
from contextlib import redirect_stderr
from io import StringIO
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import unittest

from app_control_protocol import (
    AppControlConfig,
    ToolCommand,
    ToolError,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolStatus,
    validate_protocol_payload,
)
from wechat_desktop_tool import (
    WECHAT_TOOL,
    WeChatDesktopConfig,
    WeChatDesktopTool,
    build_wechat_tool,
    draft_message_command,
    focus_contact_command,
    observe_current_chat_command,
    open_wechat_command,
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


class FakeAppControl:
    def __init__(self, responses: list[dict[str, Any] | ToolObservation] | None = None):
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


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[ToolEvent] = []

    def on_event(self, event: ToolEvent) -> None:
        self.events.append(event)


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
        ]

        for command in commands:
            with self.subTest(operation=command.operation):
                self.assertEqual(command.tool, WECHAT_TOOL)
                validate_protocol_payload("command", command.to_dict())
        self.assertEqual(commands[1].input["contact"], "Ada")
        self.assertEqual(commands[3].input["limit"], 5)
        self.assertEqual(commands[6].input["verifyAfterSubmit"], True)
        self.assertEqual(commands[7].timeout_ms, 1234)

    def test_command_builder_output_runs_through_tool(self) -> None:
        tool = WeChatDesktopTool(FakeAppControl())

        result = tool.run_command(draft_message_command("hello"))

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "draft_message")

    def test_developer_entrypoint_modules_are_available(self) -> None:
        from wechat_desktop_tool import WeChatVisibleMessage
        from wechat_desktop_tool import adapter, observations, recipes

        app_control = FakeAppControl()
        tool = build_wechat_tool(app_control)

        self.assertIsInstance(tool, WeChatDesktopTool)
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
        self.assertIn("observe", result.evidence)

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

    def test_focus_contact_runs_search_sequence(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "File Transfer - WeChat",
                    }
                },
            ]
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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
            ],
        )
        self.assertEqual(app_control.commands[2].input["keys"], ["Command", "F"])
        self.assertEqual(
            app_control.commands[2].input["bundleId"],
            "com.tencent.xinWeChat",
        )
        self.assertEqual(app_control.commands[3].input["keys"], ["Command", "A"])
        self.assertEqual(app_control.commands[4].input["key"], "Delete")
        self.assertEqual(app_control.commands[5].input["text"], "File Transfer")
        self.assertEqual(app_control.commands[6].input["key"], "Return")
        self.assertEqual(app_control.commands[7].input["includeVisibleText"], True)
        self.assertEqual(result.observation["currentChatTitle"], "File Transfer")
        self.assertEqual(result.observation["confidence"], 0.95)

    def test_focus_contact_reports_ambiguous_search_results(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                    }
                },
                {},
                {},
                {},
                {
                    "observation": {
                        "contactMatches": [
                            {"displayName": "Ada"},
                            {"displayName": "Ada Lovelace"},
                        ]
                    }
                },
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.focus_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.failure_kind, "contact_ambiguous")
        self.assertEqual(
            result.observation["candidateContacts"],
            ["Ada", "Ada Lovelace"],
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
            ],
        )

    def test_focus_contact_fails_when_verified_chat_title_mismatches(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "Bob - WeChat",
                    }
                },
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.focus_contact("Ada")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.failure_kind, "contact_not_found")
        self.assertIn("Bob", result.summary)
        self.assertIn("verify_contact", result.evidence)

    def test_focus_contact_rejects_verified_non_wechat_window(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {
                    "observation": {
                        "frontmostApp": "TextEdit",
                        "frontmostBundleId": "com.apple.TextEdit",
                        "windowTitle": "File Transfer - WeChat",
                    }
                },
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.focus_contact("File Transfer")

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertIn("com.apple.TextEdit", result.summary)
        self.assertIn("verify_contact", result.evidence)

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
        app_control = FakeAppControl()
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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
                "type_text",
                "press_key",
            ],
        )

    def test_send_message_preserves_submit_unknown_attempt_facts(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
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
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {
                    "observation": {
                        "messages": [{"direction": "outgoing", "text": "hello"}]
                    }
                },
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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
                "type_text",
                "press_key",
                "observe",
            ],
        )
        self.assertEqual(app_control.commands[-1].input["includeVisibleText"], True)

    def test_send_message_can_verify_visible_text_extract_after_submit(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {"observation": {"textExtract": "Ada\nhello\nseen"}},
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
        self.assertEqual(app_control.commands[-1].operation, "observe")

    def test_send_message_returns_unknown_when_verification_misses(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {
                    "observation": {
                        "messages": [{"direction": "incoming", "text": "hi"}]
                    }
                },
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

    def test_read_visible_messages_maps_observe_payload(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "messages": [
                            {"direction": "incoming", "text": "hi"},
                            {"direction": "outgoing", "text": "hello"},
                            {"text": ""},
                        ]
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=10)

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["messages"],
            [
                {"direction": "incoming", "text": "hi"},
                {"direction": "outgoing", "text": "hello"},
            ],
        )
        self.assertEqual(app_control.commands[0].operation, "observe")
        self.assertEqual(app_control.commands[0].input["includeVisibleText"], True)

    def test_read_visible_messages_does_not_mark_exact_limit_as_truncated(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "messages": [
                            {"direction": "incoming", "text": "hi"},
                            {"direction": "outgoing", "text": "hello"},
                        ]
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(len(result.observation["messages"]), 2)
        self.assertEqual(result.observation["truncated"], False)

    def test_read_visible_messages_marks_structured_payload_truncated(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "messages": [
                            {"direction": "incoming", "text": "one"},
                            {"direction": "outgoing", "text": "two"},
                            {"direction": "incoming", "text": "three"},
                        ]
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["messages"],
            [
                {"direction": "incoming", "text": "one"},
                {"direction": "outgoing", "text": "two"},
            ],
        )
        self.assertEqual(result.observation["truncated"], True)

    def test_read_visible_messages_maps_text_extract_payload(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "textExtract": "Ada\nhello from visible chat",
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=10)

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["messages"],
            [
                {
                    "direction": "unknown",
                    "text": "Ada",
                },
                {
                    "direction": "unknown",
                    "text": "hello from visible chat",
                },
            ],
        )

    def test_read_visible_messages_maps_prefixed_text_extract_lines(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "textExtract": (
                            "[14:32] incoming: hello\n"
                            "14:33 outgoing: reply\n"
                            "sent: done"
                        ),
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["messages"],
            [
                {
                    "direction": "incoming",
                    "text": "hello",
                    "visibleTimestamp": "14:32",
                },
                {
                    "direction": "outgoing",
                    "text": "reply",
                    "visibleTimestamp": "14:33",
                },
            ],
        )
        self.assertEqual(result.observation["truncated"], True)

    def test_read_visible_messages_rejects_mismatched_frontmost_bundle(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "frontmostApp": "TextEdit",
                        "frontmostBundleId": "com.apple.TextEdit",
                        "messages": [{"direction": "outgoing", "text": "hello"}],
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=10)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertIn("com.apple.TextEdit", result.summary)

    def test_read_visible_messages_reports_not_logged_in(self) -> None:
        app_control = FakeAppControl(
            [
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "loginRequired": True,
                    }
                }
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.read_visible_messages(limit=10)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "wechat_not_logged_in")

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
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "File Transfer - WeChat",
                    }
                },
            ]
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
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.PROGRESS,
            ToolEventType.OBSERVATION,
        ])
        self.assertEqual(
            [event.phase for event in observer.events[1:-1]],
            [
                "open_wechat",
                "verify_wechat_window",
                "focus_search",
                "select_search_text",
                "clear_search_text",
                "type_contact",
                "select_contact",
                "verify_contact",
            ],
        )
        self.assertEqual(
            [event.seq for event in observer.events],
            list(range(len(observer.events))),
        )
        self.assertEqual(
            observer.events[3].data["appControlObservation"]["operation"],
            "hotkey",
        )

    def test_from_config_uses_shared_wechat_config(self) -> None:
        app_control = FakeAppControl()
        config = AppControlConfig.from_dict(
            {
                "wechat": {
                    "app_name": "Weixin",
                    "bundle_id": "com.example.Weixin",
                    "app_control_tool": "custom.computer_use",
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
        self.assertEqual(app_control.commands[2].input["keys"], ["Command", "K"])
        self.assertEqual(
            app_control.commands[2].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(app_control.commands[3].input["keys"], ["Command", "L"])
        self.assertEqual(app_control.commands[4].input["key"], "Backspace")
        self.assertEqual(app_control.commands[6].input["key"], "Enter")
        self.assertEqual(app_control.commands[7].operation, "observe")
        self.assertEqual(
            app_control.commands[7].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(result.observation["bundleId"], "com.example.Weixin")

    def test_package_boundary_has_no_product_or_backend_imports(self) -> None:
        package_dir = Path(__file__).parents[1] / "src" / "wechat_desktop_tool"
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in package_dir.rglob("*.py")
        )

        for forbidden in (
            "taskweavn",
            "plato",
            "macos_computer_use",
            "computer_use_macos",
            "openai",
            "anthropic",
        ):
            self.assertNotIn(forbidden, source)


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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
                "type_text",
            ],
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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
                "type_text",
                "press_key",
            ],
        )


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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
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
                "hotkey",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
                "type_text",
                "press_key",
            ],
        )

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
