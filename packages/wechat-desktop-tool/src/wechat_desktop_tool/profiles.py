"""Packaged WeChat selector profile loading."""

from __future__ import annotations

from importlib import resources
import tomllib

from computer_use_macos.selectors import (
    AccessibilitySelectorProfile,
    CollectionExtractor,
    SelectorResolver,
    parse_selector_profile,
)


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


def build_packaged_selector_resolver(
    query_runner: object,
    *,
    app_bundle_id: str = "",
    window_fingerprint: str = "",
) -> SelectorResolver:
    """Build a resolver for the packaged WeChat selector profile."""

    return SelectorResolver(
        load_packaged_selector_profile(),
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
    "load_packaged_selector_profile",
]
