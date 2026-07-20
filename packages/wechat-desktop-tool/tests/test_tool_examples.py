from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    FakeAppControl,
    Path,
    StringIO,
    WECHAT_WINDOW_SCHEMA,
    _load_wechat_smoke_module,
    _load_wechat_window_inspect_module,
    _main_children_query_response,
    _pythonpath,
    _top_level_query_response,
    _visible_open_contact_responses,
    cli_main,
    cli_module,
    json,
    os,
    redirect_stderr,
    redirect_stdout,
    subprocess,
    sys,
    tempfile,
)


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
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
            ],
        )

    def test_examples_send_message_live_default_does_not_auto_select_contact(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "微信 (聊天)",
                    }
                },
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["submitted"], False)
        self.assertEqual(payload["focus"]["failureKind"], "contact_not_focused")
        self.assertFalse(payload["draft"]["success"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe"],
        )

    def test_examples_send_message_live_allows_selector_backed_focus_select(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(_visible_open_contact_responses("Ada") + [{}, {}])
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--allow-focus-select",
                        "--submit",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
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
        self.assertEqual(
            app_control.commands[2].input["query"]["match"]["descriptionContains"],
            "Ada,",
        )

    def test_examples_send_message_ignores_legacy_search_hotkey_for_visible_contact(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(_visible_open_contact_responses("Ada") + [{}, {}])
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                '[wechat]\nsearch_hotkey = ["Command", "F"]\n',
                encoding="utf-8",
            )
            try:
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "examples",
                            "send-message",
                            "--contact",
                            "Ada",
                            "--message",
                            "hello",
                            "--socket-path",
                            "/tmp/app-control.sock",
                            "--config",
                            str(config_path),
                            "--allow-focus-select",
                            "--submit",
                        ]
                    )
            finally:
                cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
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

    def test_examples_send_message_live_default_drafts_current_chat(self) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "Ada - WeChat",
                    }
                },
                {},
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertTrue(payload["focus"]["success"])
        self.assertEqual(payload["focus"]["observation"]["autoSelectContact"], False)
        self.assertTrue(payload["draft"]["success"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "type_text"],
        )

    def test_examples_send_message_live_can_assume_current_chat(self) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "微信 (聊天)",
                    }
                },
                {},
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--assume-current-chat",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["submitted"], False)
        self.assertTrue(payload["focus"]["success"])
        self.assertEqual(payload["focus"]["observation"]["assumedCurrentChat"], True)
        self.assertEqual(payload["focus"]["observation"]["autoSelectContact"], False)
        self.assertTrue(payload["draft"]["success"])
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "type_text"],
        )

    def test_examples_send_message_live_submit_wraps_current_chat_result(
        self,
    ) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                {
                    "observation": {
                        "frontmostApp": "WeChat",
                        "windowTitle": "Ada - WeChat",
                    }
                },
                {},
                {},
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with redirect_stdout(stdout):
                exit_code = cli_module.main(
                    [
                        "examples",
                        "send-message",
                        "--contact",
                        "Ada",
                        "--message",
                        "hello",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--submit",
                    ]
                )
        finally:
            cli_module._app_control_for_args = original

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["result"]["operation"], "send_message")
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
        self.assertEqual(
            payload["result"]["observation"]["autoSelectContact"],
            False,
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "type_text", "press_key"],
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
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )

    def test_examples_inspect_window_writes_output_file(self) -> None:
        stdout = StringIO()
        app_control = FakeAppControl(
            [
                {},
                _top_level_query_response(),
                _main_children_query_response(),
            ]
        )
        original = cli_module._app_control_for_args
        cli_module._app_control_for_args = lambda args, parser: app_control

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "wechat-window.json"
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "examples",
                            "inspect-window",
                            "--socket-path",
                            "/tmp/app-control.sock",
                            "--output",
                            str(output_path),
                        ]
                    )
                payload = json.loads(output_path.read_text(encoding="utf-8"))
        finally:
            cli_module._app_control_for_args = original

        status = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(status["output"], str(output_path))
        self.assertEqual(status["success"], True)
        self.assertEqual(payload["result"]["operation"], "inspect_window")
        self.assertEqual(
            payload["result"]["observation"]["schema"],
            WECHAT_WINDOW_SCHEMA,
        )
        self.assertEqual(
            payload["result"]["observation"]["window"]["navigation"][1]["label"],
            "contacts",
        )
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["open_app", "observe", "accessibility_query", "accessibility_query"],
        )
        self.assertEqual(app_control.commands[2].input["query"]["scope"], "children")


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
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
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
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )

    def test_smoke_script_dry_run_can_switch_contact_and_submit(self) -> None:
        module = _load_wechat_smoke_module()
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONTACT": "Ada",
                    "WECHAT_TOOL_MESSAGE": "hello",
                    "WECHAT_TOOL_DRY_RUN": "1",
                    "WECHAT_TOOL_ALLOW_SEND": "1",
                    "WECHAT_TOOL_ALLOW_FOCUS_SELECT": "1",
                }
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["result"]["success"])
        self.assertEqual(payload["result"]["observation"]["focusedContact"], "Ada")
        self.assertEqual(payload["result"]["observation"]["submitted"], True)
        self.assertEqual(
            [command["operation"] for command in payload["appControlCommands"]],
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
        self.assertEqual(
            payload["appControlCommands"][2]["input"]["query"]["match"][
                "descriptionContains"
            ],
            "Ada,",
        )
        self.assertEqual(payload["appControlCommands"][5]["input"]["text"], "hello")
        self.assertEqual(payload["appControlCommands"][6]["input"]["key"], "Return")

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

    def test_smoke_script_accepts_allow_focus_select_opt_in(self) -> None:
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
                    "WECHAT_TOOL_ALLOW_FOCUS_SELECT": "1",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertIn("--allow-focus-select", captured[0])

    def test_smoke_script_accepts_switch_contact_submit_opt_in(self) -> None:
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
                    "WECHAT_TOOL_ALLOW_SEND": "1",
                    "WECHAT_TOOL_ALLOW_FOCUS_SELECT": "1",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertIn("--submit", captured[0])
        self.assertIn("--allow-focus-select", captured[0])

    def test_smoke_script_accepts_assume_current_chat_opt_in(self) -> None:
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
                    "WECHAT_TOOL_ASSUME_CURRENT_CHAT": "1",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertIn("--assume-current-chat", captured[0])

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

    def test_window_inspect_script_accepts_config_and_output(self) -> None:
        module = _load_wechat_window_inspect_module()
        captured: list[list[str]] = []
        original_cli_main = module.wechat_cli_main
        module.wechat_cli_main = lambda argv: captured.append(list(argv)) or 0

        try:
            exit_code = module.main(
                {
                    "WECHAT_TOOL_CONFIG": "./app-control.toml",
                    "WECHAT_TOOL_OUTPUT": "./wechat-window.json",
                    "WECHAT_TOOL_INCLUDE_RAW": "1",
                    "WECHAT_TOOL_INCLUDE_ACTIONABLES": "0",
                }
            )
        finally:
            module.wechat_cli_main = original_cli_main

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            captured[0],
            [
                "examples",
                "inspect-window",
                "--output",
                "./wechat-window.json",
                "--config",
                "./app-control.toml",
                "--include-raw",
                "--no-actionables",
            ],
        )

    def test_window_inspect_script_requires_socket_unless_dry_run(self) -> None:
        module = _load_wechat_window_inspect_module()
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = module.main({"WECHAT_TOOL_OUTPUT": "./wechat-window.json"})

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "WECHAT_TOOL_SOCKET_PATH or WECHAT_TOOL_CONFIG is required",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
