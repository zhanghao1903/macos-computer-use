from __future__ import annotations

import ast
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
PACKAGE_SOURCE = ROOT / "src" / "wechat_desktop_tool"
PRIVATE_IMPLEMENTATION_MODULES = (
    "_action_operations.py",
    "_action_safety.py",
    "_collection_operations.py",
    "_contact_operations.py",
    "_contact_search.py",
    "_diagnostics.py",
    "_mapped_controls.py",
    "_message_operations.py",
    "_query_mapping.py",
    "_row_parsing.py",
    "_runtime.py",
    "_window_operations.py",
)
SPLIT_REGRESSION_TEST_MODULES = (
    "_tool_test_fixtures.py",
    "test_tool_action_regressions.py",
    "test_tool_cli.py",
    "test_tool_contact_regressions.py",
    "test_tool_examples.py",
    "test_tool_facade.py",
    "test_tool_message_regressions.py",
    "test_tool_window_collection_regressions.py",
)


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
        for path in PACKAGE_SOURCE.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            literal_kinds.update(re.findall(r'failure_kind="([^"]+)"', text))
            literal_kinds.update(
                re.findall(
                    r'_from_app_control_failure\(\s*command,\s*"([^"]+)"',
                    text,
                    re.S,
                )
            )

        self.assertLessEqual(literal_kinds, failure_kinds)

    def test_modularized_sources_stay_within_size_budgets(self) -> None:
        self.assertLess(_line_count(PACKAGE_SOURCE / "tool.py"), 1_000)
        for relative in PRIVATE_IMPLEMENTATION_MODULES:
            with self.subTest(relative=relative):
                self.assertLess(_line_count(PACKAGE_SOURCE / relative), 1_500)

    def test_split_regression_tests_stay_within_size_budgets(self) -> None:
        tests = ROOT / "tests"
        self.assertFalse((tests / "test_tool.py").exists())
        for relative in SPLIT_REGRESSION_TEST_MODULES:
            with self.subTest(relative=relative):
                self.assertLess(_line_count(tests / relative), 2_500)

    def test_private_module_dependency_graph_is_acyclic_and_has_no_facade_edge(
        self,
    ) -> None:
        module_names = {
            Path(relative).stem for relative in PRIVATE_IMPLEMENTATION_MODULES
        }
        graph: dict[str, set[str]] = {}
        for module_name in module_names:
            imports = _relative_imports(PACKAGE_SOURCE / f"{module_name}.py")
            with self.subTest(module=module_name):
                self.assertNotIn("tool", imports)
            graph[module_name] = imports & module_names

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(module_name: str) -> None:
            if module_name in visiting:
                self.fail(f"private module import cycle includes {module_name}")
            if module_name in visited:
                return
            visiting.add(module_name)
            for dependency in graph[module_name]:
                visit(dependency)
            visiting.remove(module_name)
            visited.add(module_name)

        for module_name in graph:
            visit(module_name)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _relative_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level > 0
        and isinstance(node.module, str)
    }


if __name__ == "__main__":
    unittest.main()
