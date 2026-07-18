"""Packaged Agent skill loading for WeChat semantic operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib import resources
from importlib.resources.abc import Traversable
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any, Final


WECHAT_AGENT_SKILL_SCHEMA: Final = "wechat.agent-skill.v1"
WECHAT_USE_SKILL_NAME: Final = "wechat-use"
WECHAT_USE_SKILL_RESOURCE: Final = "skills/wechat-use"

_MANIFEST_NAME = "manifest.json"
_ENTRYPOINT_NAME = "SKILL.md"
_MANIFEST_FIELDS = frozenset(
    {"schema", "name", "version", "description", "entrypoint", "files"}
)
_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".yaml": "application/yaml",
}
_SEMANTIC_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class WeChatAgentSkillFile:
    """One validated UTF-8 file from the packaged Agent skill."""

    path: str
    media_type: str
    content: str
    sha256: str

    def __post_init__(self) -> None:
        validated_path = _validate_resource_path(self.path)
        if validated_path != self.path:
            raise ValueError("path must use canonical relative POSIX syntax")
        expected_media_type = _media_type(self.path)
        if self.media_type != expected_media_type:
            raise ValueError(
                f"media_type for {self.path} must be {expected_media_type}"
            )
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not isinstance(self.sha256, str) or not _SHA256.fullmatch(self.sha256):
            raise ValueError("sha256 must be a lowercase hexadecimal SHA-256 digest")
        expected_digest = _content_sha256(self.content)
        if self.sha256 != expected_digest:
            raise ValueError(f"sha256 does not match content for {self.path}")

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "mediaType": self.media_type,
            "content": self.content,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class WeChatAgentSkill:
    """Immutable framework-neutral representation of the WeChat Agent skill."""

    schema: str
    name: str
    version: str
    description: str
    entrypoint: str
    files: tuple[WeChatAgentSkillFile, ...]

    def __post_init__(self) -> None:
        if self.schema != WECHAT_AGENT_SKILL_SCHEMA:
            raise ValueError(f"schema must be {WECHAT_AGENT_SKILL_SCHEMA}")
        if self.name != WECHAT_USE_SKILL_NAME:
            raise ValueError(f"name must be {WECHAT_USE_SKILL_NAME}")
        _validate_version(self.version)
        _non_empty_string(self.description, "description")
        validated_entrypoint = _validate_resource_path(self.entrypoint)
        if validated_entrypoint != _ENTRYPOINT_NAME:
            raise ValueError(f"entrypoint must be {_ENTRYPOINT_NAME}")

        normalized_files = tuple(self.files)
        if not normalized_files:
            raise ValueError("files must not be empty")
        if any(not isinstance(item, WeChatAgentSkillFile) for item in normalized_files):
            raise TypeError("files must contain WeChatAgentSkillFile values")
        paths = tuple(item.path for item in normalized_files)
        if len(paths) != len(set(paths)):
            raise ValueError("files must not contain duplicate paths")
        if paths.count(self.entrypoint) != 1:
            raise ValueError("files must contain the entrypoint exactly once")
        object.__setattr__(self, "files", normalized_files)

    @property
    def instructions(self) -> str:
        """Return the skill entrypoint text."""

        return self.get_file(self.entrypoint).content

    def get_file(self, path: str) -> WeChatAgentSkillFile:
        """Return a bundled skill file by relative POSIX path."""

        for item in self.files:
            if item.path == path:
                return item
        raise KeyError(path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "files": [item.to_dict() for item in self.files],
        }


def load_wechat_use_skill() -> WeChatAgentSkill:
    """Load and validate the packaged ``wechat-use`` Agent skill."""

    root = resources.files("wechat_desktop_tool").joinpath(WECHAT_USE_SKILL_RESOURCE)
    return _load_skill_from_root(root)


def export_wechat_use_skill(parent_directory: str | Path) -> Path:
    """Export ``wechat-use`` below *parent_directory* without overwriting."""

    skill = load_wechat_use_skill()
    parent = Path(parent_directory).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / skill.name
    target.mkdir(exist_ok=False)
    try:
        _write_text(target / _MANIFEST_NAME, _serialize_manifest(skill))
        for item in skill.files:
            output = target.joinpath(*PurePosixPath(item.path).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            _write_text(output, item.content)
    except Exception:
        try:
            shutil.rmtree(target)
        except OSError:
            pass
        raise
    return target


def _load_skill_from_root(root: Traversable) -> WeChatAgentSkill:
    manifest_text = root.joinpath(_MANIFEST_NAME).read_text(encoding="utf-8")
    manifest = _parse_manifest(manifest_text)
    files = tuple(_load_skill_file(root, path) for path in manifest["files"])
    return WeChatAgentSkill(
        schema=manifest["schema"],
        name=manifest["name"],
        version=manifest["version"],
        description=manifest["description"],
        entrypoint=manifest["entrypoint"],
        files=files,
    )


def _parse_manifest(text: str) -> dict[str, Any]:
    try:
        raw = json.loads(text, object_pairs_hook=_unique_json_object)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid skill manifest JSON: {exc.msg}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("skill manifest must be a JSON object")

    fields = set(raw)
    missing = sorted(_MANIFEST_FIELDS - fields)
    extra = sorted(fields - _MANIFEST_FIELDS)
    if missing:
        raise ValueError(f"skill manifest missing fields: {', '.join(missing)}")
    if extra:
        raise ValueError(f"skill manifest has unknown fields: {', '.join(extra)}")

    schema = _non_empty_string(raw["schema"], "schema")
    if schema != WECHAT_AGENT_SKILL_SCHEMA:
        raise ValueError(f"schema must be {WECHAT_AGENT_SKILL_SCHEMA}")
    name = _non_empty_string(raw["name"], "name")
    if name != WECHAT_USE_SKILL_NAME:
        raise ValueError(f"name must be {WECHAT_USE_SKILL_NAME}")
    version = _non_empty_string(raw["version"], "version")
    _validate_version(version)
    description = _non_empty_string(raw["description"], "description")
    entrypoint = _validate_resource_path(raw["entrypoint"])
    if entrypoint != _ENTRYPOINT_NAME:
        raise ValueError(f"entrypoint must be {_ENTRYPOINT_NAME}")
    file_paths = _manifest_file_paths(raw["files"])
    if file_paths.count(entrypoint) != 1:
        raise ValueError("files must contain the entrypoint exactly once")

    return {
        "schema": schema,
        "name": name,
        "version": version,
        "description": description,
        "entrypoint": entrypoint,
        "files": file_paths,
    }


def _manifest_file_paths(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("files must be a JSON array")
    paths = tuple(_validate_resource_path(item) for item in value)
    if not paths:
        raise ValueError("files must not be empty")
    if len(paths) != len(set(paths)):
        raise ValueError("files must not contain duplicate paths")
    return paths


def _validate_resource_path(value: object) -> str:
    path = _non_empty_string(value, "resource path")
    if "\\" in path:
        raise ValueError("resource path must use POSIX separators")
    if path.startswith("/") or path.endswith("/"):
        raise ValueError("resource path must be relative and name a file")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("resource path contains an unsafe segment")
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or pure_path.as_posix() != path:
        raise ValueError("resource path must use canonical relative POSIX syntax")
    if path == _MANIFEST_NAME:
        raise ValueError("manifest.json must not list itself")
    _media_type(path)
    return path


def _load_skill_file(root: Traversable, path: str) -> WeChatAgentSkillFile:
    resource = root
    for part in PurePosixPath(path).parts:
        resource = resource.joinpath(part)
    content = resource.read_text(encoding="utf-8")
    return WeChatAgentSkillFile(
        path=path,
        media_type=_media_type(path),
        content=content,
        sha256=_content_sha256(content),
    )


def _serialize_manifest(skill: WeChatAgentSkill) -> str:
    payload = {
        "schema": skill.schema,
        "name": skill.name,
        "version": skill.version,
        "description": skill.description,
        "entrypoint": skill.entrypoint,
        "files": [item.path for item in skill.files],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validate_version(value: object) -> str:
    version = _non_empty_string(value, "version")
    if not _SEMANTIC_VERSION.fullmatch(version):
        raise ValueError("version must use MAJOR.MINOR.PATCH numeric syntax")
    return version


def _media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix
    try:
        return _MEDIA_TYPES[suffix]
    except KeyError as exc:
        raise ValueError(
            f"unsupported skill resource suffix: {suffix or '<none>'}"
        ) from exc


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(content)


__all__ = [
    "export_wechat_use_skill",
    "load_wechat_use_skill",
    "WECHAT_AGENT_SKILL_SCHEMA",
    "WECHAT_USE_SKILL_NAME",
    "WECHAT_USE_SKILL_RESOURCE",
    "WeChatAgentSkill",
    "WeChatAgentSkillFile",
]
