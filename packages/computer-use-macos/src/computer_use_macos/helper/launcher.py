"""Helper app launcher."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..commands import CommandRunner, SubprocessCommandRunner


@dataclass(frozen=True)
class HelperLaunchResult:
    status: str
    app_path: Path
    launched: bool
    summary: str
    stderr: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "appPath": str(self.app_path),
            "launched": self.launched,
            "summary": self.summary,
            **({"stderr": self.stderr} if self.stderr else {}),
        }


def launch_helper_app(
    app_path: str | Path,
    *,
    runner: CommandRunner | None = None,
    timeout: float = 10.0,
) -> HelperLaunchResult:
    path = Path(app_path).expanduser()
    if not path.exists():
        return HelperLaunchResult(
            status="missing",
            app_path=path,
            launched=False,
            summary=f"helper app not found: {path}",
        )
    command_runner = runner or SubprocessCommandRunner()
    result = command_runner.run(["open", str(path)], timeout=timeout)
    if result.returncode != 0:
        return HelperLaunchResult(
            status="failed",
            app_path=path,
            launched=False,
            summary="helper app launch failed",
            stderr=result.stderr,
        )
    return HelperLaunchResult(
        status="launched",
        app_path=path,
        launched=True,
        summary="helper app launch requested",
    )
