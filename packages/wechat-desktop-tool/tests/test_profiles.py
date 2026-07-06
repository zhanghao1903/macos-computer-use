from __future__ import annotations

import unittest

from wechat_desktop_tool.profiles import (
    DEFAULT_WECHAT_SELECTOR_PROFILE_ID,
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


if __name__ == "__main__":
    unittest.main()
