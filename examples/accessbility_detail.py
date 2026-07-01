#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import subprocess
from pathlib import Path
from typing import Any

import objc
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyActionNames,
    kAXFocusedWindowAttribute,
)


CHILDREN_ATTRIBUTE = "AXChildren"
APPKIT_FRAMEWORK_PATH = "/System/Library/Frameworks/AppKit.framework"

WECHAT_APP_NAMES = [
    "WeChat",
    "微信",
]


def ax_attribute_names(element):
    try:
        err, names = AXUIElementCopyAttributeNames(element, None)
        if err != 0 or names is None:
            return []
        return [str(name) for name in names]
    except Exception:
        return []


def ax_get(element, attr):
    try:
        err, value = AXUIElementCopyAttributeValue(element, attr, None)
        if err != 0:
            return None
        return value
    except Exception:
        return None


def ax_actions(element):
    try:
        err, actions = AXUIElementCopyActionNames(element, None)
        if err != 0 or actions is None:
            return []
        return [str(a) for a in actions]
    except Exception:
        return []


def shared_workspace():
    objc.loadBundle("AppKit", globals(), bundle_path=APPKIT_FRAMEWORK_PATH)
    workspace_class = objc.lookUpClass("NSWorkspace")
    return workspace_class.sharedWorkspace()


def safe_scalar(value: Any):
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    # PyObjC bridged NSString / NSNumber 通常已经能走到上面；
    # CGPoint / CGSize / AXValue 这里先转字符串，后面你可以再精细解析。
    text = str(value)

    # 避免 value 里塞入特别长的文本，比如聊天输入框或网页正文
    if len(text) > 500:
        return text[:500] + "...<truncated>"

    return text


def dump_element(element, depth=0, max_depth=5, path="0"):
    node: dict[str, Any] = {
        "path": path,
        "depth": depth,
    }

    attribute_names = ax_attribute_names(element)
    node["attribute_names"] = attribute_names

    for attr in attribute_names:
        if attr == CHILDREN_ATTRIBUTE:
            continue
        value = ax_get(element, attr)
        py_value = safe_scalar(value)
        if py_value is not None:
            node[attr] = py_value

    actions = ax_actions(element)
    if actions:
        node["actions"] = actions

    if depth >= max_depth:
        return node

    children = (
        ax_get(element, CHILDREN_ATTRIBUTE)
        if CHILDREN_ATTRIBUTE in attribute_names
        else None
    )
    if children:
        node["children_count"] = len(children)
        node["children"] = []
        for idx, child in enumerate(children):
            child_path = f"{path}/{idx}"
            node["children"].append(
                dump_element(child, depth + 1, max_depth, child_path)
            )
    else:
        node["children_count"] = 0

    return node


def open_wechat_by_open_command():
    """
    用 macOS open 命令启动 / 激活微信。
    - open -a WeChat：英文系统 / 标准 app 名通常可用
    - open -a 微信：中文 app 名兜底
    """
    last_error = None
    for app_name in WECHAT_APP_NAMES:
        try:
            subprocess.run(
                ["open", "-a", app_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return
        except subprocess.CalledProcessError as e:
            last_error = e.stderr
    raise RuntimeError(f"无法通过 open -a 启动 WeChat: {last_error}")

def main():
    if not AXIsProcessTrusted():
        print("当前 Python/Terminal 没有 Accessibility 权限。")
        print("请到 系统设置 → 隐私与安全性 → 辅助功能 中授权。")
        sys.exit(1)

    open_wechat_by_open_command()
    app = shared_workspace().frontmostApplication()
    if app is None:
        print("没有找到前台应用。")
        sys.exit(1)

    pid = app.processIdentifier()
    app_name = app.localizedName()
    bundle_id = app.bundleIdentifier()


    app_ax = AXUIElementCreateApplication(pid)
    window = ax_get(app_ax, kAXFocusedWindowAttribute)

    if window is None:
        print("没有读取到 focused window。")
        sys.exit(1)

    tree = dump_element(window, max_depth=6)

    result = {
        "app": {
            "name": app_name,
            "bundle_id": bundle_id,
            "pid": pid,
        },
        "focused_window": tree,
    }
    output_path = Path("window.json.bak")
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入: {output_path.resolve()}")


if __name__ == "__main__":
    main()
