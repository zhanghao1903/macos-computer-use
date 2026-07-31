from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CLAUDECTL = PLUGIN_ROOT / "scripts" / "claudectl.py"
WORKFLOWCTL = PLUGIN_ROOT / "scripts" / "workflowctl.py"
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"


def digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ClaudeCtlIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.codex_home = self.root / "codex-home"
        self.fake = self.root / "fake_claude.py"
        shutil.copy2(FIXTURES / "fake_claude.py", self.fake)
        self.fake.chmod(0o755)
        self.fake_mode = self.fake.with_suffix(".mode")
        self.fake_log = self.fake.with_suffix(".log")
        subprocess.run(
            ["git", "init", "--bare", str(self.remote)],
            check=True,
            text=True,
            capture_output=True,
        )
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Hybrid Workflow Test")
        self.git("config", "user.email", "hybrid@example.invalid")
        self.git(
            "config",
            f"url.{self.remote.as_uri()}.insteadOf",
            "https://github.com/example/project.git",
        )
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        self.write_repo("README.md", "# Test repository\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "chore: initialize test repository")
        self.git("push", "-u", "origin", "main")
        self.feature_id = "sample-feature-0123456789ab"
        self.tasks = {
            "requirements": "task-requirements",
            "main": "task-main",
        }
        self.sessions: dict[str, str] = {}
        self.workflow_id = ""

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.codex_home)
        environment["ANTHROPIC_API_KEY"] = "must-not-reach-child"
        environment["CLAUDE_CODE_OAUTH_TOKEN"] = "must-not-reach-child"
        return environment

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()

    def write_repo(self, relative: str, content: str) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def payload_file(self, name: str, value: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def workflow(self, name: str, *args: str, expect: int = 0) -> dict:
        result = subprocess.run(
            [
                "python3",
                str(WORKFLOWCTL),
                name,
                "--repo",
                str(self.repo),
                *args,
            ],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )
        self.assertEqual(
            result.returncode,
            expect,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        stream = result.stdout if result.returncode == 0 else result.stderr
        return json.loads(stream)

    def bridge(self, name: str, *args: str, expect: int = 0) -> dict:
        command = ["python3", str(CLAUDECTL), name]
        if name != "probe":
            command.extend(["--repo", str(self.repo)])
        command.extend(args)
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )
        self.assertEqual(
            result.returncode,
            expect,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return json.loads(result.stdout)

    def set_fake_mode(self, mode: str) -> None:
        self.fake_mode.write_text(mode, encoding="utf-8")

    def log_entries(self) -> list[dict]:
        if not self.fake_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.fake_log.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def initialize(self) -> None:
        bridge_begin = self.bridge(
            "begin-init",
            "--claude-command",
            str(self.fake),
            "--frontend-edit-authorized",
            "--frontend-model",
            "frontend-test-model",
            "--review-model",
            "review-test-model",
            "--frontend-max-turns",
            "9",
            "--review-max-turns",
            "7",
            "--frontend-max-budget-usd",
            "1.25",
            "--review-max-budget-usd",
            "0.75",
            "--timeout-seconds",
            "30",
        )
        self.sessions = bridge_begin["sessions"]
        begun = self.workflow(
            "begin-init",
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
        )
        self.workflow_id = begun["workflowId"]
        role_ids = {
            **self.tasks,
            "review": self.sessions["review"],
        }
        for role, role_id in role_ids.items():
            self.workflow(
                "record-init-task",
                "--role",
                role,
                "--created-task-id",
                role_id,
            )
        self.workflow(
            "init",
            "--requirements-task-id",
            self.tasks["requirements"],
            "--main-task-id",
            self.tasks["main"],
            "--review-task-id",
            self.sessions["review"],
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
        )
        self.bridge(
            "init",
            "--workflow-id",
            self.workflow_id,
            "--requirements-task-id",
            self.tasks["requirements"],
            "--main-task-id",
            self.tasks["main"],
        )
        self.bridge("bootstrap", "--role", "frontend")
        self.bridge("bootstrap", "--role", "review")

    def frontend_request(
        self,
        *,
        branch: str = "main",
        start_sha: str | None = None,
        message_seed: str = "frontend-1",
        allowed: list[str] | None = None,
    ) -> dict:
        return {
            "schemaVersion": 1,
            "type": "FrontendWorkRequest",
            "messageId": digest(
                {
                    "workflowId": self.workflow_id,
                    "featureId": self.feature_id,
                    "seed": message_seed,
                }
            ),
            "workflowId": self.workflow_id,
            "repositoryKey": "example/project",
            "featureId": self.feature_id,
            "cycle": 1,
            "branch": branch,
            "startHeadSha": start_sha or self.git("rev-parse", "HEAD"),
            "planCommitSha": "a" * 40,
            "planCompositeSha256": "b" * 64,
            "objective": "Implement the approved frontend slice.",
            "allowedPathPrefixes": allowed or ["frontend"],
            "acceptanceCriteria": ["The frontend slice is implemented."],
            "verificationCommands": ["npm test"],
            "previousResultMessageId": None,
        }

    def review_request(self, kind: str, *, cycle: int = 1) -> dict:
        fixture_name = (
            "technical-plan-review-request.valid.json"
            if kind == "plan-review"
            else "code-review-request.valid.json"
        )
        fixture = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        message_type = (
            "TechnicalPlanReviewRequest"
            if kind == "plan-review"
            else "CodeReviewRequest"
        )
        message = {
            "schemaVersion": 1,
            "type": message_type,
            "workflowId": self.workflow_id,
            "featureId": self.feature_id,
            "repositoryKey": "example/project",
            "routing": {
                "sourceTaskId": self.tasks["main"],
                "destinationTaskId": self.sessions["review"],
            },
            "cycle": cycle,
            "createdAt": "2026-07-31T12:00:00Z",
            "body": copy.deepcopy(fixture["body"]),
        }
        message["messageId"] = digest(
            {
                key: value
                for key, value in message.items()
                if key not in {"messageId", "createdAt"}
            }
        )
        return message

    def test_init_bootstrap_and_role_specific_invocation_are_isolated(self) -> None:
        unauthorized = self.bridge(
            "begin-init",
            "--claude-command",
            str(self.fake),
            expect=2,
        )
        self.assertEqual(
            unauthorized["error"]["kind"], "frontend_edit_not_authorized"
        )
        self.initialize()
        self.assertNotEqual(self.sessions["frontend"], self.sessions["review"])
        status = self.bridge("status")
        self.assertTrue(status["ready"])

        request = self.frontend_request()
        self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(self.payload_file("frontend.json", request)),
        )
        plan = self.review_request("plan-review")
        self.bridge(
            "dispatch",
            "--kind",
            "plan-review",
            "--request-file",
            str(self.payload_file("plan.json", plan)),
        )

        entries = self.log_entries()
        self.assertEqual(len(entries), 4)
        for entry in entries:
            self.assertEqual(entry["credentialEnvironment"], [])
            self.assertNotIn("--dangerously-skip-permissions", entry["argv"])
            self.assertNotIn("bypassPermissions", entry["argv"])
        frontend_bootstrap, review_bootstrap, frontend_work, review_work = entries
        self.assertEqual(
            frontend_bootstrap["argv"][
                frontend_bootstrap["argv"].index("--session-id") + 1
            ],
            self.sessions["frontend"],
        )
        self.assertEqual(
            review_bootstrap["argv"][
                review_bootstrap["argv"].index("--session-id") + 1
            ],
            self.sessions["review"],
        )
        self.assertIn("acceptEdits", frontend_bootstrap["argv"])
        self.assertIn("plan", review_bootstrap["argv"])
        self.assertEqual(
            frontend_work["argv"][frontend_work["argv"].index("--resume") + 1],
            self.sessions["frontend"],
        )
        self.assertEqual(
            review_work["argv"][review_work["argv"].index("--resume") + 1],
            self.sessions["review"],
        )

    def test_unknown_outcome_recovers_same_message_and_is_idempotent(self) -> None:
        self.initialize()
        request = self.frontend_request()
        request_file = self.payload_file("frontend.json", request)
        self.set_fake_mode("malformed")
        failed = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
            expect=2,
        )
        self.assertEqual(failed["error"]["kind"], "claude_invalid_json")
        unresolved = self.bridge("status")["unresolved"]
        self.assertEqual(unresolved[0]["status"], "UNKNOWN")
        self.assertEqual(unresolved[0]["messageId"], request["messageId"])

        self.set_fake_mode("success")
        recovered = self.bridge(
            "recover",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
        )
        self.assertEqual(recovered["messageId"], request["messageId"])
        duplicate = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(self.log_entries()), 4)
        recovery_argv = self.log_entries()[-1]["argv"]
        self.assertEqual(
            recovery_argv[recovery_argv.index("--resume") + 1],
            self.sessions["frontend"],
        )

        conflicting = copy.deepcopy(request)
        conflicting["objective"] = "Different authority under the same message ID."
        conflict = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(self.payload_file("conflict.json", conflicting)),
            expect=2,
        )
        self.assertEqual(conflict["error"]["kind"], "replay_conflict")

    def test_review_routing_and_exact_snapshot_fail_closed(self) -> None:
        self.initialize()
        request = self.review_request("plan-review")
        bad_route = copy.deepcopy(request)
        bad_route["routing"]["destinationTaskId"] = self.sessions["frontend"]
        bad_route["messageId"] = digest(
            {
                key: value
                for key, value in bad_route.items()
                if key not in {"messageId", "createdAt"}
            }
        )
        route_result = self.bridge(
            "dispatch",
            "--kind",
            "plan-review",
            "--request-file",
            str(self.payload_file("bad-route.json", bad_route)),
            expect=2,
        )
        self.assertEqual(route_result["error"]["kind"], "routing_mismatch")

        self.set_fake_mode("wrong-snapshot")
        snapshot_result = self.bridge(
            "dispatch",
            "--kind",
            "plan-review",
            "--request-file",
            str(self.payload_file("wrong-snapshot.json", request)),
            expect=2,
        )
        self.assertEqual(snapshot_result["error"]["kind"], "result_mismatch")
        unresolved = self.bridge("status")["unresolved"]
        self.assertEqual(unresolved[0]["status"], "UNKNOWN")

    def test_deterministic_preflight_failure_is_retryable_and_status_stays_readable(
        self,
    ) -> None:
        self.initialize()
        request = self.frontend_request()
        request_file = self.payload_file("preflight.json", request)
        unavailable = self.root / "fake_claude.unavailable"
        self.fake.rename(unavailable)
        failed = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
            expect=2,
        )
        self.assertEqual(failed["error"]["kind"], "claude_not_found")
        unresolved = self.bridge("status")["unresolved"]
        self.assertEqual(unresolved[0]["status"], "FAILED")
        self.assertEqual(unresolved[0]["messageId"], request["messageId"])

        unavailable.rename(self.fake)
        retried = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
        )
        self.assertEqual(retried["status"], "COMPLETED")

    def test_orphaned_running_requires_explicit_process_stop_confirmation(
        self,
    ) -> None:
        self.initialize()
        request = self.frontend_request()
        request_file = self.payload_file("orphaned.json", request)
        dispatched = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
        )
        state_root = Path(self.bridge("status")["stateRoot"])
        state_path = state_root / "claude-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = state["dispatches"][request["messageId"]]
        entry.update(
            {
                "status": "RUNNING",
                "finishedAt": None,
                "resultPath": None,
                "resultDigest": None,
                "errorKind": None,
            }
        )
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
        )
        Path(dispatched["resultPath"]).unlink()

        refused = self.bridge(
            "mark-orphaned",
            "--message-id",
            request["messageId"],
            expect=2,
        )
        self.assertEqual(
            refused["error"]["kind"], "process_stop_not_confirmed"
        )
        marked = self.bridge(
            "mark-orphaned",
            "--message-id",
            request["messageId"],
            "--confirm-process-stopped",
        )
        self.assertEqual(marked["status"], "UNKNOWN")
        recovered = self.bridge(
            "recover",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
        )
        self.assertEqual(recovered["status"], "COMPLETED")

    def proof_case(self, changed_path: str, *, expect: int) -> dict:
        self.initialize()
        branch = "codex/frontend-proof"
        self.git("checkout", "-b", branch)
        start_sha = self.git("rev-parse", "HEAD")
        self.git("push", "-u", "origin", branch)
        request = self.frontend_request(
            branch=branch,
            start_sha=start_sha,
            message_seed=changed_path,
        )
        request_file = self.payload_file("proof-request.json", request)
        dispatched = self.bridge(
            "dispatch",
            "--kind",
            "frontend",
            "--request-file",
            str(request_file),
        )
        self.write_repo(changed_path, "export const proof = true;\n")
        self.git("add", changed_path)
        self.git("commit", "-m", "feat: add frontend proof change")
        end_sha = self.git("rev-parse", "HEAD")

        state_root = Path(self.bridge("status")["stateRoot"])
        state_path = state_root / "claude-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = state["dispatches"][request["messageId"]]
        result = {
            "schemaVersion": 1,
            "type": "ClaudeFrontendOutput",
            "messageId": request["messageId"],
            "requestDigest": entry["requestDigest"],
            "workflowId": self.workflow_id,
            "repositoryKey": "example/project",
            "featureId": self.feature_id,
            "cycle": 1,
            "sessionId": self.sessions["frontend"],
            "status": "COMPLETED",
            "startHeadSha": start_sha,
            "endHeadSha": end_sha,
            "commitShas": [end_sha],
            "modifiedPaths": [changed_path],
            "verification": [
                {
                    "name": "offline proof",
                    "status": "PASS",
                    "evidence": "Git state is constructed by the integration test.",
                }
            ],
            "summary": "Frontend proof fixture completed.",
            "questions": [],
            "error": None,
        }
        result_path = Path(dispatched["resultPath"])
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        entry["resultDigest"] = digest(result)
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
        )
        result_file = self.payload_file("proof-result.json", result)
        return self.bridge(
            "verify-frontend",
            "--request-file",
            str(request_file),
            "--result-file",
            str(result_file),
            expect=expect,
        )

    def test_frontend_git_proof_accepts_exact_allowed_change(self) -> None:
        verified = self.proof_case("frontend/app.tsx", expect=0)
        self.assertEqual(verified["proof"]["modifiedPaths"], ["frontend/app.tsx"])

    def test_frontend_git_proof_rejects_path_escape(self) -> None:
        rejected = self.proof_case("backend/escape.py", expect=2)
        self.assertEqual(rejected["error"]["kind"], "frontend_path_escape")

    def test_probe_reports_auth_failure_without_exposing_details(self) -> None:
        self.set_fake_mode("auth-fail")
        result = self.bridge(
            "probe",
            "--claude-command",
            str(self.fake),
            expect=2,
        )
        self.assertEqual(result["error"]["kind"], "claude_not_authenticated")
        self.assertNotIn("must-not-reach-child", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
