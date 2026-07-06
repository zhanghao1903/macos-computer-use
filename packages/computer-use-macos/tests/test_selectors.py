from __future__ import annotations

from copy import deepcopy
import unittest

from computer_use_macos.selectors.profile import parse_selector_profile
from computer_use_macos.selectors.validation import SelectorProfileValidationError


def _valid_profile() -> dict[str, object]:
    return {
        "schema_version": "app-control.selector-profile.v1",
        "profile_id": "sample.macos",
        "profile_version": "2026.07",
        "app": {
            "app_id": "sample",
            "bundle_ids": ["com.example.Sample"],
            "app_names": ["Sample"],
            "supported_locales": ["en-US"],
            "window_title_patterns": ["Sample.*"],
        },
        "locale_aliases": {
            "contacts": ["Contacts", "通讯录"],
        },
        "selectors": {
            "navigation": {
                "contacts": {
                    "root": {"kind": "focusedWindow"},
                    "steps": [
                        {
                            "scope": "descendants",
                            "max_depth": 2,
                            "limit": 40,
                            "time_budget_ms": 1500,
                            "role_in": ["AXRadioButton"],
                            "actions_include": ["AXPress"],
                            "match": {
                                "attributes": {
                                    "AXDescription": {"alias_ref": "contacts"}
                                }
                            },
                        }
                    ],
                    "cache": {
                        "mode": "readWrite",
                        "ttl_seconds": 60,
                        "validate_signature": True,
                    },
                }
            },
            "fallback": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "children",
                        "max_depth": 1,
                        "limit": 10,
                        "time_budget_ms": 500,
                    }
                ],
            },
        },
        "collections": {
            "contacts": {
                "root_selector_id": "navigation.contacts",
                "item": {
                    "steps": [
                        {
                            "scope": "children",
                            "max_depth": 1,
                            "limit": 30,
                            "time_budget_ms": 1000,
                            "role_in": ["AXRow"],
                        }
                    ]
                },
                "fields": {
                    "displayName": {
                        "source": "descendant",
                        "selector": {
                            "root": {"kind": "focusedWindow"},
                            "steps": [
                                {
                                    "scope": "descendants",
                                    "max_depth": 2,
                                    "limit": 10,
                                    "time_budget_ms": 500,
                                    "role_in": ["AXStaticText"],
                                }
                            ],
                        },
                        "attribute": "AXValue",
                        "required": True,
                        "transform": "strip",
                    }
                },
            }
        },
        "actions": {
            "openContact": {
                "selector_id": "navigation.contacts",
                "ax_action": "AXPress",
                "risk": "changes_current_chat",
                "preconditions": [
                    {"kind": "appFrontmost", "value": True},
                ],
            }
        },
    }


class SelectorProfileTests(unittest.TestCase):
    def test_valid_minimal_profile_validates(self) -> None:
        profile = parse_selector_profile(_valid_profile())

        self.assertEqual(profile.profile_id, "sample.macos")
        self.assertIn("navigation.contacts", profile.selectors)
        self.assertIn("contacts", profile.collections)
        self.assertIn("openContact", profile.actions)
        self.assertEqual(
            profile.selectors["navigation.contacts"].steps[0]
            .match.attributes["AXDescription"]
            .alias_ref,
            "contacts",
        )

    def test_unknown_schema_version_is_rejected(self) -> None:
        profile = _valid_profile()
        profile["schema_version"] = "app-control.selector-profile.v999"

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "unsupported selector profile schema",
        ):
            parse_selector_profile(profile)

    def test_invalid_selector_reference_is_rejected(self) -> None:
        profile = _valid_profile()
        profile["actions"]["openContact"]["selector_id"] = "missing"  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "references unknown selector",
        ):
            parse_selector_profile(profile)

    def test_fallback_cycles_are_rejected(self) -> None:
        profile = _valid_profile()
        selectors = profile["selectors"]  # type: ignore[assignment]
        selectors["navigation"]["contacts"]["fallbacks"] = ["fallback"]  # type: ignore[index]
        selectors["fallback"]["fallbacks"] = ["navigation.contacts"]  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "fallback cycle",
        ):
            parse_selector_profile(profile)

    def test_invalid_regex_is_rejected(self) -> None:
        profile = _valid_profile()
        profile["app"]["window_title_patterns"] = ["["]  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "valid regex",
        ):
            parse_selector_profile(profile)

    def test_missing_alias_ref_is_rejected(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["steps"][0]["match"]["attributes"]["AXDescription"] = {  # type: ignore[index]
            "alias_ref": "missing"
        }

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "unknown alias",
        ):
            parse_selector_profile(profile)

    def test_unbounded_selector_step_is_rejected(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["steps"][0]["limit"] = 0  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "limit must be > 0",
        ):
            parse_selector_profile(profile)

    def test_unknown_transform_is_rejected(self) -> None:
        profile = _valid_profile()
        fields = profile["collections"]["contacts"]["fields"]  # type: ignore[index]
        fields["displayName"]["transform"] = "eval"  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "not allowlisted",
        ):
            parse_selector_profile(profile)

    def test_cache_requires_signature_validation_when_enabled(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["cache"]["validate_signature"] = False  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "validate_signature must be true",
        ):
            parse_selector_profile(profile)

    def test_risky_action_requires_explicit_known_risk(self) -> None:
        profile = _valid_profile()
        action = profile["actions"]["openContact"]  # type: ignore[index]
        action["risk"] = "clicks_anything"  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "risk is invalid",
        ):
            parse_selector_profile(profile)

    def test_parser_does_not_mutate_input(self) -> None:
        profile = _valid_profile()
        original = deepcopy(profile)

        parse_selector_profile(profile)

        self.assertEqual(profile, original)


if __name__ == "__main__":
    unittest.main()
