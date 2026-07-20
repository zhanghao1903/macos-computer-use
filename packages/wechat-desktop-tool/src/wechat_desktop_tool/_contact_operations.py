"""Verified WeChat contact discovery and open/focus workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._action_operations import _click_node_phase, _execute_action_ref
from ._action_safety import (
    _execute_action_failure_kind,
    _should_fallback_from_accessibility_action,
    _should_press_return_for_search_result,
)
from ._contact_search import _focus_search_box_phase
from ._diagnostics import (
    _failure,
    _nested_failure,
    _optional_string_from_mapping,
    _required_input,
    _string_from_observation,
    _string_value,
)
from ._mapped_controls import (
    _mapped_region_node,
    _press_mapped_navigation,
    _query_mapped_conversation_target,
)
from ._query_mapping import (
    _contact_target_query_issue,
    _failure_from_selector_query,
    _failure_from_selector_result,
    _node_ax_path,
    _node_frame_within_query_window,
    _node_from_selector_element,
    _query_nodes,
    _query_payload,
    _query_snapshot_id,
)
from ._row_parsing import (
    _chat_title_from_query_nodes,
    _contact_candidates_ambiguity_failure,
    _contact_confidence,
    _search_candidates_from_nodes,
    _visible_contact_candidates_from_nodes,
)
from ._runtime import (
    _from_app_control_failure,
    _open_wechat_phase_failure,
    _PhaseEventCollector,
    _safe_app_control_observation,
    _WeChatSelectorQueryRunner,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL
from .profiles import build_packaged_selector_resolver


@dataclass(frozen=True)
class _ContactQueryFailureContext:
    failure_kind: str
    cause_failure_kind: str
    message: str
    retryable: bool | None


def _open_contact(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    contact = _required_input(command, "contact")
    evidence: dict[str, JsonValue] = {}
    opened = runtime._open_wechat_phase(
        command,
        evidence,
        phase_events=phase_events,
    )
    if not opened.success:
        return _open_wechat_phase_failure(command, opened, evidence)
    chats_ready = _press_mapped_navigation(
        runtime,
        command,
        "chats",
        active_window_title=_string_from_observation(
            opened,
            "windowTitle",
            "window_title",
            "title",
        ),
        evidence=evidence,
        phase_events=phase_events,
    )
    if chats_ready is not None and not chats_ready.success:
        return _from_app_control_failure(
            command,
            "wechat_navigation_failed",
            chats_ready,
            evidence=evidence,
        )
    visible_opened = _open_visible_contact_with_control_map(
        runtime,
        command,
        contact=contact,
        evidence=evidence,
        phase_events=phase_events,
    )
    if visible_opened is not None:
        return visible_opened
    selector_runner = _WeChatSelectorQueryRunner(
        runtime,
        command,
        evidence=evidence,
        phase_prefix="selectors.open_contact",
        phase_events=phase_events,
    )
    resolver = build_packaged_selector_resolver(
        selector_runner,
        app_bundle_id=runtime.config.bundle_id or "",
        selector_profile=runtime.selector_profile,
    )
    main_content = resolver.resolve("regions.mainContent")
    if main_content.status != "resolved" or not main_content.elements:
        return _failure_from_selector_result(
            command,
            main_content,
            failure_kind="main_content_not_found",
            message="Could not locate WeChat main content region.",
            evidence=evidence,
        )
    visible_opened = _open_visible_contact_phase(
        runtime,
        command,
        contact=contact,
        main_content=_node_from_selector_element(main_content.elements[0]),
        evidence=evidence,
        phase_events=phase_events,
    )
    if visible_opened is not None:
        return visible_opened
    search_box = resolver.resolve("regions.searchBox")
    if search_box.status != "resolved" or not search_box.elements:
        return _failure_from_selector_result(
            command,
            search_box,
            failure_kind="search_focus_failed",
            message="Could not locate WeChat search box.",
            evidence=evidence,
        )
    verified_search = _focus_search_box_phase(
        runtime,
        command,
        contact=contact,
        search_box=search_box,
        evidence=evidence,
        phase_events=phase_events,
    )
    if not verified_search.success:
        return verified_search
    selected_search_text = runtime._app_control_command(
        command,
        phase="select_search_text",
        operation="hotkey",
        input=runtime._target_app_input(keys=["Command", "A"]),
        phase_events=phase_events,
    )
    evidence["select_search_text"] = _safe_app_control_observation(selected_search_text)
    if not selected_search_text.success:
        return _from_app_control_failure(
            command,
            "contact_search_failed",
            selected_search_text,
            evidence=evidence,
        )
    typed = runtime._app_control_command(
        command,
        phase="type_contact",
        operation="type_text",
        input=runtime._target_app_input(text=contact),
        phase_events=phase_events,
    )
    evidence["type_contact"] = _safe_app_control_observation(typed)
    if not typed.success:
        return _from_app_control_failure(
            command,
            "contact_search_failed",
            typed,
            evidence=evidence,
        )
    results = runtime._query_accessibility_nodes(
        command,
        root_node=_node_from_selector_element(main_content.elements[0]),
        phase="search_results",
        scope="descendants",
        max_depth=4,
        role_in=["AXRow", "AXCell", "AXStaticText"],
        limit=40,
        time_budget_ms=350,
        prefer_visible_rows=True,
        evidence=evidence,
        phase_events=phase_events,
    )
    query_failure = _contact_target_query_validation_failure(
        command,
        contact,
        results,
        evidence=evidence,
    )
    if query_failure is not None:
        return query_failure
    candidates = _search_candidates_from_nodes(
        _query_nodes(results),
        contact,
        snapshot_id=_query_snapshot_id(_query_payload(results)),
    )
    if len(candidates) > 1:
        return _contact_candidates_ambiguity_failure(
            command,
            contact,
            candidates,
            evidence=evidence,
        )
    if not candidates:
        return _contact_target_not_found_failure(
            command,
            contact,
            evidence=evidence,
        )
    element = candidates[0].get("element")
    if not isinstance(element, Mapping) or not _node_frame_within_query_window(
        element,
        results,
    ):
        return _contact_target_unverified_failure(
            command,
            contact,
            reason="search_candidate_frame_invalid",
            evidence=evidence,
        )
    selected = _click_node_phase(
        runtime,
        command,
        element,
        phase="open_search_result",
        evidence=evidence,
        snapshot_id=_query_snapshot_id(_query_payload(results)),
        phase_events=phase_events,
    )
    if not selected.success and _should_press_return_for_search_result(
        selected,
        expected_action="AXPress",
    ):
        return_selected = runtime._app_control_command(
            command,
            phase="open_search_result:return_fallback",
            operation="press_key",
            input=runtime._target_app_input(key=runtime.config.submit_key),
            phase_events=phase_events,
        )
        evidence["open_search_result:return_fallback"] = _safe_app_control_observation(
            return_selected
        )
        if return_selected.success:
            selected = return_selected
    if not selected.success:
        return _from_app_control_failure(
            command,
            "contact_not_found",
            selected,
            evidence=evidence,
        )
    return _opened_contact_observation(
        runtime,
        command,
        contact=contact,
        main_content=(
            _mapped_region_node(
                runtime,
                "chatPanel",
                reference_ax_path=_node_ax_path(
                    _node_from_selector_element(main_content.elements[0])
                ),
            )
            or _node_from_selector_element(main_content.elements[0])
        ),
        open_method="search",
        evidence=evidence,
        phase_events=phase_events,
    )


def _open_visible_contact_phase(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    contact: str,
    main_content: Mapping[str, Any],
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    visible_rows = runtime._query_accessibility_nodes(
        command,
        root_node=main_content,
        phase="visible_contact_rows",
        scope="descendants",
        max_depth=4,
        role_in=["AXRow", "AXCell", "AXStaticText"],
        limit=40,
        time_budget_ms=350,
        prefer_visible_rows=True,
        evidence=evidence,
        phase_events=phase_events,
    )
    query_failure = _contact_target_query_validation_failure(
        command,
        contact,
        visible_rows,
        evidence=evidence,
    )
    if query_failure is not None:
        return query_failure
    candidates = _visible_contact_candidates_from_nodes(
        _query_nodes(visible_rows),
        contact,
        snapshot_id=_query_snapshot_id(_query_payload(visible_rows)),
    )
    if len(candidates) > 1:
        return _contact_candidates_ambiguity_failure(
            command,
            contact,
            candidates,
            evidence=evidence,
        )
    if not candidates:
        return None
    element = candidates[0].get("element")
    if not isinstance(element, Mapping):
        return _contact_target_unverified_failure(
            command,
            contact,
            reason="visible_candidate_element_invalid",
            evidence=evidence,
        )
    if not _node_frame_within_query_window(element, visible_rows):
        return _contact_target_unverified_failure(
            command,
            contact,
            reason="visible_candidate_frame_invalid",
            evidence=evidence,
        )
    action_ref = candidates[0].get("actionRef")
    expected_action = "AXPress"
    if isinstance(action_ref, Mapping):
        expected_action = (
            _optional_string_from_mapping(action_ref, "action") or "AXPress"
        )
        opened = _execute_action_ref(
            runtime,
            command,
            action_ref,
            phase="open_visible_contact",
            evidence=evidence,
            phase_events=phase_events,
        )
    else:
        opened = _click_node_phase(
            runtime,
            command,
            element,
            phase="open_visible_contact",
            evidence=evidence,
            snapshot_id=_query_snapshot_id(_query_payload(visible_rows)),
            phase_events=phase_events,
        )
    if not opened.success:
        if _should_fallback_from_accessibility_action(
            opened,
            expected_action=expected_action,
        ):
            return None
        if opened.tool == WECHAT_TOOL:
            return opened
        return _from_app_control_failure(
            command,
            _execute_action_failure_kind(opened),
            opened,
            evidence=evidence,
        )
    return _opened_contact_observation(
        runtime,
        command,
        contact=contact,
        main_content=(
            _mapped_region_node(
                runtime,
                "chatPanel",
                reference_ax_path=_node_ax_path(main_content),
            )
            or main_content
        ),
        open_method="visible_action_ref",
        evidence=evidence,
        phase_events=phase_events,
    )


def _open_visible_contact_with_control_map(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    contact: str,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    collection_query = _query_mapped_conversation_target(
        runtime,
        command,
        contact,
        evidence=evidence,
        phase_events=phase_events,
    )
    if collection_query is None:
        return None
    query_result, _collection, nodes = collection_query
    query_failure = _contact_target_query_validation_failure(
        command,
        contact,
        query_result,
        evidence=evidence,
    )
    if query_failure is not None:
        return query_failure
    candidates = _visible_contact_candidates_from_nodes(
        nodes,
        contact,
        snapshot_id=_query_snapshot_id(_query_payload(query_result)),
    )
    if len(candidates) > 1:
        return _contact_candidates_ambiguity_failure(
            command,
            contact,
            candidates,
            evidence=evidence,
            source={
                "mode": "control_map",
                "mapId": runtime.control_map.map_id,
                "mapVersion": runtime.control_map.map_version,
            },
        )
    if not candidates:
        return None
    element = candidates[0].get("element")
    if not isinstance(element, Mapping):
        return _contact_target_unverified_failure(
            command,
            contact,
            reason="mapped_candidate_element_invalid",
            evidence=evidence,
        )
    if not _node_frame_within_query_window(element, query_result):
        return _contact_target_unverified_failure(
            command,
            contact,
            reason="mapped_candidate_frame_invalid",
            evidence=evidence,
        )
    action_ref = candidates[0].get("actionRef")
    expected_action = "AXPress"
    if isinstance(action_ref, Mapping):
        expected_action = (
            _optional_string_from_mapping(action_ref, "action") or "AXPress"
        )
        opened = _execute_action_ref(
            runtime,
            command,
            action_ref,
            phase="control_map_open_visible_contact",
            evidence=evidence,
            phase_events=phase_events,
        )
    else:
        opened = _click_node_phase(
            runtime,
            command,
            element,
            phase="control_map_open_visible_contact",
            evidence=evidence,
            snapshot_id=_query_snapshot_id(_query_payload(query_result)),
            phase_events=phase_events,
        )
    if not opened.success:
        if _should_fallback_from_accessibility_action(
            opened,
            expected_action=expected_action,
        ):
            return None
        if opened.tool == WECHAT_TOOL:
            return opened
        return _from_app_control_failure(
            command,
            _execute_action_failure_kind(opened),
            opened,
            evidence=evidence,
        )
    return _opened_contact_observation(
        runtime,
        command,
        contact=contact,
        main_content=(
            _mapped_region_node(
                runtime,
                "chatPanel",
                reference_ax_path=_node_ax_path(element),
            )
            or {"axPath": "0/12/4"}
        ),
        open_method="control_map_visible_action_ref",
        evidence=evidence,
        phase_events=phase_events,
    )


def _opened_contact_observation(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    contact: str,
    main_content: Mapping[str, Any],
    open_method: str,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    verification_roots: list[dict[str, Any]] = [dict(main_content)]
    chat_panel = runtime.control_map.regions.get("chatPanel")
    known_paths = {_node_ax_path(main_content)}
    if chat_panel is not None:
        for ax_path in chat_panel.ax_paths:
            if ax_path in known_paths:
                continue
            known_paths.add(ax_path)
            verification_roots.append(
                {
                    "axPath": ax_path,
                    "role": chat_panel.role,
                }
            )

    verification: ToolObservation | None = None
    successful_verification: ToolObservation | None = None
    chat_title: str | None = None
    for index, root_node in enumerate(verification_roots):
        phase = "verify_contact" if index == 0 else f"verify_contact:{index}"
        candidate = runtime._query_accessibility_nodes(
            command,
            root_node=root_node,
            phase=phase,
            scope="descendants",
            max_depth=2,
            role_in=["AXStaticText"],
            limit=20,
            time_budget_ms=1_200,
            attributes=[
                "AXRole",
                "AXDescription",
                "AXTitle",
                "AXValue",
                "AXFrame",
            ],
            actions=False,
            evidence=evidence,
            phase_events=phase_events,
        )
        verification = candidate
        if not candidate.success:
            continue
        successful_verification = candidate
        chat_title = _chat_title_from_query_nodes(_query_nodes(candidate))
        if chat_title is not None:
            break

    verification = successful_verification or verification
    if verification is None or not verification.success:
        return _from_app_control_failure(
            command,
            "contact_not_found",
            verification
            or _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="query_root_not_found",
                message="Could not locate a WeChat chat panel.",
                retryable=True,
            ),
            evidence=evidence,
        )
    confidence = _contact_confidence(contact, chat_title)
    if chat_title is None or confidence < 0.9:
        actual_title = chat_title or "unknown"
        return _failure(
            command,
            status=ToolStatus.NOT_FOUND,
            failure_kind="contact_not_found",
            message=(
                "Verified WeChat chat title does not match requested contact: "
                f"{actual_title}"
            ),
            recovery_hint=(
                "Return to the WeChat chats view and retry opening the target "
                "contact."
            ),
            retryable=True,
            observation={
                "schema": "wechat.open_contact.v1",
                "target": contact,
                "status": "not_opened",
                "openMethod": open_method,
                "currentChat": {"title": chat_title},
            },
            evidence=evidence,
        )
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Opened WeChat contact.",
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "opened",
            "openMethod": open_method,
            "currentChat": {"title": chat_title},
            "confidence": confidence,
            "availableActions": [
                {"id": "wechat.read_visible_messages", "status": "available"},
                {"id": "wechat.draft_message", "status": "needs_input"},
            ],
        },
        evidence=evidence,
    )


def _focus_contact(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    contact = _required_input(command, "contact")
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

    current_chat = opened.observation.get("currentChat")
    current_chat_title = (
        _string_value(current_chat.get("title"))
        if isinstance(current_chat, Mapping)
        else None
    )
    confidence = opened.observation.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        confidence = _contact_confidence(contact, current_chat_title)
    environment: dict[str, JsonValue] = {
        "configuredAppName": runtime.config.app_name,
        "frontmostApp": runtime.config.app_name,
    }
    if runtime.config.bundle_id is not None:
        environment["configuredBundleId"] = runtime.config.bundle_id
        environment["frontmostBundleId"] = runtime.config.bundle_id
    if current_chat_title is not None:
        environment["windowTitle"] = current_chat_title

    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Focused WeChat contact through verified open_contact.",
        observation={
            "focusedContact": contact,
            "confidence": float(confidence),
            "appName": runtime.config.app_name,
            "bundleId": runtime.config.bundle_id,
            "frontmostApp": runtime.config.app_name,
            "windowTitle": current_chat_title,
            "currentChatTitle": current_chat_title,
            "wechatEnvironment": environment,
            "openContact": opened.observation,
        },
        evidence={"openContact": opened.to_dict()},
    )


def _contact_target_query_validation_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    issue = _contact_target_query_issue(observation)
    if issue is None:
        return None
    issue_kind, reason = issue
    if issue_kind == "failed":
        return _failure_from_contact_target_query(
            command,
            observation,
            evidence=evidence,
        )
    if issue_kind == "truncated":
        return _contact_target_query_truncation_failure(
            command,
            contact,
            observation,
            evidence=evidence,
        )
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="accessibility_query_failed",
        message=(
            "WeChat contact target query returned an invalid response and "
            "cannot establish a safe target."
        ),
        recovery_hint="Retry after WeChat and the local control service settle.",
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "query_invalid",
            "diagnostics": {"reason": reason or "query_invalid"},
        },
        evidence=evidence,
    )


def _failure_from_contact_target_query(
    command: ToolCommand,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    cause = observation.failure_kind or "accessibility_query_failed"
    message = observation.message or observation.summary
    selector_failure_kind = "selector_query_failed"
    diagnostics = _ContactQueryFailureContext(
        failure_kind=selector_failure_kind,
        cause_failure_kind=cause,
        message=message,
        retryable=observation.retryable,
    )
    return _failure_from_selector_query(
        command,
        diagnostics,
        message="WeChat contact target query failed.",
        observation_key="selector",
        semantic_payload={
            "id": "wechat.contactTarget",
            "status": "failed",
            "profileId": "wechat.contactTarget",
            "profileVersion": "1",
            "diagnostics": {
                "failureKind": selector_failure_kind,
                "causeFailureKind": cause,
                "retryable": (
                    observation.retryable if observation.retryable is not None else True
                ),
                "message": message,
            },
        },
        evidence=evidence,
    )


def _contact_target_query_truncation_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    issue = _contact_target_query_issue(observation)
    if issue is None or issue[0] != "truncated":
        return None
    raw_diagnostics = _query_payload(observation).get("diagnostics")
    diagnostics: dict[str, JsonValue] = {"truncated": True}
    if isinstance(raw_diagnostics, Mapping):
        returned_nodes = raw_diagnostics.get("returnedNodes")
        if isinstance(returned_nodes, int) and not isinstance(returned_nodes, bool):
            diagnostics["returnedNodes"] = returned_nodes
        truncation_reason = raw_diagnostics.get("truncationReason")
        if isinstance(truncation_reason, str) and truncation_reason:
            diagnostics["truncationReason"] = truncation_reason
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_query_truncated",
        message=(
            "WeChat contact target query was truncated before uniqueness could "
            "be established."
        ),
        recovery_hint=(
            "Retry after WeChat settles or use a narrower contact identifier."
        ),
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "query_truncated",
            "diagnostics": diagnostics,
        },
        evidence=evidence,
    )


def _contact_target_not_found_failure(
    command: ToolCommand,
    contact: str,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    return _failure(
        command,
        status=ToolStatus.NOT_FOUND,
        failure_kind="contact_not_found",
        message=f"Could not find a unique search result for {contact}.",
        recovery_hint="Use a contact name that produces one visible result.",
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "not_found",
        },
        evidence=evidence,
    )


def _contact_target_unverified_failure(
    command: ToolCommand,
    contact: str,
    *,
    reason: str,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_action_target_unverified",
        message="WeChat contact target geometry could not be verified.",
        recovery_hint="Restore the target row inside the visible WeChat window.",
        retryable=True,
        observation={
            "schema": "wechat.open_contact.v1",
            "target": contact,
            "status": "target_unverified",
            "diagnostics": {"reason": reason},
        },
        evidence=evidence,
    )
