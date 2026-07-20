from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    FakeAppControl,
    RecordingObserver,
    ToolError,
    ToolObservation,
    ToolStatus,
    WeChatDesktopConfig,
    WeChatDesktopTool,
    _accessibility_query_response,
    _normalized_node,
    _normalized_row,
    _visible_open_contact_responses,
    draft_message_command,
    json,
    wechat_message_hash,
)


class WeChatDesktopToolTests(unittest.TestCase):
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
        self.assertEqual(
            app_control.commands[-1].input["query"]["scope"], "descendants"
        )

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


if __name__ == "__main__":
    unittest.main()
