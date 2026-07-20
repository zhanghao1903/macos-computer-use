"""Search focus and legacy contact-selection workflows."""

from __future__ import annotations

from typing import Any

from app_control_protocol import ToolCommand, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._action_safety import _should_fallback_from_accessibility_action
from ._diagnostics import (
    _CHAT_INPUT_MARKERS,
    _SEARCH_FOCUS_MARKERS,
    _failure,
    _mapping_from_observation,
    _mapping_value,
    _required_input,
    _string_from_observation,
    _wechat_environment,
)
from ._query_mapping import (
    _accessibility_element_contains,
    _coordinate_click_disabled,
    _focused_text_field_position,
    _is_text_like_accessibility_element,
    _public_accessibility_element,
    _query_nodes,
    _query_payload,
    _selector_element_center_coordinates,
)
from ._row_parsing import (
    _contact_ambiguity_failure,
    _contact_confidence,
    _current_chat_title,
)
from ._runtime import (
    _from_app_control_failure,
    _PhaseEventCollector,
    _safe_app_control_observation,
    _wechat_identity_failure,
    _wechat_login_failure,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL


_SEARCH_FOCUS_QUERY_TIMEOUT_MS = 500


def _focus_search_box_phase(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    contact: str,
    search_box: Any,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    search_element = search_box.elements[0]
    coordinate_verified = _focus_search_box_coordinate_fallback(
        runtime,
        command,
        contact=contact,
        search_element=search_element,
        evidence=evidence,
        phase_events=phase_events,
    )
    if coordinate_verified is not None:
        return coordinate_verified

    action_verified = _focus_search_box_accessibility_action(
        runtime,
        command,
        contact=contact,
        search_element=search_element,
        evidence=evidence,
        phase_events=phase_events,
    )
    if action_verified is not None:
        return action_verified

    clicked = runtime._app_control_command(
        command,
        phase="click_search_box",
        operation="click",
        input=runtime._target_app_input(
            selector={
                "role": search_element.role,
                "name": search_element.label or "搜索",
            },
        ),
        phase_events=phase_events,
    )
    evidence["click_search_box"] = _safe_app_control_observation(clicked)
    if clicked.success:
        verified_after_click = _verify_search_focus_phase(
            runtime,
            command,
            phase="verify_search_focus_after_click",
            search_element=search_element,
            phase_events=phase_events,
        )
        evidence["verify_search_focus_after_click"] = _safe_app_control_observation(
            verified_after_click
        )
        if verified_after_click.success:
            click_focus_failure = _search_focus_failure(
                command,
                contact,
                verified_after_click,
                evidence=evidence,
            )
            if click_focus_failure is None:
                return verified_after_click
            return click_focus_failure
        return _from_app_control_failure(
            command,
            "search_focus_failed",
            verified_after_click,
            evidence=evidence,
        )
    return _from_app_control_failure(
        command,
        "search_focus_failed",
        clicked,
        evidence=evidence,
    )


def _focus_search_box_accessibility_action(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    contact: str,
    search_element: Any,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    element_ref = getattr(search_element, "element_ref", None)
    ax_path = getattr(element_ref, "ax_path", None)
    if not isinstance(ax_path, str) or not ax_path:
        return None
    preconditions: dict[str, JsonValue] = {
        "roleIn": [str(search_element.role)],
        "actionIn": ["AXSetFocus"],
    }
    if search_element.label:
        preconditions["labelIn"] = [str(search_element.label)]
    input_payload = runtime._target_app_input(
        target={"kind": "axPath", "axPath": ax_path},
        action="AXSetFocus",
        preconditions=preconditions,
    )
    snapshot_id = getattr(element_ref, "snapshot_id", None)
    if isinstance(snapshot_id, str) and snapshot_id:
        input_payload["snapshotId"] = snapshot_id
    focused = runtime._app_control_command(
        command,
        phase="focus_search_box_accessibility_action",
        operation="accessibility_action",
        input=input_payload,
        phase_events=phase_events,
    )
    evidence["focus_search_box_accessibility_action"] = _safe_app_control_observation(
        focused
    )
    if not focused.success:
        if _should_fallback_from_accessibility_action(
            focused,
            expected_action="AXSetFocus",
        ):
            return None
        return _from_app_control_failure(
            command,
            "search_focus_failed",
            focused,
            evidence=evidence,
        )
    verified = _verify_search_focus_phase(
        runtime,
        command,
        phase="verify_search_focus_after_accessibility_action",
        search_element=search_element,
        phase_events=phase_events,
    )
    evidence["verify_search_focus_after_accessibility_action"] = (
        _safe_app_control_observation(verified)
    )
    if not verified.success:
        return _from_app_control_failure(
            command,
            "search_focus_failed",
            verified,
            evidence=evidence,
        )
    focus_failure = _search_focus_failure(
        command,
        contact,
        verified,
        evidence=evidence,
    )
    if focus_failure is not None:
        return focus_failure
    return verified


def _focus_search_box_coordinate_fallback(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    contact: str,
    search_element: Any,
    evidence: dict[str, JsonValue],
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation | None:
    coordinates = _selector_element_center_coordinates(search_element)
    if coordinates is None:
        return None
    clicked = runtime._app_control_command(
        command,
        phase="click_search_box_coordinate",
        operation="click",
        input=runtime._target_app_input(coordinates=coordinates),
        command_metadata={
            "coordinateSource": "accessibility_frame",
        },
        phase_events=phase_events,
    )
    evidence["click_search_box_coordinate"] = _safe_app_control_observation(clicked)
    if not clicked.success:
        if _coordinate_click_disabled(clicked):
            return None
        return _from_app_control_failure(
            command,
            "search_focus_failed",
            clicked,
            evidence=evidence,
        )
    verified = _verify_search_focus_phase(
        runtime,
        command,
        phase="verify_search_focus_after_coordinate",
        search_element=search_element,
        phase_events=phase_events,
    )
    evidence["verify_search_focus_after_coordinate"] = _safe_app_control_observation(
        verified
    )
    if not verified.success:
        return _from_app_control_failure(
            command,
            "search_focus_failed",
            verified,
            evidence=evidence,
        )
    coordinate_focus_failure = _search_focus_failure(
        command,
        contact,
        verified,
        evidence=evidence,
    )
    if coordinate_focus_failure is not None:
        return coordinate_focus_failure
    return verified


def _verify_search_focus_phase(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase: str,
    search_element: Any,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    element_ref = getattr(search_element, "element_ref", None)
    ax_path = getattr(element_ref, "ax_path", None)
    if isinstance(ax_path, str) and ax_path:
        return runtime._app_control_command(
            command,
            phase=phase,
            operation="accessibility_query",
            input=runtime._accessibility_query_input(
                root={"kind": "axPath", "axPath": ax_path},
                query={
                    "scope": "self",
                    "maxDepth": 0,
                    "limit": 1,
                    "timeBudgetMs": _SEARCH_FOCUS_QUERY_TIMEOUT_MS,
                    "attributes": [
                        "AXRole",
                        "AXDescription",
                        "AXTitle",
                        "AXValue",
                        "AXPlaceholderValue",
                        "AXFocused",
                        "AXEnabled",
                        "AXFrame",
                    ],
                    "actions": False,
                    "includeChildrenCount": False,
                    "match": {"roleIn": [str(search_element.role)]},
                },
            ),
            timeout_ms=_SEARCH_FOCUS_QUERY_TIMEOUT_MS,
            phase_events=phase_events,
        )
    return runtime._app_control_command(
        command,
        phase=phase,
        operation="observe",
        input=runtime._target_app_input(
            includeAccessibility=True,
            includeVisibleText=True,
        ),
        phase_events=phase_events,
    )


def _focus_contact_legacy(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    contact = _required_input(command, "contact")
    evidence: dict[str, JsonValue] = {}
    opened = runtime._app_control_command(
        command,
        phase="open_wechat",
        operation="open_app",
        input=runtime._open_app_input(),
        phase_events=phase_events,
    )
    evidence["open_wechat"] = _safe_app_control_observation(opened)
    if not opened.success:
        return _from_app_control_failure(
            command,
            "wechat_open_failed",
            opened,
            evidence=evidence,
        )
    ready = runtime._app_control_command(
        command,
        phase="verify_wechat_window",
        operation="observe",
        input=runtime._target_app_input(),
        phase_events=phase_events,
    )
    evidence["verify_wechat_window"] = _safe_app_control_observation(ready)
    if not ready.success:
        return _from_app_control_failure(
            command,
            "wechat_not_ready",
            ready,
            evidence=evidence,
        )
    identity_failure = _wechat_identity_failure(
        command,
        runtime.config,
        ready,
        evidence=evidence,
    )
    if identity_failure is not None:
        return identity_failure
    login_failure = _wechat_login_failure(
        command,
        runtime.config,
        ready,
        evidence=evidence,
    )
    if login_failure is not None:
        return login_failure
    phases = (
        (
            "focus_search",
            "hotkey",
            runtime._target_app_input(
                keys=list(runtime.config.search_hotkey),
            ),
        ),
        (
            "verify_search_focus",
            "observe",
            runtime._target_app_input(
                includeAccessibility=True,
                includeVisibleText=True,
            ),
        ),
        (
            "select_search_text",
            "hotkey",
            runtime._target_app_input(
                keys=list(runtime.config.search_clear_hotkey),
            ),
        ),
        (
            "clear_search_text",
            "press_key",
            runtime._target_app_input(key=runtime.config.clear_key),
        ),
        (
            "type_contact",
            "type_text",
            runtime._target_app_input(text=contact),
        ),
        (
            "select_contact",
            "press_key",
            runtime._target_app_input(key=runtime.config.submit_key),
        ),
    )
    for phase, operation, input_payload in phases:
        result = runtime._app_control_command(
            command,
            phase=phase,
            operation=operation,
            input=input_payload,
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        if not result.success:
            return _from_app_control_failure(
                command,
                "contact_not_found",
                result,
                evidence=evidence,
            )
        if phase == "verify_search_focus":
            search_focus_failure = _search_focus_failure(
                command,
                contact,
                result,
                evidence=evidence,
            )
            if search_focus_failure is not None:
                return search_focus_failure
        if phase in {"type_contact", "select_contact"}:
            ambiguity_failure = _contact_ambiguity_failure(
                command,
                contact,
                result,
                evidence=evidence,
            )
            if ambiguity_failure is not None:
                return ambiguity_failure
    verification = runtime._app_control_command(
        command,
        phase="verify_contact",
        operation="observe",
        input=runtime._target_app_input(includeVisibleText=True),
        phase_events=phase_events,
    )
    evidence["verify_contact"] = _safe_app_control_observation(verification)
    if not verification.success:
        return _from_app_control_failure(
            command,
            "wechat_window_unavailable",
            verification,
            evidence=evidence,
        )
    identity_failure = _wechat_identity_failure(
        command,
        runtime.config,
        verification,
        evidence=evidence,
    )
    if identity_failure is not None:
        return identity_failure
    login_failure = _wechat_login_failure(
        command,
        runtime.config,
        verification,
        evidence=evidence,
    )
    if login_failure is not None:
        return login_failure
    ambiguity_failure = _contact_ambiguity_failure(
        command,
        contact,
        verification,
        evidence=evidence,
    )
    if ambiguity_failure is not None:
        return ambiguity_failure
    window_title = _string_from_observation(
        verification,
        "windowTitle",
        "window_title",
        "title",
    )
    frontmost_app = _string_from_observation(
        verification,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    )
    current_chat_title = _current_chat_title(window_title, runtime.config.app_name)
    confidence = _contact_confidence(contact, current_chat_title)
    if current_chat_title is not None and confidence < 0.9:
        return _failure(
            command,
            status=ToolStatus.NOT_FOUND,
            failure_kind="contact_not_found",
            message=(
                "Verified WeChat chat title does not match requested contact: "
                f"{current_chat_title}"
            ),
            retryable=True,
            evidence=evidence,
        )
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Focused WeChat contact.",
        observation={
            "focusedContact": contact,
            "confidence": confidence,
            "appName": runtime.config.app_name,
            "bundleId": runtime.config.bundle_id,
            "frontmostApp": frontmost_app or runtime.config.app_name,
            "windowTitle": window_title or runtime.config.app_name,
            "currentChatTitle": current_chat_title,
            "wechatEnvironment": _wechat_environment(
                runtime.config,
                verification,
            ),
        },
        evidence=evidence,
    )


def _search_focus_failure(
    command: ToolCommand,
    contact: str,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue],
) -> ToolObservation | None:
    assessment = _search_focus_assessment(observation)
    state = assessment.get("state")
    if state == "verified":
        return None
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="search_not_focused",
        message=(
            "WeChat search field is not focused after the search hotkey; "
            "refusing to type the contact into the current chat."
        ),
        recovery_hint="Click WeChat search manually or adjust search_hotkey, then retry.",
        retryable=True,
        observation={
            "requestedContact": contact,
            "searchFocus": assessment,
        },
        evidence=evidence,
    )


def _search_focus_assessment(observation: ToolObservation) -> dict[str, JsonValue]:
    query_payload = _query_payload(observation)
    if query_payload:
        if query_payload.get("available") is False:
            payload: dict[str, JsonValue] = {
                "state": "unknown",
                "reason": "search_focus_query_unavailable",
            }
            failure_kind = query_payload.get("failureKind")
            if isinstance(failure_kind, str):
                payload["failureKind"] = failure_kind
            return payload
        nodes = _query_nodes(observation)
        if len(nodes) != 1:
            return {
                "state": "unknown",
                "reason": "search_focus_query_target_missing",
            }
        search_element = nodes[0]
        public_element = _public_accessibility_element(search_element)
        if not _is_text_like_accessibility_element(search_element):
            return {
                "state": "not_search",
                "reason": "search_focus_query_target_is_not_text_input",
                "focusedElement": public_element,
            }
        if not _accessibility_element_contains(
            search_element,
            _SEARCH_FOCUS_MARKERS,
        ):
            return {
                "state": "not_search",
                "reason": "search_focus_query_target_has_no_search_marker",
                "focusedElement": public_element,
            }
        focused = search_element.get("focused")
        if focused is True:
            return {
                "state": "verified",
                "reason": "targeted_search_element_focused",
                "focusedElement": public_element,
            }
        if focused is False:
            return {
                "state": "not_search",
                "reason": "targeted_search_element_not_focused",
                "focusedElement": public_element,
            }
        return {
            "state": "unknown",
            "reason": "targeted_search_element_focus_unknown",
            "focusedElement": public_element,
        }

    accessibility = _mapping_from_observation(observation, "accessibility")
    if accessibility is None:
        return {"state": "unknown", "reason": "no_accessibility_snapshot"}
    if accessibility.get("available") is False:
        accessibility_payload: dict[str, JsonValue] = {
            "state": "unknown",
            "reason": "accessibility_snapshot_unavailable",
        }
        failure_kind = accessibility.get("failureKind")
        if isinstance(failure_kind, str):
            accessibility_payload["failureKind"] = failure_kind
        message = accessibility.get("message")
        if isinstance(message, str):
            accessibility_payload["message"] = message
        return accessibility_payload
    focused = _mapping_value(accessibility.get("focusedElement"))
    if focused is None:
        return {"state": "unknown", "reason": "no_focused_element"}
    focused_payload = _public_accessibility_element(focused)
    if not _is_text_like_accessibility_element(focused):
        return {
            "state": "not_search",
            "reason": "focused_element_is_not_text_input",
            "focusedElement": focused_payload,
        }
    if _accessibility_element_contains(focused, _SEARCH_FOCUS_MARKERS):
        return {
            "state": "verified",
            "reason": "focused_element_has_search_marker",
            "focusedElement": focused_payload,
        }
    if _accessibility_element_contains(focused, _CHAT_INPUT_MARKERS):
        return {
            "state": "not_search",
            "reason": "focused_element_looks_like_chat_input",
            "focusedElement": focused_payload,
        }
    position = _focused_text_field_position(focused, accessibility)
    if position == "top":
        return {
            "state": "verified",
            "reason": "focused_text_field_is_top_candidate",
            "focusedElement": focused_payload,
        }
    if position == "bottom":
        return {
            "state": "not_search",
            "reason": "focused_text_field_is_bottom_candidate",
            "focusedElement": focused_payload,
        }
    return {
        "state": "unknown",
        "reason": "focused_text_field_is_not_identifiable",
        "focusedElement": focused_payload,
    }
