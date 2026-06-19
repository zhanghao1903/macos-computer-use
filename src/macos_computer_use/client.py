"""Public client for conservative macOS computer-use primitives."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import time

from .commands import CommandRunner, SubprocessCommandRunner
from .models import (
    ComputerUseOperation,
    ComputerUseReadiness,
    ComputerUseReadinessStatus,
    ComputerUseResult,
)
from .policy import SafetyPolicy
from .readiness import DefaultPermissionProbe, PermissionProbe, build_readiness


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _bounded(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


class MacOSComputerUseClient:
    """Small, LLM-free macOS automation client.

    The client exposes conservative primitives only. It never stores raw screen
    contents and does not own user confirmation.
    """

    def __init__(
        self,
        *,
        allowed_apps: Iterable[str] | Mapping[str, str] = (),
        enabled: bool = True,
        allow_coordinate_click: bool = False,
        screen_recording_required: bool = False,
        max_text_chars: int = 4000,
        probe: PermissionProbe | None = None,
        runner: CommandRunner | None = None,
        policy: SafetyPolicy | None = None,
    ) -> None:
        self._enabled = enabled
        self._allow_coordinate_click = allow_coordinate_click
        self._screen_recording_required = screen_recording_required
        self._max_text_chars = max_text_chars
        self._probe = probe or DefaultPermissionProbe()
        self._runner = runner or SubprocessCommandRunner()
        self._policy = policy or SafetyPolicy()
        self._allowed_apps = self._normalize_allowed_apps(allowed_apps)

    @staticmethod
    def _normalize_allowed_apps(
        allowed_apps: Iterable[str] | Mapping[str, str],
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

    def open_app(self, app: str, *, timeout: float = 10.0) -> ComputerUseResult:
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
                metadata={"app": app},
            )

        result = self._runner.run(["open", "-a", app], timeout=timeout)
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.OPEN_APP,
                "Failed to open allowlisted app.",
                metadata={"app": app, "stderr": _bounded(result.stderr, 1000)},
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.OPEN_APP,
            f"Opened app: {app}",
            metadata={"app": app},
        )

    def observe(
        self,
        *,
        target_app: str | None = None,
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
            "  set windowTitle to \"\"\n"
            "  try\n"
            "    set windowTitle to name of front window of frontApp\n"
            "  end try\n"
            '  return appName & "\\n" & windowTitle\n'
            "end tell\n"
        )
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.OBSERVE,
                "Failed to observe frontmost app via Accessibility.",
                metadata={"stderr": _bounded(result.stderr, 1000)},
            )

        lines = result.stdout.splitlines()
        app_name = lines[0].strip() if lines else ""
        window_title = lines[1].strip() if len(lines) > 1 else ""

        if target_app and app_name != target_app:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.OBSERVE,
                f"Target app is not frontmost: expected {target_app}, got {app_name}.",
                metadata={"target_app": target_app, "frontmost_app": app_name},
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
            metadata={"frontmost_app": app_name, "window_title": window_title},
        )

    def type_text(
        self,
        text: str,
        *,
        target_app: str | None = None,
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

        if target_app:
            observed = self.observe(target_app=target_app, timeout=timeout)
            if not observed.success:
                return observed
        else:
            readiness = self.readiness()
            if readiness.status != ComputerUseReadinessStatus.READY:
                return ComputerUseResult.not_available(
                    ComputerUseOperation.TYPE_TEXT,
                    "macOS type_text is unavailable until readiness is ready.",
                    metadata={"readiness": readiness.to_dict()},
                )

        script = (
            'tell application "System Events"\n'
            f"  keystroke {_applescript_string(text)}\n"
            "end tell\n"
        )
        result = self._runner.run(["osascript", "-e", script], timeout=timeout)
        if result.returncode != 0:
            return ComputerUseResult.failed(
                ComputerUseOperation.TYPE_TEXT,
                "Failed to type text into the focused editable target.",
                metadata={"stderr": _bounded(result.stderr, 1000)},
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.TYPE_TEXT,
            "Typed text into the focused editable target.",
            metadata={"chars": len(text), "submitted": False},
        )

    def click(
        self,
        target: str,
        *,
        target_app: str | None = None,
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
                metadata={"target": target},
            )

        observed = self.observe(target_app=target_app, timeout=timeout)
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
        if result.returncode != 0:
            return ComputerUseResult.needs_user(
                ComputerUseOperation.CLICK,
                "Could not resolve a safe semantic button target.",
                metadata={
                    "target": target,
                    "target_app": target_app,
                    "stderr": _bounded(result.stderr, 1000),
                },
            )
        return ComputerUseResult.ok(
            ComputerUseOperation.CLICK,
            "Clicked semantic target.",
            metadata={"target": target, "target_app": target_app},
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
