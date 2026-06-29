"""Helper app endpoint manifest parsing and identity checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from ..models import JsonValue

DEFAULT_HELPER_API_VERSION = "app_control.helper.v1"


class HelperManifestIdentityError(ValueError):
    """Raised when a manifest does not match expected helper identity."""


@dataclass(frozen=True)
class HelperManifest:
    """Connection metadata published by a local helper app."""

    bundle_id: str
    api_version: str = DEFAULT_HELPER_API_VERSION
    transport: str = "unix_socket"
    endpoint: str | None = None
    socket_path: str | None = None
    token: str | None = None
    token_ref: str | None = None
    helper_app_path: str | None = None
    pid: int | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", _non_empty(self.bundle_id, "bundle_id"))
        object.__setattr__(
            self,
            "api_version",
            _non_empty(self.api_version, "api_version"),
        )
        object.__setattr__(self, "transport", _non_empty(self.transport, "transport"))
        if self.pid is not None and self.pid <= 0:
            raise ValueError("pid must be positive")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HelperManifest":
        return cls(
            bundle_id=_string_field(payload, "bundleId", "bundle_id"),
            api_version=_optional_string_field(
                payload,
                "apiVersion",
                "api_version",
                default=DEFAULT_HELPER_API_VERSION,
            ),
            transport=_optional_string_field(
                payload,
                "transport",
                default="unix_socket",
            ),
            endpoint=_optional_string_field(payload, "endpoint"),
            socket_path=_optional_string_field(payload, "socketPath", "socket_path"),
            token=_optional_string_field(payload, "token"),
            token_ref=_optional_string_field(payload, "tokenRef", "token_ref"),
            helper_app_path=_optional_string_field(
                payload,
                "helperAppPath",
                "helper_app_path",
            ),
            pid=_optional_int_field(payload, "pid"),
            metadata=_json_mapping(payload.get("metadata", {}), "metadata"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "bundleId": self.bundle_id,
            "apiVersion": self.api_version,
            "transport": self.transport,
        }
        if self.endpoint is not None:
            payload["endpoint"] = self.endpoint
        if self.socket_path is not None:
            payload["socketPath"] = self.socket_path
        if self.token is not None:
            payload["token"] = self.token
        if self.token_ref is not None:
            payload["tokenRef"] = self.token_ref
        if self.helper_app_path is not None:
            payload["helperAppPath"] = self.helper_app_path
        if self.pid is not None:
            payload["pid"] = self.pid
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def validate_identity(
        self,
        *,
        expected_bundle_id: str | None = None,
        expected_api_version: str | None = DEFAULT_HELPER_API_VERSION,
    ) -> None:
        if expected_bundle_id and self.bundle_id != expected_bundle_id:
            raise HelperManifestIdentityError(
                "helper bundle id mismatch: "
                f"expected {expected_bundle_id}, got {self.bundle_id}"
            )
        if expected_api_version and self.api_version != expected_api_version:
            raise HelperManifestIdentityError(
                "helper api version mismatch: "
                f"expected {expected_api_version}, got {self.api_version}"
            )

    def read_token(self) -> str | None:
        if self.token is not None:
            return self.token
        if self.token_ref is None:
            return None
        return Path(self.token_ref).expanduser().read_text(encoding="utf-8").strip()


def load_helper_manifest(path: str | Path) -> HelperManifest:
    manifest_path = Path(path).expanduser()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("helper manifest must contain a JSON object")
    return HelperManifest.from_dict(payload)


def _string_field(payload: Mapping[str, Any], *names: str) -> str:
    value = _field(payload, *names)
    return _non_empty(value, " or ".join(names))


def _optional_string_field(
    payload: Mapping[str, Any],
    *names: str,
    default: str | None = None,
) -> str | None:
    value = _field(payload, *names)
    if value is None:
        return default
    return _non_empty(value, " or ".join(names))


def _optional_int_field(payload: Mapping[str, Any], *names: str) -> int | None:
    value = _field(payload, *names)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(" or ".join(names) + " must be an integer")
    return value


def _field(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _json_mapping(value: Any, field_name: str) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: Any) -> JsonValue:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"value is not JSON compatible: {type(value).__name__}")
