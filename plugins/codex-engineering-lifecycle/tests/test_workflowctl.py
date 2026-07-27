from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWCTL = PLUGIN_ROOT / "scripts" / "workflowctl.py"

SPEC = importlib.util.spec_from_file_location(
    "engineering_lifecycle_workflowctl", WORKFLOWCTL
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load workflowctl")
WORKFLOW_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW_MODULE)


class WorkflowCtlIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.codex_home = self.root / "codex-home"
        subprocess.run(
            ["git", "init", "--bare", str(self.remote)],
            check=True,
            text=True,
            capture_output=True,
        )
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Workflow Test")
        self.git("config", "user.email", "workflow@example.invalid")
        self.git(
            "config",
            f"url.{self.remote.as_uri()}.insteadOf",
            "https://github.com/example/project.git",
        )
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        self.feature_id = "sample-feature-0123456789ab"
        self.feature_branch = "codex/sample-feature"
        self.tasks = {
            "requirements": "task-requirements",
            "main": "task-main",
            "review": "task-review",
        }

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()

    def write(self, relative: str, content: str) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def payload_file(self, name: str, value: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def command(self, name: str, *args: str, expect: int = 0) -> dict:
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.codex_home)
        result = subprocess.run(
            ["python3", str(WORKFLOWCTL), name, "--repo", str(self.repo), *args],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(
            result.returncode,
            expect,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        stream = result.stdout if result.returncode == 0 else result.stderr
        return json.loads(stream)

    def commit_feature_documents(self) -> str:
        self.git("checkout", "-b", self.feature_branch)
        self.write(
            "docs/feature/sample-feature/requirements.md",
            "\n".join(
                [
                    "# Requirements",
                    "",
                    "- Status: Confirmed",
                    f"- FeatureId: {self.feature_id}",
                    f"- Branch: {self.feature_branch}",
                    "- ConfirmedBy: test-user",
                    "- ConfirmedAt: 2026-07-27T12:00:00Z",
                    "",
                    "## Acceptance criteria",
                    "",
                    "- The workflow reaches closure only after release proof.",
                    "",
                ]
            ),
        )
        self.write(
            "docs/feature/sample-feature/design.md",
            "# Design\n\nUse strict state transitions.\n",
        )
        self.write(
            "docs/feature/sample-feature/implementation-plan.md",
            "# Implementation Plan\n\nImplement, test, review, merge, release, close.\n",
        )
        self.git("add", "docs")
        self.git("commit", "-m", "docs: add confirmed feature plan")
        commit = self.git("rev-parse", "HEAD")
        self.git("push", "-u", "origin", self.feature_branch)
        return commit

    def initialize(self) -> dict:
        begun = self.command(
            "begin-init",
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
        )
        self.assertFalse(begun["duplicate"])
        self.assertEqual(begun["missingRoles"], list(self.tasks))
        for role, task_id in self.tasks.items():
            recorded = self.command(
                "record-init-task",
                "--role",
                role,
                "--created-task-id",
                task_id,
            )
            self.assertEqual(recorded["taskId"], task_id)
        return self.finalize_init()

    def finalize_init(self) -> dict:
        return self.command(
            "init",
            "--requirements-task-id",
            self.tasks["requirements"],
            "--main-task-id",
            self.tasks["main"],
            "--review-task-id",
            self.tasks["review"],
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
        )

    def ack_all(self) -> None:
        for role, task_id in self.tasks.items():
            self.command(
                "ack-bootstrap",
                "--task-id",
                task_id,
                "--role",
                role,
            )

    def add_review_report(
        self, branch: str, base_sha: str, relative: str, content: str
    ) -> tuple[str, str]:
        self.git("checkout", "-b", branch, base_sha)
        path = self.write(relative, content)
        self.git("add", relative)
        self.git("commit", "-m", "docs: record independent review")
        commit = self.git("rev-parse", "HEAD")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.git("checkout", self.feature_branch)
        return commit, digest

    def test_init_ledger_and_config_only_recovery(self) -> None:
        unauthorized = self.command(
            "begin-init",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
            expect=2,
        )
        self.assertEqual(unauthorized["error"]["kind"], "goal_not_authorized")
        self.assertFalse(self.codex_home.exists())
        direct = self.command(
            "init",
            "--requirements-task-id",
            self.tasks["requirements"],
            "--main-task-id",
            self.tasks["main"],
            "--review-task-id",
            self.tasks["review"],
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
            expect=2,
        )
        self.assertEqual(direct["error"]["kind"], "init_not_started")
        begun = self.command(
            "begin-init",
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
        )
        first = self.command(
            "record-init-task",
            "--role",
            "requirements",
            "--created-task-id",
            self.tasks["requirements"],
        )
        self.assertEqual(first["missingRoles"], ["main", "review"])
        resumed = self.command(
            "begin-init",
            "--goal-mode-authorized",
            "--merge-mode",
            "review-only",
            "--merge-method",
            "squash",
        )
        self.assertTrue(resumed["duplicate"])
        self.assertEqual(resumed["workflowId"], begun["workflowId"])
        self.assertEqual(resumed["tasks"], {"requirements": self.tasks["requirements"]})
        for role in ("main", "review"):
            self.command(
                "record-init-task",
                "--role",
                role,
                "--created-task-id",
                self.tasks[role],
            )
        initialized = self.finalize_init()
        self.assertFalse(initialized["recovered"])
        policy_conflict = self.command(
            "begin-init",
            "--goal-mode-authorized",
            "--merge-mode",
            "merge-on-approve",
            "--merge-method",
            "squash",
            expect=2,
        )
        self.assertEqual(policy_conflict["error"]["kind"], "config_conflict")
        state_path = Path(initialized["stateRoot"]) / "state.json"
        state_path.unlink()
        interrupted = self.command("status")
        self.assertTrue(interrupted["recoveryRequired"])
        self.assertEqual(interrupted["tasks"], self.tasks)
        recovered = self.finalize_init()
        self.assertTrue(recovered["recovered"])
        self.assertEqual(recovered["workflowId"], initialized["workflowId"])
        self.assertEqual(recovered["tasks"], self.tasks)

    def test_requirements_requires_deterministic_pushed_current_snapshot(self) -> None:
        first_commit = self.commit_feature_documents()
        initialized = self.initialize()
        self.ack_all()
        wrong_path = self.command(
            "prepare-requirements",
            "--task-id",
            self.tasks["requirements"],
            "--feature-id",
            self.feature_id,
            "--title",
            "Sample feature",
            "--branch",
            self.feature_branch,
            "--requirements-path",
            "docs/feature/other/requirements.md",
            "--requirements-commit-sha",
            first_commit,
            "--confirmation-evidence",
            "Confirmed.",
            expect=2,
        )
        self.assertEqual(wrong_path["error"]["kind"], "invalid_requirements")

        requirements_path = "docs/feature/sample-feature/requirements.md"
        content = (self.repo / requirements_path).read_text(encoding="utf-8")
        self.write(
            requirements_path,
            content.replace(
                "2026-07-27T12:00:00Z",
                "2026-07-27T12:05:00Z",
            ),
        )
        self.git("add", requirements_path)
        self.git("commit", "-m", "docs: reconfirm requirements")
        unpushed = self.git("rev-parse", "HEAD")
        not_remote = self.command(
            "prepare-requirements",
            "--task-id",
            self.tasks["requirements"],
            "--feature-id",
            self.feature_id,
            "--title",
            "Sample feature",
            "--branch",
            self.feature_branch,
            "--requirements-path",
            requirements_path,
            "--requirements-commit-sha",
            unpushed,
            "--confirmation-evidence",
            "Reconfirmed.",
            expect=2,
        )
        self.assertEqual(not_remote["error"]["kind"], "snapshot_mismatch")
        self.git("push", "origin", self.feature_branch)
        superseded = self.command(
            "prepare-requirements",
            "--task-id",
            self.tasks["requirements"],
            "--feature-id",
            self.feature_id,
            "--title",
            "Sample feature",
            "--branch",
            self.feature_branch,
            "--requirements-path",
            requirements_path,
            "--requirements-commit-sha",
            first_commit,
            "--confirmation-evidence",
            "Old confirmation.",
            expect=2,
        )
        self.assertEqual(superseded["error"]["kind"], "snapshot_mismatch")

        conflicting_content = (self.repo / requirements_path).read_text(
            encoding="utf-8"
        )
        self.write(
            requirements_path,
            f"""{conflicting_content}
- Status: Draft
- FeatureId: conflicting-feature-abcdef012345
- Branch: codex/conflicting-feature
- ConfirmedBy:
- ConfirmedAt:
""",
        )
        self.git("add", requirements_path)
        self.git("commit", "-m", "docs: add conflicting requirements metadata")
        conflicting_commit = self.git("rev-parse", "HEAD")
        self.git("push", "origin", self.feature_branch)
        state_path = Path(initialized["stateRoot"]) / "state.json"
        before_conflict = json.loads(state_path.read_text(encoding="utf-8"))
        conflicting = self.command(
            "prepare-requirements",
            "--task-id",
            self.tasks["requirements"],
            "--feature-id",
            self.feature_id,
            "--title",
            "Sample feature",
            "--branch",
            self.feature_branch,
            "--requirements-path",
            requirements_path,
            "--requirements-commit-sha",
            conflicting_commit,
            "--confirmation-evidence",
            "The conflicting document must not be accepted.",
            expect=2,
        )
        self.assertEqual(conflicting["error"]["kind"], "invalid_requirements")
        after_conflict = self.command("status")
        self.assertEqual(after_conflict["features"], {})
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8")),
            before_conflict,
        )

    def test_full_lifecycle_with_blocked_goal_and_partial_release_retry(self) -> None:
        plan_sha = self.commit_feature_documents()
        init = self.initialize()
        self.assertFalse(init["duplicate"])
        premature_feature = self.command(
            "prepare-requirements",
            "--task-id",
            self.tasks["requirements"],
            "--feature-id",
            self.feature_id,
            "--title",
            "Sample feature",
            "--branch",
            self.feature_branch,
            "--requirements-path",
            "docs/feature/sample-feature/requirements.md",
            "--requirements-commit-sha",
            plan_sha,
            "--confirmation-evidence",
            "Premature confirmation.",
            expect=2,
        )
        self.assertEqual(premature_feature["error"]["kind"], "bootstrap_incomplete")
        for index, (role, task_id) in enumerate(self.tasks.items(), start=1):
            before_ack = self.command("status", "--task-id", task_id)
            self.assertEqual(before_ack["role"], role)
            self.assertFalse(before_ack["bootstrap"][role])
            self.assertFalse(before_ack["ready"])
            ack = self.command(
                "ack-bootstrap",
                "--task-id",
                task_id,
                "--role",
                role,
            )
            self.assertEqual(ack["ready"], index == len(self.tasks))
        self.assertTrue(ack["ready"])

        requirements = self.command(
            "prepare-requirements",
            "--task-id",
            self.tasks["requirements"],
            "--feature-id",
            self.feature_id,
            "--title",
            "Sample feature",
            "--branch",
            self.feature_branch,
            "--requirements-path",
            "docs/feature/sample-feature/requirements.md",
            "--requirements-commit-sha",
            plan_sha,
            "--confirmation-evidence",
            "Test user confirmed the complete snapshot.",
        )
        requirements_file = self.payload_file(
            "requirements.json", requirements["message"]
        )
        state_path = Path(init["stateRoot"]) / "state.json"
        before_failed_acceptance = state_path.read_bytes()
        corrupt_state = json.loads(before_failed_acceptance)
        corrupt_state["features"][self.feature_id]["unexpectedAuthority"] = True
        state_path.write_text(json.dumps(corrupt_state), encoding="utf-8")
        corrupt_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(corrupt_status["error"]["kind"], "invalid_payload")
        state_path.write_bytes(before_failed_acceptance)

        def reject_transition(state: dict, payload: dict, duplicate: bool) -> None:
            del state, payload, duplicate
            raise WORKFLOW_MODULE.WorkflowError(
                "stale_result", "synthetic stale request"
            )

        environment_before = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(self.codex_home)
        try:
            with self.assertRaises(WORKFLOW_MODULE.WorkflowError):
                WORKFLOW_MODULE.accept_request(
                    argparse.Namespace(
                        repo=str(self.repo),
                        task_id=self.tasks["main"],
                        payload_file=str(requirements_file),
                    ),
                    "RequirementsHandoff",
                    "requirements",
                    "main",
                    reject_transition,
                )
        finally:
            if environment_before is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = environment_before
        self.assertEqual(state_path.read_bytes(), before_failed_acceptance)
        self.command(
            "accept-requirements",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(requirements_file),
        )

        plan = self.command(
            "prepare-plan-review",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--plan-commit-sha",
            plan_sha,
            "--requirements-path",
            "docs/feature/sample-feature/requirements.md",
            "--design-path",
            "docs/feature/sample-feature/design.md",
            "--implementation-plan-path",
            "docs/feature/sample-feature/implementation-plan.md",
            "--acceptance-criteria-digest",
            "1" * 64,
        )
        plan_file = self.payload_file("plan-request.json", plan["message"])
        self.command(
            "accept-plan-review",
            "--task-id",
            self.tasks["review"],
            "--payload-file",
            str(plan_file),
        )
        plan_report_branch = plan["message"]["body"]["reviewRecordBranch"]
        plan_report_commit, plan_report_digest = self.add_review_report(
            plan_report_branch,
            plan_sha,
            "docs/reviews/plan-1.md",
            "# Technical Plan Review\n\nDecision: Fail\n",
        )
        failed_plan_result = self.command(
            "prepare-plan-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(plan_file),
            "--decision",
            "FAIL",
            "--majors",
            "1",
            "--report-branch",
            plan_report_branch,
            "--report-path",
            "docs/reviews/plan-1.md",
            "--report-commit-sha",
            plan_report_commit,
            "--report-sha256",
            plan_report_digest,
            "--summary",
            "Plan needs an explicit recovery design.",
        )
        failed_plan_file = self.payload_file(
            "plan-result-fail.json", failed_plan_result["message"]
        )
        failed_plan = self.command(
            "apply-plan-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(failed_plan_file),
        )
        self.assertEqual(failed_plan["stage"], "PLAN_CHANGES_REQUESTED")

        self.write(
            "docs/feature/sample-feature/design.md",
            "# Design\n\nUse strict state transitions and explicit recovery.\n",
        )
        self.git("add", "docs/feature/sample-feature/design.md")
        self.git("commit", "-m", "docs: address plan review")
        revised_plan_sha = self.git("rev-parse", "HEAD")
        self.git("push", "origin", self.feature_branch)
        revised_plan = self.command(
            "prepare-plan-review",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--plan-commit-sha",
            revised_plan_sha,
            "--requirements-path",
            "docs/feature/sample-feature/requirements.md",
            "--design-path",
            "docs/feature/sample-feature/design.md",
            "--implementation-plan-path",
            "docs/feature/sample-feature/implementation-plan.md",
            "--acceptance-criteria-digest",
            "1" * 64,
            "--previous-result-message-id",
            failed_plan_result["message"]["messageId"],
        )
        revised_plan_file = self.payload_file(
            "plan-request-2.json", revised_plan["message"]
        )
        self.command(
            "accept-plan-review",
            "--task-id",
            self.tasks["review"],
            "--payload-file",
            str(revised_plan_file),
        )
        revised_report_branch = revised_plan["message"]["body"]["reviewRecordBranch"]
        revised_report_commit, revised_report_digest = self.add_review_report(
            revised_report_branch,
            revised_plan_sha,
            "docs/reviews/plan-2.md",
            "# Technical Plan Re-review\n\nDecision: Pass\n",
        )
        plan_result = self.command(
            "prepare-plan-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(revised_plan_file),
            "--decision",
            "PASS",
            "--minors",
            "1",
            "--report-branch",
            revised_report_branch,
            "--report-path",
            "docs/reviews/plan-2.md",
            "--report-commit-sha",
            revised_report_commit,
            "--report-sha256",
            revised_report_digest,
            "--summary",
            "Revised plan is approved for Goal-mode implementation.",
        )
        plan_result_file = self.payload_file(
            "plan-result-pass.json", plan_result["message"]
        )
        applied_plan = self.command(
            "apply-plan-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(plan_result_file),
        )
        self.assertEqual(applied_plan["stage"], "DEVELOPMENT_QUEUED")

        objective = (
            "Implement sample feature with tests, docs, changelog, push, and PR proof."
        )
        prepared_goal = self.command(
            "start-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--objective",
            objective,
        )
        goal_run_id = prepared_goal["goalRun"]["goalRunId"]
        prepared_retry = self.command(
            "start-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--objective",
            objective,
        )
        self.assertTrue(prepared_retry["duplicate"])
        self.assertEqual(prepared_retry["goalRun"], prepared_goal["goalRun"])
        activated = self.command(
            "start-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--objective",
            objective,
            "--activate",
            "--goal-run-id",
            goal_run_id,
            "--goal-thread-id",
            self.tasks["main"],
        )
        activated_retry = self.command(
            "start-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--objective",
            objective,
            "--activate",
            "--goal-run-id",
            goal_run_id,
            "--goal-thread-id",
            self.tasks["main"],
        )
        self.assertFalse(activated["duplicate"])
        self.assertTrue(activated_retry["duplicate"])
        self.assertEqual(activated_retry["goalRun"], activated["goalRun"])
        blocked = self.command(
            "block-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--goal-run-id",
            goal_run_id,
            "--reason",
            "Waiting for deterministic test recovery.",
        )
        self.assertEqual(blocked["stage"], "DEVELOPMENT_BLOCKED")
        self.command(
            "resume-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--goal-run-id",
            goal_run_id,
        )
        self.write("src/sample.txt", "implemented\n")
        self.git("add", "src/sample.txt")
        self.git("commit", "-m", "feat: implement sample")
        head_sha = self.git("rev-parse", "HEAD")
        self.git("push", "origin", self.feature_branch)
        self.command(
            "complete-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--goal-run-id",
            goal_run_id,
            "--tokens-used",
            "1234",
        )

        code = self.command(
            "prepare-code-review",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--pr-number",
            "7",
            "--pr-url",
            "https://github.com/example/project/pull/7",
            "--base-ref",
            "main",
            "--base-sha",
            plan_sha,
            "--head-ref",
            self.feature_branch,
            "--head-sha",
            head_sha,
        )
        code_file = self.payload_file("code-request.json", code["message"])
        self.command(
            "accept-code-review",
            "--task-id",
            self.tasks["review"],
            "--payload-file",
            str(code_file),
        )
        code_report_branch = code["message"]["body"]["reviewRecordBranch"]
        code_report_commit, code_report_digest = self.add_review_report(
            code_report_branch,
            head_sha,
            "docs/reviews/code-1.md",
            "# Code Review\n\nDecision: Request changes\n",
        )
        changes_result = self.command(
            "prepare-code-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(code_file),
            "--decision",
            "REQUEST_CHANGES",
            "--blockers",
            "1",
            "--report-branch",
            code_report_branch,
            "--report-path",
            "docs/reviews/code-1.md",
            "--report-commit-sha",
            code_report_commit,
            "--report-sha256",
            code_report_digest,
            "--checks-status",
            "PASSING",
            "--checks-checked-at",
            "2026-07-27T12:00:00Z",
            "--merge-status",
            "NOT_REQUESTED",
            "--summary",
            "A blocking recovery defect must be fixed.",
        )
        changes_file = self.payload_file(
            "code-result-changes.json", changes_result["message"]
        )
        changes_applied = self.command(
            "apply-code-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(changes_file),
        )
        self.assertEqual(changes_applied["stage"], "DEVELOPMENT_QUEUED")

        remediation_objective = "Fix the blocking review finding and refresh proof."
        remediation = self.command(
            "start-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--objective",
            remediation_objective,
        )
        self.assertEqual(remediation["goalRun"]["purpose"], "CODE_REMEDIATION")
        remediation_id = remediation["goalRun"]["goalRunId"]
        self.command(
            "start-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--objective",
            remediation_objective,
            "--activate",
            "--goal-run-id",
            remediation_id,
            "--goal-thread-id",
            self.tasks["main"],
        )
        self.write("src/sample.txt", "implemented and fixed\n")
        self.git("add", "src/sample.txt")
        self.git("commit", "-m", "fix: address code review")
        head_sha = self.git("rev-parse", "HEAD")
        self.git("push", "origin", self.feature_branch)
        self.command(
            "complete-development",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--goal-run-id",
            remediation_id,
        )

        code = self.command(
            "prepare-code-review",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--pr-number",
            "7",
            "--pr-url",
            "https://github.com/example/project/pull/7",
            "--base-ref",
            "main",
            "--base-sha",
            plan_sha,
            "--head-ref",
            self.feature_branch,
            "--head-sha",
            head_sha,
            "--previous-result-message-id",
            changes_result["message"]["messageId"],
        )
        code_file = self.payload_file("code-request-2.json", code["message"])
        self.command(
            "accept-code-review",
            "--task-id",
            self.tasks["review"],
            "--payload-file",
            str(code_file),
        )
        code_report_branch = code["message"]["body"]["reviewRecordBranch"]
        code_report_commit, code_report_digest = self.add_review_report(
            code_report_branch,
            head_sha,
            "docs/reviews/code-2.md",
            "# Code Re-review\n\nDecision: Approve\n",
        )
        direct_merge = self.command(
            "prepare-code-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(code_file),
            "--decision",
            "APPROVE",
            "--report-branch",
            code_report_branch,
            "--report-path",
            "docs/reviews/code-2.md",
            "--report-commit-sha",
            code_report_commit,
            "--report-sha256",
            code_report_digest,
            "--checks-status",
            "PASSING",
            "--checks-checked-at",
            "2026-07-27T12:00:00Z",
            "--checks-url",
            "https://github.com/example/project/actions/runs/7",
            "--merge-status",
            "MERGED",
            "--merge-method",
            "squash",
            "--merge-url",
            "https://github.com/example/project/pull/7",
            "--merge-sha",
            head_sha,
            "--merged-at",
            "2026-07-27T12:01:00Z",
            "--summary",
            "Exact reviewed head passed checks and was merged.",
            expect=2,
        )
        self.assertEqual(direct_merge["error"]["kind"], "invalid_transition")

        failing_ready = self.command(
            "prepare-code-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(code_file),
            "--decision",
            "APPROVE",
            "--report-branch",
            code_report_branch,
            "--report-path",
            "docs/reviews/code-2.md",
            "--report-commit-sha",
            code_report_commit,
            "--report-sha256",
            code_report_digest,
            "--checks-status",
            "FAILING",
            "--checks-checked-at",
            "2026-07-27T12:00:00Z",
            "--merge-status",
            "READY",
            "--summary",
            "Failing checks must never authorize merge readiness.",
            expect=2,
        )
        self.assertEqual(failing_ready["error"]["kind"], "invalid_payload")

        ready_result = self.command(
            "prepare-code-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(code_file),
            "--decision",
            "APPROVE",
            "--report-branch",
            code_report_branch,
            "--report-path",
            "docs/reviews/code-2.md",
            "--report-commit-sha",
            code_report_commit,
            "--report-sha256",
            code_report_digest,
            "--checks-status",
            "PASSING",
            "--checks-checked-at",
            "2026-07-27T12:00:00Z",
            "--checks-url",
            "https://github.com/example/project/actions/runs/7",
            "--merge-status",
            "READY",
            "--summary",
            "Exact reviewed head is ready for an externally authorized merge.",
        )
        ready_file = self.payload_file(
            "code-result-ready.json", ready_result["message"]
        )
        ready_applied = self.command(
            "apply-code-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(ready_file),
        )
        self.assertEqual(ready_applied["stage"], "MERGE_READY")

        merged_result = self.command(
            "prepare-code-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(code_file),
            "--decision",
            "APPROVE",
            "--report-branch",
            code_report_branch,
            "--report-path",
            "docs/reviews/code-2.md",
            "--report-commit-sha",
            code_report_commit,
            "--report-sha256",
            code_report_digest,
            "--checks-status",
            "PASSING",
            "--checks-checked-at",
            "2026-07-27T12:01:00Z",
            "--checks-url",
            "https://github.com/example/project/actions/runs/7",
            "--merge-status",
            "MERGED",
            "--merge-method",
            "squash",
            "--merge-url",
            "https://github.com/example/project/pull/7",
            "--merge-sha",
            head_sha,
            "--merged-at",
            "2026-07-27T12:01:00Z",
            "--summary",
            "Review observed authoritative merge proof for the exact READY head.",
        )
        merged_file = self.payload_file(
            "code-result-merged.json", merged_result["message"]
        )
        applied_code = self.command(
            "apply-code-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(merged_file),
        )
        self.assertEqual(applied_code["stage"], "RELEASE_AWAITING_AUTHORIZATION")

        authorization_draft = {
            "schemaVersion": 1,
            "workflowId": init["workflowId"],
            "featureId": self.feature_id,
            "mergeCommitSha": head_sha,
            "version": "1.2.3",
            "tag": "v1.2.3",
            "targets": [
                {
                    "kind": "GITHUB_RELEASE",
                    "repositoryKey": "example/project",
                    "tag": "v1.2.3",
                    "releaseName": "Version 1.2.3",
                    "artifacts": [{"name": "sample.zip", "sha256": "8" * 64}],
                },
                {
                    "kind": "PYPI",
                    "repository": "PYPI",
                    "projectName": "sample-project",
                    "version": "1.2.3",
                    "artifacts": [
                        {"name": "sample_project-1.2.3.whl", "sha256": "9" * 64}
                    ],
                },
            ],
            "authorizedBy": "test-user",
            "authorizationEvidence": "Publish exactly these two targets and artifact digests.",
            "createdAt": "2026-07-27T12:02:00Z",
        }
        authorization_file = self.payload_file(
            "release-authorization.json", authorization_draft
        )
        authorization_result = self.command(
            "record-release-authorization",
            "--task-id",
            self.tasks["main"],
            "--authorization-file",
            str(authorization_file),
        )
        authorization = authorization_result["authorization"]
        by_kind = {target["kind"]: target for target in authorization["targets"]}

        first_release = {
            "schemaVersion": 1,
            "workflowId": init["workflowId"],
            "featureId": self.feature_id,
            "authorizationId": authorization["authorizationId"],
            "mergeCommitSha": head_sha,
            "version": "1.2.3",
            "tag": "v1.2.3",
            "targets": [
                {
                    "targetId": by_kind["GITHUB_RELEASE"]["targetId"],
                    "kind": "GITHUB_RELEASE",
                    "status": "PUBLISHED",
                    "artifacts": [
                        {
                            "name": "sample.zip",
                            "sha256": "8" * 64,
                            "url": "https://github.com/example/project/releases/download/v1.2.3/sample.zip",
                        }
                    ],
                    "publishedAt": "2026-07-27T12:03:00Z",
                    "releaseUrl": "https://github.com/example/project/releases/tag/v1.2.3",
                    "tagCommitSha": head_sha,
                },
                {
                    "targetId": by_kind["PYPI"]["targetId"],
                    "kind": "PYPI",
                    "status": "FAILED",
                    "error": "Transient upload failure.",
                },
            ],
            "publishedAt": "2026-07-27T12:03:00Z",
        }
        wrong_github_proof = copy.deepcopy(first_release)
        wrong_github_proof["targets"][0]["releaseUrl"] = (
            "https://github.com/another/project/releases/tag/v1.2.3"
        )
        wrong_github_file = self.payload_file(
            "release-result-wrong-github.json",
            wrong_github_proof,
        )
        wrong_github = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(wrong_github_file),
            expect=2,
        )
        self.assertEqual(wrong_github["error"]["kind"], "invalid_payload")
        first_release_file = self.payload_file(
            "release-result-first.json", first_release
        )
        first_result = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(first_release_file),
        )
        self.assertEqual(first_result["stage"], "RELEASE_FAILED")
        replayed_failure = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(first_release_file),
        )
        self.assertTrue(replayed_failure["duplicate"])
        failed_state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            len(failed_state["features"][self.feature_id]["release"]["submissions"]),
            1,
        )
        close_error = self.command(
            "close-feature",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--scenario",
            "Sample scenario",
            expect=2,
        )
        self.assertEqual(close_error["error"]["kind"], "invalid_transition")

        retry_release = {
            "schemaVersion": 1,
            "workflowId": init["workflowId"],
            "featureId": self.feature_id,
            "authorizationId": authorization["authorizationId"],
            "mergeCommitSha": head_sha,
            "version": "1.2.3",
            "tag": "v1.2.3",
            "targets": [
                {
                    "targetId": by_kind["PYPI"]["targetId"],
                    "kind": "PYPI",
                    "status": "PUBLISHED",
                    "artifacts": [
                        {
                            "name": "sample_project-1.2.3.whl",
                            "sha256": "9" * 64,
                            "url": "https://files.pythonhosted.org/packages/sample_project-1.2.3.whl",
                        }
                    ],
                    "publishedAt": "2026-07-27T12:04:00Z",
                    "projectUrl": "https://pypi.org/project/sample-project/1.2.3/",
                    "repository": "PYPI",
                    "projectName": "sample-project",
                    "version": "1.2.3",
                }
            ],
            "publishedAt": "2026-07-27T12:04:00Z",
        }
        wrong_pypi_proof = copy.deepcopy(retry_release)
        wrong_pypi_proof["targets"][0]["projectUrl"] = (
            "https://pypi.org/project/another-project/1.2.3/"
        )
        wrong_pypi_file = self.payload_file(
            "release-result-wrong-pypi.json",
            wrong_pypi_proof,
        )
        wrong_pypi = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(wrong_pypi_file),
            expect=2,
        )
        self.assertEqual(wrong_pypi["error"]["kind"], "invalid_payload")
        retry_file = self.payload_file("release-result-retry.json", retry_release)
        retry_result = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(retry_file),
        )
        self.assertEqual(retry_result["stage"], "RELEASED")
        self.assertEqual(len(retry_result["result"]["targets"]), 2)

        legacy_state = json.loads(state_path.read_bytes())
        legacy_state["schemaVersion"] = 1
        del legacy_state["features"][self.feature_id]["release"]["submissions"]
        state_path.write_text(json.dumps(legacy_state), encoding="utf-8")
        migrated_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
        )
        self.assertEqual(
            migrated_status["features"][self.feature_id]["stage"], "RELEASED"
        )
        migrated_state = json.loads(state_path.read_bytes())
        self.assertEqual(migrated_state["schemaVersion"], 2)
        self.assertEqual(
            len(migrated_state["features"][self.feature_id]["release"]["submissions"]),
            2,
        )

        released_state_bytes = state_path.read_bytes()
        released_state = json.loads(released_state_bytes)
        release_ledger = released_state["features"][self.feature_id]["release"]
        self.assertEqual(len(release_ledger["submissions"]), 2)
        self.assertEqual(
            release_ledger["lastSubmission"],
            release_ledger["submissions"][-1],
        )

        missing_history_state = copy.deepcopy(released_state)
        del missing_history_state["features"][self.feature_id]["release"]["submissions"]
        state_path.write_text(json.dumps(missing_history_state), encoding="utf-8")
        missing_history_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(missing_history_status["error"]["kind"], "invalid_state")
        state_path.write_bytes(released_state_bytes)

        rewritten_submission_state = copy.deepcopy(released_state)
        rewritten_release = rewritten_submission_state["features"][self.feature_id][
            "release"
        ]
        github_proof = next(
            item
            for item in rewritten_release["result"]["targets"]
            if item["kind"] == "GITHUB_RELEASE"
        )
        rewritten_submission = {
            "authorizationId": rewritten_release["authorization"]["authorizationId"],
            "targets": [github_proof],
            "publishedAt": rewritten_release["result"]["publishedAt"],
        }
        rewritten_submission["submissionDigest"] = WORKFLOW_MODULE.digest(
            rewritten_submission
        )
        rewritten_release["lastSubmission"] = rewritten_submission
        rewritten_release["submissions"][-1] = rewritten_submission
        state_path.write_text(json.dumps(rewritten_submission_state), encoding="utf-8")
        rewritten_submission_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(rewritten_submission_status["error"]["kind"], "invalid_state")
        state_path.write_bytes(released_state_bytes)

        duplicate_target_state = copy.deepcopy(released_state)
        duplicate_release = duplicate_target_state["features"][self.feature_id][
            "release"
        ]
        duplicate_submission = copy.deepcopy(duplicate_release["lastSubmission"])
        duplicate_submission["targets"].append(
            copy.deepcopy(duplicate_submission["targets"][0])
        )
        duplicate_submission["submissionDigest"] = WORKFLOW_MODULE.digest(
            {
                key: value
                for key, value in duplicate_submission.items()
                if key != "submissionDigest"
            }
        )
        duplicate_release["lastSubmission"] = duplicate_submission
        duplicate_release["submissions"][-1] = duplicate_submission
        state_path.write_text(json.dumps(duplicate_target_state), encoding="utf-8")
        duplicate_target_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(duplicate_target_status["error"]["kind"], "invalid_state")
        state_path.write_bytes(released_state_bytes)

        missing_target_state = json.loads(released_state_bytes)
        persisted_release = missing_target_state["features"][self.feature_id]["release"]
        persisted_release["result"]["targets"] = persisted_release["result"]["targets"][
            :1
        ]
        proof_authority = {
            key: value
            for key, value in persisted_release["result"].items()
            if key != "proofDigest"
        }
        persisted_release["result"]["proofDigest"] = WORKFLOW_MODULE.digest(
            proof_authority
        )
        state_path.write_text(json.dumps(missing_target_state), encoding="utf-8")
        missing_target_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(missing_target_status["error"]["kind"], "invalid_state")
        state_path.write_bytes(released_state_bytes)

        missing_authorization_id = json.loads(released_state_bytes)
        del missing_authorization_id["features"][self.feature_id]["release"][
            "authorization"
        ]["authorizationId"]
        state_path.write_text(json.dumps(missing_authorization_id), encoding="utf-8")
        missing_authorization_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(missing_authorization_status["error"]["kind"], "invalid_state")
        state_path.write_bytes(released_state_bytes)

        wrong_subset = copy.deepcopy(retry_result["result"])
        wrong_subset["targets"] = [
            item for item in wrong_subset["targets"] if item["kind"] == "GITHUB_RELEASE"
        ]
        wrong_subset.pop("proofDigest")
        wrong_subset_file = self.payload_file(
            "release-result-wrong-subset-replay.json", wrong_subset
        )
        wrong_subset_replay = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(wrong_subset_file),
            expect=2,
        )
        self.assertEqual(wrong_subset_replay["error"]["kind"], "replay_conflict")

        replayed_release = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(retry_file),
        )
        self.assertTrue(replayed_release["duplicate"])
        self.assertEqual(replayed_release["result"], retry_result["result"])
        cumulative_file = self.payload_file(
            "release-result-cumulative-replay.json", retry_result["result"]
        )
        cumulative_replay = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(cumulative_file),
        )
        self.assertTrue(cumulative_replay["duplicate"])
        self.assertEqual(cumulative_replay["result"], retry_result["result"])

        closure = self.command(
            "close-feature",
            "--task-id",
            self.tasks["main"],
            "--feature-id",
            self.feature_id,
            "--scenario",
            "A confirmed feature completed plan review, implementation, code review, merge, and release.",
        )
        self.assertEqual(closure["stage"], "CLOSED")
        self.assertEqual(len(closure["closure"]["releaseTargets"]), 2)
        closed_state_bytes = state_path.read_bytes()
        arbitrary_closure_target = json.loads(closed_state_bytes)
        closure_record = arbitrary_closure_target["features"][self.feature_id][
            "closure"
        ]
        closure_record["releaseTargets"] = ["a" * 64]
        closure_authority = {
            key: value for key, value in closure_record.items() if key != "closureId"
        }
        closure_record["closureId"] = WORKFLOW_MODULE.digest(closure_authority)
        state_path.write_text(json.dumps(arbitrary_closure_target), encoding="utf-8")
        arbitrary_closure_status = self.command(
            "status",
            "--task-id",
            self.tasks["main"],
            expect=2,
        )
        self.assertEqual(arbitrary_closure_status["error"]["kind"], "invalid_state")
        state_path.write_bytes(closed_state_bytes)
        for impossible_stage in (
            "RELEASE_AWAITING_AUTHORIZATION",
            "RELEASED",
            "MERGED",
        ):
            contradictory = json.loads(closed_state_bytes)
            contradictory["features"][self.feature_id]["stage"] = impossible_stage
            state_path.write_text(json.dumps(contradictory), encoding="utf-8")
            contradictory_status = self.command(
                "status",
                "--task-id",
                self.tasks["main"],
                expect=2,
            )
            self.assertEqual(
                contradictory_status["error"]["kind"],
                "invalid_state",
                impossible_stage,
            )
            state_path.write_bytes(closed_state_bytes)
        status = self.command("status", "--task-id", self.tasks["main"])
        self.assertEqual(status["features"][self.feature_id]["stage"], "CLOSED")


if __name__ == "__main__":
    unittest.main()
