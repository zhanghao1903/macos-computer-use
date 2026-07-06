"""List visible WeChat contacts through the SDK-style local service path.

Run from the repository root after starting the local app-control service:

    /opt/anaconda3/bin/python examples/wechat_contacts_list_test.py

The script opens WeChat, switches to Contacts through `list_contacts`, writes a
JSON report, and prints the returned contact names.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from uuid import uuid4

from app_control_protocol import (
    ProtocolValidationError,
    ToolCommand,
    ToolError,
    ToolObservation,
    ToolStatus,
    load_app_control_config,
    validate_protocol_payload,
)
from computer_use_macos import UnixSocketServiceClient, readiness_command
from wechat_desktop_tool import WeChatDesktopTool


DEFAULT_CONFIG = "./app-control.toml"
DEFAULT_LIMIT = 30
DEFAULT_OUTPUT = "./wechat-contacts-list-test.json"
DEFAULT_SOCKET_PATH = "/tmp/app-control.sock"
DEFAULT_TOKEN_FILE = "./app-control.token"
DEFAULT_WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"


class LocalServiceAppControlAdapter:
    """Adapt UnixSocketServiceClient to the AppControlClient protocol."""

    def __init__(self, service_client: Any) -> None:
        self._service_client = service_client

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = _coerce_command(command)
        responses = self._service_client.run_command(
            tool_command.to_dict(),
            action="run",
            request_id="sdk_" + uuid4().hex,
        )
        if not responses:
            raise RuntimeError("local service returned no response")
        response = dict(responses[-1])
        try:
            validate_protocol_payload("service_response", response)
        except ProtocolValidationError as exc:
            raise RuntimeError(f"invalid service response: {exc}") from exc
        if not response.get("success"):
            raise RuntimeError(response.get("error", response))
        observation = response.get("observation")
        if not isinstance(observation, dict):
            raise RuntimeError("service response does not include observation")
        try:
            validate_protocol_payload("observation", observation)
        except ProtocolValidationError as exc:
            raise RuntimeError(f"invalid service observation: {exc}") from exc
        return ToolObservation.from_dict(observation)


def run_contacts_list_test(
    *,
    config_path: str | Path | None,
    output_path: str | Path,
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
    token: str | None = None,
    timeout: float = 30.0,
    limit: int = DEFAULT_LIMIT,
    system_open: bool = True,
    wechat_bundle_id: str = DEFAULT_WECHAT_BUNDLE_ID,
    system_open_runner: Any | None = None,
    service_client: Any | None = None,
) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be positive")

    system_opened = (
        _open_wechat_process(wechat_bundle_id, runner=system_open_runner)
        if system_open
        else {
            "operation": "system_open_wechat",
            "success": True,
            "skipped": True,
        }
    )
    concrete_service_client = service_client or UnixSocketServiceClient(
        socket_path,
        token=token,
        timeout=timeout,
    )
    app_control = LocalServiceAppControlAdapter(concrete_service_client)
    config_for_tool = _existing_config_or_none(config_path)

    readiness = app_control.run_command(
        readiness_command(command_id="sdk_readiness_" + uuid4().hex)
    )
    wechat = WeChatDesktopTool.from_config(app_control, config_for_tool)
    opened = (
        wechat.open_wechat()
        if system_opened["success"] is True and readiness.success
        else _skipped_observation(
            "open_wechat",
            "system_open_wechat"
            if system_opened["success"] is not True
            else "readiness",
            readiness,
        )
    )
    contacts = (
        wechat.list_contacts(limit=limit)
        if opened.success
        else _skipped_observation("list_contacts", "open_wechat", opened)
    )
    contact_items = _contact_items(contacts)[:limit] if contacts.success else []
    contact_names = [
        name for item in contact_items if (name := _contact_display_name(item))
    ]

    payload: dict[str, Any] = {
        "schema": "macos_computer_use.sdk.wechat_contacts_list_test.v1",
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "imports": _import_diagnostics(),
        "service": {
            "socketPath": str(socket_path),
            "configPath": str(config_for_tool) if config_for_tool else None,
        },
        "options": {
            "limit": limit,
            "systemOpen": system_open,
            "wechatBundleId": wechat_bundle_id,
        },
        "systemOpenWeChat": system_opened,
        "readiness": readiness.to_dict(),
        "openWeChat": opened.to_dict(),
        "listContacts": contacts.to_dict(),
        "contacts": contact_items,
        "contactNames": contact_names,
        "summary": {
            "success": (
                system_opened["success"] is True
                and readiness.success
                and opened.success
                and contacts.success
            ),
            "listedContactCount": len(contact_items),
            "contactNames": contact_names,
            "failedStep": _failed_step(system_opened, readiness, opened, contacts),
        },
    }
    _write_json(output_path, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        socket_path, token, timeout = _service_settings(args)
        payload = run_contacts_list_test(
            config_path=args.config,
            output_path=args.output,
            socket_path=socket_path,
            token=token,
            timeout=timeout,
            limit=args.limit,
            system_open=not args.skip_system_open,
            wechat_bundle_id=args.wechat_bundle_id,
        )
    except Exception as exc:
        print(f"wechat contacts list test failed: {exc}", file=sys.stderr)
        return 2

    _print_result(payload, args.output)
    return 0 if payload["summary"]["success"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open WeChat and list visible contacts.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("APP_CONTROL_CONFIG", DEFAULT_CONFIG),
    )
    parser.add_argument(
        "--socket-path",
        default=os.environ.get("WECHAT_TOOL_SOCKET_PATH")
        or os.environ.get("APP_CONTROL_SOCKET_PATH"),
    )
    parser.add_argument("--token", default=os.environ.get("WECHAT_TOOL_TOKEN"))
    parser.add_argument(
        "--token-file",
        default=os.environ.get("WECHAT_TOOL_TOKEN_FILE", DEFAULT_TOKEN_FILE),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--skip-system-open", action="store_true")
    parser.add_argument("--wechat-bundle-id", default=DEFAULT_WECHAT_BUNDLE_ID)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser


def _service_settings(args: argparse.Namespace) -> tuple[str, str | None, float]:
    if args.token and args.token_file:
        raise ValueError("--token and --token-file are mutually exclusive")

    socket_path = args.socket_path
    token = args.token
    timeout = args.timeout
    config_path = _existing_config_or_none(args.config)
    if config_path is not None:
        config = load_app_control_config(config_path)
        timeout = args.timeout or config.computer_use.timeout_ms / 1000.0
        helper = config.helper
        if socket_path is None and helper.endpoint:
            if helper.transport != "unix_socket":
                raise ValueError("helper.transport must be unix_socket")
            socket_path = helper.endpoint
        if token is None and not args.token_file:
            token = helper.token

    if socket_path is None:
        socket_path = DEFAULT_SOCKET_PATH
    if token is None and args.token_file:
        token_path = Path(args.token_file).expanduser()
        if token_path.exists():
            token = token_path.read_text(encoding="utf-8").strip()
            if not token:
                raise ValueError(f"token file is empty: {token_path}")
        else:
            raise ValueError(f"token file does not exist: {token_path}")
    return str(socket_path), token, float(timeout)


def _contact_items(observation: ToolObservation) -> list[dict[str, Any]]:
    items = observation.observation.get("items")
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, Mapping)]


def _contact_display_name(item: Mapping[str, Any]) -> str | None:
    value = item.get("displayName")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _open_wechat_process(bundle_id: str, *, runner: Any | None = None) -> dict[str, Any]:
    concrete_runner = runner or subprocess.run
    commands = [
        ["open", "-b", bundle_id],
        [
            "osascript",
            "-e",
            f"tell application id {_applescript_string(bundle_id)} to reopen",
            "-e",
            f"tell application id {_applescript_string(bundle_id)} to activate",
        ],
    ]
    results = []
    success = True
    for command in commands:
        try:
            completed = concrete_runner(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            success = False
            results.append(
                {
                    "command": command,
                    "success": False,
                    "error": str(exc),
                }
            )
            break
        command_success = getattr(completed, "returncode", 1) == 0
        success = success and command_success
        results.append(
            {
                "command": command,
                "success": command_success,
                "returnCode": getattr(completed, "returncode", None),
                "stdout": _bounded_text(getattr(completed, "stdout", "")),
                "stderr": _bounded_text(getattr(completed, "stderr", "")),
            }
        )
        if not command_success:
            break
    return {
        "operation": "system_open_wechat",
        "success": success,
        "bundleId": bundle_id,
        "commands": results,
    }


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _bounded_text(value: object, *, limit: int = 1000) -> str:
    text = value if isinstance(value, str) else str(value or "")
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def _failed_step(
    system_opened: Mapping[str, Any],
    readiness: ToolObservation,
    opened: ToolObservation,
    contacts: ToolObservation,
) -> str | None:
    if system_opened.get("success") is not True:
        return "systemOpenWeChat"
    if not readiness.success:
        return "readiness"
    if not opened.success:
        return "openWeChat"
    if not contacts.success:
        return "listContacts"
    return None


def _skipped_observation(
    operation: str,
    failed_step: str,
    failed: ToolObservation,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=f"wechat-contacts-list:{operation}:skipped",
        tool="wechat.desktop",
        operation=operation,
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind=f"{failed_step}_failed",
            message=f"{operation} skipped because {failed_step} failed.",
            retryable=failed.retryable,
            evidence={failed_step: failed.to_dict()},
        ),
        summary=f"{operation} skipped because {failed_step} failed.",
    )


def _import_diagnostics() -> dict[str, Any]:
    packages = (
        "app_control_protocol",
        "computer_use_macos",
        "wechat_desktop_tool",
    )
    optional_modules = ("ApplicationServices", "AppKit", "objc")
    return {
        "packages": {name: _module_info(name) for name in packages},
        "optionalModules": {
            name: _optional_module_info(name) for name in optional_modules
        },
    }


def _module_info(name: str) -> dict[str, Any]:
    module = importlib.import_module(name)
    return {
        "version": getattr(module, "__version__", None),
        "file": getattr(module, "__file__", None),
    }


def _optional_module_info(name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(name)
    if spec is None:
        return {"available": False}
    return {"available": True, "origin": spec.origin}


def _existing_config_or_none(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _print_result(payload: Mapping[str, Any], output_path: str | Path) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote: {Path(output_path).expanduser()}")
    print("contacts:")
    names = payload.get("contactNames")
    if isinstance(names, list):
        for name in names:
            print(f"- {name}")


if __name__ == "__main__":
    raise SystemExit(main())
