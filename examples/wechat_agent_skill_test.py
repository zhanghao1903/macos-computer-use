#!/usr/bin/env python3
"""Load and export the packaged WeChat Agent skill without desktop access."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any

from wechat_desktop_tool import (
    export_wechat_use_skill,
    load_wechat_use_skill,
)


def build_agent_skill_registration() -> dict[str, Any]:
    """Return a framework-neutral payload for an application skill registry."""

    return load_wechat_use_skill().to_dict()


def run_agent_skill_test(export_parent: str | Path) -> dict[str, Any]:
    """Load the bundle, export it, and return privacy-safe proof."""

    registration = build_agent_skill_registration()
    target = export_wechat_use_skill(export_parent)
    exported_files = sorted(
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    )
    registered_files = [
        item["path"]
        for item in registration["files"]
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    ]
    return {
        "success": True,
        "schema": registration["schema"],
        "name": registration["name"],
        "version": registration["version"],
        "entrypoint": registration["entrypoint"],
        "registeredFiles": registered_files,
        "exportedDirectory": str(target),
        "exportedFiles": exported_files,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wechat-agent-skill-example-") as tmpdir:
        result = run_agent_skill_test(Path(tmpdir) / "application-skills")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
