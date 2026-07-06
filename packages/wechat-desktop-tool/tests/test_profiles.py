from __future__ import annotations

import unittest

from wechat_desktop_tool.profiles import (
    DEFAULT_WECHAT_SELECTOR_PROFILE_ID,
    build_packaged_selector_resolver,
    load_packaged_selector_profile,
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


if __name__ == "__main__":
    unittest.main()
