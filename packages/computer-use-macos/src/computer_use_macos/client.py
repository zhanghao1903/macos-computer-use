"""Public client for conservative macOS computer-use primitives."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from app_control_protocol import AppControlConfig, HelperConfig

from .commands import CommandRunner, SubprocessCommandRunner
from .models import (
    ComputerUseOperation,
    ComputerUseReadiness,
    ComputerUseReadinessStatus,
    ComputerUseResult,
    ComputerUseStatus,
)
from .policy import SafetyPolicy
from .readiness import DefaultPermissionProbe, PermissionProbe, build_readiness

if TYPE_CHECKING:
    from app_control_protocol import (
        ToolCommand,
        ToolEvent,
        ToolObserver,
        ToolObservation,
    )


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _bounded(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


def _timeout_metadata(
    result: Any,
    timeout: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload["timeout_seconds"] = timeout
    if result.stdout:
        payload["stdout"] = _bounded(result.stdout, 1000)
    if result.stderr:
        payload["stderr"] = _bounded(result.stderr, 1000)
    return payload


def _timed_out_result(
    operation: ComputerUseOperation,
    summary: str,
    result: Any,
    timeout: float,
    *,
    metadata: dict[str, Any] | None = None,
) -> ComputerUseResult:
    return ComputerUseResult.timed_out(
        operation,
        summary,
        metadata=_timeout_metadata(result, timeout, metadata),
    )


def _target_metadata(
    observed: ComputerUseResult,
    target_app: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "target_summary": observed.summary,
    }
    if target_app is not None:
        metadata["target_app"] = target_app
    if observed.snapshot_id is not None:
        metadata["target_snapshot_id"] = observed.snapshot_id
    for key in ("bundle_id", "frontmost_bundle_id", "frontmost_app", "window_title"):
        value = observed.metadata.get(key)
        if value is not None:
            metadata[key] = value
    return metadata


def _app_metadata(app: str, bundle_id: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"app": app}
    if bundle_id is not None:
        metadata["bundle_id"] = bundle_id
    return metadata


def _target_identity_metadata(
    target_app: str | None,
    bundle_id: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if target_app is not None:
        metadata["target_app"] = target_app
    if bundle_id is not None:
        metadata["bundle_id"] = bundle_id
    return metadata


_KEY_CODES = {
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "escape": 53,
    "esc": 53,
    "delete": 51,
    "backspace": 51,
    "forwarddelete": 117,
    "forward_delete": 117,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "page_up": 116,
    "pagedown": 121,
    "page_down": 121,
    "left": 123,
    "leftarrow": 123,
    "left_arrow": 123,
    "right": 124,
    "rightarrow": 124,
    "right_arrow": 124,
    "down": 125,
    "downarrow": 125,
    "down_arrow": 125,
    "up": 126,
    "uparrow": 126,
    "up_arrow": 126,
}

_MODIFIER_NAMES = {
    "command": "command down",
    "cmd": "command down",
    "meta": "command down",
    "control": "control down",
    "ctrl": "control down",
    "option": "option down",
    "alt": "option down",
    "shift": "shift down",
}

_ACCESSIBILITY_ROLES = {
    "button": "button",
    "checkbox": "checkbox",
    "check_box": "checkbox",
    "menuitem": "menu item",
    "menu_item": "menu item",
    "radio_button": "radio button",
    "radiobutton": "radio button",
    "pop_up_button": "pop up button",
    "popup_button": "pop up button",
    "text_field": "text field",
    "textfield": "text field",
}


class MacOSComputerUseClient:
    """Small, LLM-free macOS automation client.

    The client exposes conservative primitives only. It never stores raw screen
    contents and does not own user confirmation.
    """

    def __init__(
        self,
        *,
        allowed_apps: Iterable[str] | Mapping[str, str | None] = (),
        enabled: bool = True,
        allow_coordinate_click: bool = False,
        screen_recording_required: bool = False,
        max_text_chars: int = 4000,
        default_timeout_ms: int = 10_000,
        probe: PermissionProbe | None = None,
        runner: CommandRunner | None = None,
        policy: SafetyPolicy | None = None,
    ) -> None:
        if default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms must be positive")
        self._enabled = enabled
        self._allow_coordinate_click = allow_coordinate_click
        self._screen_recording_required = screen_recording_required
        self._max_text_chars = max_text_chars
        self._default_timeout_ms = default_timeout_ms
        self._probe = probe or DefaultPermissionProbe()
        self._runner = runner or SubprocessCommandRunner()
        self._policy = policy or SafetyPolicy()
        self._allowed_apps = self._normalize_allowed_apps(allowed_apps)

    @classmethod
    def from_config(
        cls,
        config: "AppControlConfig | Mapping[str, Any] | str | Path | None" = None,
        *,
        env: Mapping[str, str] | None = None,
        probe: PermissionProbe | None = None,
        runner: CommandRunner | None = None,
        policy: SafetyPolicy | None = None,
    ) -> Any:
        """Build a client from shared app-control configuration."""

        app_config = _load_app_control_config(config, env=env)
        computer_use = app_config.computer_use
        backend = computer_use.backend.strip().lower()
        enabled = backend not in {"", "disabled", "none", "off"}
        if enabled and backend == "helper":
            return _helper_transport_from_config(app_config, runner=runner)
        if enabled and backend not in _DIRECT_BACKENDS:
            raise ValueError(
                "MacOSComputerUseClient.from_config supports direct or helper "
                f"backends, got: {computer_use.backend}"
            )
        return cls(
            allowed_apps=_computer_use_allowed_apps(computer_use),
            enabled=enabled,
            allow_coordinate_click=computer_use.allow_coordinate_click,
            screen_recording_required=computer_use.screen_recording_required,
            default_timeout_ms=computer_use.timeout_ms,
            probe=probe,
            runner=runner,
            policy=policy,
        )

    @classmethod
    def from_helper_manifest(
        cls,
        manifest: object,
        *,
        timeout: float = 10.0,
        expected_bundle_id: str | None = None,
        expected_api_version: str | None = None,
    ) -> Any:
        """Build a helper transport client from a helper manifest."""

        if timeout <= 0:
            raise ValueError("timeout must be positive")
        helper_manifest = _coerce_helper_manifest(manifest)
        helper_manifest.validate_identity(
            expected_bundle_id=expected_bundle_id,
            expected_api_version=expected_api_version,
        )
        from .helper import helper_transport_from_manifest

        return helper_transport_from_manifest(helper_manifest, timeout=timeout)

    @staticmethod
    def _normalize_allowed_apps(
        allowed_apps: Iterable[str] | Mapping[str, str | None],
    ) -> dict[str, str | None]:
        if isinstance(allowed_apps, Mapping):
            return {name: bundle_id for name, bundle_id in allowed_apps.items()}
        return {name: None for name in allowed_apps}

    def readiness(self) -> ComputerUseReadiness:
        return build_readiness(
            enabled=self._enabled,
            probe=self._probe,
            screen_recording_required=self._screen_recording_required,
        )

    def run_command(
        self,
        command: "ToolCommand | Mapping[str, Any]",
        *,
        observer: "ToolObserver | None" = None,
    ) -> "ToolObservation":
        """Run one app-control protocol command and return an observation."""

        (
            tool_command_cls,
            tool_observation_cls,
            tool_status_cls,
            tool_error_cls,
            tool_event_cls,
            tool_event_type_cls,
        ) = _protocol_models()
        tool_command = _coerce_tool_command(command, tool_command_cls)
        started_at = _utc_now()
        started_monotonic = time.monotonic()
        _emit_observer(
            observer,
            _started_event(
                tool_command,
                tool_event_cls=tool_event_cls,
                tool_event_type_cls=tool_event_type_cls,
            ),
        )
        observation = self._execute_protocol_command(
            tool_command,
            tool_observation_cls=tool_observation_cls,
            tool_status_cls=tool_status_cls,
            tool_error_cls=tool_error_cls,
        )
        observation = _with_timing(
            observation,
            started_at=started_at,
            duration_ms=_duration_ms(started_monotonic),
        )
        _emit_observer(
            observer,
            _observation_event(
                tool_command,
                observation,
                tool_event_cls=tool_event_cls,
                tool_event_type_cls=tool_event_type_cls,
            ),
        )
        return observation

    def run_stream(
        self,
        command: "ToolCommand | Mapping[str, Any]",
        *,
        observer: "ToolObserver | None" = None,
    ) -> "Iterator[ToolEvent]":
        """Run one command and yield protocol events."""

        (
            tool_command_cls,
            tool_observation_cls,
            tool_status_cls,
            tool_error_cls,
            tool_event_cls,
            tool_event_type_cls,
        ) = _protocol_models()
        tool_command = _coerce_tool_command(command, tool_command_cls)
        started_at = _utc_now()
        started_monotonic = time.monotonic()
        started = _started_event(
            tool_command,
            tool_event_cls=tool_event_cls,
            tool_event_type_cls=tool_event_type_cls,
        )
        _emit_observer(observer, started)
        yield started
        observation = self._execute_protocol_command(
            tool_command,
            tool_observation_cls=tool_observation_cls,
            tool_status_cls=tool_status_cls,
            tool_error_cls=tool_error_cls,
        )
        observation = _with_timing(
            observation,
            started_at=started_at,
            duration_ms=_duration_ms(started_monotonic),
        )
        final_event = _observation_event(
            tool_command,
            observation,
            tool_event_cls=tool_event_cls,
            tool_event_type_cls=tool_event_type_cls,
        )
        _emit_observer(observer, final_event)
        yield final_event

    def _execute_protocol_command(
        self,
        tool_command: Any,
        *,
        tool_observation_cls: type[Any],
        tool_status_cls: type[Any],
        tool_error_cls: type[Any],
    ) -> Any:
        timeout = _timeout_seconds(getattr(tool_command, "timeout_ms", None))
        operation = tool_command.operation
        payload = tool_command.input
        if tool_command.tool not in _SUPPORTED_PROTOCOL_TOOLS:
            return _protocol_failure(
                command=tool_command,
                status=tool_status_cls.FAILED,
                failure_kind="unsupported_tool",
                message=(
                    "computer-use-macos cannot execute tool envelope: "
                    f"{tool_command.tool}"
                ),
                retryable=False,
                tool_observation_cls=tool_observation_cls,
                tool_error_cls=tool_error_cls,
            )
        try:
            bundle_id = _bundle_id_from_payload(payload)
            if operation == "readiness":
                return _readiness_to_protocol_observation(
                    command=tool_command,
                    readiness=self.readiness(),
                    tool_observation_cls=tool_observation_cls,
                    tool_status_cls=tool_status_cls,
                    tool_error_cls=tool_error_cls,
                )
            if operation == "open_app":
                app = _required_string(payload, "app", "target")
                result = self.open_app(
                    app,
                    bundle_id=bundle_id,
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "focus_app":
                app = _required_string(payload, "app", "target")
                result = self.focus_app(
                    app,
                    bundle_id=bundle_id,
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "observe":
                result = self.observe(
                    target_app=_optional_string(
                        payload,
                        "targetApp",
                        "target_app",
                        "app",
                    ),
                    bundle_id=bundle_id,
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "type_text":
                text = _required_string(payload, "text")
                result = self.type_text(
                    text,
                    target_app=_optional_string(
                        payload,
                        "targetApp",
                        "target_app",
                        "app",
                    ),
                    bundle_id=bundle_id,
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "click":
                target_app = _optional_string(
                    payload,
                    "targetApp",
                    "target_app",
                    "app",
                )
                snapshot_id = _optional_string(
                    payload,
                    "snapshotId",
                    "snapshot_id",
                )
                selector = _accessibility_selector_from_payload(payload)
                coordinate = _coordinate_from_payload(payload)
                if selector is not None:
                    result = self.click_accessibility(
                        selector,
                        target_app=target_app,
                        bundle_id=bundle_id,
                        snapshot_id=snapshot_id,
                        timeout=timeout or self._default_timeout,
                    )
                elif coordinate is not None:
                    result = self.click_coordinate(
                        coordinate[0],
                        coordinate[1],
                        target_app=target_app,
                        bundle_id=bundle_id,
                        snapshot_id=snapshot_id,
                        timeout=timeout or self._default_timeout,
                    )
                else:
                    target = _required_string(payload, "target", "text")
                    result = self.click(
                        target,
                        target_app=target_app,
                        bundle_id=bundle_id,
                        snapshot_id=snapshot_id,
                        timeout=timeout or self._default_timeout,
                    )
            elif operation == "press_key":
                result = self.press_key(
                    _press_key_from_payload(payload),
                    target_app=_optional_string(
                        payload,
                        "targetApp",
                        "target_app",
                        "app",
                    ),
                    bundle_id=bundle_id,
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "hotkey":
                result = self.hotkey(
                    _hotkey_from_payload(payload),
                    target_app=_optional_string(
                        payload,
                        "targetApp",
                        "target_app",
                        "app",
                    ),
                    bundle_id=bundle_id,
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "wait":
                result = self.wait(seconds=_seconds(payload, default=1.0))
            else:
                return _protocol_failure(
                    command=tool_command,
                    status=tool_status_cls.FAILED,
                    failure_kind="unsupported_operation",
                    message=(
                        "computer-use-macos does not support operation: "
                        f"{operation}"
                    ),
                    retryable=False,
                    tool_observation_cls=tool_observation_cls,
                    tool_error_cls=tool_error_cls,
                )
        except (TypeError, ValueError) as exc:
            return _protocol_failure(
                command=tool_command,
                status=tool_status_cls.FAILED,
                failure_kind="invalid_input",
                message=str(exc),
                retryable=False,
                tool_observation_cls=tool_observation_cls,
                tool_error_cls=tool_error_cls,
            )

        return _result_to_protocol_observation(
            command=tool_command,
            result=result,
            tool_observation_cls=tool_observation_cls,
            tool_status_cls=tool_status_cls,
            tool_error_cls=tool_error_cls,
        )

    @property
    def _default_timeout(self) -> float:
        return self._default_timeout_ms / 1000.0

    def open_app(
        self,
        app: str,
        *,
        bundle_id: str | None = None,
        timeout: float = 10.0,
    ) -> ComputerUseResult:
        metadata = _app_metadata(app, bundle_id)
        if not self._enabled:
            return ComputerUseResult.not_available(
                ComputerUseOperation.OPEN_APP,
                "macOS computer-use backend is disabled.",
            )
        if self._probe.platform_name() != "Darwin":
            return ComputerUseResult.not_available(
                ComputerUseOperation.OPEN_APP,
                "macOS open_app is unsupported on this platform.",
            )
        if app not in self._allowed_apps:
            return ComputerUseResult.blocked(
                ComputerUseOperation.OPEN_APP,
                f"App is not allowlisted: {app}",
                metadata=metadata,
            )
        expected_bundle_id = self._allowed_apps.get(app)
        if expected_bundle_id and bundle_id and expected_bundle_id != bundle_id:
            return ComputerUseResult.blocked(
                ComputerUseOperation.OPEN_APP,
                f"App bundle id is not allowlisted: {bundle_id}",
                metadata={**metadata, "expected_bundle_id": expected_bundle_id},
            )

        args = ["open", "-b", bundle_id] if bundle_id else ["open", "-a", app]
        result = self._runner.run(args, timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.OPEN_APP,
                "Timed out opening allowlisted app.",
                result,
                timeout,
                metadata=metadata,
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.OPEN_APP,
                "Failed to open allowlisted app.",
                metadata={**metadata, "stderr": _bounded(result.stderr, 1000)},
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.OPEN_APP,
            f"Opened app: {app}",
            metadata=metadata,
        )

    def focus_app(
        self,
        app: str,
        *,
        bundle_id: str | None = None,
        timeout: float = 10.0,
    ) -> ComputerUseResult:
        metadata = _app_metadata(app, bundle_id)
        if not self._enabled:
            return ComputerUseResult.not_available(
                ComputerUseOperation.FOCUS_APP,
                "macOS computer-use backend is disabled.",
            )
        if self._probe.platform_name() != "Darwin":
            return ComputerUseResult.not_available(
                ComputerUseOperation.FOCUS_APP,
                "macOS focus_app is unsupported on this platform.",
            )
        if app not in self._allowed_apps:
            return ComputerUseResult.blocked(
                ComputerUseOperation.FOCUS_APP,
                f"App is not allowlisted: {app}",
                metadata=metadata,
            )
        expected_bundle_id = self._allowed_apps.get(app)
        if expected_bundle_id and bundle_id and expected_bundle_id != bundle_id:
            return ComputerUseResult.blocked(
                ComputerUseOperation.FOCUS_APP,
                f"App bundle id is not allowlisted: {bundle_id}",
                metadata={**metadata, "expected_bundle_id": expected_bundle_id},
            )

        if bundle_id:
            script = (
                f"tell application id {_applescript_string(bundle_id)} to activate\n"
            )
        else:
            script = f"tell application {_applescript_string(app)} to activate\n"
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.FOCUS_APP,
                "Timed out focusing allowlisted app.",
                result,
                timeout,
                metadata=metadata,
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.FOCUS_APP,
                "Failed to focus allowlisted app.",
                metadata={**metadata, "stderr": _bounded(result.stderr, 1000)},
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.FOCUS_APP,
            f"Focused app: {app}",
            metadata={**metadata, "action_attempted": True},
        )

    def observe(
        self,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        readiness = self.readiness()
        if readiness.status != ComputerUseReadinessStatus.READY:
            return ComputerUseResult.not_available(
                ComputerUseOperation.OBSERVE,
                "macOS observe is unavailable until readiness is ready.",
                metadata={"readiness": readiness.to_dict()},
            )

        script = (
            'tell application "System Events"\n'
            '  set frontApp to first application process whose frontmost is true\n'
            "  set appName to name of frontApp\n"
            "  set bundleId to \"\"\n"
            "  try\n"
            "    set bundleId to bundle identifier of frontApp\n"
            "  end try\n"
            "  set windowTitle to \"\"\n"
            "  try\n"
            "    set windowTitle to name of front window of frontApp\n"
            "  end try\n"
            '  return appName & "\\n" & windowTitle & "\\n" & bundleId\n'
            "end tell\n"
        )
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.OBSERVE,
                "Timed out observing frontmost app via Accessibility.",
                result,
                timeout,
                metadata=_target_identity_metadata(target_app, bundle_id),
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.OBSERVE,
                "Failed to observe frontmost app via Accessibility.",
                metadata={"stderr": _bounded(result.stderr, 1000)},
            )

        lines = result.stdout.splitlines()
        app_name = lines[0].strip() if lines else ""
        window_title = lines[1].strip() if len(lines) > 1 else ""
        frontmost_bundle_id = lines[2].strip() if len(lines) > 2 else ""
        observation_metadata = {
            **_target_identity_metadata(target_app, bundle_id),
            "frontmost_app": app_name,
            "frontmost_bundle_id": frontmost_bundle_id,
            "window_title": window_title,
        }

        if bundle_id and frontmost_bundle_id and frontmost_bundle_id != bundle_id:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.OBSERVE,
                (
                    "Target app bundle id is not frontmost: "
                    f"expected {bundle_id}, got {frontmost_bundle_id}."
                ),
                metadata=observation_metadata,
            )
        if (
            target_app
            and (not bundle_id or not frontmost_bundle_id)
            and app_name != target_app
        ):
            return ComputerUseResult.needs_user(
                ComputerUseOperation.OBSERVE,
                f"Target app is not frontmost: expected {target_app}, got {app_name}.",
                metadata=observation_metadata,
            )

        snapshot_id = f"frontmost:{app_name}:{window_title}"
        summary = f"Frontmost app: {app_name or 'unknown'}."
        if window_title:
            summary += f" Window: {window_title}."
        return ComputerUseResult.ok(
            ComputerUseOperation.OBSERVE,
            summary,
            text_extract=summary,
            snapshot_id=snapshot_id,
            metadata=observation_metadata,
        )

    def type_text(
        self,
        text: str,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        if len(text) > self._max_text_chars:
            return ComputerUseResult.blocked(
                ComputerUseOperation.TYPE_TEXT,
                "Text exceeds max_text_chars.",
                metadata={"max_text_chars": self._max_text_chars},
            )
        if "\n" in text or "\r" in text:
            return ComputerUseResult.blocked(
                ComputerUseOperation.TYPE_TEXT,
                "type_text does not submit or press Enter; newline text is blocked.",
            )

        risk = self._policy.classify(ComputerUseOperation.TYPE_TEXT, text=text)
        if risk.level.value == "high":
            return ComputerUseResult.blocked(
                ComputerUseOperation.TYPE_TEXT,
                risk.reason,
                risk=risk,
            )

        target_metadata: dict[str, Any] = {}
        if target_app or bundle_id:
            observed = self.observe(
                target_app=target_app,
                bundle_id=bundle_id,
                timeout=timeout,
            )
            if not observed.success:
                return observed
            target_metadata = _target_metadata(observed, target_app)
        else:
            readiness = self.readiness()
            if readiness.status != ComputerUseReadinessStatus.READY:
                return ComputerUseResult.not_available(
                    ComputerUseOperation.TYPE_TEXT,
                    "macOS type_text is unavailable until readiness is ready.",
                    metadata={"readiness": readiness.to_dict()},
                )

        script = _type_text_script(text)
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.TYPE_TEXT,
                "Timed out typing text into the focused editable target.",
                result,
                timeout,
                metadata={
                    **target_metadata,
                    "chars": len(text),
                    "submitted": False,
                    "input_method": "clipboard",
                    "action_attempted": True,
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.TYPE_TEXT,
                "Failed to type text into the focused editable target.",
                metadata={
                    **target_metadata,
                    "chars": len(text),
                    "submitted": False,
                    "input_method": "clipboard",
                    "action_attempted": True,
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.TYPE_TEXT,
            "Typed text into the focused editable target.",
            metadata={
                **target_metadata,
                "chars": len(text),
                "submitted": False,
                "input_method": "clipboard",
                "action_attempted": True,
            },
        )

    def press_key(
        self,
        key: str,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        normalized_key = _normalize_key_name(key)
        readiness_result, target_metadata = self._keyboard_preflight(
            ComputerUseOperation.PRESS_KEY,
            target_app=target_app,
            bundle_id=bundle_id,
            timeout=timeout,
        )
        if readiness_result is not None:
            return readiness_result

        script = _keyboard_script(normalized_key)
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.PRESS_KEY,
                "Timed out pressing key in the focused target.",
                result,
                timeout,
                metadata={
                    **target_metadata,
                    "key": normalized_key,
                    **_target_identity_metadata(target_app, bundle_id),
                    "action_attempted": True,
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.PRESS_KEY,
                "Failed to press key in the focused target.",
                metadata={
                    **target_metadata,
                    "key": normalized_key,
                    **_target_identity_metadata(target_app, bundle_id),
                    "action_attempted": True,
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.PRESS_KEY,
            f"Pressed key: {normalized_key}.",
            metadata={
                **target_metadata,
                "key": normalized_key,
                **_target_identity_metadata(target_app, bundle_id),
                "action_attempted": True,
            },
        )

    def hotkey(
        self,
        keys: Iterable[str],
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        normalized_keys = tuple(_normalize_key_name(key) for key in keys)
        modifiers, key = _split_hotkey(normalized_keys)
        readiness_result, target_metadata = self._keyboard_preflight(
            ComputerUseOperation.HOTKEY,
            target_app=target_app,
            bundle_id=bundle_id,
            timeout=timeout,
        )
        if readiness_result is not None:
            return readiness_result

        script = _keyboard_script(key, modifiers=modifiers)
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.HOTKEY,
                "Timed out pressing hotkey in the focused target.",
                result,
                timeout,
                metadata={
                    **target_metadata,
                    "keys": list(normalized_keys),
                    **_target_identity_metadata(target_app, bundle_id),
                    "action_attempted": True,
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.HOTKEY,
                "Failed to press hotkey in the focused target.",
                metadata={
                    **target_metadata,
                    "keys": list(normalized_keys),
                    **_target_identity_metadata(target_app, bundle_id),
                    "action_attempted": True,
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.HOTKEY,
            f"Pressed hotkey: {'+'.join(normalized_keys)}.",
            metadata={
                **target_metadata,
                "keys": list(normalized_keys),
                "key": key,
                "modifiers": list(modifiers),
                **_target_identity_metadata(target_app, bundle_id),
                "action_attempted": True,
            },
        )

    def _keyboard_preflight(
        self,
        operation: ComputerUseOperation,
        *,
        target_app: str | None,
        bundle_id: str | None,
        timeout: float,
    ) -> tuple[ComputerUseResult | None, dict[str, Any]]:
        if target_app or bundle_id:
            observed = self.observe(
                target_app=target_app,
                bundle_id=bundle_id,
                timeout=timeout,
            )
            if not observed.success:
                return (
                    ComputerUseResult(
                        operation=operation,
                        status=observed.status,
                        success=False,
                        summary=observed.summary,
                        text_extract=observed.text_extract,
                        snapshot_id=observed.snapshot_id,
                        risk=observed.risk,
                        metadata=observed.metadata,
                    ),
                    {},
                )
            return None, _target_metadata(observed, target_app)
        readiness = self.readiness()
        if readiness.status != ComputerUseReadinessStatus.READY:
            return (
                ComputerUseResult.not_available(
                    operation,
                    f"macOS {operation.value} is unavailable until readiness is ready.",
                    metadata={"readiness": readiness.to_dict()},
                ),
                {},
            )
        return None, {}

    def click(
        self,
        target: str,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        snapshot_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        risk = self._policy.classify(ComputerUseOperation.CLICK, target=target)
        if risk.requires_confirmation:
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                "computer-use action requires confirmation",
                risk=risk,
                metadata={
                    "confirmation_required": True,
                    "confirmation_title": "Confirm desktop action",
                    "confirmation_body": (
                        "Approve the requested click before it is executed."
                    ),
                },
            )
        if risk.level.value == "high":
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                risk.reason,
                risk=risk,
            )

        if not target_app:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.CLICK,
                "target_app is required for semantic click in this package version.",
                metadata={
                    "target": target,
                    **_target_identity_metadata(None, bundle_id),
                },
            )

        observed = self.observe(
            target_app=target_app,
            bundle_id=bundle_id,
            timeout=timeout,
        )
        if not observed.success:
            return observed
        if snapshot_id and observed.snapshot_id != snapshot_id:
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                "Target snapshot is stale.",
                metadata={"expected": snapshot_id, "actual": observed.snapshot_id},
            )

        script = (
            'tell application "System Events"\n'
            f"  tell process {_applescript_string(target_app)}\n"
            "    set frontmost to true\n"
            f"    click button {_applescript_string(target)} of front window\n"
            "  end tell\n"
            "end tell\n"
        )
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.CLICK,
                "Timed out clicking semantic target.",
                result,
                timeout,
                metadata={
                    "target": target,
                    **_target_identity_metadata(target_app, bundle_id),
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.CLICK,
                "Could not resolve a safe semantic button target.",
                metadata={
                    "target": target,
                    **_target_identity_metadata(target_app, bundle_id),
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.CLICK,
            "Clicked semantic target.",
            metadata={
                "target": target,
                **_target_identity_metadata(target_app, bundle_id),
            },
        )

    def click_accessibility(
        self,
        selector: Mapping[str, Any],
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        snapshot_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        normalized = _normalize_accessibility_selector(selector)
        target = _selector_target_text(normalized)
        risk = self._policy.classify(ComputerUseOperation.CLICK, target=target)
        if risk.requires_confirmation:
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                "computer-use action requires confirmation",
                risk=risk,
                metadata={
                    "confirmation_required": True,
                    "confirmation_title": "Confirm desktop action",
                    "confirmation_body": (
                        "Approve the requested click before it is executed."
                    ),
                },
            )
        if risk.level.value == "high":
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                risk.reason,
                risk=risk,
            )

        if not target_app:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.CLICK,
                "target_app is required for accessibility selector click.",
                metadata={
                    "selector": normalized,
                    **_target_identity_metadata(None, bundle_id),
                },
            )

        observed = self.observe(
            target_app=target_app,
            bundle_id=bundle_id,
            timeout=timeout,
        )
        if not observed.success:
            return observed
        if snapshot_id and observed.snapshot_id != snapshot_id:
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                "Target snapshot is stale.",
                metadata={"expected": snapshot_id, "actual": observed.snapshot_id},
            )

        script = _accessibility_click_script(target_app, normalized)
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.CLICK,
                "Timed out clicking accessibility selector.",
                result,
                timeout,
                metadata={
                    "selector": normalized,
                    **_target_identity_metadata(target_app, bundle_id),
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.CLICK,
                "Could not resolve a safe accessibility selector target.",
                metadata={
                    "selector": normalized,
                    **_target_identity_metadata(target_app, bundle_id),
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.CLICK,
            "Clicked accessibility selector target.",
            metadata={
                "selector": normalized,
                **_target_identity_metadata(target_app, bundle_id),
                "action_attempted": True,
            },
        )

    def click_coordinate(
        self,
        x: int,
        y: int,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        snapshot_id: str | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        x = _coordinate_int(x, "x")
        y = _coordinate_int(y, "y")
        target = f"{x},{y}"
        risk = self._policy.classify(
            ComputerUseOperation.CLICK,
            target=target,
            coordinate_click=True,
            allow_coordinate_click=self._allow_coordinate_click,
        )
        if risk.level.value == "high":
            return ComputerUseResult.blocked(
                ComputerUseOperation.CLICK,
                risk.reason,
                risk=risk,
                metadata={
                    "coordinateClick": True,
                    "x": x,
                    "y": y,
                    **_target_identity_metadata(target_app, bundle_id),
                },
            )

        if target_app or bundle_id:
            observed = self.observe(
                target_app=target_app,
                bundle_id=bundle_id,
                timeout=timeout,
            )
            if not observed.success:
                return observed
            if snapshot_id and observed.snapshot_id != snapshot_id:
                return ComputerUseResult.blocked(
                    ComputerUseOperation.CLICK,
                    "Target snapshot is stale.",
                    metadata={
                        "expected": snapshot_id,
                        "actual": observed.snapshot_id,
                        "coordinateClick": True,
                        "x": x,
                        "y": y,
                        **_target_identity_metadata(target_app, bundle_id),
                    },
                )
        else:
            readiness = self.readiness()
            if readiness.status != ComputerUseReadinessStatus.READY:
                return ComputerUseResult.not_available(
                    ComputerUseOperation.CLICK,
                    "macOS coordinate click is unavailable until readiness is ready.",
                    metadata={"readiness": readiness.to_dict()},
                )

        script = (
            'tell application "System Events"\n'
            f"  click at {{{x}, {y}}}\n"
            "end tell\n"
        )
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.CLICK,
                "Timed out clicking screen coordinate.",
                result,
                timeout,
                metadata={
                    "coordinateClick": True,
                    "x": x,
                    "y": y,
                    **_target_identity_metadata(target_app, bundle_id),
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.CLICK,
                "Failed to click screen coordinate.",
                metadata={
                    "coordinateClick": True,
                    "x": x,
                    "y": y,
                    **_target_identity_metadata(target_app, bundle_id),
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.CLICK,
            "Clicked screen coordinate.",
            metadata={
                "coordinateClick": True,
                "x": x,
                "y": y,
                **_target_identity_metadata(target_app, bundle_id),
                "action_attempted": True,
            },
        )

    def wait(self, *, seconds: float = 1.0) -> ComputerUseResult:
        if seconds < 0:
            return ComputerUseResult.blocked(
                ComputerUseOperation.WAIT,
                "wait seconds must be non-negative.",
            )
        time.sleep(seconds)
        return ComputerUseResult.ok(
            ComputerUseOperation.WAIT,
            f"Waited {seconds:.2f} seconds.",
            metadata={"seconds": seconds},
        )


class ComputerUseClient:
    """Developer-facing factory for direct, config, and helper clients."""

    def __new__(
        cls,
        config: AppControlConfig | HelperConfig | Mapping[str, Any] | str | Path | None
        = None,
        **kwargs: Any,
    ) -> Any:
        if config is None:
            return MacOSComputerUseClient(**kwargs)
        if isinstance(config, HelperConfig):
            return MacOSComputerUseClient.from_config(
                _app_config_from_helper(config),
                **kwargs,
            )
        return MacOSComputerUseClient.from_config(config, **kwargs)

    @classmethod
    def from_config(
        cls,
        config: AppControlConfig | Mapping[str, Any] | str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        """Build a direct or helper backend from shared app-control config."""

        return MacOSComputerUseClient.from_config(config, **kwargs)

    @classmethod
    def from_helper_config(
        cls,
        config: HelperConfig,
        **kwargs: Any,
    ) -> Any:
        """Build a helper backend from a standalone helper config."""

        return MacOSComputerUseClient.from_config(
            _app_config_from_helper(config),
            **kwargs,
        )

    @classmethod
    def from_helper_manifest(
        cls,
        manifest: object,
        **kwargs: Any,
    ) -> Any:
        """Build a helper transport client from a helper manifest."""

        return MacOSComputerUseClient.from_helper_manifest(manifest, **kwargs)


def _app_config_from_helper(helper: HelperConfig) -> AppControlConfig:
    return AppControlConfig.from_dict(
        {
            "computer_use": {
                "backend": "helper",
                "allowed_apps": list(helper.allowed_apps),
            },
            "helper": _helper_config_payload(helper),
        }
    )


def _helper_config_payload(helper: HelperConfig) -> dict[str, Any]:
    return {
        "transport": helper.transport,
        "helper_app_path": helper.helper_app_path,
        "bundle_id": helper.bundle_id,
        "manifest_path": helper.manifest_path,
        "endpoint": helper.endpoint,
        "token": helper.token,
        "allowed_apps": list(helper.allowed_apps),
        "auto_launch": helper.auto_launch,
        "launch_timeout_ms": helper.launch_timeout_ms,
    }


_SUPPORTED_PROTOCOL_TOOLS = frozenset(
    {
        "macos.computer_use",
        "computer-use-macos",
    }
)

_DIRECT_BACKENDS = frozenset(
    {
        "direct",
        "macos",
        "macos-direct",
        "computer-use-macos",
    }
)


def _protocol_models() -> tuple[
    type[Any],
    type[Any],
    type[Any],
    type[Any],
    type[Any],
    type[Any],
]:
    try:
        from app_control_protocol import (
            ToolCommand,
            ToolError,
            ToolEvent,
            ToolEventType,
            ToolObservation,
            ToolStatus,
        )
    except ImportError as exc:  # pragma: no cover - environment setup failure.
        raise RuntimeError(
            "run_command requires the app-control-protocol package. "
            "Install app-control-protocol or add packages/app-control-protocol/src "
            "to PYTHONPATH in the monorepo checkout."
        ) from exc
    return ToolCommand, ToolObservation, ToolStatus, ToolError, ToolEvent, ToolEventType


def _coerce_tool_command(command: Any, tool_command_cls: type[Any]) -> Any:
    if isinstance(command, Mapping):
        return tool_command_cls.from_dict(dict(command))
    return command


def _started_event(
    command: Any,
    *,
    tool_event_cls: type[Any],
    tool_event_type_cls: type[Any],
) -> Any:
    return tool_event_cls(
        command_id=command.command_id,
        seq=0,
        event_type=tool_event_type_cls.STARTED,
        phase=command.operation,
        summary=f"Started {command.tool}.{command.operation}.",
        data={
            "tool": command.tool,
            "operation": command.operation,
        },
    )


def _observation_event(
    command: Any,
    observation: Any,
    *,
    tool_event_cls: type[Any],
    tool_event_type_cls: type[Any],
) -> Any:
    return tool_event_cls(
        command_id=command.command_id,
        seq=1,
        event_type=tool_event_type_cls.OBSERVATION,
        phase=command.operation,
        status=observation.status,
        summary=observation.summary,
        data={"observation": observation.to_dict()},
    )


def _emit_observer(observer: Any, event: Any) -> None:
    if observer is not None:
        observer.on_event(event)


def _load_app_control_config(
    config: "AppControlConfig | Mapping[str, Any] | str | Path | None",
    *,
    env: Mapping[str, str] | None,
) -> Any:
    try:
        from app_control_protocol import AppControlConfig, load_app_control_config
    except ImportError as exc:  # pragma: no cover - environment setup failure.
        raise RuntimeError(
            "from_config requires the app-control-protocol package. "
            "Install app-control-protocol or add packages/app-control-protocol/src "
            "to PYTHONPATH in the monorepo checkout."
        ) from exc
    if config is None or isinstance(config, str | Path):
        return load_app_control_config(config, env=env)
    if isinstance(config, Mapping):
        return AppControlConfig.from_dict(config)
    return config


def _coerce_helper_manifest(manifest: object) -> Any:
    from .helper import HelperManifest, load_helper_manifest

    if isinstance(manifest, HelperManifest):
        return manifest
    if isinstance(manifest, Mapping):
        return HelperManifest.from_dict(manifest)
    if isinstance(manifest, str | Path):
        return load_helper_manifest(manifest)
    raise TypeError("manifest must be a HelperManifest, mapping, or path")


def _helper_transport_from_config(
    app_config: Any,
    *,
    runner: CommandRunner | None,
) -> Any:
    from .helper import (
        HelperManifest,
        discover_helper_manifest,
        helper_transport_from_manifest,
        launch_helper_app,
    )

    helper = app_config.helper
    allowed_app_identities = _helper_allowed_app_identities(app_config)
    if helper.auto_launch and helper.helper_app_path:
        launch = launch_helper_app(
            helper.helper_app_path,
            runner=runner,
            timeout=helper.launch_timeout_ms / 1000.0,
        )
        if not launch.launched:
            raise RuntimeError(launch.summary)

    if helper.manifest_path:
        discovery = discover_helper_manifest(helper.manifest_path)
        if not discovery.found or discovery.manifest is None:
            raise RuntimeError(discovery.summary)
        manifest = discovery.manifest
    elif helper.helper_app_path:
        manifest_path = _helper_app_manifest_path(helper.helper_app_path)
        discovery = discover_helper_manifest(manifest_path)
        if discovery.found and discovery.manifest is not None:
            manifest = discovery.manifest
        elif not helper.bundle_id or not helper.endpoint:
            raise RuntimeError(
                "helper backend requires helper.manifest_path, a helper app "
                "with Contents/Resources/helper_config.json, or helper.bundle_id "
                "plus helper.endpoint"
            )
        else:
            manifest = HelperManifest(
                bundle_id=helper.bundle_id,
                transport=helper.transport,
                endpoint=helper.endpoint,
                socket_path=(
                    helper.endpoint if helper.transport == "unix_socket" else None
                ),
                token=helper.token,
                helper_app_path=helper.helper_app_path,
                metadata=_helper_metadata(allowed_app_identities),
            )
    else:
        if not helper.bundle_id or not helper.endpoint:
            raise RuntimeError(
                "helper backend requires helper.manifest_path, a helper app "
                "with Contents/Resources/helper_config.json, or helper.bundle_id "
                "plus helper.endpoint"
            )
        manifest = HelperManifest(
            bundle_id=helper.bundle_id,
            transport=helper.transport,
            endpoint=helper.endpoint,
            socket_path=helper.endpoint if helper.transport == "unix_socket" else None,
            token=helper.token,
            helper_app_path=helper.helper_app_path,
            metadata=_helper_metadata(allowed_app_identities),
        )

    if allowed_app_identities:
        metadata = dict(manifest.metadata)
        metadata.update(_helper_metadata(allowed_app_identities))
        manifest = replace(manifest, metadata=metadata)
    manifest.validate_identity(expected_bundle_id=helper.bundle_id)
    return helper_transport_from_manifest(
        manifest,
        timeout=app_config.computer_use.timeout_ms / 1000.0,
    )


def _helper_allowed_app_identities(
    app_config: Any,
) -> Iterable[str] | Mapping[str, str | None]:
    helper_allowed_apps = tuple(getattr(app_config.helper, "allowed_apps", ()) or ())
    if helper_allowed_apps:
        return helper_allowed_apps
    return _computer_use_allowed_apps(app_config.computer_use)


def _computer_use_allowed_apps(
    computer_use: Any,
) -> Iterable[str] | Mapping[str, str | None]:
    identities = getattr(computer_use, "allowed_app_identities", None)
    if callable(identities):
        return identities()
    bundle_ids = dict(getattr(computer_use, "allowed_app_bundle_ids", {}) or {})
    if bundle_ids:
        allowed_apps = {
            app: None for app in getattr(computer_use, "allowed_apps", ()) or ()
        }
        allowed_apps.update(bundle_ids)
        return allowed_apps
    return tuple(getattr(computer_use, "allowed_apps", ()) or ())


def _helper_metadata(
    allowed_app_identities: Iterable[str] | Mapping[str, str | None],
) -> dict[str, Any]:
    if not allowed_app_identities:
        return {}
    if isinstance(allowed_app_identities, Mapping):
        allowed_apps = list(allowed_app_identities.keys())
        allowed_app_bundle_ids = {
            app: bundle_id
            for app, bundle_id in allowed_app_identities.items()
            if bundle_id
        }
        metadata: dict[str, Any] = {"allowedApps": allowed_apps}
        if allowed_app_bundle_ids:
            metadata["allowedAppBundleIds"] = allowed_app_bundle_ids
        return metadata
    return {"allowedApps": list(allowed_app_identities)}


def _helper_app_manifest_path(helper_app_path: str) -> Path:
    return (
        Path(helper_app_path).expanduser()
        / "Contents"
        / "Resources"
        / "helper_config.json"
    )


def _timeout_seconds(timeout_ms: int | None) -> float | None:
    if timeout_ms is None:
        return None
    return timeout_ms / 1000.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _duration_ms(started_monotonic: float) -> int:
    return max(0, int(round((time.monotonic() - started_monotonic) * 1000)))


def _with_timing(
    observation: Any,
    *,
    started_at: str,
    duration_ms: int,
) -> Any:
    payload = observation.to_dict()
    timing = dict(payload.get("timing", {}))
    timing.setdefault("startedAt", started_at)
    timing.setdefault("durationMs", duration_ms)
    payload["timing"] = timing
    return type(observation).from_dict(payload)


def _required_string(payload: Mapping[str, Any], *keys: str) -> str:
    value = _first(payload, *keys)
    if not isinstance(value, str) or not value.strip():
        joined = " or ".join(keys)
        raise ValueError(f"{joined} is required")
    return value.strip()


def _optional_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    value = _first(payload, *keys)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        joined = " or ".join(keys)
        raise ValueError(f"{joined} must be a non-empty string")
    return value.strip()


def _bundle_id_from_payload(payload: Mapping[str, Any]) -> str | None:
    return _optional_string(payload, "bundleId", "bundle_id")


def _first(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _seconds(payload: Mapping[str, Any], *, default: float) -> float:
    value = _first(payload, "seconds", "durationSeconds", "duration_seconds")
    if value is None:
        return default
    if not isinstance(value, int | float):
        raise TypeError("seconds must be numeric")
    return float(value)


def _coordinate_from_payload(payload: Mapping[str, Any]) -> tuple[int, int] | None:
    x = _first(payload, "x", "screenX", "screen_x")
    y = _first(payload, "y", "screenY", "screen_y")
    if x is not None or y is not None:
        if x is None or y is None:
            raise ValueError("coordinate click requires both x and y")
        return _coordinate_int(x, "x"), _coordinate_int(y, "y")

    raw_coordinate = _first(payload, "coordinate", "coordinates", "point")
    if raw_coordinate is None:
        return None
    if isinstance(raw_coordinate, Mapping):
        x = _first(raw_coordinate, "x", "screenX", "screen_x")
        y = _first(raw_coordinate, "y", "screenY", "screen_y")
        if x is None or y is None:
            raise ValueError("coordinate click requires both x and y")
        return _coordinate_int(x, "x"), _coordinate_int(y, "y")
    if isinstance(raw_coordinate, list | tuple) and len(raw_coordinate) == 2:
        return (
            _coordinate_int(raw_coordinate[0], "x"),
            _coordinate_int(raw_coordinate[1], "y"),
        )
    raise TypeError("coordinate must be an object with x/y or a two-item list")


def _coordinate_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _accessibility_selector_from_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw_selector = _first(
        payload,
        "selector",
        "accessibilitySelector",
        "accessibility_selector",
    )
    if raw_selector is None:
        return None
    if not isinstance(raw_selector, Mapping):
        raise TypeError("selector must be an object")
    return _normalize_accessibility_selector(raw_selector)


def _normalize_accessibility_selector(selector: Mapping[str, Any]) -> dict[str, Any]:
    role = _optional_string(selector, "role", "kind", "element") or "button"
    role_name = _ACCESSIBILITY_ROLES.get(_key_lookup_name(role))
    if role_name is None:
        raise ValueError(f"unsupported accessibility selector role: {role}")
    name = _optional_string(selector, "name", "title", "label", "description")
    raw_index = _first(selector, "index")
    if name is None and raw_index is None:
        raise ValueError(
            "accessibility selector requires name/title/label/description or index"
        )
    normalized: dict[str, Any] = {"role": role_name}
    if name is not None:
        normalized["name"] = name
    if raw_index is not None:
        normalized["index"] = _positive_int(raw_index, "index")
    return normalized


def _positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _selector_target_text(selector: Mapping[str, Any]) -> str:
    name = selector.get("name")
    if isinstance(name, str):
        return name
    index = selector.get("index")
    return f"{selector['role']} {index}"


def _accessibility_click_script(target_app: str, selector: Mapping[str, Any]) -> str:
    role = str(selector["role"])
    name = selector.get("name")
    if isinstance(name, str):
        element = f"{role} {_applescript_string(name)}"
    else:
        element = f"{role} {selector['index']}"
    return (
        'tell application "System Events"\n'
        f"  tell process {_applescript_string(target_app)}\n"
        "    set frontmost to true\n"
        f"    click {element} of front window\n"
        "  end tell\n"
        "end tell\n"
    )


def _press_key_from_payload(payload: Mapping[str, Any]) -> str:
    key = _optional_string(payload, "key")
    if key is not None:
        return key
    keys = _string_sequence(payload, "keys")
    if len(keys) != 1:
        raise ValueError("press_key requires key or exactly one keys item")
    return keys[0]


def _hotkey_from_payload(payload: Mapping[str, Any]) -> tuple[str, ...]:
    keys = _string_sequence(payload, "keys")
    if keys:
        return keys
    key = _required_string(payload, "key")
    modifiers = _string_sequence(payload, "modifiers")
    return (*modifiers, key)


def _string_sequence(payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise TypeError(f"{key} must be a list of strings")
    output: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} items must be non-empty strings")
        output.append(item.strip())
    return tuple(output)


def _normalize_key_name(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("key must be a non-empty string")
    return key.strip()


def _split_hotkey(keys: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    if len(keys) < 2:
        raise ValueError("hotkey requires at least one modifier and one key")
    modifiers: list[str] = []
    action_keys: list[str] = []
    for key in keys:
        if _modifier_script_name(key) is not None:
            modifiers.append(key)
        else:
            action_keys.append(key)
    if not modifiers:
        raise ValueError("hotkey requires at least one modifier")
    if len(action_keys) != 1:
        raise ValueError("hotkey requires exactly one non-modifier key")
    return tuple(modifiers), action_keys[0]


def _keyboard_script(key: str, *, modifiers: Iterable[str] = ()) -> str:
    modifier_clause = _modifier_clause(modifiers)
    key_code = _key_code(key)
    if key_code is not None:
        action = f"  key code {key_code}{modifier_clause}\n"
    else:
        if len(key) != 1:
            raise ValueError(f"unsupported key name: {key}")
        action = f"  keystroke {_applescript_string(key)}{modifier_clause}\n"
    return 'tell application "System Events"\n' + action + "end tell\n"


def _type_text_script(text: str) -> str:
    escaped_text = _applescript_string(text)
    return (
        "set __computerUseClipboardWasCaptured to false\n"
        'set __computerUsePreviousClipboard to ""\n'
        "try\n"
        "  set __computerUsePreviousClipboard to the clipboard\n"
        "  set __computerUseClipboardWasCaptured to true\n"
        "end try\n"
        "try\n"
        f"  set the clipboard to {escaped_text}\n"
        "  delay 0.05\n"
        '  tell application "System Events"\n'
        '    keystroke "v" using {command down}\n'
        "  end tell\n"
        "  delay 0.1\n"
        "on error __computerUseErrorMessage number __computerUseErrorNumber\n"
        "  if __computerUseClipboardWasCaptured then set the clipboard to "
        "__computerUsePreviousClipboard\n"
        "  error __computerUseErrorMessage number __computerUseErrorNumber\n"
        "end try\n"
        "if __computerUseClipboardWasCaptured then set the clipboard to "
        "__computerUsePreviousClipboard\n"
    )


def _key_code(key: str) -> int | None:
    return _KEY_CODES.get(_key_lookup_name(key))


def _key_lookup_name(key: str) -> str:
    return key.strip().replace("-", "_").replace(" ", "_").lower()


def _modifier_clause(modifiers: Iterable[str]) -> str:
    modifier_names = tuple(_modifier_script_name(modifier) for modifier in modifiers)
    if not modifier_names:
        return ""
    if any(name is None for name in modifier_names):
        raise ValueError("hotkey contains an unsupported modifier")
    return " using {" + ", ".join(name for name in modifier_names if name) + "}"


def _modifier_script_name(modifier: str) -> str | None:
    return _MODIFIER_NAMES.get(_key_lookup_name(modifier))


def _readiness_to_protocol_observation(
    *,
    command: Any,
    readiness: ComputerUseReadiness,
    tool_observation_cls: type[Any],
    tool_status_cls: type[Any],
    tool_error_cls: type[Any],
) -> Any:
    payload = readiness.to_dict()
    summary = f"macOS computer-use readiness: {readiness.status.value}."
    if readiness.setup_hint:
        summary = f"{summary} {readiness.setup_hint}"
    if readiness.ready:
        return tool_observation_cls.ok(
            command_id=command.command_id,
            tool=command.tool,
            operation=command.operation,
            summary=summary,
            observation=payload,
        )
    status = (
        tool_status_cls.PERMISSION_MISSING
        if readiness.status
        in {
            ComputerUseReadinessStatus.MISSING_ACCESSIBILITY,
            ComputerUseReadinessStatus.MISSING_SCREEN_RECORDING,
        }
        else tool_status_cls.NOT_READY
    )
    if readiness.status == ComputerUseReadinessStatus.ERROR:
        status = tool_status_cls.FAILED
    return _protocol_failure(
        command=command,
        status=status,
        failure_kind=readiness.status.value,
        message=summary,
        recovery_hint=readiness.setup_hint,
        retryable=True,
        observation=payload,
        tool_observation_cls=tool_observation_cls,
        tool_error_cls=tool_error_cls,
    )


def _result_to_protocol_observation(
    *,
    command: Any,
    result: ComputerUseResult,
    tool_observation_cls: type[Any],
    tool_status_cls: type[Any],
    tool_error_cls: type[Any],
) -> Any:
    observation = _result_observation(result)
    if result.success:
        return tool_observation_cls.ok(
            command_id=command.command_id,
            tool=command.tool,
            operation=command.operation,
            summary=result.summary,
            observation=observation,
            evidence=_result_evidence(result),
        )
    return _protocol_failure(
        command=command,
        status=_protocol_status(result, tool_status_cls),
        failure_kind=_failure_kind(result),
        message=result.summary,
        retryable=result.status
        in {
            ComputerUseStatus.NEEDS_USER,
            ComputerUseStatus.NOT_AVAILABLE,
            ComputerUseStatus.TIMEOUT,
        },
        observation=observation,
        evidence=_result_evidence(result),
        metadata={"legacyStatus": result.status.value},
        tool_observation_cls=tool_observation_cls,
        tool_error_cls=tool_error_cls,
    )


def _protocol_failure(
    *,
    command: Any,
    status: Any,
    failure_kind: str,
    message: str,
    retryable: bool,
    tool_observation_cls: type[Any],
    tool_error_cls: type[Any],
    recovery_hint: str | None = None,
    observation: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    error = tool_error_cls(
        failure_kind=failure_kind,
        message=message,
        recovery_hint=recovery_hint,
        retryable=retryable,
        phase=command.operation,
        operation=command.operation,
        evidence=evidence or {},
    )
    return tool_observation_cls.failure(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        status=status,
        error=error,
        summary=message,
        observation=observation or {},
        metadata=metadata or {},
    )


def _protocol_status(result: ComputerUseResult, tool_status_cls: type[Any]) -> Any:
    if result.status == ComputerUseStatus.NOT_AVAILABLE:
        return tool_status_cls.NOT_READY
    if result.status == ComputerUseStatus.NEEDS_USER:
        return tool_status_cls.NOT_READY
    if result.status == ComputerUseStatus.TIMEOUT:
        return tool_status_cls.TIMEOUT
    if result.status == ComputerUseStatus.FAILED:
        return tool_status_cls.FAILED
    if result.status == ComputerUseStatus.BLOCKED:
        return tool_status_cls.FAILED
    return tool_status_cls.UNKNOWN


def _failure_kind(result: ComputerUseResult) -> str:
    if result.risk is not None and result.risk.risk_label:
        return result.risk.risk_label
    value = result.metadata.get("failure_kind")
    if isinstance(value, str) and value:
        return value
    return result.status.value


_PUBLIC_METADATA_FIELDS = {
    "chars": "chars",
    "submitted": "submitted",
    "input_method": "inputMethod",
    "action_attempted": "actionAttempted",
    "key": "key",
    "keys": "keys",
    "modifiers": "modifiers",
    "target_app": "targetApp",
    "target_summary": "targetSummary",
    "target_snapshot_id": "targetSnapshotId",
    "bundle_id": "bundleId",
    "frontmost_app": "frontmostApp",
    "frontmost_bundle_id": "frontmostBundleId",
    "window_title": "windowTitle",
}


def _result_observation(result: ComputerUseResult) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "legacyStatus": result.status.value,
        "metadata": result.metadata,
    }
    for metadata_key, observation_key in _PUBLIC_METADATA_FIELDS.items():
        if metadata_key in result.metadata:
            observation[observation_key] = result.metadata[metadata_key]
    if result.text_extract is not None:
        observation["textExtract"] = result.text_extract
    if result.snapshot_id is not None:
        observation["snapshotId"] = result.snapshot_id
    if result.risk is not None:
        observation["risk"] = result.risk.to_dict()
    return observation


def _result_evidence(result: ComputerUseResult) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if result.text_extract is not None:
        evidence["textExtract"] = result.text_extract
    if result.snapshot_id is not None:
        evidence["snapshotId"] = result.snapshot_id
    return evidence
