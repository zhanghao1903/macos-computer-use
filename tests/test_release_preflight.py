from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from typing import Any
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class ReleasePreflightTests(unittest.TestCase):
    def test_release_docs_json_examples_are_valid(self) -> None:
        preflight = _load_preflight()
        for relative in preflight.MARKDOWN_JSON_DOCS:
            path = ROOT / relative
            text = path.read_text(encoding="utf-8")
            for index, match in enumerate(
                re.finditer(r"```json\n(.*?)\n```", text, re.S),
                start=1,
            ):
                with self.subTest(path=relative, index=index):
                    json.loads(match.group(1))

    def test_default_preflight_passes_local_checks(self) -> None:
        preflight = _load_preflight()

        results = preflight.run_preflight(ROOT)
        failures = [result for result in results if result.status == "fail"]
        external = [
            result for result in results if result.name.startswith("external-proof:")
        ]

        self.assertEqual(failures, [])
        self.assertTrue(external)
        self.assertTrue(all(result.status == "warn" for result in external))
        names = {result.name for result in results}
        self.assertIn("public-api:app-control-protocol", names)
        self.assertIn("public-api:computer-use-macos", names)
        self.assertIn("public-api:wechat-desktop-tool", names)
        self.assertIn("command-builder:computer-use-macos", names)
        self.assertIn("command-builder:wechat-desktop-tool", names)
        self.assertIn("service-envelope:app-control-protocol", names)
        self.assertIn("observer-surface:app-control-protocol", names)
        self.assertIn("observer-surface:computer-use-macos", names)
        self.assertIn("observer-surface:wechat-desktop-tool", names)
        self.assertIn("module-entrypoint:computer-use-macos:root", names)
        self.assertIn("module-entrypoint:computer-use-macos:doctor", names)
        self.assertIn("module-entrypoint:computer-use-macos:serve", names)
        self.assertIn("module-entrypoint:wechat-desktop-tool:send-message", names)
        self.assertIn("helper-template-smoke:computer-use-macos", names)
        self.assertIn("dry-run-smoke:textedit", names)
        self.assertIn("dry-run-smoke:wechat-focus-draft", names)
        self.assertIn("dry-run-smoke:wechat-example-module-focus-draft", names)
        self.assertIn("local-service-smoke:computer-use-macos", names)
        self.assertIn("workflow:ci-verifies-sdist-contents", names)
        self.assertIn("workflow:release-verifies-sdist-contents", names)
        self.assertIn("workflow:release-verifies-tag-version", names)
        self.assertIn("path:docs/quickstart.md", names)
        self.assertIn("docs-json:docs/quickstart.md", names)
        self.assertIn("docs-toml:docs/quickstart.md", names)
        self.assertIn("docs-json:docs/protocol.md", names)
        self.assertIn("docs-toml:docs/protocol.md", names)
        self.assertIn("config-toml:examples/app-control.toml", names)
        self.assertIn(
            "path:packages/computer-use-macos/src/computer_use_macos/"
            "observations.py",
            names,
        )
        self.assertIn(
            "path:packages/wechat-desktop-tool/src/wechat_desktop_tool/"
            "adapter.py",
            names,
        )
        dry_run = [
            result for result in results if result.name.startswith("dry-run-smoke:")
        ]
        self.assertTrue(dry_run)
        self.assertTrue(all(result.status == "ok" for result in dry_run))
        module_entrypoints = [
            result
            for result in results
            if result.name.startswith("module-entrypoint:")
        ]
        self.assertTrue(module_entrypoints)
        self.assertTrue(all(result.status == "ok" for result in module_entrypoints))
        helper_smoke = [
            result
            for result in results
            if result.name.startswith("helper-template-smoke:")
        ]
        self.assertEqual(len(helper_smoke), 1)
        self.assertEqual(helper_smoke[0].status, "ok")
        local_service_smoke = [
            result
            for result in results
            if result.name == "local-service-smoke:computer-use-macos"
        ]
        self.assertEqual(len(local_service_smoke), 1)
        self.assertIn(local_service_smoke[0].status, {"ok", "warn"})
        self.assertNotEqual(local_service_smoke[0].status, "fail")

    def test_external_proof_loader_reports_missing_file(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "release-proof.json"
            proof: dict[str, Any] = {}
            results: list[Any] = []

            preflight._merge_external_proof(
                proof,
                results,
                source_name="release-proof",
                path=missing,
                loader=preflight._load_proof,
            )

        self.assertEqual(proof, {})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "external-proof-source:release-proof")
        self.assertEqual(results[0].status, "fail")
        self.assertIn("failed to load", results[0].summary)
        self.assertIn("release-proof.json", results[0].summary)

    def test_protocol_public_api_gate_includes_client_protocols(self) -> None:
        preflight = _load_preflight()

        expected = preflight.EXPECTED_PUBLIC_API["app-control-protocol"]

        self.assertIn("AppControlClient", expected)
        self.assertIn("StreamingAppControlClient", expected)

    def test_computer_use_public_api_gate_includes_service_mode(self) -> None:
        preflight = _load_preflight()

        expected = preflight.EXPECTED_PUBLIC_API["computer-use-macos"]

        self.assertIn("LocalCommandService", expected)
        self.assertIn("UnixSocketCommandService", expected)
        self.assertIn("UnixSocketServiceClient", expected)

    def test_wechat_public_api_gate_includes_developer_entrypoints(self) -> None:
        preflight = _load_preflight()

        expected = preflight.EXPECTED_PUBLIC_API["wechat-desktop-tool"]

        self.assertIn("build_wechat_tool", expected)
        self.assertIn("send_message", expected)

    def test_module_entrypoint_check_reports_missing_help_term(self) -> None:
        preflight = _load_preflight()
        original = preflight.MODULE_ENTRYPOINT_CHECKS
        preflight.MODULE_ENTRYPOINT_CHECKS = (
            (
                "computer-use-macos:bad-help-term",
                ("computer_use_macos", "--help"),
                (
                    "packages/app-control-protocol/src",
                    "packages/computer-use-macos/src",
                ),
                ("definitely-not-in-help-output",),
            ),
        )
        try:
            results = preflight._check_module_entrypoints(ROOT)
        finally:
            preflight.MODULE_ENTRYPOINT_CHECKS = original

        self.assertEqual(results[0].status, "fail")
        self.assertIn("definitely-not-in-help-output", results[0].summary)

    def test_markdown_json_check_reports_invalid_example(self) -> None:
        preflight = _load_preflight()
        original = preflight.MARKDOWN_JSON_DOCS
        preflight.MARKDOWN_JSON_DOCS = ("bad.md",)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                (root / "bad.md").write_text(
                    "```json\n{\"missing\": true,\n```\n",
                    encoding="utf-8",
                )

                results = preflight._check_markdown_json_examples(root)
        finally:
            preflight.MARKDOWN_JSON_DOCS = original

        self.assertEqual(results[0].status, "fail")
        self.assertIn("example 1", results[0].summary)

    def test_markdown_json_check_validates_protocol_payloads(self) -> None:
        preflight = _load_preflight()
        original = preflight.MARKDOWN_JSON_DOCS
        preflight.MARKDOWN_JSON_DOCS = ("bad-protocol.md",)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                (root / "bad-protocol.md").write_text(
                    "\n".join(
                        (
                            "```json",
                            "{",
                            '  "schema": "app_control.command.v1",',
                            '  "commandId": "cmd",',
                            '  "tool": "macos.computer_use",',
                            '  "operation": "readiness"',
                            "}",
                            "```",
                            "",
                        )
                    ),
                    encoding="utf-8",
                )

                results = preflight._check_markdown_json_examples(root)
        finally:
            preflight.MARKDOWN_JSON_DOCS = original

        self.assertEqual(results[0].status, "fail")
        self.assertIn("input", results[0].summary)

    def test_toml_config_check_reports_invalid_config_example(self) -> None:
        preflight = _load_preflight()
        original = preflight.MARKDOWN_TOML_DOCS
        preflight.MARKDOWN_TOML_DOCS = ("bad-config.md",)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                examples = root / "examples"
                examples.mkdir()
                (examples / "app-control.toml").write_text(
                    "[computer_use]\ntimeout_ms = 1000\n",
                    encoding="utf-8",
                )
                (root / "bad-config.md").write_text(
                    "```toml\n[computer_use]\ntimeout_ms = 0\n```\n",
                    encoding="utf-8",
                )

                results = preflight._check_toml_config_examples(root)
        finally:
            preflight.MARKDOWN_TOML_DOCS = original

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].name, "docs-toml:bad-config.md")
        self.assertIn("timeout_ms", failures[0].summary)

    def test_public_api_check_reports_missing_export(self) -> None:
        preflight = _load_preflight()
        original = preflight.EXPECTED_PUBLIC_API
        preflight.EXPECTED_PUBLIC_API = {
            **original,
            "computer-use-macos": (
                *original["computer-use-macos"],
                "missing_export_for_test",
            ),
        }
        try:
            results = preflight.run_preflight(ROOT)
        finally:
            preflight.EXPECTED_PUBLIC_API = original

        failures = [result for result in results if result.status == "fail"]
        failure = [
            result
            for result in failures
            if result.name == "public-api:computer-use-macos"
        ][0]
        self.assertIn("missing_export_for_test", failure.summary)

    def test_workflow_check_requires_strict_release_external_preflight(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "ci.yml").write_text(
                (ROOT / ".github" / "workflows" / "ci.yml").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            release = (ROOT / ".github" / "workflows" / "release.yml").read_text(
                encoding="utf-8"
            )
            (workflow_dir / "release.yml").write_text(
                release.replace("--require-external", ""),
                encoding="utf-8",
            )

            results = preflight._check_workflows(root)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("workflow:release-requires-external-proof-preflight", failures)

    def test_workflow_check_requires_release_tag_version_gate(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "ci.yml").write_text(
                (ROOT / ".github" / "workflows" / "ci.yml").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            release = (ROOT / ".github" / "workflows" / "release.yml").read_text(
                encoding="utf-8"
            )
            (workflow_dir / "release.yml").write_text(
                release.replace(
                    '      - name: Verify release tag\n'
                    '        run: python scripts/release_tag_check.py --tag '
                    '"${{ github.event.release.tag_name }}"\n',
                    "",
                ),
                encoding="utf-8",
            )

            results = preflight._check_workflows(root)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("workflow:release-verifies-tag-version", failures)

    def test_require_external_fails_without_external_proofs(self) -> None:
        preflight = _load_preflight()

        results = preflight.run_preflight(ROOT, require_external=True)
        failures = [result.name for result in results if result.status == "fail"]

        self.assertIn("external-proof:helper_app_doctor", failures)
        self.assertIn("external-proof:testpypi_install", failures)

    def test_require_external_accepts_complete_proof_file(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_release_proof_file_rejects_unknown_keys(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            proof_path.write_text(
                json.dumps(
                    {
                        **{key: True for key in preflight.EXTERNAL_PROOFS},
                        "unexpected_external_proof": True,
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                require_external=True,
            )

        source_failures = [
            result
            for result in results
            if result.name == "external-proof-source:release-proof"
        ]
        self.assertEqual(len(source_failures), 1)
        self.assertEqual(source_failures[0].status, "fail")
        self.assertIn("unknown proof key", source_failures[0].summary)

    def test_release_proof_file_rejects_non_boolean_values(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            proof_path.write_text(
                json.dumps(
                    {
                        **{key: True for key in preflight.EXTERNAL_PROOFS},
                        "testpypi_install": "true",
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                require_external=True,
            )

        source_failures = [
            result
            for result in results
            if result.name == "external-proof-source:release-proof"
        ]
        self.assertEqual(len(source_failures), 1)
        self.assertEqual(source_failures[0].status, "fail")
        self.assertIn("must be booleans", source_failures[0].summary)

    def test_helper_doctor_report_supplies_helper_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            helper_report_path = Path(tmpdir) / "helper-doctor.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if key != "helper_app_doctor"
                    }
                ),
                encoding="utf-8",
            )
            helper_report_path.write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "checks": _helper_release_checks(),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                helper_doctor_report_path=helper_report_path,
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_helper_doctor_report_requires_core_helper_checks(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            helper_report_path = Path(tmpdir) / "helper-doctor.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            helper_report_path.write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "checks": [
                            {"name": "manifest", "status": "ok"},
                            {"name": "identity", "status": "ok"},
                            {"name": "helper_app", "status": "ok"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                helper_doctor_report_path=helper_report_path,
                require_external=True,
            )

        failures = {result.name for result in results if result.status == "fail"}
        self.assertIn("external-proof:helper_app_doctor", failures)

    def test_detailed_external_report_overrides_manual_proof_file(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            helper_report_path = Path(tmpdir) / "helper-doctor.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            helper_report_path.write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "checks": [
                            {"name": "manifest", "status": "ok"},
                            {"name": "identity", "status": "ok"},
                            {"name": "endpoint", "status": "ok"},
                            {"name": "token", "status": "ok"},
                            {"name": "helper_app", "status": "failed"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                helper_doctor_report_path=helper_report_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:helper_app_doctor", failures)

    def test_textedit_smoke_report_supplies_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            smoke_path = Path(tmpdir) / "textedit-smoke.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if key != "textedit_smoke"
                    }
                ),
                encoding="utf-8",
            )
            smoke_path.write_text(
                json.dumps(_textedit_smoke_report()),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                textedit_smoke_report_path=smoke_path,
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_textedit_dry_run_report_does_not_supply_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            smoke_path = Path(tmpdir) / "textedit-smoke.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            smoke_path.write_text(
                json.dumps(
                    {
                        "dryRun": True,
                        "app": "TextEdit",
                        "commands": [],
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                textedit_smoke_report_path=smoke_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:textedit_smoke", failures)

    def test_failed_textedit_smoke_report_does_not_supply_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            smoke_path = Path(tmpdir) / "textedit-smoke.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            failed_report = _textedit_smoke_report()
            failed_report.update(
                {
                    "success": False,
                    "failedCommandId": "cmd_textedit_observe",
                    "failurePhase": "observe",
                    "frontmostApp": "pycharm",
                }
            )
            smoke_path.write_text(json.dumps(failed_report), encoding="utf-8")

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                textedit_smoke_report_path=smoke_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:textedit_smoke", failures)

    def test_wechat_smoke_report_supplies_wechat_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            smoke_path = Path(tmpdir) / "wechat-smoke.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if not key.startswith("wechat_")
                    }
                ),
                encoding="utf-8",
            )
            smoke_path.write_text(
                json.dumps(
                    {
                        "result": {
                            "schema": "app_control.observation.v1",
                            "commandId": "cmd",
                            "tool": "wechat.desktop",
                            "operation": "send_message",
                            "status": "ok",
                            "success": True,
                            "summary": "sent",
                            "observation": {"submitted": True},
                        }
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                wechat_smoke_report_paths=(smoke_path,),
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_wechat_dry_run_report_does_not_supply_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "wechat-smoke.json"
            smoke_path.write_text(
                json.dumps(
                    {
                        "submitted": False,
                        "focus": {"success": True},
                        "draft": {"success": True},
                        "appControlCommands": [],
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                wechat_smoke_report_paths=(smoke_path,),
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:wechat_focus_draft_smoke", failures)
        self.assertIn("external-proof:wechat_submit_smoke", failures)

    def test_wechat_focus_draft_report_supplies_focus_draft_external_proof(
        self,
    ) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "wechat-smoke.json"
            smoke_path.write_text(
                json.dumps(
                    {
                        "submitted": False,
                        "focus": _wechat_observation(
                            command_id="cmd_focus",
                            operation="focus_contact",
                            observation={"focusedContact": "File Transfer"},
                        ),
                        "draft": _wechat_observation(
                            command_id="cmd_draft",
                            operation="draft_message",
                            observation={"draftReady": True},
                        ),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                wechat_smoke_report_paths=(smoke_path,),
                require_external=True,
            )

        failures = {result.name for result in results if result.status == "fail"}
        self.assertNotIn("external-proof:wechat_focus_draft_smoke", failures)
        self.assertIn("external-proof:wechat_submit_smoke", failures)

    def test_wechat_focus_draft_report_requires_protocol_observations(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            smoke_path = Path(tmpdir) / "wechat-smoke.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            smoke_path.write_text(
                json.dumps(
                    {
                        "submitted": False,
                        "focus": {"success": True},
                        "draft": {"success": True},
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                wechat_smoke_report_paths=(smoke_path,),
                require_external=True,
            )

        failures = {result.name for result in results if result.status == "fail"}
        self.assertIn("external-proof:wechat_focus_draft_smoke", failures)
        self.assertIn("external-proof:wechat_submit_smoke", failures)

    def test_failed_wechat_smoke_report_overrides_manual_proof_file(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            smoke_path = Path(tmpdir) / "wechat-smoke.json"
            proof_path.write_text(
                json.dumps({key: True for key in preflight.EXTERNAL_PROOFS}),
                encoding="utf-8",
            )
            smoke_path.write_text(
                json.dumps(
                    {
                        "submitted": False,
                        "focus": {"success": False},
                        "draft": {"success": False},
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                wechat_smoke_report_paths=(smoke_path,),
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:wechat_focus_draft_smoke", failures)
        self.assertIn("external-proof:wechat_submit_smoke", failures)

    def test_testpypi_install_report_supplies_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            testpypi_path = Path(tmpdir) / "testpypi-install.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if key != "testpypi_install"
                    }
                ),
                encoding="utf-8",
            )
            testpypi_path.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(preflight),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                testpypi_install_report_path=testpypi_path,
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_testpypi_install_report_requires_all_packages(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            testpypi_path = Path(tmpdir) / "testpypi-install.json"
            testpypi_path.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(
                            preflight,
                            package_names=("app-control-protocol",),
                        ),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                testpypi_install_report_path=testpypi_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:testpypi_install", failures)

    def test_testpypi_install_report_requires_api_smoke(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            testpypi_path = Path(tmpdir) / "testpypi-install.json"
            testpypi_path.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(
                            preflight,
                            api_smoke_overrides={"wechat-desktop-tool": False},
                        ),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                testpypi_install_report_path=testpypi_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:testpypi_install", failures)

    def test_testpypi_install_report_requires_testpypi_index(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            testpypi_path = Path(tmpdir) / "testpypi-install.json"
            testpypi_path.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(preflight),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                testpypi_install_report_path=testpypi_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:testpypi_install", failures)

    def test_testpypi_install_report_requires_current_versions(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            testpypi_path = Path(tmpdir) / "testpypi-install.json"
            testpypi_path.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(
                            preflight,
                            version_overrides={"wechat-desktop-tool": "0.0.1"},
                        ),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                testpypi_install_report_path=testpypi_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:testpypi_install", failures)

    def test_testpypi_install_report_requires_clean_install_policy(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            testpypi_path = Path(tmpdir) / "testpypi-install.json"
            testpypi_path.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(
                            force_reinstall=False
                        ),
                        "packages": _testpypi_packages(preflight),
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                testpypi_install_report_path=testpypi_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:testpypi_install", failures)

    def test_trusted_publisher_report_supplies_external_proof(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            trusted_path = Path(tmpdir) / "trusted-publisher.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if key != "pypi_trusted_publisher"
                    }
                ),
                encoding="utf-8",
            )
            trusted_path.write_text(
                json.dumps(
                    {
                        "source": "pypi",
                        "projects": [
                            {
                                "name": name,
                                "trustedPublisher": True,
                                "publisher": preflight.EXPECTED_TRUSTED_PUBLISHER,
                            }
                            for name in preflight.PACKAGE_PROJECTS
                        ],
                    }
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                trusted_publisher_report_path=trusted_path,
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_cli_json_mode_returns_success_for_default_preflight(self) -> None:
        preflight = _load_preflight()
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = preflight.main(["--root", str(ROOT), "--json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(isinstance(payload, list))

    def test_wheel_dir_accepts_complete_built_artifacts(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(preflight, wheel_dir)

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])
        names = {result.name for result in results}
        self.assertIn("wheel:app-control-protocol", names)
        self.assertIn(
            "wheel-content:app-control-protocol:app_control_protocol/config.py",
            names,
        )
        self.assertIn(
            "wheel-content:app-control-protocol:app_control_protocol/models.py",
            names,
        )
        self.assertIn(
            "wheel-content:app-control-protocol:"
            "app_control_protocol/schemas/service-event.schema.json",
            names,
        )
        self.assertIn(
            "wheel-content:computer-use-macos:computer_use_macos/__main__.py",
            names,
        )
        self.assertIn(
            "wheel-content:computer-use-macos:computer_use_macos/service.py",
            names,
        )
        self.assertIn(
            "wheel-content:computer-use-macos:"
            "computer_use_macos/helper/transport.py",
            names,
        )
        self.assertIn(
            "wheel-content:computer-use-macos:computer_use_macos/helper/template.py",
            names,
        )
        self.assertIn(
            "wheel-content:computer-use-macos:computer_use_macos/transport.py",
            names,
        )
        self.assertIn(
            "wheel-content:computer-use-macos:"
            "computer_use_macos/examples/textedit_smoke.py",
            names,
        )
        self.assertIn(
            "wheel-content:wechat-desktop-tool:wechat_desktop_tool/__main__.py",
            names,
        )
        self.assertIn(
            "wheel-content:wechat-desktop-tool:wechat_desktop_tool/tool.py",
            names,
        )
        self.assertIn(
            "wheel-content:wechat-desktop-tool:wechat_desktop_tool/models.py",
            names,
        )
        self.assertIn(
            "wheel-content:wechat-desktop-tool:wechat_desktop_tool/recipes.py",
            names,
        )
        self.assertIn(
            "wheel-content:wechat-desktop-tool:"
            "wechat_desktop_tool/examples/wechat_smoke.py",
            names,
        )
        self.assertIn("wheel-entry-point:computer-use-macos", names)
        self.assertIn("wheel-metadata-deps:computer-use-macos", names)

    def test_wheel_dir_reports_missing_protocol_schema(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                omitted_content={
                    "app-control-protocol": {
                        "app_control_protocol/schemas/service-event.schema.json"
                    }
                },
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "wheel-content:app-control-protocol:"
            "app_control_protocol/schemas/service-event.schema.json",
            failures,
        )

    def test_wheel_dir_reports_missing_protocol_config_module(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                omitted_content={
                    "app-control-protocol": {"app_control_protocol/config.py"}
                },
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "wheel-content:app-control-protocol:app_control_protocol/config.py",
            failures,
        )

    def test_wheel_dir_reports_missing_module_entrypoint(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                omitted_content={
                    "computer-use-macos": {"computer_use_macos/__main__.py"}
                },
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "wheel-content:computer-use-macos:computer_use_macos/__main__.py",
            failures,
        )

    def test_wheel_dir_reports_missing_computer_use_helper_transport(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                omitted_content={
                    "computer-use-macos": {
                        "computer_use_macos/helper/transport.py"
                    }
                },
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "wheel-content:computer-use-macos:"
            "computer_use_macos/helper/transport.py",
            failures,
        )

    def test_wheel_dir_reports_missing_runtime_dependency_metadata(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                dependency_overrides={"computer-use-macos": ()},
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("wheel-metadata-deps:computer-use-macos", failures)

    def test_wheel_dir_reports_missing_example_module(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                omitted_content={
                    "wechat-desktop-tool": {
                        "wechat_desktop_tool/examples/wechat_smoke.py"
                    }
                },
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "wheel-content:wechat-desktop-tool:"
            "wechat_desktop_tool/examples/wechat_smoke.py",
            failures,
        )

    def test_wheel_dir_reports_missing_wechat_tool_module(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            wheel_dir = Path(tmpdir) / "dist"
            wheel_dir.mkdir()
            _write_fake_wheel_set(
                preflight,
                wheel_dir,
                omitted_content={
                    "wechat-desktop-tool": {"wechat_desktop_tool/tool.py"}
                },
            )

            results = preflight.run_preflight(ROOT, wheel_dir=wheel_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "wheel-content:wechat-desktop-tool:wechat_desktop_tool/tool.py",
            failures,
        )

    def test_sdist_dir_accepts_complete_built_artifacts(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            sdist_dir = Path(tmpdir) / "dist"
            sdist_dir.mkdir()
            _write_fake_sdist_set(preflight, sdist_dir)

            results = preflight.run_preflight(ROOT, sdist_dir=sdist_dir)

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])
        names = {result.name for result in results}
        self.assertIn("sdist:app-control-protocol", names)
        self.assertIn(
            "sdist-content:app-control-protocol:"
            "src/app_control_protocol/config.py",
            names,
        )
        self.assertIn(
            "sdist-content:app-control-protocol:"
            "src/app_control_protocol/models.py",
            names,
        )
        self.assertIn(
            "sdist-content:app-control-protocol:"
            "src/app_control_protocol/schemas/service-event.schema.json",
            names,
        )
        self.assertIn(
            "sdist-content:computer-use-macos:"
            "src/computer_use_macos/helper/template.py",
            names,
        )
        self.assertIn(
            "sdist-content:computer-use-macos:"
            "src/computer_use_macos/service.py",
            names,
        )
        self.assertIn(
            "sdist-content:computer-use-macos:"
            "src/computer_use_macos/helper/transport.py",
            names,
        )
        self.assertIn(
            "sdist-content:wechat-desktop-tool:"
            "src/wechat_desktop_tool/examples/wechat_smoke.py",
            names,
        )
        self.assertIn(
            "sdist-content:wechat-desktop-tool:"
            "src/wechat_desktop_tool/tool.py",
            names,
        )
        self.assertIn(
            "sdist-content:wechat-desktop-tool:"
            "src/wechat_desktop_tool/models.py",
            names,
        )
        self.assertIn("sdist-metadata-deps:computer-use-macos", names)

    def test_sdist_dir_reports_missing_protocol_schema(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            sdist_dir = Path(tmpdir) / "dist"
            sdist_dir.mkdir()
            _write_fake_sdist_set(
                preflight,
                sdist_dir,
                omitted_content={
                    "app-control-protocol": {
                        "src/app_control_protocol/schemas/service-event.schema.json"
                    }
                },
            )

            results = preflight.run_preflight(ROOT, sdist_dir=sdist_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "sdist-content:app-control-protocol:"
            "src/app_control_protocol/schemas/service-event.schema.json",
            failures,
        )

    def test_sdist_dir_reports_missing_protocol_models_module(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            sdist_dir = Path(tmpdir) / "dist"
            sdist_dir.mkdir()
            _write_fake_sdist_set(
                preflight,
                sdist_dir,
                omitted_content={
                    "app-control-protocol": {"src/app_control_protocol/models.py"}
                },
            )

            results = preflight.run_preflight(ROOT, sdist_dir=sdist_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "sdist-content:app-control-protocol:"
            "src/app_control_protocol/models.py",
            failures,
        )

    def test_sdist_dir_reports_missing_computer_use_service_module(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            sdist_dir = Path(tmpdir) / "dist"
            sdist_dir.mkdir()
            _write_fake_sdist_set(
                preflight,
                sdist_dir,
                omitted_content={
                    "computer-use-macos": {
                        "src/computer_use_macos/service.py"
                    }
                },
            )

            results = preflight.run_preflight(ROOT, sdist_dir=sdist_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "sdist-content:computer-use-macos:"
            "src/computer_use_macos/service.py",
            failures,
        )

    def test_sdist_dir_reports_missing_wechat_tool_module(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            sdist_dir = Path(tmpdir) / "dist"
            sdist_dir.mkdir()
            _write_fake_sdist_set(
                preflight,
                sdist_dir,
                omitted_content={
                    "wechat-desktop-tool": {"src/wechat_desktop_tool/tool.py"}
                },
            )

            results = preflight.run_preflight(ROOT, sdist_dir=sdist_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn(
            "sdist-content:wechat-desktop-tool:src/wechat_desktop_tool/tool.py",
            failures,
        )

    def test_sdist_dir_reports_missing_runtime_dependency_metadata(self) -> None:
        preflight = _load_preflight()

        with TemporaryDirectory() as tmpdir:
            sdist_dir = Path(tmpdir) / "dist"
            sdist_dir.mkdir()
            _write_fake_sdist_set(
                preflight,
                sdist_dir,
                dependency_overrides={"computer-use-macos": ()},
            )

            results = preflight.run_preflight(ROOT, sdist_dir=sdist_dir)

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("sdist-metadata-deps:computer-use-macos", failures)


class ReleaseTagCheckScriptTests(unittest.TestCase):
    def test_expected_release_tag_uses_shared_package_version(self) -> None:
        script = _load_release_tag_check_script()

        self.assertEqual(
            script.expected_release_tag({"a": "0.1.0", "b": "0.1.0"}),
            "v0.1.0",
        )
        with self.assertRaisesRegex(ValueError, "package versions do not match"):
            script.expected_release_tag({"a": "0.1.0", "b": "0.2.0"})

    def test_normalize_tag_accepts_git_ref(self) -> None:
        script = _load_release_tag_check_script()

        self.assertEqual(script.normalize_tag("refs/tags/v0.1.0"), "v0.1.0")
        self.assertEqual(script.normalize_tag(" v0.1.0 "), "v0.1.0")
        with self.assertRaisesRegex(ValueError, "GITHUB_REF_NAME"):
            script.normalize_tag("")

    def test_main_accepts_current_package_version(self) -> None:
        script = _load_release_tag_check_script()
        output = StringIO()

        with redirect_stdout(output):
            result = script.main(["--root", str(ROOT), "--tag", "v0.1.0"])

        self.assertEqual(result, 0)
        self.assertIn("release tag ok: v0.1.0", output.getvalue())

    def test_main_rejects_mismatched_tag(self) -> None:
        script = _load_release_tag_check_script()
        error = StringIO()

        with redirect_stderr(error):
            result = script.main(["--root", str(ROOT), "--tag", "v9.9.9"])

        self.assertEqual(result, 1)
        self.assertIn("release tag mismatch", error.getvalue())


class TestPyPIInstallReportTests(unittest.TestCase):
    def test_build_report_installs_and_imports_expected_packages(self) -> None:
        script = _load_testpypi_script()
        runner = FakeReportRunner()

        with TemporaryDirectory() as tmpdir:
            report = script.build_report(
                runner=runner,
                timeout=12.0,
                venv_dir=Path(tmpdir) / "venv",
            )

        self.assertEqual(report["source"], "testpypi")
        packages = report["packages"]
        self.assertIsInstance(packages, list)
        self.assertEqual(
            [package["name"] for package in packages],
            [package[0] for package in script.DEFAULT_PACKAGES],
        )
        self.assertTrue(all(package["installed"] for package in packages))
        self.assertTrue(all(package["imported"] for package in packages))
        self.assertTrue(all(package["apiSmoke"] for package in packages))
        self.assertTrue(all(package["version"] == "0.1.0" for package in packages))
        self.assertEqual(
            report["installPolicy"],
            _testpypi_install_policy(managed_virtualenv=False),
        )
        install_commands = [
            command
            for command in runner.calls
            if "-m" in command and "pip" in command
        ]
        self.assertEqual(len(install_commands), 3)
        self.assertTrue(
            all(
                "https://test.pypi.org/simple/" in command
                for command in install_commands
            )
        )
        self.assertTrue(
            all("--no-cache-dir" in command for command in install_commands)
        )
        self.assertTrue(
            all("--force-reinstall" in command for command in install_commands)
        )
        self.assertTrue(
            all(
                "--disable-pip-version-check" in command
                for command in install_commands
            )
        )
        self.assertTrue(all("--isolated" in command for command in install_commands))

    def test_migration_api_smoke_covers_helper_convenience_surface(self) -> None:
        script = _load_testpypi_script()
        snippet = script.PACKAGE_SMOKE_SNIPPETS["computer-use-macos"]

        for expected in (
            "HelperManifest",
            "HelperTransportClient",
            "ComputerUseClient.from_helper_manifest",
            "callable(helper.open_app)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, snippet)

    def test_protocol_api_smoke_covers_observer_surface(self) -> None:
        script = _load_testpypi_script()
        snippet = script.PACKAGE_SMOKE_SNIPPETS["app-control-protocol"]

        for expected in (
            "ToolObserver",
            "LoggingToolObserver",
            "build_logging_observer",
            "observer.on_event(event)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, snippet)

    def test_protocol_api_smoke_covers_client_protocols(self) -> None:
        script = _load_testpypi_script()
        snippet = script.PACKAGE_SMOKE_SNIPPETS["app-control-protocol"]

        for expected in (
            "AppControlClient",
            "StreamingAppControlClient",
            "client.run_command(command)",
            "streaming_client.run_stream(command)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, snippet)

    def test_protocol_api_smoke_covers_helper_schemas(self) -> None:
        script = _load_testpypi_script()
        snippet = script.PACKAGE_SMOKE_SNIPPETS["app-control-protocol"]

        for expected in (
            "HELPER_REQUEST_SCHEMA",
            "HELPER_RESPONSE_SCHEMA",
            "validate_protocol_payload('helper_request'",
            "validate_protocol_payload('helper_response'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, snippet)

    def test_build_report_marks_failed_install(self) -> None:
        script = _load_testpypi_script()
        runner = FakeReportRunner(fail_package="computer-use-macos")

        with TemporaryDirectory() as tmpdir:
            report = script.build_report(
                runner=runner,
                venv_dir=Path(tmpdir) / "venv",
            )

        packages = report["packages"]
        self.assertIsInstance(packages, list)
        failed = [
            package for package in packages if package["name"] == "computer-use-macos"
        ][0]
        self.assertEqual(failed["installed"], False)
        self.assertEqual(failed["imported"], False)
        self.assertEqual(failed["apiSmoke"], False)

    def test_build_report_marks_failed_api_smoke(self) -> None:
        script = _load_testpypi_script()
        runner = FakeReportRunner(fail_api_smoke_package="wechat-desktop-tool")

        with TemporaryDirectory() as tmpdir:
            report = script.build_report(
                runner=runner,
                venv_dir=Path(tmpdir) / "venv",
            )

        packages = report["packages"]
        self.assertIsInstance(packages, list)
        failed = [
            package for package in packages if package["name"] == "wechat-desktop-tool"
        ][0]
        self.assertEqual(failed["installed"], True)
        self.assertEqual(failed["imported"], True)
        self.assertEqual(failed["apiSmoke"], False)

    def test_main_output_mode_reports_failed_packages(self) -> None:
        script = _load_testpypi_script()
        report = _testpypi_install_report_payload(
            script,
            failed_package="computer-use-macos",
        )
        original_build_report = script.build_report
        try:
            script.build_report = lambda **_kwargs: report
            with TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "testpypi-install.json"
                error = StringIO()

                with redirect_stderr(error):
                    exit_code = script.main(["--output", str(output_path)])

                payload = json.loads(output_path.read_text(encoding="utf-8"))
        finally:
            script.build_report = original_build_report

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["source"], "testpypi")
        self.assertIn(str(output_path), error.getvalue())
        self.assertIn("failed", error.getvalue())
        self.assertIn("computer-use-macos", error.getvalue())

    def test_main_output_mode_reports_success(self) -> None:
        script = _load_testpypi_script()
        report = _testpypi_install_report_payload(script)
        original_build_report = script.build_report
        try:
            script.build_report = lambda **_kwargs: report
            with TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "testpypi-install.json"
                error = StringIO()

                with redirect_stderr(error):
                    exit_code = script.main(["--output", str(output_path)])
        finally:
            script.build_report = original_build_report

        self.assertEqual(exit_code, 0)
        self.assertIn(str(output_path), error.getvalue())
        self.assertIn("passed", error.getvalue())
        self.assertNotIn("failed packages", error.getvalue())

    def test_computer_use_api_smoke_covers_all_public_command_builders(self) -> None:
        script = _load_testpypi_script()
        snippet = script.PACKAGE_SMOKE_SNIPPETS["computer-use-macos"]

        for builder in (
            "readiness_command",
            "observe_command",
            "open_app_command",
            "focus_app_command",
            "click_command",
            "click_accessibility_command",
            "click_coordinate_command",
            "type_text_command",
            "press_key_command",
            "hotkey_command",
            "wait_command",
        ):
            with self.subTest(builder=builder):
                self.assertIn(builder, snippet)
        self.assertIn("from computer_use_macos import observations, transport", snippet)
        self.assertIn("HelperManifest", snippet)
        self.assertIn("HelperTransportClient", snippet)
        self.assertIn("ComputerUseClient.from_helper_manifest", snippet)
        self.assertIn("callable(helper.open_app)", snippet)
        self.assertIn("from computer_use_macos.examples import textedit_smoke", snippet)
        self.assertIn("textedit_smoke.main", snippet)

    def test_wechat_api_smoke_covers_all_public_command_builders(self) -> None:
        script = _load_testpypi_script()
        snippet = script.PACKAGE_SMOKE_SNIPPETS["wechat-desktop-tool"]

        for builder in (
            "open_wechat_command",
            "focus_contact_command",
            "observe_current_chat_command",
            "read_visible_messages_command",
            "draft_message_command",
            "submit_draft_command",
            "send_message_command",
        ):
            with self.subTest(builder=builder):
                self.assertIn(builder, snippet)
        self.assertIn("from wechat_desktop_tool import adapter, observations, recipes", snippet)
        self.assertIn("from wechat_desktop_tool.examples import wechat_smoke", snippet)
        self.assertIn("wechat_smoke.main", snippet)


class TrustedPublisherReportTests(unittest.TestCase):
    def test_build_report_marks_all_expected_projects_configured(self) -> None:
        script = _load_trusted_publisher_script()

        report = script.build_report(
            all_configured=True,
            generated_at="2026-06-28T00:00:00Z",
        )

        self.assertEqual(report["source"], "pypi")
        self.assertEqual(report["verification"], "manual")
        projects = report["projects"]
        self.assertIsInstance(projects, list)
        self.assertEqual(
            [project["name"] for project in projects],
            list(script.EXPECTED_PROJECTS),
        )
        self.assertTrue(
            all(project["trustedPublisher"] is True for project in projects)
        )
        for project in projects:
            publisher = project["publisher"]
            self.assertEqual(publisher["owner"], "zhanghao1903")
            self.assertEqual(publisher["repository"], "macos-computer-use")
            self.assertEqual(publisher["workflow"], "release.yml")

    def test_generated_report_supplies_trusted_publisher_external_proof(self) -> None:
        preflight = _load_preflight()
        script = _load_trusted_publisher_script()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            trusted_path = Path(tmpdir) / "trusted-publisher.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if key != "pypi_trusted_publisher"
                    }
                ),
                encoding="utf-8",
            )
            trusted_path.write_text(
                json.dumps(
                    script.build_report(
                        all_configured=True,
                        generated_at="2026-06-28T00:00:00Z",
                    )
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                trusted_publisher_report_path=trusted_path,
                require_external=True,
            )

        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_partial_report_does_not_supply_external_proof(self) -> None:
        preflight = _load_preflight()
        script = _load_trusted_publisher_script()

        with TemporaryDirectory() as tmpdir:
            trusted_path = Path(tmpdir) / "trusted-publisher.json"
            trusted_path.write_text(
                json.dumps(
                    script.build_report(
                        configured_projects=("app-control-protocol",),
                        generated_at="2026-06-28T00:00:00Z",
                    )
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                trusted_publisher_report_path=trusted_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:pypi_trusted_publisher", failures)

    def test_wrong_trusted_publisher_workflow_does_not_supply_external_proof(
        self,
    ) -> None:
        preflight = _load_preflight()
        script = _load_trusted_publisher_script()

        with TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "proof.json"
            trusted_path = Path(tmpdir) / "trusted-publisher.json"
            proof_path.write_text(
                json.dumps(
                    {
                        key: True
                        for key in preflight.EXTERNAL_PROOFS
                        if key != "pypi_trusted_publisher"
                    }
                ),
                encoding="utf-8",
            )
            trusted_path.write_text(
                json.dumps(
                    script.build_report(
                        all_configured=True,
                        workflow="wrong-release.yml",
                        generated_at="2026-06-28T00:00:00Z",
                    )
                ),
                encoding="utf-8",
            )

            results = preflight.run_preflight(
                ROOT,
                proof_path=proof_path,
                trusted_publisher_report_path=trusted_path,
                require_external=True,
            )

        failures = [result.name for result in results if result.status == "fail"]
        self.assertIn("external-proof:pypi_trusted_publisher", failures)

    def test_main_output_mode_reports_partial_configuration(self) -> None:
        script = _load_trusted_publisher_script()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "trusted-publisher.json"
            error = StringIO()

            with redirect_stderr(error):
                exit_code = script.main(
                    [
                        "--project",
                        "app-control-protocol",
                        "--output",
                        str(output_path),
                    ]
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["source"], "pypi")
        self.assertIn(str(output_path), error.getvalue())
        self.assertIn("failed", error.getvalue())
        self.assertIn("computer-use-macos", error.getvalue())
        self.assertIn("wechat-desktop-tool", error.getvalue())

    def test_main_output_mode_reports_all_configured_success(self) -> None:
        script = _load_trusted_publisher_script()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "trusted-publisher.json"
            error = StringIO()

            with redirect_stderr(error):
                exit_code = script.main(
                    ["--all-configured", "--output", str(output_path)]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn(str(output_path), error.getvalue())
        self.assertIn("passed", error.getvalue())
        self.assertNotIn("unconfigured or mismatched", error.getvalue())


class WheelCheckScriptTests(unittest.TestCase):
    def test_builds_all_wheels_then_runs_preflight_and_install_smoke(self) -> None:
        script = _load_wheel_check_script()
        calls: list[tuple[tuple[str, ...], Path]] = []
        original_run = script.subprocess.run
        original_env_builder = script.venv.EnvBuilder

        class FakeEnvBuilder:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs

            def create(self, venv_dir: Path) -> None:
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True)
                executable = bin_dir / (
                    "python.exe" if sys.platform == "win32" else "python"
                )
                executable.write_text("", encoding="utf-8")

        def fake_run(
            command: tuple[str, ...],
            *,
            cwd: Path,
            check: bool,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[object]:
            self.assertFalse(check)
            if env is not None:
                self.assertNotIn("PYTHONPATH", env)
            calls.append((tuple(command), cwd))
            return subprocess.CompletedProcess(command, 0)

        script.subprocess.run = fake_run
        script.venv.EnvBuilder = FakeEnvBuilder
        try:
            with TemporaryDirectory() as tmpdir:
                wheel_dir = Path(tmpdir) / "wheels"
                result = script.run_wheel_check(ROOT, wheel_dir)
        finally:
            script.subprocess.run = original_run
            script.venv.EnvBuilder = original_env_builder

        self.assertEqual(result, 0)
        package_count = len(script.PACKAGE_PATHS)
        self.assertEqual(len(calls), package_count + 1 + 1 + len(script.DEFAULT_PACKAGES) * 2)
        for call, cwd in calls[:package_count]:
            self.assertEqual(cwd, ROOT)
            self.assertEqual(call[1:5], ("-m", "pip", "wheel", "--no-build-isolation"))
            self.assertIn("--no-deps", call)
        self.assertEqual(calls[package_count][1], ROOT)
        self.assertEqual(
            calls[package_count][0][1:3],
            ("scripts/release_preflight.py", "--wheel-dir"),
        )
        install_call, install_cwd = calls[package_count + 1]
        self.assertEqual(install_cwd, wheel_dir)
        self.assertIn("--no-index", install_call)
        self.assertIn("--find-links", install_call)
        self.assertIn(str(wheel_dir), install_call)
        self.assertEqual(
            set(install_call[-len(script.DEFAULT_PACKAGES):]),
            {package_name for package_name, _ in script.DEFAULT_PACKAGES},
        )
        smoke_calls = calls[package_count + 2:]
        self.assertEqual(len(smoke_calls), len(script.DEFAULT_PACKAGES) * 2)
        self.assertTrue(
            all(cwd == wheel_dir for _call, cwd in smoke_calls)
        )


class ReleaseProofBundleTests(unittest.TestCase):
    def test_bundle_writes_release_assets_that_satisfy_strict_preflight(self) -> None:
        preflight = _load_preflight()
        bundle = _load_release_proof_bundle_script()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            helper = root / "helper-doctor-source.json"
            textedit = root / "textedit-source.json"
            focus = root / "focus-source.json"
            submit = root / "submit-source.json"
            testpypi = root / "testpypi-source.json"
            trusted = root / "trusted-source.json"
            output = root / "release-proof"
            helper.write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "checks": _helper_release_checks(),
                    }
                ),
                encoding="utf-8",
            )
            textedit.write_text(
                json.dumps(_textedit_smoke_report()),
                encoding="utf-8",
            )
            focus.write_text(
                json.dumps(
                    {
                        "submitted": False,
                        "focus": _wechat_observation(
                            command_id="cmd_focus",
                            operation="focus_contact",
                            observation={"focusedContact": "File Transfer"},
                        ),
                        "draft": _wechat_observation(
                            command_id="cmd_draft",
                            operation="draft_message",
                            observation={"draftReady": True},
                        ),
                    }
                ),
                encoding="utf-8",
            )
            submit.write_text(
                json.dumps(
                    {
                        "result": {
                            "schema": "app_control.observation.v1",
                            "commandId": "cmd",
                            "tool": "wechat.desktop",
                            "operation": "send_message",
                            "status": "ok",
                            "success": True,
                            "summary": "sent",
                            "observation": {"submitted": True},
                        }
                    }
                ),
                encoding="utf-8",
            )
            testpypi.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(preflight),
                    }
                ),
                encoding="utf-8",
            )
            trusted.write_text(
                json.dumps(
                    {
                        "source": "pypi",
                        "projects": [
                            {
                                "name": name,
                                "trustedPublisher": True,
                                "publisher": preflight.EXPECTED_TRUSTED_PUBLISHER,
                            }
                            for name in preflight.PACKAGE_PROJECTS
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = bundle.build_bundle(
                output_dir=output,
                helper_doctor_report=helper,
                textedit_smoke_report=textedit,
                wechat_focus_draft_report=focus,
                wechat_submit_report=submit,
                testpypi_install_report=testpypi,
                trusted_publisher_report=trusted,
            )
            results = preflight.run_preflight(
                ROOT,
                proof_path=output / "release-proof.json",
                helper_doctor_report_path=output / "helper-doctor.json",
                textedit_smoke_report_path=output / "textedit-smoke.json",
                wechat_smoke_report_paths=(
                    output / "wechat-focus-draft-smoke.json",
                    output / "wechat-submit-smoke.json",
                ),
                testpypi_install_report_path=output / "testpypi-install.json",
                trusted_publisher_report_path=output / "trusted-publisher.json",
                require_external=True,
            )

        self.assertEqual(report["passed"], True)
        self.assertEqual(report["missingProofs"], [])
        failures = [result for result in results if result.status == "fail"]
        self.assertEqual(failures, [])

    def test_bundle_reports_missing_external_proofs(self) -> None:
        preflight = _load_preflight()
        bundle = _load_release_proof_bundle_script()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            helper = root / "helper-doctor-source.json"
            textedit = root / "textedit-source.json"
            focus = root / "focus-source.json"
            submit = root / "submit-source.json"
            testpypi = root / "testpypi-source.json"
            trusted = root / "trusted-source.json"
            output = root / "release-proof"
            helper.write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "checks": _helper_release_checks(),
                    }
                ),
                encoding="utf-8",
            )
            textedit.write_text(
                json.dumps(_textedit_smoke_report()),
                encoding="utf-8",
            )
            focus.write_text(
                json.dumps(
                    {
                        "submitted": False,
                        "focus": _wechat_observation(
                            command_id="cmd_focus",
                            operation="focus_contact",
                            observation={"focusedContact": "File Transfer"},
                        ),
                        "draft": _wechat_observation(
                            command_id="cmd_draft",
                            operation="draft_message",
                            observation={"draftReady": True},
                        ),
                    }
                ),
                encoding="utf-8",
            )
            submit.write_text(
                json.dumps(
                    {
                        "result": {
                            "schema": "app_control.observation.v1",
                            "commandId": "cmd",
                            "tool": "wechat.desktop",
                            "operation": "send_message",
                            "status": "ok",
                            "success": True,
                            "summary": "sent",
                            "observation": {"submitted": True},
                        }
                    }
                ),
                encoding="utf-8",
            )
            testpypi.write_text(
                json.dumps(
                    {
                        "source": "testpypi",
                        "indexUrl": "https://test.pypi.org/simple/",
                        "installPolicy": _testpypi_install_policy(),
                        "packages": _testpypi_packages(preflight),
                    }
                ),
                encoding="utf-8",
            )
            trusted.write_text(
                json.dumps(
                    {
                        "source": "pypi",
                        "projects": [
                            {
                                "name": name,
                                "trustedPublisher": name != "wechat-desktop-tool",
                                "publisher": preflight.EXPECTED_TRUSTED_PUBLISHER,
                            }
                            for name in preflight.PACKAGE_PROJECTS
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = bundle.build_bundle(
                output_dir=output,
                helper_doctor_report=helper,
                textedit_smoke_report=textedit,
                wechat_focus_draft_report=focus,
                wechat_submit_report=submit,
                testpypi_install_report=testpypi,
                trusted_publisher_report=trusted,
            )

        self.assertEqual(report["passed"], False)
        self.assertEqual(report["missingProofs"], ["pypi_trusted_publisher"])
        proof = report["proof"]
        self.assertIsInstance(proof, dict)
        self.assertEqual(proof["pypi_trusted_publisher"], False)

    def test_main_rejects_incomplete_bundle_without_allow_incomplete(self) -> None:
        preflight = _load_preflight()
        bundle = _load_release_proof_bundle_script()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = _write_release_proof_bundle_sources(
                preflight,
                root,
                trusted_all=False,
            )
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = bundle.main(_release_proof_bundle_args(paths))

            report = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertEqual(report["passed"], False)
        self.assertEqual(report["missingProofs"], ["pypi_trusted_publisher"])

    def test_main_allows_incomplete_bundle_for_diagnostics(self) -> None:
        preflight = _load_preflight()
        bundle = _load_release_proof_bundle_script()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = _write_release_proof_bundle_sources(
                preflight,
                root,
                trusted_all=False,
            )
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = bundle.main(
                    [*_release_proof_bundle_args(paths), "--allow-incomplete"]
                )

            report = json.loads(stdout.getvalue())
            output = Path(report["outputDir"])
            release_proof_exists = (output / "release-proof.json").exists()
            trusted_report_exists = (output / "trusted-publisher.json").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["passed"], False)
        self.assertEqual(report["missingProofs"], ["pypi_trusted_publisher"])
        self.assertTrue(release_proof_exists)
        self.assertTrue(trusted_report_exists)


class FakeReportRunner:
    def __init__(
        self,
        *,
        fail_package: str | None = None,
        fail_api_smoke_package: str | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_package = fail_package
        self.fail_api_smoke_package = fail_api_smoke_package

    def run(
        self,
        args: list[str] | tuple[str, ...],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        command = tuple(args)
        self.calls.append(command)
        if "install" in command:
            package = command[-1]
            if package == self.fail_package:
                return subprocess.CompletedProcess(command, 1, "", "install failed")
            return subprocess.CompletedProcess(command, 0, "installed", "")
        if "-c" in command:
            script = command[command.index("-c") + 1]
            if (
                self.fail_api_smoke_package is not None
                and "api-smoke-ok" in script
                and self._script_matches_package(script, self.fail_api_smoke_package)
            ):
                return subprocess.CompletedProcess(command, 1, "", "api smoke failed")
            return subprocess.CompletedProcess(command, 0, "0.1.0\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    def _script_matches_package(self, script: str, package_name: str) -> bool:
        return package_name.replace("-", "_") in script.replace("-", "_")


def _load_preflight() -> Any:
    path = ROOT / "scripts" / "release_preflight.py"
    spec = importlib.util.spec_from_file_location("release_preflight", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_testpypi_script() -> Any:
    path = ROOT / "scripts" / "testpypi_install_report.py"
    spec = importlib.util.spec_from_file_location("testpypi_install_report", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_release_tag_check_script() -> Any:
    path = ROOT / "scripts" / "release_tag_check.py"
    spec = importlib.util.spec_from_file_location("release_tag_check", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_trusted_publisher_script() -> Any:
    path = ROOT / "scripts" / "trusted_publisher_report.py"
    spec = importlib.util.spec_from_file_location("trusted_publisher_report", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_wheel_check_script() -> Any:
    path = ROOT / "scripts" / "wheel_check.py"
    spec = importlib.util.spec_from_file_location("wheel_check", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_release_proof_bundle_script() -> Any:
    path = ROOT / "scripts" / "release_proof_bundle.py"
    spec = importlib.util.spec_from_file_location("release_proof_bundle", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_fake_wheel_set(
    preflight: Any,
    wheel_dir: Path,
    *,
    omitted_content: dict[str, set[str]] | None = None,
    dependency_overrides: dict[str, tuple[str, ...]] | None = None,
) -> None:
    omitted = omitted_content or {}
    dependency_overrides = dependency_overrides or {}
    for project_name, content in preflight.EXPECTED_WHEEL_CONTENT.items():
        scripts = preflight.EXPECTED_SCRIPTS.get(project_name, {})
        _write_fake_wheel(
            wheel_dir,
            project_name=project_name,
            version="0.1.0",
            dependencies=dependency_overrides.get(
                project_name,
                preflight.EXPECTED_RUNTIME_DEPS[project_name],
            ),
            content=tuple(
                item
                for item in content
                if item not in omitted.get(project_name, set())
            ),
            scripts=scripts,
        )


def _write_fake_wheel(
    wheel_dir: Path,
    *,
    project_name: str,
    version: str,
    dependencies: tuple[str, ...],
    content: tuple[str, ...],
    scripts: dict[str, str],
) -> Path:
    import_name = project_name.replace("-", "_")
    wheel_path = wheel_dir / f"{import_name}-{version}-py3-none-any.whl"
    dist_info = f"{import_name}-{version}.dist-info"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(
            f"{dist_info}/METADATA",
            "\n".join(
                (
                    "Metadata-Version: 2.1",
                    f"Name: {project_name}",
                    f"Version: {version}",
                    *(f"Requires-Dist: {dependency}" for dependency in dependencies),
                    "",
                )
            ),
        )
        if scripts:
            wheel.writestr(
                f"{dist_info}/entry_points.txt",
                "[console_scripts]\n"
                + "\n".join(
                    f"{script} = {target}" for script, target in scripts.items()
                )
                + "\n",
            )
        for relative in content:
            wheel.writestr(relative, "")
    return wheel_path


def _write_fake_sdist_set(
    preflight: Any,
    sdist_dir: Path,
    *,
    omitted_content: dict[str, set[str]] | None = None,
    dependency_overrides: dict[str, tuple[str, ...]] | None = None,
) -> None:
    omitted = omitted_content or {}
    dependency_overrides = dependency_overrides or {}
    for project_name, content in preflight.EXPECTED_SDIST_CONTENT.items():
        _write_fake_sdist(
            sdist_dir,
            project_name=project_name,
            version="0.1.0",
            dependencies=dependency_overrides.get(
                project_name,
                preflight.EXPECTED_RUNTIME_DEPS[project_name],
            ),
            content=tuple(
                item
                for item in content
                if item not in omitted.get(project_name, set())
            ),
        )


def _write_fake_sdist(
    sdist_dir: Path,
    *,
    project_name: str,
    version: str,
    dependencies: tuple[str, ...],
    content: tuple[str, ...],
) -> Path:
    distribution_name = project_name.replace("-", "_")
    top_level = f"{distribution_name}-{version}"
    sdist_path = sdist_dir / f"{distribution_name}-{version}.tar.gz"
    with tarfile.open(sdist_path, "w:gz") as sdist:
        _write_tar_text(
            sdist,
            f"{top_level}/PKG-INFO",
            "\n".join(
                (
                    "Metadata-Version: 2.1",
                    f"Name: {project_name}",
                    f"Version: {version}",
                    *(f"Requires-Dist: {dependency}" for dependency in dependencies),
                    "",
                )
            ),
        )
        for relative in content:
            _write_tar_text(sdist, f"{top_level}/{relative}", "")
    return sdist_path


def _write_tar_text(sdist: tarfile.TarFile, name: str, content: str) -> None:
    payload = content.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    sdist.addfile(info, BytesIO(payload))


def _testpypi_packages(
    preflight: Any,
    *,
    package_names: tuple[str, ...] | None = None,
    api_smoke_overrides: dict[str, bool] | None = None,
    version_overrides: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    names = package_names or tuple(preflight.PACKAGE_PROJECTS)
    api_smoke = api_smoke_overrides or {}
    versions = version_overrides or {}
    packages: list[dict[str, object]] = []
    for name in names:
        project = preflight._project_table(ROOT / preflight.PACKAGE_PROJECTS[name])
        packages.append(
            {
                "name": name,
                "installed": True,
                "imported": True,
                "apiSmoke": api_smoke.get(name, True),
                "version": versions.get(name, project["version"]),
            }
        )
    return packages


def _testpypi_install_report_payload(
    script: Any,
    *,
    failed_package: str | None = None,
) -> dict[str, object]:
    packages: list[dict[str, object]] = []
    for name, import_name in script.DEFAULT_PACKAGES:
        failed = name == failed_package
        packages.append(
            {
                "name": name,
                "importName": import_name,
                "installed": not failed,
                "imported": not failed,
                "apiSmoke": not failed,
                "version": None if failed else "0.1.0",
            }
        )
    return {
        "source": "testpypi",
        "indexUrl": script.TESTPYPI_INDEX_URL,
        "installPolicy": dict(script.TESTPYPI_INSTALL_POLICY),
        "packages": packages,
    }


def _write_release_proof_bundle_sources(
    preflight: Any,
    root: Path,
    *,
    trusted_all: bool,
) -> dict[str, Path]:
    paths = {
        "output": root / "release-proof",
        "helper": root / "helper-doctor-source.json",
        "textedit": root / "textedit-source.json",
        "focus": root / "focus-source.json",
        "submit": root / "submit-source.json",
        "testpypi": root / "testpypi-source.json",
        "trusted": root / "trusted-source.json",
    }
    paths["helper"].write_text(
        json.dumps(
            {
                "status": "ready",
                "checks": _helper_release_checks(),
            }
        ),
        encoding="utf-8",
    )
    paths["textedit"].write_text(
        json.dumps(_textedit_smoke_report()),
        encoding="utf-8",
    )
    paths["focus"].write_text(
        json.dumps(
            {
                "submitted": False,
                "focus": _wechat_observation(
                    command_id="cmd_focus",
                    operation="focus_contact",
                    observation={"focusedContact": "File Transfer"},
                ),
                "draft": _wechat_observation(
                    command_id="cmd_draft",
                    operation="draft_message",
                    observation={"draftReady": True},
                ),
            }
        ),
        encoding="utf-8",
    )
    paths["submit"].write_text(
        json.dumps(
            {
                "result": {
                    "schema": "app_control.observation.v1",
                    "commandId": "cmd",
                    "tool": "wechat.desktop",
                    "operation": "send_message",
                    "status": "ok",
                    "success": True,
                    "summary": "sent",
                    "observation": {"submitted": True},
                }
            }
        ),
        encoding="utf-8",
    )
    paths["testpypi"].write_text(
        json.dumps(
            {
                "source": "testpypi",
                "indexUrl": "https://test.pypi.org/simple/",
                "installPolicy": _testpypi_install_policy(),
                "packages": _testpypi_packages(preflight),
            }
        ),
        encoding="utf-8",
    )
    paths["trusted"].write_text(
        json.dumps(
            {
                "source": "pypi",
                "projects": [
                    {
                        "name": name,
                        "trustedPublisher": trusted_all,
                        "publisher": preflight.EXPECTED_TRUSTED_PUBLISHER,
                    }
                    for name in preflight.PACKAGE_PROJECTS
                ],
            }
        ),
        encoding="utf-8",
    )
    return paths


def _release_proof_bundle_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--output-dir",
        str(paths["output"]),
        "--helper-doctor-report",
        str(paths["helper"]),
        "--textedit-smoke-report",
        str(paths["textedit"]),
        "--wechat-focus-draft-report",
        str(paths["focus"]),
        "--wechat-submit-report",
        str(paths["submit"]),
        "--testpypi-install-report",
        str(paths["testpypi"]),
        "--trusted-publisher-report",
        str(paths["trusted"]),
    ]


def _testpypi_install_policy(
    *,
    managed_virtualenv: bool = True,
    index_only: bool = True,
    no_cache: bool = True,
    force_reinstall: bool = True,
) -> dict[str, bool]:
    return {
        "managedVirtualenv": managed_virtualenv,
        "isolated": True,
        "indexOnly": index_only,
        "noCache": no_cache,
        "forceReinstall": force_reinstall,
    }


def _helper_release_checks() -> list[dict[str, str]]:
    return [
        {"name": "manifest", "status": "ok"},
        {"name": "identity", "status": "ok"},
        {"name": "endpoint", "status": "ok"},
        {"name": "token", "status": "ok"},
        {"name": "helper_app", "status": "ok"},
        {"name": "signature", "status": "ok"},
        {"name": "notarization", "status": "ok"},
    ]


def _textedit_smoke_report() -> dict[str, Any]:
    return {
        "dryRun": False,
        "success": True,
        "app": "TextEdit",
        "configPath": None,
        "observations": [
            _macos_observation(
                command_id="cmd_textedit_readiness",
                operation="readiness",
                observation={"status": "ready"},
            ),
            _macos_observation(
                command_id="cmd_textedit_open",
                operation="open_app",
                observation={"app": "TextEdit"},
            ),
            _macos_observation(
                command_id="cmd_textedit_focus",
                operation="focus_app",
                observation={"app": "TextEdit"},
            ),
            _macos_observation(
                command_id="cmd_textedit_observe",
                operation="observe",
                observation={"frontmostApp": "TextEdit"},
            ),
            _macos_observation(
                command_id="cmd_textedit_type",
                operation="type_text",
                observation={"submitted": False, "typedChars": 5},
            ),
        ],
    }


def _macos_observation(
    *,
    command_id: str,
    operation: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "app_control.observation.v1",
        "commandId": command_id,
        "tool": "macos.computer_use",
        "operation": operation,
        "status": "ok",
        "success": True,
        "summary": f"{operation} ok",
        "observation": observation,
    }


def _wechat_observation(
    *,
    command_id: str,
    operation: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "app_control.observation.v1",
        "commandId": command_id,
        "tool": "wechat.desktop",
        "operation": operation,
        "status": "ok",
        "success": True,
        "summary": f"{operation} ok",
        "observation": observation,
    }


if __name__ == "__main__":
    unittest.main()
