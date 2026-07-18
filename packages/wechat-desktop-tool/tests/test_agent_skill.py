from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wechat_desktop_tool import (
    WECHAT_AGENT_SKILL_SCHEMA,
    WECHAT_USE_SKILL_NAME,
    WeChatAgentSkill,
    WeChatAgentSkillFile,
    export_wechat_use_skill,
    load_wechat_use_skill,
)
from wechat_desktop_tool import agent_skill as agent_skill_module


class WeChatAgentSkillTests(unittest.TestCase):
    def test_packaged_skill_loads_as_immutable_public_model(self) -> None:
        skill = load_wechat_use_skill()

        self.assertIsInstance(skill, WeChatAgentSkill)
        self.assertEqual(skill.schema, WECHAT_AGENT_SKILL_SCHEMA)
        self.assertEqual(skill.name, WECHAT_USE_SKILL_NAME)
        self.assertEqual(skill.version, "1.0.0")
        self.assertEqual(skill.entrypoint, "SKILL.md")
        self.assertIsInstance(skill.files, tuple)
        self.assertEqual(
            [item.path for item in skill.files],
            [
                "SKILL.md",
                "agents/openai.yaml",
                "references/operations.md",
                "references/recovery.md",
            ],
        )
        self.assertEqual(skill.instructions, skill.get_file("SKILL.md").content)
        with self.assertRaises(KeyError):
            skill.get_file("missing.md")

    def test_packaged_skill_metadata_matches_entrypoint_frontmatter(self) -> None:
        skill = load_wechat_use_skill()
        lines = skill.instructions.splitlines()

        self.assertEqual(lines[0], "---")
        self.assertEqual(lines[1], f"name: {skill.name}")
        self.assertEqual(lines[2], f"description: {skill.description}")
        self.assertEqual(lines[3], "---")
        self.assertNotIn("TODO", skill.instructions)

    def test_skill_files_have_verified_hashes_and_json_model(self) -> None:
        skill = load_wechat_use_skill()

        for item in skill.files:
            with self.subTest(path=item.path):
                self.assertIsInstance(item, WeChatAgentSkillFile)
                self.assertEqual(
                    item.sha256,
                    hashlib.sha256(item.content.encode("utf-8")).hexdigest(),
                )
        payload = skill.to_dict()
        self.assertEqual(payload["schema"], WECHAT_AGENT_SKILL_SCHEMA)
        self.assertEqual(payload["name"], WECHAT_USE_SKILL_NAME)
        self.assertEqual(payload["entrypoint"], "SKILL.md")
        self.assertEqual(len(payload["files"]), len(skill.files))
        json.dumps(payload)

    def test_skill_file_rejects_digest_or_media_type_mismatch(self) -> None:
        content = "# Skill\n"
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

        with self.assertRaisesRegex(ValueError, "media_type"):
            WeChatAgentSkillFile(
                path="SKILL.md",
                media_type="text/plain",
                content=content,
                sha256=digest,
            )
        with self.assertRaisesRegex(ValueError, "does not match"):
            WeChatAgentSkillFile(
                path="SKILL.md",
                media_type="text/markdown",
                content=content,
                sha256="0" * 64,
            )

    def test_manifest_rejects_invalid_contract_values(self) -> None:
        base = _manifest()
        cases = {
            "schema": ({**base, "schema": "wechat.agent-skill.v2"}, "schema"),
            "name": ({**base, "name": "other"}, "name"),
            "version": ({**base, "version": "1"}, "version"),
            "files_type": ({**base, "files": "SKILL.md"}, "JSON array"),
            "duplicate_path": (
                {**base, "files": ["SKILL.md", "SKILL.md"]},
                "duplicate",
            ),
            "absolute_path": (
                {**base, "files": ["SKILL.md", "/reference.md"]},
                "relative",
            ),
            "traversal_path": (
                {**base, "files": ["SKILL.md", "../reference.md"]},
                "unsafe segment",
            ),
            "backslash_path": (
                {**base, "files": ["SKILL.md", "references\\ops.md"]},
                "POSIX",
            ),
            "empty_segment": (
                {**base, "files": ["SKILL.md", "references//ops.md"]},
                "unsafe segment",
            ),
            "self_listing": (
                {**base, "files": ["SKILL.md", "manifest.json"]},
                "must not list itself",
            ),
            "unsupported_suffix": (
                {**base, "files": ["SKILL.md", "reference.txt"]},
                "unsupported",
            ),
            "missing_entrypoint": (
                {**base, "files": ["reference.md"]},
                "entrypoint",
            ),
            "unknown_field": ({**base, "extra": True}, "unknown fields"),
        }

        for name, (manifest, expected) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, expected):
                    agent_skill_module._parse_manifest(json.dumps(manifest))

    def test_manifest_rejects_duplicate_json_keys(self) -> None:
        text = json.dumps(_manifest())
        duplicate = text.replace(
            '"schema": "wechat.agent-skill.v1",',
            '"schema": "wechat.agent-skill.v1", "schema": "duplicate",',
            1,
        )

        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            agent_skill_module._parse_manifest(duplicate)

    def test_loader_rejects_missing_manifest_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_test_bundle(root, files={"SKILL.md": "# Skill\n"})

            with self.assertRaises(FileNotFoundError):
                agent_skill_module._load_skill_from_root(root)

    def test_export_writes_complete_skill_to_resolved_target(self) -> None:
        packaged = load_wechat_use_skill()
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir) / "runtime" / "skills"

            target = export_wechat_use_skill(parent)

            self.assertTrue(target.is_absolute())
            self.assertEqual(target, parent.resolve() / WECHAT_USE_SKILL_NAME)
            manifest = json.loads((target / "manifest.json").read_text())
            self.assertEqual(manifest["version"], packaged.version)
            self.assertEqual(manifest["files"], [item.path for item in packaged.files])
            for item in packaged.files:
                with self.subTest(path=item.path):
                    self.assertEqual(
                        target.joinpath(*Path(item.path).parts).read_text(),
                        item.content,
                    )

    def test_export_never_modifies_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            target = parent / WECHAT_USE_SKILL_NAME
            target.mkdir()
            sentinel = target / "application-owned.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                export_wechat_use_skill(parent)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(target.iterdir()), [sentinel])

    def test_export_removes_only_new_target_after_write_failure(self) -> None:
        original_write = agent_skill_module._write_text

        def fail_on_entrypoint(path: Path, content: str) -> None:
            if path.name == "SKILL.md":
                raise OSError("simulated write failure")
            original_write(path, content)

        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir) / "skills"
            with mock.patch.object(
                agent_skill_module,
                "_write_text",
                side_effect=fail_on_entrypoint,
            ):
                with self.assertRaisesRegex(OSError, "simulated"):
                    export_wechat_use_skill(parent)

            self.assertTrue(parent.is_dir())
            self.assertFalse((parent / WECHAT_USE_SKILL_NAME).exists())

    def test_skill_content_covers_required_operations_and_recovery(self) -> None:
        skill = load_wechat_use_skill()
        content = "\n".join(item.content for item in skill.files)

        required_operations = {
            "inspect_window",
            "list_contacts",
            "list_conversations",
            "open_contact",
            "read_visible_messages",
            "read_contact_messages",
            "draft_message",
            "submit_draft",
            "send_message",
        }
        for operation in required_operations:
            with self.subTest(operation=operation):
                self.assertIn(f"`{operation}`", content)
        for rule in (
            "contact_ambiguous",
            "contact_not_found",
            "submit_unknown",
            "send_unverified",
            "status=unknown",
            "Never automatically replay",
            "visible and currently loaded",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, content)
        self.assertNotIn("0/12/", content)
        self.assertNotIn("/tmp/", content)

    def test_skill_bundle_stays_within_context_budget(self) -> None:
        skill = load_wechat_use_skill()
        total_bytes = sum(len(item.content.encode("utf-8")) for item in skill.files)

        self.assertLess(total_bytes, 64 * 1024)
        self.assertLess(len(skill.instructions.splitlines()), 500)


def _manifest() -> dict[str, object]:
    return {
        "schema": WECHAT_AGENT_SKILL_SCHEMA,
        "name": WECHAT_USE_SKILL_NAME,
        "version": "1.0.0",
        "description": "Test skill",
        "entrypoint": "SKILL.md",
        "files": ["SKILL.md", "references/operations.md"],
    }


def _write_test_bundle(root: Path, *, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(_manifest()),
        encoding="utf-8",
    )
    for relative, content in files.items():
        path = root.joinpath(*Path(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
