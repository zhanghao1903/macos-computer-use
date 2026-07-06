"""Packaged WeChat selector profile loading."""

from __future__ import annotations

from importlib import resources
import tomllib

from computer_use_macos.selectors import (
    AccessibilitySelectorProfile,
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


__all__ = [
    "DEFAULT_WECHAT_SELECTOR_PROFILE_ID",
    "DEFAULT_WECHAT_SELECTOR_PROFILE_RESOURCE",
    "load_packaged_selector_profile",
]
