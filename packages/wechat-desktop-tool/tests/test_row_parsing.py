from __future__ import annotations

import unittest

from app_control_protocol import ToolObservation

from wechat_desktop_tool._row_parsing import (
    _chat_title_from_query_nodes,
    _messages_from_query_nodes,
    _next_page_token,
    _parse_row_label,
    _row_items_from_nodes,
    _visible_contact_candidates_from_nodes,
)


def _query_observation(*, truncated: bool) -> ToolObservation:
    return ToolObservation.ok(
        command_id="cmd_query",
        tool="macos.computer_use",
        operation="accessibility_query",
        summary="query ok",
        observation={
            "accessibilityQuery": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "snapshotId": "snapshot-rows",
                "nodes": [],
                "diagnostics": {"returnedNodes": 0, "truncated": truncated},
            }
        },
    )


class RowParsingTests(unittest.TestCase):
    def test_conversation_label_parsing_preserves_preview_and_badges(self) -> None:
        self.assertEqual(
            _parse_row_label("Ada,hello,09:00,置顶,消息免打扰"),
            {
                "displayName": "Ada",
                "preview": "hello",
                "timestamp": "09:00",
                "badges": ["置顶", "消息免打扰"],
            },
        )

    def test_contact_rows_are_synthesized_from_static_text_paths(self) -> None:
        items = _row_items_from_nodes(
            [
                {
                    "axPath": "0/12/2/0/0/0/1",
                    "role": "AXStaticText",
                    "value": "新的朋友",
                    "frame": {"x": 295, "y": 120, "width": 175, "height": 23},
                },
                {
                    "axPath": "0/12/2/0/1/0/1",
                    "role": "AXStaticText",
                    "value": "A",
                    "frame": {"x": 295, "y": 180, "width": 175, "height": 23},
                },
                {
                    "axPath": "0/12/2/0/2/0/1",
                    "role": "AXStaticText",
                    "value": "Ada",
                    "frame": {"x": 295, "y": 240, "width": 175, "height": 23},
                },
            ],
            section="contacts",
            limit=30,
            snapshot_id="snapshot-contacts",
        )

        self.assertEqual([item["displayName"] for item in items], ["Ada"])
        self.assertEqual(items[0]["kind"], "contact")
        self.assertEqual(items[0]["element"]["axPath"], "0/12/2/0/2")

    def test_visible_contact_matching_is_exact_after_normalization(self) -> None:
        rows = [
            {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "description": " Ada  Lovelace ,hello,09:00",
                "actions": ["AXPress"],
            },
            {
                "axPath": "0/12/1/0/1",
                "role": "AXRow",
                "description": "Ada,other,10:00",
                "actions": ["AXPress"],
            },
        ]

        candidates = _visible_contact_candidates_from_nodes(
            rows,
            "ada lovelace",
            snapshot_id="snapshot-chats",
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["displayName"], "Ada  Lovelace")
        self.assertEqual(candidates[0]["actionId"], "visible.contact.0.open")

    def test_message_rows_use_descendant_text_and_respect_limit(self) -> None:
        nodes = [
            {
                "axPath": "0/11/4/0/0/0",
                "role": "AXRow",
                "frame": {"x": 400, "y": 120, "width": 300, "height": 60},
            },
            {
                "axPath": "0/11/4/0/0/0/1",
                "role": "AXStaticText",
                "value": "first",
            },
            {
                "axPath": "0/11/4/0/0/1",
                "role": "AXRow",
                "description": "second",
            },
        ]

        messages = _messages_from_query_nodes(nodes, limit=1)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["text"], "first")
        self.assertEqual(messages[0]["id"], "message.visible.0")

    def test_chat_title_skips_search_labels(self) -> None:
        self.assertEqual(
            _chat_title_from_query_nodes(
                [
                    {"role": "AXStaticText", "value": "搜索"},
                    {"role": "AXStaticText", "value": "文件传输助手"},
                ]
            ),
            "文件传输助手",
        )

    def test_page_token_exists_only_for_truncated_query(self) -> None:
        self.assertEqual(
            _next_page_token("contacts", _query_observation(truncated=True)),
            "contacts:next:snapshot-rows",
        )
        self.assertIsNone(
            _next_page_token("contacts", _query_observation(truncated=False))
        )


if __name__ == "__main__":
    unittest.main()
