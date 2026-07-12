"""Run the remaining Accessibility Selector Engine WeChat smoke checklist.

Run from the repository root after starting the local app-control service:

    /opt/anaconda3/bin/python examples/wechat_selector_engine_smoke_test.py \
        --head-sha "$(git rev-parse HEAD)"

The script opens WeChat, inspects the normalized window model, lists visible
conversations and contacts, opens one target contact, reads visible messages,
verifies profile override loading/fallback, and verifies expired actionRefs
fail before any backend or fallback execution. It does not draft or submit
messages.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import importlib
import importlib.resources
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
from typing import Any
from uuid import uuid4

import app_control_protocol
from app_control_protocol import (
    ProtocolValidationError,
    ToolCommand,
    ToolError,
    ToolObservation,
    ToolStatus,
    load_app_control_config,
    validate_protocol_payload,
)
import computer_use_macos
from computer_use_macos import UnixSocketServiceClient, readiness_command
from computer_use_macos.selectors import parse_selector_profile
import wechat_desktop_tool
from wechat_desktop_tool import WeChatDesktopTool
from wechat_desktop_tool.profiles import (
    DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE,
    load_packaged_selector_profile,
    load_selector_profile,
)


DEFAULT_CONFIG = "./app-control.toml"
DEFAULT_CONTACT = "文件传输助手"
DEFAULT_CONTACT_LIMIT = 30
DEFAULT_CONVERSATION_LIMIT = 30
DEFAULT_MESSAGE_LIMIT = 30
DEFAULT_OUTPUT = "./wechat-selector-engine-smoke-test.json"
DEFAULT_SOCKET_PATH = "/tmp/app-control.sock"
DEFAULT_TOKEN_FILE = "./app-control.token"
DEFAULT_WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"
PROOF_SCHEMA = "macos_computer_use.release.wechat_selector_engine_proof.v2"
PROOF_REPOSITORY = "zhanghao1903/macos-computer-use"
MAX_PROOF_COLLECTION_LIMIT = 30
_HEAD_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PROOF_CHECKS = (
    "systemOpenWeChat",
    "readiness",
    "openWeChat",
    "inspectWindow",
    "listConversations",
    "openContact",
    "readVisibleMessages",
    "listContacts",
    "validProfileOverride",
    "invalidProfileFallback",
)
_TIMING_KEYS = (
    "openWeChat",
    "inspectWindow",
    "listConversations",
    "openContact",
    "readVisibleMessages",
    "listContacts",
)
_SENSITIVE_VALUE_KEYS = {
    "axpath",
    "configpath",
    "contact",
    "displayname",
    "executable",
    "messagetext",
    "rawobservation",
    "socketpath",
    "text",
    "token",
    "windowtitle",
}
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._:-])/(?!/)[^\s]*"
)


class LocalServiceAppControlAdapter:
    """Adapt UnixSocketServiceClient to the AppControlClient protocol."""

    def __init__(self, service_client: Any) -> None:
        self._service_client = service_client
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


def run_selector_engine_smoke_test(
    *,
    head_sha: str,
    config_path: str | Path | None,
    output_path: str | Path,
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
    token: str | None = None,
    timeout: float = 30.0,
    contact: str = DEFAULT_CONTACT,
    contact_limit: int = DEFAULT_CONTACT_LIMIT,
    conversation_limit: int = DEFAULT_CONVERSATION_LIMIT,
    message_limit: int = DEFAULT_MESSAGE_LIMIT,
    system_open: bool = True,
    wechat_bundle_id: str = DEFAULT_WECHAT_BUNDLE_ID,
    valid_profile_path: str | Path | None = None,
    invalid_profile_path: str | Path | None = None,
    system_open_runner: Any | None = None,
    service_client: Any | None = None,
    private_debug_output_path: str | Path | None = None,
) -> dict[str, Any]:
    _validate_head_sha(head_sha)
    _validate_proof_limit("contact_limit", contact_limit)
    _validate_proof_limit("conversation_limit", conversation_limit)
    _validate_proof_limit("message_limit", message_limit)
    if private_debug_output_path is not None and (
        Path(output_path).expanduser().resolve()
        == Path(private_debug_output_path).expanduser().resolve()
    ):
        raise ValueError("private debug output must differ from public proof output")

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
            "system_open_wechat" if system_opened["success"] is not True else "readiness",
            readiness,
        )
    )
    inspected = (
        wechat.inspect_window(include_actionables=True)
        if opened.success
        else _skipped_observation("inspect_window", "open_wechat", opened)
    )
    conversations = (
        wechat.list_conversations(limit=conversation_limit)
        if opened.success
        else _skipped_observation("list_conversations", "open_wechat", opened)
    )
    expired_action_ref = _expired_action_ref_check(
        wechat,
        inspected,
        conversations,
    )
    opened_contact = (
        wechat.open_contact(contact)
        if opened.success
        else _skipped_observation("open_contact", "open_wechat", opened)
    )
    visible_messages = (
        wechat.read_visible_messages(limit=message_limit)
        if opened_contact.success
        else _skipped_observation(
            "read_visible_messages",
            "open_contact",
            opened_contact,
        )
    )
    contacts = (
        wechat.list_contacts(limit=contact_limit)
        if opened.success
        else _skipped_observation("list_contacts", "open_wechat", opened)
    )
    profile_checks = _profile_override_checks(
        valid_profile_path=valid_profile_path,
        invalid_profile_path=invalid_profile_path,
    )

    checks: dict[str, bool] = {
        "systemOpenWeChat": system_opened["success"] is True,
        "readiness": readiness.success,
        "openWeChat": opened.success,
        "inspectWindow": inspected.success,
        "listConversations": conversations.success,
        "expiredActionRef": expired_action_ref["success"] is True,
        "openContact": opened_contact.success,
        "readVisibleMessages": visible_messages.success,
        "listContacts": contacts.success,
        "validProfileOverride": profile_checks["validOverride"]["success"] is True,
        "invalidProfileFallback": profile_checks["invalidFallback"]["success"] is True,
    }

    live_result: dict[str, Any] = {
        "schema": "macos_computer_use.sdk.wechat_selector_engine_smoke_test.v1",
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
            "contact": contact,
            "contactLimit": contact_limit,
            "conversationLimit": conversation_limit,
            "messageLimit": message_limit,
            "systemOpen": system_open,
            "wechatBundleId": wechat_bundle_id,
        },
        "systemOpenWeChat": system_opened,
        "readiness": readiness.to_dict(),
        "openWeChat": opened.to_dict(),
        "inspectWindow": inspected.to_dict(),
        "listConversations": conversations.to_dict(),
        "expiredActionRef": expired_action_ref,
        "openContact": opened_contact.to_dict(),
        "readVisibleMessages": visible_messages.to_dict(),
        "listContacts": contacts.to_dict(),
        "profileOverrides": profile_checks,
        "appControlCommands": [
            app_control_command.to_dict()
            for app_control_command in app_control.commands
        ],
        "summary": {
            "success": all(checks.values()),
            "checks": checks,
            "conversationCount": _row_count(conversations),
            "contactCount": _row_count(contacts),
            "messageCount": _message_count(visible_messages),
            "failedStep": _failed_step(checks),
        },
    }
    proof = _build_selector_proof_v2(live_result, head_sha=head_sha)
    _write_json(output_path, proof)
    if private_debug_output_path is not None:
        private_output = Path(private_debug_output_path).expanduser().resolve()
        _write_json(private_output, live_result)
    return proof


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        socket_path, token, timeout = _service_settings(args)
        payload = run_selector_engine_smoke_test(
            head_sha=args.head_sha,
            config_path=args.config,
            output_path=args.output,
            socket_path=socket_path,
            token=token,
            timeout=timeout,
            contact=args.contact,
            contact_limit=args.contact_limit,
            conversation_limit=args.conversation_limit,
            message_limit=args.message_limit,
            system_open=not args.skip_system_open,
            wechat_bundle_id=args.wechat_bundle_id,
            valid_profile_path=args.valid_profile_path,
            invalid_profile_path=args.invalid_profile_path,
            private_debug_output_path=args.private_debug_output,
        )
    except Exception as exc:
        print(f"wechat selector engine smoke test failed: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "schema": payload["schema"],
                "checks": payload["checks"],
                "failedStep": payload["failedStep"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"wrote: {Path(args.output).expanduser()}")
    return 0 if _proof_passed(payload) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the WeChat selector-engine live smoke checklist.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("APP_CONTROL_CONFIG", DEFAULT_CONFIG),
    )
    configured_head_sha = os.environ.get("GITHUB_SHA")
    parser.add_argument(
        "--head-sha",
        default=configured_head_sha,
        required=configured_head_sha is None,
        help="Exact 40-character lowercase source commit SHA for proof v2.",
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
    parser.add_argument("--contact-limit", type=int, default=DEFAULT_CONTACT_LIMIT)
    parser.add_argument(
        "--conversation-limit",
        type=int,
        default=DEFAULT_CONVERSATION_LIMIT,
    )
    parser.add_argument("--message-limit", type=int, default=DEFAULT_MESSAGE_LIMIT)
    parser.add_argument("--skip-system-open", action="store_true")
    parser.add_argument("--wechat-bundle-id", default=DEFAULT_WECHAT_BUNDLE_ID)
    parser.add_argument("--valid-profile-path")
    parser.add_argument("--invalid-profile-path")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--private-debug-output",
        help=(
            "Optional private local path for raw smoke diagnostics. Never attach "
            "this file to a release."
        ),
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


def _expired_action_ref_check(
    wechat: WeChatDesktopTool,
    inspected: ToolObservation,
    conversations: ToolObservation,
) -> dict[str, Any]:
    action_ref = _first_action_ref(inspected, conversations)
    if action_ref is None:
        skipped = _skipped_observation(
            "execute_action",
            "inspect_window",
            inspected,
        )
        return {
            "success": False,
            "reason": "missing_live_action_ref",
            "executeAction": skipped.to_dict(),
        }
    expired_ref = dict(action_ref)
    expired_ref["expiresAt"] = "1970-01-01T00:00:00Z"
    result = wechat.execute_action(expired_ref)
    return {
        "success": (
            result.success is False
            and result.failure_kind == "wechat_action_ref_expired"
        ),
        "failureKind": result.failure_kind,
        "executeAction": result.to_dict(),
    }


def _profile_override_checks(
    *,
    valid_profile_path: str | Path | None,
    invalid_profile_path: str | Path | None,
) -> dict[str, Any]:
    packaged = load_packaged_selector_profile()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        valid_path = (
            Path(valid_profile_path).expanduser()
            if valid_profile_path is not None
            else _write_generated_valid_profile(tmp_path)
        )
        invalid_path = (
            Path(invalid_profile_path).expanduser()
            if invalid_profile_path is not None
            else _write_generated_invalid_profile(tmp_path)
        )
        valid_direct = parse_selector_profile(
            tomllib.loads(valid_path.read_text(encoding="utf-8"))
        )
        valid_loaded = load_selector_profile(valid_path)
        invalid_loaded = load_selector_profile(invalid_path)
        return {
            "validOverride": {
                "success": valid_loaded.profile_id == valid_direct.profile_id,
                "path": str(valid_path),
                "profileId": valid_loaded.profile_id,
                "expectedProfileId": valid_direct.profile_id,
            },
            "invalidFallback": {
                "success": invalid_loaded.profile_id == packaged.profile_id,
                "path": str(invalid_path),
                "profileId": invalid_loaded.profile_id,
                "packagedProfileId": packaged.profile_id,
            },
        }


def _write_generated_valid_profile(directory: Path) -> Path:
    profile_text = (
        importlib.resources.files("wechat_desktop_tool")
        .joinpath(DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE)
        .read_text(encoding="utf-8")
    )
    profile_text = profile_text.replace(
        'profile_id = "wechat.macos"',
        'profile_id = "wechat.selector_engine_smoke_override"',
        1,
    )
    path = directory / "wechat-selector-engine-smoke-valid.toml"
    path.write_text(profile_text, encoding="utf-8")
    return path


def _write_generated_invalid_profile(directory: Path) -> Path:
    path = directory / "wechat-selector-engine-smoke-invalid.toml"
    path.write_text(
        'schema_version = "app-control.selector-profile.v1"\n'
        'profile_id = "wechat.invalid"\n',
        encoding="utf-8",
    )
    return path


def _first_action_ref(
    *observations: ToolObservation,
) -> dict[str, Any] | None:
    def visit(value: Any) -> dict[str, Any] | None:
        if isinstance(value, Mapping):
            action_ref = value.get("actionRef")
            if isinstance(action_ref, Mapping):
                return dict(action_ref)
            for child in value.values():
                found = visit(child)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = visit(child)
                if found is not None:
                    return found
        return None

    for observation in observations:
        found = visit(observation.observation)
        if found is not None:
            return found
    return None


def _row_count(observation: ToolObservation) -> int:
    items = observation.observation.get("items") if observation.observation else None
    return len(items) if isinstance(items, list) else 0


def _message_count(observation: ToolObservation) -> int:
    messages = (
        observation.observation.get("messages") if observation.observation else None
    )
    return len(messages) if isinstance(messages, list) else 0


def _validate_head_sha(head_sha: str) -> None:
    if not isinstance(head_sha, str) or not _HEAD_SHA_PATTERN.fullmatch(head_sha):
        raise ValueError("head_sha must be exactly 40 lowercase hexadecimal characters")


def _validate_proof_limit(name: str, value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_PROOF_COLLECTION_LIMIT:
        raise ValueError(f"{name} must be between 1 and 30")


def _build_selector_proof_v2(
    live_result: Mapping[str, Any],
    *,
    head_sha: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    _validate_head_sha(head_sha)
    summary = _mapping_value(live_result.get("summary"))
    raw_checks = _mapping_value(summary.get("checks"))
    options = _mapping_value(live_result.get("options"))
    contacts = _operation_items(live_result, "listContacts", "items")
    conversations = _operation_items(
        live_result,
        "listConversations",
        "items",
    )
    visible_messages = _operation_items(
        live_result,
        "readVisibleMessages",
        "messages",
    )
    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "source": {
            "repository": PROOF_REPOSITORY,
            "headSha": head_sha,
            "generatedAt": generated_at or _utc_now(),
            "packageVersions": {
                "app-control-protocol": app_control_protocol.__version__,
                "computer-use-macos": computer_use_macos.__version__,
                "wechat-desktop-tool": wechat_desktop_tool.__version__,
            },
        },
        "checks": {
            name: raw_checks.get(name) is True
            for name in _PROOF_CHECKS
        },
        "collections": {
            "contacts": {
                "requestedLimit": _integer_value(options.get("contactLimit")),
                "count": len(contacts),
                "items": [
                    {"semanticFieldsPresent": _contact_fields_present(item)}
                    for item in contacts
                ],
            },
            "conversations": {
                "requestedLimit": _integer_value(
                    options.get("conversationLimit")
                ),
                "count": len(conversations),
                "items": [
                    {
                        "semanticFieldsPresent": _conversation_fields_present(item),
                        "actionable": _conversation_actionable(item),
                    }
                    for item in conversations
                ],
            },
            "visibleMessages": {
                "requestedLimit": _integer_value(options.get("messageLimit")),
                "count": len(visible_messages),
                "items": [
                    {"nonEmptyTextObserved": _message_text_present(item)}
                    for item in visible_messages
                ],
            },
        },
        "safety": {
            "focusGatePassed": _focus_gate_passed(live_result),
            "targetPostconditionPassed": _target_postcondition_passed(live_result),
            "expiredActionRefRejected": _expired_action_ref_rejected(live_result),
            "frameDerivedCoordinatesOnly": _frame_derived_coordinates_only(
                live_result
            ),
            "rawObservationIncluded": False,
            "sensitiveFieldScanPassed": False,
        },
        "timingsMs": {
            name: _operation_duration_ms(live_result, name)
            for name in _TIMING_KEYS
        },
        "failedStep": summary.get("failedStep"),
    }
    proof["safety"]["sensitiveFieldScanPassed"] = (
        not _proof_contains_sensitive_content(
            proof,
            canaries=_sensitive_canaries(live_result),
        )
    )
    return proof


def _operation_items(
    live_result: Mapping[str, Any],
    operation_key: str,
    item_key: str,
) -> list[Mapping[str, Any]]:
    operation = _mapping_value(live_result.get(operation_key))
    observation = _mapping_value(operation.get("observation"))
    raw_items = observation.get(item_key)
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, Mapping)]


def _contact_fields_present(item: Mapping[str, Any]) -> bool:
    return _non_empty_string(item.get("displayName")) is not None and isinstance(
        item.get("element"),
        Mapping,
    )


def _conversation_fields_present(item: Mapping[str, Any]) -> bool:
    return _non_empty_string(item.get("displayName")) is not None and isinstance(
        item.get("element"),
        Mapping,
    )


def _conversation_actionable(item: Mapping[str, Any]) -> bool:
    if isinstance(item.get("actionRef"), Mapping):
        return True
    element = item.get("element")
    if not isinstance(element, Mapping):
        return False
    frame = element.get("frame")
    if not isinstance(frame, Mapping):
        return False
    action_id = _non_empty_string(item.get("actionId"))
    return (
        action_id is not None
        and action_id.endswith(".open")
        and all(
            isinstance(frame.get(key), int | float)
            and not isinstance(frame.get(key), bool)
            for key in ("x", "y", "width", "height")
        )
        and float(frame["width"]) > 0
        and float(frame["height"]) > 0
    )


def _message_text_present(item: Mapping[str, Any]) -> bool:
    return _non_empty_string(item.get("text")) is not None


def _focus_gate_passed(live_result: Mapping[str, Any]) -> bool:
    commands = _command_payloads(live_result)
    text_commands = [
        command for command in commands if command.get("operation") == "type_text"
    ]
    if not text_commands:
        return True
    opened_contact = _mapping_value(live_result.get("openContact"))
    if opened_contact.get("success") is not True:
        return False
    return all(
        _mapping_value(command.get("metadata")).get("phase") == "type_contact"
        for command in text_commands
    )


def _target_postcondition_passed(live_result: Mapping[str, Any]) -> bool:
    opened_contact = _mapping_value(live_result.get("openContact"))
    if opened_contact.get("success") is not True:
        return False
    observation = _mapping_value(opened_contact.get("observation"))
    current_chat = _mapping_value(observation.get("currentChat"))
    target = _non_empty_string(observation.get("target"))
    title = _non_empty_string(current_chat.get("title"))
    if target is None or title is None:
        return False
    normalized_target = target.casefold()
    normalized_title = title.casefold()
    return (
        normalized_target == normalized_title
        or normalized_target in normalized_title
        or normalized_title in normalized_target
    )


def _expired_action_ref_rejected(live_result: Mapping[str, Any]) -> bool:
    expired = _mapping_value(live_result.get("expiredActionRef"))
    return (
        expired.get("success") is True
        and expired.get("failureKind") == "wechat_action_ref_expired"
    )


def _frame_derived_coordinates_only(live_result: Mapping[str, Any]) -> bool:
    for command in _command_payloads(live_result):
        if command.get("operation") != "click":
            continue
        input_payload = _mapping_value(command.get("input"))
        if not isinstance(input_payload.get("coordinates"), Mapping):
            continue
        metadata = _mapping_value(command.get("metadata"))
        if metadata.get("coordinateSource") != "accessibility_frame":
            return False
    return True


def _command_payloads(live_result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_commands = live_result.get("appControlCommands")
    if not isinstance(raw_commands, list):
        return []
    return [item for item in raw_commands if isinstance(item, Mapping)]


def _operation_duration_ms(
    live_result: Mapping[str, Any],
    operation_key: str,
) -> int:
    operation = _mapping_value(live_result.get(operation_key))
    timing = _mapping_value(operation.get("timing"))
    return _integer_value(timing.get("durationMs"))


def _sensitive_canaries(live_result: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                normalized_key = str(child_key).casefold()
                visit(child_value, normalized_key)
            return
        if isinstance(value, list):
            for child in value:
                visit(child, key)
            return
        if key in _SENSITIVE_VALUE_KEYS and isinstance(value, str) and value:
            values.add(value)

    visit(live_result)
    return tuple(sorted(values))


def _proof_contains_sensitive_content(
    proof: Mapping[str, Any],
    *,
    canaries: Sequence[str],
) -> bool:
    normalized_canaries = tuple(
        value.casefold() for value in canaries if value.strip()
    )

    def visit(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(visit(child) for child in value.values())
        if isinstance(value, list):
            return any(visit(child) for child in value)
        if not isinstance(value, str):
            return False
        normalized = value.casefold()
        return bool(_ABSOLUTE_PATH_PATTERN.search(value)) or any(
            canary in normalized for canary in normalized_canaries
        )

    return visit(proof)


def _proof_passed(proof: Mapping[str, Any]) -> bool:
    checks = _mapping_value(proof.get("checks"))
    collections = _mapping_value(proof.get("collections"))
    safety = _mapping_value(proof.get("safety"))
    timings = _mapping_value(proof.get("timingsMs"))
    collections_passed = all(
        1 <= _integer_value(_mapping_value(collections.get(name)).get("count"))
        <= _integer_value(
            _mapping_value(collections.get(name)).get("requestedLimit")
        )
        for name in ("contacts", "conversations", "visibleMessages")
    )
    safety_passed = all(
        safety.get(name) is True
        for name in (
            "focusGatePassed",
            "targetPostconditionPassed",
            "expiredActionRefRejected",
            "frameDerivedCoordinatesOnly",
            "sensitiveFieldScanPassed",
        )
    ) and safety.get("rawObservationIncluded") is False
    timings_passed = all(
        0 <= _integer_value(timings.get(name)) <= 3_000
        for name in _TIMING_KEYS
    )
    return (
        proof.get("schema") == PROOF_SCHEMA
        and set(checks) == set(_PROOF_CHECKS)
        and all(checks.get(name) is True for name in _PROOF_CHECKS)
        and collections_passed
        and safety_passed
        and timings_passed
        and proof.get("failedStep") is None
    )


def _mapping_value(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _integer_value(value: Any) -> int:
    return value if type(value) is int else -1


def _non_empty_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _failed_step(checks: Mapping[str, bool]) -> str | None:
    for name, passed in checks.items():
        if not passed:
            return name
    return None


def _skipped_observation(
    operation: str,
    failed_step: str,
    failed: ToolObservation,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=f"wechat-selector-engine-smoke:{operation}:skipped",
        tool="wechat.desktop",
        operation=operation,
        status=ToolStatus.FAILED,
        error=ToolError(
            failure_kind=f"{failed_step}_failed",
            message=f"Skipped {operation} because {failed_step} failed.",
            retryable=False,
            evidence={failed_step: failed.to_dict()},
        ),
        summary=f"Skipped {operation}.",
        observation={
            "schema": "macos_computer_use.sdk.wechat_selector_engine_smoke_test.skipped.v1",
            "operation": operation,
            "failedStep": failed_step,
        },
    )


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    return command if isinstance(command, ToolCommand) else ToolCommand.from_dict(command)


def _existing_config_or_none(config_path: str | Path | None) -> Path | None:
    if config_path is None:
        return None
    path = Path(config_path).expanduser()
    return path if path.exists() else None


def _open_wechat_process(
    bundle_id: str,
    *,
    runner: Any | None = None,
) -> dict[str, Any]:
    run = runner or subprocess.run
    commands = [
        ["open", "-b", bundle_id],
        ["osascript", "-e", 'tell application id "com.tencent.xinWeChat" to activate'],
    ]
    attempts: list[dict[str, Any]] = []
    success = False
    for command in commands:
        try:
            completed = run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            returncode = int(getattr(completed, "returncode", 1))
            attempts.append(
                {
                    "command": command,
                    "returnCode": returncode,
                    "stdout": getattr(completed, "stdout", ""),
                    "stderr": getattr(completed, "stderr", ""),
                }
            )
            success = success or returncode == 0
        except OSError as exc:
            attempts.append({"command": command, "error": repr(exc)})
    return {
        "operation": "system_open_wechat",
        "success": success,
        "bundleId": bundle_id,
        "attempts": attempts,
    }


def _service_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _import_diagnostics() -> dict[str, Any]:
    return {
        "app_control_protocol": _service_module_available("app_control_protocol"),
        "computer_use_macos": _service_module_available("computer_use_macos"),
        "wechat_desktop_tool": _service_module_available("wechat_desktop_tool"),
    }


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path).expanduser()
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
