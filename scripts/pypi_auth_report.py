#!/usr/bin/env python3
"""Generate sanitized PyPI API-token authentication metadata."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Sequence


REPORT_SCHEMA = "macos_computer_use.release.pypi_auth.v1"
SOURCE = "pypi"
MODE = "api-token"
TARGET_REPOSITORY = "https://upload.pypi.org/legacy/"
CREDENTIAL_KIND = "github-actions-secret"
SECRET_NAME = "PYPI_API_TOKEN"
PUBLISHER_OWNER = "zhanghao1903"
PUBLISHER_REPOSITORY = "macos-computer-use"
PUBLISHER_WORKFLOW = "release.yml"
VERIFICATION = "github-secret-metadata"


def build_report(
    *,
    configured: bool,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Build metadata without accepting or inspecting credential material."""

    return {
        "schema": REPORT_SCHEMA,
        "source": SOURCE,
        "mode": MODE,
        "targetRepository": TARGET_REPOSITORY,
        "credential": {
            "kind": CREDENTIAL_KIND,
            "name": SECRET_NAME,
            "configured": configured,
        },
        "publisher": {
            "owner": PUBLISHER_OWNER,
            "repository": PUBLISHER_REPOSITORY,
            "workflow": PUBLISHER_WORKFLOW,
        },
        "verification": VERIFICATION,
        "generatedAt": generated_at or _utc_timestamp(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write sanitized PyPI API-token authentication metadata after "
            "verifying the expected GitHub repository secret name."
        )
    )
    parser.add_argument(
        "--configured",
        action="store_true",
        required=True,
        help=(
            "Assert that the PYPI_API_TOKEN GitHub repository secret name was "
            "verified. No token value is read."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = build_report(configured=args.configured)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote sanitized PyPI authentication report to {args.output}", file=sys.stderr)
    return 0


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
