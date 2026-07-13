"""Public client for conservative macOS computer-use primitives."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import select
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

from app_control_protocol import AppControlConfig, HelperConfig

from .accessibility_limits import MAX_ACCESSIBILITY_QUERY_DEPTH
from .commands import CommandResult, CommandRunner, SubprocessCommandRunner
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


def _duration_ms(started: float) -> int:
    return max(0, int(round((time.monotonic() - started) * 1000)))


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


def _attach_accessibility_transport(
    payload: dict[str, Any],
    transport: Mapping[str, Any],
) -> None:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        payload["diagnostics"] = diagnostics
    diagnostics["transport"] = dict(transport)


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
    "axbutton": "button",
    "button": "button",
    "axcheckbox": "checkbox",
    "checkbox": "checkbox",
    "check_box": "checkbox",
    "axmenuitem": "menu item",
    "menuitem": "menu item",
    "menu_item": "menu item",
    "axradiobutton": "radio button",
    "radio_button": "radio button",
    "radiobutton": "radio button",
    "axrow": "row",
    "row": "row",
    "axpopupbutton": "pop up button",
    "pop_up_button": "pop up button",
    "popup_button": "pop up button",
    "axtextfield": "text field",
    "axtextarea": "text area",
    "text_area": "text area",
    "textarea": "text area",
    "text_field": "text field",
    "textfield": "text field",
}

_ACCESSIBILITY_ROLE_COLLECTIONS = {
    "button": "buttons",
    "checkbox": "checkboxes",
    "menu item": "menu items",
    "radio button": "radio buttons",
    "row": "rows",
    "text field": "text fields",
    "text area": "text areas",
}


class _AccessibilityWorker:
    """Warm subprocess for repeated Accessibility operations in service mode."""

    _PROTOCOL_FAILURE = 70

    def __init__(
        self,
        *,
        worker_name: str,
        worker_script: str,
        executable: str = sys.executable,
    ) -> None:
        self._worker_name = worker_name
        self._worker_script = worker_script
        self._executable = executable
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self._ensure_started()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def run(self, request: Mapping[str, Any], *, timeout: float) -> CommandResult:
        started = time.monotonic()
        timeout = max(0.1, timeout)
        with self._lock:
            try:
                process = self._ensure_started()
            except Exception as exc:
                return CommandResult(self._PROTOCOL_FAILURE, "", str(exc))
            if process.stdin is None or process.stdout is None:
                self._stop_locked()
                return CommandResult(
                    self._PROTOCOL_FAILURE,
                    "",
                    f"Accessibility {self._worker_name} worker pipes are unavailable.",
                )
            try:
                process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                process.stdin.flush()
            except Exception as exc:
                self._stop_locked()
                return CommandResult(self._PROTOCOL_FAILURE, "", str(exc))

            line = self._read_response_line(process, timeout, started)
            if line is None:
                stderr = self._terminate_for_timeout(process)
                return CommandResult(124, "", stderr, timed_out=True)
            if not line:
                stderr = self._collect_stderr(process)
                self._stop_locked()
                return CommandResult(
                    self._PROTOCOL_FAILURE,
                    "",
                    stderr
                    or (
                        f"Accessibility {self._worker_name} worker exited "
                        "without a response."
                    ),
                )
            return CommandResult(0, line, "")

    def _ensure_started(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._stop_locked()
        self._process = subprocess.Popen(
            [
                self._executable,
                "-u",
                "-c",
                self._worker_script,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return self._process

    def _read_response_line(
        self,
        process: subprocess.Popen[str],
        timeout: float,
        started: float,
    ) -> str | None:
        if process.stdout is None:
            return ""
        deadline = started + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                return None
            line = process.stdout.readline()
            if line == "":
                return ""
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_worker_ready_line(stripped):
                continue
            return stripped

    def _is_worker_ready_line(self, line: str) -> bool:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and payload.get("workerReady") is True

    def _terminate_for_timeout(self, process: subprocess.Popen[str]) -> str:
        try:
            process.kill()
            _, stderr = process.communicate(timeout=1)
        except Exception as exc:
            stderr = str(exc)
        finally:
            self._process = None
        return stderr or f"Accessibility {self._worker_name} worker timed out."

    def _collect_stderr(self, process: subprocess.Popen[str]) -> str:
        if process.poll() is None:
            return ""
        try:
            _, stderr = process.communicate(timeout=1)
        except Exception as exc:
            return str(exc)
        return stderr or ""

    def _stop_locked(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass


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
        self._accessibility_query_worker: _AccessibilityWorker | None = None
        self._accessibility_action_worker: _AccessibilityWorker | None = None
        if runner is None and probe is None and enabled and self._is_darwin_host():
            try:
                query_worker = _AccessibilityWorker(
                    worker_name="query",
                    worker_script=_accessibility_query_worker_script(),
                )
                query_worker.start()
                self._accessibility_query_worker = query_worker
            except Exception:
                self._accessibility_query_worker = None
            try:
                action_worker = _AccessibilityWorker(
                    worker_name="action",
                    worker_script=_accessibility_action_worker_script(),
                )
                action_worker.start()
                self._accessibility_action_worker = action_worker
            except Exception:
                self._accessibility_action_worker = None

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

    def _is_darwin_host(self) -> bool:
        try:
            return self._probe.platform_name() == "Darwin"
        except Exception:
            return False

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
                    include_accessibility=_optional_bool(
                        payload,
                        "includeAccessibility",
                        "include_accessibility",
                        default=False,
                    ),
                    include_accessibility_tree=_optional_bool(
                        payload,
                        "includeAccessibilityTree",
                        "include_accessibility_tree",
                        default=False,
                    ),
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "accessibility_query":
                result = self.accessibility_query(
                    target_app=_optional_string(
                        payload,
                        "targetApp",
                        "target_app",
                        "app",
                    ),
                    bundle_id=bundle_id,
                    root=_mapping_from_payload(payload, "root"),
                    query=_mapping_from_payload(payload, "query"),
                    include_raw=_optional_bool(
                        payload,
                        "includeRaw",
                        "include_raw",
                        default=False,
                    ),
                    timeout=timeout or self._default_timeout,
                )
            elif operation == "accessibility_action":
                result = self.accessibility_action(
                    target_app=_optional_string(
                        payload,
                        "targetApp",
                        "target_app",
                        "app",
                    ),
                    bundle_id=bundle_id,
                    snapshot_id=_optional_string(
                        payload,
                        "snapshotId",
                        "snapshot_id",
                    ),
                    target=_accessibility_action_target_from_payload(payload),
                    action=_required_string(payload, "action"),
                    preconditions=_mapping_from_payload(payload, "preconditions"),
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
        include_accessibility: bool = False,
        include_accessibility_tree: bool = False,
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
        if include_accessibility or include_accessibility_tree:
            accessibility = (
                self._accessibility_snapshot(timeout=timeout)
                if include_accessibility
                else {"available": True}
            )
            if include_accessibility_tree:
                tree_snapshot = self._accessibility_tree_snapshot(
                    timeout=timeout,
                    bundle_id=bundle_id or frontmost_bundle_id or None,
                )
                if tree_snapshot.get("available") is False:
                    accessibility["treeAvailable"] = False
                    for key in ("failureKind", "message", "timeoutSeconds"):
                        if key in tree_snapshot:
                            accessibility[f"tree{key[:1].upper()}{key[1:]}"] = (
                                tree_snapshot[key]
                            )
                else:
                    accessibility["treeAvailable"] = True
                    if "focusedWindow" in tree_snapshot:
                        accessibility["focusedWindow"] = tree_snapshot["focusedWindow"]
                    if "app" in tree_snapshot:
                        accessibility["app"] = tree_snapshot["app"]
            observation_metadata["accessibility"] = accessibility

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

    def _accessibility_snapshot(self, *, timeout: float) -> dict[str, Any]:
        snapshot_timeout = min(timeout, 2.0)
        result = self._runner.run(
            ["osascript", "-e", _accessibility_snapshot_script()],
            timeout=snapshot_timeout,
        )
        if getattr(result, "timed_out", False):
            return {
                "available": False,
                "failureKind": "accessibility_snapshot_timeout",
                "message": "Timed out collecting Accessibility snapshot.",
                "timeoutSeconds": snapshot_timeout,
            }
        if result.returncode != 0:
            return {
                "available": False,
                "failureKind": "accessibility_snapshot_failed",
                "message": _bounded(result.stderr or result.stdout, 1000),
            }
        return _accessibility_snapshot_from_stdout(result.stdout)

    def _accessibility_tree_snapshot(
        self,
        *,
        timeout: float,
        bundle_id: str | None = None,
    ) -> dict[str, Any]:
        snapshot_timeout = min(timeout, 15.0)
        script_budget = max(0.5, snapshot_timeout - 1.0)
        args = [
            sys.executable,
            "-c",
            _accessibility_tree_snapshot_script(),
            f"{script_budget:.3f}",
        ]
        if bundle_id:
            args.append(bundle_id)
        result = self._runner.run(args, timeout=snapshot_timeout)
        if getattr(result, "timed_out", False):
            return {
                "available": False,
                "failureKind": "accessibility_tree_snapshot_timeout",
                "message": "Timed out collecting Accessibility tree snapshot.",
                "timeoutSeconds": snapshot_timeout,
            }
        if result.returncode != 0:
            return {
                "available": False,
                "failureKind": "accessibility_tree_snapshot_failed",
                "message": _bounded(result.stderr or result.stdout, 1000),
            }
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "available": False,
                "failureKind": "accessibility_tree_snapshot_invalid_json",
                "message": _bounded(result.stdout, 1000),
            }
        if not isinstance(payload, dict):
            return {
                "available": False,
                "failureKind": "accessibility_tree_snapshot_invalid_payload",
                "message": "Accessibility tree snapshot did not return an object.",
            }
        return payload

    def accessibility_query(
        self,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        root: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        include_raw: bool = False,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        readiness = self.readiness()
        if readiness.status != ComputerUseReadinessStatus.READY:
            return ComputerUseResult.not_available(
                ComputerUseOperation.ACCESSIBILITY_QUERY,
                "macOS Accessibility query is unavailable until readiness is ready.",
                metadata={"readiness": readiness.to_dict()},
            )

        allowlist_failure = self._accessibility_target_allowlist_failure(
            ComputerUseOperation.ACCESSIBILITY_QUERY,
            target_app,
            bundle_id,
            require_identity=False,
        )
        if allowlist_failure is not None:
            return allowlist_failure
        bundle_id = self._effective_accessibility_bundle_id(target_app, bundle_id)

        request = _normalize_accessibility_query_request(
            target_app=target_app,
            bundle_id=bundle_id,
            root=root,
            query=query,
            include_raw=include_raw,
        )
        snapshot_timeout = min(timeout, 15.0)
        result, transport = self._run_accessibility_query_request(
            request,
            snapshot_timeout,
        )
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.ACCESSIBILITY_QUERY,
                "Timed out running Accessibility query.",
                result,
                snapshot_timeout,
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_query_timeout",
                    "accessibility_query_transport": transport,
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_QUERY,
                "Failed to run Accessibility query.",
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_query_failed",
                    "stderr": _bounded(result.stderr or result.stdout, 1000),
                    "accessibility_query_transport": transport,
                },
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_QUERY,
                "Accessibility query returned invalid JSON.",
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_query_invalid_json",
                    "stdout": _bounded(result.stdout, 1000),
                    "accessibility_query_transport": transport,
                },
            )
        if not isinstance(payload, dict):
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_QUERY,
                "Accessibility query did not return an object.",
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_query_invalid_payload",
                    "accessibility_query_transport": transport,
                },
            )
        _attach_accessibility_transport(payload, transport)
        if payload.get("available") is False:
            failure_kind = payload.get("failureKind")
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_QUERY,
                str(payload.get("message") or "Accessibility query failed."),
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": (
                        failure_kind
                        if isinstance(failure_kind, str) and failure_kind
                        else "accessibility_query_unavailable"
                    ),
                    "accessibility_query": payload,
                },
            )

        snapshot_id = payload.get("snapshotId")
        return ComputerUseResult.ok(
            ComputerUseOperation.ACCESSIBILITY_QUERY,
            "Ran Accessibility query.",
            snapshot_id=snapshot_id if isinstance(snapshot_id, str) else None,
            metadata={
                **_target_identity_metadata(target_app, bundle_id),
                "accessibility_query": payload,
            },
        )

    def _run_accessibility_query_request(
        self,
        request: Mapping[str, Any],
        timeout: float,
    ) -> tuple[CommandResult, dict[str, Any]]:
        worker = self._accessibility_query_worker
        if worker is None:
            return self._run_accessibility_query_subprocess(request, timeout)

        worker_started = time.monotonic()
        worker_result = worker.run(request, timeout=timeout)
        worker_transport: dict[str, Any] = {
            "mode": "worker",
            "durationMs": _duration_ms(worker_started),
            "fallback": False,
        }
        if worker_result.timed_out or worker_result.returncode == 0:
            return worker_result, worker_transport

        result, transport = self._run_accessibility_query_subprocess(request, timeout)
        transport["fallback"] = True
        transport["fallbackFromWorker"] = True
        transport["workerDurationMs"] = worker_transport["durationMs"]
        transport["workerReturnCode"] = worker_result.returncode
        if worker_result.stderr:
            transport["workerStderr"] = _bounded(worker_result.stderr, 1000)
        return result, transport

    def _run_accessibility_query_subprocess(
        self,
        request: Mapping[str, Any],
        timeout: float,
    ) -> tuple[CommandResult, dict[str, Any]]:
        started = time.monotonic()
        result = self._runner.run(
            [
                sys.executable,
                "-c",
                _accessibility_query_script(),
                json.dumps(request, ensure_ascii=False),
            ],
            timeout=timeout,
        )
        return result, {
            "mode": "subprocess",
            "durationMs": _duration_ms(started),
            "fallback": False,
        }

    def accessibility_action(
        self,
        *,
        target_app: str | None = None,
        bundle_id: str | None = None,
        snapshot_id: str | None = None,
        target: Mapping[str, Any] | None = None,
        action: str = "AXPress",
        preconditions: Mapping[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> ComputerUseResult:
        readiness = self.readiness()
        if readiness.status != ComputerUseReadinessStatus.READY:
            return ComputerUseResult.not_available(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                "macOS Accessibility action is unavailable until readiness is ready.",
                metadata={"readiness": readiness.to_dict()},
            )
        allowlist_failure = self._accessibility_target_allowlist_failure(
            ComputerUseOperation.ACCESSIBILITY_ACTION,
            target_app,
            bundle_id,
            require_identity=True,
        )
        if allowlist_failure is not None:
            return allowlist_failure
        bundle_id = self._effective_accessibility_bundle_id(target_app, bundle_id)

        request = _normalize_accessibility_action_request(
            target_app=target_app,
            bundle_id=bundle_id,
            snapshot_id=snapshot_id,
            target=target,
            action=action,
            preconditions=preconditions,
        )
        target_text = _accessibility_action_target_text(request)
        risk = self._policy.classify(
            ComputerUseOperation.ACCESSIBILITY_ACTION,
            target=target_text,
        )
        if risk.requires_confirmation:
            return ComputerUseResult.blocked(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                "computer-use action requires confirmation",
                risk=risk,
                metadata={
                    "confirmation_required": True,
                    "confirmation_title": "Confirm desktop action",
                    "confirmation_body": (
                        "Approve the requested Accessibility action before it is "
                        "executed."
                    ),
                },
            )
        if risk.level.value == "high":
            return ComputerUseResult.blocked(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                risk.reason,
                risk=risk,
            )

        result, transport = self._run_accessibility_action_request(
            request,
            timeout,
        )
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                "Timed out running Accessibility action.",
                result,
                timeout,
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_action_timeout",
                    "accessibility_action_transport": transport,
                },
            )
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                "Failed to run Accessibility action.",
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_action_failed",
                    "stderr": _bounded(result.stderr or result.stdout, 1000),
                    "accessibility_action_transport": transport,
                },
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                "Accessibility action returned invalid JSON.",
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_action_invalid_json",
                    "stdout": _bounded(result.stdout, 1000),
                    "accessibility_action_transport": transport,
                },
            )
        if not isinstance(payload, dict):
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                "Accessibility action did not return an object.",
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": "accessibility_action_invalid_payload",
                    "accessibility_action_transport": transport,
                },
            )
        _attach_accessibility_transport(payload, transport)
        if payload.get("available") is False or payload.get("status") != "ok":
            failure_kind = payload.get("failureKind")
            return ComputerUseResult.failed(
                ComputerUseOperation.ACCESSIBILITY_ACTION,
                str(payload.get("message") or "Accessibility action failed."),
                metadata={
                    **_target_identity_metadata(target_app, bundle_id),
                    "failure_kind": (
                        failure_kind
                        if isinstance(failure_kind, str) and failure_kind
                        else "accessibility_action_failed"
                    ),
                    "accessibility_action": payload,
                    "action_attempted": bool(payload.get("actionAttempted")),
                },
            )

        snapshot = payload.get("snapshotId")
        return ComputerUseResult.ok(
            ComputerUseOperation.ACCESSIBILITY_ACTION,
            "Ran Accessibility action.",
            snapshot_id=snapshot if isinstance(snapshot, str) else None,
            metadata={
                **_target_identity_metadata(target_app, bundle_id),
                "accessibility_action": payload,
                "action_attempted": bool(payload.get("actionAttempted")),
            },
        )

    def _run_accessibility_action_request(
        self,
        request: Mapping[str, Any],
        timeout: float,
    ) -> tuple[CommandResult, dict[str, Any]]:
        worker = self._accessibility_action_worker
        if worker is None:
            return self._run_accessibility_action_subprocess(request, timeout)

        worker_started = time.monotonic()
        worker_result = worker.run(request, timeout=timeout)
        worker_transport: dict[str, Any] = {
            "mode": "worker",
            "durationMs": _duration_ms(worker_started),
            "fallback": False,
        }
        return worker_result, worker_transport

    def _run_accessibility_action_subprocess(
        self,
        request: Mapping[str, Any],
        timeout: float,
    ) -> tuple[CommandResult, dict[str, Any]]:
        started = time.monotonic()
        result = self._runner.run(
            [
                sys.executable,
                "-c",
                _accessibility_action_script(),
                json.dumps(request, ensure_ascii=False),
            ],
            timeout=timeout,
        )
        return result, {
            "mode": "subprocess",
            "durationMs": _duration_ms(started),
            "fallback": False,
        }

    def _accessibility_action_allowlist_failure(
        self,
        target_app: str | None,
        bundle_id: str | None,
    ) -> ComputerUseResult | None:
        return self._accessibility_target_allowlist_failure(
            ComputerUseOperation.ACCESSIBILITY_ACTION,
            target_app,
            bundle_id,
            require_identity=True,
        )

    def _accessibility_target_allowlist_failure(
        self,
        operation: ComputerUseOperation,
        target_app: str | None,
        bundle_id: str | None,
        *,
        require_identity: bool,
    ) -> ComputerUseResult | None:
        metadata = _target_identity_metadata(target_app, bundle_id)
        if target_app is None and bundle_id is None:
            if not require_identity:
                return None
            return ComputerUseResult.needs_user(
                operation,
                "target_app or bundle_id is required for Accessibility action.",
                metadata=metadata,
            )
        if target_app is not None:
            if target_app not in self._allowed_apps:
                return ComputerUseResult.blocked(
                    operation,
                    f"App is not allowlisted: {target_app}",
                    metadata=metadata,
                )
            expected_bundle_id = self._allowed_apps.get(target_app)
            if expected_bundle_id and bundle_id and expected_bundle_id != bundle_id:
                return ComputerUseResult.blocked(
                    operation,
                    f"App bundle id is not allowlisted: {bundle_id}",
                    metadata={
                        **metadata,
                        "expected_bundle_id": expected_bundle_id,
                    },
                )
            return None
        allowed_bundle_ids = {
            item for item in self._allowed_apps.values() if isinstance(item, str) and item
        }
        if bundle_id not in allowed_bundle_ids:
            return ComputerUseResult.blocked(
                operation,
                f"App bundle id is not allowlisted: {bundle_id}",
                metadata=metadata,
            )
        return None

    def _effective_accessibility_bundle_id(
        self,
        target_app: str | None,
        bundle_id: str | None,
    ) -> str | None:
        if bundle_id is not None:
            return bundle_id
        if target_app is None:
            return None
        expected_bundle_id = self._allowed_apps.get(target_app)
        return expected_bundle_id if isinstance(expected_bundle_id, str) else None

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

        result = self._runner.run(
            [
                sys.executable,
                "-m",
                "computer_use_macos._coordinate_click",
                str(x),
                str(y),
            ],
            timeout=timeout,
        )
        if getattr(result, "timed_out", False):
            return _timed_out_result(
                ComputerUseOperation.CLICK,
                "Timed out clicking screen coordinate.",
                result,
                timeout,
                metadata={
                    "coordinateClick": True,
                    "method": "quartz_cg_event",
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
                    "method": "quartz_cg_event",
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
                "method": "quartz_cg_event",
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


def _mapping_from_payload(payload: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be an object")
    return dict(value)


_ACCESSIBILITY_QUERY_SAFE_ATTRIBUTES = {
    "AXRole",
    "AXSubrole",
    "AXRoleDescription",
    "AXTitle",
    "AXValue",
    "AXDescription",
    "AXHelp",
    "AXEnabled",
    "AXFocused",
    "AXSelected",
    "AXHidden",
    "AXPosition",
    "AXSize",
    "AXFrame",
    "AXIdentifier",
    "AXPlaceholderValue",
}

_ACCESSIBILITY_ROOT_RESOLVER_ATTRIBUTES = {
    "AXChildren",
    "AXContents",
    "AXRows",
    "AXVisibleRows",
}


def _normalize_accessibility_query_request(
    *,
    target_app: str | None,
    bundle_id: str | None,
    root: Mapping[str, Any] | None,
    query: Mapping[str, Any] | None,
    include_raw: bool,
) -> dict[str, Any]:
    root_payload = dict(root or {"kind": "focusedWindow"})
    root_kind = root_payload.get("kind", "focusedWindow")
    if root_kind not in {"focusedWindow", "frontmostApp", "axPath"}:
        raise ValueError("root.kind must be focusedWindow, frontmostApp, or axPath")
    if root_kind == "axPath":
        ax_path = root_payload.get("axPath") or root_payload.get("path")
        if not isinstance(ax_path, str) or not ax_path.strip():
            raise ValueError("root.axPath is required when root.kind is axPath")
        root_payload["axPath"] = ax_path.strip()
    root_resolver = root_payload.get("resolver")
    if root_resolver is not None:
        if root_kind != "axPath":
            raise ValueError("root.resolver is only supported for axPath roots")
        root_payload["resolver"] = _normalize_accessibility_root_resolver(
            root_resolver,
        )

    query_payload = dict(query or {})
    scope = query_payload.get("scope", "children")
    if scope not in {"self", "children", "descendants"}:
        raise ValueError("query.scope must be self, children, or descendants")
    query_payload["scope"] = scope
    query_payload["maxDepth"] = _bounded_int(
        query_payload.get("maxDepth"),
        default=1 if scope != "descendants" else 3,
        minimum=0,
        maximum=MAX_ACCESSIBILITY_QUERY_DEPTH,
        name="query.maxDepth",
    )
    query_payload["limit"] = _bounded_int(
        query_payload.get("limit"),
        default=50,
        minimum=1,
        maximum=500,
        name="query.limit",
    )
    query_payload["timeBudgetMs"] = _bounded_int(
        query_payload.get("timeBudgetMs"),
        default=500,
        minimum=50,
        maximum=15_000,
        name="query.timeBudgetMs",
    )

    raw_attributes = query_payload.get("attributes")
    if raw_attributes is None:
        attributes = [
            "AXRole",
            "AXSubrole",
            "AXTitle",
            "AXValue",
            "AXDescription",
            "AXEnabled",
            "AXFocused",
            "AXSelected",
            "AXHidden",
            "AXPosition",
            "AXSize",
            "AXFrame",
        ]
    else:
        if not isinstance(raw_attributes, list | tuple):
            raise TypeError("query.attributes must be a list of strings")
        attributes = []
        for item in raw_attributes:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("query.attributes items must be non-empty strings")
            attr = item.strip()
            if attr not in _ACCESSIBILITY_QUERY_SAFE_ATTRIBUTES:
                raise ValueError(f"unsupported accessibility attribute: {attr}")
            attributes.append(attr)
    query_payload["attributes"] = attributes

    actions = query_payload.get("actions", False)
    if not isinstance(actions, bool):
        raise TypeError("query.actions must be a boolean")
    query_payload["actions"] = actions

    include_children_count = query_payload.get("includeChildrenCount", True)
    if not isinstance(include_children_count, bool):
        raise TypeError("query.includeChildrenCount must be a boolean")
    query_payload["includeChildrenCount"] = include_children_count

    include_child_roles = query_payload.get("includeChildRoles", False)
    if not isinstance(include_child_roles, bool):
        raise TypeError("query.includeChildRoles must be a boolean")
    query_payload["includeChildRoles"] = include_child_roles

    include_descendant_roles = query_payload.get("includeDescendantRoles", False)
    if not isinstance(include_descendant_roles, bool):
        raise TypeError("query.includeDescendantRoles must be a boolean")
    query_payload["includeDescendantRoles"] = include_descendant_roles

    prefer_visible_rows = query_payload.get("preferVisibleRows")
    if prefer_visible_rows is not None:
        if not isinstance(prefer_visible_rows, bool):
            raise TypeError("query.preferVisibleRows must be a boolean")
        query_payload["preferVisibleRows"] = prefer_visible_rows

    match = query_payload.get("match")
    if match is None:
        query_payload["match"] = {}
    elif not isinstance(match, Mapping):
        raise TypeError("query.match must be an object")
    else:
        query_payload["match"] = dict(match)

    return {
        "targetApp": target_app,
        "bundleId": bundle_id,
        "root": root_payload,
        "query": query_payload,
        "includeRaw": include_raw,
    }


def _normalize_accessibility_root_resolver(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("root.resolver must be an object")
    strategy = value.get("strategy", "attributePath")
    if strategy != "attributePath":
        raise ValueError("root.resolver.strategy must be attributePath")
    raw_steps = value.get("steps")
    if not isinstance(raw_steps, list | tuple) or not raw_steps:
        raise ValueError("root.resolver.steps must be a non-empty list")
    steps: list[dict[str, int | str]] = []
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, Mapping):
            raise TypeError(f"root.resolver.steps[{index}] must be an object")
        attribute = raw_step.get("attribute")
        if not isinstance(attribute, str) or not attribute.strip():
            raise ValueError(
                f"root.resolver.steps[{index}].attribute must be non-empty"
            )
        normalized_attribute = attribute.strip()
        if normalized_attribute not in _ACCESSIBILITY_ROOT_RESOLVER_ATTRIBUTES:
            raise ValueError(
                "unsupported root resolver attribute: "
                f"{normalized_attribute}"
            )
        raw_item_index = raw_step.get("index")
        if (
            isinstance(raw_item_index, bool)
            or not isinstance(raw_item_index, int)
            or raw_item_index < 0
            or raw_item_index > 10_000
        ):
            raise ValueError(
                f"root.resolver.steps[{index}].index must be a non-negative integer"
            )
        step: dict[str, int | str] = {
            "attribute": normalized_attribute,
            "index": raw_item_index,
        }
        raw_path_index = raw_step.get("pathIndex", raw_step.get("path_index"))
        if raw_path_index is not None:
            if (
                isinstance(raw_path_index, bool)
                or not isinstance(raw_path_index, int)
                or raw_path_index < 0
                or raw_path_index > 10_000
            ):
                raise ValueError(
                    "root.resolver.steps"
                    f"[{index}].pathIndex must be a non-negative integer"
                )
            step["pathIndex"] = raw_path_index
        steps.append(step)
    return {
        "strategy": "attributePath",
        "steps": steps,
    }


_ACCESSIBILITY_ACTION_ALLOWLIST = {"AXPress", "AXSetFocus"}


def _accessibility_action_target_from_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    target = _mapping_from_payload(payload, "target")
    ax_path = _optional_string(payload, "axPath", "ax_path", "path")
    if target is not None and ax_path is not None:
        raise ValueError("target and axPath are mutually exclusive")
    if target is not None:
        return target
    if ax_path is not None:
        return {"kind": "axPath", "axPath": ax_path}
    return None


def _normalize_accessibility_action_request(
    *,
    target_app: str | None,
    bundle_id: str | None,
    snapshot_id: str | None,
    target: Mapping[str, Any] | None,
    action: str,
    preconditions: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    normalized_action = action.strip()
    if normalized_action not in _ACCESSIBILITY_ACTION_ALLOWLIST:
        raise ValueError(f"unsupported accessibility action: {normalized_action}")

    target_payload = dict(target or {})
    target_kind = target_payload.get("kind", "axPath")
    if target_kind != "axPath":
        raise ValueError("target.kind must be axPath")
    ax_path = target_payload.get("axPath") or target_payload.get("path")
    if not isinstance(ax_path, str) or not ax_path.strip():
        raise ValueError("target.axPath is required")
    target_payload["kind"] = "axPath"
    target_payload["axPath"] = ax_path.strip()

    return {
        "targetApp": target_app,
        "bundleId": bundle_id,
        "snapshotId": snapshot_id,
        "target": target_payload,
        "action": normalized_action,
        "preconditions": _normalize_accessibility_action_preconditions(
            preconditions or {}
        ),
    }


def _normalize_accessibility_action_preconditions(
    preconditions: Mapping[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for input_key, output_key in (
        ("roleIn", "roleIn"),
        ("labelIn", "labelIn"),
        ("actionIn", "actionIn"),
    ):
        value = preconditions.get(input_key)
        if value is None:
            continue
        if not isinstance(value, list | tuple):
            raise TypeError(f"preconditions.{input_key} must be a list")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"preconditions.{input_key} items must be non-empty strings"
                )
            items.append(item.strip())
        normalized[output_key] = items
    if "enabled" in preconditions:
        enabled = preconditions.get("enabled")
        if not isinstance(enabled, bool):
            raise TypeError("preconditions.enabled must be a boolean")
        normalized["enabled"] = enabled
    return normalized


def _accessibility_action_target_text(request: Mapping[str, Any]) -> str:
    action = request.get("action")
    target = request.get("target")
    if isinstance(target, Mapping):
        path = target.get("axPath")
        if isinstance(path, str):
            return f"{action} {path}"
    return str(action or "accessibility_action")


def _bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
    name: str,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return int(value)


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
    collection = _ACCESSIBILITY_ROLE_COLLECTIONS.get(role)
    if isinstance(name, str):
        target_name = name
        target_index = 0
    else:
        target_name = ""
        target_index = int(selector["index"])
    if collection is None:
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
    return (
        "on cleanText(rawValue)\n"
        "  try\n"
        "    return rawValue as text\n"
        "  on error\n"
        '    return ""\n'
        "  end try\n"
        "end cleanText\n"
        "\n"
        "on elementMatches(uiElement, targetName)\n"
        "  try\n"
        "    if my cleanText((name of uiElement)) is targetName then return true\n"
        "  end try\n"
        "  try\n"
        "    if my cleanText((description of uiElement)) is targetName then return true\n"
        "  end try\n"
        "  try\n"
        "    if my cleanText((title of uiElement)) is targetName then return true\n"
        "  end try\n"
        "  try\n"
        "    if my cleanText((value of uiElement)) is targetName then return true\n"
        "  end try\n"
        "  return false\n"
        "end elementMatches\n"
        "\n"
        'tell application "System Events"\n'
        f"  tell process {_applescript_string(target_app)}\n"
        "    set frontmost to true\n"
        "    set frontWindow to front window\n"
        f"    set roleName to {_applescript_string(role)}\n"
        f"    set targetName to {_applescript_string(target_name)}\n"
        f"    set targetIndex to {target_index}\n"
        f"    set candidates to {collection} of frontWindow\n"
        "    set currentIndex to 0\n"
        "    repeat with uiElement in candidates\n"
        "      set currentIndex to currentIndex + 1\n"
        "      if targetIndex > 0 then\n"
        "        if currentIndex is targetIndex then\n"
        "          click uiElement\n"
        "          return\n"
        "        end if\n"
        "      else if my elementMatches(uiElement, targetName) then\n"
        "        click uiElement\n"
        "        return\n"
        "      end if\n"
        "    end repeat\n"
        '    error "No matching accessibility selector target: " & roleName\n'
        "  end tell\n"
        "end tell\n"
    )


def _accessibility_snapshot_script() -> str:
    return (
        "on replaceText(theText, searchString, replacementString)\n"
        "  set oldDelimiters to AppleScript's text item delimiters\n"
        "  set AppleScript's text item delimiters to searchString\n"
        "  set textItems to text items of theText\n"
        "  set AppleScript's text item delimiters to replacementString\n"
        "  set replacedText to textItems as text\n"
        "  set AppleScript's text item delimiters to oldDelimiters\n"
        "  return replacedText\n"
        "end replaceText\n"
        "\n"
        "on cleanText(rawValue)\n"
        "  try\n"
        "    set textValue to rawValue as text\n"
        "  on error\n"
        '    return ""\n'
        "  end try\n"
        '  set textValue to my replaceText(textValue, tab, " ")\n'
        '  set textValue to my replaceText(textValue, linefeed, " ")\n'
        '  set textValue to my replaceText(textValue, (ASCII character 13), " ")\n'
        "  if (length of textValue) > 300 then set textValue to text 1 thru 300 of textValue\n"
        "  return textValue\n"
        "end cleanText\n"
        "\n"
        "on elementLine(uiElement, itemIndex)\n"
        '  set roleValue to ""\n'
        '  set roleDescriptionValue to ""\n'
        '  set nameValue to ""\n'
        '  set descriptionValue to ""\n'
        '  set titleValue to ""\n'
        '  set valueValue to ""\n'
        '  set focusedValue to ""\n'
        '  set xValue to ""\n'
        '  set yValue to ""\n'
        '  set widthValue to ""\n'
        '  set heightValue to ""\n'
        "  try\n"
        "    set roleValue to my cleanText((role of uiElement))\n"
        "  end try\n"
        "  try\n"
        "    set nameValue to my cleanText((name of uiElement))\n"
        "  end try\n"
        "  try\n"
        "    set descriptionValue to my cleanText((description of uiElement))\n"
        "  end try\n"
        "  try\n"
        "    set titleValue to my cleanText((title of uiElement))\n"
        "  end try\n"
        "  try\n"
        "    set valueValue to my cleanText((value of uiElement))\n"
        "  end try\n"
        "  try\n"
        "    set focusedValue to my cleanText((focused of uiElement))\n"
        "  end try\n"
        "  try\n"
        "    set positionValue to position of uiElement\n"
        "    set xValue to my cleanText((item 1 of positionValue))\n"
        "    set yValue to my cleanText((item 2 of positionValue))\n"
        "  end try\n"
        "  try\n"
        "    set sizeValue to size of uiElement\n"
        "    set widthValue to my cleanText((item 1 of sizeValue))\n"
        "    set heightValue to my cleanText((item 2 of sizeValue))\n"
        "  end try\n"
        "  return itemIndex & tab & roleValue & tab & roleDescriptionValue & tab & nameValue & tab & descriptionValue & tab & titleValue & tab & valueValue & tab & focusedValue & tab & xValue & tab & yValue & tab & widthValue & tab & heightValue\n"
        "end elementLine\n"
        "\n"
        'tell application "System Events"\n'
        "  set frontApp to first application process whose frontmost is true\n"
        '  set outputText to ""\n'
        "  try\n"
        '    set focusedElement to value of attribute "AXFocusedUIElement" of frontApp\n'
        '    set outputText to outputText & "focused" & tab & my elementLine(focusedElement, 0) & linefeed\n'
        "  on error errMsg\n"
        '    set outputText to outputText & "focusedError" & tab & my cleanText(errMsg) & linefeed\n'
        "  end try\n"
        "  try\n"
        "    set itemIndex to 0\n"
        "    repeat with uiElement in (text fields of front window of frontApp)\n"
        "      set itemIndex to itemIndex + 1\n"
        '      set outputText to outputText & "textField" & tab & my elementLine(uiElement, itemIndex) & linefeed\n'
        "      if itemIndex >= 30 then exit repeat\n"
        "    end repeat\n"
        "    if itemIndex < 30 then\n"
        "      repeat with uiElement in (text areas of front window of frontApp)\n"
        "        set itemIndex to itemIndex + 1\n"
        '        set outputText to outputText & "textField" & tab & my elementLine(uiElement, itemIndex) & linefeed\n'
        "        if itemIndex >= 30 then exit repeat\n"
        "      end repeat\n"
        "    end if\n"
        "  on error errMsg\n"
        '    set outputText to outputText & "textFieldsError" & tab & my cleanText(errMsg) & linefeed\n'
        "  end try\n"
        "  return outputText\n"
        "end tell\n"
    )


def _accessibility_query_script() -> str:
    return r'''
from __future__ import annotations

import json
import re
import sys
import time
from typing import Any


APPKIT_FRAMEWORK_PATH = "/System/Library/Frameworks/AppKit.framework"
CHILDREN_ATTRIBUTE = "AXChildren"
CONTENTS_ATTRIBUTE = "AXContents"
VISIBLE_ROWS_ATTRIBUTE = "AXVisibleRows"
ROOT_RESOLVER_ATTRIBUTES = {
    CHILDREN_ATTRIBUTE,
    CONTENTS_ATTRIBUTE,
    "AXRows",
    VISIBLE_ROWS_ATTRIBUTE,
}
AX_VALUE_NUMBER_RE = re.compile(r"([xywh]):(-?\d+(?:\.\d+)?)")
STARTED_AT = time.monotonic()
QUERY_STARTED_AT = STARTED_AT
ATTRIBUTE_CACHE: dict[tuple[str, str], list[Any] | Any | None] = {}
ROOT_RESOLUTION: dict[str, Any] = {
    "strategy": "default",
    "durationMs": 0,
}
STEP_TIMINGS: list[dict[str, Any]] = []
LAST_STEP_AT = STARTED_AT


def elapsed_ms(started: float | None = None, ended: float | None = None) -> int:
    base = STARTED_AT if started is None else started
    finish = time.monotonic() if ended is None else ended
    return max(0, int(round((finish - base) * 1000)))


def mark_step(name: str) -> None:
    global LAST_STEP_AT
    now = time.monotonic()
    STEP_TIMINGS.append(
        {
            "name": name,
            "startedMs": elapsed_ms(STARTED_AT, LAST_STEP_AT),
            "durationMs": elapsed_ms(LAST_STEP_AT, now),
        }
    )
    LAST_STEP_AT = now


def fail(failure_kind: str, message: str) -> None:
    print(
        json.dumps(
            {
                "available": False,
                "failureKind": failure_kind,
                "message": message,
                "diagnostics": {
                    "durationMs": elapsed_ms(),
                    "stepTimings": list(STEP_TIMINGS),
                },
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


try:
    REQUEST = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    mark_step("parseRequest")
except Exception as exc:
    mark_step("parseRequest")
    fail("accessibility_query_invalid_request", str(exc))

try:
    import objc
    from ApplicationServices import (
        AXIsProcessTrusted,
        AXUIElementCopyActionNames,
        AXUIElementCopyAttributeNames,
        AXUIElementCopyAttributeValue,
        AXUIElementCreateApplication,
        kAXFocusedWindowAttribute,
    )
    mark_step("pyobjcImport")
except Exception as exc:
    mark_step("pyobjcImport")
    fail("accessibility_query_pyobjc_unavailable", str(exc))


def ax_get(element: Any, attr: str) -> Any:
    try:
        err, value = AXUIElementCopyAttributeValue(element, attr, None)
        if err != 0:
            return None
        return value
    except Exception:
        return None


def ax_attribute_names(element: Any) -> list[str]:
    try:
        err, names = AXUIElementCopyAttributeNames(element, None)
        if err != 0 or names is None:
            return []
        return [str(name) for name in names]
    except Exception:
        return []


def ax_actions(element: Any) -> list[str]:
    try:
        err, actions = AXUIElementCopyActionNames(element, None)
        if err != 0 or actions is None:
            return []
        return [str(action) for action in actions]
    except Exception:
        return []


def app_matches_bundle(app: Any, bundle_id: str) -> bool:
    try:
        return str(app.bundleIdentifier() or "") == bundle_id
    except Exception:
        return False


def app_matches_name(app: Any, app_name: str) -> bool:
    try:
        return str(app.localizedName() or "").casefold() == app_name.casefold()
    except Exception:
        return False


def app_is_usable(app: Any) -> bool:
    try:
        return not bool(app.isTerminated())
    except Exception:
        return True


def selected_running_app() -> Any:
    bundle_id = str(REQUEST.get("bundleId") or "").strip()
    target_app = str(REQUEST.get("targetApp") or "").strip()
    workspace = objc.lookUpClass("NSWorkspace").sharedWorkspace()
    frontmost = workspace.frontmostApplication()
    if bundle_id:
        if (
            frontmost is not None
            and app_matches_bundle(frontmost, bundle_id)
            and app_is_usable(frontmost)
        ):
            return frontmost
        running_application = objc.lookUpClass("NSRunningApplication")
        apps = running_application.runningApplicationsWithBundleIdentifier_(bundle_id)
        for candidate in apps or []:
            try:
                if bool(candidate.isActive()) and app_is_usable(candidate):
                    return candidate
            except Exception:
                pass
        for candidate in apps or []:
            if app_is_usable(candidate):
                return candidate
        fail(
            "accessibility_query_target_app_not_running",
            f"No running app found for bundle id: {bundle_id}",
        )
    if target_app:
        if (
            frontmost is not None
            and app_matches_name(frontmost, target_app)
            and app_is_usable(frontmost)
        ):
            return frontmost
        fail(
            "accessibility_query_target_app_not_frontmost",
            f"Target app is not frontmost: {target_app}",
        )
    return frontmost


def safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    text = str(value)
    if len(text) > 500:
        return text[:500] + "...<truncated>"
    return text


def numbers_from_ax_value(value: Any) -> dict[str, float]:
    if isinstance(value, str):
        return {key: float(raw) for key, raw in AX_VALUE_NUMBER_RE.findall(value)}
    text = str(value)
    return {key: float(raw) for key, raw in AX_VALUE_NUMBER_RE.findall(text)}


def frame_from_attrs(attrs: dict[str, Any]) -> dict[str, float] | None:
    frame_numbers = numbers_from_ax_value(attrs.get("AXFrame"))
    if {"x", "y", "w", "h"} <= frame_numbers.keys():
        return {
            "x": frame_numbers["x"],
            "y": frame_numbers["y"],
            "width": frame_numbers["w"],
            "height": frame_numbers["h"],
        }
    position_numbers = numbers_from_ax_value(attrs.get("AXPosition"))
    size_numbers = numbers_from_ax_value(attrs.get("AXSize"))
    if {"x", "y"} <= position_numbers.keys() and {"w", "h"} <= size_numbers.keys():
        return {
            "x": position_numbers["x"],
            "y": position_numbers["y"],
            "width": size_numbers["w"],
            "height": size_numbers["h"],
        }
    return None


def ax_role(element: Any) -> str:
    value = safe_scalar(cached_ax_get(element, "AXRole"))
    return str(value or "")


def element_cache_key(element: Any) -> str:
    return str(element)


def cached_ax_get(element: Any, attr: str) -> Any:
    key = (element_cache_key(element), attr)
    if key not in ATTRIBUTE_CACHE:
        ATTRIBUTE_CACHE[key] = ax_get(element, attr)
    return ATTRIBUTE_CACHE[key]


def attribute_list(element: Any, attr: str) -> list[Any]:
    value = cached_ax_get(element, attr)
    if not value:
        return []
    try:
        return list(value)
    except Exception:
        return []


def prefer_visible_rows() -> bool:
    query = REQUEST.get("query") if isinstance(REQUEST.get("query"), dict) else {}
    return bool(query.get("preferVisibleRows", False))


def child_attribute_for(element: Any) -> str:
    if prefer_visible_rows() and ax_role(element) == "AXTable":
        visible_rows = attribute_list(element, VISIBLE_ROWS_ATTRIBUTE)
        if visible_rows:
            return VISIBLE_ROWS_ATTRIBUTE
    return CHILDREN_ATTRIBUTE


def children_of(element: Any) -> list[Any]:
    return attribute_list(element, child_attribute_for(element))


def path_children_of(element: Any) -> list[Any]:
    return attribute_list(element, CHILDREN_ATTRIBUTE)


def child_path_index(parent: Any, child: Any, fallback_index: int) -> int:
    if not (prefer_visible_rows() and ax_role(parent) == "AXTable"):
        return fallback_index
    value = safe_scalar(cached_ax_get(child, "AXIndex"))
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return fallback_index


def child_entries(element: Any) -> list[tuple[int, Any]]:
    return [
        (child_path_index(element, child, index), child)
        for index, child in enumerate(children_of(element))
    ]


def append_unique_role(roles: list[str], role: str) -> None:
    if role and role not in roles:
        roles.append(role)


def child_roles_of(element: Any) -> list[str]:
    roles: list[str] = []
    for child in children_of(element):
        append_unique_role(roles, ax_role(child))
    return roles


def descendant_roles_of(element: Any, max_depth: int, limit: int = 200) -> list[str]:
    roles: list[str] = []
    visited = 0

    def visit(current: Any, depth: int) -> None:
        nonlocal visited
        if depth <= 0 or visited >= limit:
            return
        for child in children_of(current):
            if visited >= limit:
                return
            visited += 1
            append_unique_role(roles, ax_role(child))
            visit(child, depth - 1)

    visit(element, max_depth)
    return roles


def windows_of(app_element: Any) -> list[Any]:
    windows = ax_get(app_element, "AXWindows")
    if not windows:
        return []
    try:
        return list(windows)
    except Exception:
        return []


def focused_window_for_app(app_element: Any) -> Any | None:
    focused = ax_get(app_element, kAXFocusedWindowAttribute)
    if focused is not None and ax_role(focused) == "AXWindow":
        return focused
    for candidate in windows_of(app_element):
        if ax_role(candidate) == "AXWindow":
            return candidate
    return None


def time_budget_exceeded() -> bool:
    query = REQUEST.get("query") if isinstance(REQUEST.get("query"), dict) else {}
    budget_ms = int(query.get("timeBudgetMs") or 500)
    return (time.monotonic() - QUERY_STARTED_AT) * 1000 >= budget_ms


def root_resolver_steps(resolver: Any) -> list[dict[str, Any]]:
    if not isinstance(resolver, dict):
        return []
    if resolver.get("strategy") != "attributePath":
        return []
    steps = resolver.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def resolve_root_with_attribute_path(
    app_element: Any,
    window: Any | None,
    raw_path: str,
    resolver: Any,
) -> tuple[Any | None, str]:
    steps = root_resolver_steps(resolver)
    if not steps:
        return None, raw_path
    if raw_path == "app" or raw_path.startswith("app/"):
        current = app_element
        current_path = "app"
    elif raw_path in {"", "0"} or raw_path.startswith("0/"):
        if window is None:
            return None, raw_path
        current = window
        current_path = "0"
    else:
        return None, raw_path
    for step in steps:
        attr = str(step.get("attribute") or "")
        if attr not in ROOT_RESOLVER_ATTRIBUTES:
            return None, raw_path
        try:
            index = int(step.get("index"))
            path_index = int(step.get("pathIndex", index))
        except Exception:
            return None, raw_path
        values = attribute_list(current, attr)
        if index < 0 or index >= len(values) or path_index < 0:
            return None, raw_path
        current = values[index]
        current_path = f"{current_path}/{path_index}"
    return current, current_path


def resolve_root_inner(app_element: Any, window: Any | None) -> tuple[Any | None, str]:
    root = REQUEST.get("root") if isinstance(REQUEST.get("root"), dict) else {}
    kind = root.get("kind", "focusedWindow")
    if kind == "frontmostApp":
        return app_element, "app"
    if kind == "focusedWindow":
        if window is None:
            return None, "0"
        return window, "0"
    if kind != "axPath":
        return None, "0"
    raw_path = str(root.get("axPath") or root.get("path") or "").strip()
    resolver = root.get("resolver")
    if resolver is not None:
        ROOT_RESOLUTION["requestedAxPath"] = raw_path
        resolved_element, resolved_path = resolve_root_with_attribute_path(
            app_element,
            window,
            raw_path,
            resolver,
        )
        if resolved_element is not None:
            ROOT_RESOLUTION["strategy"] = "attributePath"
            ROOT_RESOLUTION["resolvedAxPath"] = resolved_path
            return resolved_element, resolved_path
        ROOT_RESOLUTION["strategy"] = "attributePathFallback"
    if raw_path == "app":
        return app_element, "app"
    if raw_path.startswith("app/"):
        current = app_element
        current_path = "app"
        for raw_index in raw_path.split("/")[1:]:
            try:
                index = int(raw_index)
            except ValueError:
                return None, raw_path
            children = path_children_of(current)
            if index < 0 or index >= len(children):
                return None, raw_path
            current = children[index]
            current_path = f"{current_path}/{index}"
        return current, current_path
    if window is None:
        return None, raw_path
    if raw_path in {"", "0"}:
        return window, "0"
    parts = raw_path.split("/")
    if not parts or parts[0] != "0":
        return None, raw_path
    current = window
    current_path = "0"
    for raw_index in parts[1:]:
        try:
            index = int(raw_index)
        except ValueError:
            return None, raw_path
        children = path_children_of(current)
        if index < 0 or index >= len(children):
            return None, raw_path
        current = children[index]
        current_path = f"{current_path}/{index}"
    return current, current_path


def resolve_root(app_element: Any, window: Any | None) -> tuple[Any | None, str]:
    started = time.monotonic()
    root_element, root_path = resolve_root_inner(app_element, window)
    ROOT_RESOLUTION["durationMs"] = int(round((time.monotonic() - started) * 1000))
    ROOT_RESOLUTION["resolvedAxPath"] = root_path
    return root_element, root_path


def read_node(element: Any, path: str) -> dict[str, Any]:
    query = REQUEST.get("query") if isinstance(REQUEST.get("query"), dict) else {}
    requested_attrs = query.get("attributes") or []
    raw_attrs: dict[str, Any] = {}
    for attr in requested_attrs:
        value = safe_scalar(cached_ax_get(element, attr))
        if value is not None:
            raw_attrs[attr] = value
    node: dict[str, Any] = {"axPath": path}
    mapping = {
        "AXRole": "role",
        "AXSubrole": "subrole",
        "AXRoleDescription": "roleDescription",
        "AXTitle": "title",
        "AXValue": "value",
        "AXDescription": "description",
        "AXHelp": "help",
        "AXEnabled": "enabled",
        "AXFocused": "focused",
        "AXSelected": "selected",
        "AXIdentifier": "identifier",
        "AXPlaceholderValue": "placeholder",
    }
    for attr, output_key in mapping.items():
        if attr in raw_attrs:
            node[output_key] = raw_attrs[attr]
    frame = frame_from_attrs(raw_attrs)
    if frame is not None:
        node["frame"] = frame
    if bool(query.get("actions", False)):
        actions = ax_actions(element)
        if actions:
            node["actions"] = actions
    if bool(query.get("includeChildrenCount", True)):
        node["childrenCount"] = len(children_of(element))
    if bool(query.get("includeChildRoles", False)):
        node["childRoles"] = child_roles_of(element)
    if bool(query.get("includeDescendantRoles", False)):
        node["descendantRoles"] = descendant_roles_of(
            element,
            int(query.get("maxDepth") or 1),
        )
    if bool(REQUEST.get("includeRaw", False)):
        node["raw"] = raw_attrs
    return node


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).casefold()


def string_set(value: Any) -> set[str]:
    if isinstance(value, list | tuple):
        return {str(item).casefold() for item in value}
    if value is None:
        return set()
    return {str(value).casefold()}


def role_filter_allows(element: Any) -> bool:
    query = REQUEST.get("query") if isinstance(REQUEST.get("query"), dict) else {}
    match = query.get("match") if isinstance(query.get("match"), dict) else {}
    if "role" not in match and "roleIn" not in match:
        return True
    role = text_value(safe_scalar(cached_ax_get(element, "AXRole")))
    if "role" in match and role != text_value(match.get("role")):
        return False
    if "roleIn" in match and role not in string_set(match.get("roleIn")):
        return False
    return True


def node_matches(node: dict[str, Any]) -> bool:
    query = REQUEST.get("query") if isinstance(REQUEST.get("query"), dict) else {}
    match = query.get("match") if isinstance(query.get("match"), dict) else {}
    if not match:
        return True
    role = text_value(node.get("role"))
    if "role" in match and role != text_value(match.get("role")):
        return False
    if "roleIn" in match and role not in string_set(match.get("roleIn")):
        return False
    description = text_value(node.get("description"))
    if "description" in match and description != text_value(match.get("description")):
        return False
    if "descriptionIn" in match and description not in string_set(match.get("descriptionIn")):
        return False
    if "descriptionContains" in match and text_value(match.get("descriptionContains")) not in description:
        return False
    title = text_value(node.get("title"))
    if "titleContains" in match and text_value(match.get("titleContains")) not in title:
        return False
    if "valueEquals" in match and node.get("value") != match.get("valueEquals"):
        return False
    if "enabled" in match and node.get("enabled") is not bool(match.get("enabled")):
        return False
    if "focused" in match and node.get("focused") is not bool(match.get("focused")):
        return False
    return True


def collect(root_element: Any, root_path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = REQUEST.get("query") if isinstance(REQUEST.get("query"), dict) else {}
    scope = str(query.get("scope") or "children")
    max_depth = int(query.get("maxDepth") or 1)
    limit = int(query.get("limit") or 50)
    nodes: list[dict[str, Any]] = []
    diagnostics = {
        "durationMs": 0,
        "truncated": False,
        "nodeCount": 0,
    }

    def visit(element: Any, path: str, depth: int, include_self: bool) -> None:
        if len(nodes) >= limit:
            diagnostics["truncated"] = True
            diagnostics["truncationReason"] = "limit"
            return
        if time_budget_exceeded():
            diagnostics["truncated"] = True
            diagnostics["truncationReason"] = "time_budget"
            return
        diagnostics["nodeCount"] += 1
        if include_self:
            if role_filter_allows(element):
                node = read_node(element, path)
                if node_matches(node):
                    nodes.append(node)
                    if len(nodes) >= limit:
                        diagnostics["truncated"] = True
                        diagnostics["truncationReason"] = "limit"
                        return
        if scope == "self" or depth >= max_depth:
            return
        for index, child in child_entries(element):
            visit(child, f"{path}/{index}", depth + 1, True)
            if diagnostics["truncated"]:
                return

    if scope == "self":
        visit(root_element, root_path, 0, True)
    elif scope == "children":
        for index, child in child_entries(root_element):
            visit(child, f"{root_path}/{index}", 1, True)
            if diagnostics["truncated"]:
                break
    else:
        for index, child in child_entries(root_element):
            visit(child, f"{root_path}/{index}", 1, True)
            if diagnostics["truncated"]:
                break
    diagnostics["durationMs"] = int(round((time.monotonic() - QUERY_STARTED_AT) * 1000))
    return nodes, diagnostics


permission_available = bool(AXIsProcessTrusted())
mark_step("permissionCheck")
if not permission_available:
    fail(
        "missing_accessibility",
        "Accessibility permission is not available for the Python process.",
    )

try:
    try:
        objc.lookUpClass("NSWorkspace")
    except Exception:
        objc.loadBundle("AppKit", globals(), bundle_path=APPKIT_FRAMEWORK_PATH)
    mark_step("appKitLoad")
except Exception as exc:
    mark_step("appKitLoad")
    fail("accessibility_query_frontmost_app_failed", str(exc))

try:
    app = selected_running_app()
    mark_step("selectRunningApp")
except Exception as exc:
    mark_step("selectRunningApp")
    fail("accessibility_query_frontmost_app_failed", str(exc))

if app is None:
    fail("accessibility_query_no_frontmost_app", "No frontmost app is available.")

pid = int(app.processIdentifier())
mark_step("readProcessIdentifier")
app_ax = AXUIElementCreateApplication(pid)
mark_step("createApplicationElement")
root_request = REQUEST.get("root") if isinstance(REQUEST.get("root"), dict) else {}
root_kind = root_request.get("kind", "focusedWindow")
raw_root_path = str(root_request.get("axPath") or root_request.get("path") or "").strip()
mark_step("readRootRequest")
window = focused_window_for_app(app_ax)
mark_step("focusedWindow")
if (
    window is None
    and root_kind != "frontmostApp"
    and raw_root_path != "app"
    and not raw_root_path.startswith("app/")
):
    fail("accessibility_query_no_focused_window", "No focused window is available.")

root_element, root_path = resolve_root(app_ax, window)
mark_step("resolveRoot")
if root_element is None:
    fail("accessibility_query_root_not_found", "Could not resolve query root.")

window_title = safe_scalar(ax_get(window, "AXTitle")) if window is not None else None
window_frame = (
    frame_from_attrs(
        {
            "AXFrame": ax_get(window, "AXFrame"),
            "AXPosition": ax_get(window, "AXPosition"),
            "AXSize": ax_get(window, "AXSize"),
        }
    )
    if window is not None
    else None
)
mark_step("windowTitle")
QUERY_STARTED_AT = time.monotonic()
nodes, diagnostics = collect(root_element, root_path)
mark_step("collect")
diagnostics["rootResolution"] = dict(ROOT_RESOLUTION)
if prefer_visible_rows():
    diagnostics["preferVisibleRows"] = True
app_name = str(app.localizedName() or "")
bundle_id = str(app.bundleIdentifier() or "")
snapshot_id = f"frontmost:{app_name}:{window_title or ''}"
mark_step("responseMetadata")
payload = {
    "schema": "macos.accessibility.query.v1",
    "available": True,
    "snapshotId": snapshot_id,
    "app": {
        "name": app_name,
        "bundleId": bundle_id,
        "pid": pid,
    },
    "window": {
        "title": str(window_title or ""),
        "role": (
            str(safe_scalar(ax_get(window, "AXRole")) or "AXWindow")
            if window is not None
            else ""
        ),
        "frame": window_frame,
    },
    "root": {
        "axPath": root_path,
    },
    "nodes": nodes,
    "diagnostics": diagnostics,
}
mark_step("buildResponse")
diagnostics["stepTimings"] = list(STEP_TIMINGS)
serialized_payload = json.dumps(payload, ensure_ascii=False)
mark_step("serializeResponse")
diagnostics["stepTimings"] = list(STEP_TIMINGS)
serialized_payload = json.dumps(payload, ensure_ascii=False)
print(serialized_payload)
'''


def _accessibility_query_worker_script() -> str:
    query_script = json.dumps(_accessibility_query_script(), ensure_ascii=False)
    return f'''
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import traceback

APPKIT_FRAMEWORK_PATH = "/System/Library/Frameworks/AppKit.framework"
QUERY_SCRIPT = {query_script}


def warm_frameworks() -> None:
    status = "ok"
    message = ""
    try:
        import objc
        import ApplicationServices  # noqa: F401
        try:
            objc.loadBundle("AppKit", globals(), bundle_path=APPKIT_FRAMEWORK_PATH)
        except Exception:
            objc.lookUpClass("NSWorkspace")
    except Exception as exc:
        status = "error"
        message = str(exc)
    print(
        json.dumps(
            {{
                "workerReady": True,
                "status": status,
                "message": message,
            }},
            ensure_ascii=False,
        ),
        flush=True,
    )


def run_query(raw_request: str) -> str:
    output = StringIO()
    original_argv = sys.argv
    sys.argv = ["accessibility_query_worker", raw_request]
    namespace = {{"__name__": "__main__"}}
    try:
        with redirect_stdout(output):
            try:
                exec(QUERY_SCRIPT, namespace)
            except SystemExit:
                pass
    except BaseException as exc:
        return json.dumps(
            {{
                "available": False,
                "failureKind": "accessibility_query_worker_failed",
                "message": str(exc),
                "diagnostics": {{
                    "workerException": traceback.format_exc(limit=8),
                }},
            }},
            ensure_ascii=False,
        )
    finally:
        sys.argv = original_argv
    lines = [line.strip() for line in output.getvalue().splitlines() if line.strip()]
    if not lines:
        return json.dumps(
            {{
                "available": False,
                "failureKind": "accessibility_query_worker_empty_response",
                "message": "Accessibility query worker produced no response.",
            }},
            ensure_ascii=False,
        )
    return lines[-1]


warm_frameworks()
for line in sys.stdin:
    raw_request = line.strip()
    if not raw_request:
        continue
    print(run_query(raw_request), flush=True)
'''


def _accessibility_action_script() -> str:
    return r'''
from __future__ import annotations

import json
import sys
import time
from typing import Any


APPKIT_FRAMEWORK_PATH = "/System/Library/Frameworks/AppKit.framework"
CHILDREN_ATTRIBUTE = "AXChildren"
STARTED_AT = time.monotonic()


def finish(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def fail(failure_kind: str, message: str, *, target: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "schema": "macos.accessibility.action.result.v1",
        "available": False,
        "status": "failed",
        "failureKind": failure_kind,
        "message": message,
        "actionAttempted": False,
        "diagnostics": {
            "durationMs": int(round((time.monotonic() - STARTED_AT) * 1000)),
        },
    }
    if target is not None:
        payload["target"] = target
    finish(payload)


try:
    REQUEST = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
except Exception as exc:
    fail("invalid_request", str(exc))

try:
    import objc
    from ApplicationServices import (
        AXIsProcessTrusted,
        AXUIElementCopyActionNames,
        AXUIElementCopyAttributeValue,
        AXUIElementCreateApplication,
        AXUIElementPerformAction,
        AXUIElementSetAttributeValue,
        kAXFocusedWindowAttribute,
    )
except Exception as exc:
    fail("accessibility_action_pyobjc_unavailable", str(exc))


def ax_get(element: Any, attr: str) -> Any:
    try:
        err, value = AXUIElementCopyAttributeValue(element, attr, None)
        if err != 0:
            return None
        return value
    except Exception:
        return None


def ax_actions(element: Any) -> list[str]:
    try:
        err, actions = AXUIElementCopyActionNames(element, None)
        if err != 0 or actions is None:
            return []
        return [str(action) for action in actions]
    except Exception:
        return []


def ax_perform_action(element: Any, action: str) -> int:
    try:
        return int(AXUIElementPerformAction(element, action))
    except Exception:
        return -1


def ax_set_focused(element: Any) -> int:
    try:
        return int(AXUIElementSetAttributeValue(element, "AXFocused", True))
    except Exception:
        return -1


def safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    text = str(value)
    if len(text) > 500:
        return text[:500] + "...<truncated>"
    return text


def children_of(element: Any) -> list[Any]:
    children = ax_get(element, CHILDREN_ATTRIBUTE)
    if not children:
        return []
    try:
        return list(children)
    except Exception:
        return []


def ax_role(element: Any) -> str:
    value = safe_scalar(ax_get(element, "AXRole"))
    return str(value or "")


def windows_of(app_element: Any) -> list[Any]:
    windows = ax_get(app_element, "AXWindows")
    if not windows:
        return []
    try:
        return list(windows)
    except Exception:
        return []


def focused_window_for_app(app_element: Any) -> Any | None:
    focused = ax_get(app_element, kAXFocusedWindowAttribute)
    if focused is not None and ax_role(focused) == "AXWindow":
        return focused
    for candidate in windows_of(app_element):
        if ax_role(candidate) == "AXWindow":
            return candidate
    return None


def app_matches_bundle(app: Any, bundle_id: str) -> bool:
    try:
        return str(app.bundleIdentifier() or "") == bundle_id
    except Exception:
        return False


def app_matches_name(app: Any, app_name: str) -> bool:
    try:
        return str(app.localizedName() or "").casefold() == app_name.casefold()
    except Exception:
        return False


def app_is_usable(app: Any) -> bool:
    try:
        return not bool(app.isTerminated())
    except Exception:
        return True


def selected_running_app() -> Any:
    bundle_id = str(REQUEST.get("bundleId") or "").strip()
    target_app = str(REQUEST.get("targetApp") or "").strip()
    workspace = objc.lookUpClass("NSWorkspace").sharedWorkspace()
    frontmost = workspace.frontmostApplication()
    if bundle_id:
        if (
            frontmost is not None
            and app_matches_bundle(frontmost, bundle_id)
            and app_is_usable(frontmost)
        ):
            return frontmost
        running_application = objc.lookUpClass("NSRunningApplication")
        apps = running_application.runningApplicationsWithBundleIdentifier_(bundle_id)
        for candidate in apps or []:
            try:
                if bool(candidate.isActive()) and app_is_usable(candidate):
                    return candidate
            except Exception:
                pass
        for candidate in apps or []:
            if app_is_usable(candidate):
                return candidate
        fail(
            "target_app_not_running",
            f"No running app found for bundle id: {bundle_id}",
        )
    if target_app:
        if (
            frontmost is not None
            and app_matches_name(frontmost, target_app)
            and app_is_usable(frontmost)
        ):
            return frontmost
        fail(
            "target_app_not_frontmost",
            f"Target app is not frontmost: {target_app}",
        )
    return frontmost


def resolve_ax_path(window: Any, raw_path: str) -> tuple[Any | None, str]:
    ax_path = str(raw_path or "").strip()
    if ax_path in {"", "0"}:
        return window, "0"
    parts = ax_path.split("/")
    if not parts or parts[0] != "0":
        return None, ax_path
    current = window
    current_path = "0"
    for raw_index in parts[1:]:
        try:
            index = int(raw_index)
        except ValueError:
            return None, ax_path
        children = children_of(current)
        if index < 0 or index >= len(children):
            return None, ax_path
        current = children[index]
        current_path = f"{current_path}/{index}"
    return current, current_path


def label_for(element: Any) -> str:
    for attr in ("AXDescription", "AXTitle", "AXValue", "AXPlaceholderValue", "AXHelp"):
        value = safe_scalar(ax_get(element, attr))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def target_facts(element: Any, ax_path: str) -> dict[str, Any]:
    enabled = safe_scalar(ax_get(element, "AXEnabled"))
    facts: dict[str, Any] = {
        "axPath": ax_path,
        "role": ax_role(element),
        "label": label_for(element),
        "actions": ax_actions(element),
    }
    if isinstance(enabled, bool):
        facts["enabled"] = enabled
    return facts


def string_set(value: Any) -> set[str]:
    if isinstance(value, list | tuple):
        return {str(item).casefold() for item in value}
    if value is None:
        return set()
    return {str(value).casefold()}


def validate_preconditions(facts: dict[str, Any], action: str) -> str | None:
    preconditions = REQUEST.get("preconditions")
    if not isinstance(preconditions, dict):
        preconditions = {}
    role_set = string_set(preconditions.get("roleIn"))
    if role_set and str(facts.get("role") or "").casefold() not in role_set:
        return "role did not match preconditions.roleIn"
    label_set = string_set(preconditions.get("labelIn"))
    if label_set and str(facts.get("label") or "").casefold() not in label_set:
        return "label did not match preconditions.labelIn"
    expected_enabled = bool(preconditions.get("enabled"))
    if "enabled" in preconditions and facts.get("enabled") is not expected_enabled:
        return "enabled did not match preconditions.enabled"
    action_set = string_set(preconditions.get("actionIn"))
    if action_set and action.casefold() not in action_set:
        return "action did not match preconditions.actionIn"
    action_names = {str(item).casefold() for item in facts.get("actions") or []}
    if action != "AXSetFocus" and action.casefold() not in action_names:
        role = str(facts.get("role") or "")
        if action == "AXPress" and role == "AXRow":
            return None
        return f"target does not expose action: {action}"
    return None


if not AXIsProcessTrusted():
    fail(
        "missing_accessibility",
        "Accessibility permission is not available for the Python process.",
    )

action = str(REQUEST.get("action") or "").strip()
if action not in {"AXPress", "AXSetFocus"}:
    fail("unsupported_accessibility_action", f"Unsupported Accessibility action: {action}")

target = REQUEST.get("target")
if not isinstance(target, dict):
    fail("invalid_request", "target must be an object")
if target.get("kind", "axPath") != "axPath":
    fail("invalid_request", "target.kind must be axPath")
ax_path = str(target.get("axPath") or target.get("path") or "").strip()
if not ax_path:
    fail("invalid_request", "target.axPath is required")

try:
    objc.loadBundle("AppKit", globals(), bundle_path=APPKIT_FRAMEWORK_PATH)
    app = selected_running_app()
except Exception as exc:
    fail("target_app_not_running", str(exc))

if app is None:
    fail("target_app_not_running", "No frontmost app is available.")

pid = int(app.processIdentifier())
app_ax = AXUIElementCreateApplication(pid)
window = focused_window_for_app(app_ax)
if window is None:
    fail("focused_window_missing", "No focused window is available.")

window_title = safe_scalar(ax_get(window, "AXTitle"))
app_name = str(app.localizedName() or "")
bundle_id = str(app.bundleIdentifier() or "")
snapshot_id = f"frontmost:{app_name}:{window_title or ''}"
expected_snapshot_id = str(REQUEST.get("snapshotId") or "").strip()
if expected_snapshot_id and expected_snapshot_id != snapshot_id:
    fail(
        "snapshot_stale",
        "Target snapshot is stale.",
        target={"axPath": ax_path},
    )

element, resolved_path = resolve_ax_path(window, ax_path)
if element is None:
    fail("ax_path_not_found", "Could not resolve target axPath.", target={"axPath": ax_path})

facts = target_facts(element, resolved_path)
precondition_failure = validate_preconditions(facts, action)
if precondition_failure is not None:
    fail("precondition_failed", precondition_failure, target=facts)

method = "AXUIElementPerformAction"
if action == "AXSetFocus":
    method = "AXUIElementSetAttributeValue"
    err = ax_set_focused(element)
else:
    err = ax_perform_action(element, action)
if err != 0:
    fail(
        "accessibility_action_failed",
        f"{method} returned error: {err}",
        target=facts,
    )

finish(
    {
        "schema": "macos.accessibility.action.result.v1",
        "available": True,
        "status": "ok",
        "operation": "accessibility_action",
        "method": method,
        "snapshotId": snapshot_id,
        "action": action,
        "actionAttempted": True,
        "target": facts,
        "app": {
            "name": app_name,
            "bundleId": bundle_id,
            "pid": pid,
        },
        "window": {
            "title": str(window_title or ""),
            "role": str(safe_scalar(ax_get(window, "AXRole")) or "AXWindow"),
        },
        "diagnostics": {
            "durationMs": int(round((time.monotonic() - STARTED_AT) * 1000)),
            "verifiedPreconditions": True,
        },
    }
)
'''


def _accessibility_action_worker_script() -> str:
    action_script = json.dumps(_accessibility_action_script(), ensure_ascii=False)
    return f'''
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import traceback

APPKIT_FRAMEWORK_PATH = "/System/Library/Frameworks/AppKit.framework"
ACTION_SCRIPT = {action_script}


def warm_frameworks() -> None:
    status = "ok"
    message = ""
    try:
        import objc
        import ApplicationServices  # noqa: F401
        try:
            objc.loadBundle("AppKit", globals(), bundle_path=APPKIT_FRAMEWORK_PATH)
        except Exception:
            objc.lookUpClass("NSWorkspace")
    except Exception as exc:
        status = "error"
        message = str(exc)
    print(
        json.dumps(
            {{
                "workerReady": True,
                "status": status,
                "message": message,
            }},
            ensure_ascii=False,
        ),
        flush=True,
    )


def run_action(raw_request: str) -> str:
    output = StringIO()
    original_argv = sys.argv
    sys.argv = ["accessibility_action_worker", raw_request]
    namespace = {{"__name__": "__main__"}}
    try:
        with redirect_stdout(output):
            try:
                exec(ACTION_SCRIPT, namespace)
            except SystemExit:
                pass
    except BaseException as exc:
        return json.dumps(
            {{
                "available": False,
                "failureKind": "accessibility_action_worker_failed",
                "message": str(exc),
                "actionAttempted": False,
                "diagnostics": {{
                    "workerException": traceback.format_exc(limit=8),
                }},
            }},
            ensure_ascii=False,
        )
    finally:
        sys.argv = original_argv
    lines = [line.strip() for line in output.getvalue().splitlines() if line.strip()]
    if not lines:
        return json.dumps(
            {{
                "available": False,
                "failureKind": "accessibility_action_worker_empty_response",
                "message": "Accessibility action worker produced no response.",
                "actionAttempted": False,
            }},
            ensure_ascii=False,
        )
    return lines[-1]


warm_frameworks()
for line in sys.stdin:
    raw_request = line.strip()
    if not raw_request:
        continue
    print(run_action(raw_request), flush=True)
'''


def _accessibility_tree_snapshot_script() -> str:
    return r'''
from __future__ import annotations

import json
import sys
import time
from typing import Any


APPKIT_FRAMEWORK_PATH = "/System/Library/Frameworks/AppKit.framework"
CHILDREN_ATTRIBUTE = "AXChildren"
SAFE_ATTRIBUTES = (
    "AXRole",
    "AXSubrole",
    "AXRoleDescription",
    "AXTitle",
    "AXValue",
    "AXDescription",
    "AXHelp",
    "AXEnabled",
    "AXFocused",
    "AXSelected",
    "AXHidden",
    "AXPosition",
    "AXSize",
    "AXFrame",
    "AXIdentifier",
    "AXPlaceholderValue",
)
MAX_DEPTH = 6
MAX_CHILDREN_PER_NODE = 1200
MAX_TEXT_CHARS = 500
TIME_BUDGET_SECONDS = 12.0
if len(sys.argv) > 1:
    try:
        TIME_BUDGET_SECONDS = max(0.5, float(sys.argv[1]))
    except ValueError:
        pass
TARGET_BUNDLE_ID = sys.argv[2].strip() if len(sys.argv) > 2 else ""
STARTED_AT = time.monotonic()
STATE = {
    "node_count": 0,
    "truncated": False,
    "truncation_reason": None,
}


def fail(failure_kind: str, message: str) -> None:
    print(
        json.dumps(
            {
                "available": False,
                "failureKind": failure_kind,
                "message": message,
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


try:
    import objc
    from ApplicationServices import (
        AXIsProcessTrusted,
        AXUIElementCopyActionNames,
        AXUIElementCopyAttributeNames,
        AXUIElementCopyAttributeValue,
        AXUIElementCreateApplication,
        kAXFocusedWindowAttribute,
    )
except Exception as exc:
    fail("accessibility_tree_pyobjc_unavailable", str(exc))


def ax_get(element: Any, attr: str) -> Any:
    try:
        err, value = AXUIElementCopyAttributeValue(element, attr, None)
        if err != 0:
            return None
        return value
    except Exception:
        return None


def ax_attribute_names(element: Any) -> list[str]:
    try:
        err, names = AXUIElementCopyAttributeNames(element, None)
        if err != 0 or names is None:
            return []
        return [str(name) for name in names]
    except Exception:
        return []


def ax_actions(element: Any) -> list[str]:
    try:
        err, actions = AXUIElementCopyActionNames(element, None)
        if err != 0 or actions is None:
            return []
        return [str(action) for action in actions]
    except Exception:
        return []


def time_budget_exceeded() -> bool:
    return time.monotonic() - STARTED_AT >= TIME_BUDGET_SECONDS


def mark_truncated(reason: str) -> None:
    STATE["truncated"] = True
    STATE["truncation_reason"] = reason


def selected_running_app() -> Any:
    workspace = objc.lookUpClass("NSWorkspace").sharedWorkspace()
    frontmost = workspace.frontmostApplication()
    if TARGET_BUNDLE_ID:
        if (
            frontmost is not None
            and app_matches_bundle(frontmost, TARGET_BUNDLE_ID)
            and app_is_usable(frontmost)
        ):
            return frontmost
        running_application = objc.lookUpClass("NSRunningApplication")
        apps = running_application.runningApplicationsWithBundleIdentifier_(
            TARGET_BUNDLE_ID
        )
        for candidate in apps or []:
            try:
                if bool(candidate.isActive()) and app_is_usable(candidate):
                    return candidate
            except Exception:
                pass
        for candidate in apps or []:
            if app_is_usable(candidate):
                return candidate
        fail(
            "accessibility_tree_target_app_not_running",
            f"No running app found for bundle id: {TARGET_BUNDLE_ID}",
        )
    return frontmost


def app_matches_bundle(app: Any, bundle_id: str) -> bool:
    try:
        return str(app.bundleIdentifier() or "") == bundle_id
    except Exception:
        return False


def app_is_usable(app: Any) -> bool:
    try:
        return not bool(app.isTerminated())
    except Exception:
        return True


def safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    text = str(value)
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS] + "...<truncated>"
    return text


def dump_element(element: Any, *, depth: int = 0, path: str = "0") -> dict[str, Any]:
    node: dict[str, Any] = {
        "path": path,
        "depth": depth,
    }
    if time_budget_exceeded():
        mark_truncated("time_budget_exceeded")
        node["truncated"] = True
        node["truncationReason"] = "time_budget_exceeded"
        return node
    STATE["node_count"] = int(STATE["node_count"]) + 1
    attribute_names = ax_attribute_names(element)
    node["attribute_names"] = attribute_names
    attribute_name_set = set(attribute_names)
    for attr in SAFE_ATTRIBUTES:
        if attr not in attribute_name_set:
            continue
        if time_budget_exceeded():
            mark_truncated("time_budget_exceeded")
            node["attributes_truncated"] = True
            break
        value = safe_scalar(ax_get(element, attr))
        if value is not None:
            node[attr] = value
    if not time_budget_exceeded():
        actions = ax_actions(element)
        if actions:
            node["actions"] = actions
    if depth >= MAX_DEPTH or time_budget_exceeded():
        if time_budget_exceeded():
            mark_truncated("time_budget_exceeded")
            node["children_truncated"] = True
            node["truncationReason"] = "time_budget_exceeded"
        return node
    children = (
        ax_get(element, CHILDREN_ATTRIBUTE)
        if CHILDREN_ATTRIBUTE in attribute_name_set
        else None
    )
    if children:
        try:
            node["children_count"] = len(children)
        except Exception:
            node["children_count"] = 0
        node["children"] = []
        for index, child in enumerate(children):
            if index >= MAX_CHILDREN_PER_NODE:
                node["children_truncated"] = True
                node["truncationReason"] = "max_children_per_node"
                mark_truncated("max_children_per_node")
                break
            if time_budget_exceeded():
                node["children_truncated"] = True
                node["truncationReason"] = "time_budget_exceeded"
                mark_truncated("time_budget_exceeded")
                break
            node["children"].append(
                dump_element(child, depth=depth + 1, path=f"{path}/{index}")
            )
    else:
        node["children_count"] = 0
    return node


if not AXIsProcessTrusted():
    fail(
        "missing_accessibility",
        "Accessibility permission is not available for the Python process.",
    )

try:
    objc.loadBundle("AppKit", globals(), bundle_path=APPKIT_FRAMEWORK_PATH)
    app = selected_running_app()
except Exception as exc:
    fail("accessibility_tree_frontmost_app_failed", str(exc))

if app is None:
    fail("accessibility_tree_no_frontmost_app", "No frontmost app is available.")

pid = int(app.processIdentifier())
app_ax = AXUIElementCreateApplication(pid)
window = ax_get(app_ax, kAXFocusedWindowAttribute)
if window is None:
    fail("accessibility_tree_no_focused_window", "No focused window is available.")

payload = {
    "available": True,
    "app": {
        "name": str(app.localizedName() or ""),
        "bundleId": str(app.bundleIdentifier() or ""),
        "pid": pid,
    },
    "focusedWindow": dump_element(window),
}
if STATE["truncated"]:
    payload["truncated"] = True
    if STATE["truncation_reason"]:
        payload["truncationReason"] = STATE["truncation_reason"]
payload["nodeCount"] = STATE["node_count"]
print(json.dumps(payload, ensure_ascii=False))
'''


_ACCESSIBILITY_ELEMENT_FIELDS = (
    "index",
    "role",
    "roleDescription",
    "name",
    "description",
    "title",
    "value",
    "focused",
    "x",
    "y",
    "width",
    "height",
)


def _accessibility_snapshot_from_stdout(stdout: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"available": True}
    text_fields: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        kind = parts[0]
        if kind == "focused":
            snapshot["focusedElement"] = _accessibility_element_from_fields(parts[1:])
        elif kind == "textField":
            text_fields.append(_accessibility_element_from_fields(parts[1:]))
        elif kind in {"focusedError", "textFieldsError"}:
            errors.append({"kind": kind, "message": parts[1] if len(parts) > 1 else ""})
    if text_fields:
        snapshot["textFields"] = text_fields
    if errors:
        snapshot["errors"] = errors
    if "focusedElement" not in snapshot and not text_fields:
        snapshot["available"] = False
        snapshot.setdefault("failureKind", "accessibility_snapshot_empty")
    return snapshot


def _accessibility_element_from_fields(fields: list[str]) -> dict[str, Any]:
    values = fields + [""] * (len(_ACCESSIBILITY_ELEMENT_FIELDS) - len(fields))
    raw = dict(zip(_ACCESSIBILITY_ELEMENT_FIELDS, values, strict=False))
    element: dict[str, Any] = {}
    index = _int_or_none(raw["index"])
    if index is not None:
        element["index"] = index
    for key in ("role", "roleDescription", "name", "description", "title", "value"):
        value = raw[key].strip()
        if value:
            element[key] = value
    focused = _bool_or_none(raw["focused"])
    if focused is not None:
        element["focused"] = focused
    frame = {
        key: parsed
        for key in ("x", "y", "width", "height")
        if (parsed := _int_or_none(raw[key])) is not None
    }
    if frame:
        element["frame"] = frame
    return element


def _int_or_none(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None


def _bool_or_none(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


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


def _optional_bool(
    payload: Mapping[str, Any],
    *keys: str,
    default: bool,
) -> bool:
    for key in keys:
        if key in payload:
            value = payload[key]
            if not isinstance(value, bool):
                raise TypeError(f"{key} must be a boolean")
            return value
    return default


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
    "accessibility": "accessibility",
    "accessibility_query": "accessibilityQuery",
    "accessibility_action": "accessibilityAction",
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
