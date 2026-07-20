"""Visible contact and conversation collection workflows."""

from __future__ import annotations

from typing import cast

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._action_operations import _click_node_phase
from ._diagnostics import (
    _failure,
    _optional_string_input,
    _positive_int,
    _string_from_observation,
)
from ._mapped_controls import (
    _press_mapped_navigation,
    _query_mapped_collection,
)
from ._query_mapping import (
    _failure_from_collection_result,
    _failure_from_selector_result,
    _node_from_selector_element,
    _query_payload,
    _query_snapshot_id,
    _query_truncated,
    _selector_element_selected,
)
from ._row_parsing import (
    _collection_extraction_limit,
    _collection_has_more,
    _row_items_from_collection_items,
    _row_items_from_nodes,
)
from ._runtime import (
    _from_app_control_failure,
    _open_wechat_phase_failure,
    _PhaseEventCollector,
    _WeChatSelectorQueryRunner,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL
from .profiles import (
    build_packaged_collection_extractor,
    build_packaged_selector_resolver,
)


def _list_contacts(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    return _list_row_items_with_selector_profile(
        runtime,
        command,
        section="contacts",
        schema="wechat.contacts.v1",
        collection_id="contacts",
        navigation_selector_id="navigation.contacts",
        summary="Listed visible WeChat contacts.",
        phase_events=phase_events,
    )


def _list_conversations(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    return _list_row_items_with_selector_profile(
        runtime,
        command,
        section="chats",
        schema="wechat.conversations.v1",
        collection_id="conversations",
        navigation_selector_id="navigation.chats",
        summary="Listed visible WeChat conversations.",
        phase_events=phase_events,
    )


def _list_row_items_with_selector_profile(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    section: str,
    schema: str,
    collection_id: str,
    navigation_selector_id: str,
    summary: str,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    limit = _positive_int(command.input.get("limit"), default=30)
    page_token = _optional_string_input(command, "pageToken", "page_token")
    if page_token is not None:
        return _failure(
            command,
            status=ToolStatus.FAILED,
            failure_kind="pagination_not_supported",
            message=(
                "WeChat visible-window lists do not support continuation "
                "page tokens. Request a larger limit or refresh the list."
            ),
            recovery_hint="Retry without pageToken.",
            retryable=False,
            observation={
                "schema": schema,
                "section": section,
                "pagination": {
                    "mode": "visibleWindow",
                    "limit": limit,
                    "pageToken": page_token,
                    "hasMore": False,
                    "nextPageToken": None,
                },
            },
        )
    evidence: dict[str, JsonValue] = {}
    opened = runtime._open_wechat_phase(
        command,
        evidence,
        phase_events=phase_events,
    )
    if not opened.success:
        return _open_wechat_phase_failure(command, opened, evidence)

    fast_result = _list_row_items_with_control_map(
        runtime,
        command,
        section=section,
        schema=schema,
        collection_id=collection_id,
        summary=summary,
        limit=limit,
        page_token=page_token,
        active_window_title=_string_from_observation(
            opened,
            "windowTitle",
            "window_title",
            "title",
        ),
        evidence=evidence,
        phase_events=phase_events,
    )
    if fast_result is not None:
        return fast_result

    selector_runner = _WeChatSelectorQueryRunner(
        runtime,
        command,
        evidence=evidence,
        phase_prefix=f"selectors.{section}",
        phase_events=phase_events,
    )
    resolver = build_packaged_selector_resolver(
        selector_runner,
        app_bundle_id=runtime.config.bundle_id or "",
        selector_profile=runtime.selector_profile,
    )
    navigation = resolver.resolve(navigation_selector_id)
    if navigation.status != "resolved" or not navigation.elements:
        return _failure_from_selector_result(
            command,
            navigation,
            failure_kind="wechat_navigation_failed",
            message=f"Could not locate WeChat {section} navigation item.",
            evidence=evidence,
        )
    if not _selector_element_selected(navigation.elements[0]):
        clicked = _click_node_phase(
            runtime,
            command,
            _node_from_selector_element(navigation.elements[0]),
            phase=f"switch_{section}",
            evidence=evidence,
            snapshot_id=navigation.snapshot_id,
            phase_events=phase_events,
        )
        if not clicked.success:
            return _from_app_control_failure(
                command,
                "wechat_navigation_failed",
                clicked,
                evidence=evidence,
            )

    collection_limit = _collection_extraction_limit(section, limit)
    collection = build_packaged_collection_extractor(resolver).extract(
        collection_id,
        limit=collection_limit,
    )
    if collection.status == "failed":
        return _failure_from_collection_result(
            command,
            collection,
            failure_kind="wechat_list_failed",
            message=f"Could not list WeChat {section} items.",
            evidence=evidence,
        )
    page_rows = _row_items_from_collection_items(
        collection.items,
        section=section,
        limit=limit + 1,
        snapshot_id=collection.snapshot_id,
    )
    rows = page_rows[:limit]
    semantic_has_more = len(page_rows) > limit
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary=summary,
        observation={
            "schema": schema,
            "section": section,
            "items": cast(JsonValue, rows),
            "pagination": {
                "mode": "visibleWindow",
                "limit": limit,
                "pageToken": page_token,
                "hasMore": semantic_has_more or _collection_has_more(collection),
                "nextPageToken": None,
            },
            "availableActions": [
                {
                    "id": "wechat.open_contact",
                    "status": "needs_input",
                    "operation": "open_contact",
                }
            ],
        },
        evidence=evidence,
    )


def _list_row_items_with_control_map(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    section: str,
    schema: str,
    collection_id: str,
    summary: str,
    limit: int,
    page_token: str | None,
    active_window_title: str | None,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    navigation_key = "contacts" if section == "contacts" else "chats"
    switched = _press_mapped_navigation(
        runtime,
        command,
        navigation_key,
        active_window_title=active_window_title,
        evidence=evidence,
        phase_events=phase_events,
    )
    if switched is None:
        return None
    if not switched.success:
        return _from_app_control_failure(
            command,
            "wechat_navigation_failed",
            switched,
            evidence=evidence,
        )
    collection_query = _query_mapped_collection(
        runtime,
        command,
        collection_id,
        semantic_limit=limit + 1,
        evidence=evidence,
        phase_events=phase_events,
    )
    if collection_query is None:
        return None
    query_result, collection, nodes = collection_query
    page_rows = _row_items_from_nodes(
        nodes,
        section=section,
        limit=limit + 1,
        snapshot_id=_query_snapshot_id(_query_payload(query_result)),
    )
    if not page_rows and nodes:
        return None
    rows = page_rows[:limit]
    semantic_has_more = len(page_rows) > limit
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary=summary,
        observation={
            "schema": schema,
            "section": section,
            "items": cast(JsonValue, rows),
            "pagination": {
                "mode": "visibleWindow",
                "limit": limit,
                "pageToken": page_token,
                "hasMore": semantic_has_more or _query_truncated(query_result),
                "nextPageToken": None,
            },
            "source": {
                "mode": "control_map",
                "mapId": runtime.control_map.map_id,
                "mapVersion": runtime.control_map.map_version,
                "collection": collection.collection_id,
            },
            "availableActions": [
                {
                    "id": "wechat.open_contact",
                    "status": "needs_input",
                    "operation": "open_contact",
                }
            ],
        },
        evidence=evidence,
    )
