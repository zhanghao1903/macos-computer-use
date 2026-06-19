from __future__ import annotations

import unittest

from macos_computer_use.models import ComputerUseOperation, RiskLevel
from macos_computer_use.policy import SafetyPolicy


class PolicyTests(unittest.TestCase):
    def test_send_click_requires_confirmation(self) -> None:
        risk = SafetyPolicy().classify(ComputerUseOperation.CLICK, target="Send")

        self.assertEqual(risk.level, RiskLevel.HIGH)
        self.assertTrue(risk.requires_confirmation)
        self.assertEqual(risk.risk_label, "high_risk_click")

    def test_password_target_is_never_supported(self) -> None:
        risk = SafetyPolicy().classify(
            ComputerUseOperation.CLICK,
            target="Password field",
        )

        self.assertEqual(risk.level, RiskLevel.HIGH)
        self.assertFalse(risk.requires_confirmation)
        self.assertEqual(risk.risk_label, "security_or_password")

    def test_low_risk_target_is_allowed(self) -> None:
        risk = SafetyPolicy().classify(ComputerUseOperation.CLICK, target="Cancel")

        self.assertEqual(risk.level, RiskLevel.LOW)
        self.assertFalse(risk.requires_confirmation)

    def test_coordinate_click_is_disabled_by_default(self) -> None:
        risk = SafetyPolicy().classify(
            ComputerUseOperation.CLICK,
            coordinate_click=True,
        )

        self.assertEqual(risk.level, RiskLevel.HIGH)
        self.assertFalse(risk.requires_confirmation)
        self.assertEqual(risk.risk_label, "coordinate_click_disabled")


if __name__ == "__main__":
    unittest.main()
