from __future__ import annotations

from collections.abc import Mapping
from contextlib import redirect_stdout
from io import StringIO
import json
import os
import plistlib
from pathlib import Path
import py_compile
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
import unittest

from app_control_protocol import (
    HELPER_RESPONSE_SCHEMA,
    ToolCommand,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolStatus,
    validate_protocol_payload,
)
import computer_use_macos
from computer_use_macos import (
    COMPUTER_USE_TOOL,
    COMPUTER_USE_FAILURE_KINDS,
    AppControlConfig,
    ComputerUseClient,
    ComputerUseError,
    HelperConfig,
    MacOSComputerUseClient,
    UnixSocketServiceClient,
    accessibility_action_command,
    accessibility_query_command,
    click_accessibility_command,
    click_command,
    click_coordinate_command,
    computer_use_command,
    focus_app_command,
    hotkey_command,
    load_app_control_config,
    observe_command,
    open_app_command,
    press_key_command,
    readiness_command,
    type_text_command,
    wait_command,
)
from computer_use_macos.commands import CommandResult
from computer_use_macos.client import ComputerUseClient as ShortClientFromModule
from computer_use_macos.client import MacOSComputerUseClient as ClientFromModule
from computer_use_macos.client import _accessibility_action_script
from computer_use_macos.client import _accessibility_query_script
from computer_use_macos.client import _accessibility_tree_snapshot_script
from computer_use_macos.helper import (
    HelperManifest,
    HelperManifestIdentityError,
    HelperTransportClient,
    HelperTemplateConfig,
    build_helper_template,
    doctor_helper,
    helper_transport_from_manifest,
    init_helper_template,
)
from computer_use_macos.models import ComputerUseOperation
from computer_use_macos.models import ComputerUseReadinessStatus
from computer_use_macos.models import ComputerUseStatus
from computer_use_macos.service import (
    SERVICE_EVENT_SCHEMA,
    SERVICE_REQUEST_SCHEMA,
    SERVICE_RESPONSE_SCHEMA,
    LocalCommandService,
    LocalServiceError,
    UnixSocketCommandService,
    _decode_service_responses,
)
from computer_use_macos.service import UnixSocketServiceClient as ServiceClientFromModule
from computer_use_macos.service import service_envelope_to_sse


ROOT = Path(__file__).resolve().parents[1]
BANNED_TERMS = (
    "taskweavn",
    "from plato",
    "import plato",
    "openai",
    "anthropic",
    "langchain",
    "ui_tars",
    "uitars",
    "wechat_desktop_tool",
)
BANNED_IMPORTS = ("from macos_computer_use", "import macos_computer_use")


class FakeStreamingAppControl:
    def run_command(
        self,
        command: ToolCommand | Mapping[str, object],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        tool_command = _coerce_command(command)
        if observer is not None:
            observer.on_event(
                ToolEvent(
                    command_id=tool_command.command_id,
                    seq=0,
                    event_type=ToolEventType.STARTED,
                    phase=tool_command.operation,
                )
            )
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary="ran command",
            observation={"operation": tool_command.operation},
        )

    def run_stream(
        self,
        command: ToolCommand | Mapping[str, object],
        *,
        observer: object | None = None,
    ) -> object:
        tool_command = _coerce_command(command)
        started = ToolEvent(
            command_id=tool_command.command_id,
            seq=0,
            event_type=ToolEventType.STARTED,
            phase=tool_command.operation,
        )
        if observer is not None:
            observer.on_event(started)
        yield started
        observation = self.run_command(tool_command)
        finished = ToolEvent(
            command_id=tool_command.command_id,
            seq=1,
            event_type=ToolEventType.OBSERVATION,
            phase=tool_command.operation,
            status=observation.status,
            summary=observation.summary,
            data={"observation": observation.to_dict()},
        )
        if observer is not None:
            observer.on_event(finished)
        yield finished


class RunOnlyFakeAppControl:
    def run_command(
        self,
        command: ToolCommand | Mapping[str, object],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        tool_command = _coerce_command(command)
        if observer is not None:
            observer.on_event(
                ToolEvent(
                    command_id=tool_command.command_id,
                    seq=0,
                    event_type=ToolEventType.STARTED,
                    phase=tool_command.operation,
                )
            )
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary="ran command",
            observation={"operation": tool_command.operation},
        )


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[ToolEvent] = []

    def on_event(self, event: ToolEvent) -> None:
        self.events.append(event)


class FakeProbe:
    def __init__(
        self,
        *,
        screen_recording: bool | None = None,
        apple_events: bool | None = None,
        fail_screen_recording: bool = False,
    ) -> None:
        self.screen_recording = screen_recording
        self.apple_events = apple_events
        self.fail_screen_recording = fail_screen_recording

    def platform_name(self) -> str:
        return "Darwin"

    def accessibility_trusted(self) -> bool:
        return True

    def screen_recording_available(self) -> bool | None:
        if self.fail_screen_recording:
            raise RuntimeError("screen recording probe failed")
        return self.screen_recording

    def apple_events_available(self) -> bool | None:
        return self.apple_events


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.timeouts: list[float] = []
        self.responses: list[CommandResult] = []

    def queue(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.responses.append(CommandResult(returncode, stdout, stderr))

    def queue_timeout(self, stderr: str = "timed out") -> None:
        self.responses.append(CommandResult(124, "", stderr, timed_out=True))

    def run(
        self,
        args: list[str] | tuple[str, ...],
        *,
        timeout: float,
    ) -> CommandResult:
        self.calls.append(tuple(args))
        self.timeouts.append(timeout)
        if self.responses:
            return self.responses.pop(0)
        return CommandResult(0, "", "")


class ComputerUseMacOSPackageTests(unittest.TestCase):
    def test_command_builders_create_protocol_envelopes(self) -> None:
        commands = [
            readiness_command(command_id="cmd_readiness"),
            observe_command(
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                include_visible_text=True,
                include_accessibility=True,
                command_id="cmd_observe",
            ),
            accessibility_query_command(
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                root={"kind": "focusedWindow"},
                query={"scope": "children", "limit": 5},
                command_id="cmd_accessibility_query",
            ),
            accessibility_action_command(
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                snapshot_id="frontmost:TextEdit:Current",
                ax_path="0/1",
                action="AXPress",
                preconditions={
                    "roleIn": ["AXButton"],
                    "labelIn": ["OK"],
                    "actionIn": ["AXPress"],
                },
                command_id="cmd_accessibility_action",
            ),
            open_app_command(
                "TextEdit",
                bundle_id="com.apple.TextEdit",
                command_id="cmd_open",
            ),
            focus_app_command(
                "TextEdit",
                bundle_id="com.apple.TextEdit",
                command_id="cmd_focus",
            ),
            click_command(
                "OK",
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                snapshot_id="snapshot-1",
                command_id="cmd_click",
            ),
            click_accessibility_command(
                {"role": "button", "name": "OK"},
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                command_id="cmd_selector",
            ),
            click_coordinate_command(
                12,
                34,
                bundle_id="com.apple.TextEdit",
                command_id="cmd_coordinate",
            ),
            type_text_command(
                "hello",
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                command_id="cmd_type",
            ),
            press_key_command(
                "Return",
                bundle_id="com.apple.TextEdit",
                command_id="cmd_press",
            ),
            hotkey_command(
                ("Command", "K"),
                bundle_id="com.apple.TextEdit",
                command_id="cmd_hotkey",
            ),
            wait_command(seconds=0.25, command_id="cmd_wait"),
            computer_use_command(
                ComputerUseOperation.OPEN_APP,
                {"app": "TextEdit"},
                command_id="cmd_custom",
                timeout_ms=1234,
                metadata={"caller": "unit-test"},
            ),
        ]

        for command in commands:
            with self.subTest(operation=command.operation):
                self.assertEqual(command.tool, COMPUTER_USE_TOOL)
                validate_protocol_payload("command", command.to_dict())
        self.assertEqual(commands[1].input["includeVisibleText"], True)
        self.assertEqual(commands[1].input["includeAccessibility"], True)
        self.assertEqual(commands[1].input["bundleId"], "com.apple.TextEdit")
        self.assertEqual(commands[2].operation, "accessibility_query")
        self.assertEqual(commands[2].input["query"]["limit"], 5)
        self.assertEqual(commands[3].operation, "accessibility_action")
        self.assertEqual(commands[3].input["target"]["axPath"], "0/1")
        self.assertEqual(commands[3].input["action"], "AXPress")
        self.assertEqual(commands[4].input["bundleId"], "com.apple.TextEdit")
        self.assertEqual(commands[6].input["snapshotId"], "snapshot-1")
        self.assertEqual(
            commands[7].input["selector"],
            {"role": "button", "name": "OK"},
        )
        self.assertEqual(commands[7].input["bundleId"], "com.apple.TextEdit")
        self.assertEqual(commands[8].input["coordinates"], [12, 34])
        self.assertEqual(commands[11].input["keys"], ["Command", "K"])
        self.assertEqual(commands[9].input["bundleId"], "com.apple.TextEdit")
        self.assertEqual(commands[13].timeout_ms, 1234)

    def test_command_builder_output_runs_through_client(self) -> None:
        runner = FakeRunner()
        client = ComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        pressed = client.run_command(press_key_command("Return"))
        hotkey = client.run_command(hotkey_command(("Command", "K")))

        self.assertTrue(pressed.success)
        self.assertTrue(hotkey.success)
        self.assertIn("key code 36", runner.calls[0][2])
        self.assertIn('keystroke "K" using {command down}', runner.calls[1][2])

    def test_package_local_readiness_reports_permission_states(self) -> None:
        client = ComputerUseClient(
            probe=FakeProbe(screen_recording=True, apple_events=True),
            runner=FakeRunner(),
        )
        missing_screen_recording = ComputerUseClient(
            screen_recording_required=True,
            probe=FakeProbe(screen_recording=False, apple_events=True),
            runner=FakeRunner(),
        )
        unknown_screen_recording = ComputerUseClient(
            probe=FakeProbe(fail_screen_recording=True, apple_events=True),
            runner=FakeRunner(),
        )

        ready = client.readiness()

        self.assertEqual(ready.status, ComputerUseReadinessStatus.READY)
        self.assertEqual(ready.to_dict()["permissions"]["screenRecording"], True)
        self.assertEqual(ready.to_dict()["permissions"]["appleEvents"], True)
        self.assertEqual(
            missing_screen_recording.readiness().status,
            ComputerUseReadinessStatus.MISSING_SCREEN_RECORDING,
        )
        self.assertIsNone(
            unknown_screen_recording.readiness().screen_recording_available
        )

    def test_top_level_exports_package_local_client(self) -> None:
        self.assertIsNot(ComputerUseClient, MacOSComputerUseClient)
        self.assertIs(ClientFromModule, MacOSComputerUseClient)
        self.assertIs(ShortClientFromModule, ComputerUseClient)
        self.assertEqual(computer_use_macos.__version__, "0.1.1")

        client = ComputerUseClient(enabled=False)
        self.assertIsInstance(client, MacOSComputerUseClient)

    def test_package_local_client_observations_include_timing(self) -> None:
        runner = FakeRunner()
        client = ComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_timing",
                tool="macos.computer_use",
                operation="open_app",
                input={"app": "TextEdit"},
            )
        )

        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(runner.calls[0], ("open", "-a", "TextEdit"))
        _assert_observation_timing(observation)

    def test_package_local_client_maps_command_timeout(self) -> None:
        runner = FakeRunner()
        runner.queue_timeout()
        client = ComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_timeout",
                tool="macos.computer_use",
                operation="open_app",
                input={"app": "TextEdit"},
                timeout_ms=500,
            )
        )

        self.assertEqual(observation.status, ToolStatus.TIMEOUT)
        self.assertEqual(observation.failure_kind, "timeout")
        self.assertEqual(observation.retryable, True)
        self.assertEqual(
            observation.observation["metadata"]["timeout_seconds"],
            0.5,
        )
        _assert_observation_timing(observation)

    def test_package_local_client_supports_coordinate_click(self) -> None:
        runner = FakeRunner()
        client = ComputerUseClient(
            allowed_apps=("TextEdit",),
            allow_coordinate_click=True,
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_coordinate",
                tool="macos.computer_use",
                operation="click",
                input={"coordinates": [12, 34]},
            )
        )

        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(observation.observation["metadata"]["coordinateClick"], True)
        self.assertIn("click at {12, 34}", runner.calls[0][2])

    def test_package_local_client_supports_accessibility_selector_click(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nCurrent\n")
        client = ComputerUseClient(
            allowed_apps=("TextEdit",),
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_selector",
                tool="macos.computer_use",
                operation="click",
                input={
                    "targetApp": "TextEdit",
                    "selector": {"role": "button", "name": "OK"},
                },
            )
        )

        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(
            observation.observation["metadata"]["selector"],
            {"role": "button", "name": "OK"},
        )
        self.assertIn('click button "OK" of front window', runner.calls[1][2])

    def test_package_local_client_uses_app_control_config_for_press_key(
        self,
    ) -> None:
        runner = FakeRunner()
        config = AppControlConfig.from_dict(
            {
                "computer_use": {
                    "backend": "direct",
                    "allowed_apps": ["TextEdit"],
                    "timeout_ms": 7_500,
                }
            }
        )
        client = ComputerUseClient.from_config(
            config,
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_press_key",
                tool="macos.computer_use",
                operation="press_key",
                input={"key": "Return"},
            )
        )

        self.assertIsInstance(client, MacOSComputerUseClient)
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(observation.observation["metadata"]["key"], "Return")
        self.assertEqual(runner.timeouts[0], 7.5)
        self.assertIn("key code 36", runner.calls[0][2])

    def test_package_local_from_config_uses_allowed_app_bundle_ids(self) -> None:
        runner = FakeRunner()
        client = ComputerUseClient.from_config(
            {
                "computer_use": {
                    "backend": "direct",
                    "allowed_app_bundle_ids": {
                        "TextEdit": "com.apple.TextEdit",
                    },
                }
            },
            probe=FakeProbe(),
            runner=runner,
        )

        result = client.open_app("TextEdit", bundle_id="com.apple.TextEdit")
        blocked = client.open_app("TextEdit", bundle_id="com.example.TextEdit")

        self.assertEqual(result.status, ComputerUseStatus.OK)
        self.assertEqual(runner.calls[0], ("open", "-b", "com.apple.TextEdit"))
        self.assertEqual(blocked.status, ComputerUseStatus.BLOCKED)
        self.assertEqual(blocked.metadata["expected_bundle_id"], "com.apple.TextEdit")
        self.assertEqual(len(runner.calls), 1)

    def test_package_local_keyboard_protocol_observes_target_summary(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nCurrent\ncom.apple.TextEdit\n")
        client = ComputerUseClient.from_config(
            {"computer_use": {"backend": "direct", "allowed_apps": ["TextEdit"]}},
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_target_key",
                tool="macos.computer_use",
                operation="press_key",
                input={
                    "key": "Return",
                    "targetApp": "TextEdit",
                    "bundleId": "com.apple.TextEdit",
                },
            )
        )

        metadata = observation.observation["metadata"]
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(observation.observation["key"], "Return")
        self.assertEqual(observation.observation["actionAttempted"], True)
        self.assertEqual(observation.observation["targetApp"], "TextEdit")
        self.assertEqual(observation.observation["bundleId"], "com.apple.TextEdit")
        self.assertEqual(
            observation.observation["frontmostBundleId"],
            "com.apple.TextEdit",
        )
        self.assertEqual(
            observation.observation["targetSummary"],
            "Frontmost app: TextEdit. Window: Current.",
        )
        self.assertEqual(metadata["key"], "Return")
        self.assertEqual(metadata["action_attempted"], True)
        self.assertEqual(metadata["target_app"], "TextEdit")
        self.assertEqual(metadata["bundle_id"], "com.apple.TextEdit")
        self.assertEqual(metadata["frontmost_bundle_id"], "com.apple.TextEdit")
        self.assertEqual(
            metadata["target_summary"],
            "Frontmost app: TextEdit. Window: Current.",
        )
        self.assertEqual(
            metadata["target_snapshot_id"],
            "frontmost:TextEdit:Current",
        )
        self.assertIn("key code 36", runner.calls[1][2])

    def test_package_local_observe_prefers_bundle_id_over_display_name(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="Localized TextEdit\nCurrent\ncom.apple.TextEdit\n")
        client = ComputerUseClient.from_config(
            {"computer_use": {"backend": "direct", "allowed_apps": ["TextEdit"]}},
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_bundle_observe",
                tool="macos.computer_use",
                operation="observe",
                input={
                    "targetApp": "TextEdit",
                    "bundleId": "com.apple.TextEdit",
                },
            )
        )

        metadata = observation.observation["metadata"]
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(metadata["frontmost_app"], "Localized TextEdit")
        self.assertEqual(metadata["frontmost_bundle_id"], "com.apple.TextEdit")

    def test_package_local_observe_can_include_accessibility_snapshot(self) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nCurrent\ncom.apple.TextEdit\n")
        runner.queue(
            stdout=(
                "focused\t0\tAXTextField\tsearch field\tSearch\t\t\t\ttrue\t"
                "80\t120\t240\t28\n"
                "textField\t1\tAXTextField\tsearch field\tSearch\t\t\t\ttrue\t"
                "80\t120\t240\t28\n"
            )
        )
        client = ComputerUseClient.from_config(
            {"computer_use": {"backend": "direct", "allowed_apps": ["TextEdit"]}},
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_accessibility_observe",
                tool="macos.computer_use",
                operation="observe",
                input={
                    "targetApp": "TextEdit",
                    "bundleId": "com.apple.TextEdit",
                    "includeAccessibility": True,
                },
            )
        )

        accessibility = observation.observation["accessibility"]
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(accessibility["available"], True)
        self.assertEqual(accessibility["focusedElement"]["role"], "AXTextField")
        self.assertEqual(accessibility["focusedElement"]["focused"], True)
        self.assertEqual(
            accessibility["focusedElement"]["frame"],
            {"x": 80, "y": 120, "width": 240, "height": 28},
        )
        self.assertEqual(
            accessibility["textFields"][0]["roleDescription"],
            "search field",
        )

    def test_package_local_observe_can_include_accessibility_tree_snapshot(
        self,
    ) -> None:
        runner = FakeRunner()
        runner.queue(stdout="TextEdit\nCurrent\ncom.apple.TextEdit\n")
        runner.queue(
            stdout=json.dumps(
                {
                    "available": True,
                    "app": {"name": "TextEdit", "bundleId": "com.apple.TextEdit"},
                    "focusedWindow": {
                        "path": "0",
                        "depth": 0,
                        "attribute_names": ["AXRole", "AXTitle", "AXChildren"],
                        "AXRole": "AXWindow",
                        "AXTitle": "Current",
                        "children_count": 0,
                    },
                    "nodeCount": 1,
                }
            )
        )
        client = ComputerUseClient.from_config(
            {"computer_use": {"backend": "direct", "allowed_apps": ["TextEdit"]}},
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_accessibility_tree_observe",
                tool="macos.computer_use",
                operation="observe",
                input={
                    "targetApp": "TextEdit",
                    "bundleId": "com.apple.TextEdit",
                    "includeAccessibilityTree": True,
                },
            )
        )

        accessibility = observation.observation["accessibility"]
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(runner.calls[1][0], sys.executable)
        self.assertEqual(runner.calls[1][-1], "com.apple.TextEdit")
        self.assertGreater(float(runner.calls[1][-2]), 0)
        self.assertEqual(accessibility["available"], True)
        self.assertEqual(accessibility["treeAvailable"], True)
        self.assertEqual(accessibility["focusedWindow"]["AXRole"], "AXWindow")
        self.assertEqual(accessibility["focusedWindow"]["AXTitle"], "Current")

    def test_package_accessibility_tree_script_uses_safe_attribute_allowlist(
        self,
    ) -> None:
        source = _accessibility_tree_snapshot_script()

        self.assertIn("SAFE_ATTRIBUTES = (", source)
        self.assertIn("for attr in SAFE_ATTRIBUTES:", source)
        self.assertIn("TIME_BUDGET_SECONDS", source)
        self.assertIn("TARGET_BUNDLE_ID", source)
        self.assertIn("runningApplicationsWithBundleIdentifier_", source)
        self.assertIn("truncationReason", source)
        self.assertNotIn("for attr in attribute_names:", source)

    def test_package_local_client_supports_accessibility_query_protocol(
        self,
    ) -> None:
        runner = FakeRunner()
        runner.queue(
            stdout=json.dumps(
                {
                    "schema": "macos.accessibility.query.v1",
                    "available": True,
                    "snapshotId": "frontmost:TextEdit:Current",
                    "app": {
                        "name": "TextEdit",
                        "bundleId": "com.apple.TextEdit",
                        "pid": 123,
                    },
                    "window": {"title": "Current", "role": "AXWindow"},
                    "root": {"axPath": "0"},
                    "nodes": [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Documents",
                            "value": 1,
                            "actions": ["AXPress"],
                        }
                    ],
                    "diagnostics": {
                        "durationMs": 10,
                        "truncated": False,
                        "nodeCount": 1,
                    },
                }
            )
        )
        client = ComputerUseClient.from_config(
            {"computer_use": {"backend": "direct", "allowed_apps": ["TextEdit"]}},
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            accessibility_query_command(
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                root={"kind": "focusedWindow"},
                query={
                    "scope": "children",
                    "limit": 10,
                    "attributes": ["AXRole", "AXDescription", "AXValue"],
                    "actions": True,
                    "match": {"roleIn": ["AXRadioButton"]},
                },
                command_id="cmd_query",
            )
        )

        query = observation.observation["accessibilityQuery"]
        request = json.loads(runner.calls[0][-1])
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(observation.observation["snapshotId"], "frontmost:TextEdit:Current")
        self.assertEqual(runner.calls[0][0], sys.executable)
        self.assertEqual(request["bundleId"], "com.apple.TextEdit")
        self.assertEqual(request["query"]["scope"], "children")
        self.assertEqual(request["query"]["match"]["roleIn"], ["AXRadioButton"])
        self.assertEqual(query["nodes"][0]["axPath"], "0/1")
        self.assertEqual(query["nodes"][0]["description"], "Documents")
        self.assertNotIn("attributeNames", query["nodes"][0])

    def test_package_local_client_supports_accessibility_action_protocol(
        self,
    ) -> None:
        runner = FakeRunner()
        runner.queue(
            stdout=json.dumps(
                {
                    "schema": "macos.accessibility.action.result.v1",
                    "available": True,
                    "status": "ok",
                    "operation": "accessibility_action",
                    "method": "AXUIElementPerformAction",
                    "snapshotId": "frontmost:TextEdit:Current",
                    "action": "AXPress",
                    "actionAttempted": True,
                    "target": {
                        "axPath": "0/1",
                        "role": "AXButton",
                        "label": "OK",
                        "actions": ["AXPress"],
                    },
                    "diagnostics": {
                        "durationMs": 12,
                        "verifiedPreconditions": True,
                    },
                }
            )
        )
        client = ComputerUseClient.from_config(
            {
                "computer_use": {
                    "backend": "direct",
                    "allowed_apps": ["TextEdit"],
                    "allowed_app_bundle_ids": {"TextEdit": "com.apple.TextEdit"},
                }
            },
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            accessibility_action_command(
                target_app="TextEdit",
                bundle_id="com.apple.TextEdit",
                snapshot_id="frontmost:TextEdit:Current",
                ax_path="0/1",
                action="AXPress",
                preconditions={
                    "roleIn": ["AXButton"],
                    "labelIn": ["OK"],
                    "actionIn": ["AXPress"],
                },
                command_id="cmd_action",
            )
        )

        request = json.loads(runner.calls[0][-1])
        action = observation.observation["accessibilityAction"]
        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(observation.observation["actionAttempted"], True)
        self.assertEqual(observation.observation["snapshotId"], "frontmost:TextEdit:Current")
        self.assertEqual(request["bundleId"], "com.apple.TextEdit")
        self.assertEqual(request["target"]["axPath"], "0/1")
        self.assertEqual(request["preconditions"]["labelIn"], ["OK"])
        self.assertEqual(action["target"]["role"], "AXButton")
        self.assertEqual(action["method"], "AXUIElementPerformAction")

    def test_package_accessibility_query_script_is_scoped_and_filtered(
        self,
    ) -> None:
        source = _accessibility_query_script()

        self.assertIn("def collect(", source)
        self.assertIn("def node_matches(", source)
        self.assertIn("scope", source)
        self.assertIn("limit", source)
        self.assertIn("timeBudgetMs", source)
        self.assertIn("childrenCount", source)
        self.assertIn("def focused_window_for_app(", source)
        self.assertIn('"AXWindows"', source)

    def test_package_accessibility_action_script_executes_verified_axpress(
        self,
    ) -> None:
        source = _accessibility_action_script()

        self.assertIn("AXUIElementPerformAction", source)
        self.assertIn("def validate_preconditions(", source)
        self.assertIn('"precondition_failed"', source)
        self.assertIn('"AXPress"', source)
        self.assertIn("resolve_ax_path", source)

    def test_package_local_client_supports_hotkey_protocol_command(self) -> None:
        runner = FakeRunner()
        client = ComputerUseClient.from_config(
            {
                "computer_use": {
                    "backend": "direct",
                    "allowed_apps": ["TextEdit"],
                }
            },
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_hotkey",
                tool="macos.computer_use",
                operation="hotkey",
                input={"keys": ["Command", "K"]},
            )
        )

        self.assertEqual(observation.status, ToolStatus.OK)
        self.assertEqual(observation.observation["keys"], ["Command", "K"])
        self.assertEqual(observation.observation["key"], "K")
        self.assertEqual(observation.observation["modifiers"], ["Command"])
        self.assertEqual(observation.observation["actionAttempted"], True)
        self.assertEqual(
            observation.observation["metadata"]["keys"],
            ["Command", "K"],
        )
        self.assertIn('keystroke "K" using {command down}', runner.calls[0][2])

    def test_package_local_client_rejects_hotkey_without_modifier(self) -> None:
        runner = FakeRunner()
        client = ComputerUseClient.from_config(
            {"computer_use": {"backend": "direct"}},
            probe=FakeProbe(),
            runner=runner,
        )

        observation = client.run_command(
            ToolCommand(
                command_id="cmd_invalid_hotkey",
                tool="macos.computer_use",
                operation="hotkey",
                input={"keys": ["K"]},
            )
        )

        self.assertEqual(observation.status, ToolStatus.FAILED)
        self.assertEqual(observation.failure_kind, "invalid_input")
        self.assertEqual(runner.calls, [])

    def test_model_and_helper_re_exports_are_available(self) -> None:
        from computer_use_macos import observations, transport

        self.assertEqual(ComputerUseOperation.OPEN_APP.value, "open_app")
        self.assertEqual(
            ComputerUseOperation.ACCESSIBILITY_ACTION.value,
            "accessibility_action",
        )
        self.assertEqual(ComputerUseOperation.FOCUS_APP.value, "focus_app")
        self.assertEqual(ComputerUseOperation.PRESS_KEY.value, "press_key")
        self.assertEqual(ComputerUseOperation.HOTKEY.value, "hotkey")
        self.assertEqual(HelperConfig().transport, "unix_socket")
        self.assertIs(ComputerUseError, computer_use_macos.ComputerUseError)
        self.assertIn("invalid_input", COMPUTER_USE_FAILURE_KINDS)
        self.assertIn("app_not_allowlisted", COMPUTER_USE_FAILURE_KINDS)
        self.assertIs(AppControlConfig, computer_use_macos.AppControlConfig)
        self.assertIs(
            accessibility_action_command,
            computer_use_macos.accessibility_action_command,
        )
        self.assertIs(
            load_app_control_config,
            computer_use_macos.load_app_control_config,
        )
        self.assertIsNotNone(HelperManifestIdentityError)
        self.assertIsNotNone(HelperTransportClient)
        self.assertIsNotNone(helper_transport_from_manifest)
        self.assertIsNotNone(doctor_helper)
        self.assertIs(LocalCommandService, computer_use_macos.LocalCommandService)
        self.assertIs(
            UnixSocketServiceClient,
            computer_use_macos.UnixSocketServiceClient,
        )
        self.assertIs(UnixSocketServiceClient, ServiceClientFromModule)
        self.assertIs(observations.ComputerUseResult, computer_use_macos.ComputerUseResult)
        self.assertIs(observations.ComputerUseReadiness, computer_use_macos.ComputerUseReadiness)
        self.assertIs(transport.HelperTransportClient, HelperTransportClient)
        self.assertIs(transport.UnixSocketServiceClient, UnixSocketServiceClient)

    def test_package_helper_transport_supports_event_surface(self) -> None:
        received: list[dict[str, object]] = []
        observer = RecordingObserver()
        client = HelperTransportClient(
            HelperManifest(
                bundle_id="com.example.helper",
                socket_path="/tmp/helper.sock",
            ),
            round_trip=_recording_helper_round_trip(received),
        )

        observation = client.run_command(
            readiness_command(command_id="cmd_helper_observer"),
            observer=observer,
        )
        events = list(
            client.run_stream(
                readiness_command(command_id="cmd_helper_stream"),
                observer=observer,
            )
        )

        self.assertTrue(observation.success)
        self.assertEqual(len(received), 2)
        self.assertEqual(received[0]["schema"], "app_control.helper.request.v1")
        validate_protocol_payload("helper_request", received[0])
        self.assertEqual(
            [event.event_type for event in observer.events],
            [
                ToolEventType.STARTED,
                ToolEventType.OBSERVATION,
                ToolEventType.STARTED,
                ToolEventType.OBSERVATION,
            ],
        )
        self.assertEqual(
            [event.event_type for event in events],
            [ToolEventType.STARTED, ToolEventType.OBSERVATION],
        )
        self.assertEqual(
            events[-1].data["observation"]["commandId"],
            "cmd_helper_stream",
        )

    def test_package_helper_transport_supports_convenience_methods(self) -> None:
        received: list[dict[str, object]] = []
        client = HelperTransportClient(
            HelperManifest(
                bundle_id="com.example.helper",
                socket_path="/tmp/helper.sock",
            ),
            round_trip=_recording_helper_round_trip(received),
        )

        observations = [
            client.readiness(command_id="cmd_ready"),
            client.open_app("TextEdit", command_id="cmd_open"),
            client.focus_app("TextEdit", command_id="cmd_focus"),
            client.observe(target_app="TextEdit", command_id="cmd_observe"),
            client.type_text("hello", target_app="TextEdit", command_id="cmd_type"),
            client.press_key("Return", target_app="TextEdit", command_id="cmd_key"),
            client.hotkey(
                ("Command", "K"),
                target_app="TextEdit",
                command_id="cmd_hotkey",
            ),
            client.click("OK", target_app="TextEdit", command_id="cmd_click"),
            client.click_coordinate(12, 34, command_id="cmd_coordinate"),
            client.wait(seconds=0.01, command_id="cmd_wait"),
        ]

        self.assertTrue(all(observation.success for observation in observations))
        commands = [payload["command"] for payload in received]
        self.assertEqual(
            [command["operation"] for command in commands],
            [
                "readiness",
                "open_app",
                "focus_app",
                "observe",
                "type_text",
                "press_key",
                "hotkey",
                "click",
                "click",
                "wait",
            ],
        )
        for command in commands:
            self.assertIsInstance(command, dict)
            validate_protocol_payload("command", command)
        self.assertEqual(commands[6]["input"]["keys"], ["Command", "K"])
        self.assertEqual(commands[8]["input"]["coordinates"], [12, 34])
        self.assertEqual(commands[9]["input"]["seconds"], 0.01)

    def test_package_local_doctor_supports_release_verification(self) -> None:
        with TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "helper.json"
            app_path = Path(tmpdir) / "Helper.app"
            app_path.mkdir()
            manifest_path.write_text(
                json.dumps(
                    {
                        "bundleId": "com.example.helper",
                        "socketPath": "/tmp/helper.sock",
                        "token": "local-token",
                    }
                ),
                encoding="utf-8",
            )
            runner = FakeRunner()

            report = doctor_helper(
                manifest_path=manifest_path,
                helper_app_path=app_path,
                verify_signature=True,
                verify_notarization=True,
                verification_runner=runner,
            )

        checks = {check.name: check for check in report.checks}
        self.assertEqual(report.status, "ready")
        self.assertEqual(checks["signature"].status, "ok")
        self.assertEqual(checks["notarization"].status, "ok")
        self.assertEqual(runner.calls[0][0], "codesign")
        self.assertEqual(runner.calls[1][0], "spctl")

    def test_package_local_helper_template_includes_click_surface(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "helper"
            init_helper_template(
                output,
                config=HelperTemplateConfig(
                    name="Example Helper",
                    bundle_id="com.example.helper",
                ),
            )
            helper_main = output / "src" / "helper_main.py"
            readme = output / "README.md"
            info_plist = output / "Info.plist.template"
            sign_script = output / "sign.sh"
            notarize_script = output / "notarize.sh"
            manifest = json.loads(
                (output / "helper_config.json").read_text(encoding="utf-8")
            )
            py_compile.compile(str(helper_main), doraise=True)
            source = helper_main.read_text(encoding="utf-8")
            readme_source = readme.read_text(encoding="utf-8")
            sign_source = sign_script.read_text(encoding="utf-8")
            notarize_source = notarize_script.read_text(encoding="utf-8")
            with info_plist.open("rb") as plist_file:
                info = plistlib.load(plist_file)

        self.assertIn('"click"', source)
        self.assertIn("HELPER_RESPONSE_SCHEMA", source)
        self.assertIn("def _helper_response", source)
        self.assertIn("allowCoordinateClick", source)
        self.assertIn("allowedAppBundleIds", source)
        self.assertIn("ACCESSIBILITY_ROLES", source)
        self.assertIn("def _click_accessibility(", source)
        self.assertIn("def _click(", source)
        self.assertIn("def _target_allowlist_failure(", source)
        self.assertEqual(manifest["metadata"]["allowedAppBundleIds"], {})
        self.assertIn("os.open(token_path", source)
        self.assertIn("_restrict_private_file(socket_path)", source)
        self.assertIn("Apple Events", info["NSAppleEventsUsageDescription"])
        self.assertIn("computer-use-macos helper doctor", readme_source)
        self.assertNotIn("macos-computer-use helper doctor", readme_source)
        self.assertIn("codesign", sign_source)
        self.assertIn("--options runtime", sign_source)
        self.assertIn("xcrun notarytool submit", notarize_source)
        self.assertIn("xcrun stapler staple", notarize_source)

    def test_computer_use_client_accepts_app_control_config(self) -> None:
        config = AppControlConfig.from_dict(
            {"computer_use": {"backend": "disabled", "allowed_apps": ["TextEdit"]}}
        )

        client = ComputerUseClient.from_config(config)

        self.assertIsInstance(client, MacOSComputerUseClient)

    def test_computer_use_client_accepts_helper_config(self) -> None:
        client = ComputerUseClient(
            HelperConfig(
                bundle_id="com.example.helper",
                endpoint="/tmp/example-helper.sock",
                allowed_apps=("TextEdit",),
            )
        )

        self.assertIsInstance(client, HelperTransportClient)
        self.assertEqual(client.manifest.bundle_id, "com.example.helper")
        self.assertEqual(client.manifest.socket_path, "/tmp/example-helper.sock")
        self.assertEqual(client.manifest.metadata["allowedApps"], ["TextEdit"])

    def test_package_local_from_config_passes_bundle_allowlist_to_helper(self) -> None:
        client = ComputerUseClient.from_config(
            {
                "computer_use": {
                    "backend": "helper",
                    "allowed_app_bundle_ids": {
                        "TextEdit": "com.apple.TextEdit",
                    },
                },
                "helper": {
                    "bundle_id": "com.example.helper",
                    "endpoint": "/tmp/example-helper.sock",
                },
            }
        )

        self.assertIsInstance(client, HelperTransportClient)
        self.assertEqual(client.manifest.metadata["allowedApps"], ["TextEdit"])
        self.assertEqual(
            client.manifest.metadata["allowedAppBundleIds"],
            {"TextEdit": "com.apple.TextEdit"},
        )

    def test_package_local_service_stream_action_is_available(self) -> None:
        service = LocalCommandService(FakeStreamingAppControl())

        responses = list(
            service.stream_payload(
                {
                    "schema": SERVICE_REQUEST_SCHEMA,
                    "action": "stream",
                    "requestId": "req_stream",
                    "command": {
                        "commandId": "cmd_stream",
                        "tool": "macos.computer_use",
                        "operation": "readiness",
                    },
                }
            )
        )

        self.assertEqual([response["status"] for response in responses], [
            "event",
            "event",
            "complete",
        ])
        final = responses[-1]["observation"]
        self.assertIsInstance(final, dict)
        self.assertEqual(final["commandId"], "cmd_stream")
        self.assertIn(
            'event: event\ndata: {"schema":"app_control.service.event.v1"',
            service_envelope_to_sse(responses[0]),
        )

    def test_package_socket_client_rejects_invalid_service_envelope(self) -> None:
        raw_response = (
            b'{"schema":"app_control.service.response.v1",'
            b'"status":"complete","success":false}\n'
        )

        with self.assertRaisesRegex(
            LocalServiceError,
            "invalid local service response",
        ):
            _decode_service_responses(raw_response)

    def test_package_local_service_routes_events_to_configured_observer(self) -> None:
        observer = RecordingObserver()
        service = LocalCommandService(FakeStreamingAppControl(), observer=observer)

        response = service.handle_payload(
            {
                "schema": SERVICE_REQUEST_SCHEMA,
                "action": "run",
                "requestId": "req_observed",
                "command": {
                    "commandId": "cmd_observed",
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                },
            }
        )

        self.assertEqual(response["status"], "complete")
        self.assertEqual(len(observer.events), 1)
        self.assertEqual(observer.events[0].command_id, "cmd_observed")
        self.assertEqual(observer.events[0].event_type, ToolEventType.STARTED)

    def test_package_local_service_stream_fallback_tees_configured_observer(
        self,
    ) -> None:
        observer = RecordingObserver()
        service = LocalCommandService(RunOnlyFakeAppControl(), observer=observer)

        responses = list(
            service.stream_payload(
                {
                    "schema": SERVICE_REQUEST_SCHEMA,
                    "action": "stream",
                    "requestId": "req_stream_fallback",
                    "command": {
                        "commandId": "cmd_stream_fallback",
                        "tool": "macos.computer_use",
                        "operation": "readiness",
                    },
                }
            )
        )

        self.assertEqual([response["status"] for response in responses], [
            "event",
            "complete",
        ])
        self.assertEqual(len(observer.events), 1)
        self.assertEqual(observer.events[0].command_id, "cmd_stream_fallback")

    def test_package_local_service_requires_service_request_schema(self) -> None:
        service = LocalCommandService(FakeStreamingAppControl())

        response = service.handle_payload(
            {
                "action": "run",
                "command": {
                    "commandId": "cmd_missing_schema",
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                },
            }
        )

        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["success"], False)
        error = response["error"]
        self.assertIsInstance(error, dict)
        self.assertEqual(error["failureKind"], "invalid_request")
        self.assertIn("schema", error["message"])

    def test_package_local_service_refuses_existing_non_socket_path(self) -> None:
        with TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "app-control.sock"
            socket_path.write_text("not a socket", encoding="utf-8")
            server = UnixSocketCommandService(
                socket_path,
                LocalCommandService(FakeStreamingAppControl()),
            )

            with self.assertRaisesRegex(LocalServiceError, "not a socket"):
                server.start()

            self.assertEqual(socket_path.read_text(encoding="utf-8"), "not a socket")

    def test_package_local_service_restricts_socket_file_permissions(self) -> None:
        with TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "app-control.sock"
            server = UnixSocketCommandService(
                socket_path,
                LocalCommandService(FakeStreamingAppControl()),
            )
            try:
                server.start()
            except LocalServiceError as exc:
                if "Operation not permitted" in str(exc):
                    self.skipTest("sandbox does not allow Unix socket bind")
                raise
            try:
                self.assertEqual(socket_path.stat().st_mode & 0o777, 0o600)
            finally:
                server.close()

    def test_package_serve_cli_builds_logging_observer_from_config(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        import computer_use_macos.cli as cli_module

        captured: dict[str, object] = {}

        class FakeClientFactory:
            @staticmethod
            def from_config(config: object) -> FakeStreamingAppControl:
                captured["config"] = config
                return FakeStreamingAppControl()

        class FakeServer:
            def __init__(self, socket_path: str, service: LocalCommandService) -> None:
                self.socket_path = Path(socket_path)
                captured["service"] = service

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

        original_client = cli_module.MacOSComputerUseClient
        original_server = cli_module.UnixSocketCommandService
        try:
            cli_module.MacOSComputerUseClient = FakeClientFactory  # type: ignore[assignment]
            cli_module.UnixSocketCommandService = FakeServer  # type: ignore[assignment]
            with TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "app-control.toml"
                config_path.write_text(
                    "\n".join(
                        (
                            "[logging]",
                            "level = \"debug\"",
                            "json = true",
                            "redact_text = false",
                            "event_sink = \"logger\"",
                            "",
                            "[computer_use]",
                            "backend = \"disabled\"",
                        )
                    ),
                    encoding="utf-8",
                )
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "serve",
                            "--config",
                            str(config_path),
                            "--socket-path",
                            str(Path(tmpdir) / "app-control.sock"),
                            "--token",
                            "secret",
                        ]
                    )
        finally:
            cli_module.MacOSComputerUseClient = original_client
            cli_module.UnixSocketCommandService = original_server

        self.assertEqual(exit_code, 130)
        service = captured["service"]
        self.assertIsInstance(service, LocalCommandService)
        self.assertEqual(service.token, "secret")
        observer = service.observer
        self.assertIsNotNone(observer)
        self.assertEqual(observer.config.level, "debug")
        self.assertEqual(observer.config.json, True)
        self.assertEqual(observer.config.redact_text, False)
        self.assertEqual(observer.config.event_sink, "logger")

    def test_package_serve_cli_uses_socket_and_token_from_config(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        import computer_use_macos.cli as cli_module

        captured: dict[str, object] = {}

        class FakeClientFactory:
            @staticmethod
            def from_config(config: object) -> FakeStreamingAppControl:
                captured["config"] = config
                return FakeStreamingAppControl()

        class FakeServer:
            def __init__(self, socket_path: str, service: LocalCommandService) -> None:
                self.socket_path = Path(socket_path)
                captured["socket_path"] = socket_path
                captured["service"] = service

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

        original_client = cli_module.MacOSComputerUseClient
        original_server = cli_module.UnixSocketCommandService
        try:
            cli_module.MacOSComputerUseClient = FakeClientFactory  # type: ignore[assignment]
            cli_module.UnixSocketCommandService = FakeServer  # type: ignore[assignment]
            with TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "app-control.toml"
                socket_path = Path(tmpdir) / "configured.sock"
                config_path.write_text(
                    "\n".join(
                        (
                            "[computer_use]",
                            "backend = \"disabled\"",
                            "",
                            "[helper]",
                            "transport = \"unix_socket\"",
                            f"endpoint = \"{socket_path}\"",
                            "token = \"configured-token\"",
                        )
                    ),
                    encoding="utf-8",
                )
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "serve",
                            "--config",
                            str(config_path),
                        ]
                    )
        finally:
            cli_module.MacOSComputerUseClient = original_client
            cli_module.UnixSocketCommandService = original_server

        self.assertEqual(exit_code, 130)
        self.assertEqual(captured["socket_path"], str(socket_path))
        service = captured["service"]
        self.assertIsInstance(service, LocalCommandService)
        self.assertEqual(service.token, "configured-token")

    def test_package_request_cli_uses_socket_token_and_timeout_from_config(
        self,
    ) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        import computer_use_macos.cli as cli_module

        captured: dict[str, object] = {}

        class FakeClient:
            def __init__(
                self,
                socket_path: str,
                *,
                token: str | None,
                timeout: float,
            ) -> None:
                captured["socket_path"] = socket_path
                captured["token"] = token
                captured["timeout"] = timeout

            def request(
                self,
                payload: Mapping[str, object],
            ) -> list[dict[str, object]]:
                captured["payload"] = dict(payload)
                return [
                    {
                        "schema": SERVICE_RESPONSE_SCHEMA,
                        "status": "complete",
                        "success": True,
                    }
                ]

        original_client = cli_module.UnixSocketServiceClient
        try:
            cli_module.UnixSocketServiceClient = FakeClient  # type: ignore[assignment]
            with TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "app-control.toml"
                socket_path = Path(tmpdir) / "configured.sock"
                config_path.write_text(
                    "\n".join(
                        (
                            "[computer_use]",
                            "timeout_ms = 2500",
                            "",
                            "[helper]",
                            "transport = \"unix_socket\"",
                            f"endpoint = \"{socket_path}\"",
                            "token = \"configured-token\"",
                        )
                    ),
                    encoding="utf-8",
                )
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli_module.main(
                        [
                            "request",
                            "--config",
                            str(config_path),
                            "--operation",
                            "readiness",
                        ]
                    )
        finally:
            cli_module.UnixSocketServiceClient = original_client

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["socket_path"], str(socket_path))
        self.assertEqual(captured["token"], "configured-token")
        self.assertEqual(captured["timeout"], 2.5)
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["action"], "run")

    def test_package_request_cli_builds_submit_poll_stream_and_sse_payloads(
        self,
    ) -> None:
        import computer_use_macos.cli as cli_module

        captured_payloads: list[dict[str, object]] = []

        class FakeClient:
            def __init__(
                self,
                socket_path: str,
                *,
                token: str | None,
                timeout: float,
            ) -> None:
                self.socket_path = socket_path
                self.token = token
                self.timeout = timeout

            def request(
                self,
                payload: Mapping[str, object],
            ) -> list[dict[str, object]]:
                captured_payloads.append(dict(payload))
                action = payload.get("action")
                if action == "stream":
                    return [
                        {
                            "schema": SERVICE_EVENT_SCHEMA,
                            "requestId": payload.get("requestId"),
                            "status": "event",
                            "success": True,
                            "event": {
                                "schema": "app_control.event.v1",
                                "commandId": "cmd_stream",
                                "seq": 0,
                                "type": "started",
                                "phase": "readiness",
                                "summary": "started readiness",
                            },
                        },
                        {
                            "schema": SERVICE_RESPONSE_SCHEMA,
                            "requestId": payload.get("requestId"),
                            "status": "complete",
                            "success": True,
                        },
                    ]
                return [
                    {
                        "schema": SERVICE_RESPONSE_SCHEMA,
                        "requestId": payload.get("requestId"),
                        "status": "complete",
                        "success": True,
                    }
                ]

        original_client = cli_module.UnixSocketServiceClient
        try:
            cli_module.UnixSocketServiceClient = FakeClient  # type: ignore[assignment]
            submit_stdout = StringIO()
            with redirect_stdout(submit_stdout):
                submit_exit = cli_module.main(
                    [
                        "request",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--token",
                        "secret",
                        "--action",
                        "submit",
                        "--request-id",
                        "req_submit",
                        "--operation",
                        "readiness",
                        "--command-id",
                        "cmd_submit",
                    ]
                )
            poll_stdout = StringIO()
            with redirect_stdout(poll_stdout):
                poll_exit = cli_module.main(
                    [
                        "request",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--token",
                        "secret",
                        "--action",
                        "poll",
                        "--request-id",
                        "req_submit",
                    ]
                )
            stream_stdout = StringIO()
            with redirect_stdout(stream_stdout):
                stream_exit = cli_module.main(
                    [
                        "request",
                        "--socket-path",
                        "/tmp/app-control.sock",
                        "--token",
                        "secret",
                        "--action",
                        "stream",
                        "--request-id",
                        "req_stream",
                        "--operation",
                        "readiness",
                        "--command-id",
                        "cmd_stream",
                        "--sse",
                    ]
                )
        finally:
            cli_module.UnixSocketServiceClient = original_client

        self.assertEqual(submit_exit, 0)
        self.assertEqual(poll_exit, 0)
        self.assertEqual(stream_exit, 0)
        self.assertEqual(
            [payload["action"] for payload in captured_payloads],
            ["submit", "poll", "stream"],
        )
        submit_payload, poll_payload, stream_payload = captured_payloads
        self.assertEqual(submit_payload["requestId"], "req_submit")
        self.assertIsInstance(submit_payload["command"], dict)
        self.assertEqual(submit_payload["command"]["commandId"], "cmd_submit")
        self.assertEqual(poll_payload["requestId"], "req_submit")
        self.assertNotIn("command", poll_payload)
        self.assertEqual(stream_payload["requestId"], "req_stream")
        self.assertIsInstance(stream_payload["command"], dict)
        self.assertEqual(stream_payload["command"]["commandId"], "cmd_stream")
        self.assertIn("event: event", stream_stdout.getvalue())
        self.assertIn("event: complete", stream_stdout.getvalue())

    def test_package_serve_cli_requires_token_by_default(self) -> None:
        from contextlib import redirect_stderr
        from io import StringIO
        import computer_use_macos.cli as cli_module

        stderr = StringIO()

        with self.assertRaises(SystemExit) as raised:
            with redirect_stderr(stderr):
                cli_module.main(
                    [
                        "serve",
                        "--socket-path",
                        "/tmp/app-control.sock",
                    ]
                )

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("serve requires --token, --token-file", stderr.getvalue())

    def test_cli_uses_new_distribution_name(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "computer_use_macos",
                "--help",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: computer-use-macos", result.stdout)

    def test_cli_helper_init_and_build_create_app_bundle(self) -> None:
        with TemporaryDirectory() as tmpdir:
            helper_dir = Path(tmpdir) / "helper"
            env = _package_env()

            init_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "computer_use_macos",
                    "helper",
                    "init",
                    str(helper_dir),
                    "--name",
                    "Example Helper",
                    "--bundle-id",
                    "com.example.helper",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            build_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "computer_use_macos",
                    "helper",
                    "build",
                    str(helper_dir),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            init_payload = json.loads(init_result.stdout)
            build_payload = json.loads(build_result.stdout)
            app_path = Path(build_payload["appPath"])

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(build_result.returncode, 0, build_result.stderr)
            self.assertTrue(init_payload["outputDir"].endswith("helper"))
            self.assertTrue(app_path.name.endswith(".app"))
            self.assertTrue((app_path / "Contents" / "Info.plist").exists())
            self.assertTrue((app_path / "Contents" / "MacOS" / "helper").exists())
            self.assertTrue(
                (app_path / "Contents" / "Resources" / "helper_config.json").exists()
            )
            self.assertTrue(
                (app_path / "Contents" / "Resources" / "helper_main.py").exists()
            )
            launcher = app_path / "Contents" / "MacOS" / "helper"
            self.assertIn(
                "../Resources/helper_main.py",
                launcher.read_text(encoding="utf-8"),
            )

    def test_cli_helper_doctor_accepts_app_bundle_target(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        from computer_use_macos.cli import main as package_cli_main

        with TemporaryDirectory() as tmpdir:
            helper_dir = Path(tmpdir) / "helper"
            init_helper_template(
                helper_dir,
                config=HelperTemplateConfig(
                    name="Example Helper",
                    bundle_id="com.example.helper",
                ),
            )
            manifest = json.loads(
                (helper_dir / "helper_config.json").read_text(encoding="utf-8")
            )
            manifest.pop("tokenRef", None)
            manifest["token"] = "local-token"
            (helper_dir / "helper_config.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            app_path = build_helper_template(helper_dir)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = package_cli_main(
                    ["helper", "doctor", str(app_path), "--json"]
                )

        payload = json.loads(stdout.getvalue())
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(checks["manifest"]["status"], "ok")
        self.assertEqual(checks["helper_app"]["status"], "ok")
        self.assertEqual(
            checks["manifest"]["metadata"]["manifestPath"],
            str(app_path / "Contents" / "Resources" / "helper_config.json"),
        )
        self.assertEqual(checks["helper_app"]["metadata"]["appPath"], str(app_path))

    def test_textedit_smoke_example_has_dry_run_entrypoint(self) -> None:
        env = os.environ.copy()
        env["COMPUTER_USE_DRY_RUN"] = "1"
        env["COMPUTER_USE_TEXTEDIT_MESSAGE"] = "smoke test"
        pythonpath_parts = [
            str(ROOT / "src"),
            str(ROOT.parent / "app-control-protocol" / "src"),
        ]
        if env.get("PYTHONPATH"):
            pythonpath_parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "computer_use_macos.examples.textedit_smoke",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["dryRun"], True)
        self.assertEqual(report["app"], "TextEdit")
        self.assertEqual(
            [command["operation"] for command in report["commands"]],
            ["readiness", "open_app", "focus_app", "observe", "type_text"],
        )
        self.assertEqual(
            report["commands"][-1]["input"],
            {"targetApp": "TextEdit", "text": "smoke test"},
        )

    def test_textedit_smoke_failure_report_includes_frontmost_diagnostics(
        self,
    ) -> None:
        from app_control_protocol import ToolError
        from computer_use_macos.examples import textedit_smoke

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs

            def run_command(self, command: ToolCommand) -> ToolObservation:
                if command.operation == "observe":
                    return ToolObservation.failure(
                        command_id=command.command_id,
                        tool=command.tool,
                        operation=command.operation,
                        status=ToolStatus.NOT_READY,
                        error=ToolError(
                            failure_kind="target_not_frontmost",
                            message=(
                                "Target app is not frontmost: expected TextEdit, "
                                "got pycharm."
                            ),
                            retryable=True,
                        ),
                        observation={
                            "legacyStatus": "needs_user",
                            "metadata": {
                                "frontmost_app": "pycharm",
                                "frontmost_bundle_id": "com.jetbrains.pycharm",
                                "window_title": "Project",
                            },
                        },
                    )
                return ToolObservation.ok(
                    command_id=command.command_id,
                    tool=command.tool,
                    operation=command.operation,
                    summary="ok",
                )

        original_client = textedit_smoke.ComputerUseClient
        old_dry_run = os.environ.pop("COMPUTER_USE_DRY_RUN", None)
        old_attempts = os.environ.get("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS")
        old_delay = os.environ.get("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS")
        os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS"] = "2"
        os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS"] = "0"
        stdout = StringIO()
        try:
            textedit_smoke.ComputerUseClient = FakeClient  # type: ignore[assignment]
            with redirect_stdout(stdout):
                exit_code = textedit_smoke.main([])
        finally:
            textedit_smoke.ComputerUseClient = original_client
            if old_dry_run is not None:
                os.environ["COMPUTER_USE_DRY_RUN"] = old_dry_run
            if old_attempts is None:
                os.environ.pop("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS", None)
            else:
                os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS"] = old_attempts
            if old_delay is None:
                os.environ.pop("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS", None)
            else:
                os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS"] = old_delay

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["dryRun"], False)
        self.assertEqual(report["success"], False)
        self.assertEqual(report["failedCommandId"], "cmd_textedit_observe")
        self.assertEqual(report["failurePhase"], "observe")
        self.assertEqual(report["failureKind"], "target_not_frontmost")
        self.assertEqual(report["frontmostApp"], "pycharm")
        self.assertEqual(report["frontmostBundleId"], "com.jetbrains.pycharm")
        self.assertEqual(report["windowTitle"], "Project")
        self.assertEqual(
            [retry["command"] for retry in report["retryObservations"]],
            ["observe", "focus_app"],
        )

    def test_textedit_smoke_retries_transient_frontmost_failure(self) -> None:
        from app_control_protocol import ToolError
        from computer_use_macos.examples import textedit_smoke

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs
                self.observe_calls = 0

            def run_command(self, command: ToolCommand) -> ToolObservation:
                if command.operation == "observe":
                    self.observe_calls += 1
                    if self.observe_calls == 1:
                        return ToolObservation.failure(
                            command_id=command.command_id,
                            tool=command.tool,
                            operation=command.operation,
                            status=ToolStatus.NOT_READY,
                            error=ToolError(
                                failure_kind="target_not_frontmost",
                                message=(
                                    "Target app is not frontmost: expected TextEdit, "
                                    "got pycharm."
                                ),
                                retryable=True,
                            ),
                            observation={
                                "metadata": {
                                    "frontmost_app": "pycharm",
                                },
                            },
                        )
                observation = {"submitted": False} if command.operation == "type_text" else {}
                return ToolObservation.ok(
                    command_id=command.command_id,
                    tool=command.tool,
                    operation=command.operation,
                    summary="ok",
                    observation=observation,
                )

        original_client = textedit_smoke.ComputerUseClient
        old_dry_run = os.environ.pop("COMPUTER_USE_DRY_RUN", None)
        old_attempts = os.environ.get("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS")
        old_delay = os.environ.get("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS")
        os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS"] = "2"
        os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS"] = "0"
        stdout = StringIO()
        try:
            textedit_smoke.ComputerUseClient = FakeClient  # type: ignore[assignment]
            with redirect_stdout(stdout):
                exit_code = textedit_smoke.main([])
        finally:
            textedit_smoke.ComputerUseClient = original_client
            if old_dry_run is not None:
                os.environ["COMPUTER_USE_DRY_RUN"] = old_dry_run
            if old_attempts is None:
                os.environ.pop("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS", None)
            else:
                os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS"] = old_attempts
            if old_delay is None:
                os.environ.pop("COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS", None)
            else:
                os.environ["COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS"] = old_delay

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["success"], True)
        self.assertEqual(
            [observation["operation"] for observation in report["observations"]],
            ["readiness", "open_app", "focus_app", "observe", "type_text"],
        )
        self.assertEqual(
            [retry["command"] for retry in report["retryObservations"]],
            ["observe", "focus_app"],
        )

    def test_project_metadata_declares_distribution_boundary(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())

        self.assertEqual(project["project"]["name"], "computer-use-macos")
        package_data = project["tool"]["setuptools"]["package-data"]
        self.assertIn("py.typed", package_data["computer_use_macos"])
        self.assertIn(
            "app-control-protocol>=0.1.0",
            project["project"]["dependencies"],
        )
        self.assertNotIn(
            "macos-computer-use>=0.1.0",
            project["project"]["dependencies"],
        )

    def test_source_has_no_product_or_llm_dependency_imports(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for term in BANNED_TERMS:
                with self.subTest(path=path, term=term):
                    self.assertNotIn(term, text)
            for import_term in BANNED_IMPORTS:
                with self.subTest(path=path, import_term=import_term):
                    self.assertNotIn(import_term, text)

    def test_failure_kinds_are_declared_as_public_contract(self) -> None:
        failure_kinds = set(COMPUTER_USE_FAILURE_KINDS)
        self.assertTrue(failure_kinds)
        self.assertEqual(len(failure_kinds), len(COMPUTER_USE_FAILURE_KINDS))

        direct_statuses = {
            status.value for status in ComputerUseStatus if status is not ComputerUseStatus.OK
        }
        readiness_statuses = {
            status.value
            for status in ComputerUseReadinessStatus
            if status is not ComputerUseReadinessStatus.READY
        }
        self.assertLessEqual(direct_statuses, failure_kinds)
        self.assertLessEqual(readiness_statuses, failure_kinds)

        source_paths = (
            ROOT / "src" / "computer_use_macos" / "client.py",
            ROOT / "src" / "computer_use_macos" / "policy.py",
            ROOT / "src" / "computer_use_macos" / "service.py",
            ROOT / "src" / "computer_use_macos" / "helper" / "template.py",
        )
        literal_kinds: set[str] = set()
        for path in source_paths:
            text = path.read_text(encoding="utf-8")
            literal_kinds.update(re.findall(r'failure_kind="([^"]+)"', text))
            literal_kinds.update(re.findall(r'risk_label="([^"]+)"', text))
            literal_kinds.update(re.findall(r'_service_failure\(\s*"([^"]+)"', text))
            literal_kinds.update(
                re.findall(r'_failure\(\s*command,\s*"([^"]+)"', text)
            )

        self.assertLessEqual(literal_kinds, failure_kinds)


def _coerce_command(command: ToolCommand | Mapping[str, object]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


def _assert_observation_timing(observation: ToolObservation) -> None:
    started_at = observation.timing["startedAt"]
    duration_ms = observation.timing["durationMs"]
    if not isinstance(started_at, str) or not started_at.endswith("Z"):
        raise AssertionError("timing.startedAt must be a UTC timestamp")
    if not isinstance(duration_ms, int) or duration_ms < 0:
        raise AssertionError("timing.durationMs must be a non-negative integer")


def _recording_helper_round_trip(received: list[dict[str, object]]) -> object:
    def round_trip(
        socket_path: Path,
        payload: Mapping[str, object],
        *,
        timeout: float,
    ) -> dict[str, object]:
        del socket_path, timeout
        received.append(dict(payload))
        command = payload["command"]
        assert isinstance(command, dict)
        response = ToolObservation.ok(
            command_id=str(command["commandId"]),
            tool=str(command["tool"]),
            operation=str(command["operation"]),
            summary="helper ok",
            observation={"servedBy": "test-helper"},
        )
        return {
            "schema": HELPER_RESPONSE_SCHEMA,
            "success": True,
            "observation": response.to_dict(),
        }

    return round_trip


def _package_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_parts = [
        str(ROOT / "src"),
        str(ROOT.parent / "app-control-protocol" / "src"),
    ]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


if __name__ == "__main__":
    unittest.main()
