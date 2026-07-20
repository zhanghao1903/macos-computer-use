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

    def prepare_review(self, *, base_sha: str = BASE_SHA, head_sha: str = HEAD_SHA, pr_url: str = "https://github.com/acme/project/pull/7"):
        return self.run_ctl(
            "prepare-review",
            "--repo-root",
            str(self.repo),
            "--pr-number",
            "7",
            "--pr-url",
            pr_url,
            "--base-sha",
            base_sha,
            "--head-sha",
            head_sha,
            "--branch",
            "codex/test-feature",
            "--evidence",
            "docs/feature/test/verification.md",
            "--check",
            "unit tests: passed",
        )

    def build_result(self, request, *, decision: str = "APPROVE", merge_status: str = "NOT_AUTHORIZED"):
        return {
            "schemaVersion": 1,
            "messageType": "ReviewResult",
            "workflowId": request["workflowId"],
            "dispatchId": request["dispatchId"],
            "reviewedSnapshot": {
                "repositoryKey": request["repository"]["key"],
                "pullRequestNumber": request["pullRequest"]["number"],
                "baseSha": request["pullRequest"]["baseSha"],
                "headSha": request["pullRequest"]["headSha"],
            },
            "routes": {
                "sourceThreadId": "review-thread",
                "destinationThreadId": "main-thread",
                "hostId": "local",
            },
            "decision": decision,
            "findings": [],
            "verification": ["review completed"],
            "limitations": [],
            "merge": {"status": merge_status},
            "createdAt": "2026-07-18T00:00:00Z",
        }

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

    def test_base_only_change_creates_a_new_dispatch(self) -> None:
        self.init_workflow()
        first = self.prepare_review()["request"]
        second = self.prepare_review(base_sha="4" * 40)["request"]
        self.assertNotEqual(first["dispatchId"], second["dispatchId"])

    def test_tampered_request_is_rejected_against_stored_digest(self) -> None:
        self.init_workflow()
        request = self.prepare_review()["request"]
        request["evidence"].append("untrusted-added-evidence")
        request_path = self.write_json("tampered-request.json", request)
        payload = self.run_ctl(
            "accept-review",
            "--repo-root",
            str(self.repo),
            "--request-file",
            str(request_path),
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "dispatch_mismatch")

    def test_tampered_request_cannot_prepare_result(self) -> None:
        self.init_workflow(merge=False)
        request = self.prepare_review()["request"]
        original_path = self.write_json("original-request.json", request)
        self.run_ctl("mark-dispatched", "--repo-root", str(self.repo), "--dispatch-id", request["dispatchId"])
        self.run_ctl("accept-review", "--repo-root", str(self.repo), "--request-file", str(original_path))
        request["checks"].append("untrusted replacement")
        tampered_path = self.write_json("tampered-result-request.json", request)
        findings_path = self.write_json("tampered-result-findings.json", [])
        verification_path = self.write_json("tampered-result-verification.json", ["review completed"])
        payload = self.run_ctl(
            "prepare-result",
            "--repo-root",
            str(self.repo),
            "--request-file",
            str(tampered_path),
            "--decision",
            "APPROVE",
            "--findings-file",
            str(findings_path),
            "--verification-file",
            str(verification_path),
            "--merge-status",
            "NOT_AUTHORIZED",
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "dispatch_mismatch")

    def test_fast_reviewer_does_not_make_delivery_confirmation_regress_state(self) -> None:
        self.init_workflow()
        request = self.prepare_review()["request"]
        request_path = self.write_json("race-request.json", request)
        accepted = self.run_ctl("accept-review", "--repo-root", str(self.repo), "--request-file", str(request_path))
        self.assertEqual(accepted["status"], "reviewing")
        confirmed = self.run_ctl(
            "mark-dispatched",
            "--repo-root",
            str(self.repo),
            "--dispatch-id",
            request["dispatchId"],
        )
        self.assertEqual(confirmed["status"], "reviewing")

    def test_accept_result_requires_reviewer_prepared_state(self) -> None:
        self.init_workflow(merge=False)
        request = self.prepare_review()["request"]
        result_path = self.write_json("unprepared-result.json", self.build_result(request))
        payload = self.run_ctl(
            "accept-result",
            "--repo-root",
            str(self.repo),
            "--result-file",
            str(result_path),
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "invalid_transition")

    def test_explicit_cancellation_rejects_late_review_and_result(self) -> None:
        self.init_workflow(merge=False)
        request = self.prepare_review()["request"]
        request_path = self.write_json("cancelled-request.json", request)
        self.run_ctl("mark-dispatched", "--repo-root", str(self.repo), "--dispatch-id", request["dispatchId"])
        cancelled = self.run_ctl(
            "cancel-dispatch",
            "--repo-root",
            str(self.repo),
            "--dispatch-id",
            request["dispatchId"],
            "--reason",
            "user cancelled review",
        )
        self.assertEqual(cancelled["status"], "cancelled")
        late_review = self.run_ctl("accept-review", "--repo-root", str(self.repo), "--request-file", str(request_path))
        self.assertFalse(late_review["accepted"])
        self.assertEqual(late_review["status"], "cancelled")

        repeated = self.prepare_review()
        self.assertFalse(repeated["shouldSend"])
        self.assertEqual(repeated["status"], "cancelled")

        result_path = self.write_json("cancelled-result.json", self.build_result(request))
        late_result = self.run_ctl(
            "accept-result",
            "--repo-root",
            str(self.repo),
            "--result-file",
            str(result_path),
            expected=2,
        )
        self.assertEqual(late_result["error"]["code"], "invalid_transition")

    def test_prepare_result_is_idempotent_for_delivery_retry(self) -> None:
        self.init_workflow(merge=False)
        request = self.prepare_review()["request"]
        request_path = self.write_json("idempotent-request.json", request)
        self.run_ctl("mark-dispatched", "--repo-root", str(self.repo), "--dispatch-id", request["dispatchId"])
        self.run_ctl("accept-review", "--repo-root", str(self.repo), "--request-file", str(request_path))
        findings_path = self.write_json("idempotent-findings.json", [])
        verification_path = self.write_json("idempotent-verification.json", ["review completed"])
        command = (
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
            "NOT_AUTHORIZED",
        )
        first = self.run_ctl(*command)
        second = self.run_ctl(*command)
        self.assertEqual(first["result"], second["result"])

    def test_non_github_origin_is_rejected(self) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), "remote", "set-url", "origin", "https://gitlab.com/acme/project.git"],
            check=True,
        )
        payload = self.run_ctl(
            "init",
            "--repo-root",
            str(self.repo),
            "--origin",
            "https://gitlab.com/acme/project.git",
            "--project-id",
            "project-1",
            "--main-thread-id",
            "main-thread",
            "--review-thread-id",
            "review-thread",
            "--merge-policy",
            "review-only",
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "unsupported_repository")

    def test_pull_request_url_must_match_configured_repository(self) -> None:
        self.init_workflow()
        payload = self.run_ctl(
            "prepare-review",
            "--repo-root",
            str(self.repo),
            "--pr-number",
            "7",
            "--pr-url",
            "https://github.com/other/project/pull/7",
            "--base-sha",
            BASE_SHA,
            "--head-sha",
            HEAD_SHA,
            "--branch",
            "codex/test-feature",
            expected=2,
        )
        self.assertEqual(payload["error"]["code"], "repository_mismatch")

    def test_corrupt_dispatch_state_fails_with_safe_error(self) -> None:
        initialized = self.init_workflow()
        self.prepare_review()
        state_path = Path(initialized["statePath"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        next(iter(state["dispatches"].values()))["status"] = "unknown"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        payload = self.run_ctl("validate", "--repo-root", str(self.repo), expected=2)
        self.assertEqual(payload["error"]["code"], "invalid_state")

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
