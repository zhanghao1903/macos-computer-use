"""Manual WeChat Desktop smoke for wechat-desktop-tool."""

from __future__ import annotations

from collections.abc import Mapping
import os
import sys

from wechat_desktop_tool.cli import main as wechat_cli_main


def main(env: Mapping[str, str] | None = None) -> int:
    values = os.environ if env is None else env
    contact = values.get("WECHAT_TOOL_CONTACT", "").strip()
    if not contact:
        print("WECHAT_TOOL_CONTACT is required", file=sys.stderr)
        return 2

    message = values.get(
        "WECHAT_TOOL_MESSAGE",
        "hello from wechat-desktop-tool smoke",
    )
    argv = [
        "examples",
        "send-message",
        "--contact",
        contact,
        "--message",
        message,
    ]

    config = values.get("WECHAT_TOOL_CONFIG", "").strip()
    if config:
        argv.extend(["--config", config])

    if _truthy(values.get("WECHAT_TOOL_DRY_RUN")):
        argv.append("--dry-run")
    else:
        socket_path = values.get("WECHAT_TOOL_SOCKET_PATH", "").strip()
        if not socket_path and not config:
            print(
                "WECHAT_TOOL_SOCKET_PATH or WECHAT_TOOL_CONFIG is required unless "
                "WECHAT_TOOL_DRY_RUN=1 is set",
                file=sys.stderr,
            )
            return 2
        if socket_path:
            argv.extend(["--socket-path", socket_path])
        token_file = values.get("WECHAT_TOOL_TOKEN_FILE", "").strip()
        token = values.get("WECHAT_TOOL_TOKEN", "").strip()
        if token and token_file:
            print(
                "WECHAT_TOOL_TOKEN and WECHAT_TOOL_TOKEN_FILE are mutually exclusive",
                file=sys.stderr,
            )
            return 2
        if token_file:
            argv.extend(["--token-file", token_file])
        elif token:
            argv.extend(["--token", token])

    if _truthy(values.get("WECHAT_TOOL_ALLOW_SUBMIT")) or _truthy(
        values.get("WECHAT_TOOL_ALLOW_SEND")
    ):
        argv.append("--submit")
        if _truthy(values.get("WECHAT_TOOL_VERIFY_AFTER_SUBMIT")):
            argv.append("--verify-after-submit")
    if _truthy(values.get("WECHAT_TOOL_ASSUME_CURRENT_CHAT")):
        argv.append("--assume-current-chat")
    if _truthy(values.get("WECHAT_TOOL_ALLOW_FOCUS_SELECT")):
        argv.append("--allow-focus-select")

    return wechat_cli_main(argv)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
