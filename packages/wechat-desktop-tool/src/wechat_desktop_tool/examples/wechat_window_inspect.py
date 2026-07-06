"""Manual WeChat window inspection example for wechat-desktop-tool."""

from __future__ import annotations

from collections.abc import Mapping
import os
import sys

from wechat_desktop_tool.cli import main as wechat_cli_main


DEFAULT_OUTPUT = "./wechat-window-inspect.json"


def main(env: Mapping[str, str] | None = None) -> int:
    values = os.environ if env is None else env
    output = values.get("WECHAT_TOOL_OUTPUT", "").strip() or DEFAULT_OUTPUT
    argv = [
        "examples",
        "inspect-window",
        "--output",
        output,
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

    if _truthy(values.get("WECHAT_TOOL_INCLUDE_RAW")):
        argv.append("--include-raw")
    if _falsey(values.get("WECHAT_TOOL_INCLUDE_ACTIONABLES")):
        argv.append("--no-actionables")

    return wechat_cli_main(argv)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _falsey(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no", "off"}


if __name__ == "__main__":
    raise SystemExit(main())
