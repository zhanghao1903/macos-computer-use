#!/usr/bin/env python3
"""Run the local development verification flow for the app-control suite."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class DevCheck:
    name: str
    description: str
    args: tuple[str, ...]
    pythonpath: tuple[str, ...] = ()
    default: bool = True
    preflight: bool = False

    def command(self) -> list[str]:
        return [sys.executable, *self.args]


CHECKS: tuple[DevCheck, ...] = (
    DevCheck(
        name="root-tests",
        description="repository-level boundary and cross-package contract tests",
        args=("-m", "unittest", "discover", "-s", "tests"),
        pythonpath=(
            "packages/app-control-protocol/src",
            "packages/computer-use-macos/src",
            "packages/wechat-desktop-tool/src",
        ),
    ),
    DevCheck(
        name="protocol-tests",
        description="app-control-protocol package tests",
        args=(
            "-m",
            "unittest",
            "discover",
            "-s",
            "packages/app-control-protocol/tests",
        ),
        pythonpath=("packages/app-control-protocol/src",),
    ),
    DevCheck(
        name="computer-use-tests",
        description="computer-use-macos package tests",
        args=(
            "-m",
            "unittest",
            "discover",
            "-s",
            "packages/computer-use-macos/tests",
        ),
        pythonpath=(
            "packages/app-control-protocol/src",
            "packages/computer-use-macos/src",
        ),
    ),
    DevCheck(
        name="wechat-tests",
        description="wechat-desktop-tool package tests",
        args=(
            "-m",
            "unittest",
            "discover",
            "-s",
            "packages/wechat-desktop-tool/tests",
        ),
        pythonpath=(
            "packages/app-control-protocol/src",
            "packages/computer-use-macos/src",
            "packages/wechat-desktop-tool/src",
        ),
    ),
    DevCheck(
        name="release-preflight",
        description="local release preflight without external proof requirements",
        args=("scripts/release_preflight.py",),
        preflight=True,
    ),
    DevCheck(
        name="release-proof-preflight",
        description=(
            "strict release preflight using release-proof/ external proof assets"
        ),
        args=(
            "scripts/release_preflight.py",
            "--helper-doctor-report",
            "release-proof/helper-doctor.json",
            "--textedit-smoke-report",
            "release-proof/textedit-smoke.json",
            "--wechat-smoke-report",
            "release-proof/wechat-focus-draft-smoke.json",
            "--wechat-smoke-report",
            "release-proof/wechat-submit-smoke.json",
            "--wechat-smoke-report",
            "release-proof/wechat-selector-engine-smoke.json",
            "--testpypi-install-report",
            "release-proof/testpypi-install.json",
            "--pypi-auth-report",
            "release-proof/pypi-auth.json",
            "--proof",
            "release-proof/release-proof.json",
            "--require-external",
        ),
        default=False,
        preflight=True,
    ),
    DevCheck(
        name="wheel-preflight",
        description=(
            "build local wheels, verify contents, and install-smoke them in a venv"
        ),
        args=("scripts/wheel_check.py",),
        default=False,
        preflight=True,
    ),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dev_check.py",
        description="Run the local app-control package suite verification flow.",
    )
    parser.add_argument(
        "--check",
        action="append",
        choices=tuple(check.name for check in CHECKS),
        help="Run only the named check. May be repeated.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip release-preflight while running test checks.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at the first failing check.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List checks without running them.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    args = parser.parse_args(argv)
    if args.list:
        checks = _select_checks(
            args.check,
            skip_preflight=args.skip_preflight,
            include_optional=True,
        )
        for check in checks:
            print(f"{check.name}: {check.description}")
        return 0
    checks = _select_checks(args.check, skip_preflight=args.skip_preflight)
    return run_checks(args.root.resolve(), checks, fail_fast=args.fail_fast)


def run_checks(
    root: Path,
    checks: Iterable[DevCheck],
    *,
    fail_fast: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[object]] = subprocess.run,
) -> int:
    failed: list[str] = []
    for check in checks:
        print(f"[dev-check] {check.name}: {check.description}", flush=True)
        completed = runner(
            check.command(),
            cwd=root,
            env=_env_for_check(root, check),
            check=False,
        )
        if completed.returncode != 0:
            failed.append(check.name)
            if fail_fast:
                break
    if failed:
        print("[dev-check] failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    print("[dev-check] ok", flush=True)
    return 0


def _select_checks(
    names: Sequence[str] | None,
    *,
    skip_preflight: bool,
    include_optional: bool = False,
) -> tuple[DevCheck, ...]:
    selected_names = set(names or ())
    checks = (
        tuple(check for check in CHECKS if check.name in selected_names)
        if selected_names
        else tuple(
            check for check in CHECKS if include_optional or check.default
        )
    )
    if skip_preflight:
        checks = tuple(check for check in checks if not check.preflight)
    return checks


def _env_for_check(root: Path, check: DevCheck) -> dict[str, str]:
    env = dict(os.environ)
    if check.name == "release-proof-preflight" and not env.get("GITHUB_SHA"):
        env["GITHUB_SHA"] = _repository_head_sha(root)
    if check.pythonpath:
        paths = [str(root / part) for part in check.pythonpath]
        current = env.get("PYTHONPATH")
        if current:
            paths.append(current)
        env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _repository_head_sha(root: Path) -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    head_sha = completed.stdout.strip()
    if completed.returncode != 0 or len(head_sha) != 40:
        raise RuntimeError("could not resolve repository HEAD for strict proof")
    return head_sha


if __name__ == "__main__":
    raise SystemExit(main())
