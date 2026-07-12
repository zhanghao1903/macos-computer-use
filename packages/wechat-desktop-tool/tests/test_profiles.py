from __future__ import annotations

from importlib import resources
from pathlib import Path
import tempfile
import unittest

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
