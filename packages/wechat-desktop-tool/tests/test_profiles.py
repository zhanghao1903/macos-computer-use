from __future__ import annotations

from collections.abc import Mapping
from importlib import resources
from pathlib import Path
import tempfile
from typing import Any
import unittest

from computer_use_macos.accessibility_limits import MAX_ACCESSIBILITY_QUERY_DEPTH
from computer_use_macos.client import _normalize_accessibility_query_request
from wechat_desktop_tool.profiles import (
    DEFAULT_WECHAT_SELECTOR_PROFILE_ID,
    DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE,
    build_packaged_collection_extractor,
    build_packaged_selector_resolver,
    load_control_map,
    load_packaged_control_map,
    load_packaged_selector_profile,
    load_selector_profile,
)


class WeChatSelectorProfileTests(unittest.TestCase):
    def test_packaged_selector_profile_loads_and_validates(self) -> None:
        profile = load_packaged_selector_profile()

        self.assertEqual(profile.profile_id, DEFAULT_WECHAT_SELECTOR_PROFILE_ID)
        self.assertEqual(profile.schema_version, "app-control.selector-profile.v1")
        self.assertIn("navigation.contacts", profile.selectors)
        self.assertIn("regions.mainContent", profile.selectors)
        self.assertIn("contacts", profile.collections)
        self.assertIn("conversations", profile.collections)
        self.assertIn("visibleMessages", profile.collections)
        self.assertEqual(
            profile.selectors["navigation.contacts"]
            .steps[0]
            .match.attributes["AXDescription"]
            .alias_ref,
            "navigation.contacts",
        )

    def test_packaged_selector_profile_keeps_wechat_semantics_owned_here(self) -> None:
        profile = load_packaged_selector_profile()

        self.assertEqual(profile.app.app_id, "wechat")
        self.assertIn("com.tencent.xinWeChat", profile.app.bundle_ids)
        self.assertIn("通讯录", profile.locale_aliases["navigation.contacts"])
        self.assertEqual(
            profile.collections["contacts"].fields["displayName"].attribute,
            "AXValue",
        )
        self.assertEqual(
            profile.collections["contacts"].fields["element"].attribute,
            "elementRef",
        )
        self.assertEqual(
            profile.collections["conversations"].fields["element"].attribute,
            "elementRef",
        )

    def test_packaged_control_map_loads_known_wechat_paths(self) -> None:
        control_map = load_packaged_control_map()

        self.assertEqual(control_map.schema_version, "wechat.control-map.v1")
        self.assertEqual(control_map.map_id, "wechat.macos.default")
        self.assertEqual(control_map.navigation["contacts"].ax_paths, ("0/2",))
        self.assertEqual(
            control_map.navigation["contacts"].screen_coordinates,
            (),
        )
        self.assertEqual(
            control_map.collections["contacts"].root_ax_paths[0],
            "0/12/2/0",
        )
        self.assertEqual(control_map.collections["contacts"].roles, ("AXStaticText",))
        self.assertEqual(
            control_map.collections["contacts"].attributes,
            ("AXRole", "AXValue", "AXPosition", "AXSize", "AXFrame"),
        )
        self.assertFalse(control_map.collections["contacts"].actions)
        self.assertTrue(control_map.collections["contacts"].prefer_visible_rows)
        contacts_resolver = control_map.collections["contacts"].root_resolvers[
            "0/12/2/0"
        ]
        self.assertEqual(contacts_resolver.strategy, "attributePath")
        self.assertEqual(
            [
                (step.attribute, step.index, step.path_index)
                for step in contacts_resolver.steps
            ],
            [
                ("AXChildren", 12, None),
                ("AXChildren", 2, None),
                ("AXContents", 0, 0),
            ],
        )
        self.assertEqual(
            control_map.collections["conversations"].root_ax_paths,
            ("0/12/1/0", "0/11/1/0"),
        )
        self.assertEqual(
            control_map.collections["visibleMessages"].root_ax_paths,
            ("0/12/4/0/0", "0/11/4/0/0"),
        )

    def test_packaged_selector_resolver_uses_default_profile(self) -> None:
        def query_runner(
            *,
            root: object,
            query: object,
            include_raw: bool = False,
        ) -> dict[str, object]:
            del root, query, include_raw
            return {
                "snapshotId": "frontmost:WeChat:微信 (聊天)",
                "nodes": [
                    {
                        "axPath": "0/2",
                        "role": "AXRadioButton",
                        "description": "通讯录",
                        "value": 0,
                        "actions": ["AXPress"],
                    }
                ],
                "diagnostics": {"truncated": False},
            }

        resolver = build_packaged_selector_resolver(query_runner)
        result = resolver.resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.profile_id, DEFAULT_WECHAT_SELECTOR_PROFILE_ID)
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(
            result.elements[0].evidence.matched_attributes["AXValue"],
            0,
        )

    def test_packaged_collection_extractor_uses_default_profile(self) -> None:
        def query_runner(
            *,
            root: object,
            query: object,
            include_raw: bool = False,
        ) -> dict[str, object]:
            del root, query, include_raw
            return {
                "snapshotId": "frontmost:WeChat:微信 (聊天)",
                "nodes": [
                    {
                        "axPath": "0/11",
                        "role": "AXSplitGroup",
                        "description": "main-content",
                    }
                ],
                "diagnostics": {"truncated": False},
            }

        resolver = build_packaged_selector_resolver(query_runner)
        extractor = build_packaged_collection_extractor(resolver)

        self.assertIs(extractor.resolver, resolver)

    def test_packaged_collection_batch_depths_pass_real_normalizer(self) -> None:
        fixtures = {
            "contacts": ("displayName", "Ada", 8, 3),
            "conversations": ("rawLabel", "Ada,hello,09:00", 6, 3),
            "visibleMessages": ("text", "hello", 6, 3),
        }
        for collection_id, fixture in fixtures.items():
            with self.subTest(collection=collection_id):
                field_name, field_value, item_depth, field_depth = fixture
                normalized_requests: list[dict[str, Any]] = []
                item_paths = ["0/items/0", "0/items/1"]

                def query_runner(
                    *,
                    root: Mapping[str, Any],
                    query: Mapping[str, Any],
                    include_raw: bool = False,
                ) -> dict[str, object]:
                    normalized = _normalize_accessibility_query_request(
                        target_app="WeChat",
                        bundle_id="com.tencent.xinWeChat",
                        root=root,
                        query=query,
                        include_raw=include_raw,
                    )
                    normalized_requests.append(normalized)
                    return {
                        "available": True,
                        "snapshotId": "frontmost:WeChat:Main",
                        "nodes": [
                            {
                                "axPath": f"{path}/0",
                                "role": "AXStaticText",
                                "value": field_value,
                            }
                            for path in item_paths
                        ],
                        "diagnostics": {"truncated": False},
                    }

                resolver = build_packaged_selector_resolver(query_runner)
                extractor = build_packaged_collection_extractor(resolver)
                collection = resolver.profile.collections[collection_id]
                self.assertEqual(
                    collection.item_selector.steps[0].max_depth,
                    item_depth,
                )
                field_selector = collection.fields[field_name].selector
                self.assertIsNotNone(field_selector)
                assert field_selector is not None
                self.assertEqual(field_selector.steps[0].max_depth, field_depth)
                item_nodes = [
                    {"axPath": path, "role": "AXRow"}
                    for path in item_paths
                ]

                cache, diagnostics = extractor._batch_extract_fields(
                    collection,
                    "0/items",
                    item_nodes,
                    debug=False,
                )

                self.assertEqual(diagnostics.query_count, 1)
                self.assertLess(diagnostics.query_count, len(item_nodes))
                self.assertEqual(len(normalized_requests), 1)
                query_payload = normalized_requests[0]["query"]
                self.assertIsInstance(query_payload, Mapping)
                self.assertLessEqual(
                    query_payload["maxDepth"],
                    MAX_ACCESSIBILITY_QUERY_DEPTH,
                )
                self.assertEqual(
                    query_payload["maxDepth"],
                    MAX_ACCESSIBILITY_QUERY_DEPTH,
                )
                self.assertEqual(
                    [cache[(path, field_name)].value for path in item_paths],
                    [field_value, field_value],
                )

    def test_selector_profile_override_loads_from_path(self) -> None:
        packaged_text = (
            resources.files("wechat_desktop_tool")
            .joinpath(DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE)
            .read_text(encoding="utf-8")
        )
        override_text = packaged_text.replace(
            'profile_id = "wechat.macos"',
            'profile_id = "wechat.override"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "wechat-override.toml"
            profile_path.write_text(override_text, encoding="utf-8")

            profile = load_selector_profile(profile_path)

        self.assertEqual(profile.profile_id, "wechat.override")
        self.assertIn("navigation.contacts", profile.selectors)

    def test_control_map_override_loads_from_selector_profile_path(self) -> None:
        packaged_text = (
            resources.files("wechat_desktop_tool")
            .joinpath(DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE)
            .read_text(encoding="utf-8")
        )
        override_text = packaged_text.replace(
            'root_ax_paths = ["0/12/2/0", "0/11/2/0"]',
            'root_ax_paths = ["0/99/2/0"]',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "wechat-override.toml"
            profile_path.write_text(override_text, encoding="utf-8")

            control_map = load_control_map(profile_path)

        self.assertEqual(
            control_map.collections["contacts"].root_ax_paths,
            ("0/99/2/0",),
        )

    def test_invalid_selector_profile_override_falls_back_to_packaged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "wechat-invalid.toml"
            profile_path.write_text("schema_version = [", encoding="utf-8")

            profile = load_selector_profile(profile_path)

        self.assertEqual(profile.profile_id, DEFAULT_WECHAT_SELECTOR_PROFILE_ID)


if __name__ == "__main__":
    unittest.main()
