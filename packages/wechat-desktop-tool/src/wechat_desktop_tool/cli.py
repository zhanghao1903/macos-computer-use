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

from .commands import WECHAT_TOOL
from .models import wechat_message_hash
from .tool import WeChatDesktopTool

LOCAL_SERVICE_TIMEOUT_GRACE_SECONDS = 5.0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wechat-desktop-tool")
    subcommands = parser.add_subparsers(dest="command")
    examples = subcommands.add_parser("examples", help="runnable examples")
    example_commands = examples.add_subparsers(dest="example_command")
    _add_send_message_parser(example_commands)
    _add_inspect_window_parser(example_commands)

    args = parser.parse_args(argv)
    if args.command == "examples" and args.example_command == "send-message":
        try:
            return _run_send_message_example(args, parser)
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
    if args.command == "examples" and args.example_command == "inspect-window":
        try:
            return _run_inspect_window_example(args, parser)
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
    send.add_argument(
        "--assume-current-chat",
        action="store_true",
        help=(
            "assume the currently open WeChat chat is the requested contact "
            "when the window title cannot verify it"
        ),
    )
    send.add_argument(
        "--allow-focus-select",
        action="store_true",
        help=(
            "allow the example to press the configured submit key to select a "
            "contact search result"
        ),
    )


def _add_inspect_window_parser(
    subcommands: argparse._SubParsersAction[object],
) -> None:
    inspect = subcommands.add_parser(
        "inspect-window",
        help="open WeChat, inspect the current window, and emit JSON",
    )
    inspect.add_argument("--config")
    inspect.add_argument("--socket-path")
    inspect.add_argument("--token")
    inspect.add_argument("--token-file")
    inspect.add_argument("--dry-run", action="store_true")
    inspect.add_argument(
        "--include-raw",
        action="store_true",
        help="include the raw app-control observe payload in the output",
    )
    inspect.add_argument(
        "--no-actionables",
        action="store_true",
        help="omit the flattened actionable region list from the window model",
    )
    inspect.add_argument(
        "--output",
        help="write the full JSON result to this file; use '-' or omit for stdout",
    )


def _run_send_message_example(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    app_control = _app_control_for_args(args, parser)
    tool = WeChatDesktopTool.from_config(app_control, args.config)
    is_dry_run = isinstance(app_control, DryRunAppControl)
    allow_focus_select = args.allow_focus_select or is_dry_run
    if args.submit:
        if allow_focus_select:
            result = tool.send_message(
                contact=args.contact,
                message=args.message,
                verify_after_submit=args.verify_after_submit,
            )
        else:
            focus = _focus_current_chat_for_example(
                tool,
                args.contact,
                assume_current_chat=args.assume_current_chat,
            )
            if focus.success:
                draft = tool.draft_message(args.message)
                if draft.success:
                    submitted = tool.submit_draft()
                    result = (
                        _send_current_chat_success(
                            contact=args.contact,
                            message=args.message,
                            verify_after_submit=args.verify_after_submit,
                            focus=focus,
                            draft=draft,
                            submitted=submitted,
                        )
                        if submitted.success
                        else _nested_example_failure("submit_draft", submitted)
                    )
                else:
                    result = _nested_example_failure("draft_message", draft)
            else:
                result = _nested_example_failure("focus_contact", focus)
        output: dict[str, Any] = {"result": result.to_dict()}
        success = result.success
    else:
        focus = (
            tool.focus_contact(args.contact)
            if allow_focus_select
            else _focus_current_chat_for_example(
                tool,
                args.contact,
                assume_current_chat=args.assume_current_chat,
            )
        )
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


def _run_inspect_window_example(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    app_control = _app_control_for_args(args, parser)
    tool = WeChatDesktopTool.from_config(app_control, args.config)
    result = tool.inspect_window(
        include_raw=args.include_raw,
        include_actionables=not args.no_actionables,
    )
    output: dict[str, Any] = {"result": result.to_dict()}
    if isinstance(app_control, DryRunAppControl):
        output["appControlCommands"] = [
            command.to_dict() for command in app_control.commands
        ]

    output_json = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output and args.output != "-":
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output_path),
                    "success": result.success,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(output_json)
    return 0 if result.success else 1


def _focus_current_chat_for_example(
    tool: WeChatDesktopTool,
    contact: str,
    *,
    assume_current_chat: bool = False,
) -> ToolObservation:
    opened = tool.open_wechat()
    evidence = {"open_wechat": opened.to_dict()}
    if not opened.success:
        return ToolObservation.failure(
            command_id="wechat-example-focus-current-chat",
            tool=WECHAT_TOOL,
            operation="focus_contact",
            status=opened.status,
            error=ToolError(
                failure_kind=opened.failure_kind or "wechat_open_failed",
                message=opened.summary,
                retryable=opened.retryable or False,
                phase="focus_contact",
                operation="focus_contact",
                evidence=evidence,
            ),
            summary="Could not verify current WeChat chat.",
        )
    current_chat = _string_from_mapping(
        opened.observation,
        "currentChatTitle",
        "current_chat_title",
        "windowTitle",
        "window_title",
    )
    confidence = _contact_confidence(contact, current_chat)
    if current_chat is not None and confidence >= 0.9:
        return ToolObservation.ok(
            command_id="wechat-example-focus-current-chat",
            tool=WECHAT_TOOL,
            operation="focus_contact",
            summary="Current WeChat chat already matches requested contact.",
            observation={
                "focusedContact": contact,
                "confidence": confidence,
                "currentChatTitle": current_chat,
                "autoSelectContact": False,
            },
            evidence=evidence,
        )
    if assume_current_chat:
        return ToolObservation.ok(
            command_id="wechat-example-focus-current-chat",
            tool=WECHAT_TOOL,
            operation="focus_contact",
            summary="Assuming current WeChat chat matches requested contact.",
            observation={
                "focusedContact": contact,
                "confidence": confidence,
                "currentChatTitle": current_chat,
                "autoSelectContact": False,
                "assumedCurrentChat": True,
            },
            evidence=evidence,
        )
    current_chat_display = current_chat or "unknown"
    return ToolObservation.failure(
        command_id="wechat-example-focus-current-chat",
        tool=WECHAT_TOOL,
        operation="focus_contact",
        status=ToolStatus.NOT_FOUND,
        error=ToolError(
            failure_kind="contact_not_focused",
            message=(
                "Current WeChat chat does not match requested contact: "
                f"{current_chat_display}"
            ),
            recovery_hint=(
                "Open the target chat manually, or rerun with "
                "--allow-focus-select after confirming the search shortcut is safe "
                "for this WeChat version."
            ),
            retryable=True,
            phase="focus_contact",
            operation="focus_contact",
            evidence=evidence,
        ),
        summary="Current WeChat chat does not match requested contact.",
        observation={
            "focusedContact": None,
            "requestedContact": contact,
            "currentChatTitle": current_chat,
            "autoSelectContact": False,
        },
    )


def _nested_example_failure(phase: str, observation: ToolObservation) -> ToolObservation:
    return ToolObservation.failure(
        command_id=f"wechat-example-{phase}-failed",
        tool=WECHAT_TOOL,
        operation="send_message",
        status=observation.status,
        error=ToolError(
            failure_kind=observation.failure_kind or f"{phase}_failed",
            message=observation.summary,
            recovery_hint=observation.recovery_hint,
            retryable=observation.retryable or False,
            phase=phase,
            operation=observation.operation,
            evidence={phase: observation.to_dict()},
        ),
        summary=f"Send-message example failed during {phase}.",
    )


def _send_current_chat_success(
    *,
    contact: str,
    message: str,
    verify_after_submit: bool,
    focus: ToolObservation,
    draft: ToolObservation,
    submitted: ToolObservation,
) -> ToolObservation:
    return ToolObservation.ok(
        command_id="wechat-example-send-current-chat",
        tool=WECHAT_TOOL,
        operation="send_message",
        summary="Submitted WeChat message in the current verified chat.",
        observation={
            "focusedContact": contact,
            "submitted": True,
            "messageHash": wechat_message_hash(message),
            "messageChars": len(message),
            "verificationRequested": verify_after_submit,
            "autoSelectContact": False,
        },
        evidence={
            "focus": focus.to_dict(),
            "draft": draft.to_dict(),
            "submit": submitted.to_dict(),
        },
    )


def _string_from_mapping(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _contact_confidence(contact: str, current_chat_title: str | None) -> float:
    if current_chat_title is None:
        return 0.0
    normalized_contact = contact.casefold()
    normalized_title = current_chat_title.casefold()
    if normalized_contact == normalized_title:
        return 1.0
    if normalized_contact in normalized_title or normalized_title in normalized_contact:
        return 0.95
    return 0.0


class DryRunAppControl:
    def __init__(self) -> None:
        self.commands: list[ToolCommand] = []
        self._last_typed_text: str | None = None

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = _coerce_command(command)
        self.commands.append(tool_command)
        if tool_command.operation == "type_text":
            text = tool_command.input.get("text")
            if isinstance(text, str) and text:
                self._last_typed_text = text
        observation: dict[str, Any] = {
            "input": tool_command.input,
            "dryRun": True,
        }
        phase = tool_command.metadata.get("phase") if tool_command.metadata else None
        if tool_command.operation == "observe":
            observation.update(
                {
                    "frontmostApp": "WeChat",
                    "frontmostBundleId": "com.tencent.xinWeChat",
                    "windowTitle": "微信 (聊天)",
                }
            )
            if isinstance(phase, str) and phase.startswith("verify_search_focus"):
                observation["accessibility"] = {
                    "available": True,
                    "focusedElement": {
                        "role": "AXTextField",
                        "roleDescription": "search field",
                        "description": "搜索",
                        "frame": {
                            "x": 80,
                            "y": 120,
                            "width": 240,
                            "height": 28,
                        },
                    },
                }
            elif phase == "verify_contact" and self._last_typed_text is not None:
                observation["windowTitle"] = f"{self._last_typed_text} - WeChat"
        return ToolObservation.ok(
            command_id=tool_command.command_id,
            tool=tool_command.tool,
            operation=tool_command.operation,
            summary=f"dry-run app-control command: {tool_command.operation}",
            observation=observation,
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
        timeout = _socket_timeout_for_payload(payload, default=self._timeout)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            try:
                client.connect(str(self._socket_path))
                client.sendall(message)
                raw_response = _read_line(client)
            except TimeoutError as exc:
                raise RuntimeError(
                    "timed out waiting for local app-control service response "
                    f"after {timeout:.1f}s"
                ) from exc
            except OSError as exc:
                raise RuntimeError(
                    f"local app-control service request failed: {exc}"
                ) from exc
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


def _socket_timeout_for_payload(payload: Mapping[str, Any], *, default: float) -> float:
    command = payload.get("command")
    if not isinstance(command, Mapping):
        return default
    raw_timeout = command.get("timeoutMs")
    if raw_timeout is None:
        raw_timeout = command.get("timeout_ms")
    if (
        isinstance(raw_timeout, int | float)
        and not isinstance(raw_timeout, bool)
        and raw_timeout > 0
    ):
        command_timeout = raw_timeout / 1000.0 + LOCAL_SERVICE_TIMEOUT_GRACE_SECONDS
        return max(default, command_timeout)
    return default


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
