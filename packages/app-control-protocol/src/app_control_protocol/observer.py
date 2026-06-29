"""Observer callback protocol for app-control stream events."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ToolEvent


@runtime_checkable
class ToolObserver(Protocol):
    """Callback interface for callers that want to route tool events."""

    def on_event(self, event: ToolEvent) -> None:
        """Handle one stream event."""
