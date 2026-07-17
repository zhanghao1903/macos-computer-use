from __future__ import annotations

from collections.abc import Mapping
import unittest

from computer_use_macos.selectors.profile import parse_selector_profile
from computer_use_macos.selectors.resolver import SelectorResolver


def _profile():
    return parse_selector_profile(
        {
            "schema_version": "app-control.selector-profile.v1",
            "profile_id": "query-contract.macos",
            "profile_version": "1",
            "app": {
                "app_id": "query-contract",
                "bundle_ids": ["com.example.QueryContract"],
            },
            "locale_aliases": {},
            "selectors": {
                "target": {
                    "root": {"kind": "focusedWindow"},
                    "steps": [
                        {
                            "scope": "children",
                            "max_depth": 1,
                            "limit": 10,
                            "time_budget_ms": 500,
                            "role_in": ["AXRadioButton"],
                            "actions_include": ["AXPress"],
                            "match": {
                                "attributes": {
                                    "AXDescription": {"equals": "Contacts"}
                                }
                            },
                        }
                    ],
                    "cache": {"mode": "readWrite"},
                }
            },
        }
    )


NODE = {
    "axPath": "0/2",
    "role": "AXRadioButton",
    "description": "Contacts",
    "actions": ["AXPress"],
}


class _Runner:
    def __init__(self, *payloads: Mapping[str, object]) -> None:
        self.payloads = list(payloads)
        self.calls = 0

    def __call__(self, **_: object) -> Mapping[str, object]:
        self.calls += 1
        return self.payloads.pop(0)


class SelectorQueryContractTests(unittest.TestCase):
    def test_canonical_and_narrow_legacy_success_shapes_resolve(self) -> None:
        payloads = {
            "canonical": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "status": "ok",
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "generated": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "legacy": {
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "legacy_available": {
                "available": True,
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
        }

        for case, payload in payloads.items():
            with self.subTest(case=case):
                result = SelectorResolver(_profile(), _Runner(payload)).resolve(
                    "target"
                )

                self.assertEqual(result.status, "resolved")
                self.assertEqual(result.elements[0].element_ref.ax_path, "0/2")

    def test_malformed_query_structures_fail_closed(self) -> None:
        invalid_payloads = {
            "wrong_type_available": {
                "available": "false",
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "malformed_node_member": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": [NODE, "malformed"],
                "diagnostics": {"truncated": False},
            },
            "malformed_nodes_shape": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": {"unexpected": "mapping"},
                "diagnostics": {"truncated": False},
            },
            "wrong_type_diagnostics": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": [NODE],
                "diagnostics": [],
            },
            "truncated_integer_zero": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": [NODE],
                "diagnostics": {"truncated": 0},
            },
            "truncated_none": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": [NODE],
                "diagnostics": {"truncated": None},
            },
            "truncated_missing": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "nodes": [NODE],
                "diagnostics": {},
            },
            "wrong_schema": {
                "schema": "macos.accessibility.query.v999",
                "available": True,
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "legacy_status": {
                "available": True,
                "status": "ok",
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "malformed_direct_wrapper": {"accessibilityQuery": []},
            "malformed_observation_wrapper": {
                "observation": {"accessibilityQuery": []},
            },
        }

        for case, payload in invalid_payloads.items():
            with self.subTest(case=case):
                self._assert_invalid(payload)

    def test_contradictory_query_evidence_fails_closed(self) -> None:
        invalid_payloads = {
            "available_true_status_failed": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "status": "failed",
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "wrong_type_failure_kind": {
                "available": True,
                "failureKind": 123,
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "success_with_failure_kind": {
                "schema": "macos.accessibility.query.v1",
                "available": True,
                "failureKind": "accessibility_query_failed",
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "available_false_status_ok": {
                "schema": "macos.accessibility.query.v1",
                "available": False,
                "status": "ok",
                "nodes": [NODE],
                "diagnostics": {"truncated": False},
            },
            "conflicting_failure_aliases": {
                "available": False,
                "failureKind": "missing_accessibility",
                "diagnostics": {
                    "failure_kind": "accessibility_query_timeout",
                },
            },
            "conflicting_retryable": {
                "available": False,
                "failureKind": "accessibility_query_timeout",
                "retryable": True,
                "diagnostics": {"retryable": False},
            },
        }

        for case, payload in invalid_payloads.items():
            with self.subTest(case=case):
                self._assert_invalid(payload)

    def test_invalid_envelope_never_populates_cache(self) -> None:
        invalid = {
            "schema": "macos.accessibility.query.v1",
            "available": True,
            "nodes": [{**NODE, "axPath": "0/unsafe"}],
            "diagnostics": {"truncated": 0},
        }
        valid = {
            "nodes": [{**NODE, "axPath": "0/safe"}],
            "diagnostics": {"truncated": False},
        }
        runner = _Runner(invalid, valid)
        resolver = SelectorResolver(
            _profile(),
            runner,
            app_bundle_id="com.example.QueryContract",
            window_fingerprint="main",
        )

        failed = resolver.resolve("target")
        resolved = resolver.resolve("target")

        self.assertEqual(failed.status, "failed")
        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(resolved.elements[0].element_ref.ax_path, "0/safe")
        self.assertEqual(runner.calls, 2)

    def _assert_invalid(self, payload: Mapping[str, object]) -> None:
        runner = _Runner(payload)
        result = SelectorResolver(_profile(), runner).resolve("target")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostics.failure_kind, "selector_query_failed")
        self.assertEqual(
            result.diagnostics.cause_failure_kind,
            "accessibility_query_failed",
        )
        self.assertEqual(result.elements, ())
        self.assertEqual(runner.calls, 1)


if __name__ == "__main__":
    unittest.main()
