"""Allowlisted scalar transforms for selector collection fields."""

from __future__ import annotations

from .models import JsonValue


def apply_transform(value: JsonValue, transform: str | None) -> JsonValue:
    if transform is None:
        return value
    if transform == "strip":
        return value.strip() if isinstance(value, str) else value
    if transform == "firstText":
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item
        return value
    if transform == "joinText":
        if isinstance(value, list):
            return " ".join(item.strip() for item in value if isinstance(item, str))
        return value
    if transform == "toBool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "selected"}
        return bool(value)
    raise ValueError(f"unknown selector transform: {transform}")
