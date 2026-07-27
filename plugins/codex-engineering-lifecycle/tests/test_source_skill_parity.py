from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / ".agents" / "skills"
PACKAGED_ROOT = REPOSITORY_ROOT / "plugins" / "codex-engineering-lifecycle" / "skills"
SKILLS = (
    "feature-lifecycle",
    "product-workflow-gate",
    "technical-plan-write",
    "technical-plan-review",
    "pr-review",
)


class SourceSkillParityTests(unittest.TestCase):
    def test_runtime_resources_match_sources_except_agent_policy_overlay(self) -> None:
        for name in SKILLS:
            source = SOURCE_ROOT / name
            packaged = PACKAGED_ROOT / name
            source_files = {
                path.relative_to(source)
                for path in source.rglob("*")
                if path.is_file()
                and path.name != "README.md"
                and "tests" not in path.relative_to(source).parts
                and "__pycache__" not in path.relative_to(source).parts
                and path.relative_to(source) != Path("agents/openai.yaml")
            }
            packaged_files = {
                path.relative_to(packaged)
                for path in packaged.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.relative_to(packaged).parts
                and path.relative_to(packaged) != Path("agents/openai.yaml")
            }
            self.assertEqual(source_files, packaged_files, name)
            for relative in source_files:
                self.assertEqual(
                    (source / relative).read_bytes(),
                    (packaged / relative).read_bytes(),
                    f"{name}/{relative}",
                )

    def test_existing_agent_metadata_has_only_explicit_policy_appended(self) -> None:
        for name in (
            "feature-lifecycle",
            "technical-plan-write",
            "technical-plan-review",
        ):
            source = (SOURCE_ROOT / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            packaged = (PACKAGED_ROOT / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                packaged,
                source.rstrip() + "\n\npolicy:\n  allow_implicit_invocation: false\n",
            )

    def test_missing_source_metadata_uses_bounded_packaging_overlay(self) -> None:
        for name in ("product-workflow-gate", "pr-review"):
            self.assertFalse((SOURCE_ROOT / name / "agents" / "openai.yaml").exists())
            packaged = (PACKAGED_ROOT / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("interface:", packaged)
            self.assertIn(f"${name}", packaged)
            self.assertRegex(
                packaged,
                r"(?m)^policy:\n\s+allow_implicit_invocation:\s+false$",
            )


if __name__ == "__main__":
    unittest.main()
