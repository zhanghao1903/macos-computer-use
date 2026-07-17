"""Read-only prerequisite probe for live WeChat selector smoke tests.

Run this before live WeChat smoke checks when the desktop state is unclear:

    /opt/anaconda3/bin/python examples/wechat_live_prereq_probe.py \
      --output /private/tmp/wechat-live-prereq-probe.json

The probe does not open apps, click, type, focus windows, draft messages, or
send messages. It only reads the current frontmost app and WeChat Accessibility
window state so a developer can tell whether the selector-engine smoke test has
the required desktop prerequisites.
"""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
import sys
from typing import Any


SCHEMA = "macos_computer_use.sdk.wechat_live_prereq_probe.v1"
DEFAULT_OUTPUT = "./wechat-live-prereq-probe.json"
DEFAULT_WECHAT_BUNDLE_IDS = ("com.tencent.xinWeChat",)


class PyObjCWeChatPrereqProvider:
    """Collect read-only WeChat window prerequisites through PyObjC."""

    def __init__(self, bundle_ids: Sequence[str]) -> None:
        self._bundle_ids = tuple(bundle_ids)

    def collect(self) -> dict[str, Any]:
        try:
            importlib.import_module("AppKit")
            objc = importlib.import_module("objc")
            application_services = importlib.import_module("ApplicationServices")
        except ImportError as exc:
            raise RuntimeError(f"PyObjC module unavailable: {exc}") from exc

        workspace_class = objc.lookUpClass("NSWorkspace")
        workspace = workspace_class.sharedWorkspace()
        frontmost = workspace.frontmostApplication()
        running_apps = list(workspace.runningApplications())

        wechat_apps = [
            app
            for app in running_apps
            if _safe_text(_call(app, "bundleIdentifier")) in self._bundle_ids
        ]
        ax_trusted = bool(application_services.AXIsProcessTrusted())

        return {
            "status": "ok",
            "accessibilityTrusted": ax_trusted,
            "frontmost": _app_info(frontmost),
            "wechatApps": [
                _wechat_app_info(app, application_services) for app in wechat_apps
            ],
        }


def run_live_prereq_probe(
    *,
    output_path: str | Path | None = None,
    bundle_ids: Sequence[str] = DEFAULT_WECHAT_BUNDLE_IDS,
    provider: Any | None = None,
) -> dict[str, Any]:
    concrete_provider = provider or PyObjCWeChatPrereqProvider(bundle_ids)
    try:
        raw_state = concrete_provider.collect()
    except Exception as exc:
        raw_state = {
            "status": "failed",
            "failureKind": "pyobjc_probe_failed",
            "message": str(exc),
            "accessibilityTrusted": False,
            "frontmost": None,
            "wechatApps": [],
        }

    report = _build_report(raw_state, bundle_ids=bundle_ids)
    if output_path is not None:
        _write_json(output_path, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    bundle_ids = tuple(args.bundle_ids or DEFAULT_WECHAT_BUNDLE_IDS)
    try:
        payload = run_live_prereq_probe(
            output_path=args.output,
            bundle_ids=bundle_ids,
        )
    except Exception as exc:
        print(f"wechat live prerequisite probe failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"wrote: {Path(args.output).expanduser()}")
    return 0 if payload["success"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read current WeChat Accessibility smoke prerequisites.",
    )
    parser.add_argument(
        "--bundle-id",
        dest="bundle_ids",
        action="append",
        help="Accepted WeChat bundle id. Can be passed multiple times.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser


def _build_report(
    raw_state: Mapping[str, Any],
    *,
    bundle_ids: Sequence[str],
) -> dict[str, Any]:
    accepted_bundle_ids = tuple(bundle_ids)
    frontmost = _mapping_value(raw_state.get("frontmost"))
    wechat_apps = _list_value(raw_state.get("wechatApps"))
    accessibility_trusted = raw_state.get("accessibilityTrusted") is True
    frontmost_bundle_id = _text_value(frontmost.get("bundleId")) if frontmost else None
    focused_window = _first_focused_window(wechat_apps, frontmost_bundle_id)
    all_windows = _all_windows(wechat_apps)

    checks = {
        "probeRan": raw_state.get("status") == "ok",
        "accessibilityTrusted": accessibility_trusted,
        "wechatRunning": len(wechat_apps) > 0,
        "frontmostWeChat": frontmost_bundle_id in accepted_bundle_ids,
        "wechatAxWindow": _has_ax_window(focused_window, all_windows),
    }
    failure_kind = _failure_kind(raw_state, checks)
    ready = failure_kind is None

    payload = {
        "schema": SCHEMA,
        "success": ready,
        "readyForSmoke": ready,
        "status": "ready" if ready else "not_ready",
        "failureKind": failure_kind,
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "acceptedBundleIds": list(accepted_bundle_ids),
        "frontmost": frontmost,
        "accessibilityTrusted": accessibility_trusted,
        "wechat": {
            "runningCount": len(wechat_apps),
            "apps": wechat_apps,
            "focusedWindow": focused_window,
            "windows": all_windows,
        },
        "summary": {
            "success": ready,
            "readyForSmoke": ready,
            "failureKind": failure_kind,
            "checks": checks,
            "message": _summary_message(failure_kind, frontmost_bundle_id),
        },
    }
    return payload


def _failure_kind(
    raw_state: Mapping[str, Any],
    checks: Mapping[str, bool],
) -> str | None:
    if raw_state.get("status") != "ok":
        failure_kind = raw_state.get("failureKind")
        return _text_value(failure_kind) or "pyobjc_probe_failed"
    if not checks["accessibilityTrusted"]:
        return "accessibility_not_trusted"
    if not checks["wechatRunning"]:
        return "wechat_not_running"
    if not checks["frontmostWeChat"]:
        return "frontmost_not_wechat"
    if not checks["wechatAxWindow"]:
        return "wechat_ax_window_missing"
    return None


def _summary_message(failure_kind: str | None, frontmost_bundle_id: str | None) -> str:
    if failure_kind is None:
        return "WeChat is frontmost and exposes an AXWindow for live smoke tests."
    if failure_kind == "accessibility_not_trusted":
        return "The current Python host is not trusted for macOS Accessibility."
    if failure_kind == "wechat_not_running":
        return "WeChat is not running."
    if failure_kind == "frontmost_not_wechat":
        return f"Frontmost app is {frontmost_bundle_id!r}; expected WeChat."
    if failure_kind == "wechat_ax_window_missing":
        return "WeChat is running but does not expose an AXWindow."
    return "The PyObjC prerequisite probe could not read desktop state."


def _first_focused_window(
    wechat_apps: Sequence[Any],
    frontmost_bundle_id: str | None,
) -> dict[str, Any] | None:
    if frontmost_bundle_id:
        for app in wechat_apps:
            app_payload = _mapping_value(app)
            if not app_payload or app_payload.get("bundleId") != frontmost_bundle_id:
                continue
            focused = _mapping_value(app_payload.get("focusedWindow"))
            if focused:
                return focused
    for app in wechat_apps:
        app_payload = _mapping_value(app)
        focused = _mapping_value(app_payload.get("focusedWindow")) if app_payload else None
        if focused:
            return focused
    return None


def _all_windows(wechat_apps: Sequence[Any]) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for app in wechat_apps:
        app_payload = _mapping_value(app)
        app_windows = _list_value(app_payload.get("windows")) if app_payload else []
        for window in app_windows:
            window_payload = _mapping_value(window)
            if window_payload:
                windows.append(window_payload)
    return windows


def _has_ax_window(
    focused_window: Mapping[str, Any] | None,
    windows: Sequence[Mapping[str, Any]],
) -> bool:
    if focused_window and focused_window.get("role") == "AXWindow":
        return True
    return any(window.get("role") == "AXWindow" for window in windows)


def _wechat_app_info(app: Any, application_services: Any) -> dict[str, Any]:
    pid = _call(app, "processIdentifier")
    ax_app = application_services.AXUIElementCreateApplication(pid)
    focused_window = _ax_get(
        ax_app,
        "AXFocusedWindow",
        application_services=application_services,
    )
    windows = (
        _ax_get(ax_app, "AXWindows", application_services=application_services) or []
    )
    return {
        **_app_info(app),
        "focusedWindow": _window_info(
            focused_window,
            application_services=application_services,
        )
        if focused_window
        else None,
        "windows": [
            _window_info(window, index=index, application_services=application_services)
            for index, window in enumerate(windows)
        ],
    }


def _window_info(
    window: Any,
    *,
    application_services: Any,
    index: int | None = None,
) -> dict[str, Any]:
    children = _ax_get(window, "AXChildren", application_services=application_services)
    payload = {
        "role": _safe_text(
            _ax_get(window, "AXRole", application_services=application_services)
        ),
        "subrole": _safe_text(
            _ax_get(window, "AXSubrole", application_services=application_services)
        ),
        "title": _safe_text(
            _ax_get(window, "AXTitle", application_services=application_services)
        ),
        "description": _safe_text(
            _ax_get(window, "AXDescription", application_services=application_services)
        ),
        "childrenCount": len(children) if isinstance(children, Sequence) else None,
    }
    if index is not None:
        payload["index"] = index
    return payload


def _ax_get(element: Any, attr: str, *, application_services: Any) -> Any:
    try:
        err, value = application_services.AXUIElementCopyAttributeValue(
            element,
            attr,
            None,
        )
    except Exception:
        return None
    if err != 0:
        return None
    return value


def _app_info(app: Any) -> dict[str, Any] | None:
    if app is None:
        return None
    return {
        "name": _safe_text(_call(app, "localizedName")),
        "bundleId": _safe_text(_call(app, "bundleIdentifier")),
        "pid": _call(app, "processIdentifier"),
        "active": _call(app, "isActive"),
        "hidden": _call(app, "isHidden"),
    }


def _call(obj: Any, name: str) -> Any:
    method = getattr(obj, name, None)
    if method is None:
        return None
    try:
        return method()
    except Exception:
        return None


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _mapping_value(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _list_value(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text_value(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
