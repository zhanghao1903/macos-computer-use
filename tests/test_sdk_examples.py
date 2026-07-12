from __future__ import annotations

import importlib.util
from contextlib import redirect_stdout
from io import StringIO
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
        if operation == "observe":
            observation_payload = {
                "frontmostApp": "WeChat",
                "frontmostBundleId": "com.tencent.xinWeChat",
                "windowTitle": "微信 (聊天)",
            }
        elif operation == "accessibility_query":
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
                    _query_node("0/11/1/0/0", "AXRow", description="文件传输助手")
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


class FakeContactsListServiceClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.section = "chats"

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
            observation_payload = {"accessibilityQuery": self._query(command)}
        elif operation == "accessibility_action":
            target = command.get("input", {}).get("target", {})
            ax_path = target.get("axPath") if isinstance(target, dict) else None
            if ax_path == "0/2":
                self.section = "contacts"
            observation_payload = {"executed": True}
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

    def _query(self, command: dict[str, Any]) -> dict[str, Any]:
        input_payload = command.get("input", {})
        query = input_payload.get("query", {})
        root = input_payload.get("root", {})
        role_in = (
            query.get("match", {}).get("roleIn")
            if isinstance(query, dict)
            else None
        )
        root_path = root.get("axPath") if isinstance(root, dict) else None
        if root_path == "0/2" and role_in == ["AXRadioButton"]:
            return _wechat_query(
                [
                    _query_node(
                        "0/2",
                        "AXRadioButton",
                        description="通讯录",
                        value=1 if self.section == "contacts" else 0,
                    )
                ]
            )
        if root_path == "0/12/2/0" and role_in == ["AXStaticText"]:
            return _wechat_query(
                [
                    _query_node(
                        "0/12/2/0/0/0/1",
                        "AXStaticText",
                        value="Ada",
                    ),
                    _query_node(
                        "0/12/2/0/1/0/1",
                        "AXStaticText",
                        value="Bob",
                    ),
                ]
            )
        return _wechat_query([])


class FakeContactsRecentMessagesServiceClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.current_chat = "其他会话"

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
            observation_payload = {"accessibilityQuery": self._query(command)}
        elif operation == "accessibility_action":
            target = command.get("input", {}).get("target", {})
            ax_path = target.get("axPath") if isinstance(target, dict) else None
            if ax_path == "0/12/1/0/0":
                self.current_chat = "文件传输助手"
            observation_payload = {"executed": True}
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

    def _query(self, command: dict[str, Any]) -> dict[str, Any]:
        input_payload = command.get("input", {})
        query = input_payload.get("query", {})
        root = input_payload.get("root", {})
        role_in = (
            query.get("match", {}).get("roleIn")
            if isinstance(query, dict)
            else None
        )
        root_path = root.get("axPath") if isinstance(root, dict) else None
        if (
            root_path == "0/12/1/0"
            and isinstance(role_in, list)
            and ("AXRow" in role_in or "AXCell" in role_in)
        ):
            return _wechat_query(
                [
                    _query_node(
                        "0/12/1/0/0",
                        "AXRow",
                        description="文件传输助手,hello,09:00,置顶",
                        height=68,
                    )
                ]
            )
        if root_path == "0/12/4" and role_in == ["AXStaticText"]:
            return _wechat_query(
                [_query_node("0/12/4/2", "AXStaticText", value=self.current_chat)]
            )
        if (
            root_path == "0/12/4/0/0"
            and isinstance(role_in, list)
            and "AXRow" in role_in
        ):
            return _wechat_query(
                [
                    _query_node("0/12/4/0/0/0", "AXRow", description="hello"),
                    _query_node("0/12/4/0/0/1", "AXRow", description="reply"),
                ]
            )
        return _wechat_query([])


class FakeSelectorEngineSmokeServiceClient:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
        self.section = "chats"
        self.current_chat = "文件传输助手"

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
                "windowTitle": f"{self.current_chat} - 微信",
            }
        elif operation == "accessibility_query":
            observation_payload = {"accessibilityQuery": self._query(command)}
        elif operation == "accessibility_action":
            target = command.get("input", {}).get("target", {})
            ax_path = target.get("axPath") if isinstance(target, dict) else None
            if ax_path == "0/1":
                self.section = "chats"
            elif ax_path == "0/2":
                self.section = "contacts"
            elif ax_path in {"0/12/1/0/0", "0/11/1/0/0"}:
                self.current_chat = "文件传输助手"
                self.section = "chats"
            observation_payload = {"executed": True}
        elif operation == "click":
            coordinates = command.get("input", {}).get("coordinates")
            if coordinates == {"x": 264, "y": 227}:
                self.section = "contacts"
            elif coordinates == {"x": 264, "y": 179}:
                self.section = "chats"
            observation_payload = {"clicked": True}
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

    def _query(self, command: dict[str, Any]) -> dict[str, Any]:
        input_payload = command.get("input", {})
        query = input_payload.get("query", {})
        root = input_payload.get("root", {})
        role_in = (
            query.get("match", {}).get("roleIn")
            if isinstance(query, dict)
            else None
        )
        root_path = root.get("axPath") if isinstance(root, dict) else None
        max_depth = query.get("maxDepth") if isinstance(query, dict) else None
        scope = query.get("scope") if isinstance(query, dict) else None

        if root_path in {"0/1", "0/2"} and role_in == ["AXRadioButton"]:
            label = "聊天" if root_path == "0/1" else "通讯录"
            navigation = "chats" if root_path == "0/1" else "contacts"
            return _wechat_query(
                [
                    _query_node(
                        root_path,
                        "AXRadioButton",
                        description=label,
                        value=1 if self.section == navigation else 0,
                    )
                ]
            )
        if role_in == ["AXRadioButton"]:
            return _wechat_query(self._navigation_nodes())
        if root_path == "0/12/2/0" and role_in == ["AXStaticText"]:
            return _wechat_query(self._contact_text_nodes(root_path))
        if (
            root_path in {"0/12/1/0", "0/11/1/0", "0/12/2/0"}
            and isinstance(role_in, list)
            and ("AXRow" in role_in or "AXCell" in role_in)
        ):
            return _wechat_query(self._row_nodes(root_path))
        if role_in == ["AXSplitGroup"] and root_path in {"0/12", "0/11"}:
            main_root = root_path
            return _wechat_query(
                [
                    _query_node(
                        f"{main_root}/4",
                        "AXSplitGroup",
                        description="chat-panel",
                    )
                ]
            )
        if role_in == ["AXSplitGroup"]:
            return _wechat_query(
                [_query_node("0/11", "AXSplitGroup", description="main")]
            )
        if root_path == "0/11" and role_in == ["AXRow"]:
            return _wechat_query(self._row_nodes(root_path))
        if root_path in {"0/11/1/0/0", "0/11/1/0/1"}:
            return _wechat_query(self._field_nodes(root_path))
        if (
            root_path in {
                "0/12/4",
                "0/12/4/0/0",
                "0/11/4",
                "0/11/4/0/0",
            }
            and isinstance(role_in, list)
            and "AXRow" in role_in
        ):
            message_root = (
                "0/12/4/0/0"
                if root_path.startswith("0/12")
                else "0/11/4/0/0"
            )
            return _wechat_query(
                [
                    _query_node(f"{message_root}/0", "AXRow", description="hello"),
                    _query_node(f"{message_root}/1", "AXRow", description="reply"),
                ]
            )
        if root_path in {
            "0/12/4/0/0/0",
            "0/12/4/0/0/1",
            "0/11/4/0/0/0",
            "0/11/4/0/0/1",
        }:
            text = "hello" if root_path.endswith("/0") else "reply"
            return _wechat_query(
                [_query_node(f"{root_path}/0", "AXStaticText", value=text)]
            )
        if root_path in {"0/12", "0/12/4", "0/11", "0/11/4"} and role_in == [
            "AXStaticText"
        ]:
            main_root = "0/12" if root_path.startswith("0/12") else "0/11"
            return _wechat_query(
                [
                    _query_node(
                        f"{main_root}/4/2",
                        "AXStaticText",
                        value=self.current_chat,
                    )
                ]
            )
        if root_path == "0/11" and role_in == ["AXRow", "AXCell", "AXStaticText"]:
            return _wechat_query(self._visible_contact_nodes())
        if scope == "children" and max_depth == 1:
            return _wechat_query(
                [
                    *self._navigation_nodes(),
                    _query_node("0/11", "AXSplitGroup", description="main"),
                ]
            )
        return _wechat_query([])

    def _navigation_nodes(self) -> list[dict[str, Any]]:
        return [
            _query_node(
                "0/1",
                "AXRadioButton",
                description="聊天",
                value=1 if self.section == "chats" else 0,
            ),
            _query_node(
                "0/2",
                "AXRadioButton",
                description="通讯录",
                value=1 if self.section == "contacts" else 0,
            ),
            _query_node("0/3", "AXRadioButton", description="收藏", value=0),
        ]

    def _row_nodes(self, root_path: str = "0/12/1/0") -> list[dict[str, Any]]:
        if root_path == "0/12/2/0":
            return [
                _query_node(f"{root_path}/0", "AXRow", height=68),
                _query_node(f"{root_path}/0/0/1", "AXStaticText", value="Ada"),
                _query_node(f"{root_path}/1", "AXRow", height=68),
                _query_node(f"{root_path}/1/0/1", "AXStaticText", value="Bob"),
            ]
        return [
            _query_node(
                f"{root_path}/0",
                "AXRow",
                description="文件传输助手,hello,09:00,置顶",
                height=68,
            )
        ]

    def _contact_text_nodes(self, root_path: str) -> list[dict[str, Any]]:
        return [
            _query_node(f"{root_path}/0/0/1", "AXStaticText", value="Ada"),
            _query_node(f"{root_path}/1/0/1", "AXStaticText", value="Bob"),
        ]

    def _field_nodes(self, root_path: str) -> list[dict[str, Any]]:
        if self.section == "contacts":
            value = "Ada" if root_path.endswith("/0") else "Bob"
            return [_query_node(f"{root_path}/0", "AXStaticText", value=value)]
        return [
            _query_node(
                f"{root_path}/0",
                "AXCell",
                description="文件传输助手,hello,09:00,置顶",
            )
        ]

    def _visible_contact_nodes(self) -> list[dict[str, Any]]:
        return [
            _query_node(
                "0/11/1/0/0",
                "AXRow",
                description="文件传输助手",
                height=68,
            )
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


class FakeWeChatLivePrereqProvider:
    def __init__(self, raw_state: dict[str, Any]) -> None:
        self.raw_state = raw_state

    def collect(self) -> dict[str, Any]:
        return self.raw_state


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
            [
                "readiness",
                "open_app",
                "observe",
                "accessibility_query",
            ],
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
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "type_text",
                "press_key",
            ],
        )
        self.assertNotIn(
            "click",
            [command["operation"] for command in service_client.commands],
        )
        self.assertNotIn(
            "hotkey",
            [command["operation"] for command in service_client.commands],
        )
        self.assertEqual(service_client.commands[8]["input"]["text"], "hello")
        self.assertEqual(persisted["submitDraft"]["operation"], "submit_draft")

    def test_wechat_contacts_list_test_lists_contacts(self) -> None:
        module = _load_wechat_contacts_list_test_module()
        service_client = FakeContactsListServiceClient()
        system_open = FakeSystemOpenRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts-list-output.json"
            payload = module.run_contacts_list_test(
                config_path=None,
                output_path=output_path,
                socket_path="/tmp/app-control.sock",
                service_client=service_client,
                system_open_runner=system_open,
                limit=2,
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["success"], True)
        self.assertEqual(payload["summary"]["listedContactCount"], 2)
        self.assertEqual(payload["contactNames"], ["Ada", "Bob"])
        self.assertEqual(
            [item["displayName"] for item in payload["contacts"]],
            ["Ada", "Bob"],
        )
        self.assertEqual(payload["systemOpenWeChat"]["success"], True)
        self.assertEqual(
            [command[:2] for command in system_open.commands],
            [["open", "-b"], ["osascript", "-e"]],
        )
        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            [
                "readiness",
                "open_app",
                "observe",
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "accessibility_query",
            ],
        )
        self.assertEqual(persisted["summary"]["listedContactCount"], 2)
        self.assertEqual(persisted["contactNames"], ["Ada", "Bob"])

    def test_wechat_contacts_recent_messages_test_reads_configured_contact(
        self,
    ) -> None:
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
                contact="文件传输助手",
                message_limit=30,
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["success"], True)
        self.assertEqual(payload["summary"]["contact"], "文件传输助手")
        self.assertEqual(payload["summary"]["messageCount"], 2)
        self.assertEqual(payload["systemOpenWeChat"]["success"], True)
        self.assertEqual(
            [command[:2] for command in system_open.commands],
            [["open", "-b"], ["osascript", "-e"]],
        )
        self.assertEqual(
            payload["openContact"]["operation"],
            "open_contact",
        )
        self.assertEqual(
            payload["openContact"]["observation"]["target"],
            "文件传输助手",
        )
        self.assertEqual(
            payload["openContact"]["observation"]["currentChat"]["title"],
            "文件传输助手",
        )
        self.assertEqual(
            payload["readVisibleMessages"]["operation"],
            "read_visible_messages",
        )
        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            [
                "readiness",
                "open_app",
                "observe",
                "open_app",
                "observe",
                "accessibility_query",
                "accessibility_action",
                "accessibility_query",
                "open_app",
                "observe",
                "accessibility_query",
            ],
        )
        self.assertNotIn(
            "type_text",
            [command["operation"] for command in service_client.commands],
        )
        output = StringIO()
        with redirect_stdout(output):
            module._print_message_records(payload["readVisibleMessages"])
        self.assertIn("messages (2):", output.getvalue())
        self.assertIn("01. [unknown] hello", output.getvalue())
        self.assertIn("02. [unknown] reply", output.getvalue())
        self.assertEqual(persisted["summary"]["contact"], "文件传输助手")
        self.assertEqual(persisted["summary"]["currentChat"], "文件传输助手")
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
                contact="文件传输助手",
                message_limit=30,
            )

        self.assertEqual(payload["summary"]["success"], False)
        self.assertEqual(payload["summary"]["failedStep"], "openWeChat")
        self.assertEqual(
            payload["openContact"]["failureKind"],
            "open_wechat_failed",
        )
        self.assertEqual(
            payload["readVisibleMessages"]["failureKind"],
            "open_contact_failed",
        )
        self.assertEqual(
            [command["operation"] for command in service_client.commands],
            [
                "readiness",
                "open_app",
                "observe",
                "focus_app",
                "observe",
                "accessibility_query",
            ],
        )

    def test_wechat_selector_engine_smoke_test_runs_checklist(self) -> None:
        module = _load_wechat_selector_engine_smoke_test_module()
        service_client = FakeSelectorEngineSmokeServiceClient()
        system_open = FakeSystemOpenRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "selector-engine-smoke-output.json"
            payload = module.run_selector_engine_smoke_test(
                config_path=None,
                output_path=output_path,
                socket_path="/tmp/app-control.sock",
                service_client=service_client,
                system_open_runner=system_open,
                contact="文件传输助手",
                conversation_limit=1,
                contact_limit=2,
                message_limit=2,
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["success"], True)
        self.assertEqual(payload["summary"]["conversationCount"], 1)
        self.assertEqual(payload["summary"]["contactCount"], 2)
        self.assertEqual(payload["summary"]["messageCount"], 2)
        self.assertEqual(payload["summary"]["failedStep"], None)
        self.assertEqual(payload["expiredActionRef"]["success"], True)
        self.assertEqual(
            payload["expiredActionRef"]["failureKind"],
            "wechat_action_ref_expired",
        )
        self.assertEqual(
            payload["openContact"]["observation"]["openMethod"],
            "control_map_visible_action_ref",
        )
        self.assertEqual(payload["profileOverrides"]["validOverride"]["success"], True)
        self.assertEqual(payload["profileOverrides"]["invalidFallback"]["success"], True)
        self.assertEqual(
            [command[:2] for command in system_open.commands],
            [["open", "-b"], ["osascript", "-e"]],
        )
        operations = [command["operation"] for command in service_client.commands]
        self.assertIn("listConversations", persisted["summary"]["checks"])
        self.assertIn("accessibility_action", operations)
        self.assertNotIn("click", operations)
        self.assertNotIn("type_text", operations)
        self.assertNotIn("press_key", operations)
        self.assertEqual(
            operations.count("accessibility_action"),
            4,
            "expired actionRef check must not add a backend action",
        )

    def test_wechat_live_prereq_probe_reports_ready_state(self) -> None:
        module = _load_wechat_live_prereq_probe_module()
        provider = FakeWeChatLivePrereqProvider(
            {
                "status": "ok",
                "accessibilityTrusted": True,
                "frontmost": {
                    "name": "WeChat",
                    "bundleId": "com.tencent.xinWeChat",
                    "pid": 100,
                },
                "wechatApps": [
                    {
                        "name": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "pid": 100,
                        "focusedWindow": {
                            "role": "AXWindow",
                            "title": "微信 (聊天)",
                        },
                        "windows": [
                            {
                                "index": 0,
                                "role": "AXWindow",
                                "title": "微信 (聊天)",
                            }
                        ],
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "wechat-live-prereq.json"
            payload = module.run_live_prereq_probe(
                output_path=output_path,
                provider=provider,
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], module.SCHEMA)
        self.assertEqual(payload["success"], True)
        self.assertEqual(payload["readyForSmoke"], True)
        self.assertEqual(payload["failureKind"], None)
        self.assertEqual(payload["summary"]["checks"]["wechatAxWindow"], True)
        self.assertEqual(persisted["status"], "ready")

    def test_wechat_live_prereq_probe_reports_frontmost_blocker(self) -> None:
        module = _load_wechat_live_prereq_probe_module()
        provider = FakeWeChatLivePrereqProvider(
            {
                "status": "ok",
                "accessibilityTrusted": True,
                "frontmost": {
                    "name": "Codex",
                    "bundleId": "com.openai.codex",
                    "pid": 200,
                },
                "wechatApps": [
                    {
                        "name": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "pid": 100,
                        "focusedWindow": {
                            "role": "AXApplication",
                            "title": "微信",
                        },
                        "windows": [
                            {
                                "index": 0,
                                "role": "AXApplication",
                                "title": "微信",
                            }
                        ],
                    }
                ],
            }
        )

        payload = module.run_live_prereq_probe(provider=provider)

        self.assertEqual(payload["success"], False)
        self.assertEqual(payload["status"], "not_ready")
        self.assertEqual(payload["failureKind"], "frontmost_not_wechat")
        self.assertEqual(payload["summary"]["checks"]["frontmostWeChat"], False)
        self.assertEqual(payload["summary"]["checks"]["wechatAxWindow"], False)

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


def _load_wechat_contacts_list_test_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_contacts_list_test.py"
    return _load_example_module(example_path, "wechat_contacts_list_test")


def _load_wechat_contacts_recent_messages_test_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_contacts_recent_messages_test.py"
    return _load_example_module(example_path, "wechat_contacts_recent_messages_test")


def _load_wechat_selector_engine_smoke_test_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_selector_engine_smoke_test.py"
    return _load_example_module(example_path, "wechat_selector_engine_smoke_test")


def _load_wechat_live_prereq_probe_module() -> Any:
    root = Path(__file__).resolve().parents[1]
    example_path = root / "examples" / "wechat_live_prereq_probe.py"
    return _load_example_module(example_path, "wechat_live_prereq_probe")


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
            "frame": {
                "x": 0,
                "y": 0,
                "width": 1440,
                "height": 900,
            },
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
    height: int = 30,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "axPath": ax_path,
        "role": role,
        "enabled": True,
        "frame": {"x": 100, "y": 100, "width": 120, "height": height},
        "childrenCount": 0,
    }
    if description is not None:
        payload["description"] = description
    if value is not None:
        payload["value"] = value
    if role in {"AXRadioButton", "AXRow", "AXTextArea"}:
        payload["actions"] = ["AXPress"]
    return payload
