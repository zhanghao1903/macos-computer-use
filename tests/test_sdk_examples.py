from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
from typing import Any
import unittest

from app_control_protocol import ServiceResponse, ToolObservation


class FakeUnixSocketServiceClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def run_command(
        self,
        command: dict[str, Any],
        *,
        action: str = "run",
        request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        del action
        self.commands.append(command)
        operation = command["operation"]
        observation_payload: dict[str, Any] = {}
        if operation == "accessibility_query":
            observation_payload = {
                "accessibilityQuery": {
                    "schema": "macos.accessibility.query.v1",
                    "available": False,
                    "snapshotId": "frontmost:WeChat:微信 (聊天)",
                    "app": {
                        "name": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                    },
                    "window": {
                        "title": "微信 (聊天)",
                        "role": "AXWindow",
                    },
                    "nodes": [],
                    "diagnostics": {
                        "returnedNodes": 0,
                        "truncated": False,
                    },
                },
            }
        observation = ToolObservation.ok(
            command_id=command["commandId"],
            tool=command["tool"],
            operation=operation,
            summary=f"fake {operation}",
            observation=observation_payload,
        )
        return [
            ServiceResponse.complete(
                observation,
                request_id=request_id or "fake_request",
            ).to_dict()
        ]


class SdkExampleTests(unittest.TestCase):
    def test_wechat_window_sdk_test_runs_through_service_adapter(self) -> None:
        module = _load_wechat_window_sdk_test_module()
        service_client = FakeUnixSocketServiceClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "sdk-output.json"
            payload = module.run_sdk_test(
                config_path=None,
                output_path=output_path,
                socket_path="/tmp/app-control.sock",
                service_client=service_client,
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            ["readiness", "open_app", "accessibility_query"],
        )
        self.assertEqual(payload["summary"]["success"], True)
        self.assertEqual(
            payload["summary"]["normalization"]["reason"],
            "accessibility_query_missing",
        )
        self.assertEqual(payload["summary"]["availableActionCount"], 6)
        self.assertEqual(
            persisted["inspectWindow"]["operation"],
            "inspect_window",
        )
        self.assertEqual(
            module._exit_code(payload, allow_missing_tree=True),
            0,
        )
        self.assertEqual(
            module._exit_code(payload, allow_missing_tree=False),
            3,
        )

    def test_wechat_window_sdk_test_rejects_missing_token_file(self) -> None:
        module = _load_wechat_window_sdk_test_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_token = Path(tmpdir) / "missing.token"
            args = module._parser().parse_args(
                [
                    "--config",
                    str(Path(tmpdir) / "missing.toml"),
                    "--token-file",
                    str(missing_token),
                ]
            )

            with self.assertRaisesRegex(ValueError, "token file does not exist"):
                module._service_settings(args)


def _load_wechat_window_sdk_test_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_window_sdk_test.py"
    spec = importlib.util.spec_from_file_location(
        "wechat_window_sdk_test",
        example_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
