"""Diagnostics helpers for internal selector resolution."""

from __future__ import annotations

from .models import SelectorDiagnostics


def selector_diagnostics(
    *,
    tried_selectors: tuple[str, ...] = (),
    query_count: int = 0,
    node_count: int = 0,
    truncated: bool = False,
    truncation_reason: str | None = None,
    cache_status: str = "disabled",
    failure_kind: str | None = None,
    message: str | None = None,
) -> SelectorDiagnostics:
    return SelectorDiagnostics(
        tried_selectors=tried_selectors,
        query_count=query_count,
        node_count=node_count,
        truncated=truncated,
        truncation_reason=truncation_reason,
        cache_status=cache_status,  # type: ignore[arg-type]
        failure_kind=failure_kind,
        message=message,
    )
