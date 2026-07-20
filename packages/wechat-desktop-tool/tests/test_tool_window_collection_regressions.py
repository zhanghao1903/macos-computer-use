from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    FakeAppControl,
    LoggingConfig,
    LoggingToolObserver,
    Path,
    RecordingObserver,
    StringIO,
    ToolStatus,
    WeChatDesktopConfig,
    WeChatDesktopTool,
    _accessibility_action_response,
    _accessibility_query_response,
    _coordinate_click_response,
    _definite_unsupported_accessibility_action_response,
    _failed_accessibility_action_response,
    _failed_accessibility_query_response,
    _mapped_navigation_frame_response,
    _normalized_node,
    _normalized_row,
    json,
    list_contacts_command,
    list_conversations_command,
    read_visible_messages_command,
    resources,
    tempfile,
)


class WeChatDesktopToolTests(unittest.TestCase):
    def test_list_contacts_uses_packaged_control_map_fast_path(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _accessibility_action_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                            x=295,
                            y=132,
                        ),
                        _normalized_node(
                            "0/12/2/0/1/0/1",
                            "AXStaticText",
                            value="Bob",
                            x=295,
                            y=202,
                        ),
                        _normalized_node(
                            "0/12/2/0/2/0/1",
                            "AXStaticText",
                            value="Charlie",
                            x=295,
                            y=272,
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "list_contacts")
        self.assertEqual(result.observation["schema"], "wechat.contacts.v1")
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada", "Bob"],
        )
        self.assertEqual(result.observation["items"][0]["kind"], "contact")
        self.assertEqual(
            result.observation["items"][0]["actionId"],
            "contacts.visible.0.open",
        )
        self.assertNotIn("actionRef", result.observation["items"][0])
        self.assertEqual(
            result.observation["items"][0]["element"]["role"],
            "AXRow",
        )
        self.assertEqual(result.observation["pagination"]["limit"], 2)
        self.assertEqual(
            result.observation["pagination"]["mode"],
            "visibleWindow",
        )
        self.assertEqual(result.observation["pagination"]["hasMore"], True)
        self.assertIsNone(result.observation["pagination"]["nextPageToken"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/2")
        self.assertTrue(app_control.commands[2].input["query"]["actions"])
        self.assertEqual(app_control.commands[3].operation, "accessibility_action")
        self.assertEqual(app_control.commands[4].input["root"]["axPath"], "0/2")
        self.assertEqual(app_control.commands[5].input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(
            app_control.commands[5].input["root"]["resolver"],
            {
                "strategy": "attributePath",
                "steps": [
                    {"attribute": "AXChildren", "index": 12},
                    {"attribute": "AXChildren", "index": 2},
                    {"attribute": "AXContents", "index": 0, "pathIndex": 0},
                ],
            },
        )
        self.assertLessEqual(
            app_control.commands[5].input["query"]["timeBudgetMs"],
            1_200,
        )
        self.assertEqual(
            app_control.commands[5].input["query"]["match"]["roleIn"],
            ["AXStaticText"],
        )
        self.assertFalse(app_control.commands[5].input["query"]["actions"])
        self.assertEqual(
            app_control.commands[5].input["query"]["attributes"],
            ["AXRole", "AXValue", "AXPosition", "AXSize", "AXFrame"],
        )
        self.assertEqual(
            app_control.commands[5].input["query"]["preferVisibleRows"],
            True,
        )
        self.assertNotIn(
            "click",
            [command.operation for command in app_control.commands],
        )
        self.assertEqual(result.observation["source"]["mode"], "control_map")

    def test_list_contacts_skips_special_and_section_rows_before_limit(
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
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="新的朋友",
                        ),
                        _normalized_node(
                            "0/12/2/0/1/0/1",
                            "AXStaticText",
                            value="A",
                        ),
                        _normalized_node(
                            "0/12/2/0/2/0/1",
                            "AXStaticText",
                            value="联系人",
                        ),
                        _normalized_node(
                            "0/12/2/0/3/0/1",
                            "AXStaticText",
                            value="Ada",
                            x=295,
                            y=213,
                        ),
                        _normalized_node(
                            "0/12/2/0/4/0/1",
                            "AXStaticText",
                            value="已添加",
                            x=428,
                            y=281,
                        ),
                        _normalized_node(
                            "0/12/2/0/4/0/2",
                            "AXStaticText",
                            value="Bob",
                            x=295,
                            y=282,
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=2)

        self.assertTrue(result.success)
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada", "Bob"],
        )
        self.assertEqual(result.observation["pagination"]["limit"], 2)
        self.assertEqual(app_control.commands[2].input["query"]["limit"], 60)
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(
            app_control.commands[2].input["query"]["preferVisibleRows"],
            True,
        )

    def test_list_contacts_skips_navigation_when_contacts_window_active(self) -> None:
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
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["items"][0]["displayName"], "Ada")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/2/0")
        self.assertEqual(
            app_control.commands[2].input["query"]["preferVisibleRows"],
            True,
        )

    def test_semantic_list_limits_do_not_leak_raw_ax_content_to_observability(
        self,
    ) -> None:
        canary = "PRIVATE_CANARY_CHARLIE"
        contacts_query = _accessibility_query_response(
            [
                _normalized_node(
                    "0/12/2/0/0/0/1",
                    "AXStaticText",
                    value="Ada",
                ),
                _normalized_node(
                    "0/12/2/0/1/0/1",
                    "AXStaticText",
                    value="Bob",
                ),
                _normalized_node(
                    "0/12/2/0/2/0/1",
                    "AXStaticText",
                    value=canary,
                ),
            ]
        )
        contacts_query["summary"] = f"query observed {canary}"
        conversations_query = _accessibility_query_response(
            [
                _normalized_row("0/12/1/0/0", "Ada,first,09:00"),
                _normalized_row("0/12/1/0/1", "Bob,second,10:00", y=184),
                _normalized_row(
                    "0/12/1/0/2",
                    f"Charlie,{canary},11:00",
                    y=248,
                ),
            ]
        )
        conversations_query["summary"] = f"query observed {canary}"
        messages_query = _accessibility_query_response(
            [
                _normalized_node("0/11/4/2", "AXStaticText", value="Ada"),
                _normalized_row("0/11/4/0/0/0", "one"),
                _normalized_row("0/11/4/0/0/1", "two", y=184),
                _normalized_row("0/11/4/0/0/2", canary, y=248),
            ]
        )
        messages_query["summary"] = f"query observed {canary}"
        cases = (
            (
                "contacts",
                list_contacts_command(limit=2, command_id="cmd_contacts_privacy"),
                [
                    {},
                    {
                        "observation": {
                            "frontmostApp": "WeChat",
                            "frontmostBundleId": "com.tencent.xinWeChat",
                            "windowTitle": "微信 (通讯录)",
                        }
                    },
                    contacts_query,
                ],
                lambda result: [
                    item["displayName"] for item in result.observation["items"]
                ],
                ["Ada", "Bob"],
            ),
            (
                "conversations",
                list_conversations_command(
                    limit=2,
                    command_id="cmd_conversations_privacy",
                ),
                [{}, conversations_query],
                lambda result: [
                    item["preview"] for item in result.observation["items"]
                ],
                ["first", "second"],
            ),
            (
                "messages",
                read_visible_messages_command(
                    limit=2,
                    command_id="cmd_messages_privacy",
                ),
                [{}, messages_query],
                lambda result: [
                    item["text"] for item in result.observation["messages"]
                ],
                ["one", "two"],
            ),
        )

        for label, command, responses, semantic_values, expected in cases:
            with self.subTest(label=label):
                observer = RecordingObserver()
                result = WeChatDesktopTool(FakeAppControl(responses)).run_command(
                    command,
                    observer=observer,
                )

                self.assertTrue(result.success)
                self.assertEqual(semantic_values(result), expected)
                serialized_result_evidence = json.dumps(
                    result.evidence,
                    ensure_ascii=False,
                )
                serialized_events = json.dumps(
                    [event.to_dict() for event in observer.events],
                    ensure_ascii=False,
                )
                log_stream = StringIO()
                logging_observer = LoggingToolObserver(
                    config=LoggingConfig(json=True, redact_text=True),
                    stream=log_stream,
                )
                for event in observer.events:
                    logging_observer.on_event(event)

                self.assertNotIn(canary, serialized_result_evidence)
                self.assertNotIn(canary, serialized_events)
                self.assertNotIn(canary, log_stream.getvalue())

    def test_row_without_axpress_does_not_publish_unexecutable_axpress_action_ref(
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
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertNotIn("actionRef", result.observation["items"][0])
        self.assertNotIn(
            "AXPress",
            result.observation["items"][0]["element"].get("actions", []),
        )

    def test_list_contacts_stops_after_dispatched_action_failure(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _failed_accessibility_action_response(),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_contacts(limit=2)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.FAILED)
        self.assertEqual(result.failure_kind, "wechat_navigation_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
            ],
        )
        self.assertEqual(app_control.commands[2].timeout_ms, 800)
        self.assertEqual(app_control.commands[3].timeout_ms, 2_000)

    def test_list_contacts_falls_back_once_for_definite_unsupported_action(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _definite_unsupported_accessibility_action_response(),
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["items"][0]["displayName"], "Ada")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "click",
                "accessibility_query",
                "accessibility_query",
            ],
        )

    def test_list_contacts_preserves_selector_permission_failure(self) -> None:
        permission_failure = _failed_accessibility_query_response(
            "missing_accessibility",
            "Accessibility permission is required",
            retryable=False,
        )
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
                permission_failure,
                permission_failure,
                permission_failure,
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.NOT_READY)
        self.assertEqual(result.failure_kind, "missing_accessibility")
        self.assertFalse(result.retryable)
        self.assertIn("Grant Accessibility permission", result.recovery_hint)
        diagnostics = result.observation["selector"]["diagnostics"]
        self.assertEqual(diagnostics["failureKind"], "selector_query_failed")
        self.assertEqual(
            diagnostics["causeFailureKind"],
            "missing_accessibility",
        )

    def test_mapped_navigation_click_uses_current_validated_frame_center(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    x=10,
                    y=20,
                    width=40,
                    height=30,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[3].operation, "click")
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 30, "y": 35},
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/2")

    def test_mapped_navigation_accepts_one_point_window_edge_rounding(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    x=-1,
                    y=20,
                    width=40,
                    height=30,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[3].operation, "click")
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 19, "y": 35},
        )

    def test_mapped_navigation_ignores_packaged_screen_coordinates(self) -> None:
        profile_text = (
            resources.files("wechat_desktop_tool")
            .joinpath("profiles/wechat-macos.toml")
            .read_text(encoding="utf-8")
        )
        profile_text = profile_text.replace(
            'labels = ["通讯录", "__EN_CONTACTS_PLACEHOLDER__"]',
            (
                'labels = ["通讯录", "__EN_CONTACTS_PLACEHOLDER__"]\n'
                "screen_coordinates = [{ x = 999, y = 999 }]"
            ),
            1,
        )
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    x=10,
                    y=20,
                    width=40,
                    height=30,
                    actionable=False,
                ),
                _coordinate_click_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/12/2/0/0/0/1",
                            "AXStaticText",
                            value="Ada",
                        )
                    ]
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "wechat-with-legacy-coordinate.toml"
            profile_path.write_text(profile_text, encoding="utf-8")
            tool = WeChatDesktopTool(
                app_control,
                WeChatDesktopConfig(selector_profile_path=str(profile_path)),
            )

            result = tool.list_contacts(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[3].operation, "click")
        self.assertEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 30, "y": 35},
        )
        self.assertNotEqual(
            app_control.commands[3].input["coordinates"],
            {"x": 999, "y": 999},
        )

    def test_mapped_navigation_missing_or_stale_frame_fails_closed(self) -> None:
        unsafe_targets = {
            "missing_window_frame": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                include_window_frame=False,
            ),
            "outside_window": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                x=2_000,
                y=20,
            ),
            "outside_window_edge_tolerance": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                x=-1.1,
                y=20,
            ),
            "empty_target_frame": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                width=0,
            ),
            "disabled_target": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                enabled=False,
            ),
            "wrong_app": _mapped_navigation_frame_response(
                ax_path="0/2",
                label="通讯录",
                app_bundle_id="com.example.NotWeChat",
            ),
        }
        for name, target_response in unsafe_targets.items():
            with self.subTest(name=name):
                app_control = FakeAppControl([{}, target_response])

                result = WeChatDesktopTool(app_control).list_contacts(limit=1)

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "wechat_navigation_failed")
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["open_app", "observe", "accessibility_query"],
                )

    def test_mapped_navigation_requires_semantic_postcondition(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                ),
                _accessibility_action_response(),
                _mapped_navigation_frame_response(
                    ax_path="0/2",
                    label="通讯录",
                    selected=False,
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_contacts(limit=1)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_navigation_failed")
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

    def test_list_conversations_uses_packaged_control_map_fast_path(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_node(
                            "0/11/1/0/0",
                            "AXRow",
                            description="文件传输助手,hello,09:00,置顶",
                            x=330,
                            y=120,
                            width=270,
                            height=64,
                            actions=["AXPress"],
                        ),
                        _normalized_node(
                            "0/11/1/0/1",
                            "AXRow",
                            description="目标联系人,最近消息,10:00,消息免打扰",
                            x=330,
                            y=184,
                            width=270,
                            height=64,
                            actions=["AXPress"],
                        ),
                        _normalized_node(
                            "0/11/1/0/0/0",
                            "AXCell",
                            description="文件传输助手,hello,09:00,置顶",
                        ),
                        _normalized_node(
                            "0/11/1/0/1/0",
                            "AXCell",
                            description="目标联系人,最近消息,10:00,消息免打扰",
                        ),
                    ],
                ),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_conversations(limit=30)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "list_conversations")
        self.assertEqual(result.observation["schema"], "wechat.conversations.v1")
        rows = result.observation["items"]
        self.assertEqual(rows[0]["displayName"], "文件传输助手")
        self.assertEqual(rows[0]["preview"], "hello")
        self.assertEqual(rows[0]["timestamp"], "09:00")
        self.assertEqual(rows[0]["pinned"], True)
        self.assertEqual(rows[0]["element"]["label"], "文件传输助手")
        self.assertEqual(rows[0]["actionRef"]["action"], "AXPress")
        self.assertEqual(rows[0]["actionRef"]["target"]["role"], "AXRow")
        self.assertEqual(rows[0]["actionRef"]["target"]["actions"], ["AXPress"])
        self.assertEqual(
            rows[0]["actionRef"]["preconditions"]["labelIn"],
            ["文件传输助手,hello,09:00,置顶"],
        )
        self.assertIn("createdAt", rows[0]["actionRef"])
        self.assertIn("expiresAt", rows[0]["actionRef"])
        self.assertEqual(rows[1]["displayName"], "目标联系人")
        self.assertEqual(rows[1]["muted"], True)
        self.assertEqual(rows[1]["actionRef"]["action"], "AXPress")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
            ],
        )
        self.assertEqual(app_control.commands[2].input["root"]["axPath"], "0/12/1/0")
        self.assertEqual(app_control.commands[2].input["query"]["timeBudgetMs"], 2_200)
        self.assertEqual(
            app_control.commands[2].input["query"]["preferVisibleRows"],
            True,
        )
        self.assertEqual(
            app_control.commands[2].input["query"]["match"]["roleIn"],
            ["AXRow", "AXCell", "AXStaticText"],
        )
        self.assertEqual(result.observation["source"]["mode"], "control_map")

    def test_visible_window_list_does_not_publish_false_continuation_token(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/11/1/0/0",
                            "Ada,first,09:00",
                        ),
                        _normalized_row(
                            "0/11/1/0/1",
                            "Bob,second,09:01",
                            y=184,
                        ),
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_conversations(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["pagination"],
            {
                "mode": "visibleWindow",
                "limit": 1,
                "pageToken": None,
                "hasMore": True,
                "nextPageToken": None,
            },
        )
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["Ada"],
        )

    def test_visible_window_list_rejects_unsupported_page_token(self) -> None:
        app_control = FakeAppControl()

        result = WeChatDesktopTool(app_control).list_contacts(
            limit=30,
            page_token="contacts:next:stale",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "pagination_not_supported")
        self.assertEqual(result.recovery_hint, "Retry without pageToken.")
        self.assertEqual(result.observation["pagination"]["nextPageToken"], None)
        self.assertEqual(app_control.commands, [])

    def test_list_conversations_skips_press_when_current_nav_node_is_selected(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "Window",
                    }
                },
                _mapped_navigation_frame_response(
                    ax_path="0/1",
                    label="聊天",
                    selected=True,
                ),
                _accessibility_query_response(
                    [
                        _normalized_row(
                            "0/12/1/0/0",
                            "文件传输助手,hello,09:00,置顶",
                        )
                    ]
                ),
            ]
        )

        result = WeChatDesktopTool(app_control).list_conversations(limit=1)

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_query",
            ],
        )
        self.assertNotIn(
            "accessibility_action",
            [command.operation for command in app_control.commands],
        )

    def test_list_conversations_tries_second_mapped_root_after_empty_first(
        self,
    ) -> None:
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
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.list_conversations(limit=30)

        self.assertTrue(result.success)
        self.assertEqual(
            [item["displayName"] for item in result.observation["items"]],
            ["文件传输助手"],
        )
        self.assertEqual(
            [
                command.input["root"]["axPath"]
                for command in app_control.commands
                if command.operation == "accessibility_query"
            ],
            ["0/12/1/0", "0/11/1/0"],
        )


if __name__ == "__main__":
    unittest.main()
