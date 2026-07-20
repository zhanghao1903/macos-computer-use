"""Pure WeChat contact, conversation, and message row parsing."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any, cast

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._diagnostics import (
    _bool_from_observation,
    _contains_any,
    _failure,
    _number_value,
    _string_value,
)
from ._query_mapping import (
    _SEARCH_QUERY_LABELS,
    _action_ref_from_node,
    _element_from_query_node,
    _node_ax_path,
    _node_from_collection_element,
    _node_label,
    _query_payload,
    _query_snapshot_id,
    _query_truncated,
)
from .models import WeChatVisibleMessage


def _row_items_from_collection_items(
    collection_items: tuple[dict[str, JsonValue], ...],
    *,
    section: str,
    limit: int,
    snapshot_id: str | None = None,
) -> list[dict[str, JsonValue]]:
    items: list[dict[str, JsonValue]] = []
    for item in collection_items:
        if len(items) >= limit:
            break
        element_node = _node_from_collection_element(item.get("element"))
        if element_node is None:
            continue
        parsed: dict[str, Any]
        if section == "contacts":
            display_name = _string_value(item.get("displayName"))
            if display_name is None:
                continue
            if not _is_contact_collection_item(item):
                continue
            parsed = {
                "displayName": display_name,
                "badges": [],
            }
        else:
            raw_label = _string_value(item.get("rawLabel"))
            if raw_label is None:
                continue
            parsed = _parse_row_label(raw_label)

        item_id = f"{section}.visible.{len(items)}"
        payload: dict[str, JsonValue] = {
            "id": item_id,
            "displayName": parsed["displayName"],
            "actionId": f"{item_id}.open",
            "element": _element_from_query_node(
                element_node,
                label=parsed["displayName"],
            ),
            "confidence": 0.88,
        }
        action_ref = _action_ref_from_node(
            element_node,
            action_id=f"{item_id}.open",
            kind=f"{section}.open",
            risk="changes_current_chat",
            target_summary=f"Open {parsed['displayName']}",
            snapshot_id=snapshot_id,
        )
        if action_ref is not None:
            payload["actionRef"] = action_ref
        if section == "contacts":
            payload["kind"] = "contact"
        else:
            if parsed.get("preview") is not None:
                payload["preview"] = parsed["preview"]
            if parsed.get("timestamp") is not None:
                payload["timestamp"] = parsed["timestamp"]
            payload["badges"] = parsed["badges"]
            badges = " ".join(parsed["badges"]).casefold()
            payload["pinned"] = "置顶" in badges or "pinned" in badges
            payload["muted"] = "免打扰" in badges or "muted" in badges
        items.append(payload)
    return items


def _collection_extraction_limit(section: str, limit: int) -> int:
    if section != "contacts":
        return limit
    return max(limit, min(limit + 10, 40))


def _is_contact_collection_item(item: Mapping[str, JsonValue]) -> bool:
    element = item.get("element")
    if not isinstance(element, Mapping):
        return True
    frame = element.get("frame")
    if not isinstance(frame, Mapping):
        return True
    height = _number_value(frame.get("height"))
    if height is None:
        return True
    return height >= 50


def _row_items_from_nodes(
    nodes: list[dict[str, Any]],
    *,
    section: str,
    limit: int,
    snapshot_id: str | None = None,
) -> list[dict[str, JsonValue]]:
    if section == "contacts":
        nodes = _nodes_with_synthesized_contact_rows(nodes)
    labels_by_row = _row_labels_by_path(nodes)
    contact_labels_by_row = (
        _contact_row_labels_by_path(nodes) if section == "contacts" else {}
    )
    items: list[dict[str, JsonValue]] = []
    for index, row in enumerate(node for node in nodes if node.get("role") == "AXRow"):
        if len(items) >= limit:
            break
        row_path = str(row.get("axPath") or "")
        label = contact_labels_by_row.get(row_path) or labels_by_row.get(row_path)
        label = label or _node_label(row)
        parsed: dict[str, Any]
        if section == "contacts":
            if not _is_contact_row_node(row):
                continue
            if not label or _is_contact_non_name_label(label):
                continue
            parsed = {"displayName": label, "badges": []}
        else:
            if not label:
                continue
            parsed = _parse_row_label(label)
        item_id = f"{section}.visible.{len(items)}"
        payload: dict[str, JsonValue] = {
            "id": item_id,
            "displayName": parsed["displayName"],
            "actionId": f"{item_id}.open",
            "element": _element_from_query_node(row, label=parsed["displayName"]),
            "confidence": 0.88,
        }
        action_ref = _action_ref_from_node(
            row,
            action_id=f"{item_id}.open",
            kind=f"{section}.open",
            risk="changes_current_chat",
            target_summary=f"Open {parsed['displayName']}",
            snapshot_id=snapshot_id,
        )
        if action_ref is not None:
            payload["actionRef"] = action_ref
        if section == "contacts":
            payload["kind"] = "contact"
        else:
            if parsed.get("preview") is not None:
                payload["preview"] = parsed["preview"]
            if parsed.get("timestamp") is not None:
                payload["timestamp"] = parsed["timestamp"]
            payload["badges"] = parsed["badges"]
            badges = " ".join(parsed["badges"]).casefold()
            payload["pinned"] = "置顶" in badges or "pinned" in badges
            payload["muted"] = "免打扰" in badges or "muted" in badges
        del index
        items.append(payload)
    return items


def _row_labels_by_path(nodes: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    row_paths = _row_path_set(nodes)
    for node in nodes:
        path = str(node.get("axPath") or "")
        label = _node_label(node)
        if not path or not label:
            continue
        if node.get("role") == "AXRow":
            labels[path] = label
        else:
            row_path = _nearest_row_path(path, row_paths) or path.rsplit("/", 1)[0]
            labels.setdefault(row_path, label)
    return labels


def _nodes_with_synthesized_contact_rows(
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if any(node.get("role") == "AXRow" for node in nodes):
        return nodes
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        if node.get("role") != "AXStaticText":
            continue
        path = str(node.get("axPath") or "")
        row_path = _contact_row_path_from_static_text_path(path)
        if row_path is None:
            continue
        groups.setdefault(row_path, []).append(node)

    synthesized_rows: list[dict[str, Any]] = []
    for row_path, text_nodes in groups.items():
        labels = [
            (node, label)
            for node in text_nodes
            if (label := _node_label(node)) is not None
        ]
        if any(_is_contact_whole_row_special_label(label) for _node, label in labels):
            continue
        candidates = [
            (node, label)
            for node, label in labels
            if not _is_contact_non_name_label(label)
        ]
        if not candidates:
            continue
        label_node, label = sorted(
            candidates,
            key=lambda item: _node_frame_sort_key(item[0]),
        )[0]
        synthesized_rows.append(
            _synthesized_contact_row_node(row_path, label_node, label),
        )
    if not synthesized_rows:
        return nodes
    return [*synthesized_rows, *nodes]


def _contact_row_path_from_static_text_path(path: str) -> str | None:
    if not path or "/" not in path:
        return None
    parts = path.split("/")
    if len(parts) >= 3 and parts[-2] == "0":
        return "/".join(parts[:-2])
    if len(parts) >= 2:
        return "/".join(parts[:-1])
    return None


def _synthesized_contact_row_node(
    row_path: str,
    text_node: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "axPath": row_path,
        "role": "AXRow",
        "label": label,
    }
    frame = text_node.get("frame")
    if isinstance(frame, Mapping):
        x = _number_value(frame.get("x")) or 0.0
        y = _number_value(frame.get("y")) or 0.0
        width = _number_value(frame.get("width")) or 0.0
        row["frame"] = {
            "x": max(0.0, x - 76.0),
            "y": max(0.0, y - 18.0),
            "width": max(256.0, width + 76.0),
            "height": 58.0,
        }
    return row


def _node_frame_sort_key(node: Mapping[str, Any]) -> tuple[float, float]:
    frame = node.get("frame")
    if not isinstance(frame, Mapping):
        return (0.0, 0.0)
    return (
        _number_value(frame.get("y")) or 0.0,
        _number_value(frame.get("x")) or 0.0,
    )


def _contact_row_labels_by_path(nodes: list[dict[str, Any]]) -> dict[str, str]:
    row_paths = _row_path_set(nodes)
    candidates: dict[str, list[tuple[float, float, str]]] = {}
    for node in nodes:
        if node.get("role") != "AXStaticText":
            continue
        path = str(node.get("axPath") or "")
        row_path = _nearest_row_path(path, row_paths)
        if row_path is None:
            continue
        label = _node_label(node)
        if not label or _is_contact_non_name_label(label):
            continue
        frame = node.get("frame")
        y = _number_value(frame.get("y")) if isinstance(frame, Mapping) else None
        x = _number_value(frame.get("x")) if isinstance(frame, Mapping) else None
        candidates.setdefault(row_path, []).append((y or 0.0, x or 0.0, label))
    return {
        row_path: sorted(values, key=lambda item: (item[0], item[1]))[0][2]
        for row_path, values in candidates.items()
        if values
    }


def _row_path_set(nodes: list[dict[str, Any]]) -> set[str]:
    return {
        str(node.get("axPath"))
        for node in nodes
        if node.get("role") == "AXRow" and isinstance(node.get("axPath"), str)
    }


def _nearest_row_path(path: str, row_paths: set[str]) -> str | None:
    current = path
    while "/" in current:
        current = current.rsplit("/", 1)[0]
        if current in row_paths:
            return current
    return None


def _is_contact_row_node(row: Mapping[str, Any]) -> bool:
    frame = row.get("frame")
    if not isinstance(frame, Mapping):
        return True
    height = _number_value(frame.get("height"))
    return height is None or height >= 50


def _is_contact_non_name_label(label: str) -> bool:
    normalized = label.strip().casefold()
    return normalized in {
        "",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "#",
        "新的朋友",
        "new friends",
        "群聊",
        "group chats",
        "标签",
        "tags",
        "公众号",
        "official accounts",
        "企业微信联系人",
        "wecom contacts",
        "联系人",
        "contacts",
        "通讯录管理",
        "contacts management",
        "已添加",
        "added",
    }


def _is_contact_whole_row_special_label(label: str) -> bool:
    normalized = label.strip().casefold()
    return normalized in {
        "新的朋友",
        "new friends",
        "群聊",
        "group chats",
        "标签",
        "tags",
        "公众号",
        "official accounts",
        "企业微信联系人",
        "wecom contacts",
        "联系人",
        "contacts",
        "通讯录管理",
        "contacts management",
    }


def _parse_row_label(label: str) -> dict[str, Any]:
    parts = [part.strip() for part in label.split(",")]
    payload: dict[str, Any] = {
        "displayName": parts[0] if parts else label,
        "badges": [],
    }
    if len(parts) > 1 and parts[1]:
        payload["preview"] = parts[1]
    if len(parts) > 2 and parts[2]:
        payload["timestamp"] = parts[2]
    if len(parts) > 3:
        payload["badges"] = [part for part in parts[3:] if part]
    return payload


def _search_candidates_from_nodes(
    nodes: list[dict[str, Any]],
    contact: str,
    *,
    snapshot_id: str | None = None,
) -> list[dict[str, JsonValue]]:
    normalized = contact.casefold()
    candidates: list[dict[str, JsonValue]] = []
    for item in _row_items_from_nodes(
        nodes,
        section="search",
        limit=10,
        snapshot_id=snapshot_id,
    ):
        display_name = str(item.get("displayName") or "")
        if normalized in display_name.casefold():
            action_id = f"search.result.{len(candidates)}.open"
            item["actionId"] = action_id
            action_ref = item.get("actionRef")
            if isinstance(action_ref, dict):
                action_ref["id"] = action_id
                action_ref["kind"] = "search_result.open"
                action_ref["targetSummary"] = f"Open search result {display_name}"
            candidates.append(item)
    return candidates


def _conversation_rows_from_cells(
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for node in nodes:
        role = str(node.get("role") or "")
        ax_path = _node_ax_path(node)
        if ax_path is None:
            continue
        if role == "AXRow":
            row_path = ax_path
            row = dict(node)
        elif role == "AXCell" and "/" in ax_path:
            row_path = ax_path.rsplit("/", 1)[0]
            row = dict(node)
            row["axPath"] = row_path
            row["role"] = "AXRow"
            row.pop("actions", None)
        else:
            continue
        if row_path in seen_paths:
            continue
        seen_paths.add(row_path)
        rows.append(row)
    return rows


def _visible_contact_candidates_from_nodes(
    nodes: list[dict[str, Any]],
    contact: str,
    *,
    snapshot_id: str | None = None,
) -> list[dict[str, JsonValue]]:
    normalized = _normalized_contact_name(contact)
    candidates: list[dict[str, JsonValue]] = []
    for item in _row_items_from_nodes(
        nodes,
        section="chats",
        limit=40,
        snapshot_id=snapshot_id,
    ):
        display_name = str(item.get("displayName") or "")
        if _normalized_contact_name(display_name) != normalized:
            continue
        action_id = f"visible.contact.{len(candidates)}.open"
        item["actionId"] = action_id
        action_ref = item.get("actionRef")
        if isinstance(action_ref, dict):
            action_ref["id"] = action_id
            action_ref["kind"] = "visible_contact.open"
            action_ref["targetSummary"] = f"Open visible contact {display_name}"
        candidates.append(item)
    return candidates


def _normalized_contact_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _messages_from_query_nodes(
    nodes: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, JsonValue]]:
    labels_by_row = _row_labels_by_path(nodes)
    messages: list[dict[str, JsonValue]] = []
    for row in (node for node in nodes if node.get("role") == "AXRow"):
        if len(messages) >= limit:
            break
        text = labels_by_row.get(str(row.get("axPath"))) or _node_label(row)
        if not text:
            continue
        messages.append(
            {
                "id": f"message.visible.{len(messages)}",
                "direction": "unknown",
                "text": text,
                "timestamp": None,
                "visible": True,
                "element": _element_from_query_node(row, label=text),
            }
        )
    return messages


def _chat_title_from_query_nodes(nodes: list[dict[str, Any]]) -> str | None:
    for node in nodes:
        if node.get("role") == "AXStaticText":
            label = _node_label(node)
            if label and not _contains_any(label, _SEARCH_QUERY_LABELS):
                return label
    return None


def _next_page_token(
    section: str,
    observation: ToolObservation,
    *,
    direction: str = "next",
) -> str | None:
    if not _query_truncated(observation):
        return None
    snapshot_id = _query_snapshot_id(_query_payload(observation)) or "snapshot"
    return f"{section}:{direction}:{snapshot_id}"


def _collection_has_more(result: Any) -> bool:
    return bool(result.pagination.has_more or result.diagnostics.truncated)


_TEXT_LINE_RE = re.compile(
    r"^(?:(?:\[(?P<bracket_ts>[^\]]+)\]|(?P<plain_ts>\d{1,2}:\d{2}))\s+)?"
    r"(?:(?P<label>incoming|outgoing|received|sent|me|you)\s*:\s*)?"
    r"(?P<text>.+)$",
    re.IGNORECASE,
)


_INCOMING_LABELS = {"incoming", "received", "you"}


_OUTGOING_LABELS = {"outgoing", "sent", "me"}


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
        "candidateContacts": cast(JsonValue, matches),
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
        "candidates": cast(JsonValue, summaries),
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
