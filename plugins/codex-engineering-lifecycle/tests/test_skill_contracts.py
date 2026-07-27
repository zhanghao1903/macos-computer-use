from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = PLUGIN_ROOT / "skills"
ROLE_SKILLS = {
    "engineering-workflow-init",
    "engineering-requirements",
    "engineering-main",
    "engineering-review",
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

    def test_role_skills_remain_implicitly_available(self) -> None:
        for name in ROLE_SKILLS:
            metadata = (SKILLS / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("allow_implicit_invocation: false", metadata)
            self.assertIn(f"${name}", metadata)

    def test_main_and_review_explicitly_compose_source_skills(self) -> None:
        main = (SKILLS / "engineering-main" / "SKILL.md").read_text(encoding="utf-8")
        for name in (
            "feature-lifecycle",
            "product-workflow-gate",
            "technical-plan-write",
        ):
            self.assertIn(f"${name}", main)
        review = (SKILLS / "engineering-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("$technical-plan-review", review)
        self.assertIn("$pr-review", review)

    def test_role_boundaries_and_goal_release_gates_are_documented(self) -> None:
        init = (SKILLS / "engineering-workflow-init" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        requirements = (SKILLS / "engineering-requirements" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        main = (SKILLS / "engineering-main" / "SKILL.md").read_text(encoding="utf-8")
        review = (SKILLS / "engineering-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("exactly three", init)
        self.assertIn("explicit-per-release", init)
        self.assertIn("begin-init", init)
        self.assertIn("record-init-task", init)
        for role_text in (requirements, main, review):
            self.assertIn("Bootstrap has one narrow exception", role_text)
            self.assertIn('"type":"EngineeringRoleReady"', role_text)
            self.assertRegex(role_text, r"claim global\s+readiness")
        self.assertIn("explicit user confirmation", requirements)
        self.assertIn("authoritative", requirements)
        self.assertIn("create_goal", main)
        self.assertIn("CODE_REMEDIATION", main)
        self.assertIn("per-release authorization", main)
        self.assertRegex(main, r"separately\s+authorized merge owner")
        self.assertIn(
            "Never check out, commit to, push to, or amend the feature branch", review
        )
        self.assertIn("required checks are green", review)
        self.assertIn("review-only `MERGED` result is rejected", review)


if __name__ == "__main__":
    unittest.main()
