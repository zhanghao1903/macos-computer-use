from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from wechat_desktop_tool import WECHAT_FAILURE_KINDS


ROOT = Path(__file__).resolve().parents[1]
BANNED_TERMS = (
    "taskweavn",
    "from plato",
    "import plato",
    "openai",
    "anthropic",
    "langchain",
    "ui_tars",
    "uitars",
    "computer_use_macos.client",
    "computer_use_macos.service",
    "computer_use_macos.cli",
)
ALLOWED_SELECTOR_PROFILE_IMPORT = ROOT / "src" / "wechat_desktop_tool" / "profiles.py"


class PackageBoundaryTests(unittest.TestCase):
    def test_source_has_no_product_llm_or_backend_imports(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for term in BANNED_TERMS:
                with self.subTest(path=path, term=term):
                    self.assertNotIn(term, text)

    def test_computer_use_imports_are_limited_to_selector_profiles(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "computer_use_macos" not in text:
                continue
            with self.subTest(path=path):
                self.assertEqual(path, ALLOWED_SELECTOR_PROFILE_IMPORT)
                self.assertIn("computer_use_macos.selectors", text)

    def test_project_depends_only_on_protocol_and_selector_packages(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

        self.assertEqual(
            project.get("dependencies"),
            [
                "app-control-protocol>=0.3.0",
                "computer-use-macos>=0.3.0",
            ],
        )

    def test_package_data_is_declared(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())

        package_data = project["tool"]["setuptools"]["package-data"]
        self.assertEqual(
            package_data["wechat_desktop_tool"],
            [
                "py.typed",
                "profiles/*.toml",
                "skills/wechat-use/*.json",
                "skills/wechat-use/*.md",
                "skills/wechat-use/agents/*.yaml",
                "skills/wechat-use/references/*.md",
            ],
        )

    def test_failure_kinds_are_declared_as_public_contract(self) -> None:
        failure_kinds = set(WECHAT_FAILURE_KINDS)
        self.assertTrue(failure_kinds)
        self.assertEqual(len(failure_kinds), len(WECHAT_FAILURE_KINDS))
        self.assertIn("contact_not_found", failure_kinds)
        self.assertIn("submit_unknown", failure_kinds)
        self.assertIn("wechat_query_truncated", failure_kinds)

        literal_kinds: set[str] = set()
        for relative in ("tool.py", "cli.py"):
            text = (ROOT / "src" / "wechat_desktop_tool" / relative).read_text(
                encoding="utf-8"
            )
            literal_kinds.update(re.findall(r'failure_kind="([^"]+)"', text))
            literal_kinds.update(
                re.findall(
                    r'_from_app_control_failure\(\s*command,\s*"([^"]+)"',
                    text,
                    re.S,
                )
            )

        self.assertLessEqual(literal_kinds, failure_kinds)


if __name__ == "__main__":
    unittest.main()
