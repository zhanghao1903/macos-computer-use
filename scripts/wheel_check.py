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
import zipfile

from testpypi_install_report import DEFAULT_PACKAGES, PACKAGE_SMOKE_SNIPPETS


PACKAGE_PATHS = (
    Path("packages/app-control-protocol"),
    Path("packages/computer-use-macos"),
    Path("packages/wechat-desktop-tool"),
)
EXPECTED_PACKAGE_VERSION = "0.2.0"
INCOMPATIBLE_BASELINE_VERSION = "0.1.1"


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
    installed = _run_install_smoke(wheel_dir)
    if installed != 0:
        return installed
    return _run_incompatible_dependency_smoke(wheel_dir)


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
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                return completed.returncode
            if completed.stdout.strip() != EXPECTED_PACKAGE_VERSION:
                print(
                    "[wheel-check] unexpected version for "
                    f"{package_name}: {completed.stdout.strip()!r}",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
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


def _run_incompatible_dependency_smoke(wheel_dir: Path) -> int:
    wechat_wheels = sorted(
        wheel_dir.glob(f"wechat_desktop_tool-{EXPECTED_PACKAGE_VERSION}-*.whl")
    )
    if len(wechat_wheels) != 1:
        print(
            "[wheel-check] expected exactly one current WeChat wheel for mixed "
            f"dependency smoke, found {len(wechat_wheels)}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    with tempfile.TemporaryDirectory(
        prefix="app-control-incompatible-wheel-install-"
    ) as tmpdir:
        root = Path(tmpdir)
        mixed_wheelhouse = root / "wheelhouse"
        mixed_wheelhouse.mkdir()
        shutil.copy2(wechat_wheels[0], mixed_wheelhouse / wechat_wheels[0].name)
        _write_baseline_wheel(mixed_wheelhouse, "app-control-protocol")
        _write_baseline_wheel(
            mixed_wheelhouse,
            "computer-use-macos",
            dependencies=("app-control-protocol>=0.1.0",),
        )
        venv_dir = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _venv_python(venv_dir)
        command = (
            str(python),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-index",
            "--find-links",
            str(mixed_wheelhouse),
            f"wechat-desktop-tool=={EXPECTED_PACKAGE_VERSION}",
        )
        print(
            "[wheel-check] reject WeChat 0.2.0 with local 0.1.1 dependencies",
            flush=True,
        )
        completed = subprocess.run(
            command,
            cwd=mixed_wheelhouse,
            env=_clean_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            print(
                "[wheel-check] incompatible 0.1.1 dependency set was accepted",
                file=sys.stderr,
                flush=True,
            )
            return 1
        if not _is_expected_dependency_resolution_rejection(completed):
            print(
                "[wheel-check] mixed dependency install failed for an "
                "unexpected reason",
                file=sys.stderr,
                flush=True,
            )
            return 1
    return 0


def _is_expected_dependency_resolution_rejection(
    completed: subprocess.CompletedProcess[str],
) -> bool:
    if completed.returncode == 0:
        return False
    output = f"{completed.stdout or ''}\n{completed.stderr or ''}".casefold()
    resolution_markers = (
        "could not find a version that satisfies the requirement",
        "no matching distribution found",
    )
    incompatible_requirements = (
        f"app-control-protocol>={EXPECTED_PACKAGE_VERSION}",
        f"computer-use-macos>={EXPECTED_PACKAGE_VERSION}",
    )
    return any(marker in output for marker in resolution_markers) and any(
        requirement in output for requirement in incompatible_requirements
    )


def _write_baseline_wheel(
    wheel_dir: Path,
    package_name: str,
    *,
    dependencies: tuple[str, ...] = (),
) -> Path:
    distribution = package_name.replace("-", "_")
    dist_info = f"{distribution}-{INCOMPATIBLE_BASELINE_VERSION}.dist-info"
    wheel_path = (
        wheel_dir
        / f"{distribution}-{INCOMPATIBLE_BASELINE_VERSION}-py3-none-any.whl"
    )
    metadata = "\n".join(
        (
            "Metadata-Version: 2.1",
            f"Name: {package_name}",
            f"Version: {INCOMPATIBLE_BASELINE_VERSION}",
            *(f"Requires-Dist: {dependency}" for dependency in dependencies),
            "",
        )
    )
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(f"{distribution}/__init__.py", "")
        wheel.writestr(f"{dist_info}/METADATA", metadata)
        wheel.writestr(
            f"{dist_info}/WHEEL",
            "\n".join(
                (
                    "Wheel-Version: 1.0",
                    "Generator: macos-computer-use-wheel-check",
                    "Root-Is-Purelib: true",
                    "Tag: py3-none-any",
                    "",
                )
            ),
        )
        wheel.writestr(f"{dist_info}/RECORD", "")
    return wheel_path


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
