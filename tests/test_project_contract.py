from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any
import unittest


ROOT = Path(__file__).resolve().parents[1]
for package_src in (
    ROOT / "packages" / "app-control-protocol" / "src",
    ROOT / "packages" / "computer-use-macos" / "src",
    ROOT / "packages" / "wechat-desktop-tool" / "src",
):
    sys.path.insert(0, str(package_src))

from app_control_protocol import (  # noqa: E402
    ToolCommand,
    ToolError,
    ToolObservation,
    ToolStatus,
    validate_protocol_payload,
)
from computer_use_macos import (  # noqa: E402
    COMPUTER_USE_FAILURE_KINDS,
    ComputerUseClient,
    HelperManifest,
    HelperTransportClient,
)
from wechat_desktop_tool import (  # noqa: E402
    WECHAT_TOOL,
    WeChatDesktopTool,
    build_wechat_tool,
)


class ProtocolRecordingClient:
    def __init__(
        self,
        responses: list[dict[str, Any] | ToolObservation] | None = None,
    ) -> None:
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
        validate_protocol_payload("command", tool_command.to_dict())
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
            observation={"operation": tool_command.operation},
        )


class ProjectContractTests(unittest.TestCase):
    def test_api_docs_describe_protocol_and_direct_statuses(self) -> None:
        api_doc = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")

        for status in ToolStatus:
            with self.subTest(status=status.value):
                self.assertIn(f"| `{status.value}` |", api_doc)

        self.assertIn("| `blocked` | `failed` |", api_doc)
        self.assertIn("| `needs_user` | `not_ready` |", api_doc)
        self.assertIn("| `not_available` | `not_ready` |", api_doc)
        self.assertIn("legacyStatus", api_doc)

    def test_docs_use_current_computer_use_allowlist_failure_kind(self) -> None:
        protocol_doc = (ROOT / "docs" / "protocol.md").read_text(encoding="utf-8")

        self.assertIn("app_not_allowlisted", COMPUTER_USE_FAILURE_KINDS)
        self.assertIn('"failureKind": "app_not_allowlisted"', protocol_doc)
        self.assertNotIn("app_not_allowed", protocol_doc)

    def test_quickstart_covers_developer_preview_acceptance_path(self) -> None:
        quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for expected in (
            "30 Minute TextEdit Smoke",
            "60 Minute WeChat Focus/Draft Smoke",
            "COMPUTER_USE_DRY_RUN=1",
            "WECHAT_TOOL_DRY_RUN=1",
            "WECHAT_TOOL_SOCKET_PATH=/tmp/app-control.sock",
            "WECHAT_TOOL_ALLOW_SEND=1",
            "build_wechat_tool",
            "textedit-smoke.json",
            "wechat-focus-draft-smoke.json",
            "computer-use-macos serve",
            "python -m computer_use_macos helper init",
            "python -m computer_use_macos helper build",
            "python -m computer_use_macos doctor",
            "release_preflight.py",
            "TestPyPI install report",
            "Trusted Publisher report",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, quickstart)

        self.assertIn("docs/quickstart.md", readme)

    def test_success_standard_flow_uses_protocol_round_trip(self) -> None:
        app_control = ProtocolRecordingClient(
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
        wechat = build_wechat_tool(app_control)

        self.assertIsInstance(wechat, WeChatDesktopTool)
        focus = wechat.focus_contact("File Transfer")
        draft = wechat.draft_message("hello")
        submit = wechat.submit_draft()

        self.assertTrue(focus.success)
        self.assertTrue(draft.success)
        self.assertTrue(submit.success)
        self.assertEqual(focus.observation["focusedContact"], "File Transfer")
        self.assertEqual(draft.observation["draftReady"], True)
        self.assertEqual(submit.observation["submitted"], True)
        self.assertEqual(submit.observation["sendAttempted"], True)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            [
                "open_app",
                "observe",
                "hotkey",
                "observe",
                "hotkey",
                "press_key",
                "type_text",
                "press_key",
                "observe",
                "type_text",
                "press_key",
            ],
        )
        for observation in (focus, draft, submit):
            payload = observation.to_dict()
            validate_protocol_payload("observation", payload)
            self.assertEqual(ToolObservation.from_dict(payload).to_dict(), payload)

    def test_success_standard_helper_factory_exposes_sdk_surface(self) -> None:
        app_control = ComputerUseClient.from_helper_manifest(
            HelperManifest(
                bundle_id="com.example.helper",
                socket_path="/tmp/example-helper.sock",
            )
        )
        wechat = WeChatDesktopTool(app_control=app_control)

        self.assertIsInstance(app_control, HelperTransportClient)
        self.assertIsInstance(wechat, WeChatDesktopTool)
        for method_name in (
            "run_command",
            "run_stream",
            "readiness",
            "open_app",
            "focus_app",
            "observe",
            "type_text",
            "press_key",
            "hotkey",
            "click",
            "wait",
        ):
            with self.subTest(method_name=method_name):
                self.assertTrue(callable(getattr(app_control, method_name)))

    def test_submit_unknown_is_not_retried_by_package(self) -> None:
        failed_press = ToolObservation.failure(
            command_id="cmd_submit:submit_draft",
            tool="macos.computer_use",
            operation="press_key",
            status=ToolStatus.FAILED,
            error=ToolError(
                failure_kind="press_key_failed",
                message="press key failed",
                retryable=True,
            ),
        )
        app_control = ProtocolRecordingClient([failed_press])
        wechat = WeChatDesktopTool(app_control)

        result = wechat.run_command(
            ToolCommand(
                command_id="cmd_submit",
                tool=WECHAT_TOOL,
                operation="submit_draft",
                input={"method": "keyboard_return"},
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, ToolStatus.UNKNOWN)
        self.assertEqual(result.failure_kind, "submit_unknown")
        self.assertEqual(result.retryable, False)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["press_key"],
        )
        validate_protocol_payload("observation", result.to_dict())


if __name__ == "__main__":
    unittest.main()
