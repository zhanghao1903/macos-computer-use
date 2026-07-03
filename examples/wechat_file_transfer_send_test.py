"""Send a WeChat message to File Transfer through the SDK packages.

Run from the repository root after starting the local app-control service:

    /opt/anaconda3/bin/python examples/wechat_file_transfer_send_test.py

This script opens WeChat, switches the current chat to File Transfer, drafts
one message, submits it, and writes a JSON report with every semantic step.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import importlib
import importlib.util
import json
import os
from pathlib import Path
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
from wechat_desktop_tool import WeChatDesktopTool, wechat_message_hash


DEFAULT_CONFIG = "./app-control.toml"
DEFAULT_CONTACT = "文件传输助手"
DEFAULT_MESSAGE = "hello from wechat file transfer send test"
DEFAULT_OUTPUT = "./wechat-file-transfer-send-test.json"
DEFAULT_SOCKET_PATH = "/tmp/app-control.sock"
DEFAULT_TOKEN_FILE = "./app-control.token"


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


def run_file_transfer_send_test(
    *,
    config_path: str | Path | None,
    output_path: str | Path,
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
    token: str | None = None,
    timeout: float = 30.0,
    contact: str = DEFAULT_CONTACT,
    message: str = DEFAULT_MESSAGE,
    service_client: Any | None = None,
) -> dict[str, Any]:
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
    opened = wechat.open_wechat()
    opened_contact = (
        wechat.open_contact(contact)
        if opened.success
        else _skipped_observation("open_contact", "open_wechat", opened)
    )
    drafted = (
        wechat.draft_message(message)
        if opened_contact.success
        else _skipped_observation("draft_message", "open_contact", opened_contact)
    )
    submitted = (
        wechat.submit_draft()
        if drafted.success
        else _skipped_observation("submit_draft", "draft_message", drafted)
    )

    payload: dict[str, Any] = {
        "schema": "macos_computer_use.sdk.wechat_file_transfer_send_test.v1",
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "imports": _import_diagnostics(),
        "service": {
            "socketPath": str(socket_path),
            "configPath": str(config_for_tool) if config_for_tool else None,
        },
        "target": {
            "contact": contact,
            "messageHash": wechat_message_hash(message),
            "messageChars": len(message),
        },
        "readiness": readiness.to_dict(),
        "openWeChat": opened.to_dict(),
        "openContact": opened_contact.to_dict(),
        "draftMessage": drafted.to_dict(),
        "submitDraft": submitted.to_dict(),
        "summary": {
            "success": (
                readiness.success
                and opened.success
                and opened_contact.success
                and drafted.success
                and submitted.success
            ),
            "contact": contact,
            "submitted": submitted.success,
            "failedStep": _failed_step(
                {
                    "readiness": readiness,
                    "openWeChat": opened,
                    "openContact": opened_contact,
                    "draftMessage": drafted,
                    "submitDraft": submitted,
                }
            ),
        },
    }
    _write_json(output_path, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        socket_path, token, timeout = _service_settings(args)
        payload = run_file_transfer_send_test(
            config_path=args.config,
            output_path=args.output,
            socket_path=socket_path,
            token=token,
            timeout=timeout,
            contact=args.contact,
            message=args.message,
        )
    except Exception as exc:
        print(f"wechat file-transfer send test failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"wrote: {Path(args.output).expanduser()}")
    return 0 if payload["summary"]["success"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open WeChat and send one message to File Transfer.",
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
    parser.add_argument("--contact", default=DEFAULT_CONTACT)
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
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


def _skipped_observation(
    operation: str,
    failed_step: str,
    failed: ToolObservation,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=f"wechat-file-transfer-send:{operation}:skipped",
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


def _failed_step(steps: Mapping[str, ToolObservation]) -> str | None:
    for name, observation in steps.items():
        if not observation.success:
            return name
    return None


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


if __name__ == "__main__":
    raise SystemExit(main())
