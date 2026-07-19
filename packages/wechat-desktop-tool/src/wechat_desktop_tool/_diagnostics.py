"""Internal observation, failure, input, and event helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import re
import time
from typing import Any

from app_control_protocol import (
    ToolCommand,
    ToolError,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolObserver,
    ToolStatus,
)
from app_control_protocol.json_types import JsonValue

from .commands import WECHAT_TOOL
from .models import (
    WeChatDesktopConfig,
    WeChatVisibleMessage,
    wechat_message_hash,
)


_TEXT_LINE_RE = re.compile(
    r"^(?:(?:\[(?P<bracket_ts>[^\]]+)\]|(?P<plain_ts>\d{1,2}:\d{2}))\s+)?"
    r"(?:(?P<label>incoming|outgoing|received|sent|me|you)\s*:\s*)?"
    r"(?P<text>.+)$",
    re.IGNORECASE,
)


_INCOMING_LABELS = {"incoming", "received", "you"}


_OUTGOING_LABELS = {"outgoing", "sent", "me"}


_REDACTED = "[redacted]"


_SENSITIVE_INPUT_KEYS = {"text", "message"}


_LOGIN_REQUIRED_MARKERS = (
    "not logged in",
    "log in to wechat",
    "login to wechat",
    "sign in to wechat",
    "scan qr code",
)


_INPUT_NOT_FOCUSED_MARKERS = (
    "input not focused",
    "text field not focused",
    "no focused input",
    "editable target is not focused",
)


_SEARCH_FOCUS_MARKERS = (
    "search",
    "axsearch",
    "搜索",
    "搜一搜",
    "查找",
)


_CHAT_INPUT_MARKERS = (
    "message input",
    "chat input",
    "type a message",
    "send message",
    "输入消息",
    "聊天输入",
    "消息输入",
)


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    normalized = value.casefold()
    return any(marker.casefold() in normalized for marker in markers if marker)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _duration_ms(started_monotonic: float) -> int:
    return max(0, int(round((time.monotonic() - started_monotonic) * 1000)))


def _with_timing(
    observation: ToolObservation,
    *,
    started_at: str,
    duration_ms: int,
) -> ToolObservation:
    payload = observation.to_dict()
    timing = dict(payload.get("timing", {}))
    timing.setdefault("startedAt", started_at)
    timing.setdefault("durationMs", duration_ms)
    payload["timing"] = timing
    return ToolObservation.from_dict(payload)


def _safe_app_control_envelope(
    observation: ToolObservation,
    *,
    summary: str,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "schema": observation.schema,
        "commandId": observation.command_id,
        "tool": observation.tool,
        "operation": observation.operation,
        "status": observation.status.value,
        "success": observation.success,
        "summary": summary,
    }
    if observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    if observation.retryable is not None:
        payload["retryable"] = observation.retryable
    safe_timing: dict[str, JsonValue] = {}
    for key in ("startedAt", "durationMs", "endedAt", "timeoutMs"):
        value = observation.timing.get(key)
        if isinstance(value, str | int | float) and not isinstance(value, bool):
            safe_timing[key] = value
    if safe_timing:
        payload["timing"] = safe_timing
    return payload


def _safe_accessibility_status(
    accessibility: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    available = accessibility.get("available")
    if isinstance(available, bool):
        payload["available"] = available
    for key in (
        "failureKind",
        "timeoutSeconds",
        "treeFailureKind",
        "treeTimeoutSeconds",
        "treeAvailable",
    ):
        value = accessibility.get(key)
        if isinstance(value, str | int | float | bool):
            payload[key] = value
    payload["focusedWindowAvailable"] = isinstance(
        accessibility.get("focusedWindow"),
        Mapping,
    )
    return payload


def _safe_app_control_event_summary(observation: ToolObservation) -> str:
    if observation.operation == "accessibility_query":
        return (
            "Accessibility query completed."
            if observation.success
            else "Accessibility query failed."
        )
    if observation.operation == "accessibility_action":
        return (
            "Accessibility action completed."
            if observation.success
            else "Accessibility action failed."
        )
    if observation.operation == "click":
        return "Click completed." if observation.success else "Click failed."
    if observation.operation == "observe":
        return (
            "Observed application state."
            if observation.success
            else "Application observation failed."
        )
    return observation.summary


def _redact_input_text(value: JsonValue, *, in_input: bool = False) -> JsonValue:
    if isinstance(value, dict):
        redacted: dict[str, JsonValue] = {}
        for key, item in value.items():
            child_in_input = in_input or key == "input"
            if child_in_input and key in _SENSITIVE_INPUT_KEYS:
                redacted[key] = _REDACTED
            else:
                redacted[key] = _redact_input_text(
                    item,
                    in_input=child_in_input,
                )
        return redacted
    if isinstance(value, list):
        return [_redact_input_text(item, in_input=in_input) for item in value]
    return value


def _required_input(command: ToolCommand, key: str) -> str:
    value = command.input.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _string_input(command: ToolCommand, key: str, *, default: str) -> str:
    value = command.input.get(key)
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_string_input(command: ToolCommand, *keys: str) -> str | None:
    for key in keys:
        if key not in command.input:
            continue
        value = command.input.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value.strip()
    return None


def _action_ref_input(command: ToolCommand) -> dict[str, Any]:
    value = command.input.get("actionRef") or command.input.get("action_ref")
    if not isinstance(value, Mapping):
        raise ValueError("actionRef is required")
    schema = value.get("schema")
    if schema is not None and schema != "wechat.action_ref.v1":
        raise ValueError("actionRef.schema must be wechat.action_ref.v1")
    return dict(value)


def _executed_action_method(
    action_ref: Mapping[str, Any],
    result: ToolObservation,
) -> str:
    if result.operation == "click":
        return "selector_click"
    return (
        _optional_string_from_mapping(
            action_ref,
            "preferredMethod",
            "preferred_method",
        )
        or "accessibility_action"
    )


def _optional_string_from_mapping(
    payload: Mapping[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value.strip()
    return None


def _bool_input(command: ToolCommand, *keys: str, default: bool) -> bool:
    for key in keys:
        if key in command.input:
            value = command.input[key]
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
            return value
    return default


def _positive_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("limit must be a positive integer")
    return value


def _messages_from_observation(
    observation: ToolObservation,
    *,
    limit: int,
) -> tuple[WeChatVisibleMessage, ...]:
    messages, _truncated = _messages_from_observation_with_truncation(
        observation,
        limit=limit,
    )
    return messages


def _messages_from_observation_with_truncation(
    observation: ToolObservation,
    *,
    limit: int,
) -> tuple[tuple[WeChatVisibleMessage, ...], bool]:
    raw_messages = observation.observation.get("messages")
    if isinstance(raw_messages, list):
        messages: list[WeChatVisibleMessage] = []
        for item in raw_messages:
            message = _message_from_raw(item)
            if message is not None:
                messages.append(message)
            if len(messages) > limit:
                break
        return tuple(messages[:limit]), len(messages) > limit
    text_extract = observation.evidence.get(
        "textExtract"
    ) or observation.observation.get("textExtract")
    if isinstance(text_extract, str) and text_extract.strip():
        return _messages_from_text_extract_with_truncation(text_extract, limit=limit)
    return (), False


def _messages_from_text_extract(
    text_extract: str,
    *,
    limit: int,
) -> tuple[WeChatVisibleMessage, ...]:
    messages, _truncated = _messages_from_text_extract_with_truncation(
        text_extract,
        limit=limit,
    )
    return messages


def _messages_from_text_extract_with_truncation(
    text_extract: str,
    *,
    limit: int,
) -> tuple[tuple[WeChatVisibleMessage, ...], bool]:
    messages: list[WeChatVisibleMessage] = []
    for raw_line in text_extract.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        message = _message_from_text_line(line)
        if message is not None:
            messages.append(message)
        if len(messages) > limit:
            break
    return tuple(messages[:limit]), len(messages) > limit


def _message_from_text_line(line: str) -> WeChatVisibleMessage | None:
    match = _TEXT_LINE_RE.match(line)
    if match is None:
        return WeChatVisibleMessage(text=line)
    text = match.group("text").strip()
    if not text:
        return None
    return WeChatVisibleMessage(
        text=text,
        direction=_direction_from_text_label(match.group("label")),
        visible_timestamp=match.group("bracket_ts") or match.group("plain_ts"),
    )


def _direction_from_text_label(label: str | None) -> str:
    if label is None:
        return "unknown"
    normalized = label.casefold()
    if normalized in _INCOMING_LABELS:
        return "incoming"
    if normalized in _OUTGOING_LABELS:
        return "outgoing"
    return "unknown"


def _string_from_observation(
    observation: ToolObservation,
    *keys: str,
) -> str | None:
    for payload in (observation.observation, observation.evidence):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _int_from_observation(
    observation: ToolObservation,
    *keys: str,
) -> int | None:
    for payload in (observation.observation, observation.evidence):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
    return None


def _wechat_environment(
    config: WeChatDesktopConfig,
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "configuredAppName": config.app_name,
    }
    if config.bundle_id is not None:
        payload["configuredBundleId"] = config.bundle_id
    field_map = (
        ("frontmostApp", ("frontmostApp", "frontmost_app", "appName", "app_name")),
        (
            "frontmostBundleId",
            ("frontmostBundleId", "frontmost_bundle_id", "bundleId", "bundle_id"),
        ),
        ("windowTitle", ("windowTitle", "window_title", "title")),
        (
            "appVersion",
            (
                "frontmostVersion",
                "frontmost_version",
                "appVersion",
                "app_version",
                "version",
            ),
        ),
    )
    for output_key, source_keys in field_map:
        value = _string_from_observation(observation, *source_keys)
        if value is not None:
            payload[output_key] = value
    return payload


def _current_chat_title(window_title: str | None, app_name: str) -> str | None:
    if not window_title:
        return None
    title = window_title.strip()
    for separator in (" - ", " — ", " – ", " | "):
        suffix = separator + app_name
        if title.endswith(suffix):
            return title[: -len(suffix)].strip() or None
    return title


def _contact_confidence(contact: str, current_chat_title: str | None) -> float:
    if current_chat_title is None:
        return 0.8
    normalized_contact = contact.casefold()
    normalized_title = current_chat_title.casefold()
    if normalized_contact == normalized_title:
        return 0.95
    if normalized_contact in normalized_title or normalized_title in normalized_contact:
        return 0.9
    return 0.75


def _message_observed(message: str, observation: ToolObservation) -> bool:
    expected = message.strip()
    if not expected:
        return False
    for visible_message in _messages_from_observation(observation, limit=100):
        if expected in visible_message.text:
            return True
    return False


def _message_from_raw(raw: object) -> WeChatVisibleMessage | None:
    if isinstance(raw, str):
        return WeChatVisibleMessage(text=raw) if raw.strip() else None
    if isinstance(raw, dict):
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        direction = raw.get("direction", "unknown")
        visible_timestamp = raw.get("visibleTimestamp") or raw.get("visible_timestamp")
        return WeChatVisibleMessage(
            text=text,
            direction=direction if isinstance(direction, str) else "unknown",
            visible_timestamp=(
                visible_timestamp if isinstance(visible_timestamp, str) else None
            ),
        )
    return None


def _wechat_observation_has_window_title(observation: ToolObservation) -> bool:
    title = _string_from_observation(
        observation,
        "windowTitle",
        "window_title",
        "title",
    )
    return title is not None and bool(title.strip())


def _observation_indicates_login_required(observation: ToolObservation) -> bool:
    truthy_fields = (
        "loginRequired",
        "login_required",
        "requiresLogin",
        "requires_login",
    )
    false_fields = (
        "loggedIn",
        "logged_in",
        "isLoggedIn",
        "is_logged_in",
        "authenticated",
        "isAuthenticated",
    )
    for payload in (observation.observation, observation.evidence):
        for key in truthy_fields:
            if payload.get(key) is True:
                return True
        for key in false_fields:
            if payload.get(key) is False:
                return True
        status = payload.get("loginStatus") or payload.get("login_status")
        if isinstance(status, str) and status.strip().casefold() in {
            "logged_out",
            "login_required",
            "not_logged_in",
        }:
            return True
    text = _string_from_observation(
        observation,
        "textExtract",
        "visibleText",
        "windowTitle",
        "window_title",
        "title",
    )
    if text is None:
        return False
    normalized = text.casefold()
    return any(marker in normalized for marker in _LOGIN_REQUIRED_MARKERS)


def _contact_ambiguity_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    matches = _contact_matches_from_observation(observation)
    ambiguous = _bool_from_observation(
        observation,
        "contactAmbiguous",
        "contact_ambiguous",
        "ambiguous",
    )
    if ambiguous is not True and len(matches) <= 1:
        return None
    observation_payload: dict[str, JsonValue] = {
        "requestedContact": contact,
        "candidateContacts": matches,
    }
    return _failure(
        command,
        status=ToolStatus.NOT_FOUND,
        failure_kind="contact_ambiguous",
        message="Multiple WeChat contacts matched the requested contact.",
        recovery_hint="Use a more specific contact display name before retrying.",
        retryable=True,
        observation=observation_payload,
        evidence=evidence,
    )


def _contact_candidates_ambiguity_failure(
    command: ToolCommand,
    contact: str,
    candidates: list[dict[str, JsonValue]],
    *,
    evidence: dict[str, JsonValue],
    source: Mapping[str, JsonValue] | None = None,
) -> ToolObservation:
    summaries: list[dict[str, JsonValue]] = []
    for row_index, candidate in enumerate(candidates):
        display_name = _string_value(candidate.get("displayName"))
        if display_name is None:
            continue
        summary: dict[str, JsonValue] = {
            "displayName": display_name,
            "rowIndex": row_index,
        }
        secondary_text = _string_value(candidate.get("preview"))
        if secondary_text is not None:
            summary["secondaryText"] = secondary_text[:200]
        action_ref = candidate.get("actionRef")
        if isinstance(action_ref, Mapping):
            summary["actionRef"] = dict(action_ref)
        summaries.append(summary)
    observation: dict[str, JsonValue] = {
        "schema": "wechat.open_contact.v1",
        "target": contact,
        "status": "needs_disambiguation",
        "candidates": summaries,
    }
    if source is not None:
        observation["source"] = dict(source)
    return _failure(
        command,
        status=ToolStatus.NOT_FOUND,
        failure_kind="contact_ambiguous",
        message="Multiple WeChat contacts matched the requested contact.",
        recovery_hint="Use a more specific contact display name before retrying.",
        retryable=True,
        observation=observation,
        evidence=evidence,
    )


def _mapping_from_observation(
    observation: ToolObservation,
    key: str,
) -> dict[str, JsonValue] | None:
    for payload in (observation.observation, observation.evidence):
        mapped = _mapping_value(payload.get(key))
        if mapped is not None:
            return mapped
    return None


def _mapping_value(value: object) -> dict[str, JsonValue] | None:
    return value if isinstance(value, dict) else None


def _contact_matches_from_observation(
    observation: ToolObservation,
) -> list[str]:
    matches: list[str] = []
    for payload in (observation.observation, observation.evidence):
        for key in (
            "contactMatches",
            "contact_matches",
            "candidateContacts",
            "candidate_contacts",
            "searchResults",
            "search_results",
        ):
            raw_matches = payload.get(key)
            matches.extend(_contact_match_names(raw_matches))
    return _dedupe_strings(matches)


def _contact_match_names(raw_matches: JsonValue | None) -> list[str]:
    if not isinstance(raw_matches, list):
        return []
    matches: list[str] = []
    for item in raw_matches:
        if isinstance(item, str) and item.strip():
            matches.append(item.strip())
        elif isinstance(item, dict):
            for key in ("name", "displayName", "display_name", "contact", "title"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    matches.append(value.strip())
                    break
    return matches


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _bool_from_observation(
    observation: ToolObservation,
    *keys: str,
) -> bool | None:
    for payload in (observation.observation, observation.evidence):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                return value
    return None


def _observation_indicates_input_not_focused(observation: ToolObservation) -> bool:
    if observation.failure_kind in {
        "input_not_focused",
        "target_not_focused",
        "focus_failed",
    }:
        return True
    explicit_focus = _bool_from_observation(
        observation,
        "inputFocused",
        "input_focused",
        "focusedInput",
        "focused_input",
        "textInputFocused",
        "text_input_focused",
    )
    if explicit_focus is False:
        return True
    diagnostics = " ".join(
        part
        for part in (observation.summary, observation.message)
        if isinstance(part, str)
    ).casefold()
    return any(marker in diagnostics for marker in _INPUT_NOT_FOCUSED_MARKERS)


def _wechat_not_ready_failure(
    command: ToolCommand,
    message: str,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="wechat_not_ready",
        message=message,
        retryable=True,
        evidence=evidence,
    )


def _nested_failure(
    command: ToolCommand,
    phase: str,
    result: ToolObservation,
) -> ToolObservation:
    observation = dict(result.observation)
    observation.setdefault("failedPhase", phase)
    return _failure(
        command,
        status=result.status,
        failure_kind=result.failure_kind or f"{phase}_failed",
        message=result.summary,
        recovery_hint=result.recovery_hint,
        retryable=result.retryable if result.retryable is not None else False,
        observation=observation,
        evidence={phase: result.to_dict()},
    )


def _send_unverified(
    command: ToolCommand,
    *,
    contact: str,
    message: str,
    focus: ToolObservation,
    draft: ToolObservation,
    submitted: ToolObservation,
    verification: ToolObservation,
    reason: str,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        status=ToolStatus.UNKNOWN,
        error=ToolError(
            failure_kind="send_unverified",
            message=reason,
            recovery_hint="Check WeChat manually before retrying.",
            retryable=False,
            phase="verification",
            operation=command.operation,
            evidence={
                "focus": focus.to_dict(),
                "draft": draft.to_dict(),
                "submit": submitted.to_dict(),
                "verification": verification.to_dict(),
            },
        ),
        summary=reason,
        observation={
            "focusedContact": contact,
            "messageHash": wechat_message_hash(message),
            "submitted": True,
            "verified": False,
            "verificationRequested": True,
        },
    )


def _failure(
    command: ToolCommand,
    *,
    status: ToolStatus,
    failure_kind: str,
    message: str,
    recovery_hint: str | None = None,
    retryable: bool = False,
    observation: dict[str, JsonValue] | None = None,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation:
    return ToolObservation.failure(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        status=status,
        error=ToolError(
            failure_kind=failure_kind,
            message=message,
            recovery_hint=recovery_hint,
            retryable=retryable,
            phase=command.operation,
            operation=command.operation,
            evidence=evidence or {},
        ),
        summary=message,
        observation=observation,
    )


def _event(
    command: ToolCommand,
    seq: int,
    event_type: ToolEventType,
    observation: ToolObservation | None = None,
) -> ToolEvent:
    return ToolEvent(
        command_id=command.command_id,
        seq=seq,
        event_type=event_type,
        phase=command.operation,
        status=observation.status if observation else None,
        summary=observation.summary if observation else f"Started {command.operation}.",
        data={"observation": observation.to_dict()} if observation else {},
    )


def _emit(observer: ToolObserver | None, event: ToolEvent) -> None:
    if observer is not None:
        observer.on_event(event)
