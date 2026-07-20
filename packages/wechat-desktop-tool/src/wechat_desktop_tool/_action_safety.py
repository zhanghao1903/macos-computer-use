"""Pure actionRef validation, mutation proof, and fallback decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app_control_protocol import ToolCommand, ToolError, ToolObservation, ToolStatus
from app_control_protocol.json_types import JsonValue

from ._diagnostics import _failure, _optional_string_from_mapping
from ._query_mapping import _utc_now_datetime


_DEFINITE_UNSUPPORTED_NATIVE_ERRORS = {
    "AXPress": -25206,
    "AXSetFocus": -25205,
}


@dataclass(frozen=True)
class _BooleanEvidence:
    present: bool
    valid: bool
    value: bool | None = None


@dataclass(frozen=True)
class _StringEvidence:
    present: bool
    valid: bool
    value: str | None = None


@dataclass(frozen=True)
class _IntegerEvidence:
    present: bool
    valid: bool
    value: int | None = None


def _action_ref_expiry_value(action_ref: Mapping[str, Any]) -> str | None:
    return _optional_string_from_mapping(action_ref, "expiresAt", "expires_at")


def _parse_action_ref_time(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _action_ref_expiry_failure(
    command: ToolCommand,
    action_ref: Mapping[str, Any],
) -> ToolObservation | None:
    raw_expires_at = _action_ref_expiry_value(action_ref)
    if raw_expires_at is None:
        return None
    expires_at = _parse_action_ref_time(raw_expires_at)
    if expires_at is not None and _utc_now_datetime() < expires_at:
        return None
    action_id = _optional_string_from_mapping(action_ref, "id") or "unknown"
    message = f"WeChat actionRef is expired or invalid: {action_id}"
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_action_ref_expired",
        message=message,
        recovery_hint=(
            "Re-run inspect_window or list operation to get a fresh actionRef."
        ),
        retryable=True,
        observation={
            "schema": "wechat.execute_action.v1",
            "status": "failed",
            "actionId": action_id,
            "failureKind": "wechat_action_ref_expired",
            "expiresAt": raw_expires_at,
        },
        evidence={
            "actionRef": {
                "id": action_id,
                "expiresAt": raw_expires_at,
            }
        },
    )


def _action_ref_identity_failure(
    command: ToolCommand,
    action_ref: Mapping[str, Any],
) -> ToolObservation | None:
    target = action_ref.get("target")
    if not isinstance(target, Mapping):
        return None
    role = _optional_string_from_mapping(target, "role")
    if role is None or role.casefold() not in {"axrow", "row"}:
        return None
    target_label = _optional_string_from_mapping(target, "label", "name")
    preconditions = action_ref.get("preconditions")
    label_values = (
        preconditions.get("labelIn")
        if isinstance(preconditions, Mapping)
        else None
    )
    identity_verified = (
        target_label is not None
        and isinstance(label_values, list | tuple)
        and target_label in label_values
    )
    if identity_verified:
        return None

    action_id = _optional_string_from_mapping(action_ref, "id") or "unknown"
    return _failure(
        command,
        status=ToolStatus.FAILED,
        failure_kind="wechat_action_precondition_failed",
        message=(
            "WeChat row actionRef does not contain a verifiable target "
            f"identity: {action_id}"
        ),
        recovery_hint=(
            "Re-run list_conversations or use open_contact(displayName) to "
            "resolve the current row."
        ),
        retryable=True,
        observation={
            "schema": "wechat.execute_action.v1",
            "status": "failed",
            "actionId": action_id,
            "failureKind": "wechat_action_precondition_failed",
        },
    )


def _should_fallback_from_accessibility_action(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    if result.success or result.operation != "accessibility_action":
        return False
    if not _accessibility_action_proof_is_consistent(
        result,
        expected_action=expected_action,
    ):
        return False
    attempted = _accessibility_action_attempted(result)
    dispatched = _accessibility_action_request_dispatched(result)
    if not attempted.valid or not dispatched.valid:
        return False
    failure_kind = _accessibility_action_failure_kind(result)
    if failure_kind == "accessibility_action_unsupported":
        return _accessibility_action_has_definite_no_effect(
            result,
            expected_action=expected_action,
        )
    if not _accessibility_action_has_safe_non_native_effect(result):
        return False
    if attempted.value is True:
        return False
    unsupported = failure_kind in {
        "unsupported_operation",
        "unsupported_accessibility_action",
    }
    metadata = result.metadata if isinstance(result.metadata, Mapping) else {}
    legacy_status = metadata.get("legacyStatus")
    observation = result.observation
    if (
        not unsupported
        and legacy_status == "failed"
        and isinstance(observation, Mapping)
    ):
        nested = observation.get("accessibilityAction")
        if isinstance(nested, Mapping):
            nested_kind = nested.get("failureKind")
            unsupported = nested_kind in {
                "unsupported_operation",
                "unsupported_accessibility_action",
            }
    if unsupported:
        return True
    if result.retryable is not True:
        return False
    return dispatched.present and dispatched.value is False


def _should_try_coordinate_click_after_accessibility_action(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    return _should_fallback_from_accessibility_action(
        result,
        expected_action=expected_action,
    )


def _should_press_return_for_search_result(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    return _should_fallback_from_accessibility_action(
        result,
        expected_action=expected_action,
    )


def _accessibility_action_attempted(result: ToolObservation) -> _BooleanEvidence:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return _BooleanEvidence(present=True, valid=False)
    return _consistent_bool_evidence(
        payloads,
        ("actionAttempted", "action_attempted"),
    )


def _accessibility_action_has_definite_no_effect(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    if result.failure_kind != "accessibility_action_unsupported":
        return False
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return False
    failure_kind = _required_consistent_string_evidence(
        payloads,
        ("failureKind", "failure_kind"),
    )
    action = _required_consistent_string_evidence(payloads, ("action",))
    attempted = _required_consistent_bool_evidence(
        payloads,
        ("actionAttempted", "action_attempted"),
    )
    effect = _required_consistent_string_evidence(
        payloads,
        ("actionEffect", "action_effect"),
    )
    native_error_code = _required_consistent_int_evidence(
        payloads,
        ("nativeErrorCode", "native_error_code"),
    )
    expected_native_error = _DEFINITE_UNSUPPORTED_NATIVE_ERRORS.get(action or "")
    return (
        failure_kind == "accessibility_action_unsupported"
        and action == expected_action
        and expected_native_error is not None
        and attempted is True
        and effect == "none"
        and native_error_code == expected_native_error
    )


def _accessibility_action_has_safe_non_native_effect(
    result: ToolObservation,
) -> bool:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return False
    effect = _consistent_string_evidence(
        payloads,
        ("actionEffect", "action_effect"),
    )
    native_error_code = _consistent_int_evidence(
        payloads,
        ("nativeErrorCode", "native_error_code"),
    )
    if not effect.valid or not native_error_code.valid:
        return False
    if effect.present and effect.value != "none":
        return False
    # A native code means the request reached native action evaluation. Only
    # the complete action-bound unsupported proof above can establish no effect.
    return not native_error_code.present


def _accessibility_action_proof_payloads(
    result: ToolObservation,
) -> tuple[Mapping[str, Any], ...] | None:
    if not all(
        isinstance(payload, Mapping)
        for payload in (result.metadata, result.observation, result.evidence)
    ):
        return None

    top_level: dict[str, Any] = {}
    if result.failure_kind is not None:
        top_level["failureKind"] = result.failure_kind
    if result.retryable is not None:
        top_level["retryable"] = result.retryable

    roots: list[Mapping[str, Any]] = [
        top_level,
        result.metadata,
        result.observation,
        result.evidence,
    ]
    if result.error is not None:
        if isinstance(result.error, ToolError):
            roots.append(result.error.to_dict())
            roots.append(result.error.evidence)
        elif isinstance(result.error, Mapping):
            roots.append(result.error)
            if "evidence" in result.error:
                error_evidence = result.error.get("evidence")
                if not isinstance(error_evidence, Mapping):
                    return None
                roots.append(error_evidence)
        else:
            return None

    nested_container_keys = (
        "metadata",
        "accessibilityAction",
        "accessibility_action",
        "diagnostics",
        "transport",
        "accessibilityActionTransport",
        "accessibility_action_transport",
    )
    payloads: list[Mapping[str, Any]] = []
    pending = list(roots)
    seen: set[int] = set()
    while pending:
        payload = pending.pop(0)
        identity = id(payload)
        if identity in seen:
            continue
        seen.add(identity)
        payloads.append(payload)
        for key in nested_container_keys:
            if key not in payload:
                continue
            nested = payload.get(key)
            if not isinstance(nested, Mapping):
                return None
            pending.append(nested)
    return tuple(payloads)


def _required_consistent_string_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> str | None:
    evidence = _consistent_string_evidence(payloads, keys)
    if not evidence.present or not evidence.valid:
        return None
    return evidence.value


def _consistent_string_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> _StringEvidence:
    values: list[str] = []
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                return _StringEvidence(present=True, valid=False)
            values.append(value)
    if not values:
        return _StringEvidence(present=False, valid=True)
    if any(value != values[0] for value in values[1:]):
        return _StringEvidence(present=True, valid=False)
    return _StringEvidence(present=True, valid=True, value=values[0])


def _required_consistent_bool_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> bool | None:
    evidence = _consistent_bool_evidence(payloads, keys)
    if not evidence.present or not evidence.valid:
        return None
    return evidence.value


def _consistent_bool_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> _BooleanEvidence:
    values: list[bool] = []
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if not isinstance(value, bool):
                return _BooleanEvidence(present=True, valid=False)
            values.append(value)
    if not values:
        return _BooleanEvidence(present=False, valid=True)
    if any(value is not values[0] for value in values[1:]):
        return _BooleanEvidence(present=True, valid=False)
    return _BooleanEvidence(present=True, valid=True, value=values[0])


def _required_consistent_int_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> int | None:
    evidence = _consistent_int_evidence(payloads, keys)
    if not evidence.present or not evidence.valid:
        return None
    return evidence.value


def _consistent_int_evidence(
    payloads: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
) -> _IntegerEvidence:
    values: list[int] = []
    for payload in payloads:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if not isinstance(value, int) or isinstance(value, bool):
                return _IntegerEvidence(present=True, valid=False)
            values.append(value)
    if not values:
        return _IntegerEvidence(present=False, valid=True)
    if any(value != values[0] for value in values[1:]):
        return _IntegerEvidence(present=True, valid=False)
    return _IntegerEvidence(present=True, valid=True, value=values[0])


def _accessibility_action_proof_is_consistent(
    result: ToolObservation,
    *,
    expected_action: str,
) -> bool:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return False
    failure_kind = _consistent_string_evidence(
        payloads,
        ("failureKind", "failure_kind"),
    )
    action = _consistent_string_evidence(payloads, ("action",))
    effect = _consistent_string_evidence(
        payloads,
        ("actionEffect", "action_effect"),
    )
    native_error_code = _consistent_int_evidence(
        payloads,
        ("nativeErrorCode", "native_error_code"),
    )
    attempted = _consistent_bool_evidence(
        payloads,
        ("actionAttempted", "action_attempted"),
    )
    dispatched = _consistent_bool_evidence(
        payloads,
        ("requestDispatched", "request_dispatched"),
    )
    retryable = _consistent_bool_evidence(payloads, ("retryable",))
    if not all(
        item.valid
        for item in (
            failure_kind,
            action,
            effect,
            native_error_code,
            attempted,
            dispatched,
            retryable,
        )
    ):
        return False
    return not action.present or action.value == expected_action


def _accessibility_action_request_dispatched(
    result: ToolObservation,
) -> _BooleanEvidence:
    payloads = _accessibility_action_proof_payloads(result)
    if payloads is None:
        return _BooleanEvidence(present=True, valid=False)
    return _consistent_bool_evidence(
        payloads,
        ("requestDispatched", "request_dispatched"),
    )


def _execute_action_failure_kind(result: ToolObservation) -> str:
    failure_kind = _accessibility_action_failure_kind(result)
    if failure_kind == "wechat_action_ref_expired":
        return "wechat_action_ref_expired"
    if failure_kind in {
        "precondition_failed",
        "wechat_action_precondition_failed",
    }:
        return "wechat_action_precondition_failed"
    return "wechat_action_failed"


def _accessibility_action_failure_kind(result: ToolObservation) -> str | None:
    if result.failure_kind is not None:
        return result.failure_kind
    observation = result.observation
    if isinstance(observation, Mapping):
        for key in ("accessibilityAction", "accessibility_action"):
            nested = observation.get(key)
            if not isinstance(nested, Mapping):
                continue
            failure_kind = nested.get("failureKind") or nested.get("failure_kind")
            if isinstance(failure_kind, str) and failure_kind:
                return failure_kind
    return None


def _selector_fallback_from_action_ref(
    action_ref: Mapping[str, Any],
) -> dict[str, JsonValue] | None:
    fallbacks = action_ref.get("fallbacks")
    if not isinstance(fallbacks, list):
        return None
    for fallback in fallbacks:
        if not isinstance(fallback, Mapping):
            continue
        if fallback.get("method") != "selector_click":
            continue
        selector = fallback.get("selector")
        if not isinstance(selector, Mapping):
            continue
        role = _optional_string_from_mapping(selector, "role")
        name = _optional_string_from_mapping(selector, "name", "title", "label")
        if role is None or name is None:
            continue
        return {"role": role, "name": name}
    return None
