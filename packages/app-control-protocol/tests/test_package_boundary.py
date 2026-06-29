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
    def test_source_has_no_product_or_llm_dependency_imports(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for term in BANNED_TERMS:
                with self.subTest(path=path, term=term):
                    self.assertNotIn(term, text)

    def test_project_has_no_runtime_dependencies(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

        self.assertNotIn("dependencies", project)

    def test_py_typed_is_declared(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())

        package_data = project["tool"]["setuptools"]["package-data"]
        self.assertIn("py.typed", package_data["app_control_protocol"])

    def test_readme_mentions_service_schema_assets(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for schema_file in (
            "service-request.schema.json",
            "service-response.schema.json",
            "service-event.schema.json",
        ):
            with self.subTest(schema_file=schema_file):
                self.assertIn(schema_file, readme)


if __name__ == "__main__":
    unittest.main()
