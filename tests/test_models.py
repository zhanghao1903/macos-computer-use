from __future__ import annotations

import unittest

from macos_computer_use import __version__
from macos_computer_use.models import (
    ComputerUseOperation,
    ComputerUseReadiness,
    ComputerUseReadinessStatus,
    ComputerUseResult,
    RiskDecision,
    RiskLevel,
)


class ModelTests(unittest.TestCase):
    def test_version_is_exposed(self) -> None:
        self.assertEqual(__version__, "0.1.0")

    def test_result_to_dict_serializes_enums(self) -> None:
        result = ComputerUseResult.ok(
            ComputerUseOperation.WAIT,
            "Waited.",
            metadata={"seconds": 1.0},
        )

        data = result.to_dict()

        self.assertEqual(data["operation"], "wait")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["metadata"], {"seconds": 1.0})

    def test_readiness_ready_property(self) -> None:
        readiness = ComputerUseReadiness(
            status=ComputerUseReadinessStatus.READY,
            platform="Darwin",
            accessibility_trusted=True,
        )

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.to_dict()["status"], "ready")

    def test_result_to_dict_serializes_nested_risk(self) -> None:
        result = ComputerUseResult.blocked(
            ComputerUseOperation.CLICK,
            "confirmation required",
            risk=RiskDecision(
                level=RiskLevel.HIGH,
                requires_confirmation=True,
                risk_label="external_message",
                reason="Send action.",
                action_fingerprint="abc",
            ),
            metadata={"confirmation_required": True},
        )

        data = result.to_dict()

        self.assertEqual(data["risk"]["level"], "high")  # type: ignore[index]
        self.assertEqual(
            data["risk"]["requires_confirmation"],  # type: ignore[index]
            True,
        )


if __name__ == "__main__":
    unittest.main()
