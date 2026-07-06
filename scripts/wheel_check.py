#!/usr/bin/env python3
"""Build local wheels and verify their packaged contents."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence
import venv

from testpypi_install_report import DEFAULT_PACKAGES, PACKAGE_SMOKE_SNIPPETS


PACKAGE_PATHS = (
    Path("packages/app-control-protocol"),
    Path("packages/computer-use-macos"),
    Path("packages/wechat-desktop-tool"),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build all app-control wheels and run wheel-content preflight."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    parser.add_argument(
        "--wheel-dir",
        type=Path,
        help="Optional output directory. Defaults to a temporary directory.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.wheel_dir is None:
        with tempfile.TemporaryDirectory(prefix="app-control-wheel-check-") as tmpdir:
            return run_wheel_check(root, Path(tmpdir))
    return run_wheel_check(root, args.wheel_dir)


def run_wheel_check(root: Path, wheel_dir: Path) -> int:
    if wheel_dir.exists():
        shutil.rmtree(wheel_dir)
    wheel_dir.mkdir(parents=True)
    for package_path in PACKAGE_PATHS:
        command = (
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            str(package_path),
            "-w",
            str(wheel_dir),
        )
        print(
            "[wheel-check] build " + str(package_path),
            flush=True,
        )
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode
    print("[wheel-check] release preflight", flush=True)
    completed = subprocess.run(
        (
            sys.executable,
            "scripts/release_preflight.py",
            "--wheel-dir",
            str(wheel_dir),
        ),
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    return _run_install_smoke(wheel_dir)


def _run_install_smoke(wheel_dir: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="app-control-wheel-install-") as tmpdir:
        venv_dir = Path(tmpdir) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _venv_python(venv_dir)
        install_command = (
            str(python),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--force-reinstall",
            "--no-index",
            "--find-links",
            str(wheel_dir),
            *(package_name for package_name, _import_name in DEFAULT_PACKAGES),
        )
        print("[wheel-check] install local wheelhouse", flush=True)
        completed = subprocess.run(
            install_command,
            cwd=wheel_dir,
            env=_clean_env(),
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode
        for package_name, import_name in DEFAULT_PACKAGES:
            probe = (
                "import importlib; "
                f"module = importlib.import_module({import_name!r}); "
                "print(getattr(module, '__version__', ''))"
            )
            print(f"[wheel-check] import {import_name}", flush=True)
            completed = subprocess.run(
                (str(python), "-c", probe),
                cwd=wheel_dir,
                env=_clean_env(),
                check=False,
            )
            if completed.returncode != 0:
                return completed.returncode
            print(f"[wheel-check] api smoke {package_name}", flush=True)
            completed = subprocess.run(
                (str(python), "-c", PACKAGE_SMOKE_SNIPPETS[package_name]),
                cwd=wheel_dir,
                env=_clean_env(),
                check=False,
            )
            if completed.returncode != 0:
                return completed.returncode
    return 0


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


if __name__ == "__main__":
    raise SystemExit(main())
