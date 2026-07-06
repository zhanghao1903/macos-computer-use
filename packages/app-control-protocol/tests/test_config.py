from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from app_control_protocol import AppControlConfig, load_app_control_config


class AppControlConfigTests(unittest.TestCase):
    def test_repository_example_config_loads(self) -> None:
        config_path = (
            Path(__file__).resolve().parents[3] / "examples" / "app-control.toml"
        )

        config = load_app_control_config(config_path, env={})

        self.assertEqual(config.logging.level, "info")
        self.assertEqual(config.computer_use.allowed_apps, ("TextEdit", "WeChat"))
        self.assertEqual(
            config.computer_use.allowed_app_bundle_ids,
            {
                "TextEdit": "com.apple.TextEdit",
                "WeChat": "com.tencent.xinWeChat",
            },
        )
        self.assertEqual(config.helper.allowed_apps, ("TextEdit", "WeChat"))
        self.assertEqual(config.wechat.app_control_tool, "macos.computer_use")

    def test_default_config_is_developer_editable_shape(self) -> None:
        config = AppControlConfig()

        self.assertEqual(config.logging.level, "info")
        self.assertTrue(config.logging.redact_text)
        self.assertIsNone(config.logging.raw_data_log_path)
        self.assertEqual(config.computer_use.backend, "direct")
        self.assertEqual(config.computer_use.allowed_app_bundle_ids, {})
        self.assertEqual(config.computer_use.allowed_app_identities(), {})
        self.assertEqual(config.helper.transport, "unix_socket")
        self.assertEqual(config.helper.allowed_apps, ())
        self.assertEqual(config.wechat.app_name, "WeChat")
        self.assertEqual(config.wechat.app_control_tool, "macos.computer_use")
        self.assertEqual(config.wechat.search_hotkey, ("Command", "K"))
        self.assertEqual(config.wechat.search_clear_hotkey, ("Command", "A"))
        self.assertEqual(config.wechat.clear_key, "Delete")
        self.assertEqual(config.wechat.submit_key, "Return")

    def test_config_from_dict_parses_sections(self) -> None:
        config = AppControlConfig.from_dict(
            {
                "logging": {
                    "level": "debug",
                    "json": True,
                    "raw_data_log_path": "./app-control-rawdata.jsonl",
                },
                "computer_use": {
                    "backend": "helper",
                    "allowed_apps": ["WeChat", "TextEdit"],
                    "allowed_app_bundle_ids": {
                        "WeChat": "com.tencent.xinWeChat",
                        "TextEdit": "com.apple.TextEdit",
                    },
                    "timeout_ms": 20_000,
                },
                "helper": {
                    "auto_launch": True,
                    "allowed_apps": ["WeChat"],
                    "manifest_path": "~/helper.json",
                },
                "wechat": {
                    "app_name": "WeChat",
                    "app_control_tool": "custom.computer_use",
                    "search_hotkey": ["Command", "K"],
                    "search_clear_hotkey": ["Command", "L"],
                    "clear_key": "Backspace",
                    "submit_key": "Enter",
                    "max_message_chars": 100,
                },
            }
        )

        self.assertEqual(config.logging.level, "debug")
        self.assertTrue(config.logging.json)
        self.assertEqual(
            config.logging.raw_data_log_path,
            "./app-control-rawdata.jsonl",
        )
        self.assertEqual(config.computer_use.backend, "helper")
        self.assertEqual(config.computer_use.allowed_apps, ("WeChat", "TextEdit"))
        self.assertEqual(
            config.computer_use.allowed_app_bundle_ids,
            {
                "WeChat": "com.tencent.xinWeChat",
                "TextEdit": "com.apple.TextEdit",
            },
        )
        self.assertEqual(
            config.computer_use.allowed_app_identities(),
            {
                "WeChat": "com.tencent.xinWeChat",
                "TextEdit": "com.apple.TextEdit",
            },
        )
        self.assertTrue(config.helper.auto_launch)
        self.assertEqual(config.helper.allowed_apps, ("WeChat",))
        self.assertEqual(config.helper.manifest_path, "~/helper.json")
        self.assertEqual(config.wechat.app_control_tool, "custom.computer_use")
        self.assertEqual(config.wechat.search_hotkey, ("Command", "K"))
        self.assertEqual(config.wechat.search_clear_hotkey, ("Command", "L"))
        self.assertEqual(config.wechat.clear_key, "Backspace")
        self.assertEqual(config.wechat.submit_key, "Enter")
        self.assertEqual(config.wechat.max_message_chars, 100)

    def test_load_config_from_toml_and_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[logging]",
                        'level = "warning"',
                        "",
                        "[computer_use]",
                        'backend = "direct"',
                        'allowed_apps = ["TextEdit"]',
                    ]
                ),
                encoding="utf-8",
            )

            config = load_app_control_config(
                config_path,
                env={
                    "APP_CONTROL_LOG_LEVEL": "error",
                    "APP_CONTROL_ALLOWED_APPS": "WeChat, TextEdit",
                    "APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS": (
                        "WeChat=com.tencent.xinWeChat,"
                        " TextEdit=com.apple.TextEdit"
                    ),
                    "APP_CONTROL_HELPER_ALLOWED_APPS": "TextEdit",
                    "APP_CONTROL_HELPER_AUTO_LAUNCH": "true",
                    "APP_CONTROL_WECHAT_APP_NAME": "WeChat",
                    "APP_CONTROL_WECHAT_SEARCH_HOTKEY": "Command, K",
                    "APP_CONTROL_WECHAT_SEARCH_CLEAR_HOTKEY": "Command, L",
                    "APP_CONTROL_WECHAT_CLEAR_KEY": "Backspace",
                    "APP_CONTROL_WECHAT_SUBMIT_KEY": "Enter",
                },
            )

        self.assertEqual(config.logging.level, "error")
        self.assertEqual(config.computer_use.allowed_apps, ("WeChat", "TextEdit"))
        self.assertEqual(
            config.computer_use.allowed_app_bundle_ids,
            {
                "WeChat": "com.tencent.xinWeChat",
                "TextEdit": "com.apple.TextEdit",
            },
        )
        self.assertEqual(config.helper.allowed_apps, ("TextEdit",))
        self.assertTrue(config.helper.auto_launch)
        self.assertEqual(config.wechat.app_name, "WeChat")
        self.assertEqual(config.wechat.search_hotkey, ("Command", "K"))
        self.assertEqual(config.wechat.search_clear_hotkey, ("Command", "L"))
        self.assertEqual(config.wechat.clear_key, "Backspace")
        self.assertEqual(config.wechat.submit_key, "Enter")

    def test_env_overrides_cover_runtime_config_fields(self) -> None:
        config = load_app_control_config(
            None,
            env={
                "APP_CONTROL_LOG_JSON": "true",
                "APP_CONTROL_LOG_EVENT_SINK": "stdout",
                "APP_CONTROL_LOG_RAW_DATA_PATH": "/tmp/app-control-rawdata.jsonl",
                "APP_CONTROL_COMPUTER_USE_BACKEND": "helper",
                "APP_CONTROL_COMPUTER_USE_ALLOWED_APPS": "TextEdit, WeChat",
                "APP_CONTROL_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS": (
                    "TextEdit=com.apple.TextEdit,WeChat=com.tencent.xinWeChat"
                ),
                "APP_CONTROL_COMPUTER_USE_ALLOW_COORDINATE_CLICK": "true",
                "APP_CONTROL_COMPUTER_USE_SCREEN_RECORDING_REQUIRED": "true",
                "APP_CONTROL_COMPUTER_USE_TIMEOUT_MS": "2500",
                "APP_CONTROL_HELPER_TRANSPORT": "unix_socket",
                "APP_CONTROL_HELPER_APP_PATH": "/Applications/Helper.app",
                "APP_CONTROL_HELPER_BUNDLE_ID": "com.example.helper",
                "APP_CONTROL_HELPER_ENDPOINT": "/tmp/helper.sock",
                "APP_CONTROL_HELPER_TOKEN": "local-token",
                "APP_CONTROL_HELPER_LAUNCH_TIMEOUT_MS": "120000",
                "APP_CONTROL_WECHAT_BUNDLE_ID": "com.tencent.xinWeChat",
                "APP_CONTROL_WECHAT_APP_CONTROL_TOOL": "custom.computer_use",
                "APP_CONTROL_WECHAT_MAX_MESSAGE_CHARS": "42",
                "APP_CONTROL_WECHAT_DEFAULT_TIMEOUT_MS": "1234",
            },
        )

        self.assertTrue(config.logging.json)
        self.assertEqual(config.logging.event_sink, "stdout")
        self.assertEqual(
            config.logging.raw_data_log_path,
            "/tmp/app-control-rawdata.jsonl",
        )
        self.assertEqual(config.computer_use.backend, "helper")
        self.assertEqual(config.computer_use.allowed_apps, ("TextEdit", "WeChat"))
        self.assertEqual(
            config.computer_use.allowed_app_bundle_ids,
            {
                "TextEdit": "com.apple.TextEdit",
                "WeChat": "com.tencent.xinWeChat",
            },
        )
        self.assertTrue(config.computer_use.allow_coordinate_click)
        self.assertTrue(config.computer_use.screen_recording_required)
        self.assertEqual(config.computer_use.timeout_ms, 2500)
        self.assertEqual(config.helper.helper_app_path, "/Applications/Helper.app")
        self.assertEqual(config.helper.bundle_id, "com.example.helper")
        self.assertEqual(config.helper.endpoint, "/tmp/helper.sock")
        self.assertEqual(config.helper.token, "local-token")
        self.assertEqual(config.helper.launch_timeout_ms, 120000)
        self.assertEqual(config.wechat.bundle_id, "com.tencent.xinWeChat")
        self.assertEqual(config.wechat.app_control_tool, "custom.computer_use")
        self.assertEqual(config.wechat.max_message_chars, 42)
        self.assertEqual(config.wechat.default_timeout_ms, 1234)

    def test_invalid_log_level_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AppControlConfig.from_dict({"logging": {"level": "verbose"}})

    def test_invalid_integer_env_override_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_app_control_config(
                None,
                env={"APP_CONTROL_COMPUTER_USE_TIMEOUT_MS": "slow"},
            )


if __name__ == "__main__":
    unittest.main()
