"""SDK-style WeChat window inspection test stub.

Run from the repository root after starting the local app-control service:

    /opt/anaconda3/bin/python examples/wechat_window_sdk_test.py

This example intentionally imports the installed SDK packages instead of using
the package CLI entrypoints.
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
    ToolObservation,
    load_app_control_config,
    validate_protocol_payload,
)
from computer_use_macos import UnixSocketServiceClient, readiness_command
from wechat_desktop_tool import WECHAT_WINDOW_SCHEMA, WeChatDesktopTool


DEFAULT_CONFIG = "./app-control.toml"
DEFAULT_OUTPUT = "./wechat-window-sdk-test.json"
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


def run_sdk_test(
    *,
    config_path: str | Path | None,
    output_path: str | Path,
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
    token: str | None = None,
    timeout: float = 30.0,
    include_raw: bool = False,
    include_actionables: bool = True,
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
    inspected = wechat.inspect_window(
        include_raw=include_raw,
        include_actionables=include_actionables,
    )

    payload: dict[str, Any] = {
        "schema": "macos_computer_use.sdk.wechat_window_test.v1",
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "imports": _import_diagnostics(),
        "service": {
            "socketPath": str(socket_path),
            "configPath": str(config_for_tool) if config_for_tool else None,
        },
        "readiness": readiness.to_dict(),
        "inspectWindow": inspected.to_dict(),
        "summary": _summary(inspected),
    }
    _write_json(output_path, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config_path = args.config
        socket_path, token, timeout = _service_settings(args)
        payload = run_sdk_test(
            config_path=config_path,
            output_path=args.output,
            socket_path=socket_path,
            token=token,
            timeout=timeout,
            include_raw=args.include_raw,
            include_actionables=not args.no_actionables,
        )
    except Exception as exc:
        print(f"sdk test failed: {exc}", file=sys.stderr)
        return 2

    _print_summary(payload, args.output)
    return _exit_code(payload, allow_missing_tree=args.allow_missing_tree)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an SDK-style WeChat window inspection test.",
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
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--include-raw", action="store_true")
    parser.add_argument("--no-actionables", action="store_true")
    parser.add_argument(
        "--allow-missing-tree",
        action="store_true",
        help="return success even when inspect_window cannot normalize the tree",
    )
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


def _summary(inspected: ToolObservation) -> dict[str, Any]:
    observation = inspected.observation
    window = observation.get("window") if isinstance(observation, dict) else None
    normalization = (
        observation.get("normalization") if isinstance(observation, dict) else None
    )
    available_actions = []
    actionables = []
    if isinstance(window, dict):
        available_actions = _list_value(window.get("availableActions"))
        actionables = _list_value(window.get("actionables"))
    return {
        "success": inspected.success,
        "operation": inspected.operation,
        "schema": observation.get("schema") if isinstance(observation, dict) else None,
        "expectedSchema": WECHAT_WINDOW_SCHEMA,
        "normalization": normalization if isinstance(normalization, dict) else None,
        "actionableCount": len(actionables),
        "availableActionCount": len(available_actions),
        "availableActionIds": [
            item.get("id")
            for item in available_actions
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ],
    }


def _exit_code(payload: Mapping[str, Any], *, allow_missing_tree: bool) -> int:
    inspect_payload = _mapping_value(payload.get("inspectWindow"))
    if not inspect_payload or inspect_payload.get("success") is not True:
        return 1
    summary = _mapping_value(payload.get("summary")) or {}
    normalization = _mapping_value(summary.get("normalization")) or {}
    if (
        not allow_missing_tree
        and normalization.get("reason") != "accessibility_query_normalized"
    ):
        return 3
    return 0


def _print_summary(payload: Mapping[str, Any], output_path: str | Path) -> None:
    summary = _mapping_value(payload.get("summary")) or {}
    normalization = _mapping_value(summary.get("normalization")) or {}
    print(f"wrote: {Path(output_path).expanduser()}")
    print(f"inspect success: {summary.get('success')}")
    print(
        "normalization: "
        f"{normalization.get('status')} / {normalization.get('reason')}"
    )
    print(f"available actions: {summary.get('availableActionCount')}")
    if normalization.get("reason") != "accessibility_query_normalized":
        print(f"inspect diagnostic: {normalization.get('reason')}")


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


def _list_value(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping_value(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


if __name__ == "__main__":
    raise SystemExit(main())
