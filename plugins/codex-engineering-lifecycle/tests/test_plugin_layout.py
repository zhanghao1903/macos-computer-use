from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "codex-engineering-lifecycle"


class PluginLayoutTests(unittest.TestCase):
    def test_manifest_marketplace_and_assets_are_consistent(self) -> None:
        manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["name"], "codex-engineering-lifecycle")
        self.assertEqual(manifest["version"], "0.1.0")
        entry = next(
            item for item in marketplace["plugins"] if item["name"] == manifest["name"]
        )
        self.assertEqual(
            entry["source"]["path"], "./plugins/codex-engineering-lifecycle"
        )
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(all(len(item) <= 128 for item in prompts))
        for key in ("composerIcon", "logo", "logoDark"):
            path = PLUGIN_ROOT / manifest["interface"][key]
            self.assertTrue(path.is_file(), key)
            ET.parse(path)

    def test_user_policy_documents_and_runtime_files_exist(self) -> None:
        for name in (
            "README.md",
            "CHANGELOG.md",
            "PRIVACY.md",
            "TERMS.md",
            "SUPPORT.md",
            "LICENSE",
            "scripts/workflowctl.py",
            "scripts/validate_contracts.py",
        ):
            self.assertTrue((PLUGIN_ROOT / name).is_file(), name)

    def test_json_and_docs_have_no_scaffold_placeholders(self) -> None:
        todo_marker = "[" + "TODO:"
        scaffold_author = "Local " + "developer"
        for path in PLUGIN_ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            if path.suffix in {".json", ".md", ".yaml", ".py", ".svg"}:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(todo_marker, text, str(path))
                self.assertNotIn(scaffold_author, text, str(path))


if __name__ == "__main__":
    unittest.main()
