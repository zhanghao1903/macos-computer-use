from __future__ import annotations

import unittest

from macos_computer_use.models import ComputerUseReadinessStatus
from macos_computer_use.readiness import build_readiness


class FakeProbe:
    def __init__(
        self,
        platform: str = "Darwin",
        accessibility: bool = True,
        screen_recording: bool | None = None,
    ) -> None:
        self.platform = platform
        self.accessibility = accessibility
        self.screen_recording = screen_recording

    def platform_name(self) -> str:
        return self.platform

    def accessibility_trusted(self) -> bool:
        return self.accessibility

    def screen_recording_available(self) -> bool | None:
        return self.screen_recording


class ReadinessTests(unittest.TestCase):
    def test_backend_disabled(self) -> None:
        readiness = build_readiness(enabled=False, probe=FakeProbe())

        self.assertEqual(readiness.status, ComputerUseReadinessStatus.BACKEND_DISABLED)

    def test_unsupported_platform(self) -> None:
        readiness = build_readiness(enabled=True, probe=FakeProbe(platform="Linux"))

        self.assertEqual(
            readiness.status,
            ComputerUseReadinessStatus.UNSUPPORTED_PLATFORM,
        )

    def test_missing_accessibility(self) -> None:
        readiness = build_readiness(
            enabled=True,
            probe=FakeProbe(accessibility=False),
        )

        self.assertEqual(
            readiness.status,
            ComputerUseReadinessStatus.MISSING_ACCESSIBILITY,
        )

    def test_ready(self) -> None:
        readiness = build_readiness(enabled=True, probe=FakeProbe())

        self.assertEqual(readiness.status, ComputerUseReadinessStatus.READY)
        self.assertTrue(readiness.ready)


if __name__ == "__main__":
    unittest.main()
