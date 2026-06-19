"""Readiness and permission probing."""

from __future__ import annotations

import ctypes
import platform
from typing import Protocol

from .models import ComputerUseOperation, ComputerUseReadiness, ComputerUseReadinessStatus


DEFAULT_ENABLED_OPERATIONS: tuple[ComputerUseOperation, ...] = (
    ComputerUseOperation.OBSERVE,
    ComputerUseOperation.OPEN_APP,
    ComputerUseOperation.CLICK,
    ComputerUseOperation.TYPE_TEXT,
    ComputerUseOperation.WAIT,
)


class PermissionProbe(Protocol):
    def platform_name(self) -> str:
        """Return the host platform name, e.g. Darwin."""

    def accessibility_trusted(self) -> bool:
        """Return whether Accessibility permission is available."""

    def screen_recording_available(self) -> bool | None:
        """Return screen recording readiness, or None when not probed."""


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
            setup_hint="macos-computer-use is only available on macOS.",
        )

    accessibility_trusted = probe.accessibility_trusted()
    screen_recording_available = probe.screen_recording_available()

    if not accessibility_trusted:
        return ComputerUseReadiness(
            status=ComputerUseReadinessStatus.MISSING_ACCESSIBILITY,
            platform=platform_name,
            accessibility_trusted=False,
            screen_recording_available=screen_recording_available,
            screen_recording_required=screen_recording_required,
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
        enabled_operations=enabled_operations,
    )
