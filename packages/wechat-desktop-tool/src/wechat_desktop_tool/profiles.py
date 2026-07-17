"""Packaged WeChat selector profile loading."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any
import tomllib

from computer_use_macos.selectors import (
    AccessibilitySelectorProfile,
    CollectionExtractor,
    SelectorResolver,
    parse_selector_profile,
)

from .control_map import WeChatControlMap, parse_control_map


DEFAULT_WECHAT_SELECTOR_PROFILE_ID = "wechat.macos"
DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE = "profiles/wechat-macos.toml"


@dataclass(frozen=True)
class WeChatSelectorAssets:
    """Validated generic and WeChat-specific selectors from one TOML source."""

    selector_profile: AccessibilitySelectorProfile
    control_map: WeChatControlMap


def load_packaged_selector_assets() -> WeChatSelectorAssets:
    """Load the packaged selector profile and control map atomically."""

    profile_text = (
        resources.files("wechat_desktop_tool")
        .joinpath(DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return parse_selector_assets(tomllib.loads(profile_text))


def load_selector_assets(
    selector_profile_path: str | Path | None = None,
) -> WeChatSelectorAssets:
    """Activate an override only when both selector components validate."""

    if selector_profile_path is not None:
        try:
            profile_text = Path(selector_profile_path).expanduser().read_text(
                encoding="utf-8",
            )
            return parse_selector_assets(tomllib.loads(profile_text))
        except (OSError, ValueError, TypeError):
            pass
    return load_packaged_selector_assets()


def parse_selector_assets(data: Mapping[str, Any]) -> WeChatSelectorAssets:
    """Parse both components before publishing either one."""

    selector_profile = parse_selector_profile(data)
    control_map = parse_control_map(data)
    return WeChatSelectorAssets(
        selector_profile=selector_profile,
        control_map=control_map,
    )


def load_packaged_selector_profile() -> AccessibilitySelectorProfile:
    """Load and validate the default packaged WeChat macOS selector profile."""

    return load_packaged_selector_assets().selector_profile


def load_selector_profile(
    selector_profile_path: str | Path | None = None,
) -> AccessibilitySelectorProfile:
    """Load an override selector profile, falling back to the packaged default."""

    return load_selector_assets(selector_profile_path).selector_profile


def load_control_map(
    selector_profile_path: str | Path | None = None,
) -> WeChatControlMap:
    """Load the control map from the same atomic selector asset pair."""

    return load_selector_assets(selector_profile_path).control_map


def load_packaged_control_map() -> WeChatControlMap:
    """Load the packaged control map from the atomic selector asset pair."""

    return load_packaged_selector_assets().control_map


def build_packaged_selector_resolver(
    query_runner: object,
    *,
    app_bundle_id: str = "",
    window_fingerprint: str = "",
    selector_profile_path: str | Path | None = None,
    selector_profile: AccessibilitySelectorProfile | None = None,
) -> SelectorResolver:
    """Build a resolver for the packaged WeChat selector profile."""

    return SelectorResolver(
        selector_profile or load_selector_profile(selector_profile_path),
        query_runner,  # type: ignore[arg-type]
        app_bundle_id=app_bundle_id,
        window_fingerprint=window_fingerprint,
    )


def build_packaged_collection_extractor(
    resolver: SelectorResolver,
) -> CollectionExtractor:
    """Build a collection extractor for the packaged WeChat selector profile."""

    return CollectionExtractor(resolver)


__all__ = [
    "build_packaged_collection_extractor",
    "build_packaged_selector_resolver",
    "DEFAULT_WECHAT_SELECTOR_PROFILE_ID",
    "DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE",
    "load_control_map",
    "load_packaged_control_map",
    "load_packaged_selector_profile",
    "load_selector_profile",
]
