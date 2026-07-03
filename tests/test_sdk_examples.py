from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
from typing import Any
from types import SimpleNamespace
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


class FakeFileTransferSendServiceClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self._queries = [
            _wechat_query(
                [
                    _query_node("0/1", "AXRadioButton", description="聊天", value=1),
                    _query_node("0/2", "AXRadioButton", description="通讯录", value=0),
                    _query_node("0/3", "AXRadioButton", description="收藏", value=0),
                    _query_node("0/11", "AXSplitGroup", description="main"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/11/0", "AXTextArea", description="搜索"),
                    _query_node("0/11/1", "AXScrollArea"),
                ]
            ),
            _wechat_query(
                [
                    _query_node(
                        "0/11/search/0",
                        "AXRow",
                        description="文件传输助手",
                    )
                ]
            ),
            _wechat_query(
                [
                    _query_node(
                        "0/11/4/2",
                        "AXStaticText",
                        value="文件传输助手",
                    )
                ]
            ),
        ]

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
        if operation == "observe":
            observation_payload = {
                "frontmostApp": "WeChat",
                "frontmostBundleId": "com.tencent.xinWeChat",
                "windowTitle": "微信 (聊天)",
            }
        elif operation == "accessibility_query":
            observation_payload = {"accessibilityQuery": self._queries.pop(0)}
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


class FakeContactsRecentMessagesServiceClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self._queries = [
            _wechat_query(
                [
                    _query_node("0/1", "AXRadioButton", description="聊天", value=1),
                    _query_node("0/2", "AXRadioButton", description="通讯录", value=0),
                    _query_node("0/3", "AXRadioButton", description="收藏", value=0),
                    _query_node("0/11", "AXSplitGroup", description="main"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/1", "AXRadioButton", description="聊天", value=0),
                    _query_node("0/2", "AXRadioButton", description="通讯录", value=1),
                    _query_node("0/3", "AXRadioButton", description="收藏", value=0),
                    _query_node("0/11", "AXSplitGroup", description="main"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/11/1/0/0", "AXRow", description="Ada"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/1", "AXRadioButton", description="聊天", value=0),
                    _query_node("0/2", "AXRadioButton", description="通讯录", value=1),
                    _query_node("0/3", "AXRadioButton", description="收藏", value=0),
                    _query_node("0/11", "AXSplitGroup", description="main"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/11/0", "AXTextArea", description="搜索"),
                    _query_node("0/11/1", "AXScrollArea"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/11/search/0", "AXRow", description="Ada"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/11/4/2", "AXStaticText", value="Ada"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/1", "AXRadioButton", description="聊天", value=1),
                    _query_node("0/2", "AXRadioButton", description="通讯录", value=0),
                    _query_node("0/3", "AXRadioButton", description="收藏", value=0),
                    _query_node("0/11", "AXSplitGroup", description="main"),
                ]
            ),
            _wechat_query(
                [
                    _query_node("0/11/4/2", "AXStaticText", value="Ada"),
                    _query_node("0/11/4/0/0/0", "AXRow", description="hello"),
                    _query_node("0/11/4/0/0/1", "AXRow", description="reply"),
                ]
            ),
        ]

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
        if operation == "observe":
            observation_payload = {
                "frontmostApp": "WeChat",
                "frontmostBundleId": "com.tencent.xinWeChat",
                "windowTitle": "微信 (聊天)",
            }
        elif operation == "accessibility_query":
            observation_payload = {"accessibilityQuery": self._queries.pop(0)}
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


class FakeContactsOpenFailureServiceClient:
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
        if operation == "observe":
            observation_payload = {
                "frontmostApp": "Codex",
                "frontmostBundleId": "com.openai.codex",
                "windowTitle": "",
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


class FakeSystemOpenRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> Any:
        del kwargs
        self.commands.append(list(command))
        return SimpleNamespace(returncode=0, stdout="", stderr="")


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

    def test_wechat_file_transfer_send_test_runs_through_service_adapter(self) -> None:
        module = _load_wechat_file_transfer_send_test_module()
        service_client = FakeFileTransferSendServiceClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "send-output.json"
            payload = module.run_file_transfer_send_test(
                config_path=None,
                output_path=output_path,
                socket_path="/tmp/app-control.sock",
                service_client=service_client,
                message="hello",
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["success"], True)
        self.assertEqual(payload["summary"]["submitted"], True)
        self.assertEqual(payload["summary"]["contact"], "文件传输助手")
        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            [
                "readiness",
                "open_app",
                "observe",
                "open_app",
                "accessibility_query",
                "accessibility_query",
                "accessibility_action",
                "type_text",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )
        self.assertEqual(
            service_client.commands[7]["input"]["text"],
            "文件传输助手",
        )
        self.assertEqual(service_client.commands[11]["input"]["text"], "hello")
        self.assertEqual(persisted["submitDraft"]["operation"], "submit_draft")

    def test_wechat_contacts_recent_messages_test_reads_listed_contacts(self) -> None:
        module = _load_wechat_contacts_recent_messages_test_module()
        service_client = FakeContactsRecentMessagesServiceClient()
        system_open = FakeSystemOpenRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts-output.json"
            payload = module.run_contacts_recent_messages_test(
                config_path=None,
                output_path=output_path,
                socket_path="/tmp/app-control.sock",
                service_client=service_client,
                system_open_runner=system_open,
                max_contacts=1,
                message_limit=30,
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["success"], True)
        self.assertEqual(payload["summary"]["listedContactCount"], 1)
        self.assertEqual(payload["summary"]["processedContactCount"], 1)
        self.assertEqual(payload["systemOpenWeChat"]["success"], True)
        self.assertEqual([command[:2] for command in system_open.commands], [["open", "-b"], ["osascript", "-e"]])
        self.assertEqual(payload["contacts"][0]["contact"], "Ada")
        self.assertEqual(payload["contacts"][0]["messageCount"], 2)
        self.assertEqual(
            payload["contacts"][0]["readContactMessages"]["operation"],
            "read_contact_messages",
        )
        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            [
                "readiness",
                "open_app",
                "observe",
                "open_app",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "accessibility_query",
                "open_app",
                "accessibility_query",
                "accessibility_query",
                "accessibility_action",
                "type_text",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "open_app",
                "accessibility_query",
                "accessibility_query",
            ],
        )
        self.assertEqual(service_client.commands[12]["input"]["text"], "Ada")
        self.assertEqual(persisted["summary"]["messageLimit"], 30)

    def test_wechat_contacts_recent_messages_reports_open_failure(self) -> None:
        module = _load_wechat_contacts_recent_messages_test_module()
        service_client = FakeContactsOpenFailureServiceClient()
        system_open = FakeSystemOpenRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts-output.json"
            payload = module.run_contacts_recent_messages_test(
                config_path=None,
                output_path=output_path,
                socket_path="/tmp/app-control.sock",
                service_client=service_client,
                system_open_runner=system_open,
                max_contacts=1,
                message_limit=30,
            )

        self.assertEqual(payload["summary"]["success"], False)
        self.assertEqual(payload["summary"]["failedStep"], "openWeChat")
        self.assertEqual(payload["listContacts"]["failureKind"], "open_wechat_failed")
        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            ["readiness", "open_app", "observe"],
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
    return _load_example_module(example_path, "wechat_window_sdk_test")


def _load_wechat_file_transfer_send_test_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_file_transfer_send_test.py"
    return _load_example_module(example_path, "wechat_file_transfer_send_test")


def _load_wechat_contacts_recent_messages_test_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_contacts_recent_messages_test.py"
    return _load_example_module(example_path, "wechat_contacts_recent_messages_test")


def _load_example_module(example_path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        name,
        example_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wechat_query(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "macos.accessibility.query.v1",
        "available": True,
        "snapshotId": "frontmost:WeChat:微信 (聊天)",
        "app": {
            "name": "WeChat",
            "bundleId": "com.tencent.xinWeChat",
        },
        "window": {
            "title": "微信 (聊天)",
            "role": "AXWindow",
        },
        "nodes": nodes,
        "diagnostics": {
            "returnedNodes": len(nodes),
            "truncated": False,
        },
    }


def _query_node(
    ax_path: str,
    role: str,
    *,
    description: str | None = None,
    value: object | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "axPath": ax_path,
        "role": role,
        "frame": {"x": 100, "y": 100, "width": 120, "height": 30},
        "childrenCount": 0,
    }
    if description is not None:
        payload["description"] = description
    if value is not None:
        payload["value"] = value
    if role in {"AXRadioButton", "AXRow", "AXTextArea"}:
        payload["actions"] = ["AXPress"]
    return payload
