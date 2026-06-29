#!/usr/bin/env python3
"""Local release preflight for the app-control tool package suite."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from email.parser import Parser
import inspect
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from typing import Any, Callable
import zipfile


LOCAL_DOCS = (
    "docs/quickstart.md",
    "docs/protocol.md",
    "docs/api.md",
    "docs/helper-packaging.md",
    "docs/permissions.md",
    "docs/local-service.md",
    "docs/wechat-desktop-tool.md",
    "docs/wechat-smoke.md",
    "docs/migration-notes.md",
    "docs/publishing.md",
    "docs/release-checklist.md",
)

LOCAL_SCRIPTS = (
    "scripts/dev_check.py",
    "scripts/release_tag_check.py",
    "scripts/release_preflight.py",
    "scripts/release_proof_bundle.py",
    "scripts/testpypi_install_report.py",
    "scripts/trusted_publisher_report.py",
)

LOCAL_EXAMPLES = (
    "examples/app-control.toml",
    "examples/textedit_smoke.py",
)

LOCAL_TESTS = (
    "tests/test_package_boundary.py",
    "tests/test_project_contract.py",
    "tests/test_release_preflight.py",
)

PACKAGE_TESTS = (
    "packages/app-control-protocol/tests/test_package_boundary.py",
    "packages/app-control-protocol/tests/test_schemas.py",
    "packages/computer-use-macos/tests/test_package.py",
    "packages/wechat-desktop-tool/tests/test_package_boundary.py",
    "packages/wechat-desktop-tool/tests/test_tool.py",
)

MARKDOWN_JSON_DOCS = (
    "README.md",
    "packages/README.md",
    "packages/app-control-protocol/README.md",
    "packages/computer-use-macos/README.md",
    "packages/wechat-desktop-tool/README.md",
    *LOCAL_DOCS,
)

MARKDOWN_TOML_DOCS = MARKDOWN_JSON_DOCS

APP_CONTROL_CONFIG_SECTIONS = {
    "logging",
    "computer_use",
    "helper",
    "wechat",
}

PROTOCOL_SCHEMA_BY_ID = {
    "app_control.command.v1": "command",
    "app_control.observation.v1": "observation",
    "app_control.event.v1": "event",
    "app_control.error.v1": "error",
    "app_control.service.request.v1": "service_request",
    "app_control.service.response.v1": "service_response",
    "app_control.service.event.v1": "service_event",
    "app_control.helper.request.v1": "helper_request",
    "app_control.helper.response.v1": "helper_response",
}

PROTOCOL_SCHEMA_FILES = (
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "command.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "observation.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "event.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "error.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "service-request.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "service-response.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "service-event.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "helper-request.schema.json",
    "packages/app-control-protocol/src/app_control_protocol/schemas/"
    "helper-response.schema.json",
)

PACKAGE_PROJECTS = {
    "app-control-protocol": Path("packages/app-control-protocol/pyproject.toml"),
    "computer-use-macos": Path("packages/computer-use-macos/pyproject.toml"),
    "wechat-desktop-tool": Path("packages/wechat-desktop-tool/pyproject.toml"),
}

PACKAGE_SOURCES = {
    "app-control-protocol": Path(
        "packages/app-control-protocol/src/app_control_protocol"
    ),
    "computer-use-macos": Path("packages/computer-use-macos/src/computer_use_macos"),
    "wechat-desktop-tool": Path(
        "packages/wechat-desktop-tool/src/wechat_desktop_tool"
    ),
}

PACKAGE_MODULE_FILES = (
    "packages/computer-use-macos/src/computer_use_macos/commands.py",
    "packages/computer-use-macos/src/computer_use_macos/observations.py",
    "packages/computer-use-macos/src/computer_use_macos/errors.py",
    "packages/computer-use-macos/src/computer_use_macos/readiness.py",
    "packages/computer-use-macos/src/computer_use_macos/transport.py",
    "packages/wechat-desktop-tool/src/wechat_desktop_tool/commands.py",
    "packages/wechat-desktop-tool/src/wechat_desktop_tool/observations.py",
    "packages/wechat-desktop-tool/src/wechat_desktop_tool/errors.py",
    "packages/wechat-desktop-tool/src/wechat_desktop_tool/adapter.py",
    "packages/wechat-desktop-tool/src/wechat_desktop_tool/recipes.py",
)

EXPECTED_RUNTIME_DEPS = {
    "app-control-protocol": (),
    "computer-use-macos": ("app-control-protocol>=0.1.0",),
    "wechat-desktop-tool": ("app-control-protocol>=0.1.0",),
}

EXPECTED_PACKAGE_DATA = {
    "app-control-protocol": ("py.typed", "schemas/*.schema.json"),
}

EXPECTED_WHEEL_CONTENT = {
    "app-control-protocol": (
        "app_control_protocol/__init__.py",
        "app_control_protocol/client.py",
        "app_control_protocol/config.py",
        "app_control_protocol/errors.py",
        "app_control_protocol/event_logging.py",
        "app_control_protocol/json_types.py",
        "app_control_protocol/models.py",
        "app_control_protocol/observer.py",
        "app_control_protocol/py.typed",
        "app_control_protocol/schemas.py",
        "app_control_protocol/schemas/command.schema.json",
        "app_control_protocol/schemas/observation.schema.json",
        "app_control_protocol/schemas/event.schema.json",
        "app_control_protocol/schemas/error.schema.json",
        "app_control_protocol/schemas/service-request.schema.json",
        "app_control_protocol/schemas/service-response.schema.json",
        "app_control_protocol/schemas/service-event.schema.json",
        "app_control_protocol/schemas/helper-request.schema.json",
        "app_control_protocol/schemas/helper-response.schema.json",
    ),
    "computer-use-macos": (
        "computer_use_macos/__init__.py",
        "computer_use_macos/py.typed",
        "computer_use_macos/cli.py",
        "computer_use_macos/__main__.py",
        "computer_use_macos/client.py",
        "computer_use_macos/commands.py",
        "computer_use_macos/observations.py",
        "computer_use_macos/errors.py",
        "computer_use_macos/models.py",
        "computer_use_macos/policy.py",
        "computer_use_macos/readiness.py",
        "computer_use_macos/service.py",
        "computer_use_macos/transport.py",
        "computer_use_macos/examples/__init__.py",
        "computer_use_macos/examples/textedit_smoke.py",
        "computer_use_macos/helper/__init__.py",
        "computer_use_macos/helper/discovery.py",
        "computer_use_macos/helper/doctor.py",
        "computer_use_macos/helper/launcher.py",
        "computer_use_macos/helper/manifest.py",
        "computer_use_macos/helper/template.py",
        "computer_use_macos/helper/transport.py",
    ),
    "wechat-desktop-tool": (
        "wechat_desktop_tool/__init__.py",
        "wechat_desktop_tool/py.typed",
        "wechat_desktop_tool/cli.py",
        "wechat_desktop_tool/__main__.py",
        "wechat_desktop_tool/commands.py",
        "wechat_desktop_tool/observations.py",
        "wechat_desktop_tool/errors.py",
        "wechat_desktop_tool/models.py",
        "wechat_desktop_tool/tool.py",
        "wechat_desktop_tool/adapter.py",
        "wechat_desktop_tool/recipes.py",
        "wechat_desktop_tool/examples/__init__.py",
        "wechat_desktop_tool/examples/wechat_smoke.py",
    ),
}

EXPECTED_SDIST_CONTENT = {
    project_name: (
        "pyproject.toml",
        "README.md",
        *(f"src/{relative}" for relative in content),
    )
    for project_name, content in EXPECTED_WHEEL_CONTENT.items()
}

EXPECTED_SCRIPTS = {
    "computer-use-macos": {"computer-use-macos": "computer_use_macos.cli:main"},
    "wechat-desktop-tool": {"wechat-desktop-tool": "wechat_desktop_tool.cli:main"},
}

MODULE_ENTRYPOINT_CHECKS = (
    (
        "computer-use-macos:root",
        ("computer_use_macos", "--help"),
        ("packages/app-control-protocol/src", "packages/computer-use-macos/src"),
        ("helper", "doctor", "serve", "request"),
    ),
    (
        "computer-use-macos:helper-init",
        ("computer_use_macos", "helper", "init", "--help"),
        ("packages/app-control-protocol/src", "packages/computer-use-macos/src"),
        ("--name", "--bundle-id", "--force"),
    ),
    (
        "computer-use-macos:doctor",
        ("computer_use_macos", "doctor", "--help"),
        ("packages/app-control-protocol/src", "packages/computer-use-macos/src"),
        ("--helper-app", "--verify-signature", "--verify-notarization"),
    ),
    (
        "computer-use-macos:serve",
        ("computer_use_macos", "serve", "--help"),
        ("packages/app-control-protocol/src", "packages/computer-use-macos/src"),
        ("--socket-path", "--token-file", "--allow-unauthenticated"),
    ),
    (
        "wechat-desktop-tool:root",
        ("wechat_desktop_tool", "--help"),
        ("packages/app-control-protocol/src", "packages/wechat-desktop-tool/src"),
        ("examples",),
    ),
    (
        "wechat-desktop-tool:send-message",
        ("wechat_desktop_tool", "examples", "send-message", "--help"),
        ("packages/app-control-protocol/src", "packages/wechat-desktop-tool/src"),
        ("--contact", "--message", "--dry-run", "--submit"),
    ),
)

EXPECTED_PUBLIC_API = {
    "app-control-protocol": (
        "AppControlClient",
        "StreamingAppControlClient",
        "ToolCommand",
        "ToolObservation",
        "ToolEvent",
        "ToolObserver",
        "ToolError",
        "ServiceRequest",
        "ServiceResponse",
        "ServiceEventEnvelope",
        "HELPER_REQUEST_SCHEMA",
        "HELPER_RESPONSE_SCHEMA",
        "AppControlConfig",
        "HelperConfig",
        "LoggingToolObserver",
        "build_logging_observer",
        "validate_protocol_payload",
    ),
    "computer-use-macos": (
        "ComputerUseClient",
        "MacOSComputerUseClient",
        "AppControlConfig",
        "HelperConfig",
        "ComputerUseError",
        "COMPUTER_USE_FAILURE_KINDS",
        "LocalCommandService",
        "UnixSocketCommandService",
        "UnixSocketServiceClient",
        "computer_use_command",
        "readiness_command",
        "observe_command",
        "open_app_command",
        "focus_app_command",
        "click_command",
        "press_key_command",
        "hotkey_command",
        "click_accessibility_command",
        "click_coordinate_command",
        "type_text_command",
        "wait_command",
    ),
    "wechat-desktop-tool": (
        "WeChatDesktopTool",
        "WeChatDesktopConfig",
        "WECHAT_TOOL",
        "WECHAT_FAILURE_KINDS",
        "wechat_command",
        "open_wechat_command",
        "focus_contact_command",
        "observe_current_chat_command",
        "read_visible_messages_command",
        "draft_message_command",
        "submit_draft_command",
        "send_message_command",
        "build_wechat_tool",
        "send_message",
    ),
}

COMMON_BANNED_TERMS = (
    "taskweavn",
    "from plato",
    "import plato",
    "openai",
    "anthropic",
    "langchain",
    "ui_tars",
    "uitars",
)

PACKAGE_BANNED_TERMS = {
    "computer-use-macos": ("wechat_desktop_tool",),
    "wechat-desktop-tool": (
        "macos_computer_use",
        "computer_use_macos",
    ),
}

EXTERNAL_PROOFS = {
    "helper_app_doctor": "helper app template/build output passed helper doctor",
    "textedit_smoke": "real TextEdit smoke passed",
    "wechat_focus_draft_smoke": "real WeChat focus/draft smoke passed",
    "wechat_submit_smoke": "real opt-in WeChat submit smoke passed",
    "testpypi_install": (
        "all packages installed from TestPyPI in a clean env and API smoke passed"
    ),
    "pypi_trusted_publisher": "PyPI Trusted Publisher is configured",
}

HELPER_RELEASE_REQUIRED_CHECKS = (
    "manifest",
    "identity",
    "endpoint",
    "token",
    "helper_app",
)

EXPECTED_TRUSTED_PUBLISHER = {
    "owner": "zhanghao1903",
    "repository": "macos-computer-use",
    "workflow": "release.yml",
    "environment": None,
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    summary: str

    @property
    def failed(self) -> bool:
        return self.status == "fail"


def run_preflight(
    root: Path,
    *,
    wheel_dir: Path | None = None,
    sdist_dir: Path | None = None,
    proof_path: Path | None = None,
    helper_doctor_report_path: Path | None = None,
    textedit_smoke_report_path: Path | None = None,
    wechat_smoke_report_paths: tuple[Path, ...] = (),
    testpypi_install_report_path: Path | None = None,
    trusted_publisher_report_path: Path | None = None,
    require_external: bool = False,
) -> list[CheckResult]:
    root = root.resolve()
    proof: dict[str, Any] = {}
    proof_source_results: list[CheckResult] = []
    if proof_path is not None:
        _merge_external_proof(
            proof,
            proof_source_results,
            source_name="release-proof",
            path=proof_path,
            loader=_load_proof,
        )
    if helper_doctor_report_path is not None:
        _merge_external_proof(
            proof,
            proof_source_results,
            source_name="helper-doctor-report",
            path=helper_doctor_report_path,
            loader=_load_helper_doctor_proof,
        )
    if textedit_smoke_report_path is not None:
        _merge_external_proof(
            proof,
            proof_source_results,
            source_name="textedit-smoke-report",
            path=textedit_smoke_report_path,
            loader=_load_textedit_smoke_proof,
        )
    for index, wechat_smoke_report_path in enumerate(wechat_smoke_report_paths, 1):
        _merge_external_proof(
            proof,
            proof_source_results,
            source_name=f"wechat-smoke-report:{index}",
            path=wechat_smoke_report_path,
            loader=_load_wechat_smoke_proof,
        )
    if testpypi_install_report_path is not None:
        _merge_external_proof(
            proof,
            proof_source_results,
            source_name="testpypi-install-report",
            path=testpypi_install_report_path,
            loader=lambda path: _load_testpypi_install_proof(root, path),
        )
    if trusted_publisher_report_path is not None:
        _merge_external_proof(
            proof,
            proof_source_results,
            source_name="trusted-publisher-report",
            path=trusted_publisher_report_path,
            loader=_load_trusted_publisher_proof,
        )
    results: list[CheckResult] = []
    results.extend(_check_required_paths(root))
    results.extend(_check_markdown_json_examples(root))
    results.extend(_check_toml_config_examples(root))
    results.extend(_check_projects(root))
    results.extend(_check_public_api(root))
    results.extend(_check_source_boundaries(root))
    results.extend(_check_module_entrypoints(root))
    results.extend(_check_helper_template_smoke(root))
    results.extend(_check_dry_run_smokes(root))
    results.extend(_check_local_service_smoke(root))
    results.extend(_check_workflows(root))
    if wheel_dir is not None:
        results.extend(_check_wheel_dir(root, wheel_dir))
    if sdist_dir is not None:
        results.extend(_check_sdist_dir(root, sdist_dir))
    results.extend(proof_source_results)
    results.extend(
        _check_external_proofs(
            proof,
            require_external=require_external,
        )
    )
    return results


def _merge_external_proof(
    proof: dict[str, Any],
    results: list[CheckResult],
    *,
    source_name: str,
    path: Path,
    loader: Callable[[Path], dict[str, Any]],
) -> None:
    try:
        proof.update(loader(path))
    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        results.append(
            CheckResult(
                name=f"external-proof-source:{source_name}",
                status="fail",
                summary=f"failed to load {path}: {exc}",
            )
        )


def print_text_report(results: list[CheckResult]) -> None:
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.summary}")


def has_failures(results: list[CheckResult]) -> bool:
    return any(result.failed for result in results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run local release preflight checks for app-control tools."
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
        help=(
            "Optional directory containing built wheel artifacts. Verifies wheel "
            "metadata, py.typed markers, schemas, and console entry points."
        ),
    )
    parser.add_argument(
        "--sdist-dir",
        type=Path,
        help=(
            "Optional directory containing built sdist artifacts. Verifies sdist "
            "metadata and source-package contents."
        ),
    )
    parser.add_argument(
        "--proof",
        type=Path,
        help="Optional JSON file with external release proof booleans.",
    )
    parser.add_argument(
        "--helper-doctor-report",
        type=Path,
        help=(
            "Optional JSON output from `computer-use-macos helper doctor --json`; "
            "fills helper app doctor proof. Signature/notarization checks remain "
            "supported by doctor but are not required for the package release gate."
        ),
    )
    parser.add_argument(
        "--textedit-smoke-report",
        type=Path,
        help=(
            "Optional JSON output from `python -m "
            "computer_use_macos.examples.textedit_smoke`; fills real TextEdit "
            "smoke proof."
        ),
    )
    parser.add_argument(
        "--wechat-smoke-report",
        action="append",
        default=[],
        type=Path,
        help=(
            "Optional JSON output from `python -m "
            "wechat_desktop_tool.examples.wechat_smoke`; may be repeated."
        ),
    )
    parser.add_argument(
        "--testpypi-install-report",
        type=Path,
        help="Optional JSON report from clean TestPyPI install validation.",
    )
    parser.add_argument(
        "--trusted-publisher-report",
        type=Path,
        help="Optional JSON report confirming PyPI Trusted Publisher setup.",
    )
    parser.add_argument(
        "--require-external",
        action="store_true",
        help="Fail if external release proofs are missing or false.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable check results.",
    )
    args = parser.parse_args(argv)

    results = run_preflight(
        args.root,
        wheel_dir=args.wheel_dir,
        sdist_dir=args.sdist_dir,
        proof_path=args.proof,
        helper_doctor_report_path=args.helper_doctor_report,
        textedit_smoke_report_path=args.textedit_smoke_report,
        wechat_smoke_report_paths=tuple(args.wechat_smoke_report),
        testpypi_install_report_path=args.testpypi_install_report,
        trusted_publisher_report_path=args.trusted_publisher_report,
        require_external=args.require_external,
    )
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print_text_report(results)
    return 1 if has_failures(results) else 0


def _check_required_paths(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    required_paths = (
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        "packages/README.md",
        *LOCAL_DOCS,
        *LOCAL_SCRIPTS,
        *LOCAL_EXAMPLES,
        *LOCAL_TESTS,
        *PACKAGE_TESTS,
        *PACKAGE_MODULE_FILES,
        *PROTOCOL_SCHEMA_FILES,
        *(str(path) for path in PACKAGE_PROJECTS.values()),
        *(str(path / "__init__.py") for path in PACKAGE_SOURCES.values()),
        *(str(path / "py.typed") for path in PACKAGE_SOURCES.values()),
    )
    for relative in required_paths:
        path = root / relative
        results.append(
            CheckResult(
                name=f"path:{relative}",
                status="ok" if path.exists() else "fail",
                summary="exists" if path.exists() else "missing",
            )
        )
    return results


def _check_markdown_json_examples(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    validator: Any | None = None
    for relative in MARKDOWN_JSON_DOCS:
        path = root / relative
        if not path.exists():
            results.append(
                CheckResult(
                    name=f"docs-json:{relative}",
                    status="fail",
                    summary="missing",
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        examples = list(re.finditer(r"```json\n(.*?)\n```", text, re.S))
        failure: str | None = None
        protocol_examples = 0
        for index, match in enumerate(examples, start=1):
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                failure = f"example {index}: {exc.msg} at line {exc.lineno}"
                break
            try:
                if validator is None:
                    validator = _load_protocol_validator(root)
                protocol_examples += _validate_protocol_json_examples(
                    validator,
                    payload,
                )
            except Exception as exc:
                failure = f"example {index}: {type(exc).__name__}: {exc}"
                break
        results.append(
            CheckResult(
                name=f"docs-json:{relative}",
                status="ok" if failure is None else "fail",
                summary=(
                    f"{len(examples)} JSON example(s) valid, "
                    f"{protocol_examples} protocol payload(s) validated"
                    if failure is None
                    else failure
                ),
            )
        )
    return results


def _load_protocol_validator(root: Path) -> Any:
    source_path = root / "packages/app-control-protocol/src"
    old_path = list(sys.path)
    sys.path.insert(0, str(source_path))
    try:
        from app_control_protocol import validate_protocol_payload
    finally:
        sys.path = old_path
    return validate_protocol_payload


def _validate_protocol_json_examples(validator: Any, value: Any) -> int:
    count = 0
    if isinstance(value, dict):
        schema = value.get("schema")
        if isinstance(schema, str) and schema in PROTOCOL_SCHEMA_BY_ID:
            validator(PROTOCOL_SCHEMA_BY_ID[schema], value)
            count += 1
        for item in value.values():
            count += _validate_protocol_json_examples(validator, item)
    elif isinstance(value, list):
        for item in value:
            count += _validate_protocol_json_examples(validator, item)
    return count


def _check_toml_config_examples(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    config_loader = _load_config_models(root)
    load_app_control_config = config_loader["load_app_control_config"]
    app_control_config = config_loader["AppControlConfig"]

    example_path = root / "examples/app-control.toml"
    try:
        load_app_control_config(example_path, env={})
    except Exception as exc:
        results.append(
            CheckResult(
                name="config-toml:examples/app-control.toml",
                status="fail",
                summary=f"{type(exc).__name__}: {exc}",
            )
        )
    else:
        results.append(
            CheckResult(
                name="config-toml:examples/app-control.toml",
                status="ok",
                summary="loads as AppControlConfig",
            )
        )

    for relative in MARKDOWN_TOML_DOCS:
        path = root / relative
        if not path.exists():
            results.append(
                CheckResult(
                    name=f"docs-toml:{relative}",
                    status="fail",
                    summary="missing",
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        examples = list(re.finditer(r"```toml\n(.*?)\n```", text, re.S))
        failure: str | None = None
        config_examples = 0
        for index, match in enumerate(examples, start=1):
            try:
                payload = tomllib.loads(match.group(1))
            except tomllib.TOMLDecodeError as exc:
                failure = f"example {index}: {exc}"
                break
            if _looks_like_app_control_config(payload):
                config_examples += 1
                try:
                    app_control_config.from_dict(payload)
                except Exception as exc:
                    failure = f"example {index}: {type(exc).__name__}: {exc}"
                    break
        results.append(
            CheckResult(
                name=f"docs-toml:{relative}",
                status="ok" if failure is None else "fail",
                summary=(
                    f"{len(examples)} TOML example(s) valid, "
                    f"{config_examples} AppControlConfig example(s) validated"
                    if failure is None
                    else failure
                ),
            )
        )
    return results


def _load_config_models(root: Path) -> dict[str, Any]:
    source_path = root / "packages/app-control-protocol/src"
    old_path = list(sys.path)
    sys.path.insert(0, str(source_path))
    try:
        from app_control_protocol import AppControlConfig, load_app_control_config
    finally:
        sys.path = old_path
    return {
        "AppControlConfig": AppControlConfig,
        "load_app_control_config": load_app_control_config,
    }


def _looks_like_app_control_config(payload: dict[str, Any]) -> bool:
    keys = set(payload)
    return bool(keys & APP_CONTROL_CONFIG_SECTIONS)


def _check_projects(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    versions: dict[str, str] = {}
    for expected_name, relative in PACKAGE_PROJECTS.items():
        project = _project_table(root / relative)
        actual_name = project.get("name")
        versions[expected_name] = _string(project.get("version"))
        results.append(
            CheckResult(
                name=f"project-name:{expected_name}",
                status="ok" if actual_name == expected_name else "fail",
                summary=f"name={actual_name!r}",
            )
        )
        deps = tuple(project.get("dependencies", ()))
        expected_deps = EXPECTED_RUNTIME_DEPS[expected_name]
        results.append(
            CheckResult(
                name=f"runtime-deps:{expected_name}",
                status="ok" if deps == expected_deps else "fail",
                summary=f"dependencies={list(deps)!r}",
            )
        )
        package_name = _import_package_for_project(expected_name)
        package_data = _package_data(root / relative)
        py_typed = "py.typed" in package_data.get(package_name, ())
        results.append(
            CheckResult(
                name=f"py-typed:{expected_name}",
                status="ok" if py_typed else "fail",
                summary=f"{package_name} declares py.typed",
            )
        )
        for package_data_item in EXPECTED_PACKAGE_DATA.get(expected_name, ()):
            present = package_data_item in package_data.get(package_name, ())
            results.append(
                CheckResult(
                    name=f"package-data:{expected_name}:{package_data_item}",
                    status="ok" if present else "fail",
                    summary=(
                        f"{package_name} includes {package_data_item}"
                        if present
                        else f"{package_name} missing {package_data_item}"
                    ),
                )
            )
        expected_scripts = EXPECTED_SCRIPTS.get(expected_name, {})
        actual_scripts = project.get("scripts", {})
        for script, target in expected_scripts.items():
            results.append(
                CheckResult(
                    name=f"script:{script}",
                    status="ok" if actual_scripts.get(script) == target else "fail",
                    summary=f"target={actual_scripts.get(script)!r}",
                )
            )
    version_values = set(versions.values())
    versions_match = len(version_values) == 1 and "" not in version_values
    results.append(
        CheckResult(
            name="version-consistency",
            status="ok" if versions_match else "fail",
            summary=f"versions={versions}",
        )
    )
    return results


def _check_public_api(root: Path) -> list[CheckResult]:
    source_paths = (
        root / "packages/app-control-protocol/src",
        root / "packages/computer-use-macos/src",
        root / "packages/wechat-desktop-tool/src",
    )
    old_path = list(sys.path)
    sys.path[:0] = [str(path) for path in source_paths]
    try:
        modules = {
            project_name: __import__(_import_package_for_project(project_name))
            for project_name in PACKAGE_PROJECTS
        }
        results: list[CheckResult] = []
        for project_name, attrs in EXPECTED_PUBLIC_API.items():
            module = modules[project_name]
            missing = [attr for attr in attrs if not hasattr(module, attr)]
            results.append(
                CheckResult(
                    name=f"public-api:{project_name}",
                    status="ok" if not missing else "fail",
                    summary=(
                        "all expected public objects import"
                        if not missing
                        else f"missing {missing!r}"
                    ),
        )
            )
        results.extend(_check_command_builder_api(modules))
        results.extend(_check_service_envelope_api(modules))
        results.extend(_check_observer_surface(modules))
        return results
    except Exception as exc:
        return [
            CheckResult(
                name="public-api",
                status="fail",
                summary=f"{type(exc).__name__}: {exc}",
            )
        ]
    finally:
        sys.path = old_path


def _check_command_builder_api(modules: dict[str, Any]) -> list[CheckResult]:
    protocol = modules["app-control-protocol"]
    computer_use = modules["computer-use-macos"]
    wechat = modules["wechat-desktop-tool"]
    checks = {
        "computer-use-macos": [
            computer_use.readiness_command().to_dict(),
            computer_use.observe_command(target_app="TextEdit").to_dict(),
            computer_use.open_app_command("TextEdit").to_dict(),
            computer_use.focus_app_command("TextEdit").to_dict(),
            computer_use.click_accessibility_command(
                {"role": "button", "name": "OK"},
                target_app="TextEdit",
            ).to_dict(),
            computer_use.click_coordinate_command(10, 20).to_dict(),
            computer_use.type_text_command("hello").to_dict(),
            computer_use.press_key_command("Return").to_dict(),
            computer_use.hotkey_command(("Command", "K")).to_dict(),
            computer_use.wait_command(seconds=0.1).to_dict(),
        ],
        "wechat-desktop-tool": [
            wechat.open_wechat_command().to_dict(),
            wechat.focus_contact_command("File Transfer").to_dict(),
            wechat.observe_current_chat_command().to_dict(),
            wechat.read_visible_messages_command(limit=5).to_dict(),
            wechat.draft_message_command("hello").to_dict(),
            wechat.submit_draft_command().to_dict(),
            wechat.send_message_command(
                contact="File Transfer",
                message="hello",
            ).to_dict(),
        ],
    }
    results: list[CheckResult] = []
    for project_name, payloads in checks.items():
        try:
            for payload in payloads:
                protocol.validate_protocol_payload("command", payload)
            passed = True
            operations = ", ".join(str(payload["operation"]) for payload in payloads)
            summary = f"validated {operations}"
        except Exception as exc:
            passed = False
            summary = f"{type(exc).__name__}: {exc}"
        results.append(
            CheckResult(
                name=f"command-builder:{project_name}",
                status="ok" if passed else "fail",
                summary=summary,
            )
        )
    return results


def _check_service_envelope_api(modules: dict[str, Any]) -> list[CheckResult]:
    protocol = modules["app-control-protocol"]
    try:
        command = protocol.ToolCommand(
            command_id="cmd_service",
            tool="macos.computer_use",
            operation="readiness",
        )
        observation = protocol.ToolObservation.ok(
            command_id="cmd_service",
            tool="macos.computer_use",
            operation="readiness",
            summary="ready",
        )
        error = protocol.ToolError(
            failure_kind="not_ready",
            message="not ready",
            retryable=True,
            phase="readiness",
            operation="readiness",
        )
        event = protocol.ToolEvent(
            command_id="cmd_service",
            seq=0,
            event_type=protocol.ToolEventType.STARTED,
        )
        request_payloads = [
            protocol.ServiceRequest.run(command, token="local-token").to_dict(),
            protocol.ServiceRequest.submit(
                command,
                request_id="req_submit",
                token="local-token",
            ).to_dict(),
            protocol.ServiceRequest.poll(
                "req_submit",
                token="local-token",
            ).to_dict(),
            protocol.ServiceRequest.stream(
                command,
                token="local-token",
            ).to_dict(),
        ]
        response_payloads = [
            protocol.ServiceResponse.complete(
                observation,
                request_id="req_complete",
            ).to_dict(),
            protocol.ServiceResponse.not_found(
                request_id="req_missing",
            ).to_dict(),
            protocol.ServiceResponse.failed(
                error,
                request_id="req_failed",
            ).to_dict(),
        ]
        event_payload = protocol.ServiceEventEnvelope(
            request_id="req_event",
            event=event,
        ).to_dict()
        helper_request_payload = {
            "schema": protocol.HELPER_REQUEST_SCHEMA,
            "token": "local-token",
            "command": command.to_dict(),
            "metadata": {"bundleId": "com.example.helper"},
        }
        helper_response_payload = {
            "schema": protocol.HELPER_RESPONSE_SCHEMA,
            "success": True,
            "observation": observation.to_dict(),
        }

        for payload in request_payloads:
            protocol.validate_protocol_payload("service_request", payload)
        for payload in response_payloads:
            protocol.validate_protocol_payload("service_response", payload)
        protocol.validate_protocol_payload("service_event", event_payload)
        protocol.validate_protocol_payload("helper_request", helper_request_payload)
        protocol.validate_protocol_payload("helper_response", helper_response_payload)

        return [
            CheckResult(
                name="service-envelope:app-control-protocol",
                status="ok",
                summary=(
                    "validated run/submit/poll/stream, helper, and response "
                    "envelopes"
                ),
            )
        ]
    except Exception as exc:
        return [
            CheckResult(
                name="service-envelope:app-control-protocol",
                status="fail",
                summary=f"{type(exc).__name__}: {exc}",
            )
        ]


def _check_observer_surface(modules: dict[str, Any]) -> list[CheckResult]:
    protocol = modules["app-control-protocol"]
    computer_use = modules["computer-use-macos"]
    wechat = modules["wechat-desktop-tool"]
    results: list[CheckResult] = []

    try:
        stream = StringIO()
        observer = protocol.build_logging_observer(
            protocol.LoggingConfig(json=True, redact_text=True),
            stream=stream,
        )
        event = protocol.ToolEvent(
            command_id="cmd_observer",
            seq=0,
            event_type=protocol.ToolEventType.STARTED,
            phase="draft_message",
            data={"message": "secret text"},
        )
        observer.on_event(event)
        output = stream.getvalue()
        passed = "[redacted]" in output and "secret text" not in output
        summary = (
            "ToolObserver export and logging observer redaction work"
            if passed
            else "logging observer did not redact sensitive event data"
        )
    except Exception as exc:
        passed = False
        summary = f"{type(exc).__name__}: {exc}"
    results.append(
        CheckResult(
            name="observer-surface:app-control-protocol",
            status="ok" if passed else "fail",
            summary=summary,
        )
    )

    for project_name, callables in (
        (
            "computer-use-macos",
            (
                computer_use.MacOSComputerUseClient.run_command,
                computer_use.MacOSComputerUseClient.run_stream,
                computer_use.HelperTransportClient.run_command,
                computer_use.HelperTransportClient.run_stream,
            ),
        ),
        (
            "wechat-desktop-tool",
            (
                wechat.WeChatDesktopTool.run_command,
                wechat.WeChatDesktopTool.run_stream,
            ),
        ),
    ):
        try:
            missing = [
                callable_obj.__qualname__
                for callable_obj in callables
                if "observer" not in inspect.signature(callable_obj).parameters
            ]
            passed = not missing
            summary = (
                "run_command/run_stream accept observer callbacks"
                if passed
                else f"missing observer parameter on {missing!r}"
            )
        except Exception as exc:
            passed = False
            summary = f"{type(exc).__name__}: {exc}"
        results.append(
            CheckResult(
                name=f"observer-surface:{project_name}",
                status="ok" if passed else "fail",
                summary=summary,
            )
        )
    return results


def _check_module_entrypoints(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, module_args, pythonpath_paths, expected_terms in MODULE_ENTRYPOINT_CHECKS:
        command = [sys.executable, "-m", *module_args]
        env_updates = {"PYTHONPATH": _pythonpath(root, *pythonpath_paths)}
        try:
            output = _run_help_command(root, command, env_updates=env_updates)
            missing = [term for term in expected_terms if term not in output]
            passed = not missing
            summary = (
                "module entrypoint help is available"
                if passed
                else f"help output missing {missing!r}"
            )
        except Exception as exc:
            passed = False
            summary = f"{type(exc).__name__}: {exc}"
        results.append(
            CheckResult(
                name=f"module-entrypoint:{name}",
                status="ok" if passed else "fail",
                summary=summary,
            )
        )
    return results


def _run_help_command(
    root: Path,
    command: list[str],
    *,
    env_updates: dict[str, str],
) -> str:
    env = os.environ.copy()
    env.update(env_updates)
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(
            f"command exited {result.returncode}: {output.strip()}"
        )
    return output


def _check_helper_template_smoke(root: Path) -> list[CheckResult]:
    env_updates = {
        "PYTHONPATH": _pythonpath(
            root,
            "packages/app-control-protocol/src",
            "packages/computer-use-macos/src",
        )
    }
    try:
        with tempfile.TemporaryDirectory(prefix="app-control-helper-smoke-") as tmpdir:
            workspace = Path(tmpdir)
            template_dir = workspace / "helper"
            init_payload = _run_json_command(
                root,
                [
                    sys.executable,
                    "-m",
                    "computer_use_macos",
                    "helper",
                    "init",
                    str(template_dir),
                    "--name",
                    "Example Helper",
                    "--bundle-id",
                    "com.example.helper",
                    "--json",
                ],
                env_updates=env_updates,
            )
            _validate_helper_init_payload(init_payload, template_dir)

            build_payload = _run_json_command(
                root,
                [
                    sys.executable,
                    "-m",
                    "computer_use_macos",
                    "helper",
                    "build",
                    str(template_dir),
                    "--json",
                ],
                env_updates=env_updates,
            )
            _validate_helper_build_payload(build_payload)

            manifest_path = template_dir / "helper_config.json"
            token_path = workspace / "helper.token"
            token_path.write_text("local-token", encoding="utf-8")
            manifest = _json_file(manifest_path)
            manifest["tokenRef"] = str(token_path)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            doctor_payload = _run_json_command(
                root,
                [
                    sys.executable,
                    "-m",
                    "computer_use_macos",
                    "helper",
                    "doctor",
                    str(template_dir),
                    "--expected-bundle-id",
                    "com.example.helper",
                    "--json",
                ],
                env_updates=env_updates,
            )
            _validate_helper_doctor_payload(doctor_payload)
    except Exception as exc:
        return [
            CheckResult(
                name="helper-template-smoke:computer-use-macos",
                status="fail",
                summary=f"{type(exc).__name__}: {exc}",
            )
        ]
    return [
        CheckResult(
            name="helper-template-smoke:computer-use-macos",
            status="ok",
            summary="helper init/build/doctor CLI lifecycle passed",
        )
    ]


def _validate_helper_init_payload(payload: dict[str, Any], template_dir: Path) -> None:
    if payload.get("outputDir") != str(template_dir):
        raise ValueError("helper init outputDir did not match requested directory")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise TypeError("helper init JSON must include generated files")
    for relative in (
        "README.md",
        "Info.plist.template",
        "entitlements.plist",
        "helper_config.json",
        "src/helper_main.py",
        "build.py",
        "sign.sh",
        "notarize.sh",
    ):
        if not (template_dir / relative).exists():
            raise ValueError(f"helper init did not create {relative}")
    manifest = _json_file(template_dir / "helper_config.json")
    if manifest.get("bundleId") != "com.example.helper":
        raise ValueError("helper manifest bundleId did not match init input")
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        raise TypeError("helper manifest metadata must be an object")
    if "allowedApps" not in metadata or "allowedAppBundleIds" not in metadata:
        raise ValueError("helper manifest missing allowlist metadata")


def _validate_helper_build_payload(payload: dict[str, Any]) -> Path:
    app_path = payload.get("appPath")
    if not isinstance(app_path, str) or not app_path:
        raise TypeError("helper build JSON must include appPath")
    path = Path(app_path)
    if path.suffix != ".app" or not path.exists():
        raise ValueError(f"helper build appPath is not an app bundle: {app_path}")
    for relative in (
        "Contents/Info.plist",
        "Contents/MacOS/helper",
        "Contents/Resources/helper_config.json",
    ):
        if not (path / relative).exists():
            raise ValueError(f"helper app missing {relative}")
    return path


def _validate_helper_doctor_payload(payload: dict[str, Any]) -> None:
    if payload.get("status") != "ready":
        raise ValueError(f"helper doctor status was not ready: {payload.get('status')}")
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise TypeError("helper doctor JSON must include checks")
    statuses = {
        check.get("name"): check.get("status")
        for check in checks
        if isinstance(check, dict)
    }
    for name in ("manifest", "identity", "endpoint", "token", "helper_app"):
        if statuses.get(name) != "ok":
            raise ValueError(f"helper doctor check {name!r} was {statuses.get(name)!r}")


def _json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _check_dry_run_smokes(root: Path) -> list[CheckResult]:
    checks = (
        (
            "textedit",
            [
                sys.executable,
                "-m",
                "computer_use_macos.examples.textedit_smoke",
            ],
            {
                "COMPUTER_USE_DRY_RUN": "1",
                "PYTHONPATH": _pythonpath(
                    root,
                    "packages/app-control-protocol/src",
                    "packages/computer-use-macos/src",
                ),
            },
            _validate_textedit_dry_run,
        ),
        (
            "wechat-focus-draft",
            [
                sys.executable,
                "-m",
                "wechat_desktop_tool",
                "examples",
                "send-message",
                "--contact",
                "File Transfer",
                "--message",
                "hello",
                "--dry-run",
            ],
            {
                "PYTHONPATH": _pythonpath(
                    root,
                    "packages/app-control-protocol/src",
                    "packages/wechat-desktop-tool/src",
                ),
            },
            _validate_wechat_dry_run,
        ),
        (
            "wechat-example-module-focus-draft",
            [
                sys.executable,
                "-m",
                "wechat_desktop_tool.examples.wechat_smoke",
            ],
            {
                "WECHAT_TOOL_CONTACT": "File Transfer",
                "WECHAT_TOOL_MESSAGE": "hello",
                "WECHAT_TOOL_DRY_RUN": "1",
                "PYTHONPATH": _pythonpath(
                    root,
                    "packages/app-control-protocol/src",
                    "packages/wechat-desktop-tool/src",
                ),
            },
            _validate_wechat_dry_run,
        ),
    )
    results: list[CheckResult] = []
    for name, command, env_updates, validator in checks:
        try:
            payload = _run_json_command(root, command, env_updates=env_updates)
            validator(payload, root)
        except Exception as exc:
            results.append(
                CheckResult(
                    name=f"dry-run-smoke:{name}",
                    status="fail",
                    summary=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"dry-run-smoke:{name}",
                    status="ok",
                    summary="entrypoint produced expected dry-run command JSON",
                )
            )
    return results


def _check_local_service_smoke(root: Path) -> list[CheckResult]:
    source_paths = (
        root / "packages/app-control-protocol/src",
        root / "packages/computer-use-macos/src",
    )
    old_path = list(sys.path)
    sys.path[:0] = [str(path) for path in source_paths]
    try:
        from app_control_protocol import (
            ToolCommand,
            ToolEvent,
            ToolEventType,
            ToolObservation,
            validate_protocol_payload,
        )
        from computer_use_macos.service import (
            LocalCommandService,
            LocalServiceError,
            UnixSocketCommandService,
            UnixSocketServiceClient,
        )

        class SmokeAppControl:
            def run_command(
                self,
                command: object,
                *,
                observer: object | None = None,
            ) -> ToolObservation:
                tool_command = _smoke_tool_command(command, ToolCommand)
                if observer is not None:
                    handler = getattr(observer, "on_event", None)
                    if callable(handler):
                        handler(
                            ToolEvent(
                                command_id=tool_command.command_id,
                                seq=0,
                                event_type=ToolEventType.STARTED,
                                phase=tool_command.operation,
                                summary=f"started {tool_command.operation}",
                            )
                        )
                return ToolObservation.ok(
                    command_id=tool_command.command_id,
                    tool=tool_command.tool,
                    operation=tool_command.operation,
                    summary=f"ran {tool_command.operation}",
                    observation={"operation": tool_command.operation},
                )

            def run_stream(
                self,
                command: object,
                *,
                observer: object | None = None,
            ) -> object:
                tool_command = _smoke_tool_command(command, ToolCommand)
                started = ToolEvent(
                    command_id=tool_command.command_id,
                    seq=0,
                    event_type=ToolEventType.STARTED,
                    phase=tool_command.operation,
                    summary=f"started {tool_command.operation}",
                )
                if observer is not None:
                    handler = getattr(observer, "on_event", None)
                    if callable(handler):
                        handler(started)
                yield started
                observation = self.run_command(tool_command)
                yield ToolEvent(
                    command_id=tool_command.command_id,
                    seq=1,
                    event_type=ToolEventType.OBSERVATION,
                    phase=tool_command.operation,
                    status=observation.status,
                    summary=observation.summary,
                    data={"observation": observation.to_dict()},
                )

        with tempfile.TemporaryDirectory(prefix="app-control-service-smoke-") as tmpdir:
            socket_path = Path(tmpdir) / "app-control.sock"
            service = LocalCommandService(SmokeAppControl(), token="secret")
            server = UnixSocketCommandService(socket_path, service)
            thread = None
            try:
                thread = server.serve_in_thread()
            except LocalServiceError as exc:
                if "Operation not permitted" in str(exc):
                    return [
                        CheckResult(
                            name="local-service-smoke:computer-use-macos",
                            status="warn",
                            summary=(
                                "Unix socket bind is not permitted in this "
                                "environment"
                            ),
                        )
                    ]
                raise
            try:
                client = UnixSocketServiceClient(
                    socket_path,
                    token="secret",
                    timeout=2.0,
                )
                command = ToolCommand(
                    command_id="cmd_service_smoke",
                    tool="macos.computer_use",
                    operation="readiness",
                )
                run_responses = client.run_command(command.to_dict())
                submit_responses = client.run_command(
                    command.to_dict(),
                    action="submit",
                    request_id="req_service_smoke",
                )
                poll_response = client.poll("req_service_smoke")
                stream_responses = client.run_command(
                    command.to_dict(),
                    action="stream",
                    request_id="req_service_stream",
                )
            finally:
                server.shutdown()
                if thread is not None:
                    thread.join(timeout=2.0)

        _validate_service_smoke_responses(
            run_responses,
            submit_responses,
            poll_response,
            stream_responses,
            validate_protocol_payload,
        )
    except Exception as exc:
        return [
            CheckResult(
                name="local-service-smoke:computer-use-macos",
                status="fail",
                summary=f"{type(exc).__name__}: {exc}",
            )
        ]
    finally:
        sys.path = old_path
    return [
        CheckResult(
            name="local-service-smoke:computer-use-macos",
            status="ok",
            summary="Unix socket run, submit/poll, and stream paths passed",
        )
    ]


def _smoke_tool_command(command: object, tool_command_cls: type[Any]) -> Any:
    if isinstance(command, Mapping):
        return tool_command_cls.from_dict(dict(command))
    return command


def _validate_service_smoke_responses(
    run_responses: list[dict[str, Any]],
    submit_responses: list[dict[str, Any]],
    poll_response: dict[str, Any],
    stream_responses: list[dict[str, Any]],
    validate_protocol_payload: Callable[[str, Mapping[str, Any]], Any],
) -> None:
    if len(run_responses) != 1 or run_responses[0].get("status") != "complete":
        raise ValueError(f"unexpected run response: {run_responses!r}")
    if len(submit_responses) != 1 or submit_responses[0].get("status") != "complete":
        raise ValueError(f"unexpected submit response: {submit_responses!r}")
    if poll_response.get("status") != "complete":
        raise ValueError(f"unexpected poll response: {poll_response!r}")
    stream_statuses = [
        response.get("status")
        for response in stream_responses
        if isinstance(response, Mapping)
    ]
    if stream_statuses != ["event", "event", "complete"]:
        raise ValueError(f"unexpected stream responses: {stream_responses!r}")

    for response in (*run_responses, *submit_responses, poll_response):
        validate_protocol_payload("service_response", response)
        observation = response.get("observation")
        if isinstance(observation, Mapping):
            validate_protocol_payload("observation", observation)
    for response in stream_responses:
        schema_name = (
            "service_event"
            if response.get("status") == "event"
            else "service_response"
        )
        validate_protocol_payload(schema_name, response)


def _run_json_command(
    root: Path,
    command: list[str],
    *,
    env_updates: dict[str, str],
) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(env_updates)
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"command exited {result.returncode}: {stderr}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise TypeError("dry-run output must be a JSON object")
    return payload


def _pythonpath(root: Path, *relative_paths: str) -> str:
    values = [str(root / relative_path) for relative_path in relative_paths]
    current = os.environ.get("PYTHONPATH")
    if current:
        values.append(current)
    return os.pathsep.join(values)


def _validate_textedit_dry_run(payload: dict[str, Any], root: Path) -> None:
    if payload.get("dryRun") is not True:
        raise ValueError("TextEdit smoke did not report dryRun=true")
    commands = payload.get("commands")
    if not isinstance(commands, list):
        raise TypeError("TextEdit smoke commands must be a list")
    operations = [command.get("operation") for command in commands if isinstance(command, dict)]
    expected = ["readiness", "open_app", "focus_app", "observe", "type_text"]
    if operations != expected:
        raise ValueError(f"unexpected TextEdit dry-run operations: {operations!r}")
    _validate_dry_run_commands(commands, root)


def _validate_wechat_dry_run(payload: dict[str, Any], root: Path) -> None:
    if payload.get("submitted") is not False:
        raise ValueError("WeChat dry-run focus/draft smoke must not submit")
    if not isinstance(payload.get("focus"), dict) or not payload["focus"].get("success"):
        raise ValueError("WeChat dry-run focus phase did not succeed")
    if not isinstance(payload.get("draft"), dict) or not payload["draft"].get("success"):
        raise ValueError("WeChat dry-run draft phase did not succeed")
    commands = payload.get("appControlCommands")
    if not isinstance(commands, list):
        raise TypeError("WeChat dry-run appControlCommands must be a list")
    operations = [command.get("operation") for command in commands if isinstance(command, dict)]
    expected = [
        "open_app",
        "observe",
        "hotkey",
        "hotkey",
        "press_key",
        "type_text",
        "press_key",
        "observe",
        "type_text",
    ]
    if operations != expected:
        raise ValueError(f"unexpected WeChat dry-run operations: {operations!r}")
    _validate_dry_run_commands(commands, root)


def _validate_dry_run_commands(commands: list[Any], root: Path) -> None:
    validate_protocol_payload = _load_protocol_validator(root)

    for index, command in enumerate(commands, start=1):
        if not isinstance(command, dict):
            raise TypeError(f"command {index} must be a JSON object")
        validate_protocol_payload("command", command)


def _check_source_boundaries(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for package_name, relative in PACKAGE_SOURCES.items():
        source = root / relative
        terms = (*COMMON_BANNED_TERMS, *PACKAGE_BANNED_TERMS.get(package_name, ()))
        matches = _find_terms(source, terms)
        results.append(
            CheckResult(
                name=f"source-boundary:{package_name}",
                status="ok" if not matches else "fail",
                summary="no forbidden source terms" if not matches else matches[0],
            )
        )
    return results


def _check_workflows(root: Path) -> list[CheckResult]:
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    workflow_checks = {
        "ci-runs-root-tests": "python -m unittest discover -s tests" in ci,
        "ci-runs-protocol-tests": "packages/app-control-protocol/tests" in ci,
        "ci-runs-computer-use-tests": "packages/computer-use-macos/tests" in ci,
        "ci-runs-wechat-tests": "packages/wechat-desktop-tool/tests" in ci,
        "ci-builds-all-packages": all(
            item in ci
            for item in (
                "packages/app-control-protocol",
                "packages/computer-use-macos",
                "packages/wechat-desktop-tool",
            )
        ),
        "release-has-oidc": "id-token: write" in release,
        "release-publishes-pypi": "pypa/gh-action-pypi-publish" in release,
        "release-builds-all-packages": all(
            item in release
            for item in (
                "packages/app-control-protocol",
                "packages/computer-use-macos",
                "packages/wechat-desktop-tool",
            )
        ),
        "ci-verifies-wheel-contents": (
            "python scripts/release_preflight.py --wheel-dir dist" in ci
        ),
        "ci-verifies-sdist-contents": (
            "python scripts/release_preflight.py --wheel-dir dist-check --sdist-dir dist-check"
            in ci
        ),
        "release-verifies-wheel-contents": (
            "python scripts/release_preflight.py --wheel-dir dist --sdist-dir dist"
            in release
        ),
        "release-verifies-sdist-contents": (
            "--sdist-dir dist" in release
        ),
        "release-verifies-tag-version": (
            "python scripts/release_tag_check.py --tag" in release
            and "github.event.release.tag_name" in release
        ),
        "release-downloads-external-proof-assets": all(
            item in release
            for item in (
                "gh release download",
                "helper-doctor.json",
                "textedit-smoke.json",
                "wechat-focus-draft-smoke.json",
                "wechat-submit-smoke.json",
                "testpypi-install.json",
                "trusted-publisher.json",
                "release-proof.json",
                "test -f release-proof/helper-doctor.json",
                "test -f release-proof/textedit-smoke.json",
                "test -f release-proof/wechat-focus-draft-smoke.json",
                "test -f release-proof/wechat-submit-smoke.json",
                "test -f release-proof/testpypi-install.json",
                "test -f release-proof/trusted-publisher.json",
                "test -f release-proof/release-proof.json",
            )
        ),
        "release-requires-external-proof-preflight": all(
            item in release
            for item in (
                "--helper-doctor-report",
                "--textedit-smoke-report",
                "--wechat-smoke-report",
                "--testpypi-install-report",
                "--trusted-publisher-report",
                "--proof",
                "--require-external",
            )
        ),
    }
    return [
        CheckResult(
            name=f"workflow:{name}",
            status="ok" if passed else "fail",
            summary="configured" if passed else "missing",
        )
        for name, passed in workflow_checks.items()
    ]


def _check_external_proofs(
    proof: dict[str, Any],
    *,
    require_external: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for key, description in EXTERNAL_PROOFS.items():
        passed = proof.get(key) is True
        status = "ok" if passed else ("fail" if require_external else "warn")
        summary = "verified" if passed else f"not verified: {description}"
        results.append(
            CheckResult(
                name=f"external-proof:{key}",
                status=status,
                summary=summary,
            )
        )
    return results


def _project_table(path: Path) -> dict[str, Any]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"{path} is missing [project]")
    return project


def _package_data(path: Path) -> dict[str, tuple[str, ...]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    raw = data.get("tool", {}).get("setuptools", {}).get("package-data", {})
    return {
        str(package): tuple(str(item) for item in values)
        for package, values in raw.items()
        if isinstance(values, list)
    }


def _import_package_for_project(project_name: str) -> str:
    return project_name.replace("-", "_")


def _find_terms(source: Path, terms: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    if not source.exists():
        return [f"missing source path: {source}"]
    for path in source.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for term in terms:
            if term in text:
                matches.append(f"{path}:{term}")
    return matches


def _check_wheel_dir(root: Path, wheel_dir: Path) -> list[CheckResult]:
    wheel_root = wheel_dir if wheel_dir.is_absolute() else root / wheel_dir
    if not wheel_root.is_dir():
        return [
            CheckResult(
                name="wheel-dir",
                status="fail",
                summary=f"missing wheel directory: {wheel_root}",
            )
        ]

    results: list[CheckResult] = []
    for project_name, relative in PACKAGE_PROJECTS.items():
        project = _project_table(root / relative)
        version = _string(project.get("version"))
        import_name = _import_package_for_project(project_name)
        matches = sorted(wheel_root.glob(f"{import_name}-{version}-*.whl"))
        results.append(
            CheckResult(
                name=f"wheel:{project_name}",
                status="ok" if len(matches) == 1 else "fail",
                summary=(
                    matches[0].name
                    if len(matches) == 1
                    else f"expected 1 wheel, found {len(matches)}"
                ),
            )
        )
        if len(matches) != 1:
            continue
        results.extend(_check_wheel_file(matches[0], project_name, version))
    return results


def _check_wheel_file(
    wheel_path: Path,
    project_name: str,
    version: str,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        with zipfile.ZipFile(wheel_path) as wheel:
            names = set(wheel.namelist())
            metadata = _wheel_metadata(wheel, names)
            entry_points = _wheel_entry_points(wheel, names)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        return [
            CheckResult(
                name=f"wheel-readable:{project_name}",
                status="fail",
                summary=str(exc),
            )
        ]

    metadata_name = metadata.get("Name")
    metadata_version = metadata.get("Version")
    results.append(
        CheckResult(
            name=f"wheel-metadata-name:{project_name}",
            status="ok" if metadata_name == project_name else "fail",
            summary=f"Name={metadata_name!r}",
        )
    )
    results.append(
        CheckResult(
            name=f"wheel-metadata-version:{project_name}",
            status="ok" if metadata_version == version else "fail",
            summary=f"Version={metadata_version!r}",
        )
    )
    metadata_deps = tuple(metadata.get("Requires-Dist", ()))
    expected_deps = EXPECTED_RUNTIME_DEPS[project_name]
    results.append(
        CheckResult(
            name=f"wheel-metadata-deps:{project_name}",
            status="ok" if metadata_deps == expected_deps else "fail",
            summary=f"Requires-Dist={list(metadata_deps)!r}",
        )
    )

    for relative in EXPECTED_WHEEL_CONTENT[project_name]:
        present = relative in names
        results.append(
            CheckResult(
                name=f"wheel-content:{project_name}:{relative}",
                status="ok" if present else "fail",
                summary="included" if present else "missing",
            )
        )

    for script, target in EXPECTED_SCRIPTS.get(project_name, {}).items():
        expected_entry = f"{script} = {target}"
        present = expected_entry in entry_points
        results.append(
            CheckResult(
                name=f"wheel-entry-point:{script}",
                status="ok" if present else "fail",
                summary="included" if present else f"missing {expected_entry}",
            )
        )

    return results


def _check_sdist_dir(root: Path, sdist_dir: Path) -> list[CheckResult]:
    sdist_root = sdist_dir if sdist_dir.is_absolute() else root / sdist_dir
    if not sdist_root.is_dir():
        return [
            CheckResult(
                name="sdist-dir",
                status="fail",
                summary=f"missing sdist directory: {sdist_root}",
            )
        ]

    results: list[CheckResult] = []
    for project_name, relative in PACKAGE_PROJECTS.items():
        project = _project_table(root / relative)
        version = _string(project.get("version"))
        matches = _sdist_matches(sdist_root, project_name, version)
        results.append(
            CheckResult(
                name=f"sdist:{project_name}",
                status="ok" if len(matches) == 1 else "fail",
                summary=(
                    matches[0].name
                    if len(matches) == 1
                    else f"expected 1 sdist, found {len(matches)}"
                ),
            )
        )
        if len(matches) != 1:
            continue
        results.extend(_check_sdist_file(matches[0], project_name, version))
    return results


def _check_sdist_file(
    sdist_path: Path,
    project_name: str,
    version: str,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        with tarfile.open(sdist_path, "r:gz") as sdist:
            names = set(sdist.getnames())
            relative_names = _sdist_relative_names(names)
            metadata = _sdist_metadata(sdist, names)
    except (OSError, tarfile.TarError, ValueError) as exc:
        return [
            CheckResult(
                name=f"sdist-readable:{project_name}",
                status="fail",
                summary=str(exc),
            )
        ]

    metadata_name = metadata.get("Name")
    metadata_version = metadata.get("Version")
    results.append(
        CheckResult(
            name=f"sdist-metadata-name:{project_name}",
            status="ok" if metadata_name == project_name else "fail",
            summary=f"Name={metadata_name!r}",
        )
    )
    results.append(
        CheckResult(
            name=f"sdist-metadata-version:{project_name}",
            status="ok" if metadata_version == version else "fail",
            summary=f"Version={metadata_version!r}",
        )
    )
    metadata_deps = tuple(metadata.get("Requires-Dist", ()))
    expected_deps = EXPECTED_RUNTIME_DEPS[project_name]
    results.append(
        CheckResult(
            name=f"sdist-metadata-deps:{project_name}",
            status="ok" if metadata_deps == expected_deps else "fail",
            summary=f"Requires-Dist={list(metadata_deps)!r}",
        )
    )

    for relative in EXPECTED_SDIST_CONTENT[project_name]:
        present = relative in relative_names
        results.append(
            CheckResult(
                name=f"sdist-content:{project_name}:{relative}",
                status="ok" if present else "fail",
                summary="included" if present else "missing",
            )
        )
    return results


def _sdist_matches(sdist_root: Path, project_name: str, version: str) -> list[Path]:
    candidates: set[Path] = set()
    for distribution_name in {
        project_name,
        project_name.replace("-", "_"),
    }:
        candidates.update(sdist_root.glob(f"{distribution_name}-{version}.tar.gz"))
    return sorted(candidates)


def _sdist_relative_names(names: set[str]) -> set[str]:
    relative_names: set[str] = set()
    for name in names:
        if "/" not in name:
            continue
        _, relative = name.split("/", 1)
        if relative:
            relative_names.add(relative)
    return relative_names


def _sdist_metadata(
    sdist: tarfile.TarFile,
    names: set[str],
) -> dict[str, Any]:
    metadata_files = sorted(
        name
        for name in names
        if "/" in name and name.split("/", 1)[1] == "PKG-INFO"
    )
    if len(metadata_files) != 1:
        raise ValueError(f"expected one top-level PKG-INFO file, found {len(metadata_files)}")
    metadata_file = sdist.extractfile(metadata_files[0])
    if metadata_file is None:
        raise ValueError("failed to read sdist PKG-INFO")
    message = Parser().parsestr(metadata_file.read().decode("utf-8"))
    return {
        "Name": message.get("Name", ""),
        "Version": message.get("Version", ""),
        "Requires-Dist": tuple(message.get_all("Requires-Dist", [])),
    }


def _wheel_metadata(
    wheel: zipfile.ZipFile,
    names: set[str],
) -> dict[str, Any]:
    metadata_files = sorted(name for name in names if name.endswith(".dist-info/METADATA"))
    if len(metadata_files) != 1:
        raise ValueError(f"expected one METADATA file, found {len(metadata_files)}")
    message = Parser().parsestr(wheel.read(metadata_files[0]).decode("utf-8"))
    return {
        "Name": message.get("Name", ""),
        "Version": message.get("Version", ""),
        "Requires-Dist": tuple(message.get_all("Requires-Dist", [])),
    }


def _wheel_entry_points(
    wheel: zipfile.ZipFile,
    names: set[str],
) -> str:
    entry_point_files = sorted(
        name for name in names if name.endswith(".dist-info/entry_points.txt")
    )
    if not entry_point_files:
        return ""
    if len(entry_point_files) != 1:
        raise ValueError(
            f"expected at most one entry_points.txt file, found {len(entry_point_files)}"
        )
    return wheel.read(entry_point_files[0]).decode("utf-8")


def _load_proof(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("release proof JSON must be an object")
    unknown = sorted(str(key) for key in payload if key not in EXTERNAL_PROOFS)
    if unknown:
        raise ValueError(
            "release proof JSON contains unknown proof key(s): "
            + ", ".join(unknown)
        )
    non_bool = sorted(
        str(key)
        for key, value in payload.items()
        if not isinstance(value, bool)
    )
    if non_bool:
        raise ValueError(
            "release proof JSON values must be booleans for key(s): "
            + ", ".join(non_bool)
        )
    return payload


def _load_helper_doctor_proof(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("helper doctor report JSON must be an object")
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise ValueError("helper doctor report JSON must include a checks list")
    statuses: dict[str, str] = {}
    for item in checks:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        if isinstance(name, str) and isinstance(status, str):
            statuses[name] = status
    report_ok = payload.get("status") in {"ready", "warning"}
    required_ok = report_ok and all(
        statuses.get(name) == "ok" for name in HELPER_RELEASE_REQUIRED_CHECKS
    )
    return {"helper_app_doctor": required_ok}


def _load_textedit_smoke_proof(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("TextEdit smoke report JSON must be an object")
    if payload.get("dryRun") is not False:
        return {"textedit_smoke": False}
    if payload.get("success") is not True:
        return {"textedit_smoke": False}
    app = payload.get("app")
    observations = payload.get("observations")
    if not isinstance(app, str) or not app.strip():
        return {"textedit_smoke": False}
    if not isinstance(observations, list):
        return {"textedit_smoke": False}

    expected_operations = (
        "readiness",
        "open_app",
        "focus_app",
        "observe",
        "type_text",
    )
    if len(observations) != len(expected_operations):
        return {"textedit_smoke": False}
    passed = all(
        _observation_success(
            observation,
            expected_tool="macos.computer_use",
            expected_operation=operation,
        )
        for observation, operation in zip(observations, expected_operations)
    )
    type_text = observations[-1]
    if isinstance(type_text, dict):
        observation_payload = type_text.get("observation")
        passed = (
            passed
            and isinstance(observation_payload, dict)
            and observation_payload.get("submitted") is False
        )
    else:
        passed = False
    return {"textedit_smoke": passed}


def _load_wechat_smoke_proofs(paths: tuple[Path, ...]) -> dict[str, Any]:
    proof: dict[str, Any] = {}
    for path in paths:
        report = _load_wechat_smoke_proof(path)
        for key, value in report.items():
            if value is True:
                proof[key] = True
            elif key not in proof:
                proof[key] = False
    return proof


def _load_wechat_smoke_proof(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("WeChat smoke report JSON must be an object")
    if "appControlCommands" in payload:
        return {}

    focus_draft_passed = (
        payload.get("submitted") is False
        and _observation_success(
            payload.get("focus"),
            expected_tool="wechat.desktop",
            expected_operation="focus_contact",
        )
        and _observation_success(
            payload.get("draft"),
            expected_tool="wechat.desktop",
            expected_operation="draft_message",
        )
    )
    submit_passed = _send_message_success(payload.get("result"))
    return {
        "wechat_focus_draft_smoke": focus_draft_passed or submit_passed,
        "wechat_submit_smoke": submit_passed,
    }


def _load_testpypi_install_proof(root: Path, path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("TestPyPI install report JSON must be an object")
    source = payload.get("source")
    index_url = payload.get("indexUrl")
    install_policy = payload.get("installPolicy")
    packages = payload.get("packages")
    if (
        source != "testpypi"
        or index_url != "https://test.pypi.org/simple/"
        or not _testpypi_install_policy_ok(install_policy)
        or not isinstance(packages, list)
    ):
        return {"testpypi_install": False}

    expected_versions = {
        name: _string(_project_table(root / relative).get("version"))
        for name, relative in PACKAGE_PROJECTS.items()
    }
    package_status: dict[str, tuple[bool, bool, bool, bool]] = {}
    for item in packages:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        version = item.get("version")
        package_status[name] = (
            item.get("installed") is True,
            item.get("imported") is True,
            item.get("apiSmoke") is True,
            isinstance(version, str) and version == expected_versions.get(name),
        )
    passed = all(
        package_status.get(name) == (True, True, True, True)
        for name in PACKAGE_PROJECTS
    )
    return {"testpypi_install": passed}


def _testpypi_install_policy_ok(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    expected = {
        "managedVirtualenv": True,
        "isolated": True,
        "indexOnly": True,
        "noCache": True,
        "forceReinstall": True,
    }
    return all(
        value.get(key) is expected_value
        for key, expected_value in expected.items()
    )


def _load_trusted_publisher_proof(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Trusted Publisher report JSON must be an object")
    source = payload.get("source")
    projects = payload.get("projects")
    if source != "pypi" or not isinstance(projects, list):
        return {"pypi_trusted_publisher": False}

    project_status: dict[str, bool] = {}
    for item in projects:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            project_status[name] = (
                item.get("trustedPublisher") is True
                and _trusted_publisher_matches(item.get("publisher"))
            )
    passed = all(project_status.get(name) is True for name in PACKAGE_PROJECTS)
    return {"pypi_trusted_publisher": passed}


def _trusted_publisher_matches(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        value.get(key) == expected
        for key, expected in EXPECTED_TRUSTED_PUBLISHER.items()
    )


def _observation_success(
    value: object,
    *,
    expected_tool: str | None = None,
    expected_operation: str | None = None,
) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("schema") != "app_control.observation.v1":
        return False
    if value.get("success") is not True or value.get("status") != "ok":
        return False
    if expected_tool is not None and value.get("tool") != expected_tool:
        return False
    if expected_operation is not None and value.get("operation") != expected_operation:
        return False
    for key in ("commandId", "summary"):
        field = value.get(key)
        if not isinstance(field, str) or not field.strip():
            return False
    return isinstance(value.get("observation"), dict)


def _send_message_success(value: object) -> bool:
    if not _observation_success(
        value,
        expected_tool="wechat.desktop",
        expected_operation="send_message",
    ):
        return False
    assert isinstance(value, dict)
    observation = value.get("observation")
    return isinstance(observation, dict) and observation.get("submitted") is True


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


if __name__ == "__main__":
    sys.exit(main())
