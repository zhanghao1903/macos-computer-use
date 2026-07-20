from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    Any,
    FakeAppControl,
    SimpleNamespace,
    ToolObservation,
    ToolStatus,
    WeChatDesktopTool,
    _accessibility_action_response,
    _accessibility_query_response,
    _coordinate_click_disabled_response,
    _coordinate_click_response,
    _definite_unsupported_accessibility_action_response,
    _failed_accessibility_action_response,
    _failed_accessibility_query_response,
    _failed_click_response,
    _focus_search_box_for_test,
    _main_children_query_response,
    _mapped_navigation_frame_response,
    _normalized_node,
    _normalized_row,
    _open_visible_contact_for_test,
    _open_visible_contact_with_control_map_for_test,
    _top_level_query_response,
    _visible_open_contact_responses,
    argparse,
    contact_search_module,
    query_mapping_module,
    wechat_command,
)


class WeChatDesktopToolTests(unittest.TestCase):
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

    def test_truncated_control_map_contact_targets_never_mutate(self) -> None:
        candidate_sets = (
            [],
            [_normalized_row("0/12/1/0/0", "Ada,hello,09:00")],
            [
                _normalized_row("0/12/1/0/0", "Ada,hello,09:00"),
                _normalized_row("0/12/1/0/1", "Ada,other,09:01"),
            ],
        )
        for reason in ("limit", "time_budget", "depth"):
            for nodes in candidate_sets:
                with self.subTest(reason=reason, candidate_count=len(nodes)):
                    response = _accessibility_query_response(
                        nodes,
                        truncated=True,
                        truncation_reason=reason,
                    )
                    app_control = FakeAppControl(
                        [response] if nodes else [response, response]
                    )

                    result = _open_visible_contact_with_control_map_for_test(
                        WeChatDesktopTool(app_control),
                        wechat_command("open_contact", {"contact": "Ada"}),
                        contact="Ada",
                        evidence={},
                    )

                    assert result is not None
                    self.assertFalse(result.success)
                    self.assertEqual(result.failure_kind, "wechat_query_truncated")
                    self.assertEqual(
                        result.observation["diagnostics"]["truncationReason"],
                        reason,
                    )
                    self.assertTrue(
                        all(
                            command.operation == "accessibility_query"
                            for command in app_control.commands
                        )
                    )

    def test_truncated_selector_visible_contact_targets_never_mutate(self) -> None:
        candidate_sets = (
            [],
            [_normalized_row("0/11/1/0/0", "Ada,hello,09:00")],
            [
                _normalized_row("0/11/1/0/0", "Ada,hello,09:00"),
                _normalized_row("0/11/1/0/1", "Ada,other,09:01"),
            ],
        )
        for reason in ("limit", "time_budget", "depth"):
            for nodes in candidate_sets:
                with self.subTest(reason=reason, candidate_count=len(nodes)):
                    app_control = FakeAppControl(
                        [
                            _accessibility_query_response(
                                nodes,
                                truncated=True,
                                truncation_reason=reason,
                            )
                        ]
                    )

                    result = _open_visible_contact_for_test(
                        WeChatDesktopTool(app_control),
                        wechat_command("open_contact", {"contact": "Ada"}),
                        contact="Ada",
                        main_content={"axPath": "0/11", "role": "AXSplitGroup"},
                        evidence={},
                    )

                    assert result is not None
                    self.assertFalse(result.success)
                    self.assertEqual(result.failure_kind, "wechat_query_truncated")
                    self.assertEqual(
                        result.observation["diagnostics"]["truncationReason"],
                        reason,
                    )
                    self.assertEqual(
                        [command.operation for command in app_control.commands],
                        ["accessibility_query"],
                    )

    def test_truncated_search_targets_block_draft_and_submit(self) -> None:
        candidate_sets = (
            [],
            [_normalized_row("0/11/search/0", "Ada")],
            [
                _normalized_row("0/11/search/0", "Ada"),
                _normalized_row("0/11/search/1", "Ada"),
            ],
        )
        for reason in ("limit", "time_budget", "depth"):
            for nodes in candidate_sets:
                with self.subTest(reason=reason, candidate_count=len(nodes)):
                    responses = [
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
                            nodes,
                            truncated=True,
                            truncation_reason=reason,
                        ),
                    ]
                    app_control = FakeAppControl(responses)

                    result = WeChatDesktopTool(app_control).send_message(
                        contact="Ada",
                        message="PRIVATE_MESSAGE_MUST_NOT_BE_DRAFTED",
                    )

                    self.assertFalse(result.success)
                    self.assertEqual(result.failure_kind, "wechat_query_truncated")
                    self.assertEqual(
                        result.observation["diagnostics"]["truncationReason"],
                        reason,
                    )
                    operations = [command.operation for command in app_control.commands]
                    self.assertEqual(operations[-1], "accessibility_query")
                    self.assertNotIn("accessibility_action", operations)
                    self.assertNotIn("press_key", operations)
                    typed_text = [
                        command.input.get("text")
                        for command in app_control.commands
                        if command.operation == "type_text"
                    ]
                    self.assertEqual(typed_text, ["Ada"])

    def test_failed_search_target_query_never_presses_return(self) -> None:
        responses = [
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
            _failed_accessibility_query_response(
                "accessibility_query_timeout",
                "Search result query timed out.",
                retryable=True,
            ),
        ]
        app_control = FakeAppControl(responses)

        result = WeChatDesktopTool(app_control).send_message(
            contact="Ada",
            message="PRIVATE_MESSAGE_MUST_NOT_BE_DRAFTED",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "accessibility_query_timeout")
        operations = [command.operation for command in app_control.commands]
        self.assertEqual(operations[-1], "accessibility_query")
        self.assertNotIn("accessibility_action", operations)
        self.assertNotIn("press_key", operations)
        typed_text = [
            command.input.get("text")
            for command in app_control.commands
            if command.operation == "type_text"
        ]
        self.assertEqual(typed_text, ["Ada"])

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

        result = _open_visible_contact_for_test(
            tool,
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

    def test_open_contact_tries_second_mapped_root_after_first_is_missing(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _failed_accessibility_query_response(
                    "accessibility_query_root_not_found",
                    "Could not resolve query root.",
                    retryable=False,
                ),
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

        result = WeChatDesktopTool(app_control).open_contact("文件传输助手")

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
            return contact_search_module._search_focus_assessment(observation)

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

        result = _focus_search_box_for_test(
            tool,
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

        result = _focus_search_box_for_test(
            tool,
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

        result = _focus_search_box_for_test(
            tool,
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

        result = _focus_search_box_for_test(
            tool,
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

    def test_open_contact_rejects_offscreen_search_candidate_without_return(
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

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_target_unverified")
        self.assertNotIn(
            "press_key",
            [command.operation for command in app_control.commands],
        )
        self.assertEqual(app_control.commands[-1].operation, "accessibility_query")

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
            all("element" not in item for item in result.observation["candidates"])
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
                diagnostic_payload = query_mapping_module._selector_diagnostics_payload(
                    diagnostics
                )

                result = query_mapping_module._failure_from_selector_query(
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
        app_control = FakeAppControl(_visible_open_contact_responses("File Transfer"))
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


if __name__ == "__main__":
    unittest.main()
