"""Helper app doctor checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..commands import CommandRunner, SubprocessCommandRunner
from ..models import JsonValue

from .discovery import discover_helper_manifest
from .launcher import launch_helper_app
from .manifest import DEFAULT_HELPER_API_VERSION, HelperManifestIdentityError


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    summary: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class HelperDoctorReport:
    status: str
    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        return self.status in {"ready", "warning"}

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }


def doctor_helper(
    *,
    manifest_path: str | Path | None = None,
    helper_app_path: str | Path | None = None,
    expected_bundle_id: str | None = None,
    expected_api_version: str | None = DEFAULT_HELPER_API_VERSION,
    auto_launch: bool = False,
    verify_signature: bool = False,
    verify_notarization: bool = False,
    launcher_runner: CommandRunner | None = None,
    verification_runner: CommandRunner | None = None,
) -> HelperDoctorReport:
    checks: list[DoctorCheck] = []
    discovery = discover_helper_manifest(manifest_path)
    if discovery.found and discovery.manifest is not None:
        checks.append(
            DoctorCheck(
                name="manifest",
                status="ok",
                summary=discovery.summary,
                metadata={"manifestPath": str(discovery.manifest_path)},
            )
        )
        try:
            discovery.manifest.validate_identity(
                expected_bundle_id=expected_bundle_id,
                expected_api_version=expected_api_version,
            )
            checks.append(
                DoctorCheck(
                    name="identity",
                    status="ok",
                    summary="helper manifest identity matches expectations",
                    metadata={
                        "bundleId": discovery.manifest.bundle_id,
                        "apiVersion": discovery.manifest.api_version,
                    },
                )
            )
        except HelperManifestIdentityError as exc:
            checks.append(
                DoctorCheck(
                    name="identity",
                    status="failed",
                    summary=str(exc),
                )
            )
        _append_endpoint_check(checks, discovery.manifest)
        _append_token_check(checks, discovery.manifest)
    else:
        checks.append(
            DoctorCheck(
                name="manifest",
                status="failed",
                summary=discovery.summary,
                metadata=(
                    {"manifestPath": str(discovery.manifest_path)}
                    if discovery.manifest_path is not None
                    else {}
                ),
            )
        )

    if helper_app_path is not None:
        _append_helper_app_check(
            checks,
            helper_app_path,
            auto_launch=auto_launch,
            verify_signature=verify_signature,
            verify_notarization=verify_notarization,
            launcher_runner=launcher_runner,
            verification_runner=verification_runner,
        )
    elif verify_signature or verify_notarization:
        checks.append(
            DoctorCheck(
                name="helper_app",
                status="failed",
                summary="helper app path is required for release verification",
            )
        )

    return HelperDoctorReport(status=_overall_status(checks), checks=tuple(checks))


def _append_endpoint_check(checks: list[DoctorCheck], manifest: object) -> None:
    endpoint = getattr(manifest, "endpoint", None)
    socket_path = getattr(manifest, "socket_path", None)
    if endpoint or socket_path:
        checks.append(
            DoctorCheck(
                name="endpoint",
                status="ok",
                summary="helper endpoint is configured",
                metadata={
                    **({"endpoint": endpoint} if endpoint else {}),
                    **({"socketPath": socket_path} if socket_path else {}),
                },
            )
        )
        return
    checks.append(
        DoctorCheck(
            name="endpoint",
            status="warning",
            summary="helper manifest does not expose an endpoint or socket path",
        )
    )


def _append_token_check(checks: list[DoctorCheck], manifest: object) -> None:
    try:
        token = getattr(manifest, "read_token")()
    except OSError as exc:
        checks.append(
            DoctorCheck(
                name="token",
                status="failed",
                summary=f"helper token is unavailable: {exc}",
            )
        )
        return
    if token:
        checks.append(
            DoctorCheck(
                name="token",
                status="ok",
                summary="helper token is available",
            )
        )
        return
    checks.append(
        DoctorCheck(
            name="token",
            status="warning",
            summary="helper manifest does not include a local token",
        )
    )


def _append_helper_app_check(
    checks: list[DoctorCheck],
    helper_app_path: str | Path,
    *,
    auto_launch: bool,
    verify_signature: bool,
    verify_notarization: bool,
    launcher_runner: CommandRunner | None,
    verification_runner: CommandRunner | None,
) -> None:
    app_path = Path(helper_app_path).expanduser()
    if not app_path.exists():
        checks.append(
            DoctorCheck(
                name="helper_app",
                status="failed",
                summary=f"helper app not found: {app_path}",
                metadata={"appPath": str(app_path)},
            )
        )
        return
    checks.append(
        DoctorCheck(
            name="helper_app",
            status="ok",
            summary="helper app exists",
            metadata={"appPath": str(app_path)},
        )
    )
    if auto_launch:
        launch = launch_helper_app(app_path, runner=launcher_runner)
        checks.append(
            DoctorCheck(
                name="launch",
                status="ok" if launch.launched else "failed",
                summary=launch.summary,
                metadata=launch.to_dict(),
            )
        )
    if verify_signature:
        _append_command_check(
            checks,
            name="signature",
            args=(
                "codesign",
                "--verify",
                "--deep",
                "--strict",
                "--verbose=2",
                str(app_path),
            ),
            ok_summary="helper app code signature verifies",
            fail_summary="helper app code signature verification failed",
            runner=verification_runner,
        )
    if verify_notarization:
        _append_command_check(
            checks,
            name="notarization",
            args=(
                "spctl",
                "--assess",
                "--type",
                "execute",
                "--verbose=4",
                str(app_path),
            ),
            ok_summary="helper app passes Gatekeeper assessment",
            fail_summary="helper app Gatekeeper/notarization assessment failed",
            runner=verification_runner,
        )


def _append_command_check(
    checks: list[DoctorCheck],
    *,
    name: str,
    args: tuple[str, ...],
    ok_summary: str,
    fail_summary: str,
    runner: CommandRunner | None,
) -> None:
    command_runner = runner or SubprocessCommandRunner()
    result = command_runner.run(args, timeout=30.0)
    metadata: dict[str, JsonValue] = {
        "args": list(args),
        "returncode": result.returncode,
    }
    if result.stdout:
        metadata["stdout"] = _bounded(result.stdout)
    if result.stderr:
        metadata["stderr"] = _bounded(result.stderr)
    checks.append(
        DoctorCheck(
            name=name,
            status="ok" if result.returncode == 0 else "failed",
            summary=ok_summary if result.returncode == 0 else fail_summary,
            metadata=metadata,
        )
    )


def _bounded(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


def _overall_status(checks: list[DoctorCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "failed"
    if any(check.status == "warning" for check in checks):
        return "warning"
    return "ready"
