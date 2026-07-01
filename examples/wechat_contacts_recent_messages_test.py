"""Read recent visible WeChat messages for each listed contact.

Run from the repository root after starting the local app-control service:

    /opt/anaconda3/bin/python examples/wechat_contacts_recent_messages_test.py

The current WeChat API returns the visible contact page from `list_contacts`.
This example reads up to `--max-contacts` contacts from that page, opens each
contact, reads up to `--message-limit` visible/recent messages, and writes a
JSON report.
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
from wechat_desktop_tool import WeChatDesktopTool


DEFAULT_CONFIG = "./app-control.toml"
DEFAULT_MAX_CONTACTS = 30
DEFAULT_MESSAGE_LIMIT = 30
DEFAULT_OUTPUT = "./wechat-contacts-recent-messages-test.json"
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


def run_contacts_recent_messages_test(
    *,
    config_path: str | Path | None,
    output_path: str | Path,
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
    token: str | None = None,
    timeout: float = 30.0,
    max_contacts: int = DEFAULT_MAX_CONTACTS,
    message_limit: int = DEFAULT_MESSAGE_LIMIT,
    continue_on_error: bool = True,
    service_client: Any | None = None,
) -> dict[str, Any]:
    if max_contacts <= 0:
        raise ValueError("max_contacts must be positive")
    if message_limit <= 0:
        raise ValueError("message_limit must be positive")

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
    contacts = (
        wechat.list_contacts(limit=max_contacts)
        if readiness.success
        else _skipped_observation("list_contacts", "readiness", readiness)
    )
    contact_items = _contact_items(contacts)[:max_contacts] if contacts.success else []
    read_results: list[dict[str, Any]] = []
    for item in contact_items:
        display_name = _contact_display_name(item)
        if display_name is None:
            continue
        result = wechat.read_contact_messages(display_name, limit=message_limit)
        read_results.append(
            {
                "contact": display_name,
                "contactItem": item,
                "readContactMessages": result.to_dict(),
                "messageCount": _message_count(result),
                "success": result.success,
            }
        )
        if not result.success and not continue_on_error:
            break

    failed_contacts = [
        item["contact"] for item in read_results if item.get("success") is not True
    ]
    payload: dict[str, Any] = {
        "schema": "macos_computer_use.sdk.wechat_contacts_recent_messages_test.v1",
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
            "maxContacts": max_contacts,
            "messageLimit": message_limit,
            "continueOnError": continue_on_error,
        },
        "readiness": readiness.to_dict(),
        "listContacts": contacts.to_dict(),
        "contacts": read_results,
        "summary": {
            "success": (
                readiness.success
                and contacts.success
                and len(failed_contacts) == 0
            ),
            "listedContactCount": len(contact_items),
            "processedContactCount": len(read_results),
            "successfulContactCount": len(read_results) - len(failed_contacts),
            "failedContacts": failed_contacts,
            "messageLimit": message_limit,
            "failedStep": _failed_step(readiness, contacts, read_results),
        },
    }
    _write_json(output_path, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        socket_path, token, timeout = _service_settings(args)
        payload = run_contacts_recent_messages_test(
            config_path=args.config,
            output_path=args.output,
            socket_path=socket_path,
            token=token,
            timeout=timeout,
            max_contacts=args.max_contacts,
            message_limit=args.message_limit,
            continue_on_error=not args.stop_on_error,
        )
    except Exception as exc:
        print(f"wechat contacts recent messages test failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"wrote: {Path(args.output).expanduser()}")
    return 0 if payload["summary"]["success"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read recent visible WeChat messages for listed contacts.",
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
    parser.add_argument("--max-contacts", type=int, default=DEFAULT_MAX_CONTACTS)
    parser.add_argument("--message-limit", type=int, default=DEFAULT_MESSAGE_LIMIT)
    parser.add_argument("--stop-on-error", action="store_true")
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


def _message_count(observation: ToolObservation) -> int:
    messages_payload = observation.observation.get("messages")
    if not isinstance(messages_payload, Mapping):
        return 0
    messages = messages_payload.get("messages")
    return len(messages) if isinstance(messages, list) else 0


def _failed_step(
    readiness: ToolObservation,
    contacts: ToolObservation,
    read_results: list[dict[str, Any]],
) -> str | None:
    if not readiness.success:
        return "readiness"
    if not contacts.success:
        return "listContacts"
    if any(item.get("success") is not True for item in read_results):
        return "readContactMessages"
    return None


def _skipped_observation(
    operation: str,
    failed_step: str,
    failed: ToolObservation,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=f"wechat-contacts-recent-messages:{operation}:skipped",
        tool="wechat.desktop",
        operation=operation,
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind=f"{failed_step}_failed",
            message=f"{operation} skipped because {failed_step} failed.",
            retryable=failed.retryable,
        ),
        summary=f"{operation} skipped because {failed_step} failed.",
        evidence={failed_step: failed.to_dict()},
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


if __name__ == "__main__":
    raise SystemExit(main())
