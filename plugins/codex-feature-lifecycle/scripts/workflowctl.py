#!/usr/bin/env python3
"""Local configuration and dispatch state for Codex Feature Lifecycle.

This module deliberately does not call Codex or GitHub APIs. Skills use host
tools for external actions and call this script for deterministic identity,
validation, idempotency, and atomic persistence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = 1
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
REPO_KEY_RE = re.compile(r"^[0-9a-f]{24}$")
FINDING_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,63}$")
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 30.0
MERGE_METHODS = {"squash", "merge", "rebase"}
DECISIONS = {"APPROVE", "COMMENT", "REQUEST_CHANGES", "STALE", "FAILED"}
MERGE_STATUSES = {
    "NOT_ATTEMPTED",
    "NOT_AUTHORIZED",
    "DEFERRED",
    "MERGED",
    "FAILED",
}
SEVERITIES = {"blocker", "high", "medium", "low"}
DECISION_MERGE_STATUSES = {
    "APPROVE": {"NOT_AUTHORIZED", "DEFERRED", "MERGED", "FAILED"},
    "COMMENT": {"NOT_ATTEMPTED"},
    "REQUEST_CHANGES": {"NOT_ATTEMPTED"},
    "STALE": {"NOT_ATTEMPTED"},
    "FAILED": {"NOT_ATTEMPTED"},
}


class WorkflowError(RuntimeError):
    """A safe, user-actionable workflow failure."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_rfc3339(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise WorkflowError("invalid_payload", f"{field} must be an RFC 3339 UTC timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise WorkflowError("invalid_payload", f"{field} must be an RFC 3339 UTC timestamp") from exc
    return value


def require_string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise WorkflowError("invalid_payload", f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise WorkflowError("invalid_payload", f"{field} must not be empty")
    return value


def require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise WorkflowError("invalid_payload", f"{field} must be a boolean")
    return value


def require_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkflowError("invalid_payload", f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise WorkflowError("invalid_payload", f"{field} must be at least {minimum}")
    return value


def require_exact_keys(value: Any, field: str, required: Iterable[str], optional: Iterable[str] = ()) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("invalid_payload", f"{field} must be an object")
    required_set = set(required)
    optional_set = set(optional)
    keys = set(value)
    missing = sorted(required_set - keys)
    extra = sorted(keys - required_set - optional_set)
    if missing:
        raise WorkflowError("invalid_payload", f"{field} is missing required fields: {', '.join(missing)}")
    if extra:
        raise WorkflowError("invalid_payload", f"{field} has unsupported fields: {', '.join(extra)}")
    return value


def require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise WorkflowError("invalid_payload", f"{field} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(require_string(item, f"{field}[{index}]"))
    return result


def require_uuid(value: Any, field: str) -> str:
    text = require_string(value, field)
    try:
        parsed = uuid.UUID(text)
    except ValueError as exc:
        raise WorkflowError("invalid_payload", f"{field} must be a UUID") from exc
    if str(parsed) != text.lower():
        raise WorkflowError("invalid_payload", f"{field} must use canonical UUID form")
    return text


def require_sha(value: Any, field: str) -> str:
    text = require_string(value, field)
    if not SHA_RE.fullmatch(text):
        raise WorkflowError("invalid_payload", f"{field} must be a lowercase full 40-character git SHA")
    return text


def require_https_url(value: Any, field: str) -> str:
    text = require_string(value, field)
    parsed = urlsplit(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise WorkflowError("invalid_payload", f"{field} must be an HTTPS URL without credentials")
    return text


def canonical_repo_root(repo_root: str | os.PathLike[str]) -> Path:
    requested = Path(repo_root).expanduser().resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(requested), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise WorkflowError("not_git_repository", f"Not a git repository: {requested}") from exc
    return Path(result.stdout.strip()).resolve()


def discover_origin(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise WorkflowError("missing_origin", "The repository must have an origin remote") from exc
    return sanitize_origin(result.stdout.strip())


def sanitize_origin(origin: str) -> str:
    """Return a stable remote identity without credentials, query, or fragment."""

    raw = require_string(origin, "origin").strip()
    if "://" in raw:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() == "file":
            return f"file://{Path(parsed.path).expanduser().resolve()}"
        host = (parsed.hostname or "").lower()
        if not host:
            raise WorkflowError("invalid_origin", "Origin URL must include a host")
        port = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return urlunsplit((parsed.scheme.lower(), host + port, path, "", ""))

    scp_match = re.fullmatch(r"(?:[^@/:]+@)?([^/:]+):(.+)", raw)
    if scp_match and not re.fullmatch(r"[A-Za-z]:[\\/].*", raw):
        host, path = scp_match.groups()
        path = path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return f"ssh://{host.lower()}/{path.lstrip('/')}"

    local = Path(raw).expanduser()
    if local.exists() or raw.startswith((".", "/", "~")):
        return f"file://{local.resolve()}"
    raise WorkflowError("invalid_origin", "Origin must be a URL, scp-style git remote, or local path")


def require_github_origin(origin: str) -> str:
    sanitized = sanitize_origin(origin)
    parsed = urlsplit(sanitized)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.hostname != "github.com" or len(parts) != 2:
        raise WorkflowError("unsupported_repository", "Codex Feature Lifecycle 0.1 supports github.com repositories only")
    return sanitized


def github_pull_request_url(origin: str, number: int) -> str:
    parsed = urlsplit(require_github_origin(origin))
    owner, repository = [part for part in parsed.path.split("/") if part]
    return f"https://github.com/{owner}/{repository}/pull/{number}"


def repository_key(repo_root: Path, sanitized_origin: str) -> str:
    material = f"{repo_root}\n{sanitized_origin}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:24]


def codex_state_root() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".codex").resolve()


def workflow_paths(repo_root: Path, origin: str) -> dict[str, Path | str]:
    key = repository_key(repo_root, origin)
    directory = codex_state_root() / "feature-lifecycle" / "projects" / key
    return {
        "key": key,
        "directory": directory,
        "config": directory / "config.json",
        "state": directory / "state.json",
        "lock": directory / ".state.lock",
    }


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    ensure_private_directory(path.parent)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json(path: Path, *, code: str = "missing_file") -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise WorkflowError(code, f"Required workflow file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError("invalid_json", f"Cannot read valid JSON from: {path}") from exc
    if not isinstance(value, dict):
        raise WorkflowError("invalid_json", f"Expected a JSON object in: {path}")
    return value


class StateLock:
    def __init__(self, path: Path):
        self.path = path
        self.acquired = False

    def __enter__(self) -> "StateLock":
        ensure_private_directory(self.path.parent)
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                payload = json.dumps({"pid": os.getpid(), "createdAt": utc_now()}).encode("utf-8")
                os.write(fd, payload)
                os.close(fd)
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > STALE_LOCK_SECONDS:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise WorkflowError("lock_timeout", "Timed out waiting for workflow state lock")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def digest_json(value: Mapping[str, Any] | Sequence[Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_config(config: Any, *, expected_root: Path | None = None, expected_origin: str | None = None) -> dict[str, Any]:
    value = require_exact_keys(
        config,
        "config",
        {
            "schemaVersion",
            "workflowId",
            "repository",
            "projectId",
            "threads",
            "policy",
            "createdAt",
            "updatedAt",
        },
        {"hostId"},
    )
    if require_int(value["schemaVersion"], "config.schemaVersion") != SCHEMA_VERSION:
        raise WorkflowError("unsupported_schema", "Unsupported configuration schema version")
    require_uuid(value["workflowId"], "config.workflowId")
    repository = require_exact_keys(value["repository"], "config.repository", {"root", "origin", "key"})
    root = Path(require_string(repository["root"], "config.repository.root")).resolve()
    origin = require_github_origin(require_string(repository["origin"], "config.repository.origin"))
    key = require_string(repository["key"], "config.repository.key")
    if not REPO_KEY_RE.fullmatch(key) or key != repository_key(root, origin):
        raise WorkflowError("repository_mismatch", "Configured repository key does not match root and origin")
    if expected_root is not None and root != expected_root:
        raise WorkflowError("repository_mismatch", "Configuration belongs to a different repository root")
    if expected_origin is not None and origin != expected_origin:
        raise WorkflowError("repository_mismatch", "Configuration belongs to a different origin remote")
    require_string(value["projectId"], "config.projectId")
    if "hostId" in value:
        require_string(value["hostId"], "config.hostId")
    threads = require_exact_keys(value["threads"], "config.threads", {"main", "reviewer"})
    main_id = require_string(threads["main"], "config.threads.main")
    reviewer_id = require_string(threads["reviewer"], "config.threads.reviewer")
    if main_id == reviewer_id:
        raise WorkflowError("invalid_config", "Main and reviewer task IDs must differ")
    policy = require_exact_keys(
        value["policy"],
        "config.policy",
        {"mergeOnApprove", "mergeMethod", "deleteBranch", "requireGreenChecks", "requireExactHead"},
    )
    require_bool(policy["mergeOnApprove"], "config.policy.mergeOnApprove")
    if require_string(policy["mergeMethod"], "config.policy.mergeMethod") not in MERGE_METHODS:
        raise WorkflowError("invalid_config", "Unsupported merge method")
    require_bool(policy["deleteBranch"], "config.policy.deleteBranch")
    if require_bool(policy["requireGreenChecks"], "config.policy.requireGreenChecks") is not True:
        raise WorkflowError("invalid_config", "Green checks are mandatory in schema version 1")
    if require_bool(policy["requireExactHead"], "config.policy.requireExactHead") is not True:
        raise WorkflowError("invalid_config", "Exact-head verification is mandatory in schema version 1")
    parse_rfc3339(value["createdAt"], "config.createdAt")
    parse_rfc3339(value["updatedAt"], "config.updatedAt")
    return value


def initial_state(workflow_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "workflowId": workflow_id,
        "dispatches": {},
        "updatedAt": utc_now(),
    }


def validate_dispatch_record(dispatch_id: str, record: Any) -> dict[str, Any]:
    if not HEX_64_RE.fullmatch(dispatch_id):
        raise WorkflowError("invalid_state", "State contains an invalid dispatch ID")
    value = require_exact_keys(
        record,
        f"state.dispatches.{dispatch_id}",
        {
            "pullRequestNumber",
            "pullRequestUrl",
            "baseSha",
            "headSha",
            "branch",
            "sourceThreadId",
            "destinationThreadId",
            "requestCreatedAt",
            "requestDigest",
            "status",
            "preparedAt",
        },
        {
            "dispatchedAt",
            "deliveryFailedAt",
            "deliveryError",
            "reviewingAt",
            "decision",
            "mergeStatus",
            "resultDigest",
            "resultCreatedAt",
            "resultPreparedAt",
            "resultAcceptedAt",
            "cancelledAt",
            "cancelReason",
        },
    )
    field = f"state.dispatches.{dispatch_id}"
    require_int(value["pullRequestNumber"], f"{field}.pullRequestNumber", minimum=1)
    require_https_url(value["pullRequestUrl"], f"{field}.pullRequestUrl")
    require_sha(value["baseSha"], f"{field}.baseSha")
    require_sha(value["headSha"], f"{field}.headSha")
    for name in ("branch", "sourceThreadId", "destinationThreadId"):
        require_string(value[name], f"{field}.{name}")
    if value["sourceThreadId"] == value["destinationThreadId"]:
        raise WorkflowError("invalid_state", f"{field} routes must use different task IDs")
    parse_rfc3339(value["requestCreatedAt"], f"{field}.requestCreatedAt")
    if not HEX_64_RE.fullmatch(require_string(value["requestDigest"], f"{field}.requestDigest")):
        raise WorkflowError("invalid_state", f"{field}.requestDigest must be 64 lowercase hex characters")
    status = require_string(value["status"], f"{field}.status")
    statuses = {
        "prepared",
        "delivery_failed",
        "dispatched",
        "reviewing",
        "merge_ready",
        "merged",
        "comment",
        "changes_requested",
        "stale",
        "failed",
        "cancelled",
    }
    if status not in statuses:
        raise WorkflowError("invalid_state", f"{field}.status is unsupported")
    timestamp_fields = (
        "preparedAt",
        "dispatchedAt",
        "deliveryFailedAt",
        "reviewingAt",
        "resultCreatedAt",
        "resultPreparedAt",
        "resultAcceptedAt",
        "cancelledAt",
    )
    for name in timestamp_fields:
        if name in value:
            parse_rfc3339(value[name], f"{field}.{name}")
    for name in ("deliveryError", "cancelReason"):
        if name in value:
            require_string(value[name], f"{field}.{name}")
    if "resultDigest" in value and not HEX_64_RE.fullmatch(
        require_string(value["resultDigest"], f"{field}.resultDigest")
    ):
        raise WorkflowError("invalid_state", f"{field}.resultDigest must be 64 lowercase hex characters")
    if "decision" in value and require_string(value["decision"], f"{field}.decision") not in DECISIONS:
        raise WorkflowError("invalid_state", f"{field}.decision is unsupported")
    if "mergeStatus" in value and require_string(value["mergeStatus"], f"{field}.mergeStatus") not in MERGE_STATUSES:
        raise WorkflowError("invalid_state", f"{field}.mergeStatus is unsupported")
    terminal_statuses = {"merge_ready", "merged", "comment", "changes_requested", "stale", "failed"}
    if status in terminal_statuses:
        for name in ("decision", "mergeStatus", "resultDigest", "resultCreatedAt", "resultPreparedAt"):
            if name not in value:
                raise WorkflowError("invalid_state", f"{field}.{name} is required for terminal result state")
    if status == "delivery_failed" and not {"deliveryFailedAt", "deliveryError"}.issubset(value):
        raise WorkflowError("invalid_state", f"{field} delivery failure metadata is incomplete")
    if status == "cancelled" and not {"cancelledAt", "cancelReason"}.issubset(value):
        raise WorkflowError("invalid_state", f"{field} cancellation metadata is incomplete")
    return value


def validate_state(state: Any, config: Mapping[str, Any]) -> dict[str, Any]:
    value = require_exact_keys(state, "state", {"schemaVersion", "workflowId", "dispatches", "updatedAt"})
    if require_int(value["schemaVersion"], "state.schemaVersion") != SCHEMA_VERSION:
        raise WorkflowError("unsupported_schema", "Unsupported state schema version")
    workflow_id = require_uuid(value["workflowId"], "state.workflowId")
    if workflow_id != config["workflowId"]:
        raise WorkflowError("state_mismatch", "State workflow ID does not match configuration")
    if not isinstance(value["dispatches"], dict):
        raise WorkflowError("invalid_state", "state.dispatches must be an object")
    for dispatch_id, record in value["dispatches"].items():
        validate_dispatch_record(dispatch_id, record)
    parse_rfc3339(value["updatedAt"], "state.updatedAt")
    return value


def load_context(repo_root_arg: str) -> tuple[Path, str, dict[str, Path | str], dict[str, Any], dict[str, Any]]:
    root = canonical_repo_root(repo_root_arg)
    origin = require_github_origin(discover_origin(root))
    paths = workflow_paths(root, origin)
    config = validate_config(read_json(paths["config"], code="not_initialized"), expected_root=root, expected_origin=origin)  # type: ignore[arg-type]
    state_path = paths["state"]
    state = read_json(state_path, code="missing_state") if Path(state_path).exists() else initial_state(config["workflowId"])
    return root, origin, paths, config, validate_state(state, config)


def validate_review_request(value: Any) -> dict[str, Any]:
    request = require_exact_keys(
        value,
        "ReviewRequest",
        {
            "schemaVersion",
            "messageType",
            "workflowId",
            "dispatchId",
            "repository",
            "pullRequest",
            "routes",
            "mergePolicy",
            "evidence",
            "checks",
            "limitations",
            "createdAt",
        },
    )
    if require_int(request["schemaVersion"], "ReviewRequest.schemaVersion") != SCHEMA_VERSION:
        raise WorkflowError("unsupported_schema", "Unsupported ReviewRequest schema version")
    if request["messageType"] != "ReviewRequest":
        raise WorkflowError("invalid_payload", "ReviewRequest.messageType must be ReviewRequest")
    require_uuid(request["workflowId"], "ReviewRequest.workflowId")
    dispatch_id = require_string(request["dispatchId"], "ReviewRequest.dispatchId")
    if not HEX_64_RE.fullmatch(dispatch_id):
        raise WorkflowError("invalid_payload", "ReviewRequest.dispatchId must be 64 lowercase hex characters")
    repository = require_exact_keys(request["repository"], "ReviewRequest.repository", {"key", "origin"})
    if not REPO_KEY_RE.fullmatch(require_string(repository["key"], "ReviewRequest.repository.key")):
        raise WorkflowError("invalid_payload", "ReviewRequest.repository.key must be 24 lowercase hex characters")
    require_github_origin(require_string(repository["origin"], "ReviewRequest.repository.origin"))
    pull_request = require_exact_keys(
        request["pullRequest"],
        "ReviewRequest.pullRequest",
        {"number", "url", "baseSha", "headSha", "branch"},
    )
    require_int(pull_request["number"], "ReviewRequest.pullRequest.number", minimum=1)
    require_https_url(pull_request["url"], "ReviewRequest.pullRequest.url")
    require_sha(pull_request["baseSha"], "ReviewRequest.pullRequest.baseSha")
    require_sha(pull_request["headSha"], "ReviewRequest.pullRequest.headSha")
    require_string(pull_request["branch"], "ReviewRequest.pullRequest.branch")
    expected_pr_url = github_pull_request_url(repository["origin"], pull_request["number"])
    if pull_request["url"] != expected_pr_url:
        raise WorkflowError("repository_mismatch", "ReviewRequest PR URL does not match its repository and PR number")
    routes = require_exact_keys(request["routes"], "ReviewRequest.routes", {"sourceThreadId", "destinationThreadId"}, {"hostId"})
    source = require_string(routes["sourceThreadId"], "ReviewRequest.routes.sourceThreadId")
    destination = require_string(routes["destinationThreadId"], "ReviewRequest.routes.destinationThreadId")
    if source == destination:
        raise WorkflowError("invalid_payload", "ReviewRequest routes must use different task IDs")
    if "hostId" in routes:
        require_string(routes["hostId"], "ReviewRequest.routes.hostId")
    merge_policy = require_exact_keys(
        request["mergePolicy"],
        "ReviewRequest.mergePolicy",
        {"mergeOnApprove", "mergeMethod", "deleteBranch", "requireGreenChecks", "requireExactHead"},
    )
    require_bool(merge_policy["mergeOnApprove"], "ReviewRequest.mergePolicy.mergeOnApprove")
    if require_string(merge_policy["mergeMethod"], "ReviewRequest.mergePolicy.mergeMethod") not in MERGE_METHODS:
        raise WorkflowError("invalid_payload", "ReviewRequest merge method is unsupported")
    require_bool(merge_policy["deleteBranch"], "ReviewRequest.mergePolicy.deleteBranch")
    if require_bool(merge_policy["requireGreenChecks"], "ReviewRequest.mergePolicy.requireGreenChecks") is not True:
        raise WorkflowError("invalid_payload", "ReviewRequest must require green checks")
    if require_bool(merge_policy["requireExactHead"], "ReviewRequest.mergePolicy.requireExactHead") is not True:
        raise WorkflowError("invalid_payload", "ReviewRequest must require exact head")
    require_string_list(request["evidence"], "ReviewRequest.evidence")
    require_string_list(request["checks"], "ReviewRequest.checks")
    require_string_list(request["limitations"], "ReviewRequest.limitations")
    parse_rfc3339(request["createdAt"], "ReviewRequest.createdAt")
    return request


def validate_finding(value: Any, index: int) -> dict[str, Any]:
    field = f"ReviewResult.findings[{index}]"
    finding = require_exact_keys(
        value,
        field,
        {"id", "severity", "summary", "file", "impact", "evidence", "requiredAction"},
        {"line"},
    )
    finding_id = require_string(finding["id"], f"{field}.id")
    if not FINDING_ID_RE.fullmatch(finding_id):
        raise WorkflowError("invalid_payload", f"{field}.id has an invalid format")
    if require_string(finding["severity"], f"{field}.severity") not in SEVERITIES:
        raise WorkflowError("invalid_payload", f"{field}.severity is unsupported")
    require_string(finding["summary"], f"{field}.summary")
    require_string(finding["file"], f"{field}.file")
    if "line" in finding:
        require_int(finding["line"], f"{field}.line", minimum=1)
    require_string(finding["impact"], f"{field}.impact")
    require_string(finding["evidence"], f"{field}.evidence")
    require_string(finding["requiredAction"], f"{field}.requiredAction")
    return finding


def validate_review_result(value: Any) -> dict[str, Any]:
    result = require_exact_keys(
        value,
        "ReviewResult",
        {
            "schemaVersion",
            "messageType",
            "workflowId",
            "dispatchId",
            "reviewedSnapshot",
            "routes",
            "decision",
            "findings",
            "verification",
            "limitations",
            "merge",
            "createdAt",
        },
    )
    if require_int(result["schemaVersion"], "ReviewResult.schemaVersion") != SCHEMA_VERSION:
        raise WorkflowError("unsupported_schema", "Unsupported ReviewResult schema version")
    if result["messageType"] != "ReviewResult":
        raise WorkflowError("invalid_payload", "ReviewResult.messageType must be ReviewResult")
    require_uuid(result["workflowId"], "ReviewResult.workflowId")
    dispatch_id = require_string(result["dispatchId"], "ReviewResult.dispatchId")
    if not HEX_64_RE.fullmatch(dispatch_id):
        raise WorkflowError("invalid_payload", "ReviewResult.dispatchId must be 64 lowercase hex characters")
    snapshot = require_exact_keys(
        result["reviewedSnapshot"],
        "ReviewResult.reviewedSnapshot",
        {"repositoryKey", "pullRequestNumber", "baseSha", "headSha"},
    )
    if not REPO_KEY_RE.fullmatch(require_string(snapshot["repositoryKey"], "ReviewResult.reviewedSnapshot.repositoryKey")):
        raise WorkflowError("invalid_payload", "ReviewResult repository key has an invalid format")
    require_int(snapshot["pullRequestNumber"], "ReviewResult.reviewedSnapshot.pullRequestNumber", minimum=1)
    require_sha(snapshot["baseSha"], "ReviewResult.reviewedSnapshot.baseSha")
    require_sha(snapshot["headSha"], "ReviewResult.reviewedSnapshot.headSha")
    routes = require_exact_keys(result["routes"], "ReviewResult.routes", {"sourceThreadId", "destinationThreadId"}, {"hostId"})
    source = require_string(routes["sourceThreadId"], "ReviewResult.routes.sourceThreadId")
    destination = require_string(routes["destinationThreadId"], "ReviewResult.routes.destinationThreadId")
    if source == destination:
        raise WorkflowError("invalid_payload", "ReviewResult routes must use different task IDs")
    if "hostId" in routes:
        require_string(routes["hostId"], "ReviewResult.routes.hostId")
    decision = require_string(result["decision"], "ReviewResult.decision")
    if decision not in DECISIONS:
        raise WorkflowError("invalid_payload", "ReviewResult.decision is unsupported")
    if not isinstance(result["findings"], list):
        raise WorkflowError("invalid_payload", "ReviewResult.findings must be an array")
    findings = [validate_finding(item, index) for index, item in enumerate(result["findings"])]
    finding_ids = [item["id"] for item in findings]
    if len(finding_ids) != len(set(finding_ids)):
        raise WorkflowError("invalid_payload", "ReviewResult finding IDs must be unique")
    require_string_list(result["verification"], "ReviewResult.verification")
    require_string_list(result["limitations"], "ReviewResult.limitations")
    merge = require_exact_keys(result["merge"], "ReviewResult.merge", {"status"}, {"url", "sha", "error"})
    merge_status = require_string(merge["status"], "ReviewResult.merge.status")
    if merge_status not in MERGE_STATUSES:
        raise WorkflowError("invalid_payload", "ReviewResult.merge.status is unsupported")
    if "url" in merge:
        require_https_url(merge["url"], "ReviewResult.merge.url")
    if "sha" in merge:
        require_sha(merge["sha"], "ReviewResult.merge.sha")
    if "error" in merge:
        require_string(merge["error"], "ReviewResult.merge.error")
    parse_rfc3339(result["createdAt"], "ReviewResult.createdAt")

    blocking = [item for item in findings if item["severity"] in {"blocker", "high"}]
    if decision == "APPROVE" and blocking:
        raise WorkflowError("invalid_payload", "APPROVE cannot include blocker or high findings")
    if decision == "REQUEST_CHANGES" and not findings:
        raise WorkflowError("invalid_payload", "REQUEST_CHANGES must include at least one finding")
    if merge_status == "MERGED" and decision != "APPROVE":
        raise WorkflowError("invalid_payload", "Only an APPROVE result can report MERGED")
    if merge_status == "MERGED" and ("url" not in merge or "sha" not in merge):
        raise WorkflowError("invalid_payload", "MERGED must include the merge URL and merge SHA")
    if merge_status == "FAILED" and "error" not in merge:
        raise WorkflowError("invalid_payload", "FAILED merge status must include an error summary")
    if merge_status not in DECISION_MERGE_STATUSES[decision]:
        raise WorkflowError("invalid_payload", f"{decision} cannot use merge status {merge_status}")
    merge_keys = set(merge)
    expected_merge_keys = {
        "MERGED": {"status", "url", "sha"},
        "FAILED": {"status", "error"},
    }.get(merge_status, {"status"})
    if merge_keys != expected_merge_keys:
        raise WorkflowError(
            "invalid_payload",
            f"Merge status {merge_status} requires exactly: {', '.join(sorted(expected_merge_keys))}",
        )
    return result


def load_payload(path: str, *, expected: str) -> dict[str, Any]:
    payload = read_json(Path(path), code="missing_payload")
    if expected == "request":
        return validate_review_request(payload)
    if expected == "result":
        return validate_review_result(payload)
    raise AssertionError(expected)


def compute_dispatch_id(config: Mapping[str, Any], pr_number: int, base_sha: str, head_sha: str) -> str:
    material = "\n".join(
        [
            config["workflowId"],
            config["repository"]["key"],
            str(pr_number),
            base_sha.lower(),
            head_sha.lower(),
            config["threads"]["reviewer"],
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def expected_dispatch_metadata(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pullRequestNumber": request["pullRequest"]["number"],
        "pullRequestUrl": request["pullRequest"]["url"],
        "baseSha": request["pullRequest"]["baseSha"],
        "headSha": request["pullRequest"]["headSha"],
        "branch": request["pullRequest"]["branch"],
        "sourceThreadId": request["routes"]["sourceThreadId"],
        "destinationThreadId": request["routes"]["destinationThreadId"],
        "requestCreatedAt": request["createdAt"],
        "requestDigest": digest_json(request),
    }


def validate_request_against_config(request: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    if request["workflowId"] != config["workflowId"]:
        raise WorkflowError("route_mismatch", "ReviewRequest workflow ID does not match local config")
    if request["repository"] != {"key": config["repository"]["key"], "origin": config["repository"]["origin"]}:
        raise WorkflowError("route_mismatch", "ReviewRequest repository does not match local config")
    expected_routes = {
        "sourceThreadId": config["threads"]["main"],
        "destinationThreadId": config["threads"]["reviewer"],
    }
    if config.get("hostId"):
        expected_routes["hostId"] = config["hostId"]
    if request["routes"] != expected_routes:
        raise WorkflowError("route_mismatch", "ReviewRequest routes do not match local config")
    if request["mergePolicy"] != config["policy"]:
        raise WorkflowError("policy_mismatch", "ReviewRequest merge policy does not match local config")
    expected_pr_url = github_pull_request_url(config["repository"]["origin"], request["pullRequest"]["number"])
    if request["pullRequest"]["url"] != expected_pr_url:
        raise WorkflowError("repository_mismatch", "ReviewRequest PR URL does not match its configured GitHub repository")
    expected_id = compute_dispatch_id(
        config,
        request["pullRequest"]["number"],
        request["pullRequest"]["baseSha"],
        request["pullRequest"]["headSha"],
    )
    if request["dispatchId"] != expected_id:
        raise WorkflowError("dispatch_mismatch", "ReviewRequest dispatch ID is invalid")


def validate_request_against_dispatch(request: Mapping[str, Any], dispatch: Mapping[str, Any]) -> None:
    expected = expected_dispatch_metadata(request)
    for key, value in expected.items():
        if dispatch.get(key) != value:
            raise WorkflowError("dispatch_mismatch", f"ReviewRequest does not match stored dispatch field: {key}")


def validate_result_against_request(result: Mapping[str, Any], request: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    if result["workflowId"] != request["workflowId"] or result["dispatchId"] != request["dispatchId"]:
        raise WorkflowError("dispatch_mismatch", "ReviewResult does not match ReviewRequest")
    expected_snapshot = {
        "repositoryKey": request["repository"]["key"],
        "pullRequestNumber": request["pullRequest"]["number"],
        "baseSha": request["pullRequest"]["baseSha"],
        "headSha": request["pullRequest"]["headSha"],
    }
    if result["reviewedSnapshot"] != expected_snapshot:
        raise WorkflowError("snapshot_mismatch", "ReviewResult snapshot does not match ReviewRequest")
    expected_routes = {
        "sourceThreadId": config["threads"]["reviewer"],
        "destinationThreadId": config["threads"]["main"],
    }
    if config.get("hostId"):
        expected_routes["hostId"] = config["hostId"]
    if result["routes"] != expected_routes:
        raise WorkflowError("route_mismatch", "ReviewResult routes do not match local config")
    if result["merge"]["status"] == "MERGED":
        if not config["policy"]["mergeOnApprove"] or not request["mergePolicy"]["mergeOnApprove"]:
            raise WorkflowError("merge_not_authorized", "Merged result is not authorized by local policy")
        if result["merge"]["url"] != request["pullRequest"]["url"]:
            raise WorkflowError("repository_mismatch", "Merged result URL does not match the reviewed pull request")


def result_status(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    if decision == "APPROVE":
        return "merged" if result["merge"]["status"] == "MERGED" else "merge_ready"
    return {
        "COMMENT": "comment",
        "REQUEST_CHANGES": "changes_requested",
        "STALE": "stale",
        "FAILED": "failed",
    }[decision]


def command_locate(args: argparse.Namespace) -> dict[str, Any]:
    root = canonical_repo_root(args.repo_root)
    origin = require_github_origin(discover_origin(root))
    paths = workflow_paths(root, origin)
    return {
        "ok": True,
        "repository": {"root": str(root), "origin": origin, "key": paths["key"]},
        "paths": {"config": str(paths["config"]), "state": str(paths["state"])},
    }


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    root = canonical_repo_root(args.repo_root)
    origin = require_github_origin(args.origin)
    discovered = require_github_origin(discover_origin(root))
    if origin != discovered:
        raise WorkflowError("repository_mismatch", "Provided origin does not match the repository origin")
    paths = workflow_paths(root, origin)
    config_path = Path(paths["config"])
    state_path = Path(paths["state"])
    lock_path = Path(paths["lock"])
    now = utc_now()
    merge_on_approve = args.merge_policy == "merge-on-approve"

    with StateLock(lock_path):
        existing: dict[str, Any] | None = None
        if config_path.exists():
            existing = validate_config(read_json(config_path), expected_root=root, expected_origin=origin)
        workflow_id = existing["workflowId"] if existing else str(uuid.uuid4())
        created_at = existing["createdAt"] if existing else now
        config: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "workflowId": workflow_id,
            "repository": {"root": str(root), "origin": origin, "key": paths["key"]},
            "projectId": args.project_id,
            "threads": {"main": args.main_thread_id, "reviewer": args.review_thread_id},
            "policy": {
                "mergeOnApprove": merge_on_approve,
                "mergeMethod": args.merge_method,
                "deleteBranch": bool(args.delete_branch),
                "requireGreenChecks": True,
                "requireExactHead": True,
            },
            "createdAt": created_at,
            "updatedAt": now,
        }
        if args.host_id:
            config["hostId"] = args.host_id
        validate_config(config, expected_root=root, expected_origin=origin)

        if existing and not args.replace:
            comparable_existing = dict(existing)
            comparable_existing["updatedAt"] = now
            if comparable_existing != config:
                raise WorkflowError(
                    "config_exists",
                    "A different workflow configuration already exists; use explicit replacement after validating routes",
                    details={"configPath": str(config_path)},
                )
            return {
                "ok": True,
                "reused": True,
                "configPath": str(config_path),
                "statePath": str(state_path),
                "config": existing,
            }

        atomic_write_json(config_path, config)
        if existing and state_path.exists():
            state = validate_state(read_json(state_path), config)
        else:
            state = initial_state(workflow_id)
            atomic_write_json(state_path, state)
        return {
            "ok": True,
            "reused": False,
            "replaced": bool(existing),
            "configPath": str(config_path),
            "statePath": str(state_path),
            "config": config,
        }


def command_show(args: argparse.Namespace) -> dict[str, Any]:
    _, _, paths, config, state = load_context(args.repo_root)
    return {
        "ok": True,
        "configPath": str(paths["config"]),
        "statePath": str(paths["state"]),
        "config": config,
        "state": state,
    }


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    _, _, paths, config, state = load_context(args.repo_root)
    return {
        "ok": True,
        "valid": True,
        "workflowId": config["workflowId"],
        "repositoryKey": config["repository"]["key"],
        "dispatchCount": len(state["dispatches"]),
        "configPath": str(paths["config"]),
        "statePath": str(paths["state"]),
    }


def command_prepare_review(args: argparse.Namespace) -> dict[str, Any]:
    _, _, paths, config, state = load_context(args.repo_root)
    base_sha = require_sha(args.base_sha, "baseSha")
    head_sha = require_sha(args.head_sha, "headSha")
    pr_number = require_int(args.pr_number, "prNumber", minimum=1)
    request: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "messageType": "ReviewRequest",
        "workflowId": config["workflowId"],
        "dispatchId": compute_dispatch_id(config, pr_number, base_sha, head_sha),
        "repository": {"key": config["repository"]["key"], "origin": config["repository"]["origin"]},
        "pullRequest": {
            "number": pr_number,
            "url": args.pr_url,
            "baseSha": base_sha,
            "headSha": head_sha,
            "branch": args.branch,
        },
        "routes": {
            "sourceThreadId": config["threads"]["main"],
            "destinationThreadId": config["threads"]["reviewer"],
        },
        "mergePolicy": dict(config["policy"]),
        "evidence": list(args.evidence or []),
        "checks": list(args.check or []),
        "limitations": list(args.limitation or []),
        "createdAt": utc_now(),
    }
    if config.get("hostId"):
        request["routes"]["hostId"] = config["hostId"]
    validate_review_request(request)
    validate_request_against_config(request, config)
    dispatch_id = request["dispatchId"]

    with StateLock(Path(paths["lock"])):
        current_state = read_json(Path(paths["state"]), code="missing_state") if Path(paths["state"]).exists() else state
        current_state = validate_state(current_state, config)
        existing = current_state["dispatches"].get(dispatch_id)
        should_send = True
        status = "prepared"
        if existing:
            request["createdAt"] = existing["requestCreatedAt"]
            validate_review_request(request)
            metadata = expected_dispatch_metadata(request)
            for key in (
                "pullRequestNumber",
                "pullRequestUrl",
                "baseSha",
                "headSha",
                "branch",
                "sourceThreadId",
                "destinationThreadId",
                "requestCreatedAt",
                "requestDigest",
            ):
                if existing.get(key) != metadata[key]:
                    raise WorkflowError("dispatch_collision", "Existing dispatch metadata does not match the prepared request")
            status = existing["status"]
            should_send = status in {"prepared", "delivery_failed"}
            if status == "delivery_failed":
                existing["status"] = "prepared"
                existing["preparedAt"] = utc_now()
                existing["requestDigest"] = metadata["requestDigest"]
                existing.pop("deliveryError", None)
                status = "prepared"
        else:
            metadata = expected_dispatch_metadata(request)
            current_state["dispatches"][dispatch_id] = {
                **metadata,
                "status": "prepared",
                "preparedAt": utc_now(),
            }
        current_state["updatedAt"] = utc_now()
        atomic_write_json(Path(paths["state"]), current_state)
    return {"ok": True, "shouldSend": should_send, "status": status, "request": request}


def get_dispatch(state: Mapping[str, Any], dispatch_id: str) -> dict[str, Any]:
    if not HEX_64_RE.fullmatch(dispatch_id):
        raise WorkflowError("invalid_dispatch", "Dispatch ID must be 64 lowercase hex characters")
    dispatch = state["dispatches"].get(dispatch_id)
    if not isinstance(dispatch, dict):
        raise WorkflowError("unknown_dispatch", "Dispatch ID is not known to this workflow")
    return dispatch


def mutate_dispatch(args: argparse.Namespace, operation: str) -> dict[str, Any]:
    _, _, paths, config, state = load_context(args.repo_root)
    with StateLock(Path(paths["lock"])):
        state = validate_state(read_json(Path(paths["state"]), code="missing_state"), config)
        dispatch = get_dispatch(state, args.dispatch_id)
        current = dispatch["status"]
        if operation == "dispatched":
            if current in {"prepared", "delivery_failed"}:
                dispatch["status"] = "dispatched"
            elif current not in {
                "dispatched",
                "reviewing",
                "merge_ready",
                "merged",
                "comment",
                "changes_requested",
                "stale",
                "failed",
            }:
                raise WorkflowError("invalid_transition", f"Cannot mark {current} dispatch as dispatched")
            dispatch.setdefault("dispatchedAt", utc_now())
            dispatch.pop("deliveryError", None)
        elif operation == "delivery_failed":
            if current not in {"prepared", "delivery_failed"}:
                raise WorkflowError("invalid_transition", f"Cannot mark {current} dispatch as delivery_failed")
            dispatch["status"] = "delivery_failed"
            dispatch["deliveryFailedAt"] = utc_now()
            dispatch["deliveryError"] = require_string(args.reason, "reason")[:500]
        elif operation == "cancelled":
            if current not in {"prepared", "delivery_failed", "dispatched", "reviewing"}:
                raise WorkflowError("invalid_transition", f"Cannot cancel {current} dispatch")
            dispatch["status"] = "cancelled"
            dispatch["cancelledAt"] = utc_now()
            dispatch["cancelReason"] = require_string(args.reason, "reason")[:500]
        else:
            raise AssertionError(operation)
        state["updatedAt"] = utc_now()
        atomic_write_json(Path(paths["state"]), state)
    return {"ok": True, "dispatchId": args.dispatch_id, "status": dispatch["status"]}


def command_accept_review(args: argparse.Namespace) -> dict[str, Any]:
    request = load_payload(args.request_file, expected="request")
    _, _, paths, config, state = load_context(args.repo_root)
    validate_request_against_config(request, config)
    dispatch_id = request["dispatchId"]
    with StateLock(Path(paths["lock"])):
        state = validate_state(read_json(Path(paths["state"]), code="missing_state"), config)
        dispatch = get_dispatch(state, dispatch_id)
        validate_request_against_dispatch(request, dispatch)
        if dispatch["status"] in {"prepared", "delivery_failed", "dispatched"}:
            dispatch["status"] = "reviewing"
            dispatch["reviewingAt"] = utc_now()
        elif dispatch["status"] != "reviewing":
            return {"ok": True, "accepted": False, "duplicate": True, "status": dispatch["status"], "request": request}
        state["updatedAt"] = utc_now()
        atomic_write_json(Path(paths["state"]), state)
    return {"ok": True, "accepted": True, "duplicate": False, "status": "reviewing", "request": request}


def read_json_array(path: str, field: str) -> list[Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError("invalid_json", f"Cannot read JSON array for {field}") from exc
    if not isinstance(value, list):
        raise WorkflowError("invalid_payload", f"{field} file must contain a JSON array")
    return value


def command_prepare_result(args: argparse.Namespace) -> dict[str, Any]:
    request = load_payload(args.request_file, expected="request")
    _, _, paths, config, state = load_context(args.repo_root)
    validate_request_against_config(request, config)
    initial_dispatch = get_dispatch(state, request["dispatchId"])
    validate_request_against_dispatch(request, initial_dispatch)
    findings = read_json_array(args.findings_file, "findings")
    verification = read_json_array(args.verification_file, "verification")
    merge: dict[str, Any] = {"status": args.merge_status}
    if args.merge_url:
        merge["url"] = args.merge_url
    if args.merge_sha:
        merge["sha"] = args.merge_sha.lower()
    if args.merge_error:
        merge["error"] = args.merge_error[:500]
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "messageType": "ReviewResult",
        "workflowId": request["workflowId"],
        "dispatchId": request["dispatchId"],
        "reviewedSnapshot": {
            "repositoryKey": request["repository"]["key"],
            "pullRequestNumber": request["pullRequest"]["number"],
            "baseSha": request["pullRequest"]["baseSha"],
            "headSha": request["pullRequest"]["headSha"],
        },
        "routes": {
            "sourceThreadId": config["threads"]["reviewer"],
            "destinationThreadId": config["threads"]["main"],
        },
        "decision": args.decision,
        "findings": findings,
        "verification": verification,
        "limitations": list(args.limitation or []),
        "merge": merge,
        "createdAt": initial_dispatch.get("resultCreatedAt", utc_now()),
    }
    if config.get("hostId"):
        result["routes"]["hostId"] = config["hostId"]
    validate_review_result(result)
    validate_result_against_request(result, request, config)
    dispatch_id = request["dispatchId"]
    status = result_status(result)

    with StateLock(Path(paths["lock"])):
        state = validate_state(read_json(Path(paths["state"]), code="missing_state"), config)
        dispatch = get_dispatch(state, dispatch_id)
        validate_request_against_dispatch(request, dispatch)
        if dispatch.get("resultCreatedAt"):
            result["createdAt"] = dispatch["resultCreatedAt"]
            validate_review_result(result)
        if dispatch["status"] not in {"reviewing", "dispatched", status}:
            raise WorkflowError("invalid_transition", f"Cannot prepare result from dispatch state {dispatch['status']}")
        result_digest = digest_json(result)
        if dispatch.get("resultDigest") and dispatch["resultDigest"] != result_digest:
            raise WorkflowError("result_conflict", "A different result already exists for this dispatch")
        dispatch["status"] = status
        dispatch["decision"] = result["decision"]
        dispatch["mergeStatus"] = result["merge"]["status"]
        dispatch["resultDigest"] = result_digest
        dispatch["resultCreatedAt"] = result["createdAt"]
        dispatch["resultPreparedAt"] = utc_now()
        state["updatedAt"] = utc_now()
        atomic_write_json(Path(paths["state"]), state)
    return {"ok": True, "status": status, "result": result}


def command_accept_result(args: argparse.Namespace) -> dict[str, Any]:
    result = load_payload(args.result_file, expected="result")
    _, _, paths, config, state = load_context(args.repo_root)
    dispatch = get_dispatch(state, result["dispatchId"])
    request = {
        "schemaVersion": SCHEMA_VERSION,
        "messageType": "ReviewRequest",
        "workflowId": config["workflowId"],
        "dispatchId": result["dispatchId"],
        "repository": {"key": config["repository"]["key"], "origin": config["repository"]["origin"]},
        "pullRequest": {
            "number": dispatch["pullRequestNumber"],
            "url": dispatch["pullRequestUrl"],
            "baseSha": dispatch["baseSha"],
            "headSha": dispatch["headSha"],
            "branch": dispatch["branch"],
        },
        "routes": {
            "sourceThreadId": config["threads"]["main"],
            "destinationThreadId": config["threads"]["reviewer"],
        },
        "mergePolicy": dict(config["policy"]),
        "evidence": [],
        "checks": [],
        "limitations": [],
        "createdAt": dispatch["requestCreatedAt"],
    }
    if config.get("hostId"):
        request["routes"]["hostId"] = config["hostId"]
    validate_result_against_request(result, request, config)
    status = result_status(result)
    result_digest = digest_json(result)

    with StateLock(Path(paths["lock"])):
        state = validate_state(read_json(Path(paths["state"]), code="missing_state"), config)
        dispatch = get_dispatch(state, result["dispatchId"])
        if dispatch["status"] != status or not dispatch.get("resultDigest"):
            raise WorkflowError("invalid_transition", "ReviewResult was not prepared by the configured reviewer workflow")
        if dispatch["resultDigest"] != result_digest:
            raise WorkflowError("result_conflict", "ReviewResult conflicts with local state")
        dispatch["status"] = status
        dispatch["decision"] = result["decision"]
        dispatch["mergeStatus"] = result["merge"]["status"]
        dispatch["resultDigest"] = result_digest
        dispatch["resultAcceptedAt"] = utc_now()
        state["updatedAt"] = utc_now()
        atomic_write_json(Path(paths["state"]), state)
    return {"ok": True, "accepted": True, "status": status, "dispatchId": result["dispatchId"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Codex Feature Lifecycle local state")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def repo_command(name: str, help_text: str) -> argparse.ArgumentParser:
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--repo-root", required=True)
        return command

    repo_command("locate", "Locate config/state paths and repository identity")

    init_parser = repo_command("init", "Create or explicitly replace workflow config")
    init_parser.add_argument("--origin", required=True)
    init_parser.add_argument("--project-id", required=True)
    init_parser.add_argument("--host-id")
    init_parser.add_argument("--main-thread-id", required=True)
    init_parser.add_argument("--review-thread-id", required=True)
    init_parser.add_argument("--merge-policy", choices=("review-only", "merge-on-approve"), required=True)
    init_parser.add_argument("--merge-method", choices=sorted(MERGE_METHODS), default="squash")
    init_parser.add_argument("--delete-branch", action="store_true")
    init_parser.add_argument("--replace", action="store_true")

    repo_command("show", "Show validated config and state")
    repo_command("validate", "Validate config and state for the current repository")

    prepare = repo_command("prepare-review", "Prepare an idempotent ReviewRequest")
    prepare.add_argument("--pr-number", type=int, required=True)
    prepare.add_argument("--pr-url", required=True)
    prepare.add_argument("--base-sha", required=True)
    prepare.add_argument("--head-sha", required=True)
    prepare.add_argument("--branch", required=True)
    prepare.add_argument("--evidence", action="append")
    prepare.add_argument("--check", action="append")
    prepare.add_argument("--limitation", action="append")

    dispatched = repo_command("mark-dispatched", "Mark a host-confirmed request delivery")
    dispatched.add_argument("--dispatch-id", required=True)

    delivery_failed = repo_command("mark-delivery-failed", "Record a retryable request delivery failure")
    delivery_failed.add_argument("--dispatch-id", required=True)
    delivery_failed.add_argument("--reason", required=True)

    cancelled = repo_command("cancel-dispatch", "Invalidate a pending review dispatch after explicit user cancellation")
    cancelled.add_argument("--dispatch-id", required=True)
    cancelled.add_argument("--reason", required=True)

    accept_review = repo_command("accept-review", "Validate and accept a ReviewRequest")
    accept_review.add_argument("--request-file", required=True)

    prepare_result = repo_command("prepare-result", "Prepare and persist a ReviewResult")
    prepare_result.add_argument("--request-file", required=True)
    prepare_result.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    prepare_result.add_argument("--findings-file", required=True)
    prepare_result.add_argument("--verification-file", required=True)
    prepare_result.add_argument("--limitation", action="append")
    prepare_result.add_argument("--merge-status", choices=sorted(MERGE_STATUSES), required=True)
    prepare_result.add_argument("--merge-url")
    prepare_result.add_argument("--merge-sha")
    prepare_result.add_argument("--merge-error")

    accept_result = repo_command("accept-result", "Validate and accept a ReviewResult")
    accept_result.add_argument("--result-file", required=True)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    commands = {
        "locate": command_locate,
        "init": command_init,
        "show": command_show,
        "validate": command_validate,
        "prepare-review": command_prepare_review,
        "mark-dispatched": lambda value: mutate_dispatch(value, "dispatched"),
        "mark-delivery-failed": lambda value: mutate_dispatch(value, "delivery_failed"),
        "cancel-dispatch": lambda value: mutate_dispatch(value, "cancelled"),
        "accept-review": command_accept_review,
        "prepare-result": command_prepare_result,
        "accept-result": command_accept_result,
    }
    return commands[args.command](args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except WorkflowError as exc:
        payload: dict[str, Any] = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
        if exc.details:
            payload["error"]["details"] = exc.details
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        print(f"workflowctl: {exc.code}: {exc.message}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
