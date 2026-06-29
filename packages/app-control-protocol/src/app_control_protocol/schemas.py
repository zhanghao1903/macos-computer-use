"""Packaged JSON Schema assets for app-control protocol envelopes."""

from __future__ import annotations

from importlib import resources
import json
from typing import Any, Literal

from .errors import ProtocolValidationError
from .json_types import JsonValue, ensure_json_mapping

ProtocolSchemaName = Literal[
    "command",
    "observation",
    "event",
    "error",
    "service_request",
    "service_response",
    "service_event",
    "helper_request",
    "helper_response",
]

PROTOCOL_SCHEMA_FILES: dict[ProtocolSchemaName, str] = {
    "command": "command.schema.json",
    "observation": "observation.schema.json",
    "event": "event.schema.json",
    "error": "error.schema.json",
    "service_request": "service-request.schema.json",
    "service_response": "service-response.schema.json",
    "service_event": "service-event.schema.json",
    "helper_request": "helper-request.schema.json",
    "helper_response": "helper-response.schema.json",
}


def protocol_schema_names() -> tuple[ProtocolSchemaName, ...]:
    """Return stable names for the packaged JSON Schema documents."""

    return tuple(PROTOCOL_SCHEMA_FILES)


def load_protocol_schema(name: ProtocolSchemaName) -> dict[str, JsonValue]:
    """Load one packaged JSON Schema document as a JSON-compatible mapping."""

    try:
        filename = PROTOCOL_SCHEMA_FILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown protocol schema: {name}") from exc
    schema_file = resources.files(__package__).joinpath("schemas", filename)
    payload = json.loads(schema_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"protocol schema is not a JSON object: {name}")
    return payload


def load_protocol_schemas() -> dict[ProtocolSchemaName, dict[str, JsonValue]]:
    """Load all packaged JSON Schema documents."""

    return {name: load_protocol_schema(name) for name in protocol_schema_names()}


def validate_protocol_payload(
    name: ProtocolSchemaName,
    payload: Any,
) -> dict[str, JsonValue]:
    """Validate a payload against one packaged protocol schema.

    This is a small built-in validator for the JSON Schema subset used by the
    protocol package. It avoids a runtime dependency on a full JSON Schema
    implementation while still giving SDK callers a stable validation entry.
    """

    schema = load_protocol_schema(name)
    _validate_schema(payload, schema, schema, "$")
    return ensure_json_mapping(payload, name)


def _validate_schema(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> None:
    ref = schema.get("$ref")
    if isinstance(ref, str):
        _validate_schema(value, _resolve_ref(ref, root_schema), root_schema, path)
        return

    if "const" in schema and value != schema["const"]:
        raise ProtocolValidationError(
            f"{path} must be {schema['const']!r}, got {value!r}"
        )

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        raise ProtocolValidationError(f"{path} must be one of {enum!r}, got {value!r}")

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        _validate_type(value, expected_type, path)

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        matches = 0
        last_error: ProtocolValidationError | None = None
        for option in one_of:
            if not isinstance(option, dict):
                continue
            try:
                _validate_schema(value, option, root_schema, path)
            except ProtocolValidationError as exc:
                last_error = exc
            else:
                matches += 1
        if matches != 1:
            message = (
                f"{path} must match exactly one schema option; matched {matches}"
            )
            if last_error is not None and matches == 0:
                message = f"{message}: {last_error}"
            raise ProtocolValidationError(message)

    if isinstance(value, dict):
        _validate_object(value, schema, root_schema, path)
    if isinstance(value, list):
        _validate_array(value, schema, root_schema, path)

    minimum = schema.get("minimum")
    if isinstance(minimum, int | float) and _is_number(value) and value < minimum:
        raise ProtocolValidationError(f"{path} must be >= {minimum}, got {value!r}")

    min_length = schema.get("minLength")
    if isinstance(min_length, int) and isinstance(value, str) and len(value) < min_length:
        raise ProtocolValidationError(
            f"{path} must contain at least {min_length} character(s)"
        )

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for clause in all_of:
            if isinstance(clause, dict):
                _validate_conditional(value, clause, root_schema, path)


def _validate_object(
    value: dict[str, Any],
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> None:
    required = schema.get("required", [])
    if isinstance(required, list):
        for key in required:
            if isinstance(key, str) and key not in value:
                raise ProtocolValidationError(f"{path}.{key} is required")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    additional = schema.get("additionalProperties", True)
    for key, item in value.items():
        child_path = f"{path}.{key}"
        child_schema = properties.get(key)
        if isinstance(child_schema, dict):
            _validate_schema(item, child_schema, root_schema, child_path)
        elif additional is False:
            raise ProtocolValidationError(f"{child_path} is not allowed")
        elif isinstance(additional, dict):
            _validate_schema(item, additional, root_schema, child_path)


def _validate_array(
    value: list[Any],
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> None:
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(value):
            _validate_schema(item, items, root_schema, f"{path}[{index}]")


def _validate_conditional(
    value: Any,
    clause: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> None:
    condition = clause.get("if")
    if not isinstance(condition, dict):
        _validate_schema(value, clause, root_schema, path)
        return
    branch_name = "then" if _matches_schema(value, condition, root_schema, path) else "else"
    branch = clause.get(branch_name)
    if isinstance(branch, dict):
        _validate_schema(value, branch, root_schema, path)


def _matches_schema(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> bool:
    try:
        _validate_schema(value, schema, root_schema, path)
    except ProtocolValidationError:
        return False
    return True


def _validate_type(value: Any, expected_type: str, path: str) -> None:
    if expected_type == "object" and not isinstance(value, dict):
        raise ProtocolValidationError(f"{path} must be an object")
    if expected_type == "array" and not isinstance(value, list):
        raise ProtocolValidationError(f"{path} must be an array")
    if expected_type == "string" and not isinstance(value, str):
        raise ProtocolValidationError(f"{path} must be a string")
    if expected_type == "integer" and (
        isinstance(value, bool) or not isinstance(value, int)
    ):
        raise ProtocolValidationError(f"{path} must be an integer")
    if expected_type == "number" and not _is_number(value):
        raise ProtocolValidationError(f"{path} must be a number")
    if expected_type == "boolean" and not isinstance(value, bool):
        raise ProtocolValidationError(f"{path} must be a boolean")
    if expected_type == "null" and value is not None:
        raise ProtocolValidationError(f"{path} must be null")


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float)


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise ProtocolValidationError(f"unsupported schema ref: {ref}")
    target: Any = root_schema.get("$defs", {})
    for part in ref[len("#/") :].split("/"):
        if part == "$defs":
            target = root_schema.get("$defs", {})
            continue
        if not isinstance(target, dict) or part not in target:
            raise ProtocolValidationError(f"unknown schema ref: {ref}")
        target = target[part]
    if not isinstance(target, dict):
        raise ProtocolValidationError(f"schema ref does not resolve to object: {ref}")
    return target
