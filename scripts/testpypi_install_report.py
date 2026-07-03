#!/usr/bin/env python3
"""Generate a clean-environment TestPyPI install proof report."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Protocol, Sequence
import venv


DEFAULT_PACKAGES = (
    ("app-control-protocol", "app_control_protocol"),
    ("computer-use-macos", "computer_use_macos"),
    ("wechat-desktop-tool", "wechat_desktop_tool"),
)

PACKAGE_SMOKE_SNIPPETS = {
    "app-control-protocol": (
        "from app_control_protocol import AppControlClient, "
        "StreamingAppControlClient, ServiceEventEnvelope, ServiceRequest, "
        "ServiceResponse, ToolCommand, ToolEvent, ToolObservation, ToolError, "
        "ToolObserver, LoggingToolObserver, build_logging_observer, "
        "AppControlConfig, HELPER_REQUEST_SCHEMA, HELPER_RESPONSE_SCHEMA, "
        "validate_protocol_payload\n"
        "from io import StringIO\n"
        "command = ToolCommand(command_id='cmd', tool='macos.computer_use', "
        "operation='readiness')\n"
        "validate_protocol_payload('command', command.to_dict())\n"
        "error = ToolError(failure_kind='not_ready', message='not ready', "
        "retryable=True, phase='readiness', operation='readiness')\n"
        "observation = ToolObservation.ok(command_id='cmd', "
        "tool='macos.computer_use', operation='readiness', summary='ready')\n"
        "failure = ToolObservation.failure(command_id='cmd_fail', "
        "tool='macos.computer_use', operation='readiness', status='not_ready', "
        "error=error)\n"
        "event = ToolEvent(command_id='cmd', seq=0, event_type='started')\n"
        "class SmokeClient:\n"
        "    def run_command(self, command, *, observer=None):\n"
        "        if observer is not None:\n"
        "            observer.on_event(event)\n"
        "        return observation\n"
        "class SmokeStreamingClient(SmokeClient):\n"
        "    def run_stream(self, command, *, observer=None):\n"
        "        if observer is not None:\n"
        "            observer.on_event(event)\n"
        "        yield event\n"
        "client: AppControlClient = SmokeClient()\n"
        "streaming_client: StreamingAppControlClient = SmokeStreamingClient()\n"
        "assert client.run_command(command).success\n"
        "assert list(streaming_client.run_stream(command))[0].command_id == 'cmd'\n"
        "stream = StringIO()\n"
        "observer = build_logging_observer(stream=stream)\n"
        "assert isinstance(observer, LoggingToolObserver)\n"
        "observer.on_event(event)\n"
        "assert stream.getvalue()\n"
        "assert ToolObserver is not None\n"
        "validate_protocol_payload('observation', failure.to_dict())\n"
        "validate_protocol_payload('service_request', "
        "ServiceRequest.run(command, token='local-token').to_dict())\n"
        "validate_protocol_payload('service_request', "
        "ServiceRequest.submit(command, request_id='req_submit', "
        "token='local-token').to_dict())\n"
        "validate_protocol_payload('service_request', "
        "ServiceRequest.poll('req_submit', token='local-token').to_dict())\n"
        "validate_protocol_payload('service_request', "
        "ServiceRequest.stream(command, token='local-token').to_dict())\n"
        "validate_protocol_payload('service_response', "
        "ServiceResponse.complete(observation, request_id='req').to_dict())\n"
        "validate_protocol_payload('service_response', "
        "ServiceResponse.not_found(request_id='req_missing').to_dict())\n"
        "validate_protocol_payload('service_response', "
        "ServiceResponse.failed(error, request_id='req_failed').to_dict())\n"
        "validate_protocol_payload('service_event', "
        "ServiceEventEnvelope(request_id='req', event=event).to_dict())\n"
        "validate_protocol_payload('helper_request', {'schema': "
        "HELPER_REQUEST_SCHEMA, 'command': command.to_dict()})\n"
        "validate_protocol_payload('helper_response', {'schema': "
        "HELPER_RESPONSE_SCHEMA, 'success': True, "
        "'observation': observation.to_dict()})\n"
        "print('api-smoke-ok')"
    ),
    "computer-use-macos": (
        "from app_control_protocol import validate_protocol_payload\n"
        "from computer_use_macos import observations, transport\n"
        "from computer_use_macos.examples import textedit_smoke\n"
        "from computer_use_macos import ComputerUseClient, readiness_command, "
        "observe_command, accessibility_query_command, accessibility_action_command, "
        "open_app_command, focus_app_command, click_command, "
        "click_accessibility_command, click_coordinate_command, type_text_command, "
        "press_key_command, hotkey_command, wait_command, COMPUTER_USE_FAILURE_KINDS, "
        "HelperManifest, HelperTransportClient\n"
        "assert 'app_not_allowlisted' in COMPUTER_USE_FAILURE_KINDS\n"
        "assert observations.ComputerUseResult is not None\n"
        "assert transport.HelperTransportClient is not None\n"
        "helper = ComputerUseClient.from_helper_manifest("
        "HelperManifest(bundle_id='com.example.helper', "
        "socket_path='/tmp/example-helper.sock'))\n"
        "assert isinstance(helper, HelperTransportClient)\n"
        "assert callable(helper.open_app)\n"
        "assert textedit_smoke.main is not None\n"
        "for command in (readiness_command(), observe_command(target_app='TextEdit'), "
        "accessibility_query_command(target_app='TextEdit'), "
        "accessibility_action_command(target_app='TextEdit', ax_path='0/1', "
        "action='AXPress'), "
        "open_app_command('TextEdit'), focus_app_command('TextEdit'), "
        "click_command(target='OK', target_app='TextEdit'), "
        "click_accessibility_command({'role': 'button', 'name': 'OK'}, "
        "target_app='TextEdit'), click_coordinate_command(10, 20), "
        "type_text_command('hello'), press_key_command('Return'), "
        "hotkey_command(('Command', 'K')), wait_command(seconds=0.1)):\n"
        "    validate_protocol_payload('command', command.to_dict())\n"
        "print('api-smoke-ok')"
    ),
    "wechat-desktop-tool": (
        "from app_control_protocol import validate_protocol_payload\n"
        "from wechat_desktop_tool import adapter, observations, recipes\n"
        "from wechat_desktop_tool.examples import wechat_smoke\n"
        "from wechat_desktop_tool import WeChatDesktopTool, open_wechat_command, "
        "inspect_window_command, list_contacts_command, list_conversations_command, "
        "open_contact_command, execute_action_command, focus_contact_command, "
        "observe_current_chat_command, read_visible_messages_command, "
        "read_contact_messages_command, draft_message_command, "
        "submit_draft_command, send_message_command, build_wechat_tool, "
        "send_message, WECHAT_FAILURE_KINDS\n"
        "assert 'submit_unknown' in WECHAT_FAILURE_KINDS\n"
        "assert adapter.build_wechat_tool is not None\n"
        "assert adapter.build_wechat_tool is build_wechat_tool\n"
        "assert observations.WeChatVisibleMessage is not None\n"
        "assert recipes.send_message is not None\n"
        "assert recipes.send_message is send_message\n"
        "assert wechat_smoke.main is not None\n"
        "for command in (open_wechat_command(), "
        "inspect_window_command(), list_contacts_command(), "
        "list_conversations_command(), open_contact_command('File Transfer'), "
        "execute_action_command({'schema': 'wechat.action_ref.v1', "
        "'id': 'nav.contacts.press', 'target': {'axPath': '0/2'}, "
        "'action': 'AXPress'}), "
        "focus_contact_command('File Transfer'), observe_current_chat_command(), "
        "read_visible_messages_command(limit=5), "
        "read_contact_messages_command('File Transfer'), draft_message_command('hello'), "
        "submit_draft_command(), send_message_command(contact='File Transfer', "
        "message='hello')):\n"
        "    validate_protocol_payload('command', command.to_dict())\n"
        "print('api-smoke-ok')"
    ),
}

TESTPYPI_INDEX_URL = "https://test.pypi.org/simple/"
TESTPYPI_INSTALL_POLICY = {
    "managedVirtualenv": True,
    "isolated": True,
    "indexOnly": True,
    "noCache": True,
    "forceReinstall": True,
}


class Runner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess command."""


class SubprocessRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )


@dataclass(frozen=True)
class PackageReport:
    name: str
    importName: str
    installed: bool
    imported: bool
    apiSmoke: bool
    version: str | None = None
    installReturncode: int | None = None
    installError: str | None = None
    importReturncode: int | None = None
    importError: str | None = None
    apiSmokeReturncode: int | None = None
    apiSmokeError: str | None = None


def build_report(
    *,
    python_executable: str | Path = sys.executable,
    index_url: str = TESTPYPI_INDEX_URL,
    timeout: float = 300.0,
    runner: Runner | None = None,
    venv_dir: Path | None = None,
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    if venv_dir is not None:
        python = _venv_python(venv_dir)
        managed_virtualenv = False
        packages = [
            _validate_package(
                python=python,
                package_name=package_name,
                import_name=import_name,
                index_url=index_url,
                timeout=timeout,
                runner=command_runner,
            )
            for package_name, import_name in DEFAULT_PACKAGES
        ]
    else:
        with tempfile.TemporaryDirectory(
            prefix="app-control-tools-testpypi-"
        ) as tmpdir:
            managed_venv_dir = Path(tmpdir) / "venv"
            venv.EnvBuilder(with_pip=True, clear=True).create(managed_venv_dir)
            python = _venv_python(managed_venv_dir)
            managed_virtualenv = True
            packages = [
                _validate_package(
                    python=python,
                    package_name=package_name,
                    import_name=import_name,
                    index_url=index_url,
                    timeout=timeout,
                    runner=command_runner,
                )
                for package_name, import_name in DEFAULT_PACKAGES
            ]
    return {
        "source": "testpypi",
        "indexUrl": index_url,
        "python": str(python_executable),
        "venvPython": str(python),
        "installPolicy": {
            **TESTPYPI_INSTALL_POLICY,
            "managedVirtualenv": managed_virtualenv,
        },
        "packages": [asdict(package) for package in packages],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install app-control tool packages from TestPyPI in a clean venv."
    )
    parser.add_argument("--index-url", default=TESTPYPI_INDEX_URL)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = build_report(index_url=args.index_url, timeout=args.timeout)
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


def _validate_package(
    *,
    python: Path,
    package_name: str,
    import_name: str,
    index_url: str,
    timeout: float,
    runner: Runner,
) -> PackageReport:
    install = runner.run(
        (
            str(python),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--force-reinstall",
            "--index-url",
            index_url,
            package_name,
        ),
        timeout=timeout,
    )
    installed = install.returncode == 0
    if not installed:
        return PackageReport(
            name=package_name,
            importName=import_name,
            installed=False,
            imported=False,
            apiSmoke=False,
            installReturncode=install.returncode,
            installError=_bounded(install.stderr or install.stdout),
        )

    probe = (
        "import importlib; "
        f"module = importlib.import_module({import_name!r}); "
        "print(getattr(module, '__version__', ''))"
    )
    imported = runner.run((str(python), "-c", probe), timeout=timeout)
    api_smoke = (
        runner.run(
            (
                str(python),
                "-c",
                PACKAGE_SMOKE_SNIPPETS[package_name],
            ),
            timeout=timeout,
        )
        if imported.returncode == 0
        else subprocess.CompletedProcess((), 1, "", "import failed")
    )
    return PackageReport(
        name=package_name,
        importName=import_name,
        installed=True,
        imported=imported.returncode == 0,
        apiSmoke=api_smoke.returncode == 0,
        version=(imported.stdout.strip() or None) if imported.returncode == 0 else None,
        installReturncode=install.returncode,
        importReturncode=imported.returncode,
        importError=(
            None
            if imported.returncode == 0
            else _bounded(imported.stderr or imported.stdout)
        ),
        apiSmokeReturncode=api_smoke.returncode,
        apiSmokeError=(
            None
            if api_smoke.returncode == 0
            else _bounded(api_smoke.stderr or api_smoke.stdout)
        ),
    )


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _report_passed(report: dict[str, object]) -> bool:
    packages = report.get("packages")
    if (
        report.get("source") != "testpypi"
        or report.get("indexUrl") != TESTPYPI_INDEX_URL
    ):
        return False
    if report.get("installPolicy") != TESTPYPI_INSTALL_POLICY:
        return False
    if not isinstance(packages, list) or len(packages) != len(DEFAULT_PACKAGES):
        return False
    package_names = {
        item.get("name")
        for item in packages
        if isinstance(item, dict)
    }
    if package_names != {name for name, _ in DEFAULT_PACKAGES}:
        return False
    return all(
        isinstance(item, dict)
        and item.get("installed") is True
        and item.get("imported") is True
        and item.get("apiSmoke") is True
        and isinstance(item.get("version"), str)
        and bool(item["version"].strip())
        for item in packages
    )


def _report_summary(
    report: dict[str, object],
    *,
    output: Path,
    passed: bool,
) -> str:
    status = "passed" if passed else "failed"
    failed_packages = _failed_package_names(report)
    detail = ""
    if failed_packages:
        detail = "; failed packages: " + ", ".join(failed_packages)
    return f"wrote TestPyPI install report to {output} ({status}{detail})"


def _failed_package_names(report: dict[str, object]) -> list[str]:
    packages = report.get("packages")
    if not isinstance(packages, list):
        return ["<missing packages>"]
    failed: list[str] = []
    for item in packages:
        if not isinstance(item, dict):
            failed.append("<invalid package>")
            continue
        name = item.get("name")
        package_name = name if isinstance(name, str) and name else "<unknown package>"
        if (
            item.get("installed") is not True
            or item.get("imported") is not True
            or item.get("apiSmoke") is not True
        ):
            failed.append(package_name)
    return failed


def _bounded(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


if __name__ == "__main__":
    raise SystemExit(main())
