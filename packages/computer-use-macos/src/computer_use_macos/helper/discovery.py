"""Helper manifest discovery."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from .manifest import HelperManifest, load_helper_manifest

DEFAULT_HELPER_MANIFEST_ENV_VARS = (
    "APP_CONTROL_HELPER_MANIFEST",
    "MACOS_COMPUTER_USE_HELPER_MANIFEST",
    "COMPUTER_USE_MACOS_HELPER_MANIFEST",
)


@dataclass(frozen=True)
class HelperDiscoveryResult:
    status: str
    manifest: HelperManifest | None = None
    manifest_path: Path | None = None
    summary: str = ""

    @property
    def found(self) -> bool:
        return self.status == "found"

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status,
            "summary": self.summary,
        }
        if self.manifest_path is not None:
            payload["manifestPath"] = str(self.manifest_path)
        if self.manifest is not None:
            payload["manifest"] = self.manifest.to_dict()
        return payload


def find_helper_manifest_path(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    if path is not None:
        return Path(path).expanduser()
    environment = env if env is not None else os.environ
    for name in DEFAULT_HELPER_MANIFEST_ENV_VARS:
        value = environment.get(name)
        if value:
            return Path(value).expanduser()
    return None


def discover_helper_manifest(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> HelperDiscoveryResult:
    manifest_path = find_helper_manifest_path(path, env=env)
    if manifest_path is None:
        return HelperDiscoveryResult(
            status="not_configured",
            summary="helper manifest path is not configured",
        )
    if not manifest_path.exists():
        return HelperDiscoveryResult(
            status="missing",
            manifest_path=manifest_path,
            summary=f"helper manifest not found: {manifest_path}",
        )
    try:
        manifest = load_helper_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001 - discovery returns sanitized state.
        return HelperDiscoveryResult(
            status="invalid",
            manifest_path=manifest_path,
            summary=f"helper manifest is invalid: {exc}",
        )
    return HelperDiscoveryResult(
        status="found",
        manifest=manifest,
        manifest_path=manifest_path,
        summary="helper manifest loaded",
    )
