"""JSON type helpers for app-control protocol payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from enum import Enum
from typing import Any, TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def to_json_value(value: Any) -> JsonValue:
    """Return a JSON-compatible value or raise ``TypeError``."""

    if isinstance(value, Enum):
        return to_json_value(value.value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, tuple | list):
        return [to_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return ensure_json_mapping(value, "mapping")
    if is_dataclass(value) and hasattr(value, "to_dict"):
        converted = value.to_dict()
        return ensure_json_mapping(converted, "dataclass")
    raise TypeError(f"value is not JSON compatible: {type(value).__name__}")


def ensure_json_mapping(value: Any, field_name: str) -> dict[str, JsonValue]:
    """Validate a mapping with string keys and JSON-compatible values."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    output: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{field_name} keys must be strings")
        output[key] = to_json_value(item)
    return output


def require_non_empty_string(value: Any, field_name: str) -> str:
    """Return a stripped non-empty string or raise ``ValueError``."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()
