"""CLI examples for WeChat Desktop semantic tools."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import socket
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

from .tool import WeChatDesktopTool


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wechat-desktop-tool")
    subcommands = parser.add_subparsers(dest="command")
    examples = subcommands.add_parser("examples", help="runnable examples")
    example_commands = examples.add_subparsers(dest="example_command")
    _add_send_message_parser(example_commands)

    args = parser.parse_args(argv)
    if args.command == "examples" and args.example_command == "send-message":
        try:
            return _run_send_message_example(args, parser)
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
    parser.print_help()
    return 2


def _add_send_message_parser(
    subcommands: argparse._SubParsersAction[object],
) -> None:
    send = subcommands.add_parser(
        "send-message",
        help="focus a contact, draft a message, and optionally submit it",
    )
    send.add_argument("--contact", required=True)
    send.add_argument("--message", required=True)
    send.add_argument("--config")
    send.add_argument("--socket-path")
    send.add_argument("--token")
    send.add_argument("--token-file")
    send.add_argument("--dry-run", action="store_true")
    send.add_argument("--submit", action="store_true")
    send.add_argument("--verify-after-submit", action="store_true")


def _run_send_message_example(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    app_control = _app_control_for_args(args, parser)
    tool = WeChatDesktopTool.from_config(app_control, args.config)
    if args.submit:
        result = tool.send_message(
            contact=args.contact,
            message=args.message,
            verify_after_submit=args.verify_after_submit,
        )
        output: dict[str, Any] = {"result": result.to_dict()}
        success = result.success
    else:
        focus = tool.focus_contact(args.contact)
        draft = (
            tool.draft_message(args.message)
            if focus.success
            else ToolObservation.failure(
                command_id="wechat-example-draft-skipped",
                tool="wechat.desktop",
                operation="draft_message",
                status=ToolStatus.FAILED,
                error=ToolError(failure_kind="focus_failed", message=focus.summary),
                summary="Draft skipped because focus_contact failed.",
            )
        )
        output = {
            "submitted": False,
            "focus": focus.to_dict(),
            "draft": draft.to_dict(),
        }
        success = focus.success and draft.success
    if isinstance(app_control, DryRunAppControl):
        output["appControlCommands"] = [
            command.to_dict() for command in app_control.commands
        ]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if success else 1


class DryRunAppControl:
    def __init__(self) -> None:
        self.commands: list[ToolCommand] = []

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = _coerce_command(command)
        self.commands.append(tool_command)
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary=f"dry-run app-control command: {tool_command.operation}",
            observation={"input": tool_command.input, "dryRun": True},
        )


class LocalServiceAppControl:
    def __init__(
        self,
        socket_path: str | Path,
        *,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._socket_path = Path(socket_path).expanduser()
        self._token = token
        self._timeout = timeout

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = _coerce_command(command)
        response = self._round_trip(
            {
                "schema": "app_control.service.request.v1",
                "action": "run",
                "requestId": "wechat_" + uuid4().hex,
                "token": self._token,
                "command": tool_command.to_dict(),
            }
        )
        try:
            validate_protocol_payload("service_response", response)
        except ProtocolValidationError as exc:
            raise RuntimeError(f"invalid local service response: {exc}") from exc
        if not response.get("success"):
            raise RuntimeError(response.get("error", response))
        observation = response.get("observation")
        if not isinstance(observation, dict):
            raise RuntimeError("local service response does not include observation")
        try:
            validate_protocol_payload("observation", observation)
        except ProtocolValidationError as exc:
            raise RuntimeError(f"invalid local service observation: {exc}") from exc
        return ToolObservation.from_dict(observation)

    def _round_trip(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        message = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(self._timeout)
            client.connect(str(self._socket_path))
            client.sendall(message)
            raw_response = _read_line(client)
        response = json.loads(raw_response.decode("utf-8"))
        if not isinstance(response, dict):
            raise RuntimeError("local service response must be a JSON object")
        return response


def _app_control_for_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> DryRunAppControl | LocalServiceAppControl:
    if args.token and args.token_file:
        raise ValueError("--token and --token-file are mutually exclusive")
    if args.dry_run:
        return DryRunAppControl()

    socket_path = args.socket_path
    token = args.token
    timeout = 10.0
    if args.config:
        config = load_app_control_config(args.config)
        timeout = config.computer_use.timeout_ms / 1000.0
        helper = config.helper
        if socket_path is None and helper.endpoint:
            if helper.transport != "unix_socket":
                raise ValueError(
                    "wechat-desktop-tool local service mode requires "
                    "helper.transport='unix_socket' when using helper.endpoint "
                    "from --config"
                )
            socket_path = helper.endpoint
        if token is None and not args.token_file:
            token = helper.token
    if not socket_path:
        parser.error(
            "--socket-path or helper.endpoint in --config is required unless "
            "--dry-run is set"
        )
    if args.token_file:
        token = Path(args.token_file).expanduser().read_text(encoding="utf-8").strip()
    return LocalServiceAppControl(socket_path, token=token, timeout=timeout)


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


def _read_line(client: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    line, _, _ = b"".join(chunks).partition(b"\n")
    if not line:
        raise RuntimeError("local service closed without a response")
    return line


if __name__ == "__main__":
    raise SystemExit(main())
