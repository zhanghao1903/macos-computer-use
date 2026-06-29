"""Client protocols for app-control command execution."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol, runtime_checkable

from .models import ToolCommand, ToolEvent, ToolObservation
from .observer import ToolObserver


@runtime_checkable
class AppControlClient(Protocol):
    """Minimal protocol surface for app-control command execution."""

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: ToolObserver | None = None,
    ) -> ToolObservation:
        """Run one command and return its final observation."""


@runtime_checkable
class StreamingAppControlClient(AppControlClient, Protocol):
    """App-control client that can also stream command events."""

    def run_stream(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: ToolObserver | None = None,
    ) -> Iterator[ToolEvent]:
        """Run one command and yield stream events."""
