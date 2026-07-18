from __future__ import annotations

import json
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (PLUGIN_ROOT / relative).read_text(encoding="utf-8")

    def test_init_declares_required_task_capabilities_and_safe_defaults(self) -> None:
        text = self.read("skills/codex-workflow-init/SKILL.md")
        for capability in (
            "list_projects",
            "create_thread",
            "list_threads",
            "read_thread",
            "send_message_to_thread",
            "wait_threads",
            "set_thread_title",
            "set_thread_pinned",
            "set_thread_archived",
        ):
            self.assertIn(f"`{capability}`", text)
        self.assertIn("Default to `review-only`", text)
        self.assertIn("Do not create tasks unless the user explicitly invoked this skill", text)
        self.assertIn("entire final", text)
        self.assertIn("`NOT_MAIN_READY` fail", text)

    def test_main_and_reviewer_preserve_role_boundary_and_exact_head_gate(self) -> None:
        main = self.read("skills/codex-feature-main/SKILL.md")
        reviewer = self.read("skills/codex-pr-review-merge/SKILL.md")
        self.assertIn("send_message_to_thread", main)
        self.assertIn("prepare-review", main)
        self.assertIn("cancel-dispatch", main)
        self.assertRegex(main.lower(), r"never approve or\s+merge your own work")
        self.assertIn("never edit", reviewer.lower())
        self.assertIn("--match-head-commit", reviewer)
        self.assertIn("Never pass `--admin` or `--auto`", reviewer)
        self.assertIn("`STALE` result with merge status `NOT_ATTEMPTED`", reviewer)

    def test_only_main_role_is_implicitly_invocable(self) -> None:
        expected = {
            "codex-workflow-init": "false",
            "codex-feature-main": "true",
            "codex-pr-review-merge": "false",
        }
        for skill, value in expected.items():
            text = self.read(f"skills/{skill}/agents/openai.yaml")
            self.assertIn(f"allow_implicit_invocation: {value}", text)

    def test_manifest_is_wired_to_real_assets(self) -> None:
        manifest = json.loads(self.read(".codex-plugin/plugin.json"))
        self.assertEqual(manifest["name"], "codex-feature-lifecycle")
        self.assertEqual(manifest["skills"], "./skills/")
        for key in ("composerIcon", "logo"):
            asset = PLUGIN_ROOT / manifest["interface"][key]
            self.assertTrue(asset.is_file(), asset)

    def test_repository_marketplace_points_to_plugin(self) -> None:
        marketplace_path = PLUGIN_ROOT.parents[1] / ".agents" / "plugins" / "marketplace.json"
        if not marketplace_path.is_file():
            return  # Marketplace catalog is intentionally outside an installed plugin archive.
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        manifest = json.loads(self.read(".codex-plugin/plugin.json"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == manifest["name"])
        self.assertEqual(entry["source"]["path"], "./plugins/codex-feature-lifecycle")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")


if __name__ == "__main__":
    unittest.main()
