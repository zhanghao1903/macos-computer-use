from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWCTL = PLUGIN_ROOT / "scripts" / "workflowctl.py"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MERGE_SHA = "3" * 40


class WorkflowCtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "remote", "add", "origin", "https://user:secret@GitHub.com/acme/project.git?token=hidden#fragment"],
            check=True,
        )
        self.codex_home = self.root / "codex-home"
        self.codex_home.mkdir()
        self.env = os.environ.copy()
        self.env["CODEX_HOME"] = str(self.codex_home)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_ctl(self, *args: str, expected: int = 0):
        result = subprocess.run(
            [sys.executable, str(WORKFLOWCTL), *args],
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def init_workflow(self, *, merge: bool = True):
        return self.run_ctl(
            "init",
            "--repo-root",
            str(self.repo),
            "--origin",
            "https://github.com/acme/project.git",
            "--project-id",
            "project-1",
            "--host-id",
            "local",
            "--main-thread-id",
            "main-thread",
            "--review-thread-id",
            "review-thread",
            "--merge-policy",
            "merge-on-approve" if merge else "review-only",
            "--merge-method",
            "squash",
        )

    def prepare_review(self):
        return self.run_ctl(
            "prepare-review",
            "--repo-root",
            str(self.repo),
            "--pr-number",
            "7",
            "--pr-url",
            "https://github.com/acme/project/pull/7",
            "--base-sha",
            BASE_SHA,
            "--head-sha",
            HEAD_SHA,
            "--branch",
            "codex/test-feature",
            "--evidence",
            "docs/feature/test/verification.md",
            "--check",
            "unit tests: passed",
        )

    def write_json(self, name: str, value) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_origin_is_sanitized_and_config_is_private(self) -> None:
        payload = self.init_workflow()
        config = payload["config"]
        self.assertEqual(config["repository"]["origin"], "https://github.com/acme/project")
        self.assertNotIn("secret", json.dumps(config))
        self.assertTrue(config["policy"]["mergeOnApprove"])
        config_path = Path(payload["configPath"])
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(config_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(config_path.parent.stat().st_mode), 0o700)

    def test_repeated_init_reuses_without_creating_new_identity(self) -> None:
        first = self.init_workflow()
        second = self.init_workflow()
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["config"]["workflowId"], second["config"]["workflowId"])

    def test_different_init_requires_explicit_replace(self) -> None:
        self.init_workflow()
        payload = self.run_ctl(
            "init",
            "--repo-root",
            str(self.repo),
            "--origin",
            "https://github.com/acme/project",
            "--project-id",
            "project-1",
            "--main-thread-id",
            "different-main",
            "--review-thread-id",
            "review-thread",
            "--merge-policy",
            "review-only",
            "--merge-method",
            "squash",
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "config_exists")

    def test_dispatch_is_idempotent_and_result_reaches_terminal_state(self) -> None:
        self.init_workflow()
        first = self.prepare_review()
        self.assertTrue(first["shouldSend"])
        request = first["request"]
        dispatch_id = request["dispatchId"]
        request_path = self.write_json("request.json", request)

        self.run_ctl("mark-dispatched", "--repo-root", str(self.repo), "--dispatch-id", dispatch_id)
        accepted = self.run_ctl("accept-review", "--repo-root", str(self.repo), "--request-file", str(request_path))
        self.assertTrue(accepted["accepted"])

        findings_path = self.write_json("findings.json", [])
        verification_path = self.write_json("verification.json", ["exact head: passed", "checks: green"])
        prepared_result = self.run_ctl(
            "prepare-result",
            "--repo-root",
            str(self.repo),
            "--request-file",
            str(request_path),
            "--decision",
            "APPROVE",
            "--findings-file",
            str(findings_path),
            "--verification-file",
            str(verification_path),
            "--merge-status",
            "MERGED",
            "--merge-url",
            "https://github.com/acme/project/pull/7",
            "--merge-sha",
            MERGE_SHA,
        )
        result_path = self.write_json("result.json", prepared_result["result"])
        accepted_result = self.run_ctl(
            "accept-result",
            "--repo-root",
            str(self.repo),
            "--result-file",
            str(result_path),
        )
        self.assertEqual(accepted_result["status"], "merged")

        duplicate = self.prepare_review()
        self.assertFalse(duplicate["shouldSend"])
        self.assertEqual(duplicate["status"], "merged")
        self.assertEqual(duplicate["request"]["createdAt"], request["createdAt"])

    def test_review_only_policy_rejects_merged_result(self) -> None:
        self.init_workflow(merge=False)
        request = self.prepare_review()["request"]
        request_path = self.write_json("request.json", request)
        self.run_ctl("mark-dispatched", "--repo-root", str(self.repo), "--dispatch-id", request["dispatchId"])
        self.run_ctl("accept-review", "--repo-root", str(self.repo), "--request-file", str(request_path))
        findings_path = self.write_json("findings.json", [])
        verification_path = self.write_json("verification.json", ["review completed"])
        payload = self.run_ctl(
            "prepare-result",
            "--repo-root",
            str(self.repo),
            "--request-file",
            str(request_path),
            "--decision",
            "APPROVE",
            "--findings-file",
            str(findings_path),
            "--verification-file",
            str(verification_path),
            "--merge-status",
            "MERGED",
            "--merge-url",
            "https://github.com/acme/project/pull/7",
            "--merge-sha",
            MERGE_SHA,
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "merge_not_authorized")

    def test_delivery_failure_is_retryable(self) -> None:
        self.init_workflow()
        first = self.prepare_review()
        dispatch_id = first["request"]["dispatchId"]
        self.run_ctl(
            "mark-delivery-failed",
            "--repo-root",
            str(self.repo),
            "--dispatch-id",
            dispatch_id,
            "--reason",
            "destination temporarily unavailable",
        )
        retry = self.prepare_review()
        self.assertTrue(retry["shouldSend"])
        self.assertEqual(retry["status"], "prepared")
        self.assertEqual(retry["request"]["dispatchId"], dispatch_id)

    def test_stale_lock_is_recovered(self) -> None:
        initialized = self.init_workflow()
        lock_path = Path(initialized["configPath"]).parent / ".state.lock"
        lock_path.write_text("stale", encoding="utf-8")
        old = time.time() - 60
        os.utime(lock_path, (old, old))
        prepared = self.prepare_review()
        self.assertTrue(prepared["ok"])
        self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
