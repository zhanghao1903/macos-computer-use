from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import importlib.util
from io import StringIO
from pathlib import Path
import subprocess
import sys
from typing import Any
import unittest


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RecordedRun:
    command: list[str]
    cwd: Path
    env: dict[str, str]


class DevCheckScriptTests(unittest.TestCase):
    def test_list_outputs_named_checks(self) -> None:
        module = _load_dev_check_module()

        stdout = StringIO()
        with redirect_stdout(stdout):
            result = module.main(["--list"])

        self.assertEqual(result, 0)
        self.assertIn("root-tests", stdout.getvalue())
        self.assertIn("release-proof-preflight", stdout.getvalue())
        self.assertIn("wheel-preflight", stdout.getvalue())

    def test_select_checks_can_skip_preflight(self) -> None:
        module = _load_dev_check_module()

        checks = module._select_checks(
            None,
            skip_preflight=True,
            include_optional=True,
        )

        self.assertNotIn("release-preflight", [check.name for check in checks])
        self.assertNotIn("release-proof-preflight", [check.name for check in checks])
        self.assertNotIn("wheel-preflight", [check.name for check in checks])
        self.assertIn("root-tests", [check.name for check in checks])

    def test_default_checks_exclude_external_proof_preflight(self) -> None:
        module = _load_dev_check_module()

        checks = module._select_checks(None, skip_preflight=False)

        self.assertIn("release-preflight", [check.name for check in checks])
        self.assertNotIn("release-proof-preflight", [check.name for check in checks])
        self.assertNotIn("wheel-preflight", [check.name for check in checks])

    def test_can_select_external_proof_preflight(self) -> None:
        module = _load_dev_check_module()

        checks = module._select_checks(
            ["release-proof-preflight"],
            skip_preflight=False,
        )

        self.assertEqual([check.name for check in checks], ["release-proof-preflight"])
        command = checks[0].command()
        self.assertIn("--require-external", command)
        self.assertIn("release-proof/helper-doctor.json", command)
        self.assertIn("release-proof/wechat-selector-engine-smoke.json", command)
        self.assertIn("release-proof/release-proof.json", command)

    def test_can_select_wheel_preflight(self) -> None:
        module = _load_dev_check_module()

        checks = module._select_checks(["wheel-preflight"], skip_preflight=False)

        self.assertEqual([check.name for check in checks], ["wheel-preflight"])
        self.assertEqual(checks[0].command()[-1], "scripts/wheel_check.py")

    def test_run_checks_sets_pythonpath_and_reports_failure(self) -> None:
        module = _load_dev_check_module()
        root = ROOT
        runs: list[RecordedRun] = []

        def fake_runner(
            command: list[str],
            *,
            cwd: Path,
            env: dict[str, str],
            check: bool,
        ) -> subprocess.CompletedProcess[object]:
            del check
            runs.append(RecordedRun(command=command, cwd=cwd, env=env))
            return subprocess.CompletedProcess(command, 1 if len(runs) == 2 else 0)

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = module.run_checks(
                root,
                module.CHECKS[:2],
                runner=fake_runner,
            )

        self.assertEqual(result, 1)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].cwd, root)
        self.assertIn(
            str(root / "packages" / "app-control-protocol" / "src"),
            runs[0].env["PYTHONPATH"],
        )
        self.assertEqual(runs[1].command[:3], [runs[1].command[0], "-m", "unittest"])

    def test_fail_fast_stops_after_first_failure(self) -> None:
        module = _load_dev_check_module()
        calls = 0

        def fake_runner(
            command: list[str],
            *,
            cwd: Path,
            env: dict[str, str],
            check: bool,
        ) -> subprocess.CompletedProcess[object]:
            nonlocal calls
            del cwd, env, check
            calls += 1
            return subprocess.CompletedProcess(command, 1)

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = module.run_checks(
                ROOT,
                module.CHECKS[:3],
                fail_fast=True,
                runner=fake_runner,
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls, 1)


def _load_dev_check_module() -> Any:
    path = ROOT / "scripts" / "dev_check.py"
    spec = importlib.util.spec_from_file_location("dev_check", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
