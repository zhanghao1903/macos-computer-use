"""Readiness and permission probing."""

from __future__ import annotations

import ctypes
import platform
from typing import Protocol

from .models import (
    ComputerUseOperation,
    ComputerUseReadiness,
    ComputerUseReadinessStatus,
)


DEFAULT_ENABLED_OPERATIONS: tuple[ComputerUseOperation, ...] = (
    ComputerUseOperation.OBSERVE,
    ComputerUseOperation.ACCESSIBILITY_QUERY,
    ComputerUseOperation.OPEN_APP,
    ComputerUseOperation.FOCUS_APP,
    ComputerUseOperation.CLICK,
    ComputerUseOperation.TYPE_TEXT,
    ComputerUseOperation.PRESS_KEY,
    ComputerUseOperation.HOTKEY,
    ComputerUseOperation.WAIT,
)


class PermissionProbe(Protocol):
    def platform_name(self) -> str:
        """Return the host platform name, e.g. Darwin."""

    def accessibility_trusted(self) -> bool:
        """Return whether Accessibility permission is available."""

    def screen_recording_available(self) -> bool | None:
        """Return screen recording readiness, or None when not probed."""

    def apple_events_available(self) -> bool | None:
        """Return Apple Events readiness, or None when not probed."""


class DefaultPermissionProbe:
    """Best-effort macOS permission probe.

    The probe is intentionally conservative. Probe failures are treated as not
    trusted instead of attempting unsafe fallback behavior.
    """

    def platform_name(self) -> str:
        return platform.system()

    def accessibility_trusted(self) -> bool:
        if self.platform_name() != "Darwin":
            return False
        try:
            app_services = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/ApplicationServices.framework/"
                "ApplicationServices"
            )
            app_services.AXIsProcessTrusted.restype = ctypes.c_bool
            return bool(app_services.AXIsProcessTrusted())
        except Exception:
            return False

    def screen_recording_available(self) -> bool | None:
        if self.platform_name() != "Darwin":
            return False
        try:
            core_graphics = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
            )
            preflight = core_graphics.CGPreflightScreenCaptureAccess
            preflight.restype = ctypes.c_bool
            return bool(preflight())
        except Exception:
            return None

    def apple_events_available(self) -> bool | None:
        # Automation permission is target-app specific on macOS. There is no
        # useful global yes/no probe without naming a target application.
        return None


def build_readiness(
    *,
    enabled: bool,
    probe: PermissionProbe,
    screen_recording_required: bool = False,
    enabled_operations: tuple[ComputerUseOperation, ...] = DEFAULT_ENABLED_OPERATIONS,
) -> ComputerUseReadiness:
    platform_name = probe.platform_name()

    if not enabled:
        return ComputerUseReadiness(
            status=ComputerUseReadinessStatus.BACKEND_DISABLED,
            platform=platform_name,
            accessibility_trusted=False,
            screen_recording_required=screen_recording_required,
            setup_hint="Enable macOS computer-use before running desktop operations.",
        )

    if platform_name != "Darwin":
        return ComputerUseReadiness(
            status=ComputerUseReadinessStatus.UNSUPPORTED_PLATFORM,
            platform=platform_name,
            accessibility_trusted=False,
            screen_recording_required=screen_recording_required,
            setup_hint="computer-use-macos is only available on macOS.",
        )

    accessibility_trusted = probe.accessibility_trusted()
    screen_recording_available = _probe_optional_bool(
        probe,
        "screen_recording_available",
    )
    apple_events_available = _probe_optional_bool(probe, "apple_events_available")

    if not accessibility_trusted:
        return ComputerUseReadiness(
            status=ComputerUseReadinessStatus.MISSING_ACCESSIBILITY,
            platform=platform_name,
            accessibility_trusted=False,
            screen_recording_available=screen_recording_available,
            screen_recording_required=screen_recording_required,
            apple_events_available=apple_events_available,
            setup_hint=(
                "Grant Accessibility permission to the Python process or host app "
                "in System Settings > Privacy & Security > Accessibility."
            ),
        )

    if screen_recording_required and not screen_recording_available:
        return ComputerUseReadiness(
            status=ComputerUseReadinessStatus.MISSING_SCREEN_RECORDING,
            platform=platform_name,
            accessibility_trusted=True,
            screen_recording_available=screen_recording_available,
            screen_recording_required=True,
            apple_events_available=apple_events_available,
            setup_hint=(
                "Grant Screen Recording permission in System Settings > Privacy "
                "& Security > Screen Recording."
            ),
        )

    return ComputerUseReadiness(
        status=ComputerUseReadinessStatus.READY,
        platform=platform_name,
        accessibility_trusted=True,
        screen_recording_available=screen_recording_available,
        screen_recording_required=screen_recording_required,
        apple_events_available=apple_events_available,
        enabled_operations=enabled_operations,
    )


def _probe_optional_bool(probe: PermissionProbe, method_name: str) -> bool | None:
    method = getattr(probe, method_name, None)
    if method is None:
        return None
    try:
        value = method()
    except Exception:
        return None
    if value is None:
        return None
    return bool(value)
