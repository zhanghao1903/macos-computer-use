from __future__ import annotations

import unittest

from macos_computer_use import MacOSComputerUseClient
from macos_computer_use.commands import CommandResult
from macos_computer_use.models import ComputerUseStatus


class FakeProbe:
    def __init__(self, platform: str = "Darwin", accessibility: bool = True) -> None:
        self.platform = platform
        self.accessibility = accessibility

    def platform_name(self) -> str:
        return self.platform

    def accessibility_trusted(self) -> bool:
        return self.accessibility

    def screen_recording_available(self) -> bool | None:
        return None


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.responses: list[CommandResult] = []

    def queue(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.responses.append(CommandResult(returncode, stdout, stderr))

    def run(self, args: list[str] | tuple[str, ...], *, timeout: float) -> CommandResult:
        self.calls.append(tuple(args))
        if self.responses:
            return self.responses.pop(0)
        return CommandResult(0, "", "")


class ClientTests(unittest.TestCase):
    def test_open_app_blocks_non_allowlisted_app(self) -> None:
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=FakeRunner(),
        )

        result = client.open_app("WeChat")

        self.assertEqual(result.status, ComputerUseStatus.BLOCKED)
        self.assertFalse(result.success)

    def test_open_app_runs_allowlisted_app(self) -> None:
        runner = FakeRunner()
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        result = client.open_app("TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.OK)
        self.assertEqual(runner.calls[0], ("open", "-a", "TextEdit"))

    def test_observe_requires_ready_accessibility(self) -> None:
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(accessibility=False),
            runner=FakeRunner(),
        )

        result = client.observe(target_app="TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.NOT_AVAILABLE)

    def test_observe_returns_frontmost_summary(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nUntitled\n")
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        result = client.observe(target_app="TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.OK)
        self.assertEqual(result.metadata["frontmost_app"], "TextEdit")
        self.assertEqual(result.metadata["window_title"], "Untitled")

    def test_type_text_blocks_newline(self) -> None:
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=FakeRunner(),
        )

        result = client.type_text("hello\n")

        self.assertEqual(result.status, ComputerUseStatus.BLOCKED)

    def test_type_text_observes_target_then_types(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nUntitled\n")
        runner.queue()
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        result = client.type_text("hello", target_app="TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.OK)
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(runner.calls[1][0], "osascript")

    def test_click_blocks_high_risk_send_target(self) -> None:
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=FakeRunner(),
        )

        result = client.click("Send", target_app="TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.BLOCKED)
        self.assertEqual(result.metadata["confirmation_required"], True)
        self.assertIsNotNone(result.risk)

    def test_click_requires_target_app_for_semantic_click(self) -> None:
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=FakeRunner(),
        )

        result = client.click("OK")

        self.assertEqual(result.status, ComputerUseStatus.NEEDS_USER)

    def test_click_blocks_stale_snapshot(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nCurrent\n")
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        result = client.click(
            "OK",
            target_app="TextEdit",
            snapshot_id="frontmost:TextEdit:Old",
        )

        self.assertEqual(result.status, ComputerUseStatus.BLOCKED)
        self.assertEqual(result.metadata["expected"], "frontmost:TextEdit:Old")

    def test_disabled_backend_returns_not_available(self) -> None:
        client = MacOSComputerUseClient(
            allowed_apps=("TextEdit",),
            enabled=False,
            probe=FakeProbe(),
            runner=FakeRunner(),
        )

        result = client.open_app("TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.NOT_AVAILABLE)


if __name__ == "__main__":
    unittest.main()
