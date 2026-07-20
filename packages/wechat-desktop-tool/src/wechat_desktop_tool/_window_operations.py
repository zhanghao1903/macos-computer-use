"""Open and inspect workflows for WeChat Desktop."""

from __future__ import annotations

from typing import Any

from app_control_protocol import ToolCommand, ToolObservation
from app_control_protocol.json_types import JsonValue

from ._diagnostics import (
    _bool_input,
    _string_from_observation,
    _wechat_environment,
)
from ._query_mapping import (
    _main_content_node,
    _navigation_from_query_nodes,
    _query_nodes,
    _query_normalization_reason,
    _query_payload,
    _query_snapshot_id,
    _wechat_environment_from_query,
    _window_from_query,
)
from ._row_parsing import _current_chat_title
from ._runtime import (
    _QUERY_ATTRIBUTES,
    _from_app_control_failure,
    _open_wechat_phase_failure,
    _PhaseEventCollector,
    _safe_app_control_observation,
    _wechat_identity_failure,
    _wechat_login_failure,
    WeChatToolRuntime,
)
from .commands import WECHAT_TOOL
from .models import WECHAT_WINDOW_SCHEMA


def _open_wechat(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    evidence: dict[str, JsonValue] = {}
    observed = runtime._open_wechat_phase(
        command,
        evidence,
        phase_events=phase_events,
    )
    if not observed.success:
        return _open_wechat_phase_failure(command, observed, evidence)
    identity_failure = _wechat_identity_failure(
        command,
        runtime.config,
        observed,
        evidence=evidence,
    )
    if identity_failure is not None:
        return identity_failure
    login_failure = _wechat_login_failure(
        command,
        runtime.config,
        observed,
        evidence=evidence,
    )
    if login_failure is not None:
        return login_failure
    window_title = _string_from_observation(
        observed,
        "windowTitle",
        "window_title",
        "title",
    )
    frontmost_app = _string_from_observation(
        observed,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    )
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Opened or focused WeChat Desktop.",
        observation={
            "appName": runtime.config.app_name,
            "bundleId": runtime.config.bundle_id,
            "frontmostApp": frontmost_app or runtime.config.app_name,
            "windowTitle": window_title,
            "currentChatTitle": _current_chat_title(
                window_title,
                runtime.config.app_name,
            ),
            "wechatEnvironment": _wechat_environment(runtime.config, observed),
            "windowReady": True,
            "appControlObservation": evidence.get("open_wechat"),
            "observeObservation": _safe_app_control_observation(observed),
        },
        evidence=evidence,
    )


def _inspect_window(
    runtime: WeChatToolRuntime,
    command: ToolCommand,
    *,
    phase_events: "_PhaseEventCollector | None" = None,
) -> ToolObservation:
    include_raw = _bool_input(command, "includeRaw", "include_raw", default=False)
    include_actionables = _bool_input(
        command,
        "includeActionables",
        "include_actionables",
        default=True,
    )
    evidence: dict[str, JsonValue] = {}
    opened = runtime._open_wechat_phase(
        command,
        evidence,
        phase_events=phase_events,
    )
    if not opened.success:
        return _open_wechat_phase_failure(command, opened, evidence)
    top_level = runtime._app_control_command(
        command,
        phase="inspect_window",
        operation="accessibility_query",
        input=runtime._accessibility_query_input(
            root={"kind": "focusedWindow"},
            query={
                "scope": "children",
                "maxDepth": 1,
                "limit": 80,
                "timeBudgetMs": 10_000,
                "attributes": _QUERY_ATTRIBUTES,
                "actions": True,
                "includeChildrenCount": False,
            },
            include_raw=include_raw,
        ),
        phase_events=phase_events,
    )
    evidence["inspect_window"] = _safe_app_control_observation(top_level)
    if not top_level.success:
        return _from_app_control_failure(
            command,
            "wechat_not_ready",
            top_level,
            evidence=evidence,
        )
    top_query = _query_payload(top_level)
    top_nodes = _query_nodes(top_level)
    top_snapshot_id = _query_snapshot_id(top_query)
    navigation = _navigation_from_query_nodes(
        top_nodes,
        snapshot_id=top_snapshot_id,
    )
    main_content = _main_content_node(top_nodes)
    main_nodes: list[dict[str, Any]] = []
    if main_content is not None:
        main_query_result = runtime._app_control_command(
            command,
            phase="inspect_window:main_content",
            operation="accessibility_query",
            input=runtime._accessibility_query_input(
                root={
                    "kind": "axPath",
                    "snapshotId": _query_snapshot_id(top_query),
                    "axPath": main_content["axPath"],
                },
                query={
                    "scope": "children",
                    "maxDepth": 1,
                    "limit": 80,
                    "timeBudgetMs": 2_000,
                    "attributes": _QUERY_ATTRIBUTES,
                    "actions": True,
                    "includeChildrenCount": False,
                },
                include_raw=include_raw,
            ),
            phase_events=phase_events,
        )
        evidence["main_content"] = _safe_app_control_observation(main_query_result)
        if main_query_result.success:
            main_nodes = _query_nodes(main_query_result)
    window = _window_from_query(
        runtime.config,
        top_query,
        navigation=navigation,
        main_content=main_content,
        main_nodes=main_nodes,
        include_actionables=include_actionables,
    )
    normalization_reason = _query_normalization_reason(
        top_query,
        top_nodes=top_nodes,
        main_content=main_content,
    )
    if normalization_reason != "accessibility_query_normalized":
        available_actions = window.get("availableActions")
        if isinstance(available_actions, list):
            available_actions.append(
                {
                    "id": f"diagnostic.{normalization_reason}",
                    "kind": "diagnostic",
                    "status": "blocked",
                    "operation": "inspect_window",
                    "recoveryHint": (
                        "Retry inspect_window after confirming macOS "
                        "Accessibility permission and a focused WeChat window."
                    ),
                }
            )
    normalization = {
        "status": "normalized",
        "reason": normalization_reason,
        "actionableCount": len(window.get("actionables", [])),
        "availableActionCount": len(window.get("availableActions", [])),
        "queryMode": "scoped",
    }
    payload: dict[str, JsonValue] = {
        "schema": WECHAT_WINDOW_SCHEMA,
        "window": window,
        "includeRaw": include_raw,
        "includeActionables": include_actionables,
        "normalization": normalization,
        "wechatEnvironment": _wechat_environment_from_query(
            runtime.config,
            top_query,
        ),
    }
    if include_raw:
        payload["rawQueries"] = {
            "topLevel": top_query,
            "mainContent": main_nodes,
        }
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=WECHAT_TOOL,
        operation=command.operation,
        summary="Inspected WeChat window.",
        observation=payload,
        evidence=evidence,
    )
