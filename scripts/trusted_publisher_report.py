#!/usr/bin/env python3
"""Generate a PyPI Trusted Publisher proof report after manual verification."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Sequence


EXPECTED_PROJECTS = (
    "app-control-protocol",
    "computer-use-macos",
    "wechat-desktop-tool",
)

DEFAULT_OWNER = "zhanghao1903"
DEFAULT_REPOSITORY = "macos-computer-use"
DEFAULT_WORKFLOW = "release.yml"
DEFAULT_ENVIRONMENT: str | None = None

EXPECTED_PUBLISHER = {
    "owner": DEFAULT_OWNER,
    "repository": DEFAULT_REPOSITORY,
    "workflow": DEFAULT_WORKFLOW,
    "environment": DEFAULT_ENVIRONMENT,
}


@dataclass(frozen=True)
class TrustedPublisherProject:
    name: str
    trustedPublisher: bool
    publisher: dict[str, str | None]


def build_report(
    *,
    configured_projects: Sequence[str] = (),
    all_configured: bool = False,
    owner: str = DEFAULT_OWNER,
    repository: str = DEFAULT_REPOSITORY,
    workflow: str = DEFAULT_WORKFLOW,
    environment: str | None = None,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Build the report consumed by release_preflight.py."""

    configured = set(EXPECTED_PROJECTS if all_configured else configured_projects)
    unknown = sorted(configured.difference(EXPECTED_PROJECTS))
    if unknown:
        raise ValueError(f"unknown PyPI project(s): {', '.join(unknown)}")

    publisher = {
        "owner": owner,
        "repository": repository,
        "workflow": workflow,
        "environment": environment,
    }
    projects = [
        TrustedPublisherProject(
            name=name,
            trustedPublisher=name in configured,
            publisher=publisher,
        )
        for name in EXPECTED_PROJECTS
    ]
    return {
        "source": "pypi",
        "verification": "manual",
        "generatedAt": generated_at or _utc_timestamp(),
        "projects": [asdict(project) for project in projects],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write trusted-publisher.json after manually verifying PyPI "
            "Trusted Publisher settings for the release workflow."
        )
    )
    parser.add_argument(
        "--all-configured",
        action="store_true",
        help="Mark all expected PyPI projects as having Trusted Publisher configured.",
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        choices=EXPECTED_PROJECTS,
        help=(
            "Mark one expected PyPI project as configured. May be repeated. "
            "Ignored when --all-configured is set."
        ),
    )
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument(
        "--environment",
        default=None,
        help="PyPI Trusted Publisher environment name, if one is configured.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = build_report(
        configured_projects=tuple(args.project),
        all_configured=args.all_configured,
        owner=args.owner,
        repository=args.repository,
        workflow=args.workflow,
        environment=args.environment,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    passed = _report_passed(report)
    if args.output is not None:
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(
            _report_summary(report, output=args.output, passed=passed),
            file=sys.stderr,
        )
    else:
        print(payload)
    return 0 if passed else 1


def _report_passed(report: dict[str, object]) -> bool:
    projects = report.get("projects")
    return isinstance(projects, list) and all(
        isinstance(item, dict)
        and item.get("trustedPublisher") is True
        and _publisher_matches(item.get("publisher"))
        for item in projects
    )


def _publisher_matches(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        value.get(key) == expected
        for key, expected in EXPECTED_PUBLISHER.items()
    )


def _report_summary(
    report: dict[str, object],
    *,
    output: Path,
    passed: bool,
) -> str:
    status = "passed" if passed else "failed"
    failed_projects = _failed_project_names(report)
    detail = ""
    if failed_projects:
        detail = "; unconfigured or mismatched projects: " + ", ".join(
            failed_projects
        )
    return f"wrote Trusted Publisher report to {output} ({status}{detail})"


def _failed_project_names(report: dict[str, object]) -> list[str]:
    projects = report.get("projects")
    if not isinstance(projects, list):
        return ["<missing projects>"]
    failed: list[str] = []
    for item in projects:
        if not isinstance(item, dict):
            failed.append("<invalid project>")
            continue
        name = item.get("name")
        project_name = (
            name if isinstance(name, str) and name else "<unknown project>"
        )
        if item.get("trustedPublisher") is not True or not _publisher_matches(
            item.get("publisher")
        ):
            failed.append(project_name)
    return failed


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
