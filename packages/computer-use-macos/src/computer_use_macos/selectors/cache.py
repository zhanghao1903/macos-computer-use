"""In-memory selector cache for internal resolver use."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import SelectorCacheEntry


@dataclass
class SelectorCache:
    """Small in-memory cache keyed by profile, version, selector, app, and window."""

    _entries: dict[tuple[str, str, str, str, str], SelectorCacheEntry] = field(
        default_factory=dict
    )

    def get(
        self,
        *,
        profile_id: str,
        profile_version: str,
        selector_id: str,
        app_bundle_id: str,
        window_fingerprint: str,
    ) -> SelectorCacheEntry | None:
        return self._entries.get(
            (
                profile_id,
                profile_version,
                selector_id,
                app_bundle_id,
                window_fingerprint,
            )
        )

    def put(self, entry: SelectorCacheEntry) -> None:
        self._entries[
            (
                entry.profile_id,
                entry.profile_version,
                entry.selector_id,
                entry.app_bundle_id,
                entry.window_fingerprint,
            )
        ] = entry

    def delete(self, entry: SelectorCacheEntry) -> None:
        self._entries.pop(
            (
                entry.profile_id,
                entry.profile_version,
                entry.selector_id,
                entry.app_bundle_id,
                entry.window_fingerprint,
            ),
            None,
        )
