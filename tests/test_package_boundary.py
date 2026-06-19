from __future__ import annotations

from pathlib import Path
import tomllib
import unittest


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
)


class PackageBoundaryTests(unittest.TestCase):
    def test_source_has_no_plato_or_llm_dependency_imports(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for term in BANNED_TERMS:
                with self.subTest(path=path, term=term):
                    self.assertNotIn(term, text)

    def test_project_dependencies_are_empty_for_runtime(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

        self.assertNotIn("dependencies", project)

    def test_py_typed_is_declared(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())

        package_data = project["tool"]["setuptools"]["package-data"]
        self.assertIn("py.typed", package_data["macos_computer_use"])


if __name__ == "__main__":
    unittest.main()
