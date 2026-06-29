"""Command line interface for macOS computer-use developer tools."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from .client import MacOSComputerUseClient
from .helper import (
    DEFAULT_HELPER_API_VERSION,
    HelperTemplateConfig,
    build_helper_template,
    doctor_helper,
    init_helper_template,
)
from .service import (
    SERVICE_REQUEST_SCHEMA,
    LocalCommandService,
    LocalServiceError,
    UnixSocketCommandService,
    UnixSocketServiceClient,
    service_envelopes_to_sse,
)


def main(argv: Sequence[str] | None = None, *, prog: str = "computer-use-macos") -> int:
    parser = argparse.ArgumentParser(prog=prog)
    subcommands = parser.add_subparsers(dest="command")

    helper = subcommands.add_parser("helper", help="helper app lifecycle tools")
    helper_subcommands = helper.add_subparsers(dest="helper_command")
    _add_helper_init_parser(helper_subcommands)
    _add_helper_build_parser(helper_subcommands)
    _add_helper_doctor_parser(helper_subcommands)
    _add_helper_doctor_parser(subcommands, name="doctor")
    _add_serve_parser(subcommands)
    _add_request_parser(subcommands)

    args = parser.parse_args(argv)
    if args.command == "helper" and args.helper_command == "init":
        result = init_helper_template(
            args.output_dir,
            config=HelperTemplateConfig(
                name=args.name,
                bundle_id=args.bundle_id,
                team_id=args.team_id,
            ),
            force=args.force,
        )
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"created helper template: {result.output_dir}")
            for path in result.files:
                print(f"- {path}")
        return 0

    if args.command == "helper" and args.helper_command == "build":
        app_path = build_helper_template(args.template_dir, build_dir=args.build_dir)
        if args.json:
            print(json.dumps({"appPath": str(app_path)}, ensure_ascii=False, indent=2))
        else:
            print(app_path)
        return 0

    if (
        args.command == "doctor"
        or args.command == "helper"
        and args.helper_command == "doctor"
    ):
        return _run_doctor(args)

    if args.command == "serve":
        try:
            return _run_serve(args)
        except ValueError as exc:
            parser.error(str(exc))

    if args.command == "request":
        try:
            return _run_request(args)
        except (ValueError, LocalServiceError) as exc:
            parser.error(str(exc))

    parser.print_help()
    return 2


def _add_helper_init_parser(subcommands: argparse._SubParsersAction[object]) -> None:
    init = subcommands.add_parser("init", help="create a helper app template")
    init.add_argument("output_dir")
    init.add_argument("--name", required=True)
    init.add_argument("--bundle-id", required=True)
    init.add_argument("--team-id")
    init.add_argument("--force", action="store_true")
    init.add_argument("--json", action="store_true")


def _add_helper_build_parser(subcommands: argparse._SubParsersAction[object]) -> None:
    build = subcommands.add_parser("build", help="build a helper app skeleton")
    build.add_argument("template_dir")
    build.add_argument("--build-dir")
    build.add_argument("--json", action="store_true")


def _add_helper_doctor_parser(
    subcommands: argparse._SubParsersAction[object],
    *,
    name: str = "doctor",
) -> None:
    doctor = subcommands.add_parser(name, help="diagnose helper app setup")
    doctor.add_argument(
        "target",
        nargs="?",
        help=(
            "helper template directory, helper manifest file, or built .app "
            "bundle. Explicit --manifest/--helper-app values take precedence."
        ),
    )
    doctor.add_argument("--manifest", dest="manifest_path")
    doctor.add_argument("--helper-app", dest="helper_app_path")
    doctor.add_argument("--expected-bundle-id")
    doctor.add_argument(
        "--expected-api-version",
        default=DEFAULT_HELPER_API_VERSION,
    )
    doctor.add_argument("--auto-launch", action="store_true")
    doctor.add_argument("--verify-signature", action="store_true")
    doctor.add_argument("--verify-notarization", action="store_true")
    doctor.add_argument("--json", action="store_true")


def _add_serve_parser(subcommands: argparse._SubParsersAction[object]) -> None:
    serve = subcommands.add_parser(
        "serve",
        help="serve app-control commands over a local Unix socket",
    )
    serve.add_argument("--config")
    serve.add_argument("--socket-path")
    serve.add_argument("--token")
    serve.add_argument("--token-file")
    serve.add_argument(
        "--allow-unauthenticated",
        action="store_true",
        help="allow serving without a local token; intended only for isolated tests",
    )


def _add_request_parser(subcommands: argparse._SubParsersAction[object]) -> None:
    request = subcommands.add_parser(
        "request",
        help="send one request to a local app-control service socket",
    )
    request.add_argument("--config")
    request.add_argument("--socket-path")
    request.add_argument("--token")
    request.add_argument("--token-file")
    request.add_argument("--timeout", type=float)
    request.add_argument(
        "--action",
        choices=("run", "submit", "poll", "stream"),
        default="run",
    )
    request.add_argument("--request-id")
    request.add_argument("--command-json")
    request.add_argument("--command-file")
    request.add_argument("--command-id")
    request.add_argument("--tool", default="macos.computer_use")
    request.add_argument("--operation")
    request.add_argument("--input-json", default="{}")
    request.add_argument("--command-timeout-ms", type=int)
    request.add_argument("--sse", action="store_true")


def _run_doctor(args: argparse.Namespace) -> int:
    manifest_path, helper_app_path = _doctor_paths(args)
    report = doctor_helper(
        manifest_path=manifest_path,
        helper_app_path=helper_app_path,
        expected_bundle_id=args.expected_bundle_id,
        expected_api_version=args.expected_api_version,
        auto_launch=args.auto_launch,
        verify_signature=args.verify_signature,
        verify_notarization=args.verify_notarization,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"helper doctor: {report.status}")
        for check in report.checks:
            print(f"- {check.name}: {check.status}: {check.summary}")
    return 0 if report.ok else 1


def _doctor_paths(args: argparse.Namespace) -> tuple[str | None, str | None]:
    manifest_path = args.manifest_path
    helper_app_path = args.helper_app_path
    target = getattr(args, "target", None)
    if not target:
        return manifest_path, helper_app_path

    path = Path(target).expanduser()
    if manifest_path is None:
        inferred_manifest = _infer_doctor_manifest_path(path)
        if inferred_manifest is not None:
            manifest_path = str(inferred_manifest)
    if helper_app_path is None:
        inferred_app = _infer_doctor_helper_app_path(path)
        if inferred_app is not None:
            helper_app_path = str(inferred_app)
    return manifest_path, helper_app_path


def _infer_doctor_manifest_path(path: Path) -> Path | None:
    if path.is_dir():
        app_manifest = path / "Contents" / "Resources" / "helper_config.json"
        if app_manifest.exists():
            return app_manifest
        template_manifest = path / "helper_config.json"
        if template_manifest.exists():
            return template_manifest
    if path.is_file():
        return path
    if path.suffix == ".app":
        return None
    return path


def _infer_doctor_helper_app_path(path: Path) -> Path | None:
    if path.suffix == ".app":
        return path
    if not path.is_dir():
        return None
    matches = sorted((path / "build").glob("*.app"))
    if len(matches) == 1:
        return matches[0]
    return None


def _run_serve(args: argparse.Namespace) -> int:
    from app_control_protocol import build_logging_observer, load_app_control_config

    config = load_app_control_config(args.config)
    socket_path = _service_socket_path(args, config)
    token = _service_token(args, config)
    if token is None and not args.allow_unauthenticated:
        raise ValueError(
            "serve requires --token, --token-file, or helper.token in --config unless "
            "--allow-unauthenticated is set"
        )
    app_control = MacOSComputerUseClient.from_config(config)
    service = LocalCommandService(
        app_control,
        token=token,
        observer=build_logging_observer(config),
    )
    server = UnixSocketCommandService(socket_path, service)
    try:
        print(f"serving app-control commands on {server.socket_path}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


def _run_request(args: argparse.Namespace) -> int:
    from app_control_protocol import load_app_control_config

    config = load_app_control_config(args.config) if args.config else None
    token = _service_token(args, config)
    client = UnixSocketServiceClient(
        _service_socket_path(args, config),
        token=token,
        timeout=_service_timeout(args, config),
    )
    responses = client.request(_request_payload(args))
    if args.sse:
        for frame in service_envelopes_to_sse(responses):
            print(frame, end="")
    else:
        for response in responses:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    return 0 if responses and responses[-1].get("success") is True else 1


def _service_socket_path(args: argparse.Namespace, config: Any | None) -> str:
    if args.socket_path:
        return str(args.socket_path)
    helper = getattr(config, "helper", None)
    endpoint = getattr(helper, "endpoint", None)
    if endpoint:
        transport = getattr(helper, "transport", "unix_socket")
        if transport != "unix_socket":
            raise ValueError(
                "local service CLI requires helper.transport='unix_socket' when "
                "using helper.endpoint from --config"
            )
        return str(endpoint)
    raise ValueError(
        "--socket-path or helper.endpoint in --config is required for local service"
    )


def _service_token(args: argparse.Namespace, config: Any | None = None) -> str | None:
    if args.token and args.token_file:
        raise ValueError("--token and --token-file are mutually exclusive")
    if args.token_file:
        token = Path(args.token_file).expanduser().read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError("--token-file must contain a non-empty token")
        return token
    if args.token is None:
        helper = getattr(config, "helper", None)
        token = getattr(helper, "token", None)
        if token is None:
            return None
        token = str(token).strip()
        if not token:
            return None
        return token
    token = args.token.strip()
    if not token:
        raise ValueError("--token must be non-empty")
    return token


def _service_timeout(args: argparse.Namespace, config: Any | None = None) -> float:
    if args.timeout is not None:
        return args.timeout
    computer_use = getattr(config, "computer_use", None)
    timeout_ms = getattr(computer_use, "timeout_ms", None)
    if timeout_ms is None:
        return 30.0
    return timeout_ms / 1000.0


def _request_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": SERVICE_REQUEST_SCHEMA,
        "action": args.action,
    }
    if args.request_id:
        payload["requestId"] = args.request_id
    if args.action == "poll":
        if not args.request_id:
            raise ValueError("request --action poll requires --request-id")
        return payload
    payload["command"] = _command_payload(args)
    return payload


def _command_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.command_json and args.command_file:
        raise ValueError("--command-json and --command-file are mutually exclusive")
    if args.command_json:
        return _json_object(args.command_json, "--command-json")
    if args.command_file:
        return _json_object(
            Path(args.command_file).expanduser().read_text(encoding="utf-8"),
            "--command-file",
        )
    if not args.operation:
        raise ValueError("request requires --operation, --command-json, or --command-file")
    command: dict[str, Any] = {
        "schema": "app_control.command.v1",
        "commandId": args.command_id or "cmd_" + uuid4().hex,
        "tool": args.tool,
        "operation": args.operation,
        "input": _json_object(args.input_json, "--input-json"),
    }
    if args.command_timeout_ms is not None:
        command["timeoutMs"] = args.command_timeout_ms
    return command


def _json_object(raw: str, source: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{source} must be a JSON object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
