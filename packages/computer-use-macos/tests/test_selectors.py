from __future__ import annotations

from copy import deepcopy
import unittest

from computer_use_macos.selectors.collections import CollectionExtractor
from computer_use_macos.selectors.profile import parse_selector_profile
from computer_use_macos.selectors.resolver import SelectorResolver
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

    def test_unknown_computed_field_is_rejected(self) -> None:
        profile = _valid_profile()
        fields = profile["collections"]["contacts"]["fields"]  # type: ignore[index]
        fields["unsafe"] = {  # type: ignore[index]
            "source": "computed",
            "attribute": "rawNode",
        }

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "not an allowlisted computed field",
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

    def test_action_is_disabled_by_default(self) -> None:
        profile = parse_selector_profile(_valid_profile())

        self.assertFalse(profile.actions["openContact"].enabled_by_default)

    def test_read_or_focus_action_can_be_enabled_by_default(self) -> None:
        profile = _valid_profile()
        action = profile["actions"]["openContact"]  # type: ignore[index]
        action["risk"] = "changes_focus"  # type: ignore[index]
        action["enabled_by_default"] = True  # type: ignore[index]

        parsed = parse_selector_profile(profile)

        self.assertTrue(parsed.actions["openContact"].enabled_by_default)

    def test_mutating_action_cannot_be_enabled_by_default(self) -> None:
        profile = _valid_profile()
        action = profile["actions"]["openContact"]  # type: ignore[index]
        action["risk"] = "submits_text"  # type: ignore[index]
        action["enabled_by_default"] = True  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "enabled_by_default is only allowed",
        ):
            parse_selector_profile(profile)

    def test_action_enabled_by_default_must_be_boolean(self) -> None:
        profile = _valid_profile()
        action = profile["actions"]["openContact"]  # type: ignore[index]
        action["enabled_by_default"] = "false"  # type: ignore[index]

        with self.assertRaisesRegex(
            ValueError,
            "enabled_by_default must be a boolean",
        ):
            parse_selector_profile(profile)

    def test_parser_does_not_mutate_input(self) -> None:
        profile = _valid_profile()
        original = deepcopy(profile)

        parse_selector_profile(profile)

        self.assertEqual(profile, original)


class FakeQueryRunner:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        root: object,
        query: object,
        include_raw: bool = False,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "root": root,
                "query": query,
                "include_raw": include_raw,
            }
        )
        if not self.payloads:
            return {
                "snapshotId": "snapshot",
                "nodes": [],
                "diagnostics": {"truncated": False, "nodeCount": 0},
            }
        return self.payloads.pop(0)


def _query_payload(nodes: list[dict[str, object]], *, truncated: bool = False) -> dict[str, object]:
    return {
        "schema": "macos.accessibility.query.v1",
        "snapshotId": "frontmost:Sample:Main",
        "nodes": nodes,
        "diagnostics": {
            "truncated": truncated,
            "truncationReason": "limit reached" if truncated else None,
            "nodeCount": len(nodes),
        },
    }


class SelectorResolverTests(unittest.TestCase):
    def test_resolver_returns_matching_element(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "frame": {"x": 1, "y": 2, "width": 100, "height": 20},
                        }
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/1")
        self.assertEqual(result.elements[0].label, "Contacts")
        self.assertIsNotNone(result.elements[0].frame)
        self.assertEqual(result.elements[0].frame.x, 1)
        self.assertIn("AXFrame", runner.calls[0]["query"]["attributes"])
        self.assertEqual(result.diagnostics.query_count, 1)
        self.assertEqual(runner.calls[0]["root"], {"kind": "focusedWindow"})
        self.assertEqual(runner.calls[0]["query"]["scope"], "descendants")
        self.assertEqual(runner.calls[0]["query"]["limit"], 40)

    def test_resolver_redacts_debug_evidence_by_default(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertIsNone(result.elements[0].evidence.debug_attributes)

    def test_resolver_reports_ambiguous_candidates(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(result.diagnostics.failure_kind, "selector_ambiguous")
        self.assertEqual(len(result.elements), 2)

    def test_resolver_chains_steps_under_previous_candidate(self) -> None:
        raw = _valid_profile()
        raw["selectors"]["regions"] = {  # type: ignore[index]
            "contactsTable": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 20,
                        "time_budget_ms": 500,
                        "role_in": ["AXGroup"],
                        "match": {
                            "attributes": {
                                "AXDescription": {"equals": "Main Content"}
                            }
                        },
                    },
                    {
                        "scope": "children",
                        "max_depth": 1,
                        "limit": 10,
                        "time_budget_ms": 500,
                        "role_in": ["AXTable"],
                        "match": {
                            "attributes": {
                                "AXDescription": {"equals": "Contacts Table"}
                            }
                        },
                    },
                ],
            }
        }
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/11",
                            "role": "AXGroup",
                            "description": "Main Content",
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/3",
                            "role": "AXTable",
                            "description": "Contacts Table",
                        }
                    ]
                ),
            ]
        )

        result = SelectorResolver(profile, runner).resolve("regions.contactsTable")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/11/3")
        self.assertEqual(result.diagnostics.query_count, 2)
        self.assertEqual(runner.calls[0]["root"], {"kind": "focusedWindow"})
        self.assertEqual(runner.calls[1]["root"], {"kind": "axPath", "axPath": "0/11"})
        self.assertEqual(runner.calls[1]["query"]["scope"], "children")

    def test_resolver_uses_fallback_selector(self) -> None:
        raw = _valid_profile()
        raw["selectors"]["navigation"]["contacts"]["fallbacks"] = ["fallback"]  # type: ignore[index]
        raw["selectors"]["fallback"]["steps"][0]["role_in"] = ["AXButton"]  # type: ignore[index]
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload([]),
                _query_payload(
                    [
                        {
                            "axPath": "0/9",
                            "role": "AXButton",
                            "title": "Fallback",
                            "actions": [],
                        }
                    ]
                ),
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.selector_id, "fallback")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/9")
        self.assertEqual(len(runner.calls), 2)

    def test_resolver_refreshes_stale_cache(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        first_runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                )
            ]
        )
        resolver = SelectorResolver(
            profile,
            first_runner,
            app_bundle_id="com.example.Sample",
            window_fingerprint="main",
        )
        first = resolver.resolve("navigation.contacts")
        self.assertEqual(first.status, "resolved")

        second_runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/3",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
            ]
        )
        resolver.query_runner = second_runner

        refreshed = resolver.resolve("navigation.contacts")

        self.assertEqual(refreshed.status, "resolved")
        self.assertEqual(refreshed.elements[0].element_ref.ax_path, "0/3")
        self.assertEqual(refreshed.diagnostics.cache_status, "stale")
        self.assertEqual(second_runner.calls[0]["root"], {"kind": "axPath", "axPath": "0/1"})

    def test_resolver_reports_truncation_without_full_window_fallback(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner([_query_payload([], truncated=True)])

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostics.failure_kind, "selector_query_truncated")
        self.assertEqual(result.diagnostics.truncated, True)
        self.assertEqual(len(runner.calls), 1)


class CollectionExtractorTests(unittest.TestCase):
    def test_extracts_semantic_items_from_row_descendants(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload(
                    [
                        {"axPath": "0/11/0", "role": "AXRow"},
                        {"axPath": "0/11/1", "role": "AXRow"},
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0/0",
                            "role": "AXStaticText",
                            "value": " Alice ",
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/1/0",
                            "role": "AXStaticText",
                            "value": "Bob",
                        }
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=2)

        self.assertEqual(result.status, "resolved")
        self.assertEqual(
            result.items,
            ({"displayName": "Alice"}, {"displayName": "Bob"}),
        )
        self.assertEqual(result.pagination.limit, 2)
        self.assertEqual(result.pagination.returned, 2)
        self.assertEqual(result.pagination.has_more, False)
        self.assertEqual(result.diagnostics.query_count, 4)
        self.assertEqual(result.diagnostics.node_count, 5)
        self.assertEqual(runner.calls[1]["root"], {"kind": "axPath", "axPath": "0/1"})
        self.assertEqual(
            runner.calls[2]["root"],
            {"kind": "axPath", "axPath": "0/11/0"},
        )

    def test_missing_required_field_returns_partial_collection(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload(
                    [
                        {"axPath": "0/11/0", "role": "AXRow"},
                        {"axPath": "0/11/1", "role": "AXRow"},
                    ]
                ),
                _query_payload([]),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/1/0",
                            "role": "AXStaticText",
                            "value": "Bob",
                        }
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=2)

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.items, ({"displayName": "Bob"},))
        self.assertEqual(result.pagination.returned, 1)
        self.assertEqual(result.diagnostics.query_count, 4)
        self.assertEqual(result.diagnostics.node_count, 4)
        self.assertEqual(result.diagnostics.failure_kind, "selector_field_missing")
        self.assertEqual(
            result.diagnostics.message,
            "skipped 1 item(s); field failures 1",
        )

    def test_missing_all_required_fields_fails_collection(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload([{"axPath": "0/11/0", "role": "AXRow"}]),
                _query_payload([]),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.items, ())
        self.assertEqual(result.diagnostics.failure_kind, "selector_field_missing")

    def test_descendant_field_can_use_node_summary_without_attribute(self) -> None:
        raw = _valid_profile()
        display_name = raw["collections"]["contacts"]["fields"]["displayName"]  # type: ignore[index]
        del display_name["attribute"]  # type: ignore[index]
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload([{"axPath": "0/11/0", "role": "AXRow"}]),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0/0",
                            "role": "AXStaticText",
                            "value": "Ada",
                        }
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.items, ({"displayName": "Ada"},))

    def test_pagination_uses_limit_plus_one_for_has_more(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload(
                    [
                        {"axPath": "0/11/0", "role": "AXRow"},
                        {"axPath": "0/11/1", "role": "AXRow"},
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0/0",
                            "role": "AXStaticText",
                            "value": "Alice",
                        }
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.items, ({"displayName": "Alice"},))
        self.assertEqual(result.pagination.limit, 1)
        self.assertEqual(result.pagination.has_more, True)
        self.assertEqual(result.diagnostics.query_count, 3)
        self.assertEqual(runner.calls[1]["query"]["limit"], 2)

    def test_collection_skips_invalid_candidates_before_filling_limit(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload(
                    [
                        {"axPath": "0/11/0", "role": "AXRow"},
                        {"axPath": "0/11/1", "role": "AXRow"},
                    ]
                ),
                _query_payload([]),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/1/0",
                            "role": "AXStaticText",
                            "value": "Bob",
                        }
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.items, ({"displayName": "Bob"},))
        self.assertEqual(result.pagination.limit, 1)
        self.assertEqual(result.pagination.returned, 1)
        self.assertEqual(result.pagination.has_more, True)
        self.assertEqual(result.diagnostics.failure_kind, "selector_field_missing")
        self.assertEqual(result.diagnostics.query_count, 4)

    def test_computed_element_ref_returns_normalized_item_element(self) -> None:
        raw = _valid_profile()
        fields = raw["collections"]["contacts"]["fields"]  # type: ignore[index]
        fields["element"] = {  # type: ignore[index]
            "source": "computed",
            "attribute": "elementRef",
            "required": True,
        }
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0",
                            "role": "AXRow",
                            "description": "Ada",
                            "actions": ["AXPress"],
                            "enabled": True,
                            "frame": {
                                "x": 10,
                                "y": 20,
                                "width": 200,
                                "height": 44,
                            },
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0/0",
                            "role": "AXStaticText",
                            "value": "Ada",
                        }
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.items[0]["displayName"], "Ada")
        self.assertEqual(
            result.items[0]["element"],
            {
                "kind": "accessibilityElement",
                "axPath": "0/11/0",
                "role": "AXRow",
                "label": "Ada",
                "frame": {"x": 10.0, "y": 20.0, "width": 200.0, "height": 44.0},
                "actions": ["AXPress"],
                "enabled": True,
            },
        )
        self.assertEqual(runner.calls[1]["query"]["actions"], True)
        self.assertIn("AXFrame", runner.calls[1]["query"]["attributes"])


if __name__ == "__main__":
    unittest.main()
