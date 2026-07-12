from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
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

        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["steps"][0]["max_depth"] = 9  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "max_depth must be between 0 and 8",
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

    def test_cursor_pagination_is_rejected_for_internal_mvp(self) -> None:
        profile = _valid_profile()
        profile["collections"]["contacts"]["pagination"] = {  # type: ignore[index]
            "mode": "cursor",
            "default_limit": 30,
            "max_limit": 100,
        }

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "cursor is not supported",
        ):
            parse_selector_profile(profile)

    def test_near_relation_requires_positive_max_distance(self) -> None:
        profile = _valid_profile()
        step = profile["selectors"]["navigation"]["contacts"]["steps"][0]  # type: ignore[index]
        step["relation"] = {  # type: ignore[index]
            "anchor_selector_id": "fallback",
            "relation": "near",
        }

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "max_distance is required for near",
        ):
            parse_selector_profile(profile)

        step["relation"]["max_distance"] = 0  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "max_distance must be > 0",
        ):
            parse_selector_profile(profile)

    def test_best_pick_requires_nonzero_confidence_weight(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["confidence"] = {  # type: ignore[index]
            "minimum": 0.5,
            "attribute_weight": 0,
            "action_weight": 0,
            "structure_weight": 0,
            "geometry_weight": 0,
            "cache_weight": 0,
        }

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "non-zero weight",
        ):
            parse_selector_profile(profile)

    def test_non_best_pick_allows_zero_confidence_weight(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["pick"] = "first"  # type: ignore[index]
        selector["confidence"] = {  # type: ignore[index]
            "minimum": 0,
            "attribute_weight": 0,
            "action_weight": 0,
            "structure_weight": 0,
            "geometry_weight": 0,
            "cache_weight": 0,
        }

        parsed = parse_selector_profile(profile)

        self.assertEqual(parsed.selectors["navigation.contacts"].pick, "first")

    def test_frame_constraint_value_is_validated(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["constraints"] = [  # type: ignore[index]
            {
                "kind": "frameWithin",
                "value": {"x": 0, "y": 0, "width": 100},
                "required": True,
            }
        ]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "constraints\\[0\\]\\.value\\.height must be a number",
        ):
            parse_selector_profile(profile)

        selector["constraints"][0]["value"]["height"] = 100  # type: ignore[index]

        parsed = parse_selector_profile(profile)

        self.assertEqual(
            parsed.selectors["navigation.contacts"].constraints[0].kind,
            "frameWithin",
        )

    def test_nearest_to_anchor_pick_requires_final_relation(self) -> None:
        profile = _valid_profile()
        selector = profile["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["pick"] = "nearestToAnchor"  # type: ignore[index]

        with self.assertRaisesRegex(
            SelectorProfileValidationError,
            "nearestToAnchor requires a final-step relation",
        ):
            parse_selector_profile(profile)

        selector["steps"][0]["relation"] = {  # type: ignore[index]
            "anchor_selector_id": "fallback",
            "relation": "rightOf",
        }

        parsed = parse_selector_profile(profile)

        self.assertEqual(
            parsed.selectors["navigation.contacts"].pick,
            "nearestToAnchor",
        )

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

    def test_boolean_profile_fields_must_be_boolean(self) -> None:
        profile = _valid_profile()
        fields = profile["collections"]["contacts"]["fields"]  # type: ignore[index]
        fields["displayName"]["required"] = "true"  # type: ignore[index]

        with self.assertRaisesRegex(
            ValueError,
            "fields.displayName.required must be a boolean",
        ):
            parse_selector_profile(profile)

        profile = _valid_profile()
        diagnostics = profile["collections"]["contacts"]["diagnostics"] = {}  # type: ignore[index]
        diagnostics["include_skipped_count"] = "false"  # type: ignore[index]

        with self.assertRaisesRegex(
            ValueError,
            "diagnostics.include_skipped_count must be a boolean",
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


def _query_payload(
    nodes: list[dict[str, object]],
    *,
    truncated: bool = False,
    truncation_reason: str | None = None,
) -> dict[str, object]:
    return {
        "schema": "macos.accessibility.query.v1",
        "snapshotId": "frontmost:Sample:Main",
        "nodes": nodes,
        "diagnostics": {
            "truncated": truncated,
            "truncationReason": (
                truncation_reason or "limit" if truncated else None
            ),
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
        self.assertNotIn("AXHidden", runner.calls[0]["query"]["attributes"])
        self.assertNotIn("AXEnabled", runner.calls[0]["query"]["attributes"])
        self.assertNotIn("AXSelected", runner.calls[0]["query"]["attributes"])
        self.assertEqual(result.diagnostics.query_count, 1)
        self.assertEqual(runner.calls[0]["root"], {"kind": "focusedWindow"})
        self.assertEqual(runner.calls[0]["query"]["scope"], "descendants")
        self.assertEqual(runner.calls[0]["query"]["limit"], 40)

    def test_resolver_preserves_frontmost_app_root(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["root"] = {"kind": "frontmostApp"}  # type: ignore[index]
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "app/1",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "app/1")
        self.assertEqual(runner.calls[0]["root"], {"kind": "frontmostApp"})

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

    def test_resolver_applies_visible_match_filter(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["steps"][0]["visible"] = True  # type: ignore[index]
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
                            "visible": False,
                            "frame": {
                                "x": 1,
                                "y": 2,
                                "width": 100,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "frame": {
                                "x": 1,
                                "y": 2,
                                "width": 0,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/3",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "frame": {
                                "x": 1,
                                "y": 2,
                                "width": 100,
                                "height": 20,
                            },
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/3")
        self.assertEqual(result.elements[0].evidence.score_breakdown["visible"], 1.0)
        self.assertIn("AXHidden", runner.calls[0]["query"]["attributes"])

    def test_resolver_applies_enabled_match_filter_fail_closed(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["steps"][0]["enabled"] = True  # type: ignore[index]
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
                            "frame": {
                                "x": 1,
                                "y": 2,
                                "width": 100,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "enabled": False,
                            "frame": {
                                "x": 1,
                                "y": 2,
                                "width": 100,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/3",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "raw": {"AXEnabled": True},
                            "frame": {
                                "x": 1,
                                "y": 2,
                                "width": 100,
                                "height": 20,
                            },
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/3")
        self.assertEqual(result.elements[0].evidence.score_breakdown["enabled"], 1.0)
        self.assertIn("AXEnabled", runner.calls[0]["query"]["attributes"])

    def test_resolver_applies_required_frame_constraints(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["constraints"] = [  # type: ignore[index]
            {
                "kind": "frameWithin",
                "value": {"x": 0, "y": 0, "width": 240, "height": 180},
                "required": True,
            },
            {
                "kind": "rightOf",
                "value": {"x": 0, "y": 80, "width": 100, "height": 40},
                "required": True,
            },
            {
                "kind": "below",
                "value": {"x": 130, "y": 0, "width": 80, "height": 70},
                "required": True,
            },
        ]
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
                            "frame": {
                                "x": 260,
                                "y": 90,
                                "width": 40,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "frame": {
                                "x": 130,
                                "y": 90,
                                "width": 80,
                                "height": 30,
                            },
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(
            result.elements[0].evidence.matched_constraints,
            ("frameWithin", "rightOf", "below"),
        )

    def test_resolver_applies_selected_constraint_fail_closed(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["constraints"] = [  # type: ignore[index]
            {
                "kind": "selected",
                "value": False,
                "required": True,
            },
        ]
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
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "raw": {"AXSelected": True},
                        },
                        {
                            "axPath": "0/3",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "AXSelected": False,
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/3")
        self.assertEqual(
            result.elements[0].evidence.matched_constraints,
            ("selected",),
        )
        self.assertIn("AXSelected", runner.calls[0]["query"]["attributes"])

    def test_resolver_applies_structural_role_constraints_precisely(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["constraints"] = [  # type: ignore[index]
            {
                "kind": "hasChildRole",
                "value": "AXRow",
                "required": True,
            },
            {
                "kind": "hasDescendantRole",
                "value": "AXStaticText",
                "required": True,
            },
        ]
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
                            "descendantRoles": ["AXRow", "AXStaticText"],
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "childRoles": ["AXRow"],
                            "descendantRoles": ["AXButton"],
                        },
                        {
                            "axPath": "0/3",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "childRoles": ["AXRow"],
                            "descendantRoles": ["AXStaticText"],
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/3")
        self.assertEqual(
            result.elements[0].evidence.matched_constraints,
            ("hasChildRole", "hasDescendantRole"),
        )
        self.assertTrue(runner.calls[0]["query"]["includeChildRoles"])
        self.assertTrue(runner.calls[0]["query"]["includeDescendantRoles"])

    def test_resolver_uses_confidence_policy_weights(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["confidence"] = {  # type: ignore[index]
            "minimum": 0.9,
            "attribute_weight": 0,
            "action_weight": 0,
            "structure_weight": 1,
            "geometry_weight": 0,
            "cache_weight": 0,
        }
        selector["constraints"] = [  # type: ignore[index]
            {
                "kind": "hasChildRole",
                "value": "AXRow",
                "weight": 1,
                "required": False,
            },
        ]
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
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                            "childRoles": ["AXRow"],
                        },
                    ]
                )
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(result.elements[0].confidence, 1.0)
        self.assertEqual(
            result.elements[0].evidence.matched_constraints,
            ("hasChildRole",),
        )

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

    def test_resolver_filters_candidates_by_relation_anchor(self) -> None:
        raw = _valid_profile()
        raw["selectors"]["anchors"] = {  # type: ignore[index]
            "searchBox": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 20,
                        "time_budget_ms": 500,
                        "role_in": ["AXTextField"],
                        "match": {
                            "attributes": {
                                "AXPlaceholderValue": {"equals": "Search"}
                            }
                        },
                    }
                ],
            }
        }
        raw["selectors"]["buttons"] = {  # type: ignore[index]
            "openResult": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 20,
                        "time_budget_ms": 500,
                        "role_in": ["AXButton"],
                        "relation": {
                            "anchor_selector_id": "anchors.searchBox",
                            "relation": "rightOf",
                            "max_distance": 50,
                        },
                    }
                ],
            }
        }
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/0",
                            "role": "AXTextField",
                            "placeholderValue": "Search",
                            "frame": {
                                "x": 10,
                                "y": 10,
                                "width": 100,
                                "height": 20,
                            },
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/1",
                            "role": "AXButton",
                            "frame": {
                                "x": 0,
                                "y": 10,
                                "width": 8,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXButton",
                            "frame": {
                                "x": 120,
                                "y": 10,
                                "width": 80,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/3",
                            "role": "AXButton",
                            "frame": {
                                "x": 300,
                                "y": 10,
                                "width": 80,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/4",
                            "role": "AXButton",
                            "frame": {
                                "x": 120,
                                "y": 90,
                                "width": 80,
                                "height": 20,
                            },
                        },
                    ]
                ),
            ]
        )

        result = SelectorResolver(profile, runner).resolve("buttons.openResult")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(
            result.elements[0].evidence.matched_constraints,
            ("relation:rightOf",),
        )
        self.assertEqual(result.diagnostics.query_count, 2)
        self.assertEqual(
            runner.calls[0]["query"]["match"]["roleIn"],
            ["AXTextField"],
        )
        self.assertEqual(
            runner.calls[1]["query"]["match"]["roleIn"],
            ["AXButton"],
        )

    def test_resolver_picks_nearest_relation_candidate(self) -> None:
        raw = _valid_profile()
        raw["selectors"]["anchors"] = {  # type: ignore[index]
            "searchBox": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 20,
                        "time_budget_ms": 500,
                        "role_in": ["AXTextField"],
                        "match": {
                            "attributes": {
                                "AXPlaceholderValue": {"equals": "Search"}
                            }
                        },
                    }
                ],
            }
        }
        raw["selectors"]["buttons"] = {  # type: ignore[index]
            "openResult": {
                "root": {"kind": "focusedWindow"},
                "pick": "nearestToAnchor",
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 20,
                        "time_budget_ms": 500,
                        "role_in": ["AXButton"],
                        "relation": {
                            "anchor_selector_id": "anchors.searchBox",
                            "relation": "rightOf",
                            "max_distance": 300,
                        },
                    }
                ],
            }
        }
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/0",
                            "role": "AXTextField",
                            "placeholderValue": "Search",
                            "frame": {
                                "x": 10,
                                "y": 10,
                                "width": 100,
                                "height": 20,
                            },
                        }
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/3",
                            "role": "AXButton",
                            "frame": {
                                "x": 260,
                                "y": 10,
                                "width": 80,
                                "height": 20,
                            },
                        },
                        {
                            "axPath": "0/2",
                            "role": "AXButton",
                            "frame": {
                                "x": 120,
                                "y": 10,
                                "width": 80,
                                "height": 20,
                            },
                        },
                    ]
                ),
            ]
        )

        result = SelectorResolver(profile, runner).resolve("buttons.openResult")

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(result.diagnostics.query_count, 2)

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
        self.assertEqual(refreshed.diagnostics.query_count, 2)
        self.assertEqual(second_runner.calls[0]["root"], {"kind": "axPath", "axPath": "0/1"})

    def test_resolver_cache_revalidates_matcher_and_required_actions(self) -> None:
        invalid_cached_nodes = {
            "changed_matcher": {
                "axPath": "0/1",
                "role": "AXRadioButton",
                "description": "Chats",
                "actions": ["AXPress"],
            },
            "required_action_removed": {
                "axPath": "0/1",
                "role": "AXRadioButton",
                "description": "Contacts",
                "actions": [],
            },
        }
        for case, invalid_cached_node in invalid_cached_nodes.items():
            with self.subTest(case=case):
                profile = parse_selector_profile(_valid_profile())
                resolver = SelectorResolver(
                    profile,
                    FakeQueryRunner(
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
                    ),
                    app_bundle_id="com.example.Sample",
                    window_fingerprint="main",
                )
                self.assertEqual(
                    resolver.resolve("navigation.contacts").status,
                    "resolved",
                )
                refresh_runner = FakeQueryRunner(
                    [
                        _query_payload([invalid_cached_node]),
                        _query_payload(
                            [
                                {
                                    "axPath": "0/2",
                                    "role": "AXRadioButton",
                                    "description": "Contacts",
                                    "actions": ["AXPress"],
                                }
                            ]
                        ),
                    ]
                )
                resolver.query_runner = refresh_runner

                refreshed = resolver.resolve("navigation.contacts")

                self.assertEqual(refreshed.status, "resolved")
                self.assertEqual(refreshed.elements[0].element_ref.ax_path, "0/2")
                self.assertEqual(refreshed.diagnostics.cache_status, "stale")
                self.assertEqual(refreshed.diagnostics.query_count, 2)
                validation_query = refresh_runner.calls[0]["query"]
                self.assertIn("AXDescription", validation_query["attributes"])
                self.assertTrue(validation_query["actions"])

    def test_resolver_cache_revalidates_state_and_frame_constraints(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["steps"][0]["enabled"] = True  # type: ignore[index]
        selector["steps"][0]["visible"] = True  # type: ignore[index]
        selector["cache"]["key_attributes"] = ["AXIdentifier"]  # type: ignore[index]
        selector["constraints"] = [  # type: ignore[index]
            {"kind": "selected", "value": False, "required": True},
            {
                "kind": "frameWithin",
                "value": {"x": 0, "y": 0, "width": 300, "height": 200},
                "required": True,
            },
        ]
        profile = parse_selector_profile(raw)
        valid_node = {
            "axPath": "0/1",
            "role": "AXRadioButton",
            "description": "Contacts",
            "actions": ["AXPress"],
            "enabled": True,
            "hidden": False,
            "selected": False,
            "AXIdentifier": "contacts-navigation",
            "frame": {"x": 10, "y": 10, "width": 100, "height": 20},
        }
        invalid_overrides = {
            "enabled": {"enabled": False},
            "visible": {"hidden": True},
            "selected": {"selected": True},
            "frame": {
                "frame": {"x": 400, "y": 10, "width": 100, "height": 20}
            },
        }
        for case, override in invalid_overrides.items():
            with self.subTest(case=case):
                resolver = SelectorResolver(
                    profile,
                    FakeQueryRunner([_query_payload([valid_node])]),
                    app_bundle_id="com.example.Sample",
                    window_fingerprint="main",
                )
                self.assertEqual(
                    resolver.resolve("navigation.contacts").status,
                    "resolved",
                )
                invalid_node = {**valid_node, **override}
                fresh_node = {**valid_node, "axPath": "0/2"}
                refresh_runner = FakeQueryRunner(
                    [
                        _query_payload([invalid_node]),
                        _query_payload([fresh_node]),
                    ]
                )
                resolver.query_runner = refresh_runner

                refreshed = resolver.resolve("navigation.contacts")

                self.assertEqual(refreshed.status, "resolved")
                self.assertEqual(refreshed.elements[0].element_ref.ax_path, "0/2")
                self.assertEqual(refreshed.diagnostics.cache_status, "stale")
                attributes = refresh_runner.calls[0]["query"]["attributes"]
                self.assertIn("AXEnabled", attributes)
                self.assertIn("AXHidden", attributes)
                self.assertIn("AXSelected", attributes)
                self.assertIn("AXFrame", attributes)
                self.assertIn("AXIdentifier", attributes)

    def test_resolver_cache_revalidates_relation_geometry(self) -> None:
        raw = _valid_profile()
        raw["selectors"]["anchors"] = {  # type: ignore[index]
            "searchBox": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 10,
                        "time_budget_ms": 500,
                        "role_in": ["AXTextField"],
                        "match": {
                            "attributes": {
                                "AXPlaceholderValue": {"equals": "Search"}
                            }
                        },
                    }
                ],
                "cache": {"mode": "disabled"},
            }
        }
        raw["selectors"]["buttons"] = {  # type: ignore[index]
            "openResult": {
                "root": {"kind": "focusedWindow"},
                "steps": [
                    {
                        "scope": "descendants",
                        "max_depth": 2,
                        "limit": 10,
                        "time_budget_ms": 500,
                        "role_in": ["AXButton"],
                        "relation": {
                            "anchor_selector_id": "anchors.searchBox",
                            "relation": "rightOf",
                            "max_distance": 50,
                        },
                    }
                ],
            }
        }
        profile = parse_selector_profile(raw)
        anchor = {
            "axPath": "0/0",
            "role": "AXTextField",
            "placeholderValue": "Search",
            "frame": {"x": 10, "y": 10, "width": 100, "height": 20},
        }
        target = {
            "axPath": "0/1",
            "role": "AXButton",
            "frame": {"x": 120, "y": 10, "width": 40, "height": 20},
        }
        resolver = SelectorResolver(
            profile,
            FakeQueryRunner([_query_payload([anchor]), _query_payload([target])]),
            app_bundle_id="com.example.Sample",
            window_fingerprint="main",
        )
        self.assertEqual(resolver.resolve("buttons.openResult").status, "resolved")
        moved_target = {
            **target,
            "frame": {"x": 0, "y": 10, "width": 8, "height": 20},
        }
        fresh_target = {**target, "axPath": "0/2"}
        refresh_runner = FakeQueryRunner(
            [
                _query_payload([anchor]),
                _query_payload([moved_target]),
                _query_payload([fresh_target]),
            ]
        )
        resolver.query_runner = refresh_runner

        refreshed = resolver.resolve("buttons.openResult")

        self.assertEqual(refreshed.status, "resolved")
        self.assertEqual(refreshed.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(refreshed.diagnostics.cache_status, "stale")
        self.assertEqual(refreshed.diagnostics.query_count, 3)

    def test_resolver_pick_all_bypasses_single_element_cache(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["pick"] = "all"  # type: ignore[index]
        profile = parse_selector_profile(raw)
        nodes = [
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
        first_runner = FakeQueryRunner([_query_payload(nodes)])
        resolver = SelectorResolver(
            profile,
            first_runner,
            app_bundle_id="com.example.Sample",
            window_fingerprint="main",
        )
        cold = resolver.resolve("navigation.contacts")
        second_runner = FakeQueryRunner([_query_payload(nodes)])
        resolver.query_runner = second_runner

        hot = resolver.resolve("navigation.contacts")

        cold_paths = [item.element_ref.ax_path for item in cold.elements]
        hot_paths = [item.element_ref.ax_path for item in hot.elements]
        self.assertEqual(cold.status, "resolved")
        self.assertEqual(hot.status, "resolved")
        self.assertEqual(hot_paths, cold_paths)
        self.assertEqual(hot.diagnostics.cache_status, "miss")
        self.assertEqual(len(second_runner.calls), 1)
        self.assertEqual(second_runner.calls[0]["root"], {"kind": "focusedWindow"})

    def test_resolver_preserves_query_failure_causes_and_empty_success(self) -> None:
        failures = {
            "permission": (
                {
                    "available": False,
                    "failureKind": "missing_accessibility",
                    "message": "permission denied",
                    "retryable": False,
                },
                "missing_accessibility",
                False,
            ),
            "timeout_wrapped": (
                {
                    "accessibilityQuery": {
                        "available": False,
                        "failureKind": "accessibility_query_timeout",
                        "message": "query timed out",
                        "retryable": True,
                    }
                },
                "accessibility_query_timeout",
                True,
            ),
            "transport_observation_wrapped": (
                {
                    "observation": {
                        "accessibilityQuery": {
                            "available": False,
                            "diagnostics": {
                                "failureKind": "helper_transport_failed",
                                "message": "socket unavailable",
                                "retryable": True,
                            },
                        }
                    }
                },
                "helper_transport_failed",
                True,
            ),
        }
        profile = parse_selector_profile(_valid_profile())
        for case, (payload, cause, retryable) in failures.items():
            with self.subTest(case=case):
                result = SelectorResolver(
                    profile,
                    FakeQueryRunner([payload]),
                ).resolve("navigation.contacts")

                self.assertEqual(result.status, "failed")
                self.assertEqual(
                    result.diagnostics.failure_kind,
                    "selector_query_failed",
                )
                self.assertEqual(result.diagnostics.cause_failure_kind, cause)
                self.assertEqual(result.diagnostics.retryable, retryable)

        empty = SelectorResolver(
            profile,
            FakeQueryRunner(
                [
                    {
                        "available": True,
                        "nodes": [],
                        "diagnostics": {"truncated": False},
                    }
                ]
            ),
        ).resolve("navigation.contacts")

        self.assertEqual(empty.status, "not_found")
        self.assertEqual(empty.diagnostics.failure_kind, "selector_not_found")
        self.assertIsNone(empty.diagnostics.cause_failure_kind)

    def test_resolver_stops_when_fallback_query_fails(self) -> None:
        raw = _valid_profile()
        selector = raw["selectors"]["navigation"]["contacts"]  # type: ignore[index]
        selector["fallbacks"] = ["fallback"]  # type: ignore[index]
        profile = parse_selector_profile(raw)
        runner = FakeQueryRunner(
            [
                _query_payload([]),
                {
                    "available": False,
                    "failureKind": "helper_transport_failed",
                    "message": "helper unavailable",
                    "retryable": True,
                },
            ]
        )

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostics.failure_kind, "selector_query_failed")
        self.assertEqual(
            result.diagnostics.cause_failure_kind,
            "helper_transport_failed",
        )
        self.assertEqual(result.diagnostics.query_count, 2)

    def test_resolver_cache_query_failure_stops_and_evicts_entry(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        resolver = SelectorResolver(
            profile,
            FakeQueryRunner(
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
            ),
            app_bundle_id="com.example.Sample",
            window_fingerprint="main",
        )
        self.assertEqual(
            resolver.resolve("navigation.contacts").status,
            "resolved",
        )
        failure_runner = FakeQueryRunner(
            [
                {
                    "available": False,
                    "failureKind": "missing_accessibility",
                    "message": "permission denied",
                    "retryable": False,
                }
            ]
        )
        resolver.query_runner = failure_runner

        failed = resolver.resolve("navigation.contacts")

        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.diagnostics.failure_kind, "selector_query_failed")
        self.assertEqual(
            failed.diagnostics.cause_failure_kind,
            "missing_accessibility",
        )
        self.assertEqual(failed.diagnostics.cache_status, "stale")
        self.assertEqual(len(failure_runner.calls), 1)
        fresh_runner = FakeQueryRunner(
            [
                _query_payload(
                    [
                        {
                            "axPath": "0/2",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                )
            ]
        )
        resolver.query_runner = fresh_runner

        recovered = resolver.resolve("navigation.contacts")

        self.assertEqual(recovered.status, "resolved")
        self.assertEqual(recovered.elements[0].element_ref.ax_path, "0/2")
        self.assertEqual(fresh_runner.calls[0]["root"], {"kind": "focusedWindow"})

    def test_resolver_refreshes_expired_cache_without_validating_old_path(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        current_time = [datetime(2026, 7, 7, 0, 0, tzinfo=UTC)]
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
                            "axPath": "0/4",
                            "role": "AXRadioButton",
                            "description": "Contacts",
                            "actions": ["AXPress"],
                        }
                    ]
                ),
            ]
        )
        resolver = SelectorResolver(
            profile,
            runner,
            app_bundle_id="com.example.Sample",
            window_fingerprint="main",
            now=lambda: current_time[0],
        )
        first = resolver.resolve("navigation.contacts")
        self.assertEqual(first.status, "resolved")

        current_time[0] = current_time[0] + timedelta(seconds=61)
        runner.calls.clear()
        refreshed = resolver.resolve("navigation.contacts")

        self.assertEqual(refreshed.status, "resolved")
        self.assertEqual(refreshed.elements[0].element_ref.ax_path, "0/4")
        self.assertEqual(refreshed.diagnostics.cache_status, "stale")
        self.assertEqual(refreshed.diagnostics.query_count, 1)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0]["root"], {"kind": "focusedWindow"})

    def test_resolver_reports_truncation_without_full_window_fallback(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        runner = FakeQueryRunner([_query_payload([], truncated=True)])

        result = SelectorResolver(profile, runner).resolve("navigation.contacts")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostics.failure_kind, "selector_query_truncated")
        self.assertEqual(result.diagnostics.truncated, True)
        self.assertEqual(len(runner.calls), 1)


class CollectionExtractorTests(unittest.TestCase):
    def test_collection_preserves_item_query_failure(self) -> None:
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
                {
                    "available": False,
                    "failureKind": "accessibility_query_timeout",
                    "message": "item query timed out",
                    "retryable": True,
                },
            ]
        )

        result = CollectionExtractor(SelectorResolver(profile, runner)).extract(
            "contacts",
            limit=2,
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostics.failure_kind, "selector_query_failed")
        self.assertEqual(
            result.diagnostics.cause_failure_kind,
            "accessibility_query_timeout",
        )
        self.assertTrue(result.diagnostics.retryable)

    def test_collection_preserves_field_query_failure(self) -> None:
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
                {
                    "available": False,
                    "failureKind": "helper_transport_failed",
                    "message": "helper socket unavailable",
                    "retryable": True,
                },
            ]
        )

        result = CollectionExtractor(SelectorResolver(profile, runner)).extract(
            "contacts",
            limit=1,
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostics.failure_kind, "selector_query_failed")
        self.assertEqual(
            result.diagnostics.cause_failure_kind,
            "helper_transport_failed",
        )
        self.assertTrue(result.diagnostics.retryable)

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
                        },
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
        self.assertFalse(result.diagnostics.truncated)
        self.assertIsNone(result.diagnostics.failure_kind)
        self.assertEqual(result.diagnostics.query_count, 3)
        self.assertLess(result.diagnostics.query_count, 4)
        self.assertEqual(result.diagnostics.node_count, 5)
        self.assertEqual(runner.calls[1]["root"], {"kind": "axPath", "axPath": "0/1"})
        self.assertEqual(
            runner.calls[2]["root"],
            {"kind": "axPath", "axPath": "0/1"},
        )
        self.assertEqual(runner.calls[2]["query"]["limit"], 20)
        self.assertEqual(runner.calls[2]["query"]["maxDepth"], 3)

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

    def test_capped_batch_depth_uses_item_rooted_field_fallback(self) -> None:
        raw = _valid_profile()
        contacts = raw["collections"]["contacts"]  # type: ignore[index]
        item_step = contacts["item"]["steps"][0]  # type: ignore[index]
        item_step["max_depth"] = 8  # type: ignore[index]
        display_name = contacts["fields"]["displayName"]  # type: ignore[index]
        field_step = display_name["selector"]["steps"][0]  # type: ignore[index]
        field_step["max_depth"] = 3  # type: ignore[index]
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
                _query_payload(
                    [
                        {
                            "axPath": "0/11/1/deep/name",
                            "role": "AXStaticText",
                            "value": "Bob",
                        }
                    ]
                ),
            ]
        )

        result = CollectionExtractor(SelectorResolver(profile, runner)).extract(
            "contacts",
            limit=2,
        )

        self.assertEqual(result.status, "resolved")
        self.assertEqual(
            result.items,
            ({"displayName": "Alice"}, {"displayName": "Bob"}),
        )
        self.assertEqual(result.diagnostics.query_count, 4)
        self.assertEqual(runner.calls[2]["root"], {"kind": "axPath", "axPath": "0/1"})
        self.assertEqual(runner.calls[2]["query"]["maxDepth"], 8)
        self.assertEqual(
            runner.calls[3]["root"],
            {"kind": "axPath", "axPath": "0/11/1"},
        )
        self.assertEqual(runner.calls[3]["query"]["maxDepth"], 3)
        self.assertEqual(runner.calls[3]["query"]["limit"], 10)

    def test_collection_diagnostics_policy_can_suppress_safe_counts(self) -> None:
        raw = _valid_profile()
        raw["collections"]["contacts"]["diagnostics"] = {  # type: ignore[index]
            "include_skipped_count": False,
            "include_field_failures": False,
            "include_candidate_counts": False,
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
                        {"axPath": "0/11/0", "role": "AXRow"},
                        {"axPath": "0/11/1", "role": "AXRow"},
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

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.items, ({"displayName": "Bob"},))
        self.assertEqual(result.diagnostics.query_count, 4)
        self.assertEqual(result.diagnostics.node_count, 0)
        self.assertEqual(result.diagnostics.failure_kind, "selector_field_missing")
        self.assertEqual(
            result.diagnostics.message,
            "collection field extraction failed",
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

    def test_descendant_field_can_filter_enabled_nodes(self) -> None:
        raw = _valid_profile()
        display_name = raw["collections"]["contacts"]["fields"]["displayName"]  # type: ignore[index]
        display_name_step = display_name["selector"]["steps"][0]  # type: ignore[index]
        display_name_step["enabled"] = True  # type: ignore[index]
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
                            "value": "Missing enabled evidence",
                        },
                        {
                            "axPath": "0/11/0/1",
                            "role": "AXStaticText",
                            "value": "Ada",
                            "raw": {"AXEnabled": True},
                        },
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.items, ({"displayName": "Ada"},))
        self.assertIn("AXEnabled", runner.calls[2]["query"]["attributes"])

    def test_collection_item_selector_applies_constraints(self) -> None:
        raw = _valid_profile()
        item = raw["collections"]["contacts"]["item"]  # type: ignore[index]
        item["constraints"] = [  # type: ignore[index]
            {
                "kind": "minChildren",
                "value": 1,
                "required": True,
            }
        ]
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
                            "childrenCount": 0,
                        },
                        {
                            "axPath": "0/11/1",
                            "role": "AXRow",
                            "childrenCount": 1,
                        },
                    ]
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/1/0",
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
        self.assertEqual(result.diagnostics.query_count, 3)
        self.assertEqual(
            runner.calls[2]["root"],
            {"kind": "axPath", "axPath": "0/11/1"},
        )
        self.assertTrue(runner.calls[1]["query"]["includeChildrenCount"])

    def test_descendant_field_selector_applies_constraints(self) -> None:
        raw = _valid_profile()
        display_name = raw["collections"]["contacts"]["fields"]["displayName"]  # type: ignore[index]
        display_name["selector"]["constraints"] = [  # type: ignore[index]
            {
                "kind": "selected",
                "value": False,
                "required": True,
            }
        ]
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
                            "value": "Missing selected evidence",
                        },
                        {
                            "axPath": "0/11/0/1",
                            "role": "AXStaticText",
                            "value": "Selected row",
                            "raw": {"AXSelected": True},
                        },
                        {
                            "axPath": "0/11/0/2",
                            "role": "AXStaticText",
                            "value": "Ada",
                            "AXSelected": False,
                        },
                    ]
                ),
            ]
        )
        extractor = CollectionExtractor(SelectorResolver(profile, runner))

        result = extractor.extract("contacts", limit=1)

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.items, ({"displayName": "Ada"},))
        self.assertIn("AXSelected", runner.calls[2]["query"]["attributes"])

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
                    ],
                    truncated=True,
                    truncation_reason="limit",
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
        self.assertFalse(result.diagnostics.truncated)
        self.assertIsNone(result.diagnostics.truncation_reason)
        self.assertIsNone(result.diagnostics.failure_kind)
        self.assertEqual(result.diagnostics.query_count, 3)
        self.assertEqual(runner.calls[1]["query"]["limit"], 2)

    def test_limit_truncation_with_more_than_lookahead_is_complete(self) -> None:
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
                        {"axPath": "0/11/2", "role": "AXRow"},
                    ],
                    truncated=True,
                    truncation_reason="limit",
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0/0",
                            "role": "AXStaticText",
                            "value": "Alice",
                        },
                        {
                            "axPath": "0/11/1/0",
                            "role": "AXStaticText",
                            "value": "Bob",
                        },
                        {
                            "axPath": "0/11/2/0",
                            "role": "AXStaticText",
                            "value": "Carol",
                        },
                    ]
                ),
            ]
        )

        result = CollectionExtractor(SelectorResolver(profile, runner)).extract(
            "contacts",
            limit=1,
        )

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.items, ({"displayName": "Alice"},))
        self.assertTrue(result.pagination.has_more)
        self.assertFalse(result.diagnostics.truncated)
        self.assertIsNone(result.diagnostics.failure_kind)

    def test_time_budget_truncation_remains_partial_or_failed(self) -> None:
        profile = parse_selector_profile(_valid_profile())
        partial_runner = FakeQueryRunner(
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
                    ],
                    truncated=True,
                    truncation_reason="time_budget",
                ),
                _query_payload(
                    [
                        {
                            "axPath": "0/11/0/0",
                            "role": "AXStaticText",
                            "value": "Alice",
                        },
                        {
                            "axPath": "0/11/1/0",
                            "role": "AXStaticText",
                            "value": "Bob",
                        },
                    ]
                ),
            ]
        )

        partial = CollectionExtractor(
            SelectorResolver(profile, partial_runner)
        ).extract("contacts", limit=2)

        self.assertEqual(partial.status, "partial")
        self.assertEqual(len(partial.items), 2)
        self.assertTrue(partial.diagnostics.truncated)
        self.assertEqual(partial.diagnostics.truncation_reason, "time_budget")
        self.assertEqual(
            partial.diagnostics.failure_kind,
            "selector_query_truncated",
        )

        failed_runner = FakeQueryRunner(
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
                    [],
                    truncated=True,
                    truncation_reason="time_budget",
                ),
            ]
        )

        failed = CollectionExtractor(
            SelectorResolver(profile, failed_runner)
        ).extract("contacts", limit=2)

        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.items, ())
        self.assertTrue(failed.diagnostics.truncated)
        self.assertEqual(failed.diagnostics.truncation_reason, "time_budget")
        self.assertEqual(
            failed.diagnostics.failure_kind,
            "selector_query_truncated",
        )

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
        self.assertEqual(result.pagination.returned, len(result.items))
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
