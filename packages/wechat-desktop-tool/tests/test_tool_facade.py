from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    AppControlConfig,
    FakeAppControl,
    LocalServiceAppControl,
    Path,
    RecordingObserver,
    ToolCommand,
    ToolEventType,
    ToolObservation,
    ToolStatus,
    WECHAT_TOOL,
    WECHAT_WINDOW_SCHEMA,
    WeChatDesktopConfig,
    WeChatDesktopTool,
    WeChatWindow,
    _accessibility_query_response,
    _assert_observation_timing,
    _main_children_query_response,
    _top_level_query_response,
    _tree_children_query_response,
    _visible_open_contact_responses,
    _wechat_window_tree_fixture,
    build_wechat_tool,
    build_wechat_window_model,
    draft_message_command,
    execute_action_command,
    focus_contact_command,
    inspect_window_command,
    list_contacts_command,
    list_conversations_command,
    observe_current_chat_command,
    open_contact_command,
    open_wechat_command,
    read_contact_messages_command,
    read_visible_messages_command,
    send_message,
    send_message_command,
    submit_draft_command,
    validate_protocol_payload,
    wechat_command,
)


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
            inspect_window_command(command_id="cmd_inspect"),
            list_contacts_command(limit=10, command_id="cmd_contacts"),
            list_conversations_command(limit=11, command_id="cmd_conversations"),
            open_contact_command("Ada", command_id="cmd_open_contact"),
            execute_action_command(
                {
                    "schema": "wechat.action_ref.v1",
                    "id": "nav.contacts.press",
                    "target": {"axPath": "0/2"},
                    "action": "AXPress",
                },
                command_id="cmd_execute_action",
            ),
            read_contact_messages_command(
                "Ada",
                limit=12,
                command_id="cmd_contact_messages",
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
        self.assertEqual(commands[8].operation, "inspect_window")
        self.assertEqual(commands[8].input["includeRaw"], False)
        self.assertEqual(commands[8].input["includeActionables"], True)
        self.assertEqual(commands[9].operation, "list_contacts")
        self.assertEqual(commands[9].input["limit"], 10)
        self.assertEqual(commands[10].operation, "list_conversations")
        self.assertEqual(commands[10].input["limit"], 11)
        self.assertEqual(commands[11].operation, "open_contact")
        self.assertEqual(commands[11].input["contact"], "Ada")
        self.assertEqual(commands[12].operation, "execute_action")
        self.assertEqual(commands[12].input["actionRef"]["id"], "nav.contacts.press")
        self.assertEqual(commands[13].operation, "read_contact_messages")
        self.assertEqual(commands[13].input["limit"], 12)

    def test_command_builder_output_runs_through_tool(self) -> None:
        tool = WeChatDesktopTool(FakeAppControl())

        result = tool.run_command(draft_message_command("hello"))

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "draft_message")

    def test_developer_entrypoint_modules_are_available(self) -> None:
        from wechat_desktop_tool import WeChatVisibleMessage
        from wechat_desktop_tool import adapter, observations, recipes
        from wechat_desktop_tool.models import WeChatWindow as ModelWeChatWindow

        app_control = FakeAppControl(_visible_open_contact_responses("Ada") + [{}, {}])
        tool = build_wechat_tool(app_control)

        self.assertIsInstance(tool, WeChatDesktopTool)
        self.assertIs(WeChatWindow, ModelWeChatWindow)
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

    def test_open_wechat_fails_when_focus_retry_has_no_window_title(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertIn("no focused window", result.message)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "focus_app", "observe", "accessibility_query"],
        )

    def test_open_wechat_uses_accessibility_window_when_observe_title_is_empty(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                _accessibility_query_response([], window_title="微信 (通讯录)"),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.open_wechat()

        self.assertTrue(result.success)
        self.assertEqual(result.observation["windowTitle"], "微信 (通讯录)")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "focus_app", "observe", "accessibility_query"],
        )

    def test_inspect_window_observes_accessibility_without_raw_by_default(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                _top_level_query_response(),
                _main_children_query_response(),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window()

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "inspect_window")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["root"]["kind"], "focusedWindow")
        self.assertEqual(app_control.commands[2].input["query"]["scope"], "children")
        self.assertEqual(app_control.commands[2].input["query"]["timeBudgetMs"], 10_000)
        self.assertIn(
            "AXDescription", app_control.commands[2].input["query"]["attributes"]
        )
        self.assertEqual(app_control.commands[3].input["root"]["kind"], "axPath")
        self.assertEqual(app_control.commands[3].input["root"]["axPath"], "0/11")
        self.assertEqual(result.observation["schema"], WECHAT_WINDOW_SCHEMA)
        self.assertEqual(result.observation["includeRaw"], False)
        self.assertNotIn("rawObservation", result.observation)
        self.assertNotIn("rawQueries", result.observation)
        window = result.observation["window"]
        self.assertEqual(window["appName"], "WeChat")
        self.assertEqual(
            window["bundleId"],
            "com.tencent.xinWeChat",
        )
        self.assertEqual(window["title"], "微信 (聊天)")
        self.assertEqual(
            window["snapshotId"],
            "frontmost:WeChat:微信 (聊天)",
        )
        self.assertEqual(window["element"]["axPath"], "0")
        self.assertEqual(window["element"]["role"], "AXWindow")
        self.assertEqual(window["activeSection"], "chats")
        self.assertEqual(
            [item["label"] for item in window["navigation"]],
            ["chats", "contacts", "favorites"],
        )
        self.assertEqual(window["navigation"][1]["id"], "nav.contacts")
        self.assertEqual(window["navigation"][1]["element"]["axPath"], "0/2")
        self.assertNotIn("attributeNames", window["element"])
        self.assertNotIn("attributeNames", window["navigation"][1]["element"])
        self.assertEqual(
            window["regions"]["searchBox"]["element"]["axPath"],
            "0/11/0",
        )
        self.assertEqual(
            window["regions"]["mainContent"]["element"]["axPath"],
            "0/11",
        )
        actionable_ids = {item["id"] for item in window["actionables"]}
        self.assertIn("nav.contacts.press", actionable_ids)
        self.assertIn("search.focus", actionable_ids)
        nav_contacts = next(
            item for item in window["actionables"] if item["id"] == "nav.contacts.press"
        )
        self.assertEqual(nav_contacts["actionRef"]["action"], "AXPress")
        self.assertIn("createdAt", nav_contacts["actionRef"])
        self.assertIn("expiresAt", nav_contacts["actionRef"])
        self.assertEqual(
            nav_contacts["actionRef"]["target"]["axPath"],
            "0/2",
        )
        available_actions = {item["id"]: item for item in window["availableActions"]}
        self.assertEqual(
            available_actions["wechat.open_contact"]["status"],
            "needs_input",
        )
        self.assertEqual(
            available_actions["wechat.list_contacts"]["operation"],
            "list_contacts",
        )
        self.assertEqual(result.observation["normalization"]["status"], "normalized")
        self.assertGreater(
            result.observation["normalization"]["availableActionCount"],
            0,
        )
        self.assertEqual(
            result.evidence["inspect_window"]["observation"]["accessibilityQuery"][
                "available"
            ],
            True,
        )

    def test_inspect_window_stops_when_wechat_has_no_focused_window(self) -> None:
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "frontmostBundleId": "com.tencent.xinWeChat",
                        "windowTitle": "",
                    }
                },
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_not_ready")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "focus_app", "observe", "accessibility_query"],
        )

    def test_inspect_window_can_include_raw_observation(self) -> None:
        tree = _wechat_window_tree_fixture()
        app_control = FakeAppControl(
            [
                {},
                _tree_children_query_response(tree, "0", include_raw=True),
                _tree_children_query_response(tree, "0/11", include_raw=True),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window(include_raw=True)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["includeRaw"], True)
        self.assertIn("rawQueries", result.observation)
        self.assertEqual(
            result.observation["rawQueries"]["topLevel"]["raw"],
            {"nodeCount": 4},
        )
        self.assertNotIn(
            "raw",
            result.evidence["inspect_window"]["observation"]["accessibilityQuery"],
        )

    def test_raw_tree_window_model_uses_action_refs_for_ui_actions(self) -> None:
        tree = _wechat_window_tree_fixture()
        observation = ToolObservation.ok(
            command_id="cmd_observe",
            tool="macos.computer_use",
            operation="observe",
            summary="Frontmost app: WeChat. Window: 微信 (聊天).",
            observation={
                "frontmostApp": "WeChat",
                "frontmostBundleId": "com.tencent.xinWeChat",
                "windowTitle": "微信 (聊天)",
                "snapshotId": "frontmost:WeChat:微信 (聊天)",
                "accessibility": {"focusedWindow": tree},
            },
        )

        window, normalization = build_wechat_window_model(
            WeChatDesktopConfig(),
            observation,
        )

        self.assertEqual(normalization["status"], "normalized")
        available_actions = {
            item["id"]: item for item in window.to_dict()["availableActions"]
        }
        nav_action = available_actions["ui.nav.contacts.press"]
        self.assertEqual(nav_action["operation"], "execute_action")
        self.assertEqual(nav_action["inputTemplate"]["actionRef"]["action"], "AXPress")
        self.assertIn("createdAt", nav_action["inputTemplate"]["actionRef"])
        self.assertIn("expiresAt", nav_action["inputTemplate"]["actionRef"])
        self.assertEqual(
            nav_action["inputTemplate"]["actionRef"]["target"]["axPath"],
            "0/2",
        )
        self.assertNotIn("coordinates", nav_action["inputTemplate"])

        row_action = available_actions["ui.conversation.0.open"]
        self.assertEqual(row_action["operation"], "execute_action")
        self.assertEqual(
            row_action["actionRef"]["kind"],
            "conversation.open",
        )
        self.assertNotIn("coordinates", row_action["inputTemplate"])

    def test_inspect_window_reports_action_guidance_when_tree_is_missing(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                {},
                _accessibility_query_response([], available=False),
            ]
        )
        tool = WeChatDesktopTool(app_control)

        result = tool.inspect_window()

        self.assertTrue(result.success)
        self.assertEqual(
            result.observation["normalization"]["reason"],
            "accessibility_query_missing",
        )
        window = result.observation["window"]
        self.assertEqual(window["actionables"], [])
        available_actions = {item["id"]: item for item in window["availableActions"]}
        self.assertEqual(
            available_actions["diagnostic.accessibility_query_missing"]["status"],
            "blocked",
        )
        self.assertIn(
            "Accessibility",
            available_actions["diagnostic.accessibility_query_missing"]["recoveryHint"],
        )
        self.assertEqual(
            available_actions["wechat.inspect_window.refresh"]["operation"],
            "inspect_window",
        )
        self.assertEqual(
            result.evidence["inspect_window"]["observation"]["accessibilityQuery"][
                "available"
            ],
            False,
        )

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

        self.assertEqual(
            [event.event_type for event in events],
            [
                ToolEventType.STARTED,
                ToolEventType.PROGRESS,
                ToolEventType.PROGRESS,
                ToolEventType.OBSERVATION,
            ],
        )
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
        app_control = FakeAppControl(_visible_open_contact_responses("File Transfer"))
        tool = WeChatDesktopTool(app_control)
        observer = RecordingObserver()

        result = tool.run_command(
            focus_contact_command("File Transfer", command_id="cmd_focus"),
            observer=observer,
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [event.event_type for event in observer.events],
            [
                ToolEventType.STARTED,
                ToolEventType.PROGRESS,
                ToolEventType.PROGRESS,
                ToolEventType.PROGRESS,
                ToolEventType.PROGRESS,
                ToolEventType.PROGRESS,
                ToolEventType.OBSERVATION,
            ],
        )
        self.assertEqual(
            [event.phase for event in observer.events[1:-1]],
            [
                "open_contact.open_wechat",
                "open_contact.verify_wechat_window",
                "open_contact.control_map_conversation_target_0",
                "open_contact.control_map_open_visible_contact",
                "open_contact.verify_contact",
            ],
        )
        self.assertEqual(
            [event.seq for event in observer.events],
            list(range(len(observer.events))),
        )
        self.assertEqual(
            observer.events[3].data["appControlObservation"]["operation"],
            "accessibility_query",
        )

    def test_from_config_uses_shared_wechat_config(self) -> None:
        app_control = FakeAppControl(
            _visible_open_contact_responses(
                "Ada",
                app_bundle_id="com.example.Weixin",
            )
        )
        config = AppControlConfig.from_dict(
            {
                "computer_use": {"backend": "direct"},
                "wechat": {
                    "app_name": "Weixin",
                    "bundle_id": "com.example.Weixin",
                    "app_control_tool": "custom.computer_use",
                    "selector_profile_path": "./profiles/wechat-local.toml",
                    "search_hotkey": ["Command", "K"],
                    "search_clear_hotkey": ["Command", "L"],
                    "clear_key": "Backspace",
                    "submit_key": "Enter",
                    "default_timeout_ms": 1234,
                    "max_message_chars": 5,
                },
            }
        )
        tool = WeChatDesktopTool.from_config(app_control, config)

        result = tool.focus_contact("Ada")

        self.assertTrue(result.success)
        self.assertEqual(tool.config.app_name, "Weixin")
        self.assertEqual(tool.config.bundle_id, "com.example.Weixin")
        self.assertEqual(tool.config.computer_use_backend, "direct")
        self.assertEqual(
            tool.config.selector_profile_path,
            "./profiles/wechat-local.toml",
        )
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
        self.assertEqual(app_control.commands[2].operation, "accessibility_query")
        self.assertEqual(
            app_control.commands[2].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(app_control.commands[3].operation, "accessibility_action")
        self.assertEqual(app_control.commands[4].operation, "accessibility_query")
        self.assertEqual(
            app_control.commands[4].input["bundleId"],
            "com.example.Weixin",
        )
        self.assertEqual(result.observation["bundleId"], "com.example.Weixin")

    def test_from_config_rejects_helper_backend_before_app_control(self) -> None:
        app_control = FakeAppControl()
        config = AppControlConfig.from_dict({"computer_use": {"backend": "helper"}})

        with self.assertRaisesRegex(
            ValueError,
            "computer_use.backend=helper",
        ):
            WeChatDesktopTool.from_config(app_control, config)

        self.assertEqual(app_control.commands, [])

    def test_direct_and_direct_backed_local_service_remain_constructible(
        self,
    ) -> None:
        config = AppControlConfig.from_dict({"computer_use": {"backend": "direct"}})
        clients = (
            FakeAppControl(),
            LocalServiceAppControl("/tmp/app-control-construction-test.sock"),
        )
        for client in clients:
            with self.subTest(client=type(client).__name__):
                tool = WeChatDesktopTool.from_config(client, config)

                self.assertEqual(tool.config.computer_use_backend, "direct")

    def test_package_boundary_has_no_product_or_backend_imports(self) -> None:
        package_dir = Path(__file__).parents[1] / "src" / "wechat_desktop_tool"
        allowed_selector_profile_import = package_dir / "profiles.py"
        lower_source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in package_dir.rglob("*.py")
        )

        for forbidden in (
            "taskweavn",
            "plato",
            "computer_use_macos.client",
            "computer_use_macos.service",
            "computer_use_macos.cli",
            "openai",
            "anthropic",
        ):
            self.assertNotIn(forbidden, lower_source)

        for path in package_dir.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "computer_use_macos" not in source:
                continue
            self.assertEqual(path, allowed_selector_profile_import)
            self.assertIn("computer_use_macos.selectors", source)


if __name__ == "__main__":
    unittest.main()
