from __future__ import annotations

from datetime import datetime
import unittest

from app_control_protocol import ToolObservation

from wechat_desktop_tool import WeChatDesktopConfig
from wechat_desktop_tool._query_mapping import (
    _action_ref_from_node,
    _navigation_from_query_nodes,
    _node_frame_within_query_window,
    _node_from_collection_element,
    _query_matches_target_app_window,
    _query_nodes,
    _query_payload,
    _query_truncated,
)


def _query_observation(
    *,
    nodes: list[dict[str, object]] | None = None,
    truncated: bool = False,
) -> ToolObservation:
    return ToolObservation.ok(
        command_id="cmd_query",
        tool="macos.computer_use",
        operation="accessibility_query",
        summary="query ok",
        observation={
            "accessibilityQuery": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "snapshotId": "frontmost:WeChat:微信 (聊天)",
                "app": {
                    "name": "WeChat",
                    "bundleId": "com.tencent.xinWeChat",
                },
                "window": {
                    "role": "AXWindow",
                    "title": "微信 (聊天)",
                    "frame": {"x": 100, "y": 100, "width": 800, "height": 600},
                },
                "nodes": list(nodes or []),
                "diagnostics": {
                    "returnedNodes": len(nodes or []),
                    "truncated": truncated,
                },
            }
        },
    )


class QueryMappingTests(unittest.TestCase):
    def test_query_envelope_and_nodes_are_normalized_without_aliasing(self) -> None:
        source_node = {
            "axPath": "0/2",
            "role": "AXRadioButton",
            "description": "通讯录",
        }
        observation = _query_observation(nodes=[source_node])

        payload = _query_payload(observation)
        nodes = _query_nodes(observation)

        self.assertEqual(payload["snapshotId"], "frontmost:WeChat:微信 (聊天)")
        self.assertEqual(nodes, [source_node])
        self.assertIsNot(nodes[0], source_node)

    def test_navigation_mapping_preserves_action_ref_contract(self) -> None:
        items = _navigation_from_query_nodes(
            [
                {
                    "axPath": "0/2",
                    "role": "AXRadioButton",
                    "description": "通讯录",
                    "selected": False,
                    "enabled": True,
                    "actions": ["AXPress"],
                    "frame": {"x": 10, "y": 20, "width": 30, "height": 40},
                }
            ],
            snapshot_id="snapshot-1",
        )

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["id"], "nav.contacts")
        self.assertEqual(item["label"], "contacts")
        self.assertEqual(item["selected"], False)
        action_ref = item["actionRef"]
        assert isinstance(action_ref, dict)
        self.assertEqual(action_ref["schema"], "wechat.action_ref.v1")
        self.assertEqual(action_ref["id"], "nav.contacts.press")
        self.assertEqual(action_ref["snapshotId"], "snapshot-1")
        self.assertEqual(action_ref["preconditions"]["roleIn"], ["AXRadioButton"])
        created = datetime.fromisoformat(
            str(action_ref["createdAt"]).replace("Z", "+00:00")
        )
        expires = datetime.fromisoformat(
            str(action_ref["expiresAt"]).replace("Z", "+00:00")
        )
        self.assertEqual((expires - created).total_seconds(), 300)

    def test_action_ref_requires_a_pressable_verified_node(self) -> None:
        self.assertIsNone(
            _action_ref_from_node(
                {"axPath": "0/2", "role": "AXRadioButton", "actions": []}
            )
        )
        self.assertIsNone(
            _action_ref_from_node(
                {"axPath": "0/4", "role": "AXRow", "actions": ["AXPress"]}
            )
        )

    def test_frame_validation_uses_the_current_query_window(self) -> None:
        observation = _query_observation()

        self.assertTrue(
            _node_frame_within_query_window(
                {
                    "frame": {
                        "x": 120,
                        "y": 140,
                        "width": 200,
                        "height": 60,
                    }
                },
                observation,
            )
        )
        self.assertFalse(
            _node_frame_within_query_window(
                {
                    "frame": {
                        "x": 850,
                        "y": 140,
                        "width": 100,
                        "height": 60,
                    }
                },
                observation,
            )
        )

    def test_target_window_identity_requires_matching_bundle_and_window(self) -> None:
        observation = _query_observation()

        self.assertTrue(
            _query_matches_target_app_window(observation, WeChatDesktopConfig())
        )
        self.assertFalse(
            _query_matches_target_app_window(
                observation,
                WeChatDesktopConfig(bundle_id="com.example.other"),
            )
        )

    def test_collection_element_and_truncation_mapping_are_stable(self) -> None:
        node = _node_from_collection_element(
            {
                "axPath": "0/12/2/0/3",
                "role": "AXRow",
                "label": "Ada",
                "frame": {"x": 10, "y": 20, "width": 200, "height": 50},
                "actions": ["AXPress"],
                "enabled": True,
            }
        )

        self.assertEqual(
            node,
            {
                "axPath": "0/12/2/0/3",
                "role": "AXRow",
                "label": "Ada",
                "frame": {"x": 10.0, "y": 20.0, "width": 200.0, "height": 50.0},
                "actions": ["AXPress"],
                "enabled": True,
            },
        )
        self.assertTrue(_query_truncated(_query_observation(truncated=True)))
        self.assertFalse(_query_truncated(_query_observation(truncated=False)))


if __name__ == "__main__":
    unittest.main()
