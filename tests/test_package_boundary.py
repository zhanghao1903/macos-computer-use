from __future__ import annotations

from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PROJECTS = {
    "app-control-protocol": ROOT / "packages/app-control-protocol/pyproject.toml",
    "computer-use-macos": ROOT / "packages/computer-use-macos/pyproject.toml",
    "wechat-desktop-tool": ROOT / "packages/wechat-desktop-tool/pyproject.toml",
}
PACKAGE_IMPORTS = {
    "app-control-protocol": "app_control_protocol",
    "computer-use-macos": "computer_use_macos",
    "wechat-desktop-tool": "wechat_desktop_tool",
}
BANNED_TERMS = (
    "taskweavn",
    "from plato",
    "import plato",
    "openai",
    "anthropic",
    "langchain",
    "ui_tars",
    "uitars",
)
ALLOWED_WECHAT_SELECTOR_IMPORT = (
    ROOT
    / "packages"
    / "wechat-desktop-tool"
    / "src"
    / "wechat_desktop_tool"
    / "profiles.py"
)


class PackageBoundaryTests(unittest.TestCase):
    def test_root_no_longer_declares_a_python_distribution(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertNotIn("project", project)
        self.assertFalse((ROOT / "src" / "macos_computer_use").exists())
        self.assertFalse((ROOT / "MANIFEST.in").exists())

    def test_three_package_suite_declares_expected_projects(self) -> None:
        self.assertEqual(
            set(PACKAGE_PROJECTS),
            {"app-control-protocol", "computer-use-macos", "wechat-desktop-tool"},
        )
        for expected_name, pyproject_path in PACKAGE_PROJECTS.items():
            with self.subTest(project=expected_name):
                project = tomllib.loads(
                    pyproject_path.read_text(encoding="utf-8")
                )
                self.assertEqual(project["project"]["name"], expected_name)

    def test_runtime_dependencies_are_protocol_first(self) -> None:
        protocol = tomllib.loads(
            PACKAGE_PROJECTS["app-control-protocol"].read_text(encoding="utf-8")
        )
        computer_use = tomllib.loads(
            PACKAGE_PROJECTS["computer-use-macos"].read_text(encoding="utf-8")
        )
        wechat = tomllib.loads(
            PACKAGE_PROJECTS["wechat-desktop-tool"].read_text(encoding="utf-8")
        )

        self.assertNotIn("dependencies", protocol["project"])
        self.assertEqual(
            computer_use["project"]["dependencies"],
            ["app-control-protocol>=0.1.0"],
        )
        self.assertEqual(
            wechat["project"]["dependencies"],
            [
                "app-control-protocol>=0.1.0",
                "computer-use-macos>=0.1.1",
            ],
        )

    def test_py_typed_is_declared_for_all_packages(self) -> None:
        for project_name, pyproject_path in PACKAGE_PROJECTS.items():
            with self.subTest(project=project_name):
                project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
                package_data = project["tool"]["setuptools"]["package-data"]
                self.assertIn("py.typed", package_data[PACKAGE_IMPORTS[project_name]])

    def test_package_sources_have_no_product_or_llm_dependencies(self) -> None:
        for package_dir in (ROOT / "packages").iterdir():
            source_dir = package_dir / "src"
            if not source_dir.exists():
                continue
            for path in source_dir.rglob("*.py"):
                text = path.read_text(encoding="utf-8").lower()
                for term in BANNED_TERMS:
                    with self.subTest(path=path, term=term):
                        self.assertNotIn(term, text)

    def test_wechat_computer_use_imports_are_limited_to_selector_profiles(
        self,
    ) -> None:
        source_dir = (
            ROOT
            / "packages"
            / "wechat-desktop-tool"
            / "src"
            / "wechat_desktop_tool"
        )

        for path in source_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "computer_use_macos" not in text:
                continue
            with self.subTest(path=path):
                self.assertEqual(path, ALLOWED_WECHAT_SELECTOR_IMPORT)
                self.assertIn("computer_use_macos.selectors", text)


if __name__ == "__main__":
    unittest.main()
