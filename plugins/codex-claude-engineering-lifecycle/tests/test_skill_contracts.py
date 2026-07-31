from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = PLUGIN_ROOT / "skills"
ROLE_SKILLS = {
    "hybrid-workflow-init",
    "hybrid-requirements",
    "hybrid-main",
}
COMPOSITION_SKILLS = {
    "feature-lifecycle",
    "product-workflow-gate",
    "technical-plan-write",
    "technical-plan-review",
    "pr-review",
}


class SkillContractTests(unittest.TestCase):
    def test_exact_skill_set_and_frontmatter_names(self) -> None:
        actual = {path.name for path in SKILLS.iterdir() if path.is_dir()}
        self.assertEqual(ROLE_SKILLS | COMPOSITION_SKILLS, actual)
        for name in actual:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertRegex(text, rf"(?m)^name:\s*{re.escape(name)}$")
            self.assertRegex(text, r"(?m)^description:\s*\S")
            self.assertNotIn("TODO", text)
            self.assertFalse((SKILLS / name / "README.md").exists())

    def test_composition_skills_are_explicit_only(self) -> None:
        for name in COMPOSITION_SKILLS:
            metadata = (SKILLS / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertRegex(
                metadata, r"(?m)^policy:\n\s+allow_implicit_invocation:\s+false$"
            )

    def test_role_invocation_policy(self) -> None:
        for name in ("hybrid-requirements", "hybrid-main"):
            metadata = (SKILLS / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("allow_implicit_invocation: false", metadata)
            self.assertIn(f"${name}", metadata)
        init = (
            SKILLS / "hybrid-workflow-init" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("$hybrid-workflow-init", init)
        self.assertIn("allow_implicit_invocation: false", init)

    def test_main_composes_source_skills_and_claude_review(self) -> None:
        main = (SKILLS / "hybrid-main" / "SKILL.md").read_text(encoding="utf-8")
        for name in (
            "feature-lifecycle",
            "product-workflow-gate",
            "technical-plan-write",
        ):
            self.assertIn(f"${name}", main)
        self.assertIn("plan-review", main)
        self.assertIn("code-review", main)
        self.assertIn("Claude Review", main)
        self.assertIn("never asks the Frontend session to review itself", main)

    def test_role_boundaries_and_goal_release_gates_are_documented(self) -> None:
        init = (SKILLS / "hybrid-workflow-init" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        requirements = (SKILLS / "hybrid-requirements" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        main = (SKILLS / "hybrid-main" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("two Codex tasks", init)
        self.assertIn("two durable", init)
        self.assertIn("begin-init", init)
        self.assertIn("record-init-task", init)
        self.assertIn("Claude probe", init)
        self.assertIn("Every one of the four IDs must be distinct", init)
        self.assertIn("Bootstrap has one narrow exception", requirements)
        self.assertIn('"type":"EngineeringRoleReady"', requirements)
        self.assertRegex(requirements, r"claim global\s+readiness")
        self.assertIn("Bootstrap may return only", main)
        self.assertRegex(main, r"global\s+readiness claim")
        self.assertIn("explicit user confirmation", requirements)
        self.assertIn("authoritative", requirements)
        self.assertIn("create/activate one GoalRun", main)
        self.assertIn("CODE_REMEDIATION", main)
        self.assertIn("exact per-release", main)
        self.assertRegex(main, r"separately\s+authorized owner")
        self.assertIn("Claude Review never merges", main)
        self.assertIn("verify-frontend", main)


if __name__ == "__main__":
    unittest.main()
