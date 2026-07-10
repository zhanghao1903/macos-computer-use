"""Post one native macOS left-click at a global screen coordinate."""

from __future__ import annotations

from collections.abc import Sequence
import sys
import time


def click_coordinate(x: int, y: int) -> None:
    from ApplicationServices import (
        CGEventCreateMouseEvent,
        CGEventPost,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGHIDEventTap,
        kCGMouseButtonLeft,
    )

    point = (x, y)
    mouse_down = CGEventCreateMouseEvent(
        None,
        kCGEventLeftMouseDown,
        point,
        kCGMouseButtonLeft,
    )
    mouse_up = CGEventCreateMouseEvent(
        None,
        kCGEventLeftMouseUp,
        point,
        kCGMouseButtonLeft,
    )
    if mouse_down is None or mouse_up is None:
        raise RuntimeError("could not create Quartz mouse events")
    CGEventPost(kCGHIDEventTap, mouse_down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, mouse_up)


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if len(values) != 2:
        print("expected x and y coordinates", file=sys.stderr)
        return 2
    try:
        x, y = (int(value) for value in values)
        click_coordinate(x, y)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
