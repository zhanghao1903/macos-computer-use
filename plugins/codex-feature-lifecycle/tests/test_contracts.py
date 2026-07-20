from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWCTL_PATH = PLUGIN_ROOT / "scripts" / "workflowctl.py"


def load_workflowctl():
    spec = importlib.util.spec_from_file_location("workflowctl_under_test", WORKFLOWCTL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflowctl = load_workflowctl()

    def load_fixture(self, name: str):
        with (PLUGIN_ROOT / "tests" / "fixtures" / name).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_positive_request_and_results_pass_runtime_validation(self) -> None:
        self.workflowctl.validate_review_request(self.load_fixture("review-request.valid.json"))
        self.workflowctl.validate_review_result(self.load_fixture("review-result.approve.valid.json"))
        self.workflowctl.validate_review_result(self.load_fixture("review-result.changes.valid.json"))

    def test_extra_request_field_is_rejected(self) -> None:
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.validate_review_request(self.load_fixture("review-request.invalid.extra-field.json"))

    def test_approve_with_blocker_is_rejected(self) -> None:
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.validate_review_result(self.load_fixture("review-result.invalid.approve-blocker.json"))

    def test_stale_requires_not_attempted_merge_status(self) -> None:
        result = self.load_fixture("review-result.approve.valid.json")
        result["decision"] = "STALE"
        result["merge"] = {"status": "DEFERRED"}
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.validate_review_result(result)

    def test_non_merge_status_rejects_merge_artifacts(self) -> None:
        result = self.load_fixture("review-result.approve.valid.json")
        result["decision"] = "COMMENT"
        result["merge"] = {
            "status": "NOT_ATTEMPTED",
            "url": "https://github.com/acme/project/pull/7",
        }
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.validate_review_result(result)

    def test_contract_verifier_accepts_expected_positive_and_negative_fixtures(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(PLUGIN_ROOT / "scripts" / "validate_contracts.py"),
                "--schemas",
                str(PLUGIN_ROOT / "schemas"),
                "--fixtures",
                str(PLUGIN_ROOT / "tests" / "fixtures"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failures"], 0)
        self.assertEqual(payload["fixtures"], 6)
        if payload["schemaEngine"] == "jsonschema+runtime":
            for fixture in payload["results"]:
                self.assertEqual(fixture["runtimeValid"], fixture["expectedValid"], fixture)
                self.assertEqual(fixture["schemaValid"], fixture["expectedValid"], fixture)


if __name__ == "__main__":
    unittest.main()
