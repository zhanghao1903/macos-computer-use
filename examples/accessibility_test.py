#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys

from AppKit import NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    kAXFocusedWindowAttribute,
    kAXTitleAttribute,
    kAXPositionAttribute,
    kAXSizeAttribute,
)


def ax_get(element, attr):
    """
    PyObjC 下 AXUIElementCopyAttributeValue 通常返回:
      (error_code, value)
    error_code == 0 表示成功。
    """
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    if err != 0:
        return None
    return value


def ax_value_to_python(value):
    """
    AXPosition / AXSize 返回的是 AXValue。
    PyObjC 通常会桥接成对象，但不同系统版本表现可能略有差异。
    这里先尽量转成字符串兜底。
    """
    if value is None:
        return None

    # CGPoint / CGSize 有时可以直接访问 x/y 或 width/height
    for shape in ("point", "size"):
        try:
            if shape == "point" and hasattr(value, "x") and hasattr(value, "y"):
                return {"x": float(value.x), "y": float(value.y)}
            if shape == "size" and hasattr(value, "width") and hasattr(value, "height"):
                return {"width": float(value.width), "height": float(value.height)}
        except Exception:
            pass

    return str(value)


def main():
    if not AXIsProcessTrusted():
        print("当前 Python/Terminal 没有 Accessibility 权限。")
        print("请到 系统设置 → 隐私与安全性 → 辅助功能 中授权。")
        sys.exit(1)

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        print("没有找到前台应用")
        sys.exit(1)

    pid = app.processIdentifier()
    app_name = app.localizedName()
    bundle_id = app.bundleIdentifier()

    app_ax = AXUIElementCreateApplication(pid)
    window = ax_get(app_ax, kAXFocusedWindowAttribute)

    if window is None:
        print("没有读取到 focused window，可能该应用没有标准窗口或 AX 暴露不足。")
        sys.exit(1)

    title = ax_get(window, kAXTitleAttribute)
    position = ax_get(window, kAXPositionAttribute)
    size = ax_get(window, kAXSizeAttribute)

    result = {
        "app": {
            "name": app_name,
            "bundle_id": bundle_id,
            "pid": pid,
        },
        "window": {
            "title": str(title) if title is not None else None,
            "position": ax_value_to_python(position),
            "size": ax_value_to_python(size),
        },
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()