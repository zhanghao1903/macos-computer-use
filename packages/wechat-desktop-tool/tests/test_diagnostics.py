from __future__ import annotations

import unittest

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus

from wechat_desktop_tool._diagnostics import (
    _failure,
    _optional_string_from_mapping,
    _positive_int,
    _redact_input_text,
    _with_timing,
)
from wechat_desktop_tool._query_mapping import _public_accessibility_element
from wechat_desktop_tool._row_parsing import (
    _messages_from_text_extract_with_truncation,
)


class DiagnosticsTests(unittest.TestCase):
    def test_redaction_is_limited_to_sensitive_input_fields(self) -> None:
        payload = {
            "message": "semantic result",
            "input": {
                "message": "secret message",
                "text": "secret text",
                "contact": "Ada",
                "nested": [{"text": "nested secret"}],
            },
        }

        self.assertEqual(
            _redact_input_text(payload),
            {
                "message": "semantic result",
                "input": {
                    "message": "[redacted]",
                    "text": "[redacted]",
                    "contact": "Ada",
                    "nested": [{"text": "[redacted]"}],
                },
            },
        )

    def test_text_message_parsing_and_limit_are_stable(self) -> None:
        messages, truncated = _messages_from_text_extract_with_truncation(
            "[09:00] incoming: first\n10:15 me: second\nplain",
            limit=2,
        )

        self.assertTrue(truncated)
        self.assertEqual(
            [message.to_dict() for message in messages],
            [
                {
                    "text": "first",
                    "direction": "incoming",
                    "visibleTimestamp": "09:00",
                },
                {
                    "text": "second",
                    "direction": "outgoing",
                    "visibleTimestamp": "10:15",
                },
            ],
        )

    def test_failure_builder_preserves_protocol_fields(self) -> None:
        command = ToolCommand(
            command_id="cmd_failure",
            tool="wechat.desktop",
            operation="list_contacts",
        )

        result = _failure(
            command,
            status=ToolStatus.NOT_FOUND,
            failure_kind="contact_not_found",
            message="No contact matched.",
            recovery_hint="Use a complete display name.",
            retryable=True,
            observation={"target": "Ada"},
            evidence={"query": {"available": True}},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.command_id, "cmd_failure")
        self.assertEqual(result.failure_kind, "contact_not_found")
        self.assertEqual(result.status, ToolStatus.NOT_FOUND)
        self.assertEqual(result.observation, {"target": "Ada"})
        assert result.error is not None
        self.assertEqual(result.error.phase, "list_contacts")
        self.assertEqual(result.error.evidence["query"], {"available": True})

    def test_public_accessibility_element_excludes_raw_fields(self) -> None:
        public = _public_accessibility_element(
            {
                "role": "AXTextField",
                "description": "搜索",
                "focused": True,
                "index": 2,
                "frame": {"x": 10, "y": 20, "width": 100, "height": 24},
                "value": "private query",
                "attributeNames": ["AXRole", "AXValue"],
                "children": [{"role": "AXStaticText"}],
            }
        )

        self.assertEqual(
            public,
            {
                "role": "AXTextField",
                "description": "搜索",
                "focused": True,
                "index": 2,
                "frame": {"x": 10, "y": 20, "width": 100, "height": 24},
            },
        )

    def test_scalar_input_helpers_retain_validation(self) -> None:
        self.assertEqual(
            _optional_string_from_mapping({"name": "  Ada  "}, "name"),
            "Ada",
        )
        self.assertEqual(_positive_int(None, default=30), 30)
        self.assertEqual(_positive_int(5, default=30), 5)
        for invalid in (True, 0, -1, 1.5, "5"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    ValueError,
                    "limit must be a positive integer",
                ):
                    _positive_int(invalid, default=30)

    def test_timing_attachment_preserves_existing_values(self) -> None:
        observation = ToolObservation.ok(
            command_id="cmd_timing",
            tool="wechat.desktop",
            operation="open_wechat",
            summary="ok",
            timing={"startedAt": "existing", "durationMs": 7},
        )

        result = _with_timing(
            observation,
            started_at="replacement",
            duration_ms=99,
        )

        self.assertEqual(
            result.timing,
            {"startedAt": "existing", "durationMs": 7},
        )


if __name__ == "__main__":
    unittest.main()
