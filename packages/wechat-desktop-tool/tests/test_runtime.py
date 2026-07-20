from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest
from unittest.mock import patch

from app_control_protocol import (
    ToolCommand,
    ToolError,
    ToolObservation,
    ToolStatus,
)

from wechat_desktop_tool import WeChatDesktopConfig, WeChatDesktopTool
from wechat_desktop_tool._runtime import (
    _PhaseEventCollector,
    _WeChatSelectorQueryRunner,
    WeChatToolRuntime,
)
from wechat_desktop_tool.profiles import load_selector_assets


class _RecordingAppControl:
    def __init__(self, responses: list[ToolObservation] | None = None) -> None:
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
        if self._responses:
            return self._responses.pop(0)
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary="ok",
        )


def _parent(*, timeout_ms: int | None = 4_321) -> ToolCommand:
    return ToolCommand(
        command_id="wechat-parent",
        tool="wechat.desktop",
        operation="inspect_window",
        timeout_ms=timeout_ms,
    )


class RuntimeTests(unittest.TestCase):
    def test_create_loads_assets_once_and_preserves_dependency_identity(
        self,
    ) -> None:
        app_control = _RecordingAppControl()
        config = WeChatDesktopConfig()
        assets = load_selector_assets()

        with patch(
            "wechat_desktop_tool._runtime.load_selector_assets",
            return_value=assets,
        ) as loader:
            runtime = WeChatToolRuntime.create(app_control, config)

        loader.assert_called_once_with(config.selector_profile_path)
        self.assertIs(runtime.app_control, app_control)
        self.assertIs(runtime.config, config)
        self.assertIs(runtime.selector_assets, assets)
        self.assertIs(runtime.control_map, assets.control_map)
        self.assertIs(runtime.selector_profile, assets.selector_profile)

    def test_helper_backend_rejection_keeps_exact_contract(self) -> None:
        config = WeChatDesktopConfig(computer_use_backend="helper")

        with self.assertRaisesRegex(
            ValueError,
            "wechat-desktop-tool selector APIs do not support "
            "computer_use.backend=helper in version 0.3.0; use direct or "
            "a direct-backed local service",
        ):
            WeChatToolRuntime.create(_RecordingAppControl(), config)

    def test_facade_private_state_aliases_are_read_only_runtime_views(self) -> None:
        app_control = _RecordingAppControl()
        tool = WeChatDesktopTool(app_control)

        self.assertIs(tool._app_control, app_control)
        self.assertIs(tool._config, tool._runtime.config)
        self.assertIs(tool._selector_assets, tool._runtime.selector_assets)
        self.assertIs(tool._control_map, tool._runtime.control_map)
        self.assertIs(tool._selector_profile, tool._runtime.selector_profile)
        with self.assertRaises(AttributeError):
            setattr(tool, "_config", WeChatDesktopConfig())

    def test_input_and_parent_command_builders_remain_exact(self) -> None:
        runtime = WeChatToolRuntime.create(_RecordingAppControl())

        self.assertEqual(
            runtime._open_app_input(hidden=True),
            {
                "app": "WeChat",
                "bundleId": "com.tencent.xinWeChat",
                "hidden": True,
            },
        )
        self.assertEqual(
            runtime._target_app_input(key="Return"),
            {
                "targetApp": "WeChat",
                "bundleId": "com.tencent.xinWeChat",
                "key": "Return",
            },
        )
        child = runtime._command(
            "read_visible_messages",
            {"limit": 30},
            parent=_parent(),
        )
        self.assertEqual(child.command_id, "wechat-parent:read_visible_messages")
        self.assertEqual(child.timeout_ms, 4_321)
        self.assertEqual(child.input, {"limit": 30})

    def test_app_control_command_keeps_envelope_and_phase_event(self) -> None:
        app_control = _RecordingAppControl()
        runtime = WeChatToolRuntime.create(app_control)
        parent = _parent()
        events = _PhaseEventCollector(parent, observer=None)

        result = runtime._app_control_command(
            parent,
            phase="query_window",
            operation="accessibility_query",
            input={"targetApp": "WeChat"},
            command_metadata={"source": "test"},
            phase_events=events,
        )

        self.assertTrue(result.success)
        self.assertEqual(len(app_control.commands), 1)
        child = app_control.commands[0]
        self.assertEqual(child.command_id, "wechat-parent:query_window")
        self.assertEqual(child.tool, "macos.computer_use")
        self.assertEqual(child.operation, "accessibility_query")
        self.assertEqual(child.input, {"targetApp": "WeChat"})
        self.assertEqual(child.timeout_ms, 4_321)
        self.assertEqual(
            child.metadata,
            {
                "sourceTool": "wechat.desktop",
                "parentCommandId": "wechat-parent",
                "phase": "query_window",
                "source": "test",
            },
        )
        self.assertEqual(len(events.events), 1)
        self.assertEqual(events.events[0].phase, "query_window")
        self.assertEqual(events.events[0].seq, 1)

    def test_selector_runner_preserves_phase_counter_and_failure_shape(self) -> None:
        failure = ToolObservation.failure(
            command_id="child",
            tool="macos.computer_use",
            operation="accessibility_query",
            status=ToolStatus.TIMEOUT,
            error=ToolError(
                failure_kind="accessibility_query_timeout",
                message="timed out",
                retryable=True,
            ),
        )
        app_control = _RecordingAppControl([failure, failure])
        runtime = WeChatToolRuntime.create(app_control)
        evidence: dict[str, Any] = {}
        runner = _WeChatSelectorQueryRunner(
            runtime,
            _parent(),
            evidence=evidence,
            phase_prefix="selectors.contacts",
            phase_events=None,
        )

        first = runner(root={"kind": "focusedWindow"}, query={"limit": 1})
        second = runner(root={"kind": "focusedWindow"}, query={"limit": 1})

        self.assertEqual(
            [command.command_id for command in app_control.commands],
            [
                "wechat-parent:selectors.contacts:1",
                "wechat-parent:selectors.contacts:2",
            ],
        )
        self.assertEqual(
            list(evidence),
            ["selectors.contacts:1", "selectors.contacts:2"],
        )
        self.assertEqual(first, second)
        self.assertEqual(first["available"], False)
        self.assertEqual(first["failureKind"], "accessibility_query_timeout")
        self.assertEqual(first["retryable"], True)
        self.assertEqual(first["nodes"], [])


if __name__ == "__main__":
    unittest.main()
