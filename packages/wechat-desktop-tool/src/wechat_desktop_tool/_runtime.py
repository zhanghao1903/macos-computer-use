"""Immutable WeChat runtime dependencies and app-control transport helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app_control_protocol import (
    AppControlClient,
    ToolCommand,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolObserver,
    ToolStatus,
)
from app_control_protocol.json_types import JsonValue

from ._action_safety import (
    _accessibility_action_proof_payloads,
    _consistent_bool_evidence,
    _consistent_int_evidence,
    _consistent_string_evidence,
)
from ._diagnostics import (
    _emit,
    _failure,
    _mapping_from_observation,
    _observation_indicates_login_required,
    _optional_string_from_mapping,
    _redact_input_text,
    _safe_accessibility_status,
    _safe_app_control_envelope,
    _safe_app_control_event_summary,
    _string_from_observation,
    _wechat_not_ready_failure,
    _wechat_observation_has_window_title,
)
from ._query_mapping import (
    _node_ax_path,
    _query_payload,
    _query_snapshot_id,
    _root_resolver_payload,
)
from .commands import WECHAT_TOOL, wechat_command
from .control_map import WeChatControlMap, WeChatRootResolver
from .models import WeChatDesktopConfig, WeChatOperation
from .profiles import WeChatSelectorAssets, load_selector_assets

_QUERY_ATTRIBUTES: list[str] = [
    "AXRole",
    "AXSubrole",
    "AXTitle",
    "AXValue",
    "AXDescription",
    "AXHelp",
    "AXEnabled",
    "AXFocused",
    "AXSelected",
    "AXPosition",
    "AXSize",
    "AXFrame",
    "AXPlaceholderValue",
]


@dataclass(frozen=True)
class WeChatToolRuntime:
    """Process-local dependencies shared by WeChat operation functions."""

    _app_control: AppControlClient
    _config: WeChatDesktopConfig
    _selector_assets: WeChatSelectorAssets
    _control_map: WeChatControlMap
    _selector_profile: Any

    @classmethod
    def create(
        cls,
        app_control: AppControlClient,
        config: WeChatDesktopConfig | None = None,
    ) -> "WeChatToolRuntime":
        resolved_config = config or WeChatDesktopConfig()
        if resolved_config.computer_use_backend.casefold() == "helper":
            raise ValueError(
                "wechat-desktop-tool selector APIs do not support "
                "computer_use.backend=helper in version 0.3.0; use direct or "
                "a direct-backed local service"
            )
        selector_assets = load_selector_assets(resolved_config.selector_profile_path)
        return cls(
            _app_control=app_control,
            _config=resolved_config,
            _selector_assets=selector_assets,
            _control_map=selector_assets.control_map,
            _selector_profile=selector_assets.selector_profile,
        )

    @property
    def app_control(self) -> AppControlClient:
        return self._app_control

    @property
    def config(self) -> WeChatDesktopConfig:
        return self._config

    @property
    def selector_assets(self) -> WeChatSelectorAssets:
        return self._selector_assets

    @property
    def control_map(self) -> WeChatControlMap:
        return self._control_map

    @property
    def selector_profile(self) -> Any:
        return self._selector_profile

    def _app_control_command(
        self,
        parent: ToolCommand,
        *,
        phase: str,
        operation: str,
        input: dict[str, JsonValue],
        timeout_ms: int | None = None,
        command_metadata: Mapping[str, JsonValue] | None = None,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        metadata: dict[str, JsonValue] = {
            "sourceTool": WECHAT_TOOL,
            "parentCommandId": parent.command_id,
            "phase": phase,
        }
        if command_metadata is not None:
            metadata.update(command_metadata)
        observation = self._app_control.run_command(
            ToolCommand(
                command_id=f"{parent.command_id}:{phase}",
                tool=self._config.app_control_tool,
                operation=operation,
                input=input,
                timeout_ms=(
                    timeout_ms
                    if timeout_ms is not None
                    else parent.timeout_ms or self._config.default_timeout_ms
                ),
                metadata=metadata,
            )
        )
        if phase_events is not None:
            phase_events.emit(
                parent=parent,
                phase=phase,
                operation=operation,
                observation=observation,
            )
        return observation

    def _open_wechat_phase(
        self,
        command: ToolCommand,
        evidence: dict[str, JsonValue],
        *,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        opened = self._app_control_command(
            command,
            phase="open_wechat",
            operation="open_app",
            input=self._open_app_input(),
            phase_events=phase_events,
        )
        evidence["open_wechat"] = _safe_app_control_observation(opened)
        if not opened.success:
            return opened
        ready = self._app_control_command(
            command,
            phase="verify_wechat_window",
            operation="observe",
            input=self._target_app_input(),
            phase_events=phase_events,
        )
        evidence["verify_wechat_window"] = _safe_app_control_observation(ready)
        if not ready.success or not _wechat_observation_has_window_title(ready):
            focused = self._app_control_command(
                command,
                phase="focus_wechat",
                operation="focus_app",
                input=self._open_app_input(),
                phase_events=phase_events,
            )
            evidence["focus_wechat"] = _safe_app_control_observation(focused)
            if not focused.success:
                return focused
            ready = self._app_control_command(
                command,
                phase="verify_wechat_window_after_focus",
                operation="observe",
                input=self._target_app_input(),
                phase_events=phase_events,
            )
            evidence["verify_wechat_window_after_focus"] = (
                _safe_app_control_observation(ready)
            )
        if not ready.success:
            return ready
        if not _wechat_observation_has_window_title(ready):
            verified_window = self._app_control_command(
                command,
                phase="verify_wechat_accessibility_window",
                operation="accessibility_query",
                input=self._accessibility_query_input(
                    root={"kind": "focusedWindow"},
                    query={
                        "scope": "self",
                        "maxDepth": 0,
                        "limit": 1,
                        "timeBudgetMs": 2_000,
                        "attributes": ["AXRole", "AXTitle"],
                        "actions": False,
                        "includeChildrenCount": False,
                    },
                ),
                phase_events=phase_events,
            )
            evidence["verify_wechat_accessibility_window"] = (
                _safe_app_control_observation(verified_window)
            )
            ready = _ready_observation_with_accessibility_window_title(
                ready,
                verified_window,
                self._config.app_name,
            )
        if not _wechat_observation_has_window_title(ready):
            return _wechat_not_ready_failure(
                command,
                "WeChat is frontmost but no focused window is available.",
                evidence=evidence,
            )
        identity_failure = _wechat_identity_failure(
            command,
            self._config,
            ready,
            evidence=evidence,
        )
        if identity_failure is not None:
            return identity_failure
        login_failure = _wechat_login_failure(
            command,
            self._config,
            ready,
            evidence=evidence,
        )
        if login_failure is not None:
            return login_failure
        return ready

    def _accessibility_query_input(
        self,
        *,
        root: Mapping[str, JsonValue],
        query: Mapping[str, JsonValue],
        include_raw: bool = False,
    ) -> dict[str, JsonValue]:
        return self._target_app_input(
            root=dict(root),
            query=dict(query),
            includeRaw=include_raw,
        )

    def _query_top_level(
        self,
        command: ToolCommand,
        evidence: dict[str, JsonValue],
        *,
        phase: str = "query_top_level",
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        result = self._app_control_command(
            command,
            phase=phase,
            operation="accessibility_query",
            input=self._accessibility_query_input(
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
            ),
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        return result

    def _query_children(
        self,
        command: ToolCommand,
        *,
        root_node: Mapping[str, Any],
        phase: str,
        role_in: list[str],
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        return self._query_accessibility_nodes(
            command,
            root_node=root_node,
            phase=phase,
            scope="children",
            max_depth=1,
            role_in=role_in,
            limit=80,
            evidence=evidence,
            phase_events=phase_events,
        )

    def _query_descendants(
        self,
        command: ToolCommand,
        *,
        root_node: Mapping[str, Any] | None,
        phase: str,
        role_in: list[str],
        limit: int,
        evidence: dict[str, JsonValue],
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        if root_node is None:
            return _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="query_root_not_found",
                message="Could not locate query root.",
                retryable=True,
                evidence=evidence,
            )
        return self._query_accessibility_nodes(
            command,
            root_node=root_node,
            phase=phase,
            scope="descendants",
            max_depth=4,
            role_in=role_in,
            limit=limit,
            evidence=evidence,
            phase_events=phase_events,
        )

    def _query_accessibility_nodes(
        self,
        command: ToolCommand,
        *,
        root_node: Mapping[str, Any],
        phase: str,
        scope: str,
        max_depth: int,
        role_in: list[str],
        limit: int,
        evidence: dict[str, JsonValue],
        time_budget_ms: int | None = None,
        attributes: list[str] | None = None,
        actions: bool = True,
        match: Mapping[str, JsonValue] | None = None,
        root_resolver: WeChatRootResolver | None = None,
        prefer_visible_rows: bool = False,
        phase_events: "_PhaseEventCollector | None" = None,
    ) -> ToolObservation:
        ax_path = _node_ax_path(root_node)
        if ax_path is None:
            return _failure(
                command,
                status=ToolStatus.NOT_FOUND,
                failure_kind="query_root_not_found",
                message="Query root does not have an axPath.",
                retryable=True,
                evidence=evidence,
            )
        root_payload: dict[str, JsonValue] = {"kind": "axPath", "axPath": ax_path}
        if root_resolver is not None:
            root_payload["resolver"] = _root_resolver_payload(root_resolver)
        query_attributes: list[JsonValue] = [
            str(attribute) for attribute in (attributes or _QUERY_ATTRIBUTES)
        ]
        query_roles: list[JsonValue] = [str(role) for role in role_in]
        query_match: dict[str, JsonValue] = {"roleIn": query_roles}
        if match is not None:
            query_match.update(dict(match))
        query_payload: dict[str, JsonValue] = {
            "scope": scope,
            "maxDepth": max_depth,
            "limit": limit,
            "timeBudgetMs": (
                time_budget_ms
                if time_budget_ms is not None
                else (8_000 if scope == "descendants" else 5_000)
            ),
            "attributes": query_attributes,
            "actions": actions,
            "includeChildrenCount": False,
            "match": query_match,
        }
        if prefer_visible_rows:
            query_payload["preferVisibleRows"] = True
        result = self._app_control_command(
            command,
            phase=phase,
            operation="accessibility_query",
            input=self._accessibility_query_input(
                root=root_payload,
                query=query_payload,
            ),
            phase_events=phase_events,
        )
        evidence[phase] = _safe_app_control_observation(result)
        return result

    def _accessibility_action_input(
        self,
        action_ref: Mapping[str, Any],
    ) -> dict[str, JsonValue]:
        target = action_ref.get("target")
        if not isinstance(target, Mapping):
            raise ValueError("actionRef.target must be an object")
        ax_path = _optional_string_from_mapping(target, "axPath", "ax_path")
        if ax_path is None:
            raise ValueError("actionRef.target.axPath is required")
        action = _optional_string_from_mapping(action_ref, "action") or "AXPress"
        payload = self._target_app_input(
            target={"kind": "axPath", "axPath": ax_path},
            action=action,
        )
        snapshot_id = _optional_string_from_mapping(
            action_ref,
            "snapshotId",
            "snapshot_id",
        )
        if snapshot_id is not None:
            payload["snapshotId"] = snapshot_id
        preconditions = action_ref.get("preconditions")
        if isinstance(preconditions, Mapping):
            payload["preconditions"] = dict(preconditions)
        return payload

    def _open_app_input(self, **extra: JsonValue) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {"app": self._config.app_name}
        if self._config.bundle_id is not None:
            payload["bundleId"] = self._config.bundle_id
        payload.update(extra)
        return payload

    def _target_app_input(self, **extra: JsonValue) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {"targetApp": self._config.app_name}
        if self._config.bundle_id is not None:
            payload["bundleId"] = self._config.bundle_id
        payload.update(extra)
        return payload

    def _command(
        self,
        operation: WeChatOperation,
        input: dict[str, JsonValue] | None = None,
        *,
        parent: ToolCommand | None = None,
    ) -> ToolCommand:
        if parent is not None:
            timeout_ms = parent.timeout_ms
        else:
            timeout_ms = self._config.default_timeout_ms
        return wechat_command(
            operation,
            input or {},
            command_id=(
                f"{parent.command_id}:{operation}" if parent is not None else None
            ),
            timeout_ms=timeout_ms,
        )


class _WeChatSelectorQueryRunner:
    def __init__(
        self,
        runtime: WeChatToolRuntime,
        command: ToolCommand,
        *,
        evidence: dict[str, JsonValue],
        phase_prefix: str,
        phase_events: "_PhaseEventCollector | None",
    ) -> None:
        self._runtime = runtime
        self._command = command
        self._evidence = evidence
        self._phase_prefix = phase_prefix
        self._phase_events = phase_events
        self._count = 0

    def __call__(
        self,
        *,
        root: Mapping[str, JsonValue],
        query: Mapping[str, JsonValue],
        include_raw: bool = False,
    ) -> Mapping[str, Any]:
        self._count += 1
        phase = f"{self._phase_prefix}:{self._count}"
        result = self._runtime._app_control_command(
            self._command,
            phase=phase,
            operation="accessibility_query",
            input=self._runtime._accessibility_query_input(
                root=root,
                query=query,
                include_raw=include_raw,
            ),
            phase_events=self._phase_events,
        )
        self._evidence[phase] = _safe_app_control_observation(result)
        if result.success:
            return _query_payload(result)
        return {
            "schema": "macos.accessibility.query.v1",
            "available": False,
            "failureKind": result.failure_kind or "accessibility_query_failed",
            "message": result.message or result.summary,
            "retryable": result.retryable,
            "nodes": [],
            "diagnostics": {
                "truncated": False,
                "failureKind": result.failure_kind or "accessibility_query_failed",
                "message": result.message or result.summary,
                "retryable": result.retryable,
            },
        }


def _safe_app_control_observation(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    if observation.operation == "accessibility_query":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Accessibility query completed."
                if observation.success
                else "Accessibility query failed."
            ),
        )
        payload["observation"] = {
            "accessibilityQuery": _safe_accessibility_query_payload(observation)
        }
        return payload
    if observation.operation == "accessibility_action":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Accessibility action completed."
                if observation.success
                else "Accessibility action failed."
            ),
        )
        payload["observation"] = {
            "accessibilityAction": _safe_accessibility_action_payload(observation)
        }
        return payload
    if observation.operation == "click":
        payload = _safe_app_control_envelope(
            observation,
            summary=("Click completed." if observation.success else "Click failed."),
        )
        payload["observation"] = {
            "action": {
                "operation": "click",
                "available": observation.success,
            }
        }
        return payload
    if observation.operation == "observe":
        payload = _safe_app_control_envelope(
            observation,
            summary=(
                "Observed application state."
                if observation.success
                else "Application observation failed."
            ),
        )
        safe_observation: dict[str, JsonValue] = {}
        for output_key, source_keys in (
            (
                "frontmostApp",
                ("frontmostApp", "frontmost_app", "appName", "app_name"),
            ),
            (
                "frontmostBundleId",
                (
                    "frontmostBundleId",
                    "frontmost_bundle_id",
                    "bundleId",
                    "bundle_id",
                ),
            ),
        ):
            value = _string_from_observation(observation, *source_keys)
            if value is not None:
                safe_observation[output_key] = value
        accessibility = _mapping_from_observation(observation, "accessibility")
        if accessibility is not None:
            safe_observation["accessibility"] = _safe_accessibility_status(
                accessibility
            )
        payload["observation"] = safe_observation
        return payload
    return _redact_input_text(observation.to_dict())


def _safe_accessibility_query_payload(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    source = _query_payload(observation)
    payload: dict[str, JsonValue] = {}
    schema = source.get("schema")
    if isinstance(schema, str):
        payload["schema"] = schema
    available = source.get("available")
    payload["available"] = (
        available if isinstance(available, bool) else observation.success
    )
    for key in ("status", "failureKind", "causeFailureKind"):
        value = source.get(key)
        if isinstance(value, str):
            payload[key] = value
    if "failureKind" not in payload and observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    retryable = source.get("retryable")
    if isinstance(retryable, bool):
        payload["retryable"] = retryable
    elif observation.retryable is not None:
        payload["retryable"] = observation.retryable

    diagnostics = source.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        safe_diagnostics: dict[str, JsonValue] = {}
        for key in (
            "returnedNodes",
            "visitedNodes",
            "matchedNodes",
            "queryCount",
            "nodeCount",
            "durationMs",
            "elapsedMs",
            "timeBudgetMs",
            "limit",
            "maxDepth",
            "truncated",
            "truncationReason",
            "failureKind",
            "causeFailureKind",
            "retryable",
            "cacheStatus",
            "preferVisibleRows",
        ):
            value = diagnostics.get(key)
            if isinstance(value, str | int | float | bool):
                safe_diagnostics[key] = value
        if safe_diagnostics:
            payload["diagnostics"] = safe_diagnostics
    return payload


def _safe_accessibility_action_payload(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    source = _mapping_from_observation(observation, "accessibilityAction") or {}
    payload: dict[str, JsonValue] = {}
    schema = source.get("schema")
    if isinstance(schema, str):
        payload["schema"] = schema
    available = source.get("available")
    payload["available"] = (
        available if isinstance(available, bool) else observation.success
    )
    status = source.get("status")
    if isinstance(status, str):
        payload["status"] = status

    proof_payloads = _accessibility_action_proof_payloads(observation)
    if proof_payloads is not None:
        for output_key, keys in (
            ("failureKind", ("failureKind", "failure_kind")),
            ("action", ("action",)),
            ("actionEffect", ("actionEffect", "action_effect")),
        ):
            evidence = _consistent_string_evidence(proof_payloads, keys)
            if evidence.present and evidence.valid and evidence.value is not None:
                payload[output_key] = evidence.value
        native_code = _consistent_int_evidence(
            proof_payloads,
            ("nativeErrorCode", "native_error_code"),
        )
        if native_code.present and native_code.valid and native_code.value is not None:
            payload["nativeErrorCode"] = native_code.value
        for output_key, keys in (
            ("actionAttempted", ("actionAttempted", "action_attempted")),
            ("requestDispatched", ("requestDispatched", "request_dispatched")),
            ("retryable", ("retryable",)),
        ):
            evidence = _consistent_bool_evidence(proof_payloads, keys)
            if evidence.present and evidence.valid and evidence.value is not None:
                payload[output_key] = evidence.value
    elif observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    return payload


def _safe_executed_action_result(
    observation: ToolObservation,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "operation": observation.operation,
        "status": observation.status.value,
        "success": observation.success,
    }
    if observation.failure_kind is not None:
        payload["failureKind"] = observation.failure_kind
    if observation.operation == "accessibility_action":
        payload["accessibilityAction"] = _safe_accessibility_action_payload(observation)
    return payload


class _PhaseEventCollector:
    def __init__(
        self,
        command: ToolCommand,
        *,
        observer: ToolObserver | None,
    ) -> None:
        self._command = command
        self._observer = observer
        self._next_seq = 1
        self.events: list[ToolEvent] = []

    def emit(
        self,
        *,
        parent: ToolCommand,
        phase: str,
        operation: str,
        observation: ToolObservation,
    ) -> None:
        phase_name = phase
        if parent.command_id != self._command.command_id:
            phase_name = f"{parent.operation}.{phase}"
        safe_observation = _safe_app_control_observation(observation)
        event = ToolEvent(
            command_id=self._command.command_id,
            seq=self.next_seq(),
            event_type=ToolEventType.PROGRESS,
            phase=phase_name,
            status=observation.status,
            summary=_safe_app_control_event_summary(observation),
            data={
                "phase": phase_name,
                "appControlOperation": operation,
                "parentCommandId": parent.command_id,
                "appControlCommandId": observation.command_id,
                "appControlObservation": safe_observation,
            },
        )
        self.events.append(event)
        _emit(self._observer, event)

    def next_seq(self) -> int:
        seq = self._next_seq
        self._next_seq += 1
        return seq


def _wechat_identity_failure(
    command: ToolCommand,
    config: WeChatDesktopConfig,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation | None:
    frontmost_bundle_id = _string_from_observation(
        observation,
        "frontmostBundleId",
        "frontmost_bundle_id",
    )
    frontmost_app = _string_from_observation(
        observation,
        "frontmostApp",
        "frontmost_app",
        "appName",
        "app_name",
    )
    if (
        config.bundle_id is not None
        and frontmost_bundle_id is not None
        and frontmost_bundle_id != config.bundle_id
    ):
        return _wechat_not_ready_failure(
            command,
            (
                "Observed frontmost app bundle id does not match WeChat: "
                f"expected {config.bundle_id}, got {frontmost_bundle_id}."
            ),
            evidence=evidence
            or {"observe": _safe_app_control_observation(observation)},
        )
    if frontmost_bundle_id is None and frontmost_app is not None:
        if frontmost_app.casefold() != config.app_name.casefold():
            return _wechat_not_ready_failure(
                command,
                (
                    "Observed frontmost app does not match WeChat: "
                    f"expected {config.app_name}, got {frontmost_app}."
                ),
                evidence=evidence
                or {"observe": _safe_app_control_observation(observation)},
            )
    return None


def _wechat_login_failure(
    command: ToolCommand,
    config: WeChatDesktopConfig,
    observation: ToolObservation,
    *,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation | None:
    del config
    if not _observation_indicates_login_required(observation):
        return None
    return _failure(
        command,
        status=ToolStatus.NOT_READY,
        failure_kind="wechat_not_logged_in",
        message="WeChat Desktop is open but not logged in.",
        recovery_hint="Log in to WeChat Desktop before running this command.",
        retryable=False,
        evidence=evidence or {"observe": _safe_app_control_observation(observation)},
    )


def _ready_observation_with_accessibility_window_title(
    ready: ToolObservation,
    accessibility_query: ToolObservation,
    app_name: str,
) -> ToolObservation:
    title = _accessibility_query_window_title(accessibility_query)
    if title is None:
        return ready
    observation = dict(ready.observation)
    observation["windowTitle"] = title
    observation["snapshotId"] = (
        _query_snapshot_id(_query_payload(accessibility_query))
        or observation.get("snapshotId")
        or f"frontmost:{app_name}:{title}"
    )
    metadata = observation.get("metadata")
    if isinstance(metadata, Mapping):
        updated_metadata = dict(metadata)
        updated_metadata["window_title"] = title
        observation["metadata"] = updated_metadata
    summary = f"Frontmost app: {observation.get('frontmostApp') or app_name}. Window: {title}."
    return ToolObservation.ok(
        command_id=ready.command_id,
        tool=ready.tool,
        operation=ready.operation,
        summary=summary,
        observation=observation,
        evidence=ready.evidence,
        timing=ready.timing,
        metadata=ready.metadata,
    )


def _accessibility_query_window_title(observation: ToolObservation) -> str | None:
    if not observation.success:
        return None
    payload = _query_payload(observation)
    window = payload.get("window")
    if not isinstance(window, Mapping):
        return None
    role = window.get("role")
    title = window.get("title")
    if role != "AXWindow" or not isinstance(title, str) or not title.strip():
        return None
    return title.strip()


def _open_wechat_phase_failure(
    command: ToolCommand,
    result: ToolObservation,
    evidence: dict[str, JsonValue],
) -> ToolObservation:
    if result.tool == WECHAT_TOOL:
        return result
    failure_kind = (
        "wechat_not_ready"
        if result.operation in {"observe", "focus_app"}
        else "wechat_open_failed"
    )
    return _from_app_control_failure(
        command,
        failure_kind,
        result,
        evidence=evidence,
    )


def _from_app_control_failure(
    command: ToolCommand,
    failure_kind: str,
    result: ToolObservation,
    *,
    evidence: dict[str, JsonValue] | None = None,
) -> ToolObservation:
    return _failure(
        command,
        status=result.status if result.status != ToolStatus.OK else ToolStatus.FAILED,
        failure_kind=failure_kind,
        message=result.summary,
        retryable=result.retryable if result.retryable is not None else True,
        evidence=evidence
        or {"appControlObservation": _safe_app_control_observation(result)},
    )
