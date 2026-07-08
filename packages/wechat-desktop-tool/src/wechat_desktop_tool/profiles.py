"""Packaged WeChat selector profile loading."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
import tomllib

from computer_use_macos.selectors import (
    AccessibilitySelectorProfile,
    CollectionExtractor,
    SelectorResolver,
    parse_selector_profile,
)

from .control_map import load_control_map
from .control_map import load_packaged_control_map


DEFAULT_WECHAT_SELECTOR_PROFILE_ID = "wechat.macos"
DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE = "profiles/wechat-macos.toml"


def load_packaged_selector_profile() -> AccessibilitySelectorProfile:
    """Load and validate the default packaged WeChat macOS selector profile."""

    profile_text = (
        resources.files("wechat_desktop_tool")
        .joinpath(DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return parse_selector_profile(tomllib.loads(profile_text))


def load_selector_profile(
    selector_profile_path: str | Path | None = None,
) -> AccessibilitySelectorProfile:
    """Load an override selector profile, falling back to the packaged default."""

    if selector_profile_path is None:
        return load_packaged_selector_profile()
    try:
        profile_text = Path(selector_profile_path).expanduser().read_text(
            encoding="utf-8",
        )
        return parse_selector_profile(tomllib.loads(profile_text))
    except (OSError, ValueError, TypeError):
        return load_packaged_selector_profile()


def build_packaged_selector_resolver(
    query_runner: object,
    *,
    app_bundle_id: str = "",
    window_fingerprint: str = "",
    selector_profile_path: str | Path | None = None,
) -> SelectorResolver:
    """Build a resolver for the packaged WeChat selector profile."""

    return SelectorResolver(
        load_selector_profile(selector_profile_path),
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
