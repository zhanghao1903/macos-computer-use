from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from app_control_protocol import ToolCommand

from _tool_test_support import (
    contradictory_predispatch_action_response,
    definite_unsupported_accessibility_action_response,
    failed_accessibility_action_response,
    predispatch_accessibility_action_response,
)
from wechat_desktop_tool._action_safety import (
    _BooleanEvidence,
    _accessibility_action_request_dispatched,
    _action_ref_expiry_failure,
    _action_ref_identity_failure,
    _selector_fallback_from_action_ref,
    _should_fallback_from_accessibility_action,
    _should_press_return_for_search_result,
    _should_try_coordinate_click_after_accessibility_action,
)


def _command() -> ToolCommand:
    return ToolCommand(
        command_id="cmd_action",
        tool="wechat.desktop",
        operation="execute_action",
    )


class ActionSafetyTests(unittest.TestCase):
    def test_evidence_values_remain_frozen(self) -> None:
        evidence = _BooleanEvidence(present=True, valid=True, value=False)

        with self.assertRaises(FrozenInstanceError):
            setattr(evidence, "value", True)

    def test_predispatch_timeout_allows_existing_fallbacks(self) -> None:
        result = predispatch_accessibility_action_response()

        dispatched = _accessibility_action_request_dispatched(result)
        self.assertTrue(dispatched.present)
        self.assertTrue(dispatched.valid)
        self.assertEqual(dispatched.value, False)
        for policy in (
            _should_fallback_from_accessibility_action,
            _should_try_coordinate_click_after_accessibility_action,
            _should_press_return_for_search_result,
        ):
            with self.subTest(policy=policy.__name__):
                self.assertTrue(policy(result, expected_action="AXPress"))

    def test_complete_native_unsupported_proof_allows_fallback(self) -> None:
        result = definite_unsupported_accessibility_action_response()

        self.assertTrue(
            _should_fallback_from_accessibility_action(
                result,
                expected_action="AXPress",
            )
        )

    def test_unknown_or_contradictory_effect_never_allows_replay(self) -> None:
        for result in (
            failed_accessibility_action_response(),
            contradictory_predispatch_action_response(),
        ):
            for policy in (
                _should_fallback_from_accessibility_action,
                _should_try_coordinate_click_after_accessibility_action,
                _should_press_return_for_search_result,
            ):
                with self.subTest(
                    failure=result.failure_kind,
                    policy=policy.__name__,
                ):
                    self.assertFalse(policy(result, expected_action="AXPress"))

    def test_expired_or_invalid_action_ref_fails_before_execution(self) -> None:
        for expires_at in ("2000-01-01T00:00:00Z", "not-a-date"):
            with self.subTest(expires_at=expires_at):
                result = _action_ref_expiry_failure(
                    _command(),
                    {"id": "nav.contacts.press", "expiresAt": expires_at},
                )

                assert result is not None
                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "wechat_action_ref_expired")
                self.assertEqual(
                    result.observation["actionId"],
                    "nav.contacts.press",
                )

    def test_row_identity_and_selector_fallback_contracts_are_stable(self) -> None:
        action_ref = {
            "id": "chats.visible.0.open",
            "target": {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "label": "Ada,hello,09:00",
            },
            "preconditions": {"roleIn": ["AXRow"]},
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {"role": "AXRow", "name": "Ada,hello,09:00"},
                }
            ],
        }

        failure = _action_ref_identity_failure(_command(), action_ref)

        assert failure is not None
        self.assertEqual(
            failure.failure_kind,
            "wechat_action_precondition_failed",
        )
        self.assertEqual(
            _selector_fallback_from_action_ref(action_ref),
            {"role": "AXRow", "name": "Ada,hello,09:00"},
        )


if __name__ == "__main__":
    unittest.main()
