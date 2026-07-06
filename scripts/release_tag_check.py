#!/usr/bin/env python3
"""Validate that a release tag matches all package versions."""

from __future__ import annotations

import argparse
from pathlib import Path
import os
import sys
import tomllib
from typing import Sequence


PACKAGE_PROJECTS = {
    "app-control-protocol": Path("packages/app-control-protocol/pyproject.toml"),
    "computer-use-macos": Path("packages/computer-use-macos/pyproject.toml"),
    "wechat-desktop-tool": Path("packages/wechat-desktop-tool/pyproject.toml"),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a release tag against all package versions."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    parser.add_argument(
        "--tag",
        default=os.environ.get("GITHUB_REF_NAME", ""),
        help="Release tag name, for example v0.1.0.",
    )
    args = parser.parse_args(argv)

    try:
        versions = package_versions(args.root)
        expected = expected_release_tag(versions)
        tag = normalize_tag(args.tag)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"release tag check failed: {exc}", file=sys.stderr)
        return 2

    if tag != expected:
        print(
            f"release tag mismatch: got {args.tag!r}, expected {expected!r}; "
            f"versions={versions}",
            file=sys.stderr,
        )
        return 1
    print(f"release tag ok: {tag}")
    return 0


def package_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for project_name, relative_path in PACKAGE_PROJECTS.items():
        project = tomllib.loads((root / relative_path).read_text(encoding="utf-8"))[
            "project"
        ]
        version = project["version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"{relative_path} has an invalid project.version")
        versions[project_name] = version.strip()
    return versions


def expected_release_tag(versions: dict[str, str]) -> str:
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        raise ValueError(f"package versions do not match: {versions}")
    return "v" + unique_versions.pop()


def normalize_tag(tag: str) -> str:
    value = str(tag or "").strip()
    if value.startswith("refs/tags/"):
        value = value.removeprefix("refs/tags/")
    if not value:
        raise ValueError("--tag or GITHUB_REF_NAME is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
