"""Manual TextEdit smoke for the ``computer-use-macos`` package.

Run with ``COMPUTER_USE_DRY_RUN=1`` to verify the installed entrypoint without
touching the desktop.
"""

from __future__ import annotations

from collections.abc import Sequence
import json
import os
import time
from typing import Any

from app_control_protocol import ToolCommand

from computer_use_macos import (
    ComputerUseClient,
    focus_app_command,
    observe_command,
    open_app_command,
    readiness_command,
    type_text_command,
)

DEFAULT_APP = "TextEdit"
DEFAULT_MESSAGE = "hello from computer-use-macos"
DEFAULT_FRONTMOST_RETRY_ATTEMPTS = 3
DEFAULT_FRONTMOST_RETRY_DELAY_SECONDS = 0.75


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    app = os.environ.get("COMPUTER_USE_TEXTEDIT_APP", DEFAULT_APP).strip() or DEFAULT_APP
    message = (
        os.environ.get("COMPUTER_USE_TEXTEDIT_MESSAGE", DEFAULT_MESSAGE).strip()
        or DEFAULT_MESSAGE
    )
    config_path = os.environ.get("COMPUTER_USE_CONFIG")
    commands = _commands(app=app, message=message)
    retry_attempts = _env_int(
        "COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS",
        DEFAULT_FRONTMOST_RETRY_ATTEMPTS,
    )
    retry_delay = _env_float(
        "COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS",
        DEFAULT_FRONTMOST_RETRY_DELAY_SECONDS,
    )

    if _env_flag("COMPUTER_USE_DRY_RUN"):
        print(
            json.dumps(
                {
                    "dryRun": True,
                    "app": app,
                    "configPath": config_path,
                    "commands": [command.to_dict() for command in commands],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    client = _client(config_path=config_path, app=app)
    observations: list[dict[str, Any]] = []
    retry_observations: list[dict[str, Any]] = []
    success = True
    failed_observation: dict[str, Any] | None = None
    for command in commands:
        observation = _run_with_frontmost_retries(
            client,
            command,
            focus_command=commands[2],
            app=app,
            attempts=retry_attempts,
            delay_seconds=retry_delay,
            retry_observations=retry_observations,
        )
        observation_payload = observation.to_dict()
        observations.append(observation_payload)
        success = success and bool(observation.success)
        if not observation.success:
            failed_observation = observation_payload
            break

    report: dict[str, Any] = {
        "dryRun": False,
        "success": success,
        "app": app,
        "configPath": config_path,
        "observations": observations,
    }
    if retry_observations:
        report["retryObservations"] = retry_observations
    if failed_observation is not None:
        report.update(_failure_report(failed_observation))

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if success else 1


def _client(*, config_path: str | None, app: str) -> Any:
    if config_path:
        return ComputerUseClient.from_config(config_path)
    return ComputerUseClient(allowed_apps=(app,))


def _commands(*, app: str, message: str) -> list[ToolCommand]:
    return [
        readiness_command(
            command_id="cmd_textedit_readiness",
            timeout_ms=5_000,
        ),
        open_app_command(
            app,
            command_id="cmd_textedit_open",
            timeout_ms=10_000,
        ),
        focus_app_command(
            app,
            command_id="cmd_textedit_focus",
            timeout_ms=10_000,
        ),
        observe_command(
            target_app=app,
            command_id="cmd_textedit_observe",
            timeout_ms=5_000,
        ),
        type_text_command(
            message,
            target_app=app,
            command_id="cmd_textedit_type",
            timeout_ms=5_000,
        ),
    ]


def _run_with_frontmost_retries(
    client: Any,
    command: ToolCommand,
    *,
    focus_command: ToolCommand,
    app: str,
    attempts: int,
    delay_seconds: float,
    retry_observations: list[dict[str, Any]],
) -> Any:
    observation = client.run_command(command)
    if command.operation not in {"observe", "type_text"}:
        return observation

    attempt = 1
    while (
        not observation.success
        and attempt < attempts
        and _should_retry_frontmost(observation, app=app)
    ):
        retry_observations.append(
            {
                "attempt": attempt,
                "command": command.operation,
                "observation": observation.to_dict(),
            }
        )
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        focus_retry = _retry_focus_command(focus_command, attempt=attempt)
        focus_observation = client.run_command(focus_retry)
        retry_observations.append(
            {
                "attempt": attempt,
                "command": "focus_app",
                "observation": focus_observation.to_dict(),
            }
        )
        if not focus_observation.success:
            return focus_observation
        observation = client.run_command(command)
        attempt += 1
    return observation


def _retry_focus_command(command: ToolCommand, *, attempt: int) -> ToolCommand:
    return ToolCommand(
        command_id=f"{command.command_id}_retry_{attempt}",
        tool=command.tool,
        operation=command.operation,
        input=dict(command.input),
        timeout_ms=command.timeout_ms,
        idempotency_key=command.idempotency_key,
        metadata={**dict(command.metadata), "retryAttempt": attempt},
    )


def _should_retry_frontmost(observation: Any, *, app: str) -> bool:
    payload = observation.to_dict()
    if _action_attempted(payload):
        return False
    summary = str(payload.get("summary") or payload.get("message") or "").lower()
    if "frontmost" in summary and app.lower() in summary:
        return True
    nested = payload.get("observation")
    if not isinstance(nested, dict):
        return False
    if nested.get("frontmostApp") and nested.get("frontmostApp") != app:
        return True
    metadata = nested.get("metadata")
    return (
        isinstance(metadata, dict)
        and isinstance(metadata.get("frontmost_app"), str)
        and metadata.get("frontmost_app") != app
    )


def _action_attempted(payload: dict[str, Any]) -> bool:
    nested = payload.get("observation")
    if not isinstance(nested, dict):
        return False
    if nested.get("actionAttempted") is True:
        return True
    metadata = nested.get("metadata")
    return isinstance(metadata, dict) and metadata.get("action_attempted") is True


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


def _failure_report(observation: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {
        "failedCommandId": observation.get("commandId"),
        "failurePhase": observation.get("operation"),
        "failureStatus": observation.get("status"),
        "failureSummary": observation.get("summary"),
    }
    failure_kind = observation.get("failureKind")
    if isinstance(failure_kind, str) and failure_kind:
        details["failureKind"] = failure_kind
    nested = observation.get("observation")
    if isinstance(nested, dict):
        metadata = nested.get("metadata")
        if isinstance(metadata, dict):
            _copy_string(metadata, details, "frontmost_app", "frontmostApp")
            _copy_string(
                metadata,
                details,
                "frontmost_bundle_id",
                "frontmostBundleId",
            )
            _copy_string(metadata, details, "window_title", "windowTitle")
    return details


def _copy_string(
    source: dict[str, Any],
    target: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    value = source.get(source_key)
    if isinstance(value, str) and value:
        target[target_key] = value


if __name__ == "__main__":
    raise SystemExit(main())
