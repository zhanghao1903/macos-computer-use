from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWCTL_PATH = PLUGIN_ROOT / "scripts" / "workflowctl.py"
VALIDATOR_PATH = PLUGIN_ROOT / "scripts" / "validate_contracts.py"
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"
SCHEMAS = PLUGIN_ROOT / "schemas"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflowctl = load_module("engineering_workflowctl", WORKFLOWCTL_PATH)
        cls.validator = load_module("engineering_contract_validator", VALIDATOR_PATH)

    def test_all_schemas_are_json_objects(self) -> None:
        expected = {value[0] for value in self.validator.CONTRACTS.values()}
        actual = {path.name for path in SCHEMAS.glob("*.schema.json")}
        self.assertEqual(expected, actual)
        for path in SCHEMAS.glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertFalse(schema.get("additionalProperties", True))

    def test_runtime_accepts_positive_and_rejects_negative_fixtures(self) -> None:
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(path=path.name):
                key = self.validator.fixture_contract(path)
                contract_name = self.validator.CONTRACTS[key][1]
                payload = json.loads(path.read_text(encoding="utf-8"))
                if ".invalid." in path.name:
                    with self.assertRaises(self.workflowctl.WorkflowError):
                        self.workflowctl.validate_contract_payload(
                            payload, contract_name
                        )
                else:
                    self.assertIs(
                        self.workflowctl.validate_contract_payload(
                            payload, contract_name
                        ),
                        payload,
                    )

    def test_validator_cli_reports_fixture_parity(self) -> None:
        result = subprocess.run(
            ["python3", str(VALIDATOR_PATH)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["fixtures"], 16)
        self.assertEqual(report["failures"], 0)

    def test_message_retry_reuses_original_timestamp_and_payload(self) -> None:
        payload = json.loads(
            (FIXTURES / "requirements-handoff.valid.json").read_text(encoding="utf-8")
        )
        state = {"dispatches": {}}
        stored, duplicate = self.workflowctl.record_message(state, payload)
        self.assertFalse(duplicate)
        retry = copy.deepcopy(payload)
        retry["createdAt"] = "2026-07-27T12:00:01Z"
        retried, duplicate = self.workflowctl.record_message(state, retry)
        self.assertTrue(duplicate)
        self.assertEqual(retried, stored)
        self.assertEqual(retried["createdAt"], "2026-07-27T12:00:00Z")

        conflicting = copy.deepcopy(retry)
        conflicting["body"]["title"] = "Different authority"
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.record_message(state, conflicting)

    def test_re_review_requires_exact_latest_result(self) -> None:
        previous = "a" * 64
        body: dict[str, object] = {}
        self.workflowctl.bind_previous_result(
            body, None, 1, None, "previousResultMessageId"
        )
        self.assertEqual(body, {})
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.bind_previous_result(
                {}, previous, 1, None, "previousResultMessageId"
            )
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.bind_previous_result(
                {}, None, 2, previous, "previousResultMessageId"
            )
        with self.assertRaises(self.workflowctl.WorkflowError):
            self.workflowctl.bind_previous_result(
                {}, "b" * 64, 2, previous, "previousResultMessageId"
            )
        current: dict[str, object] = {}
        self.workflowctl.bind_previous_result(
            current,
            previous,
            2,
            previous,
            "previousResultMessageId",
        )
        self.assertEqual(current["previousResultMessageId"], previous)


if __name__ == "__main__":
    unittest.main()
