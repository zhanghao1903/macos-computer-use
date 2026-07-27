from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWCTL = PLUGIN_ROOT / "scripts" / "workflowctl.py"


class WorkflowCtlIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.codex_home = self.root / "codex-home"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Workflow Test")
        self.git("config", "user.email", "workflow@example.invalid")
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
            "docs/feature/sample/requirements.md",
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
        self.write("docs/feature/sample/design.md", "# Design\n\nUse strict state transitions.\n")
        self.write(
            "docs/feature/sample/implementation-plan.md",
            "# Implementation Plan\n\nImplement, test, review, merge, release, close.\n",
        )
        self.git("add", "docs")
        self.git("commit", "-m", "docs: add confirmed feature plan")
        return self.git("rev-parse", "HEAD")

    def add_review_report(self, branch: str, base_sha: str, relative: str, content: str) -> tuple[str, str]:
        self.git("checkout", "-b", branch, base_sha)
        path = self.write(relative, content)
        self.git("add", relative)
        self.git("commit", "-m", "docs: record independent review")
        commit = self.git("rev-parse", "HEAD")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.git("checkout", self.feature_branch)
        return commit, digest

    def test_full_lifecycle_with_blocked_goal_and_partial_release_retry(self) -> None:
        plan_sha = self.commit_feature_documents()
        init = self.command(
            "init",
            "--requirements-task-id",
            self.tasks["requirements"],
            "--main-task-id",
            self.tasks["main"],
            "--review-task-id",
            self.tasks["review"],
            "--goal-mode-authorized",
            "--merge-mode",
            "merge-on-approve",
            "--merge-method",
            "squash",
        )
        self.assertFalse(init["duplicate"])
        for role, task_id in self.tasks.items():
            ack = self.command(
                "ack-bootstrap",
                "--task-id",
                task_id,
                "--role",
                role,
            )
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
            "docs/feature/sample/requirements.md",
            "--requirements-commit-sha",
            plan_sha,
            "--confirmation-evidence",
            "Test user confirmed the complete snapshot.",
        )
        requirements_file = self.payload_file("requirements.json", requirements["message"])
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
            "docs/feature/sample/requirements.md",
            "--design-path",
            "docs/feature/sample/design.md",
            "--implementation-plan-path",
            "docs/feature/sample/implementation-plan.md",
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
            "docs/reviews/plan.md",
            "# Technical Plan Review\n\nDecision: Pass\n",
        )
        plan_result = self.command(
            "prepare-plan-result",
            "--task-id",
            self.tasks["review"],
            "--request-file",
            str(plan_file),
            "--decision",
            "PASS",
            "--minors",
            "1",
            "--report-branch",
            plan_report_branch,
            "--report-path",
            "docs/reviews/plan.md",
            "--report-commit-sha",
            plan_report_commit,
            "--report-sha256",
            plan_report_digest,
            "--summary",
            "Plan is approved for Goal-mode implementation.",
        )
        plan_result_file = self.payload_file("plan-result.json", plan_result["message"])
        applied_plan = self.command(
            "apply-plan-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(plan_result_file),
        )
        self.assertEqual(applied_plan["stage"], "DEVELOPMENT_QUEUED")

        objective = "Implement sample feature with tests, docs, changelog, push, and PR proof."
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
        self.command(
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
            "docs/reviews/code.md",
            "# Code Review\n\nDecision: Approve\n",
        )
        code_result = self.command(
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
            "docs/reviews/code.md",
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
        )
        code_result_file = self.payload_file("code-result.json", code_result["message"])
        applied_code = self.command(
            "apply-code-result",
            "--task-id",
            self.tasks["main"],
            "--payload-file",
            str(code_result_file),
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
                    "artifacts": [{"name": "sample_project-1.2.3.whl", "sha256": "9" * 64}],
                },
            ],
            "authorizedBy": "test-user",
            "authorizationEvidence": "Publish exactly these two targets and artifact digests.",
            "createdAt": "2026-07-27T12:02:00Z",
        }
        authorization_file = self.payload_file("release-authorization.json", authorization_draft)
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
        first_release_file = self.payload_file("release-result-first.json", first_release)
        first_result = self.command(
            "record-release-result",
            "--task-id",
            self.tasks["main"],
            "--result-file",
            str(first_release_file),
        )
        self.assertEqual(first_result["stage"], "RELEASE_FAILED")
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
        status = self.command("status", "--task-id", self.tasks["main"])
        self.assertEqual(status["features"][self.feature_id]["stage"], "CLOSED")


if __name__ == "__main__":
    unittest.main()
