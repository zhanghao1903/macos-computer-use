"""WeChat chat observation, message reading, drafting, and send workflows."""

from __future__ import annotations

from typing import cast

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._contact_operations import _focus_contact, _open_contact
from ._diagnostics import (
    _bool_input,
    _failure,
    _nested_failure,
    _observation_indicates_input_not_focused,
    _positive_int,
    _required_input,
    _send_unverified,
    _string_from_observation,
    _string_input,
    _wechat_environment,
)
from ._mapped_controls import _query_mapped_collection
from ._query_mapping import (
    _failure_from_selector_result,
    _node_from_selector_element,
    _query_nodes,
    _query_truncated,
)
from ._row_parsing import (
    _chat_title_from_query_nodes,
    _current_chat_title,
    _message_observed,
    _messages_from_observation,
    _messages_from_query_nodes,
    _next_page_token,
)
from ._runtime import (
    _from_app_control_failure,
    _open_wechat_phase_failure,
    _PhaseEventCollector,
    _safe_app_control_observation,
    _wechat_identity_failure,
    _wechat_login_failure,
    _WeChatSelectorQueryRunner,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL
from .models import wechat_message_hash
from .profiles import build_packaged_selector_resolver


def _read_contact_messages(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    contact = _required_input(command, "contact")
    limit = _positive_int(command.input.get("limit"), default=30)
    opened = _open_contact(
        runtime,
        runtime._command(
            "open_contact",
            {"contact": contact},
            parent=command,
        ),
        phase_events=phase_events,
    )
    if not opened.success:
        return _nested_failure(command, "open_contact", opened)
    messages = _read_visible_messages(
        runtime,
        runtime._command(
            "read_visible_messages",
            {"limit": limit},
            parent=command,
        ),
        phase_events=phase_events,
    )
    if not messages.success:
        return _nested_failure(command, "read_visible_messages", messages)
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Opened WeChat contact and read visible messages.",
        observation={
            "schema": "wechat.contact_messages.v1",
            "target": contact,
            "openContact": opened.observation,
            "messages": messages.observation,
        },
        evidence={
            "openContact": opened.to_dict(),
            "readVisibleMessages": messages.to_dict(),
        },
    )


def _observe_current_chat(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    include_visible_messages = _bool_input(
        command,
        "includeVisibleMessages",
        "include_visible_messages",
        default=True,
    )
    input_payload = runtime._target_app_input()
    if include_visible_messages:
        input_payload["includeVisibleText"] = True
    result = runtime._app_control_command(
        command,
        phase="observe_current_chat",
        operation="observe",
        input=input_payload,
        phase_events=phase_events,
    )
    if not result.success:
        return _from_app_control_failure(command, "wechat_not_ready", result)
    identity_failure = _wechat_identity_failure(command, runtime.config, result)
    if identity_failure is not None:
        return identity_failure
    login_failure = _wechat_login_failure(command, runtime.config, result)
    if login_failure is not None:
        return login_failure
    messages = _messages_from_observation(result, limit=20)
    window_title = _string_from_observation(
        result,
        "windowTitle",
        "window_title",
        "title",
    )
    frontmost_app = _string_from_observation(
        result,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    )
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Observed current WeChat chat.",
        observation={
            "appName": runtime.config.app_name,
            "bundleId": runtime.config.bundle_id,
            "frontmostApp": frontmost_app or runtime.config.app_name,
            "windowTitle": window_title,
            "currentChatTitle": _current_chat_title(
                window_title,
                runtime.config.app_name,
            ),
            "wechatEnvironment": _wechat_environment(runtime.config, result),
            "visibleMessages": cast(
                JsonValue,
                [message.to_dict() for message in messages],
            ),
            "messageCount": len(messages),
            "appControlObservation": _safe_app_control_observation(result),
        },
        evidence={"observe": _safe_app_control_observation(result)},
    )


def _read_visible_messages(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    limit = _positive_int(command.input.get("limit"), default=20)
    evidence: dict[str, JsonValue] = {}
    opened = runtime._open_wechat_phase(
        command,
        evidence,
        phase_events=phase_events,
    )
    if not opened.success:
        return _open_wechat_phase_failure(command, opened, evidence)
    fast_messages = _read_visible_messages_with_control_map(
        runtime,
        command,
        limit=limit,
        evidence=evidence,
        phase_events=phase_events,
    )
    if fast_messages is not None:
        return fast_messages
    selector_runner = _WeChatSelectorQueryRunner(
        runtime,
        command,
        evidence=evidence,
        phase_prefix="selectors.messages",
        phase_events=phase_events,
    )
    resolver = build_packaged_selector_resolver(
        selector_runner,
        app_bundle_id=runtime.config.bundle_id or "",
        selector_profile=runtime.selector_profile,
    )
    chat_panel = resolver.resolve("regions.chatPanel")
    if chat_panel.status != "resolved" or not chat_panel.elements:
        return _failure_from_selector_result(
            command,
            chat_panel,
            failure_kind="message_region_not_found",
            message="Could not locate WeChat chat panel region.",
            evidence=evidence,
        )
    messages_result = runtime._query_descendants(
        command,
        root_node=_node_from_selector_element(chat_panel.elements[0]),
        phase="read_visible_messages:rows",
        role_in=["AXRow", "AXCell", "AXStaticText"],
        limit=max(limit * 4, 80),
        evidence=evidence,
        phase_events=phase_events,
    )
    if not messages_result.success:
        return _from_app_control_failure(
            command,
            "message_region_not_found",
            messages_result,
            evidence=evidence,
        )
    query_nodes = _query_nodes(messages_result)
    messages = _messages_from_query_nodes(query_nodes, limit=limit)
    chat_title = _chat_title_from_query_nodes(query_nodes)
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Read visible WeChat messages.",
        observation={
            "schema": "wechat.messages.v1",
            "chat": {"title": chat_title},
            "messages": cast(JsonValue, messages),
            "pagination": {
                "limit": limit,
                "canReadOlder": _query_truncated(messages_result),
                "olderPageToken": _next_page_token(
                    "messages",
                    messages_result,
                    direction="older",
                ),
            },
            "truncated": _query_truncated(messages_result),
        },
        evidence=evidence,
    )


def _read_visible_messages_with_control_map(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    limit: int,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    collection_query = _query_mapped_collection(
        runtime,
        command,
        "visibleMessages",
        semantic_limit=limit,
        evidence=evidence,
        phase_events=phase_events,
    )
    if collection_query is None:
        return None
    query_result, collection, nodes = collection_query
    messages = _messages_from_query_nodes(nodes, limit=limit)
    if not messages and nodes:
        return None
    chat_title = _chat_title_from_query_nodes(nodes)
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Read visible WeChat messages.",
        observation={
            "schema": "wechat.messages.v1",
            "chat": {"title": chat_title},
            "messages": cast(JsonValue, messages),
            "pagination": {
                "limit": limit,
                "canReadOlder": _query_truncated(query_result),
                "olderPageToken": _next_page_token(
                    "messages",
                    query_result,
                    direction="older",
                ),
            },
            "source": {
                "mode": "control_map",
                "mapId": runtime.control_map.map_id,
                "mapVersion": runtime.control_map.map_version,
                "collection": collection.collection_id,
            },
            "truncated": _query_truncated(query_result),
        },
        evidence=evidence,
    )


def _draft_message(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    message = _required_input(command, "message")
    if len(message) > runtime.config.max_message_chars:
        return _failure(
            command,
            status=ToolStatus.FAILED,
            failure_kind="draft_failed",
            message="message exceeds max_message_chars",
        )
    result = runtime._app_control_command(
        command,
        phase="draft_message",
        operation="type_text",
        input=runtime._target_app_input(text=message),
        phase_events=phase_events,
    )
    if not result.success:
        input_focus_failure = _input_focus_failure(command, result)
        if input_focus_failure is not None:
            return input_focus_failure
        return _from_app_control_failure(command, "draft_failed", result)
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Drafted WeChat message without submitting.",
        observation={
            "draftReady": True,
            "messageHash": wechat_message_hash(message),
            "messageChars": len(message),
        },
        evidence={"draft": _safe_app_control_observation(result)},
    )


def _submit_draft(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    method = _string_input(command, "method", default="keyboard_return")
    if method != "keyboard_return":
        return _failure(
            command,
            status=ToolStatus.FAILED,
            failure_kind="submit_failed",
            message=f"unsupported submit method: {method}",
        )
    result = runtime._app_control_command(
        command,
        phase="submit_draft",
        operation="press_key",
        input=runtime._target_app_input(key=runtime.config.submit_key),
        phase_events=phase_events,
    )
    if not result.success:
        return _failure(
            command,
            status=ToolStatus.UNKNOWN,
            failure_kind="submit_unknown",
            message="WeChat submit result is unknown; review manually.",
            recovery_hint="Check WeChat manually before retrying.",
            retryable=False,
            observation={
                "sendAttempted": True,
                "method": method,
            },
            evidence={"submit": _safe_app_control_observation(result)},
        )
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Submitted WeChat draft with keyboard Return.",
        observation={
            "submitted": True,
            "sendAttempted": True,
            "method": method,
        },
        evidence={"submit": _safe_app_control_observation(result)},
    )


def _send_message(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    contact = _required_input(command, "contact")
    message = _required_input(command, "message")
    verify_after_submit = _bool_input(
        command,
        "verifyAfterSubmit",
        "verify_after_submit",
        default=False,
    )
    verify_limit = _positive_int(command.input.get("verifyLimit"), default=20)
    focus = _focus_contact(
        runtime,
        runtime._command(
            "focus_contact",
            {"contact": contact},
            parent=command,
        ),
        phase_events=phase_events,
    )
    if not focus.success:
        return _nested_failure(command, "focus_contact", focus)
    draft = _draft_message(
        runtime,
        runtime._command(
            "draft_message",
            {"message": message},
            parent=command,
        ),
        phase_events=phase_events,
    )
    if not draft.success:
        return _nested_failure(command, "draft_message", draft)
    submitted = _submit_draft(
        runtime,
        runtime._command(
            "submit_draft",
            {"method": "keyboard_return"},
            parent=command,
        ),
        phase_events=phase_events,
    )
    if not submitted.success:
        return _nested_failure(command, "submit_draft", submitted)
    verification: ToolObservation | None = None
    verified = False
    if verify_after_submit:
        verification = _read_visible_messages(
            runtime,
            runtime._command(
                "read_visible_messages",
                {"limit": verify_limit},
                parent=command,
            ),
            phase_events=phase_events,
        )
        if not verification.success:
            return _send_unverified(
                command,
                contact=contact,
                message=message,
                focus=focus,
                draft=draft,
                submitted=submitted,
                verification=verification,
                reason=verification.summary,
            )
        verified = _message_observed(message, verification)
        if not verified:
            return _send_unverified(
                command,
                contact=contact,
                message=message,
                focus=focus,
                draft=draft,
                submitted=submitted,
                verification=verification,
                reason="Submitted message was not visible after send.",
            )
    evidence: dict[str, JsonValue] = {
        "focus": focus.to_dict(),
        "draft": draft.to_dict(),
        "submit": submitted.to_dict(),
    }
    if verification is not None:
        evidence["verification"] = verification.to_dict()
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Completed WeChat send-message convenience flow.",
        observation={
            "focusedContact": contact,
            "messageHash": wechat_message_hash(message),
            "submitted": True,
            "verified": verified,
            "verificationRequested": verify_after_submit,
        },
        evidence=evidence,
    )


def _input_focus_failure(
    command: ToolCommand,
    observation: ToolObservation,
) -> ToolObservation | None:
    if not _observation_indicates_input_not_focused(observation):
        return None
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="input_not_focused",
        message="WeChat chat input is not focused.",
        recovery_hint="Focus the chat input or rerun focus_contact before drafting.",
        retryable=True,
        observation={"draftReady": False, "inputFocused": False},
        evidence={"draft": _safe_app_control_observation(observation)},
    )
