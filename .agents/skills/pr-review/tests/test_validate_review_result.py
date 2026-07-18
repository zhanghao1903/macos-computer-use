from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RESULT_PATH = SKILL_DIR / "examples" / "example-pr-review-result.json"
PREVIOUS_PATH = SKILL_DIR / "examples" / "example-pr-review-previous-result.json"
SCHEMA_PATH = SKILL_DIR / "schemas" / "pr-review-result.schema.json"
VALIDATOR_PATH = SKILL_DIR / "scripts" / "validate_review_result.py"

SPEC = importlib.util.spec_from_file_location("pr_review_validator", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load review-result validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidateReviewResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.base = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def error_codes(self, data: dict[str, object]) -> set[str]:
        errors = VALIDATOR._schema_errors(data, self.schema)
        if not errors:
            finding_map, blockers = VALIDATOR._validate_common(data, errors)
            VALIDATOR._validate_v11(
                data,
                RESULT_PATH,
                self.schema,
                errors,
                finding_map,
                blockers,
            )
        return {error[0] for error in errors}

    def test_examples_validate(self) -> None:
        self.assertEqual([], VALIDATOR.validate_result(PREVIOUS_PATH))
        self.assertEqual([], VALIDATOR.validate_result(RESULT_PATH))

    def test_rejects_approval_with_open_blocker(self) -> None:
        data = copy.deepcopy(self.base)
        data["decision"].update(status="APPROVE", mergeable=True)
        data["review_context"]["approval_renewal"]["result"] = "GRANTED"
        self.assertTrue(
            {"BLOCKER_DECISION_MISMATCH", "INVALID_APPROVAL"}
            <= self.error_codes(data)
        )

    def test_rejects_unclassified_delta(self) -> None:
        data = copy.deepcopy(self.base)
        delta = data["review_context"]["delta_review"]
        delta["changed_files"].append("src/payments/unclassified.ts")
        delta["unclassified_changes"].append("src/payments/unclassified.ts")
        self.assertIn("RENEWAL_GATE_MISMATCH", self.error_codes(data))

    def test_rejects_previous_result_hash_mismatch(self) -> None:
        data = copy.deepcopy(self.base)
        previous = data["review_context"]["previous_review"]
        previous["result_sha256"] = "0" * 64
        self.assertIn("PREVIOUS_RESULT_HASH_MISMATCH", self.error_codes(data))

    def test_rejects_v11_without_review_context(self) -> None:
        data = copy.deepcopy(self.base)
        del data["review_context"]
        self.assertIn("SCHEMA", self.error_codes(data))

    def test_rejects_duplicate_json_key(self) -> None:
        with self.assertRaises(VALIDATOR.DuplicateKeyError):
            VALIDATOR._reject_duplicate_keys([("key", 1), ("key", 2)])

    def test_rejects_unverified_material_assumption_on_approval(self) -> None:
        data = copy.deepcopy(self.base)
        data["findings"][0]["status"] = "resolved"
        data["decision"].update(
            status="APPROVE",
            mergeable=True,
            blocking_finding_ids=[],
        )
        data["required_actions"][0]["status"] = "completed"
        data["review_context"]["forward_risk_review"][0]["result"] = "PASS"
        data["review_context"]["approval_renewal"]["result"] = "GRANTED"
        data["validation"]["overall_status"] = "PASSED"
        data["validation"]["reviewer_runs"][1].update(status="PASS", exit_code=0)
        data["assumptions"][0].update(
            status="UNVERIFIED",
            method=None,
            evidence=None,
        )
        self.assertIn(
            "MATERIAL_ASSUMPTION_UNRESOLVED",
            self.error_codes(data),
        )

    def test_rejects_invalid_new_finding_origin(self) -> None:
        data = copy.deepcopy(self.base)
        data["findings"][0]["origin"] = "BASE_DIFF"
        self.assertIn("INVALID_NEW_FINDING_ORIGIN", self.error_codes(data))

    def test_requires_old_decision_invalidation(self) -> None:
        data = copy.deepcopy(self.base)
        renewal = data["review_context"]["approval_renewal"]
        renewal["old_decision_invalidated"] = False
        self.assertIn("OLD_DECISION_NOT_INVALIDATED", self.error_codes(data))


if __name__ == "__main__":
    unittest.main()
