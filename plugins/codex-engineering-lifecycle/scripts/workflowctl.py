#!/usr/bin/env python3
"""Deterministic state helper for Codex Engineering Lifecycle."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 2
ROLES = ("requirements", "main", "review")
MERGE_MODES = ("review-only", "merge-on-approve")
MERGE_METHODS = ("squash", "merge", "rebase")
STAGES = {
    "REQUIREMENTS_CONFIRMED",
    "PLAN_DRAFTING",
    "PLAN_REVIEW_PENDING",
    "PLAN_CHANGES_REQUESTED",
    "PLAN_APPROVED",
    "DEVELOPMENT_QUEUED",
    "DEVELOPMENT_ACTIVE",
    "DEVELOPMENT_BLOCKED",
    "DEVELOPMENT_COMPLETE",
    "CODE_REVIEW_PENDING",
    "CODE_CHANGES_REQUESTED",
    "MERGE_READY",
    "MERGED",
    "RELEASE_AWAITING_AUTHORIZATION",
    "RELEASE_AUTHORIZED",
    "RELEASE_FAILED",
    "RELEASED",
    "CLOSED",
}
MESSAGE_TYPES = {
    "RequirementsHandoff",
    "TechnicalPlanReviewRequest",
    "TechnicalPlanReviewResult",
    "CodeReviewRequest",
    "CodeReviewResult",
}
DISPATCH_STATUSES = {
    "prepared",
    "dispatched",
    "delivery_failed",
    "accepted",
    "applied",
}
GOAL_STATUSES = {"PREPARED", "ACTIVE", "BLOCKED", "COMPLETE"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
FEATURE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?-[0-9a-f]{12}$")
REPO_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
ARTIFACT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,199}$")


class WorkflowError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message[:500]


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("invalid_payload", f"{field} must be an object")
    return value


def exact_keys(
    value: Any,
    field: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    obj = require_object(value, field)
    optional = optional or set()
    missing = required - set(obj)
    extra = set(obj) - required - optional
    if missing:
        raise WorkflowError(
            "invalid_payload", f"{field} is missing: {', '.join(sorted(missing))}"
        )
    if extra:
        raise WorkflowError(
            "invalid_payload", f"{field} has unknown fields: {', '.join(sorted(extra))}"
        )
    return obj


def require_string(value: Any, field: str, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise WorkflowError(
            "invalid_payload",
            f"{field} must be a non-empty string up to {maximum} characters",
        )
    return value.strip()


def require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise WorkflowError("invalid_payload", f"{field} must be boolean")
    return value


def require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise WorkflowError(
            "invalid_payload", f"{field} must be an integer >= {minimum}"
        )
    return value


def require_sha(value: Any, field: str) -> str:
    text = require_string(value, field, maximum=40)
    if not SHA_RE.fullmatch(text):
        raise WorkflowError(
            "invalid_payload", f"{field} must be 40 lowercase hex characters"
        )
    return text


def require_digest(value: Any, field: str) -> str:
    text = require_string(value, field, maximum=64)
    if not DIGEST_RE.fullmatch(text):
        raise WorkflowError(
            "invalid_payload", f"{field} must be 64 lowercase hex characters"
        )
    return text


def require_timestamp(value: Any, field: str) -> str:
    text = require_string(value, field, maximum=20)
    if not RFC3339_RE.fullmatch(text):
        raise WorkflowError(
            "invalid_payload", f"{field} must be strict RFC3339 UTC with Z"
        )
    try:
        dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
    except ValueError as exc:
        raise WorkflowError(
            "invalid_payload", f"{field} is not a real UTC date/time"
        ) from exc
    return text


def require_feature_id(value: Any, field: str = "featureId") -> str:
    text = require_string(value, field, maximum=76)
    if not FEATURE_RE.fullmatch(text):
        raise WorkflowError(
            "invalid_payload", f"{field} must be a slug plus 12 lowercase hex"
        )
    return text


def require_semver(value: Any, field: str) -> str:
    text = require_string(value, field, maximum=100)
    if not SEMVER_RE.fullmatch(text):
        raise WorkflowError(
            "invalid_payload", f"{field} must use strict semantic versioning"
        )
    return text


def require_https_url(value: Any, field: str, *, host: str | None = None) -> str:
    text = require_string(value, field, maximum=1000)
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise WorkflowError(
            "invalid_payload", f"{field} must be a credential-free HTTPS URL"
        )
    if host and parsed.hostname != host:
        raise WorkflowError("invalid_payload", f"{field} must use host {host}")
    return text


def require_canonical_https_path(
    value: Any, field: str, *, host: str, path: str
) -> str:
    text = require_https_url(value, field, host=host)
    parsed = urlsplit(text)
    try:
        port = parsed.port
    except ValueError as exc:
        raise WorkflowError(
            "invalid_payload", f"{field} contains an invalid port"
        ) from exc
    if (
        port is not None
        or parsed.query
        or parsed.fragment
        or unquote(parsed.path).rstrip("/") != path.rstrip("/")
    ):
        raise WorkflowError(
            "invalid_payload", f"{field} is not the canonical authorized URL"
        )
    return text


def normalized_project_name(value: str) -> str:
    name = require_string(value, "projectName", maximum=200)
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,198}[A-Za-z0-9])?", name):
        raise WorkflowError(
            "invalid_payload", "projectName is not a valid Python project name"
        )
    return re.sub(r"[-_.]+", "-", name).lower()


def require_repo_path(value: Any, field: str) -> str:
    text = require_string(value, field, maximum=500)
    if "\\" in text:
        raise WorkflowError("invalid_payload", f"{field} must use POSIX separators")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", "..", ".git"} for part in path.parts)
    ):
        raise WorkflowError(
            "invalid_payload", f"{field} must be a safe repository-relative path"
        )
    return path.as_posix()


def parse_origin(value: str) -> tuple[str, str]:
    origin = value.strip()
    owner: str
    repo: str
    if origin.startswith("https://"):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port
        ):
            raise WorkflowError(
                "invalid_repository",
                "origin must be canonical credential-free GitHub HTTPS",
            )
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise WorkflowError(
                "invalid_repository", "origin must identify exactly owner/repository"
            )
        owner, repo = parts
    else:
        match = re.fullmatch(r"git@github\.com:([^/]+)/([^/]+)", origin)
        if not match:
            match = re.fullmatch(r"ssh://git@github\.com/([^/]+)/([^/]+)", origin)
        if not match:
            raise WorkflowError(
                "invalid_repository", "origin must be canonical GitHub HTTPS or SSH"
            )
        owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    if (
        not owner
        or not repo
        or not REPO_PART_RE.fullmatch(owner)
        or not REPO_PART_RE.fullmatch(repo)
    ):
        raise WorkflowError(
            "invalid_repository", "origin owner/repository is malformed"
        )
    if owner in {".", ".."} or repo in {".", ".."}:
        raise WorkflowError(
            "invalid_repository", "origin owner/repository is malformed"
        )
    key = f"{owner.lower()}/{repo.lower()}"
    return key, f"https://github.com/{key}"


def run_git(root: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError("git_timeout", "Git operation exceeded 30 seconds") from exc
    if check and result.returncode != 0:
        summary = (
            (result.stderr or result.stdout or "git command failed")
            .strip()
            .splitlines()[0]
        )
        raise WorkflowError("git_error", summary[:300])
    return result.stdout.strip()


def resolve_repository(repo_arg: str) -> dict[str, Any]:
    candidate = Path(repo_arg).expanduser().resolve()
    root = Path(run_git(candidate, "rev-parse", "--show-toplevel")).resolve()
    common_raw = run_git(root, "rev-parse", "--git-common-dir")
    common = (
        (root / common_raw).resolve()
        if not Path(common_raw).is_absolute()
        else Path(common_raw).resolve()
    )
    origin_raw = run_git(root, "config", "--get", "remote.origin.url")
    key, origin = parse_origin(origin_raw)
    return {"root": root, "commonDir": common, "key": key, "origin": origin}


def state_paths(repository: Mapping[str, Any]) -> dict[str, Path]:
    codex_root = (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        .expanduser()
        .resolve()
    )
    suffix = hashlib.sha256(
        f"{repository['key']}\0{repository['commonDir']}".encode()
    ).hexdigest()[:16]
    safe = repository["key"].replace("/", "--")
    root = codex_root / "engineering-lifecycle" / "projects" / f"{safe}--{suffix}"
    return {
        "root": root,
        "config": root / "config.json",
        "state": root / "state.json",
        "pending": root / "init-pending.json",
        "lock": root / "state.lock",
    }


@contextlib.contextmanager
def locked(path: Path, timeout: float = 10.0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise WorkflowError(
                        "lock_timeout", "Timed out waiting for workflow state lock"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_json(path: Path, field: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(
            "workflow_not_initialized", f"{field} does not exist; run Init"
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(
            "invalid_state", f"{field} is not valid UTF-8 JSON"
        ) from exc
    return require_object(value, field)


def atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)


def validate_config(value: Any, repository: Mapping[str, Any]) -> dict[str, Any]:
    config = exact_keys(
        value,
        "config",
        {
            "schemaVersion",
            "workflowId",
            "repository",
            "tasks",
            "policy",
            "createdAt",
            "updatedAt",
        },
    )
    if (
        require_int(config["schemaVersion"], "config.schemaVersion", minimum=1)
        != SCHEMA_VERSION
    ):
        raise WorkflowError("unsupported_schema", "Unsupported config schema version")
    try:
        uuid.UUID(require_string(config["workflowId"], "config.workflowId", maximum=36))
    except ValueError as exc:
        raise WorkflowError("invalid_state", "config.workflowId must be UUID") from exc
    repo = exact_keys(
        config["repository"], "config.repository", {"key", "origin", "commonDir"}
    )
    if repo["key"] != repository["key"] or repo["origin"] != repository["origin"]:
        raise WorkflowError(
            "repository_mismatch", "Workflow belongs to another GitHub repository"
        )
    if (
        Path(
            require_string(
                repo["commonDir"], "config.repository.commonDir", maximum=2000
            )
        ).resolve()
        != repository["commonDir"]
    ):
        raise WorkflowError(
            "repository_mismatch", "Workflow belongs to another Git common directory"
        )
    tasks = exact_keys(config["tasks"], "config.tasks", set(ROLES))
    task_ids = [
        require_string(tasks[role], f"config.tasks.{role}", maximum=200)
        for role in ROLES
    ]
    if len(set(task_ids)) != len(task_ids):
        raise WorkflowError(
            "invalid_state", "Configured task IDs must be pairwise distinct"
        )
    policy = exact_keys(
        config["policy"], "config.policy", {"goalModeAuthorized", "merge", "release"}
    )
    if (
        require_bool(policy["goalModeAuthorized"], "config.policy.goalModeAuthorized")
        is not True
    ):
        raise WorkflowError("invalid_state", "Goal mode must be explicitly authorized")
    merge = exact_keys(
        policy["merge"],
        "config.policy.merge",
        {"mode", "method", "deleteBranch", "requireGreenChecks", "requireExactHead"},
    )
    if merge["mode"] not in MERGE_MODES or merge["method"] not in MERGE_METHODS:
        raise WorkflowError("invalid_state", "Unsupported merge policy")
    require_bool(merge["deleteBranch"], "config.policy.merge.deleteBranch")
    if (
        require_bool(
            merge["requireGreenChecks"], "config.policy.merge.requireGreenChecks"
        )
        is not True
    ):
        raise WorkflowError("invalid_state", "Green checks must be required")
    if (
        require_bool(merge["requireExactHead"], "config.policy.merge.requireExactHead")
        is not True
    ):
        raise WorkflowError("invalid_state", "Exact head must be required")
    release = exact_keys(policy["release"], "config.policy.release", {"mode"})
    if release["mode"] != "explicit-per-release":
        raise WorkflowError("invalid_state", "Unsupported release mode")
    require_timestamp(config["createdAt"], "config.createdAt")
    require_timestamp(config["updatedAt"], "config.updatedAt")
    return config


def validate_goal_run(value: Any, field: str) -> dict[str, Any]:
    run = exact_keys(
        value,
        field,
        {
            "goalRunId",
            "purpose",
            "reviewCycle",
            "threadId",
            "authorityMessageId",
            "objectiveDigest",
            "status",
        },
        {"startedAt", "completedAt", "blockedReason", "usage"},
    )
    require_digest(run["goalRunId"], f"{field}.goalRunId")
    if run["purpose"] not in {"INITIAL_IMPLEMENTATION", "CODE_REMEDIATION"}:
        raise WorkflowError("invalid_state", f"{field}.purpose is unsupported")
    require_int(run["reviewCycle"], f"{field}.reviewCycle")
    require_string(run["threadId"], f"{field}.threadId", maximum=200)
    require_digest(run["authorityMessageId"], f"{field}.authorityMessageId")
    require_digest(run["objectiveDigest"], f"{field}.objectiveDigest")
    if run["status"] not in GOAL_STATUSES:
        raise WorkflowError("invalid_state", f"{field}.status is unsupported")
    if "startedAt" in run:
        require_timestamp(run["startedAt"], f"{field}.startedAt")
    if "completedAt" in run:
        require_timestamp(run["completedAt"], f"{field}.completedAt")
    if run["status"] in {"ACTIVE", "BLOCKED", "COMPLETE"} and "startedAt" not in run:
        raise WorkflowError("invalid_state", f"{field}.startedAt is required")
    if run["status"] == "COMPLETE" and "completedAt" not in run:
        raise WorkflowError("invalid_state", f"{field}.completedAt is required")
    if run["status"] == "BLOCKED" and "blockedReason" not in run:
        raise WorkflowError("invalid_state", f"{field}.blockedReason is required")
    return run


def validate_feature_record(
    value: Any,
    feature_id: str,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    field = f"state.features.{feature_id}"
    feature = exact_keys(
        value,
        field,
        {
            "featureId",
            "title",
            "branch",
            "stage",
            "requirements",
            "planReviewCycle",
            "goalRuns",
            "codeReviewCycle",
            "lastError",
            "createdAt",
            "updatedAt",
        },
        {
            "requirementsAcceptedAt",
            "requirementsMessageId",
            "plan",
            "pendingPlanRequestId",
            "planResultMessageId",
            "pullRequest",
            "pendingCodeRequestId",
            "codeResultMessageId",
            "merge",
            "release",
            "closure",
        },
    )
    if feature["featureId"] != feature_id:
        raise WorkflowError("invalid_state", "Feature key and featureId differ")
    require_string(feature["title"], f"{field}.title", maximum=200)
    require_string(feature["branch"], f"{field}.branch", maximum=240)
    if feature["stage"] not in STAGES:
        raise WorkflowError(
            "invalid_state", f"Feature {feature_id} has unsupported stage"
        )
    validate_artifact_shape(feature["requirements"], f"{field}.requirements")
    require_int(feature["planReviewCycle"], f"{field}.planReviewCycle")
    require_int(feature["codeReviewCycle"], f"{field}.codeReviewCycle")
    if feature["lastError"] is not None:
        error = exact_keys(
            feature["lastError"],
            f"{field}.lastError",
            {"kind", "phase", "summary"},
        )
        for name in ("kind", "phase", "summary"):
            require_string(error[name], f"{field}.lastError.{name}", maximum=300)
    require_timestamp(feature["createdAt"], f"{field}.createdAt")
    require_timestamp(feature["updatedAt"], f"{field}.updatedAt")
    if "requirementsAcceptedAt" in feature:
        require_timestamp(
            feature["requirementsAcceptedAt"], f"{field}.requirementsAcceptedAt"
        )
    for name in (
        "requirementsMessageId",
        "pendingPlanRequestId",
        "planResultMessageId",
        "pendingCodeRequestId",
        "codeResultMessageId",
    ):
        if name in feature:
            require_digest(feature[name], f"{field}.{name}")
    if "plan" in feature:
        validate_plan_shape(feature["plan"], f"{field}.plan")
    if "pullRequest" in feature:
        validate_pull_request_shape(feature["pullRequest"], f"{field}.pullRequest")
    if "merge" in feature:
        merge = exact_keys(
            feature["merge"],
            f"{field}.merge",
            {"method", "prUrl", "approvedHeadSha", "mergeCommitSha", "mergedAt"},
        )
        if merge["method"] not in MERGE_METHODS:
            raise WorkflowError("invalid_state", f"{field}.merge.method is unsupported")
        require_https_url(merge["prUrl"], f"{field}.merge.prUrl", host="github.com")
        require_sha(merge["approvedHeadSha"], f"{field}.merge.approvedHeadSha")
        require_sha(merge["mergeCommitSha"], f"{field}.merge.mergeCommitSha")
        require_timestamp(merge["mergedAt"], f"{field}.merge.mergedAt")
        if "pullRequest" in feature and (
            merge["prUrl"].rstrip("/") != feature["pullRequest"]["url"].rstrip("/")
            or merge["approvedHeadSha"] != feature["pullRequest"]["headSha"]
        ):
            raise WorkflowError(
                "invalid_state", f"{field}.merge differs from reviewed pull request"
            )
    stage = feature["stage"]
    merge_stages = {
        "MERGED",
        "RELEASE_AWAITING_AUTHORIZATION",
        "RELEASE_AUTHORIZED",
        "RELEASE_FAILED",
        "RELEASED",
        "CLOSED",
    }
    release_stages = {"RELEASE_AUTHORIZED", "RELEASE_FAILED", "RELEASED", "CLOSED"}
    if "merge" in feature and stage not in merge_stages:
        raise WorkflowError(
            "invalid_state", f"{field} contains merge proof outside merge stages"
        )
    if "release" in feature and stage not in release_stages:
        raise WorkflowError(
            "invalid_state", f"{field} contains release proof outside release stages"
        )
    if "closure" in feature and stage != "CLOSED":
        raise WorkflowError(
            "invalid_state", f"{field} contains closure proof before CLOSED"
        )
    release_result: dict[str, Any] | None = None
    if "release" in feature:
        release = exact_keys(
            feature["release"],
            f"{field}.release",
            {"authorization"},
            {"result", "lastSubmission", "submissions"},
        )
        proof_fields = ("result", "lastSubmission", "submissions")
        if len({name in release for name in proof_fields}) != 1:
            raise WorkflowError(
                "invalid_state",
                f"{field}.release result, lastSubmission, and submissions must appear together",
            )
        authorization = validate_release_authorization_shape(release["authorization"])
        if "authorizationId" not in authorization:
            raise WorkflowError(
                "invalid_state", f"{field}.release authorization lacks authorizationId"
            )
        authorization_targets = [
            normalize_target(
                item,
                f"{field}.release.authorization.targets[{index}]",
                config["repository"]["key"],
            )
            for index, item in enumerate(authorization["targets"])
        ]
        authorization_targets.sort(key=lambda item: item["targetId"])
        canonical_authorization = {
            "schemaVersion": SCHEMA_VERSION,
            "workflowId": authorization["workflowId"],
            "featureId": authorization["featureId"],
            "mergeCommitSha": authorization["mergeCommitSha"],
            "version": authorization["version"],
            "tag": authorization["tag"],
            "targets": authorization_targets,
            "authorizedBy": require_string(
                authorization["authorizedBy"],
                f"{field}.release.authorization.authorizedBy",
                maximum=200,
            ),
            "authorizationEvidence": require_string(
                authorization["authorizationEvidence"],
                f"{field}.release.authorization.authorizationEvidence",
                maximum=500,
            ),
            "createdAt": authorization["createdAt"],
        }
        canonical_authorization["authorizationId"] = digest(canonical_authorization)
        if authorization != canonical_authorization:
            raise WorkflowError(
                "invalid_state", f"{field}.release authorization is not canonical"
            )
        for target in authorization_targets:
            if (
                target["kind"] == "GITHUB_RELEASE"
                and target["tag"] != authorization["tag"]
            ):
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release GitHub target tag differs from authorization",
                )
            if (
                target["kind"] == "PYPI"
                and target["version"] != authorization["version"]
            ):
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release PyPI target version differs from authorization",
                )
        if (
            authorization["workflowId"] != config["workflowId"]
            or authorization["featureId"] != feature_id
            or feature.get("merge", {}).get("mergeCommitSha")
            != authorization["mergeCommitSha"]
        ):
            raise WorkflowError(
                "invalid_state", f"{field}.release authorization is misbound"
            )
        if "result" in release:
            result = validate_release_result_shape(release["result"])
            if "proofDigest" not in result:
                raise WorkflowError(
                    "invalid_state", f"{field}.release result lacks proofDigest"
                )
            if (
                result["workflowId"] != config["workflowId"]
                or result["featureId"] != feature_id
                or result["authorizationId"] != authorization["authorizationId"]
                or result["mergeCommitSha"] != authorization["mergeCommitSha"]
            ):
                raise WorkflowError(
                    "invalid_state", f"{field}.release result is misbound"
                )
            target_map = {
                item["targetId"]: item for item in canonical_authorization["targets"]
            }
            result_ids = {item["targetId"] for item in result["targets"]}
            if result_ids != set(target_map) or len(result["targets"]) != len(
                result_ids
            ):
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release result target set differs from authorization",
                )
            normalized_results = [
                normalize_target_result(
                    item,
                    f"{field}.release.result.targets[{index}]",
                    target_map[item["targetId"]],
                )
                for index, item in enumerate(result["targets"])
            ]
            for item in normalized_results:
                if (
                    item["kind"] == "GITHUB_RELEASE"
                    and item["status"] == "PUBLISHED"
                    and item["tagCommitSha"] != authorization["mergeCommitSha"]
                ):
                    raise WorkflowError(
                        "invalid_state",
                        f"{field}.release GitHub tag does not target merge commit",
                    )
            normalized_results.sort(key=lambda item: item["targetId"])
            canonical_result = {
                "schemaVersion": SCHEMA_VERSION,
                "workflowId": result["workflowId"],
                "featureId": result["featureId"],
                "authorizationId": result["authorizationId"],
                "mergeCommitSha": result["mergeCommitSha"],
                "version": result["version"],
                "tag": result["tag"],
                "targets": normalized_results,
                "publishedAt": result["publishedAt"],
            }
            canonical_result["proofDigest"] = digest(canonical_result)
            if result != canonical_result:
                raise WorkflowError(
                    "invalid_state", f"{field}.release result is not canonical"
                )
            release_result = canonical_result
            last_submission = normalize_release_submission(
                release["lastSubmission"],
                f"{field}.release.lastSubmission",
                canonical_authorization["authorizationId"],
                target_map,
            )
            submissions_value = release["submissions"]
            if not isinstance(submissions_value, list) or not submissions_value:
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release submissions must be a non-empty history",
                )
            submissions = [
                normalize_release_submission(
                    item,
                    f"{field}.release.submissions[{index}]",
                    canonical_authorization["authorizationId"],
                    target_map,
                )
                for index, item in enumerate(submissions_value)
            ]
            submission_digests = [item["submissionDigest"] for item in submissions]
            if len(submission_digests) != len(set(submission_digests)):
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release submission history contains a duplicate entry",
                )
            if submissions[-1] != last_submission:
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release lastSubmission differs from submission history",
                )
            cumulative_by_id: dict[str, dict[str, Any]] = {}
            for index, submission in enumerate(submissions):
                submission_ids = {item["targetId"] for item in submission["targets"]}
                if index == 0:
                    expected_ids = set(target_map)
                else:
                    expected_ids = {
                        target_id
                        for target_id, item in cumulative_by_id.items()
                        if item["status"] == "FAILED"
                    }
                if submission_ids != expected_ids:
                    raise WorkflowError(
                        "invalid_state",
                        f"{field}.release submission history does not retry the exact failed target set",
                    )
                cumulative_by_id = {
                    target_id: item
                    for target_id, item in cumulative_by_id.items()
                    if target_id not in submission_ids and item["status"] == "PUBLISHED"
                }
                cumulative_by_id.update(
                    {item["targetId"]: item for item in submission["targets"]}
                )
            reconstructed = sorted(
                cumulative_by_id.values(), key=lambda item: item["targetId"]
            )
            if (
                reconstructed != canonical_result["targets"]
                or last_submission["publishedAt"] != canonical_result["publishedAt"]
            ):
                raise WorkflowError(
                    "invalid_state",
                    f"{field}.release cumulative result differs from submission history",
                )
        if stage == "RELEASE_AUTHORIZED" and release_result is not None:
            raise WorkflowError(
                "invalid_state", f"{field} has release proof before publication result"
            )
        if stage == "RELEASE_FAILED" and (
            release_result is None
            or not any(item["status"] == "FAILED" for item in release_result["targets"])
            or not any(
                item["status"] == "FAILED"
                for item in release["lastSubmission"]["targets"]
            )
        ):
            raise WorkflowError(
                "invalid_state", f"{field} lacks a failed authorized release target"
            )
    if "closure" in feature:
        closure = validate_closure_shape(feature["closure"])
        expected_release_targets = (
            [item["targetId"] for item in release_result["targets"]]
            if release_result
            else []
        )
        if (
            closure["requirementsMessageId"] != feature.get("requirementsMessageId")
            or closure["planReviewResultMessageId"]
            != feature.get("planResultMessageId")
            or closure["codeReviewResultMessageId"]
            != feature.get("codeResultMessageId")
            or closure["mergeCommitSha"]
            != feature.get("merge", {}).get("mergeCommitSha")
            or closure["releaseResultId"]
            != feature.get("release", {}).get("result", {}).get("proofDigest")
            or closure["releaseTargets"] != expected_release_targets
        ):
            raise WorkflowError("invalid_state", f"{field}.closure is misbound")

    plan_required = {
        "PLAN_REVIEW_PENDING",
        "PLAN_CHANGES_REQUESTED",
        "PLAN_APPROVED",
        "DEVELOPMENT_QUEUED",
        "DEVELOPMENT_ACTIVE",
        "DEVELOPMENT_BLOCKED",
        "DEVELOPMENT_COMPLETE",
        "CODE_REVIEW_PENDING",
        "CODE_CHANGES_REQUESTED",
        "MERGE_READY",
        "MERGED",
        "RELEASE_AWAITING_AUTHORIZATION",
        "RELEASE_AUTHORIZED",
        "RELEASE_FAILED",
        "RELEASED",
        "CLOSED",
    }
    plan_result_required = plan_required - {"PLAN_REVIEW_PENDING"}
    pull_required = {
        "CODE_REVIEW_PENDING",
        "CODE_CHANGES_REQUESTED",
        "MERGE_READY",
        "MERGED",
        "RELEASE_AWAITING_AUTHORIZATION",
        "RELEASE_AUTHORIZED",
        "RELEASE_FAILED",
        "RELEASED",
        "CLOSED",
    }
    merge_required = {
        "MERGED",
        "RELEASE_AWAITING_AUTHORIZATION",
        "RELEASE_AUTHORIZED",
        "RELEASE_FAILED",
        "RELEASED",
        "CLOSED",
    }
    release_required = {"RELEASE_AUTHORIZED", "RELEASE_FAILED", "RELEASED", "CLOSED"}
    if stage != "REQUIREMENTS_CONFIRMED" and (
        "requirementsAcceptedAt" not in feature
        or "requirementsMessageId" not in feature
    ):
        raise WorkflowError(
            "invalid_state", f"{field} lacks accepted requirements authority"
        )
    if stage in plan_required and "plan" not in feature:
        raise WorkflowError("invalid_state", f"{field} lacks a plan snapshot")
    if stage in plan_result_required and "planResultMessageId" not in feature:
        raise WorkflowError("invalid_state", f"{field} lacks plan approval authority")
    if stage in pull_required and "pullRequest" not in feature:
        raise WorkflowError("invalid_state", f"{field} lacks a pull request snapshot")
    if (
        stage in {"MERGE_READY", *merge_required}
        and "codeResultMessageId" not in feature
    ):
        raise WorkflowError("invalid_state", f"{field} lacks code review authority")
    if stage in merge_required and "merge" not in feature:
        raise WorkflowError("invalid_state", f"{field} lacks merge proof")
    if stage in release_required and "release" not in feature:
        raise WorkflowError("invalid_state", f"{field} lacks release authorization")
    if stage in {"RELEASED", "CLOSED"} and (
        not release_result
        or not all(item["status"] == "PUBLISHED" for item in release_result["targets"])
    ):
        raise WorkflowError(
            "invalid_state", f"{field} lacks all-target release success"
        )
    if stage == "CLOSED" and "closure" not in feature:
        raise WorkflowError("invalid_state", f"{field} lacks closure proof")
    return feature


def validate_dispatch_record(
    value: Any,
    message_id: str,
    config: Mapping[str, Any],
    features: Mapping[str, Any],
) -> dict[str, Any]:
    field = f"state.dispatches.{message_id}"
    require_digest(message_id, "dispatch message key")
    record = exact_keys(
        value,
        field,
        {
            "type",
            "featureId",
            "cycle",
            "payloadDigest",
            "payload",
            "status",
            "preparedAt",
        },
        {
            "dispatchedAt",
            "delivery_failedAt",
            "acceptedAt",
            "appliedAt",
            "failureReason",
        },
    )
    if record["type"] not in MESSAGE_TYPES or record["status"] not in DISPATCH_STATUSES:
        raise WorkflowError("invalid_state", f"{field} type/status is unsupported")
    if record["featureId"] not in features:
        raise WorkflowError("invalid_state", f"{field} references an unknown feature")
    require_int(record["cycle"], f"{field}.cycle", minimum=1)
    require_digest(record["payloadDigest"], f"{field}.payloadDigest")
    payload = validate_contract_payload(record["payload"], record["type"])
    if (
        payload["messageId"] != message_id
        or payload["featureId"] != record["featureId"]
        or payload["cycle"] != record["cycle"]
        or payload["workflowId"] != config["workflowId"]
        or payload["repositoryKey"] != config["repository"]["key"]
        or digest(payload) != record["payloadDigest"]
    ):
        raise WorkflowError("invalid_state", f"{field} payload ledger is inconsistent")
    require_timestamp(record["preparedAt"], f"{field}.preparedAt")
    timestamp_for_status = {
        "dispatched": "dispatchedAt",
        "delivery_failed": "delivery_failedAt",
        "accepted": "acceptedAt",
        "applied": "appliedAt",
    }
    required_timestamp = timestamp_for_status.get(record["status"])
    if required_timestamp and required_timestamp not in record:
        raise WorkflowError("invalid_state", f"{field} lacks {required_timestamp}")
    for name in ("dispatchedAt", "delivery_failedAt", "acceptedAt", "appliedAt"):
        if name in record:
            require_timestamp(record[name], f"{field}.{name}")
    if "failureReason" in record:
        require_string(record["failureReason"], f"{field}.failureReason", maximum=300)
    if record["status"] == "delivery_failed" and "failureReason" not in record:
        raise WorkflowError("invalid_state", f"{field} lacks failureReason")
    return record


def validate_state(value: Any, config: Mapping[str, Any]) -> dict[str, Any]:
    state = exact_keys(
        value,
        "state",
        {
            "schemaVersion",
            "workflowId",
            "bootstrap",
            "features",
            "developmentQueue",
            "activeGoal",
            "dispatches",
            "updatedAt",
        },
    )
    if (
        require_int(state["schemaVersion"], "state.schemaVersion", minimum=1)
        != STATE_SCHEMA_VERSION
    ):
        raise WorkflowError("unsupported_schema", "Unsupported state schema version")
    if state["workflowId"] != config["workflowId"]:
        raise WorkflowError("invalid_state", "State workflow ID does not match config")
    bootstrap = exact_keys(state["bootstrap"], "state.bootstrap", set(ROLES))
    for role in ROLES:
        require_bool(bootstrap[role], f"state.bootstrap.{role}")
    features = require_object(state["features"], "state.features")
    occupied_runs: list[tuple[str, str]] = []
    for feature_id, feature_value in features.items():
        require_feature_id(feature_id, "state feature key")
        feature = validate_feature_record(feature_value, feature_id, config)
        runs = feature.get("goalRuns", [])
        if not isinstance(runs, list):
            raise WorkflowError(
                "invalid_state", f"Feature {feature_id} goalRuns must be array"
            )
        seen: set[str] = set()
        for index, run_value in enumerate(runs):
            run = validate_goal_run(
                run_value, f"state.features.{feature_id}.goalRuns[{index}]"
            )
            if run["goalRunId"] in seen:
                raise WorkflowError("invalid_state", "Duplicate GoalRun ID")
            seen.add(run["goalRunId"])
            if run["status"] in {"ACTIVE", "BLOCKED"}:
                occupied_runs.append((feature_id, run["goalRunId"]))
    queue = state["developmentQueue"]
    if not isinstance(queue, list) or len(queue) != len(set(queue)):
        raise WorkflowError(
            "invalid_state", "developmentQueue must contain unique feature IDs"
        )
    for item in queue:
        if item not in features:
            raise WorkflowError(
                "invalid_state", "developmentQueue references unknown feature"
            )
        if features[item]["stage"] != "DEVELOPMENT_QUEUED":
            raise WorkflowError(
                "invalid_state", "developmentQueue feature is not queued"
            )
    for feature_id, feature in features.items():
        if feature["stage"] == "DEVELOPMENT_QUEUED" and feature_id not in queue:
            raise WorkflowError(
                "invalid_state", "Queued feature is missing from developmentQueue"
            )
    active = state["activeGoal"]
    if active is None:
        if occupied_runs:
            raise WorkflowError(
                "invalid_state", "ACTIVE or BLOCKED GoalRun exists without activeGoal"
            )
    else:
        active_obj = exact_keys(active, "state.activeGoal", {"featureId", "goalRunId"})
        pair = (active_obj["featureId"], active_obj["goalRunId"])
        if occupied_runs != [pair]:
            raise WorkflowError(
                "invalid_state",
                "activeGoal must identify the only ACTIVE or BLOCKED GoalRun",
            )
        active_feature = features.get(active_obj["featureId"])
        if not active_feature:
            raise WorkflowError(
                "invalid_state", "activeGoal references unknown feature"
            )
        active_run = next(
            (
                run
                for run in active_feature["goalRuns"]
                if run["goalRunId"] == active_obj["goalRunId"]
            ),
            None,
        )
        if active_run is None:
            raise WorkflowError(
                "invalid_state", "activeGoal run is missing from its feature"
            )
        expected_stage = (
            "DEVELOPMENT_BLOCKED"
            if active_run["status"] == "BLOCKED"
            else "DEVELOPMENT_ACTIVE"
        )
        if active_feature["stage"] != expected_stage:
            raise WorkflowError(
                "invalid_state", "activeGoal status and feature stage differ"
            )
    dispatches = require_object(state["dispatches"], "state.dispatches")
    for message_id, record in dispatches.items():
        validate_dispatch_record(record, message_id, config, features)
    require_timestamp(state["updatedAt"], "state.updatedAt")
    return state


def migrate_state_v1(value: Any) -> tuple[dict[str, Any], bool]:
    state = require_object(value, "state")
    version = state.get("schemaVersion")
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        return dict(state), False
    migrated = require_object(json.loads(canonical_json(state)), "state")
    features = migrated.get("features")
    if isinstance(features, dict):
        for feature_value in features.values():
            if not isinstance(feature_value, dict):
                continue
            release = feature_value.get("release")
            if (
                not isinstance(release, dict)
                or "result" not in release
                or "lastSubmission" not in release
                or "submissions" in release
            ):
                continue
            result = release.get("result")
            last_submission = release.get("lastSubmission")
            authorization = release.get("authorization")
            if (
                not isinstance(result, dict)
                or not isinstance(last_submission, dict)
                or not isinstance(authorization, dict)
                or not isinstance(result.get("targets"), list)
                or not isinstance(last_submission.get("targets"), list)
                or not isinstance(authorization.get("targets"), list)
            ):
                continue
            result_targets = {
                item.get("targetId"): item
                for item in result["targets"]
                if isinstance(item, dict)
            }
            last_ids = {
                item.get("targetId")
                for item in last_submission["targets"]
                if isinstance(item, dict)
            }
            authorization_targets = {
                item.get("targetId"): item
                for item in authorization["targets"]
                if isinstance(item, dict)
            }
            if last_ids == set(result_targets):
                release["submissions"] = [last_submission]
                continue
            initial_targets: list[dict[str, Any]] = []
            for target_id, result_item in result_targets.items():
                if target_id in last_ids:
                    target = authorization_targets.get(target_id)
                    if not isinstance(target, dict):
                        initial_targets = []
                        break
                    initial_targets.append(
                        {
                            "targetId": target_id,
                            "kind": target.get("kind"),
                            "status": "FAILED",
                            "error": (
                                "Migrated from state schema v1; prior failure "
                                "detail is unavailable."
                            ),
                        }
                    )
                else:
                    initial_targets.append(result_item)
            if not initial_targets:
                continue
            initial_targets.sort(key=lambda item: str(item.get("targetId")))
            initial_submission = {
                "authorizationId": authorization.get("authorizationId"),
                "targets": initial_targets,
                "publishedAt": result.get("publishedAt"),
            }
            initial_submission["submissionDigest"] = digest(initial_submission)
            release["submissions"] = [initial_submission, last_submission]
    migrated["schemaVersion"] = STATE_SCHEMA_VERSION
    migrated["updatedAt"] = utc_now()
    return migrated, True


def load_state_locked(
    paths: Mapping[str, Path], config: Mapping[str, Any]
) -> dict[str, Any]:
    state, migrated = migrate_state_v1(load_json(paths["state"], "state"))
    validated = validate_state(state, config)
    if migrated:
        atomic_write(paths["state"], validated)
    return validated


def load_context(
    repo_arg: str,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any], dict[str, Any]]:
    repository = resolve_repository(repo_arg)
    paths = state_paths(repository)
    config = validate_config(load_json(paths["config"], "config"), repository)
    with locked(paths["lock"]):
        state = load_state_locked(paths, config)
    return repository, paths, config, state


def save_state(
    paths: Mapping[str, Path], state: dict[str, Any], config: Mapping[str, Any]
) -> None:
    state["updatedAt"] = utc_now()
    validate_state(state, config)
    atomic_write(paths["state"], state)


def role_for_task(config: Mapping[str, Any], task_id: str) -> str:
    matches = [role for role in ROLES if config["tasks"][role] == task_id]
    if len(matches) != 1:
        raise WorkflowError(
            "task_role_mismatch", "Task ID is not bound to this workflow"
        )
    return matches[0]


def require_role(config: Mapping[str, Any], task_id: str, role: str) -> None:
    if role_for_task(config, require_string(task_id, "taskId", maximum=200)) != role:
        raise WorkflowError(
            "task_role_mismatch", f"Command requires configured {role} task"
        )
    if not config:
        raise WorkflowError("workflow_not_initialized", "Workflow is not initialized")


def read_committed(root: Path, commit_sha: str, relative_path: str) -> bytes:
    sha = require_sha(commit_sha, "commitSha")
    path = require_repo_path(relative_path, "path")
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{sha}:{path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorkflowError(
            "snapshot_mismatch", f"Committed artifact is missing: {path}"
        )
    return result.stdout


def artifact_snapshot(
    root: Path, commit_sha: str, relative_path: str
) -> dict[str, str]:
    path = require_repo_path(relative_path, "artifact.path")
    sha = require_sha(commit_sha, "artifact.commitSha")
    content = read_committed(root, sha, path)
    return {
        "path": path,
        "commitSha": sha,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def validate_artifact(
    value: Any, field: str, root: Path | None = None
) -> dict[str, Any]:
    artifact = exact_keys(value, field, {"path", "commitSha", "sha256"})
    require_repo_path(artifact["path"], f"{field}.path")
    require_sha(artifact["commitSha"], f"{field}.commitSha")
    require_digest(artifact["sha256"], f"{field}.sha256")
    if root is not None:
        actual = artifact_snapshot(root, artifact["commitSha"], artifact["path"])
        if actual != artifact:
            raise WorkflowError(
                "snapshot_mismatch", f"{field} does not match committed content"
            )
    return artifact


def verify_branch_tip(root: Path, branch: str, commit_sha: str) -> None:
    require_string(branch, "report.branch", maximum=240)
    if not branch.startswith("codex/review-records/"):
        raise WorkflowError(
            "invalid_payload", "Review report branch must use codex/review-records/"
        )
    candidates = (f"refs/remotes/origin/{branch}", f"refs/heads/{branch}")
    tips = [run_git(root, "rev-parse", ref, check=False) for ref in candidates]
    if commit_sha not in tips:
        raise WorkflowError(
            "review_record_conflict",
            "Report commit is not the exact review-record branch tip",
        )


def verify_ancestor(root: Path, ancestor_sha: str, descendant_sha: str) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "merge-base",
            "--is-ancestor",
            ancestor_sha,
            descendant_sha,
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorkflowError(
            "review_record_conflict",
            "Review report branch is not based on the requested immutable snapshot",
        )


def verify_remote_branch_tip(root: Path, branch: str, commit_sha: str) -> None:
    sha = require_sha(commit_sha, "requirementsCommitSha")
    output = run_git(
        root,
        "ls-remote",
        "--exit-code",
        "--heads",
        "origin",
        f"refs/heads/{branch}",
    )
    matches = [line.split() for line in output.splitlines() if line.strip()]
    if matches != [[sha, f"refs/heads/{branch}"]]:
        raise WorkflowError(
            "snapshot_mismatch",
            "Requirements commit is not the exact authoritative origin branch tip",
        )


def validate_report(value: Any, field: str, root: Path) -> dict[str, Any]:
    report = exact_keys(
        value,
        field,
        {"branch", "path", "commitSha", "sha256"},
        {"jsonPath", "jsonSha256"},
    )
    require_sha(report["commitSha"], f"{field}.commitSha")
    require_digest(report["sha256"], f"{field}.sha256")
    snapshot = artifact_snapshot(root, report["commitSha"], report["path"])
    if snapshot["sha256"] != report["sha256"]:
        raise WorkflowError("snapshot_mismatch", f"{field} Markdown digest mismatch")
    if ("jsonPath" in report) != ("jsonSha256" in report):
        raise WorkflowError(
            "invalid_payload", f"{field} JSON path and digest must appear together"
        )
    if "jsonPath" in report:
        json_snapshot = artifact_snapshot(root, report["commitSha"], report["jsonPath"])
        if json_snapshot["sha256"] != require_digest(
            report["jsonSha256"], f"{field}.jsonSha256"
        ):
            raise WorkflowError("snapshot_mismatch", f"{field} JSON digest mismatch")
    verify_branch_tip(root, report["branch"], report["commitSha"])
    return report


def validate_artifact_shape(value: Any, field: str) -> dict[str, Any]:
    return validate_artifact(value, field)


def validate_report_shape(value: Any, field: str) -> dict[str, Any]:
    report = exact_keys(
        value,
        field,
        {"branch", "path", "commitSha", "sha256"},
        {"jsonPath", "jsonSha256"},
    )
    if not require_string(report["branch"], f"{field}.branch", maximum=240).startswith(
        "codex/review-records/"
    ):
        raise WorkflowError(
            "invalid_payload", f"{field}.branch must use codex/review-records/"
        )
    require_repo_path(report["path"], f"{field}.path")
    require_sha(report["commitSha"], f"{field}.commitSha")
    require_digest(report["sha256"], f"{field}.sha256")
    if ("jsonPath" in report) != ("jsonSha256" in report):
        raise WorkflowError(
            "invalid_payload", f"{field} JSON path and digest must appear together"
        )
    if "jsonPath" in report:
        require_repo_path(report["jsonPath"], f"{field}.jsonPath")
        require_digest(report["jsonSha256"], f"{field}.jsonSha256")
    return report


def validate_findings(value: Any, field: str) -> dict[str, int]:
    findings = exact_keys(value, field, {"blocker", "major", "minor"})
    for name in ("blocker", "major", "minor"):
        require_int(findings[name], f"{field}.{name}")
    return findings


def validate_plan_shape(value: Any, field: str) -> dict[str, Any]:
    plan = exact_keys(
        value,
        field,
        {
            "requirements",
            "design",
            "implementationPlan",
            "planCommitSha",
            "compositeSha256",
        },
    )
    commit = require_sha(plan["planCommitSha"], f"{field}.planCommitSha")
    artifacts = [
        validate_artifact_shape(plan["requirements"], f"{field}.requirements"),
        validate_artifact_shape(plan["design"], f"{field}.design"),
        validate_artifact_shape(
            plan["implementationPlan"], f"{field}.implementationPlan"
        ),
    ]
    if any(item["commitSha"] != commit for item in artifacts):
        raise WorkflowError(
            "invalid_payload", f"{field} artifacts must use planCommitSha"
        )
    if require_digest(plan["compositeSha256"], f"{field}.compositeSha256") != digest(
        artifacts
    ):
        raise WorkflowError(
            "invalid_payload", f"{field}.compositeSha256 does not match artifacts"
        )
    return plan


def validate_pull_request_shape(value: Any, field: str) -> dict[str, Any]:
    pull = exact_keys(
        value, field, {"number", "url", "baseRef", "baseSha", "headRef", "headSha"}
    )
    require_int(pull["number"], f"{field}.number", minimum=1)
    require_https_url(pull["url"], f"{field}.url", host="github.com")
    require_string(pull["baseRef"], f"{field}.baseRef", maximum=240)
    require_sha(pull["baseSha"], f"{field}.baseSha")
    require_string(pull["headRef"], f"{field}.headRef", maximum=240)
    require_sha(pull["headSha"], f"{field}.headSha")
    return pull


def validate_merge_policy_shape(value: Any, field: str) -> dict[str, Any]:
    policy = exact_keys(
        value,
        field,
        {"mode", "method", "deleteBranch", "requireGreenChecks", "requireExactHead"},
    )
    if policy["mode"] not in MERGE_MODES or policy["method"] not in MERGE_METHODS:
        raise WorkflowError(
            "invalid_payload", f"{field} contains unsupported merge policy"
        )
    require_bool(policy["deleteBranch"], f"{field}.deleteBranch")
    if (
        require_bool(policy["requireGreenChecks"], f"{field}.requireGreenChecks")
        is not True
    ):
        raise WorkflowError(
            "invalid_payload", f"{field}.requireGreenChecks must be true"
        )
    if (
        require_bool(policy["requireExactHead"], f"{field}.requireExactHead")
        is not True
    ):
        raise WorkflowError("invalid_payload", f"{field}.requireExactHead must be true")
    return policy


def validate_routed_body(
    message_type: str,
    body_value: Any,
    feature_id: str,
    cycle: int,
) -> dict[str, Any]:
    field = f"{message_type}.body"
    if message_type == "RequirementsHandoff":
        body = exact_keys(
            body_value,
            field,
            {"title", "branch", "requirements", "confirmation"},
        )
        require_string(body["title"], f"{field}.title", maximum=200)
        require_string(body["branch"], f"{field}.branch", maximum=240)
        validate_artifact_shape(body["requirements"], f"{field}.requirements")
        confirmation = exact_keys(
            body["confirmation"],
            f"{field}.confirmation",
            {"status", "confirmedBy", "confirmedAt", "evidence"},
        )
        if confirmation["status"] != "CONFIRMED":
            raise WorkflowError(
                "requirements_unconfirmed", "Requirements status must be CONFIRMED"
            )
        require_string(
            confirmation["confirmedBy"],
            f"{field}.confirmation.confirmedBy",
            maximum=200,
        )
        require_timestamp(
            confirmation["confirmedAt"], f"{field}.confirmation.confirmedAt"
        )
        require_string(
            confirmation["evidence"], f"{field}.confirmation.evidence", maximum=300
        )
        return body
    if message_type == "TechnicalPlanReviewRequest":
        body = exact_keys(
            body_value,
            field,
            {"plan", "reviewRecordBranch", "acceptanceCriteriaDigest"},
            {"previousResultMessageId"},
        )
        plan = validate_plan_shape(body["plan"], f"{field}.plan")
        expected = (
            f"codex/review-records/{feature_id}/plan-{cycle}-"
            f"{plan['planCommitSha'][:12]}"
        )
        if body["reviewRecordBranch"] != expected:
            raise WorkflowError(
                "invalid_payload", f"{field}.reviewRecordBranch is not deterministic"
            )
        require_digest(
            body["acceptanceCriteriaDigest"], f"{field}.acceptanceCriteriaDigest"
        )
        if "previousResultMessageId" in body:
            require_digest(
                body["previousResultMessageId"], f"{field}.previousResultMessageId"
            )
        return body
    if message_type == "TechnicalPlanReviewResult":
        body = exact_keys(
            body_value,
            field,
            {
                "requestMessageId",
                "reviewedPlan",
                "decision",
                "findings",
                "report",
                "summary",
            },
        )
        require_digest(body["requestMessageId"], f"{field}.requestMessageId")
        reviewed = exact_keys(
            body["reviewedPlan"],
            f"{field}.reviewedPlan",
            {"planCommitSha", "compositeSha256"},
        )
        require_sha(reviewed["planCommitSha"], f"{field}.reviewedPlan.planCommitSha")
        require_digest(
            reviewed["compositeSha256"], f"{field}.reviewedPlan.compositeSha256"
        )
        if body["decision"] not in {"PASS", "FAIL"}:
            raise WorkflowError("invalid_payload", f"{field}.decision is unsupported")
        findings = validate_findings(body["findings"], f"{field}.findings")
        if body["decision"] == "PASS" and (findings["blocker"] or findings["major"]):
            raise WorkflowError(
                "invalid_payload", "PASS requires zero blocker and major findings"
            )
        validate_report_shape(body["report"], f"{field}.report")
        require_string(body["summary"], f"{field}.summary", maximum=500)
        return body
    if message_type == "CodeReviewRequest":
        body = exact_keys(
            body_value,
            field,
            {"pullRequest", "reviewRecordBranch", "mergePolicy"},
            {"previousResultMessageId"},
        )
        pull = validate_pull_request_shape(body["pullRequest"], f"{field}.pullRequest")
        expected = (
            f"codex/review-records/{feature_id}/code-{cycle}-{pull['headSha'][:12]}"
        )
        if body["reviewRecordBranch"] != expected:
            raise WorkflowError(
                "invalid_payload", f"{field}.reviewRecordBranch is not deterministic"
            )
        validate_merge_policy_shape(body["mergePolicy"], f"{field}.mergePolicy")
        if "previousResultMessageId" in body:
            require_digest(
                body["previousResultMessageId"], f"{field}.previousResultMessageId"
            )
        return body
    if message_type == "CodeReviewResult":
        body = exact_keys(
            body_value,
            field,
            {
                "requestMessageId",
                "reviewedPullRequest",
                "decision",
                "findings",
                "report",
                "checks",
                "merge",
                "summary",
            },
        )
        require_digest(body["requestMessageId"], f"{field}.requestMessageId")
        validate_pull_request_shape(
            body["reviewedPullRequest"], f"{field}.reviewedPullRequest"
        )
        if body["decision"] not in {"APPROVE", "COMMENT", "REQUEST_CHANGES"}:
            raise WorkflowError("invalid_payload", f"{field}.decision is unsupported")
        findings = validate_findings(body["findings"], f"{field}.findings")
        if body["decision"] == "APPROVE" and findings["blocker"]:
            raise WorkflowError(
                "invalid_payload", "APPROVE cannot contain blocker findings"
            )
        validate_report_shape(body["report"], f"{field}.report")
        checks = exact_keys(
            body["checks"],
            f"{field}.checks",
            {"status", "checkedAt"},
            {"detailsUrl"},
        )
        if checks["status"] not in {"PASSING", "FAILING", "PENDING", "UNAVAILABLE"}:
            raise WorkflowError(
                "invalid_payload", f"{field}.checks.status is unsupported"
            )
        require_timestamp(checks["checkedAt"], f"{field}.checks.checkedAt")
        if "detailsUrl" in checks:
            require_https_url(checks["detailsUrl"], f"{field}.checks.detailsUrl")
        merge_value = require_object(body["merge"], f"{field}.merge")
        status = merge_value.get("status")
        if status == "MERGED":
            merge = exact_keys(
                merge_value,
                f"{field}.merge",
                {"status", "method", "url", "sha", "mergedAt"},
            )
            if body["decision"] != "APPROVE" or checks["status"] != "PASSING":
                raise WorkflowError(
                    "invalid_payload", "MERGED requires APPROVE and PASSING checks"
                )
            if merge["method"] not in MERGE_METHODS:
                raise WorkflowError(
                    "invalid_payload", f"{field}.merge.method is unsupported"
                )
            require_https_url(merge["url"], f"{field}.merge.url", host="github.com")
            require_sha(merge["sha"], f"{field}.merge.sha")
            require_timestamp(merge["mergedAt"], f"{field}.merge.mergedAt")
        elif status == "FAILED":
            merge = exact_keys(merge_value, f"{field}.merge", {"status", "error"})
            if body["decision"] != "APPROVE" or checks["status"] != "PASSING":
                raise WorkflowError(
                    "invalid_payload",
                    "FAILED merge requires APPROVE and PASSING checks",
                )
            require_string(merge["error"], f"{field}.merge.error", maximum=300)
        elif status == "READY":
            exact_keys(merge_value, f"{field}.merge", {"status"})
            if body["decision"] != "APPROVE" or checks["status"] != "PASSING":
                raise WorkflowError(
                    "invalid_payload", "READY requires APPROVE and PASSING checks"
                )
        elif status == "NOT_REQUESTED":
            exact_keys(merge_value, f"{field}.merge", {"status"})
            if body["decision"] == "APPROVE":
                raise WorkflowError(
                    "invalid_payload",
                    "APPROVE requires READY, MERGED, or FAILED merge status",
                )
        elif status == "STALE":
            exact_keys(merge_value, f"{field}.merge", {"status"})
            if body["decision"] != "COMMENT":
                raise WorkflowError(
                    "invalid_payload",
                    "STALE requires a non-authorizing COMMENT decision",
                )
        else:
            raise WorkflowError(
                "invalid_payload", f"{field}.merge.status is unsupported"
            )
        require_string(body["summary"], f"{field}.summary", maximum=500)
        return body
    raise WorkflowError(
        "invalid_payload", f"Unsupported routed contract type {message_type}"
    )


def validate_release_authorization_shape(value: Any) -> dict[str, Any]:
    draft = exact_keys(
        value,
        "ReleaseAuthorization",
        {
            "schemaVersion",
            "workflowId",
            "featureId",
            "mergeCommitSha",
            "version",
            "tag",
            "targets",
            "authorizedBy",
            "authorizationEvidence",
            "createdAt",
        },
        {"authorizationId"},
    )
    if draft["schemaVersion"] != SCHEMA_VERSION:
        raise WorkflowError(
            "unsupported_schema", "ReleaseAuthorization schema must be 1"
        )
    try:
        uuid.UUID(require_string(draft["workflowId"], "workflowId", maximum=36))
    except ValueError as exc:
        raise WorkflowError("invalid_payload", "workflowId must be UUID") from exc
    require_feature_id(draft["featureId"])
    require_sha(draft["mergeCommitSha"], "mergeCommitSha")
    require_semver(draft["version"], "version")
    require_string(draft["tag"], "tag", maximum=200)
    if not isinstance(draft["targets"], list) or not draft["targets"]:
        raise WorkflowError("invalid_payload", "targets must be a non-empty array")
    targets: list[dict[str, Any]] = []
    for index, target_value in enumerate(draft["targets"]):
        target_obj = require_object(target_value, f"targets[{index}]")
        repository_key = target_obj.get("repositoryKey", "contract/shape")
        targets.append(
            normalize_target(target_obj, f"targets[{index}]", repository_key)
        )
    if len({target["targetId"] for target in targets}) != len(targets):
        raise WorkflowError("invalid_payload", "Release targets must be unique")
    require_string(draft["authorizedBy"], "authorizedBy", maximum=200)
    require_string(draft["authorizationEvidence"], "authorizationEvidence", maximum=500)
    require_timestamp(draft["createdAt"], "createdAt")
    if "authorizationId" in draft:
        normalized = {
            "schemaVersion": SCHEMA_VERSION,
            "workflowId": draft["workflowId"],
            "featureId": draft["featureId"],
            "mergeCommitSha": draft["mergeCommitSha"],
            "version": draft["version"],
            "tag": draft["tag"],
            "targets": sorted(targets, key=lambda item: item["targetId"]),
            "authorizedBy": draft["authorizedBy"].strip(),
            "authorizationEvidence": draft["authorizationEvidence"].strip(),
            "createdAt": draft["createdAt"],
        }
        if require_digest(draft["authorizationId"], "authorizationId") != digest(
            normalized
        ):
            raise WorkflowError(
                "invalid_payload", "authorizationId does not match authorization"
            )
    return draft


def validate_release_result_shape(value: Any) -> dict[str, Any]:
    result = exact_keys(
        value,
        "ReleaseResult",
        {
            "schemaVersion",
            "workflowId",
            "featureId",
            "authorizationId",
            "mergeCommitSha",
            "version",
            "tag",
            "targets",
            "publishedAt",
        },
        {"proofDigest"},
    )
    if result["schemaVersion"] != SCHEMA_VERSION:
        raise WorkflowError("unsupported_schema", "ReleaseResult schema must be 1")
    try:
        uuid.UUID(require_string(result["workflowId"], "workflowId", maximum=36))
    except ValueError as exc:
        raise WorkflowError("invalid_payload", "workflowId must be UUID") from exc
    require_feature_id(result["featureId"])
    require_digest(result["authorizationId"], "authorizationId")
    require_sha(result["mergeCommitSha"], "mergeCommitSha")
    require_semver(result["version"], "version")
    require_string(result["tag"], "tag", maximum=200)
    if not isinstance(result["targets"], list) or not result["targets"]:
        raise WorkflowError("invalid_payload", "targets must be a non-empty array")
    target_ids: set[str] = set()
    for index, value_item in enumerate(result["targets"]):
        item = require_object(value_item, f"targets[{index}]")
        target_id = require_digest(item.get("targetId"), f"targets[{index}].targetId")
        if target_id in target_ids:
            raise WorkflowError(
                "invalid_payload", "Release result target IDs must be unique"
            )
        target_ids.add(target_id)
        kind = item.get("kind")
        status = item.get("status")
        if kind not in {"GITHUB_RELEASE", "PYPI"}:
            raise WorkflowError(
                "invalid_payload", f"targets[{index}].kind is unsupported"
            )
        if status == "FAILED":
            exact_keys(
                item, f"targets[{index}]", {"targetId", "kind", "status", "error"}
            )
            require_string(item["error"], f"targets[{index}].error", maximum=300)
        elif status == "PUBLISHED" and kind == "GITHUB_RELEASE":
            exact_keys(
                item,
                f"targets[{index}]",
                {
                    "targetId",
                    "kind",
                    "status",
                    "artifacts",
                    "publishedAt",
                    "releaseUrl",
                    "tagCommitSha",
                },
            )
            normalize_result_artifacts(item["artifacts"], f"targets[{index}].artifacts")
            require_timestamp(item["publishedAt"], f"targets[{index}].publishedAt")
            require_https_url(
                item["releaseUrl"], f"targets[{index}].releaseUrl", host="github.com"
            )
            require_sha(item["tagCommitSha"], f"targets[{index}].tagCommitSha")
        elif status == "PUBLISHED" and kind == "PYPI":
            exact_keys(
                item,
                f"targets[{index}]",
                {
                    "targetId",
                    "kind",
                    "status",
                    "artifacts",
                    "publishedAt",
                    "projectUrl",
                    "repository",
                    "projectName",
                    "version",
                },
            )
            normalize_result_artifacts(item["artifacts"], f"targets[{index}].artifacts")
            require_timestamp(item["publishedAt"], f"targets[{index}].publishedAt")
            require_https_url(item["projectUrl"], f"targets[{index}].projectUrl")
            if item["repository"] not in {"PYPI", "TEST_PYPI"}:
                raise WorkflowError(
                    "invalid_payload", f"targets[{index}].repository is unsupported"
                )
            require_string(
                item["projectName"], f"targets[{index}].projectName", maximum=200
            )
            require_semver(item["version"], f"targets[{index}].version")
        else:
            raise WorkflowError(
                "invalid_payload", f"targets[{index}].status is unsupported"
            )
    require_timestamp(result["publishedAt"], "publishedAt")
    if "proofDigest" in result:
        proof_value = {
            key: item for key, item in result.items() if key != "proofDigest"
        }
        if require_digest(result["proofDigest"], "proofDigest") != digest(proof_value):
            raise WorkflowError(
                "invalid_payload", "proofDigest does not match release result"
            )
    return result


def validate_closure_shape(value: Any) -> dict[str, Any]:
    closure = exact_keys(
        value,
        "ClosureRecord",
        {
            "releaseResultId",
            "requirementsMessageId",
            "planReviewResultMessageId",
            "codeReviewResultMessageId",
            "mergeCommitSha",
            "releaseTargets",
            "scenariosSolved",
            "followUps",
            "closedAt",
            "closureId",
        },
    )
    for name in (
        "releaseResultId",
        "requirementsMessageId",
        "planReviewResultMessageId",
        "codeReviewResultMessageId",
    ):
        require_digest(closure[name], name)
    require_sha(closure["mergeCommitSha"], "mergeCommitSha")
    if not isinstance(closure["releaseTargets"], list) or not closure["releaseTargets"]:
        raise WorkflowError("invalid_payload", "releaseTargets must be non-empty")
    if len(set(closure["releaseTargets"])) != len(closure["releaseTargets"]):
        raise WorkflowError("invalid_payload", "releaseTargets must be unique")
    for index, target_id in enumerate(closure["releaseTargets"]):
        require_digest(target_id, f"releaseTargets[{index}]")
    if (
        not isinstance(closure["scenariosSolved"], list)
        or not closure["scenariosSolved"]
    ):
        raise WorkflowError("invalid_payload", "scenariosSolved must be non-empty")
    if not isinstance(closure["followUps"], list):
        raise WorkflowError("invalid_payload", "followUps must be an array")
    for index, item in enumerate(closure["scenariosSolved"]):
        require_string(item, f"scenariosSolved[{index}]", maximum=300)
    for index, item in enumerate(closure["followUps"]):
        require_string(item, f"followUps[{index}]", maximum=300)
    require_timestamp(closure["closedAt"], "closedAt")
    authority = {key: item for key, item in closure.items() if key != "closureId"}
    if require_digest(closure["closureId"], "closureId") != digest(authority):
        raise WorkflowError("invalid_payload", "closureId does not match closure")
    return closure


def validate_contract_payload(value: Any, contract_name: str) -> dict[str, Any]:
    if contract_name in MESSAGE_TYPES:
        message = exact_keys(
            value,
            contract_name,
            {
                "schemaVersion",
                "type",
                "workflowId",
                "messageId",
                "featureId",
                "repositoryKey",
                "routing",
                "cycle",
                "createdAt",
                "body",
            },
        )
        if (
            message["schemaVersion"] != SCHEMA_VERSION
            or message["type"] != contract_name
        ):
            raise WorkflowError(
                "invalid_payload", f"Expected {contract_name} schema v1"
            )
        try:
            uuid.UUID(require_string(message["workflowId"], "workflowId", maximum=36))
        except ValueError as exc:
            raise WorkflowError("invalid_payload", "workflowId must be UUID") from exc
        require_feature_id(message["featureId"])
        require_digest(message["messageId"], "messageId")
        repository_key = require_string(
            message["repositoryKey"], "repositoryKey", maximum=300
        )
        if repository_key.count("/") != 1:
            raise WorkflowError(
                "invalid_payload", "repositoryKey must be owner/repository"
            )
        route = exact_keys(
            message["routing"], "routing", {"sourceTaskId", "destinationTaskId"}
        )
        source = require_string(
            route["sourceTaskId"], "routing.sourceTaskId", maximum=200
        )
        destination = require_string(
            route["destinationTaskId"], "routing.destinationTaskId", maximum=200
        )
        if source == destination:
            raise WorkflowError("invalid_payload", "routing task IDs must differ")
        cycle = require_int(message["cycle"], "cycle", minimum=1)
        require_timestamp(message["createdAt"], "createdAt")
        validate_routed_body(
            contract_name, message["body"], message["featureId"], cycle
        )
        if digest(message_authority(message)) != message["messageId"]:
            raise WorkflowError(
                "invalid_payload", "messageId does not match canonical authority"
            )
        return message
    if contract_name == "ReleaseAuthorization":
        return validate_release_authorization_shape(value)
    if contract_name == "ReleaseResult":
        return validate_release_result_shape(value)
    if contract_name == "ClosureRecord":
        return validate_closure_shape(value)
    raise WorkflowError("invalid_payload", f"Unsupported contract {contract_name}")


def parse_requirements_metadata(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkflowError(
            "invalid_requirements", "Requirements must be UTF-8 Markdown"
        ) from exc
    names = ("Status", "FeatureId", "Branch", "ConfirmedBy", "ConfirmedAt")
    matches: list[tuple[int, str, str]] = []
    metadata_pattern = re.compile(
        r"^-\s*(Status|FeatureId|Branch|ConfirmedBy|ConfirmedAt):\s*(.*?)\s*$"
    )
    for index, line in enumerate(text.splitlines()):
        match = metadata_pattern.fullmatch(line)
        if match:
            matches.append((index, match.group(1), match.group(2).strip()))
    counts = {name: sum(item[1] == name for item in matches) for name in names}
    if any(counts[name] != 1 for name in names):
        raise WorkflowError(
            "invalid_requirements",
            "Requirements metadata fields must each appear exactly once",
        )
    line_numbers = [item[0] for item in matches]
    if (
        [item[1] for item in matches] != list(names)
        or line_numbers != list(range(line_numbers[0], line_numbers[0] + len(names)))
        or line_numbers[0] >= 40
    ):
        raise WorkflowError(
            "invalid_requirements",
            "Requirements metadata must be one ordered contiguous block near the top",
        )
    fields = {name: value for _, name, value in matches}
    if fields.get("Status") != "Confirmed":
        raise WorkflowError(
            "requirements_unconfirmed", "Requirements status must be Confirmed"
        )
    for name in ("FeatureId", "Branch", "ConfirmedBy", "ConfirmedAt"):
        if not fields.get(name):
            raise WorkflowError(
                "requirements_unconfirmed", f"Requirements metadata {name} is required"
            )
    require_feature_id(fields["FeatureId"], "requirements.FeatureId")
    require_timestamp(fields["ConfirmedAt"], "requirements.ConfirmedAt")
    return fields


def message_authority(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"messageId", "createdAt"}
    }


def validate_routing(
    value: Any, field: str, config: Mapping[str, Any], source: str, destination: str
) -> dict[str, Any]:
    route = exact_keys(value, field, {"sourceTaskId", "destinationTaskId"})
    if (
        route["sourceTaskId"] != config["tasks"][source]
        or route["destinationTaskId"] != config["tasks"][destination]
    ):
        raise WorkflowError(
            "routing_mismatch", f"{field} does not match configured roles"
        )
    return route


def validate_message_base(
    payload: Any,
    expected_type: str,
    config: Mapping[str, Any],
    source: str,
    destination: str,
) -> dict[str, Any]:
    message = validate_contract_payload(payload, expected_type)
    if (
        message["workflowId"] != config["workflowId"]
        or message["repositoryKey"] != config["repository"]["key"]
    ):
        raise WorkflowError(
            "workflow_mismatch", "Message workflow/repository does not match config"
        )
    validate_routing(message["routing"], "routing", config, source, destination)
    return message


def build_message(
    config: Mapping[str, Any],
    message_type: str,
    feature_id: str,
    cycle: int,
    source: str,
    destination: str,
    body: Mapping[str, Any],
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "type": message_type,
        "workflowId": config["workflowId"],
        "featureId": require_feature_id(feature_id),
        "repositoryKey": config["repository"]["key"],
        "routing": {
            "sourceTaskId": config["tasks"][source],
            "destinationTaskId": config["tasks"][destination],
        },
        "cycle": cycle,
        "createdAt": utc_now(),
        "body": dict(body),
    }
    message["messageId"] = digest(message_authority(message))
    return message


def record_message(
    state: dict[str, Any], payload: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    message_id = payload["messageId"]
    existing = state["dispatches"].get(message_id)
    if existing:
        stored_payload = require_object(existing.get("payload"), "dispatch.payload")
        if digest(message_authority(stored_payload)) != digest(
            message_authority(payload)
        ):
            raise WorkflowError(
                "replay_conflict", "Existing message ID has different payload"
            )
        return stored_payload, True
    state["dispatches"][message_id] = {
        "type": payload["type"],
        "featureId": payload["featureId"],
        "cycle": payload["cycle"],
        "payloadDigest": digest(payload),
        "payload": payload,
        "status": "prepared",
        "preparedAt": utc_now(),
    }
    return payload, False


def load_payload(path: str) -> dict[str, Any]:
    return load_json(Path(path).expanduser().resolve(), "payload")


def dispatch_for(
    state: Mapping[str, Any], message_id: str, expected_type: str | None = None
) -> dict[str, Any]:
    require_digest(message_id, "messageId")
    record = state["dispatches"].get(message_id)
    if not isinstance(record, dict):
        raise WorkflowError(
            "unknown_message", "Message was not prepared by this workflow"
        )
    if expected_type and record.get("type") != expected_type:
        raise WorkflowError("invalid_transition", f"Message is not {expected_type}")
    return record


def feature_for(state: Mapping[str, Any], feature_id: str) -> dict[str, Any]:
    if not all(require_object(state.get("bootstrap"), "state.bootstrap").values()):
        raise WorkflowError(
            "bootstrap_incomplete",
            "All three role acknowledgements are required before feature work",
        )
    require_feature_id(feature_id)
    value = state["features"].get(feature_id)
    if not isinstance(value, dict):
        raise WorkflowError(
            "unknown_feature", "Feature is not present in workflow state"
        )
    return value


def new_feature(
    feature_id: str, title: str, branch: str, requirements: Mapping[str, Any]
) -> dict[str, Any]:
    now = utc_now()
    return {
        "featureId": feature_id,
        "title": require_string(title, "title", maximum=200),
        "branch": require_string(branch, "branch", maximum=240),
        "stage": "REQUIREMENTS_CONFIRMED",
        "requirements": dict(requirements),
        "planReviewCycle": 0,
        "goalRuns": [],
        "codeReviewCycle": 0,
        "lastError": None,
        "createdAt": now,
        "updatedAt": now,
    }


def touch(feature: dict[str, Any], stage: str | None = None) -> None:
    if stage:
        if stage not in STAGES:
            raise WorkflowError("invalid_transition", f"Unsupported stage {stage}")
        feature["stage"] = stage
    feature["updatedAt"] = utc_now()


def add_queue(state: dict[str, Any], feature_id: str) -> None:
    if feature_id not in state["developmentQueue"]:
        state["developmentQueue"].append(feature_id)


def bind_previous_result(
    body: dict[str, Any],
    supplied: str | None,
    cycle: int,
    expected: Any,
    field: str,
) -> None:
    if cycle == 1:
        if supplied:
            raise WorkflowError(
                "invalid_transition", f"{field} is not allowed on the initial cycle"
            )
        return
    expected_id = require_digest(expected, f"expected {field}")
    if not supplied or require_digest(supplied, field) != expected_id:
        raise WorkflowError(
            "stale_result", f"{field} must match the latest review result"
        )
    body["previousResultMessageId"] = expected_id


def init_policy(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "goalModeAuthorized": bool(args.goal_mode_authorized),
        "merge": {
            "mode": args.merge_mode,
            "method": args.merge_method,
            "deleteBranch": bool(args.delete_branch),
            "requireGreenChecks": True,
            "requireExactHead": True,
        },
        "release": {"mode": "explicit-per-release"},
    }


def repository_binding(repository: Mapping[str, Any]) -> dict[str, str]:
    return {
        "key": repository["key"],
        "origin": repository["origin"],
        "commonDir": str(repository["commonDir"]),
    }


def validate_init_pending(value: Any, repository: Mapping[str, Any]) -> dict[str, Any]:
    pending = exact_keys(
        value,
        "initPending",
        {
            "schemaVersion",
            "workflowId",
            "repository",
            "tasks",
            "policy",
            "createdAt",
            "updatedAt",
        },
    )
    if pending["schemaVersion"] != SCHEMA_VERSION:
        raise WorkflowError("unsupported_schema", "Pending Init schema must be 1")
    try:
        uuid.UUID(require_string(pending["workflowId"], "workflowId", maximum=36))
    except ValueError as exc:
        raise WorkflowError("invalid_state", "Pending workflowId must be UUID") from exc
    binding = exact_keys(
        pending["repository"],
        "initPending.repository",
        {"key", "origin", "commonDir"},
    )
    if binding != repository_binding(repository):
        raise WorkflowError(
            "repository_mismatch", "Pending Init belongs to another repository identity"
        )
    tasks = require_object(pending["tasks"], "initPending.tasks")
    if not set(tasks) <= set(ROLES):
        raise WorkflowError("invalid_state", "Pending Init contains an unknown role")
    task_ids = [
        require_string(task_id, f"initPending.tasks.{role}", maximum=200)
        for role, task_id in tasks.items()
    ]
    if len(task_ids) != len(set(task_ids)):
        raise WorkflowError("invalid_state", "Pending Init task IDs must be distinct")
    placeholders = {role: tasks.get(role, f"pending-role-{role}") for role in ROLES}
    validate_config(
        {
            **pending,
            "tasks": placeholders,
        },
        repository,
    )
    return dict(pending)


def comparable_init(value: Mapping[str, Any]) -> dict[str, Any]:
    comparable = require_object(json.loads(canonical_json(value)), "comparableInit")
    for name in ("workflowId", "createdAt", "updatedAt"):
        comparable.pop(name, None)
    return comparable


def new_workflow_state(workflow_id: str, now: str) -> dict[str, Any]:
    return {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "workflowId": workflow_id,
        "bootstrap": {role: False for role in ROLES},
        "features": {},
        "developmentQueue": [],
        "activeGoal": None,
        "dispatches": {},
        "updatedAt": now,
    }


def command_begin_init(args: argparse.Namespace) -> dict[str, Any]:
    repository = resolve_repository(args.repo)
    policy = init_policy(args)
    if not policy["goalModeAuthorized"]:
        raise WorkflowError(
            "goal_not_authorized",
            "Goal mode must be explicitly authorized before Init persistence",
        )
    paths = state_paths(repository)
    with locked(paths["lock"]):
        if paths["config"].exists() or paths["state"].exists():
            if not paths["config"].exists() or not paths["state"].exists():
                raise WorkflowError(
                    "init_recovery_required",
                    "Workflow persistence is partial; run final Init with the recorded task IDs",
                )
            config = validate_config(load_json(paths["config"], "config"), repository)
            state = load_state_locked(paths, config)
            if config["policy"] != policy:
                raise WorkflowError(
                    "config_conflict",
                    "Existing workflow policy differs from requested Init",
                )
            return {
                "ok": True,
                "duplicate": True,
                "initialized": True,
                "workflowId": config["workflowId"],
                "repositoryKey": repository["key"],
                "tasks": config["tasks"],
                "bootstrap": state["bootstrap"],
                "stateRoot": str(paths["root"]),
            }
        now = utc_now()
        proposed = {
            "schemaVersion": SCHEMA_VERSION,
            "workflowId": str(uuid.uuid4()),
            "repository": repository_binding(repository),
            "tasks": {},
            "policy": policy,
            "createdAt": now,
            "updatedAt": now,
        }
        if paths["pending"].exists():
            pending = validate_init_pending(
                load_json(paths["pending"], "initPending"), repository
            )
            comparable_pending = comparable_init(pending)
            comparable_proposed = comparable_init(proposed)
            comparable_pending["tasks"] = {}
            if comparable_pending != comparable_proposed:
                raise WorkflowError(
                    "config_conflict",
                    "Pending Init policy differs from requested Init",
                )
            duplicate = True
        else:
            pending = validate_init_pending(proposed, repository)
            atomic_write(paths["pending"], pending)
            duplicate = False
    return {
        "ok": True,
        "duplicate": duplicate,
        "initialized": False,
        "workflowId": pending["workflowId"],
        "repositoryKey": repository["key"],
        "tasks": pending["tasks"],
        "missingRoles": [role for role in ROLES if role not in pending["tasks"]],
        "stateRoot": str(paths["root"]),
    }


def command_record_init_task(args: argparse.Namespace) -> dict[str, Any]:
    repository = resolve_repository(args.repo)
    paths = state_paths(repository)
    with locked(paths["lock"]):
        if not paths["pending"].exists():
            raise WorkflowError(
                "init_not_started", "Run begin-init before creating workflow tasks"
            )
        pending = validate_init_pending(
            load_json(paths["pending"], "initPending"), repository
        )
        task_id = require_string(args.created_task_id, "createdTaskId", maximum=200)
        existing = pending["tasks"].get(args.role)
        if existing and existing != task_id:
            raise WorkflowError(
                "config_conflict", "Pending role is already bound to another task"
            )
        if any(
            role != args.role and candidate == task_id
            for role, candidate in pending["tasks"].items()
        ):
            raise WorkflowError(
                "config_conflict", "One task cannot own multiple workflow roles"
            )
        duplicate = existing == task_id
        if not duplicate:
            pending["tasks"][args.role] = task_id
            pending["updatedAt"] = utc_now()
            validate_init_pending(pending, repository)
            atomic_write(paths["pending"], pending)
    return {
        "ok": True,
        "duplicate": duplicate,
        "workflowId": pending["workflowId"],
        "role": args.role,
        "taskId": task_id,
        "tasks": pending["tasks"],
        "missingRoles": [role for role in ROLES if role not in pending["tasks"]],
    }


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    repository = resolve_repository(args.repo)
    paths = state_paths(repository)
    with locked(paths["lock"]):
        now = utc_now()
        requested_tasks = {
            "requirements": require_string(
                args.requirements_task_id, "requirementsTaskId", maximum=200
            ),
            "main": require_string(args.main_task_id, "mainTaskId", maximum=200),
            "review": require_string(args.review_task_id, "reviewTaskId", maximum=200),
        }
        pending = (
            validate_init_pending(
                load_json(paths["pending"], "initPending"), repository
            )
            if paths["pending"].exists()
            else None
        )
        if (
            not paths["config"].exists()
            and not paths["state"].exists()
            and pending is None
        ):
            raise WorkflowError(
                "init_not_started", "Run begin-init before creating workflow tasks"
            )
        if pending is not None and pending["tasks"] != requested_tasks:
            raise WorkflowError(
                "config_conflict",
                "Final task IDs must exactly match the recoverable pending Init ledger",
            )
        if pending is not None and pending["policy"] != init_policy(args):
            raise WorkflowError(
                "config_conflict", "Final Init policy differs from pending Init"
            )
        proposed = {
            "schemaVersion": SCHEMA_VERSION,
            "workflowId": pending["workflowId"] if pending else str(uuid.uuid4()),
            "repository": repository_binding(repository),
            "tasks": requested_tasks,
            "policy": init_policy(args),
            "createdAt": pending["createdAt"] if pending else now,
            "updatedAt": now,
        }
        validate_config(proposed, repository)
        if paths["config"].exists() or paths["state"].exists():
            if paths["state"].exists() and not paths["config"].exists():
                raise WorkflowError(
                    "invalid_state",
                    "Workflow state exists without config; preserve it for explicit recovery",
                )
            config = validate_config(load_json(paths["config"], "config"), repository)
            if comparable_init(config) != comparable_init(proposed):
                raise WorkflowError(
                    "config_conflict",
                    "Existing workflow config differs from requested Init",
                )
            if paths["state"].exists():
                state = load_state_locked(paths, config)
                recovered = False
                duplicate = True
            else:
                state = new_workflow_state(
                    require_string(config["workflowId"], "workflowId", maximum=36),
                    now,
                )
                validate_state(state, config)
                atomic_write(paths["state"], state)
                recovered = True
                duplicate = False
            paths["pending"].unlink(missing_ok=True)
            return {
                "ok": True,
                "duplicate": duplicate,
                "recovered": recovered,
                "workflowId": config["workflowId"],
                "repositoryKey": repository["key"],
                "stateRoot": str(paths["root"]),
                "tasks": config["tasks"],
                "bootstrap": state["bootstrap"],
            }
        state = new_workflow_state(
            require_string(proposed["workflowId"], "workflowId", maximum=36),
            now,
        )
        validate_state(state, proposed)
        atomic_write(paths["config"], proposed)
        atomic_write(paths["state"], state)
        paths["pending"].unlink(missing_ok=True)
        return {
            "ok": True,
            "duplicate": False,
            "recovered": False,
            "workflowId": proposed["workflowId"],
            "repositoryKey": repository["key"],
            "stateRoot": str(paths["root"]),
            "tasks": proposed["tasks"],
            "bootstrap": state["bootstrap"],
        }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    repository = resolve_repository(args.repo)
    paths = state_paths(repository)
    if not paths["config"].exists() and not paths["state"].exists():
        if paths["pending"].exists():
            pending = validate_init_pending(
                load_json(paths["pending"], "initPending"), repository
            )
            return {
                "ok": True,
                "initialized": False,
                "initPending": True,
                "workflowId": pending["workflowId"],
                "repositoryKey": repository["key"],
                "tasks": pending["tasks"],
                "missingRoles": [
                    role for role in ROLES if role not in pending["tasks"]
                ],
                "policy": pending["policy"],
                "stateRoot": str(paths["root"]),
            }
        return {
            "ok": True,
            "initialized": False,
            "initPending": False,
            "repositoryKey": repository["key"],
            "stateRoot": str(paths["root"]),
        }
    if paths["config"].exists() and not paths["state"].exists():
        config = validate_config(load_json(paths["config"], "config"), repository)
        return {
            "ok": True,
            "initialized": False,
            "initPending": paths["pending"].exists(),
            "recoveryRequired": True,
            "workflowId": config["workflowId"],
            "repositoryKey": config["repository"]["key"],
            "tasks": config["tasks"],
            "policy": config["policy"],
            "stateRoot": str(paths["root"]),
        }
    if paths["state"].exists() and not paths["config"].exists():
        raise WorkflowError(
            "invalid_state",
            "Workflow state exists without config; preserve it for explicit recovery",
        )
    _, _, config, state = load_context(args.repo)
    role = role_for_task(config, args.task_id) if args.task_id else None
    features = {
        feature_id: {
            "title": feature["title"],
            "branch": feature["branch"],
            "stage": feature["stage"],
            "planReviewCycle": feature.get("planReviewCycle", 0),
            "codeReviewCycle": feature.get("codeReviewCycle", 0),
            "goalRuns": [
                {
                    "goalRunId": run["goalRunId"],
                    "purpose": run["purpose"],
                    "status": run["status"],
                }
                for run in feature.get("goalRuns", [])
            ],
        }
        for feature_id, feature in state["features"].items()
    }
    return {
        "ok": True,
        "initialized": True,
        "workflowId": config["workflowId"],
        "repositoryKey": config["repository"]["key"],
        "tasks": config["tasks"],
        "role": role,
        "bootstrap": state["bootstrap"],
        "ready": all(state["bootstrap"].values()),
        "policy": config["policy"],
        "developmentQueue": state["developmentQueue"],
        "activeGoal": state["activeGoal"],
        "features": features,
        "stateRoot": str(paths["root"]),
    }


def command_ack_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    del repository
    require_role(config, args.task_id, args.role)
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        duplicate = state["bootstrap"][args.role]
        if not duplicate:
            state["bootstrap"][args.role] = True
            save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": duplicate,
        "role": args.role,
        "ready": all(state["bootstrap"].values()),
    }


def command_prepare_requirements(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "requirements")
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        if not all(state["bootstrap"].values()):
            raise WorkflowError(
                "bootstrap_incomplete",
                "All three role acknowledgements are required before feature work",
            )
        feature_id = require_feature_id(args.feature_id)
        feature_slug = feature_id.rsplit("-", 1)[0]
        expected_branch = f"codex/{feature_slug}"
        expected_path = f"docs/feature/{feature_slug}/requirements.md"
        branch = require_string(args.branch, "branch", maximum=240)
        requirements_path = require_repo_path(
            args.requirements_path, "requirementsPath"
        )
        if branch != expected_branch or requirements_path != expected_path:
            raise WorkflowError(
                "invalid_requirements",
                "Requirements branch/path must match the deterministic feature slug",
            )
        snapshot = artifact_snapshot(
            repository["root"], args.requirements_commit_sha, requirements_path
        )
        verify_remote_branch_tip(repository["root"], branch, snapshot["commitSha"])
        metadata = parse_requirements_metadata(
            read_committed(repository["root"], snapshot["commitSha"], snapshot["path"])
        )
        if metadata["FeatureId"] != feature_id or metadata["Branch"] != branch:
            raise WorkflowError(
                "snapshot_mismatch", "Requirements metadata differs from command"
            )
        body = {
            "title": require_string(args.title, "title", maximum=200),
            "branch": branch,
            "requirements": snapshot,
            "confirmation": {
                "status": "CONFIRMED",
                "confirmedBy": metadata["ConfirmedBy"],
                "confirmedAt": metadata["ConfirmedAt"],
                "evidence": require_string(
                    args.confirmation_evidence, "confirmationEvidence", maximum=300
                ),
            },
        }
        message = build_message(
            config,
            "RequirementsHandoff",
            feature_id,
            1,
            "requirements",
            "main",
            body,
        )
        stored, duplicate = record_message(state, message)
        existing = state["features"].get(feature_id)
        if existing:
            if existing["requirements"] != snapshot or existing["branch"] != branch:
                raise WorkflowError(
                    "feature_conflict",
                    "Feature ID already uses another requirements snapshot",
                )
        else:
            state["features"][feature_id] = new_feature(
                feature_id, args.title, branch, snapshot
            )
        save_state(paths, state, config)
    return {"ok": True, "duplicate": duplicate, "message": stored}


def command_mark_dispatch(args: argparse.Namespace, failed: bool) -> dict[str, Any]:
    _, paths, config, _ = load_context(args.repo)
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        record = dispatch_for(state, args.message_id)
        target = "delivery_failed" if failed else "dispatched"
        duplicate = record["status"] == target
        failure_reason = (
            require_string(args.reason, "reason", maximum=300) if failed else None
        )
        if duplicate and failed and record.get("failureReason") != failure_reason:
            raise WorkflowError("replay_conflict", "Delivery failure reason differs")
        if not duplicate and record["status"] not in {
            "prepared",
            "delivery_failed",
            "dispatched",
        }:
            raise WorkflowError(
                "invalid_transition", f"Cannot mark {record['status']} message {target}"
            )
        if not duplicate:
            record["status"] = target
            record[f"{target}At"] = utc_now()
            if failed:
                record["failureReason"] = failure_reason
            save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": duplicate,
        "messageId": args.message_id,
        "status": target,
    }


def accept_request(
    args: argparse.Namespace,
    message_type: str,
    source: str,
    destination: str,
    transition: Callable[[dict[str, Any], dict[str, Any], bool], None] | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Path],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    bool,
]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, destination)
    payload = validate_message_base(
        load_payload(args.payload_file), message_type, config, source, destination
    )
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        record = dispatch_for(state, payload["messageId"], message_type)
        if record["payloadDigest"] != digest(payload):
            raise WorkflowError(
                "replay_conflict", "Delivered payload differs from prepared payload"
            )
        duplicate = record["status"] == "accepted"
        if not duplicate and record["status"] not in {
            "prepared",
            "dispatched",
            "delivery_failed",
        }:
            raise WorkflowError(
                "invalid_transition", f"Cannot accept message in {record['status']}"
            )
        if transition is not None:
            transition(state, payload, duplicate)
        if not duplicate:
            record["status"] = "accepted"
            record["acceptedAt"] = utc_now()
            save_state(paths, state, config)
    return repository, paths, config, state, payload, duplicate


def command_accept_requirements(args: argparse.Namespace) -> dict[str, Any]:
    repository = resolve_repository(args.repo)

    def apply_requirements(
        current: dict[str, Any],
        payload: dict[str, Any],
        duplicate: bool,
    ) -> None:
        del duplicate
        body = payload["body"]
        validate_artifact(
            body["requirements"],
            "RequirementsHandoff.body.requirements",
            repository["root"],
        )
        feature = feature_for(current, payload["featureId"])
        if (
            feature["requirements"] != body["requirements"]
            or feature["branch"] != body["branch"]
        ):
            raise WorkflowError(
                "snapshot_mismatch", "Requirements payload differs from durable feature"
            )
        if not feature.get("requirementsAcceptedAt"):
            feature["requirementsMessageId"] = payload["messageId"]
            feature["requirementsAcceptedAt"] = utc_now()
            touch(feature, "PLAN_DRAFTING")
        elif feature.get("requirementsMessageId") != payload["messageId"]:
            raise WorkflowError(
                "replay_conflict", "Feature accepted another requirements message"
            )

    _, _, _, state, payload, duplicate = accept_request(
        args,
        "RequirementsHandoff",
        "requirements",
        "main",
        apply_requirements,
    )
    feature = feature_for(state, payload["featureId"])
    return {
        "ok": True,
        "duplicate": duplicate,
        "featureId": payload["featureId"],
        "stage": feature["stage"],
    }


def command_prepare_plan_review(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, args.feature_id)
        if feature["stage"] not in {"PLAN_DRAFTING", "PLAN_CHANGES_REQUESTED"}:
            raise WorkflowError(
                "invalid_transition", "Feature is not ready for plan review"
            )
        commit = require_sha(args.plan_commit_sha, "planCommitSha")
        requirements = artifact_snapshot(
            repository["root"], commit, args.requirements_path
        )
        if requirements["sha256"] != feature["requirements"]["sha256"]:
            raise WorkflowError(
                "snapshot_mismatch", "Confirmed requirements changed in plan snapshot"
            )
        design = artifact_snapshot(repository["root"], commit, args.design_path)
        implementation = artifact_snapshot(
            repository["root"], commit, args.implementation_plan_path
        )
        composite = digest([requirements, design, implementation])
        cycle = feature["planReviewCycle"] + 1
        branch = f"codex/review-records/{args.feature_id}/plan-{cycle}-{commit[:12]}"
        body = {
            "plan": {
                "requirements": requirements,
                "design": design,
                "implementationPlan": implementation,
                "planCommitSha": commit,
                "compositeSha256": composite,
            },
            "reviewRecordBranch": branch,
            "acceptanceCriteriaDigest": require_digest(
                args.acceptance_criteria_digest, "acceptanceCriteriaDigest"
            ),
        }
        bind_previous_result(
            body,
            args.previous_result_message_id,
            cycle,
            feature.get("planResultMessageId"),
            "previousResultMessageId",
        )
        message = build_message(
            config,
            "TechnicalPlanReviewRequest",
            args.feature_id,
            cycle,
            "main",
            "review",
            body,
        )
        stored, duplicate = record_message(state, message)
        feature["plan"] = body["plan"]
        feature["planReviewCycle"] = cycle
        feature["pendingPlanRequestId"] = message["messageId"]
        touch(feature, "PLAN_REVIEW_PENDING")
        save_state(paths, state, config)
    return {"ok": True, "duplicate": duplicate, "message": stored}


def command_accept_plan_review(args: argparse.Namespace) -> dict[str, Any]:
    def require_current_plan(
        state: dict[str, Any],
        payload: dict[str, Any],
        duplicate: bool,
    ) -> None:
        feature = feature_for(state, payload["featureId"])
        if feature.get("pendingPlanRequestId") != payload["messageId"]:
            raise WorkflowError(
                "stale_result", "Plan request is not the latest pending snapshot"
            )
        if not duplicate and feature["stage"] != "PLAN_REVIEW_PENDING":
            raise WorkflowError("stale_result", "Plan request is not pending review")

    _, _, _, state, payload, duplicate = accept_request(
        args,
        "TechnicalPlanReviewRequest",
        "main",
        "review",
        require_current_plan,
    )
    feature = feature_for(state, payload["featureId"])
    return {
        "ok": True,
        "duplicate": duplicate,
        "messageId": payload["messageId"],
        "stage": feature["stage"],
    }


def report_from_args(
    args: argparse.Namespace, repository: Mapping[str, Any]
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "branch": args.report_branch,
        "path": require_repo_path(args.report_path, "reportPath"),
        "commitSha": require_sha(args.report_commit_sha, "reportCommitSha"),
        "sha256": require_digest(args.report_sha256, "reportSha256"),
    }
    if args.report_json_path or args.report_json_sha256:
        report["jsonPath"] = require_repo_path(args.report_json_path, "reportJsonPath")
        report["jsonSha256"] = require_digest(
            args.report_json_sha256, "reportJsonSha256"
        )
    validate_report(report, "report", repository["root"])
    return report


def command_prepare_plan_result(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "review")
    request = validate_message_base(
        load_payload(args.request_file),
        "TechnicalPlanReviewRequest",
        config,
        "main",
        "review",
    )
    decision = args.decision
    findings = {
        "blocker": require_int(args.blockers, "blockers"),
        "major": require_int(args.majors, "majors"),
        "minor": require_int(args.minors, "minors"),
    }
    if decision == "PASS" and (findings["blocker"] or findings["major"]):
        raise WorkflowError(
            "invalid_payload", "PASS requires zero blocker and major findings"
        )
    report = report_from_args(args, repository)
    if report["branch"] != request["body"]["reviewRecordBranch"]:
        raise WorkflowError(
            "review_record_conflict", "Plan report branch differs from request"
        )
    verify_ancestor(
        repository["root"],
        request["body"]["plan"]["planCommitSha"],
        report["commitSha"],
    )
    body = {
        "requestMessageId": request["messageId"],
        "reviewedPlan": {
            "planCommitSha": request["body"]["plan"]["planCommitSha"],
            "compositeSha256": request["body"]["plan"]["compositeSha256"],
        },
        "decision": decision,
        "findings": findings,
        "report": report,
        "summary": require_string(args.summary, "summary", maximum=500),
    }
    result = build_message(
        config,
        "TechnicalPlanReviewResult",
        request["featureId"],
        request["cycle"],
        "review",
        "main",
        body,
    )
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        request_record = dispatch_for(
            state, request["messageId"], "TechnicalPlanReviewRequest"
        )
        if request_record["status"] != "accepted":
            raise WorkflowError(
                "invalid_transition", "Plan request was not accepted for review"
            )
        feature = feature_for(state, request["featureId"])
        if (
            feature.get("pendingPlanRequestId") != request["messageId"]
            or feature["stage"] != "PLAN_REVIEW_PENDING"
        ):
            raise WorkflowError(
                "stale_result", "Plan request is not the latest pending snapshot"
            )
        stored, duplicate = record_message(state, result)
        save_state(paths, state, config)
    return {"ok": True, "duplicate": duplicate, "message": stored}


def command_apply_plan_result(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    result = validate_message_base(
        load_payload(args.payload_file),
        "TechnicalPlanReviewResult",
        config,
        "review",
        "main",
    )
    body = exact_keys(
        result["body"],
        "TechnicalPlanReviewResult.body",
        {
            "requestMessageId",
            "reviewedPlan",
            "decision",
            "findings",
            "report",
            "summary",
        },
    )
    validate_report(
        body["report"], "TechnicalPlanReviewResult.body.report", repository["root"]
    )
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, result["featureId"])
        if feature.get("pendingPlanRequestId") != body["requestMessageId"]:
            raise WorkflowError(
                "stale_result", "Plan result does not match pending request"
            )
        request = dispatch_for(
            state, body["requestMessageId"], "TechnicalPlanReviewRequest"
        )["payload"]
        expected = {
            "planCommitSha": request["body"]["plan"]["planCommitSha"],
            "compositeSha256": request["body"]["plan"]["compositeSha256"],
        }
        if body["reviewedPlan"] != expected:
            raise WorkflowError(
                "snapshot_mismatch", "Plan result reviewed another snapshot"
            )
        result_record = dispatch_for(
            state, result["messageId"], "TechnicalPlanReviewResult"
        )
        if result_record["payloadDigest"] != digest(result):
            raise WorkflowError(
                "replay_conflict", "Plan result differs from prepared result"
            )
        duplicate = result_record["status"] == "applied"
        if not duplicate:
            findings = body["findings"]
            if body["decision"] == "PASS":
                if findings.get("blocker") or findings.get("major"):
                    raise WorkflowError(
                        "invalid_payload", "PASS contains blocking findings"
                    )
                feature["planResultMessageId"] = result["messageId"]
                touch(feature, "PLAN_APPROVED")
                add_queue(state, feature["featureId"])
                touch(feature, "DEVELOPMENT_QUEUED")
            elif body["decision"] == "FAIL":
                feature["planResultMessageId"] = result["messageId"]
                touch(feature, "PLAN_CHANGES_REQUESTED")
            else:
                raise WorkflowError(
                    "invalid_payload", "Plan decision must be PASS or FAIL"
                )
            result_record["status"] = "applied"
            result_record["appliedAt"] = utc_now()
        save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": duplicate,
        "featureId": feature["featureId"],
        "stage": feature["stage"],
    }


def command_start_development(args: argparse.Namespace) -> dict[str, Any]:
    _, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    if not config["policy"]["goalModeAuthorized"]:
        raise WorkflowError(
            "goal_not_authorized", "Workflow was initialized without Goal authorization"
        )
    objective = require_string(args.objective, "objective", maximum=4000)
    objective_digest = hashlib.sha256(objective.encode("utf-8")).hexdigest()
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, args.feature_id)
        purpose = (
            "CODE_REMEDIATION"
            if feature.get("codeResultMessageId")
            else "INITIAL_IMPLEMENTATION"
        )
        authority = (
            feature.get("codeResultMessageId")
            if purpose == "CODE_REMEDIATION"
            else feature.get("planResultMessageId")
        )
        if not authority:
            raise WorkflowError(
                "invalid_transition", "GoalRun lacks an authorizing review result"
            )
        review_cycle = (
            feature["codeReviewCycle"] if purpose == "CODE_REMEDIATION" else 0
        )
        run_id = digest(
            {
                "workflowId": config["workflowId"],
                "featureId": feature["featureId"],
                "purpose": purpose,
                "reviewCycle": review_cycle,
                "authorityMessageId": authority,
            }
        )
        existing = next(
            (item for item in feature["goalRuns"] if item["goalRunId"] == run_id), None
        )
        if existing and existing["objectiveDigest"] != objective_digest:
            raise WorkflowError("replay_conflict", "Prepared GoalRun objective differs")
        if args.activate:
            supplied_run_id = require_digest(args.goal_run_id, "goalRunId")
            if supplied_run_id != run_id:
                raise WorkflowError(
                    "invalid_transition", "GoalRun ID differs from current authority"
                )
            if args.goal_thread_id != config["tasks"]["main"]:
                raise WorkflowError(
                    "task_role_mismatch", "Goal thread must be configured Main task"
                )
            if not existing:
                raise WorkflowError(
                    "invalid_transition", "GoalRun is not prepared for this objective"
                )
            run = existing
            if run["status"] != "PREPARED":
                if run["status"] in {"ACTIVE", "BLOCKED"} and state["activeGoal"] != {
                    "featureId": feature["featureId"],
                    "goalRunId": run_id,
                }:
                    raise WorkflowError(
                        "invalid_state", "Active GoalRun does not own the global slot"
                    )
                if run["status"] not in {"ACTIVE", "BLOCKED", "COMPLETE"}:
                    raise WorkflowError(
                        "invalid_transition", "GoalRun has unsupported replay status"
                    )
                return {
                    "ok": True,
                    "duplicate": True,
                    "goalRun": run,
                    "stage": feature["stage"],
                }
            if state["activeGoal"] is not None:
                raise WorkflowError("goal_slot_busy", "Another GoalRun is active")
            run["status"] = "ACTIVE"
            run["startedAt"] = utc_now()
            state["activeGoal"] = {
                "featureId": feature["featureId"],
                "goalRunId": run_id,
            }
            state["developmentQueue"] = [
                item
                for item in state["developmentQueue"]
                if item != feature["featureId"]
            ]
            touch(feature, "DEVELOPMENT_ACTIVE")
            save_state(paths, state, config)
            return {
                "ok": True,
                "duplicate": False,
                "goalRun": run,
                "stage": feature["stage"],
            }
        if existing:
            return {
                "ok": True,
                "duplicate": True,
                "goalRun": existing,
                "stage": feature["stage"],
            }
        if feature["stage"] != "DEVELOPMENT_QUEUED":
            raise WorkflowError(
                "invalid_transition", "Feature is not queued for development"
            )
        if state["activeGoal"] is not None:
            raise WorkflowError("goal_slot_busy", "Another GoalRun is active")
        run = {
            "goalRunId": run_id,
            "purpose": purpose,
            "reviewCycle": review_cycle,
            "threadId": config["tasks"]["main"],
            "authorityMessageId": authority,
            "objectiveDigest": objective_digest,
            "status": "PREPARED",
        }
        feature["goalRuns"].append(run)
        save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": False,
        "goalRun": run,
        "stage": feature["stage"],
    }


def active_run(
    state: Mapping[str, Any], feature: Mapping[str, Any], run_id: str
) -> dict[str, Any]:
    active = state["activeGoal"]
    if active != {"featureId": feature["featureId"], "goalRunId": run_id}:
        raise WorkflowError(
            "invalid_transition", "GoalRun is not the active workflow Goal"
        )
    run = next(
        (item for item in feature["goalRuns"] if item["goalRunId"] == run_id), None
    )
    if not run:
        raise WorkflowError("invalid_transition", "GoalRun does not exist")
    return require_object(run, "GoalRun")


def command_goal_transition(args: argparse.Namespace, operation: str) -> dict[str, Any]:
    _, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, args.feature_id)
        run = active_run(state, feature, require_digest(args.goal_run_id, "goalRunId"))
        if operation == "block":
            if run["status"] != "ACTIVE":
                raise WorkflowError(
                    "invalid_transition", "Only ACTIVE GoalRun can block"
                )
            run["status"] = "BLOCKED"
            run["blockedReason"] = require_string(args.reason, "reason", maximum=300)
            touch(feature, "DEVELOPMENT_BLOCKED")
        elif operation == "resume":
            if run["status"] != "BLOCKED":
                raise WorkflowError(
                    "invalid_transition", "Only BLOCKED GoalRun can resume"
                )
            run["status"] = "ACTIVE"
            run.pop("blockedReason", None)
            touch(feature, "DEVELOPMENT_ACTIVE")
        elif operation == "complete":
            if run["status"] != "ACTIVE":
                raise WorkflowError(
                    "invalid_transition", "Only ACTIVE GoalRun can complete"
                )
            run["status"] = "COMPLETE"
            run["completedAt"] = utc_now()
            usage: dict[str, int] = {}
            if args.tokens_used is not None:
                usage["tokensUsed"] = require_int(args.tokens_used, "tokensUsed")
            if args.time_used_seconds is not None:
                usage["timeUsedSeconds"] = require_int(
                    args.time_used_seconds, "timeUsedSeconds"
                )
            if usage:
                run["usage"] = usage
            state["activeGoal"] = None
            touch(feature, "DEVELOPMENT_COMPLETE")
        save_state(paths, state, config)
    return {"ok": True, "goalRun": run, "stage": feature["stage"]}


def command_prepare_code_review(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, args.feature_id)
        if feature["stage"] != "DEVELOPMENT_COMPLETE":
            raise WorkflowError(
                "invalid_transition", "Development must complete before code review"
            )
        number = require_int(args.pr_number, "prNumber", minimum=1)
        expected_url = f"https://github.com/{repository['key']}/pull/{number}"
        if (
            require_https_url(args.pr_url, "prUrl", host="github.com").rstrip("/")
            != expected_url
        ):
            raise WorkflowError(
                "repository_mismatch",
                "PR URL does not match workflow repository/number",
            )
        base_sha = require_sha(args.base_sha, "baseSha")
        head_sha = require_sha(args.head_sha, "headSha")
        run_git(repository["root"], "cat-file", "-e", f"{base_sha}^{{commit}}")
        run_git(repository["root"], "cat-file", "-e", f"{head_sha}^{{commit}}")
        cycle = feature["codeReviewCycle"] + 1
        branch = f"codex/review-records/{args.feature_id}/code-{cycle}-{head_sha[:12]}"
        pull = {
            "number": number,
            "url": expected_url,
            "baseRef": require_string(args.base_ref, "baseRef", maximum=240),
            "baseSha": base_sha,
            "headRef": require_string(args.head_ref, "headRef", maximum=240),
            "headSha": head_sha,
        }
        body = {
            "pullRequest": pull,
            "reviewRecordBranch": branch,
            "mergePolicy": config["policy"]["merge"],
        }
        bind_previous_result(
            body,
            args.previous_result_message_id,
            cycle,
            feature.get("codeResultMessageId"),
            "previousResultMessageId",
        )
        message = build_message(
            config, "CodeReviewRequest", args.feature_id, cycle, "main", "review", body
        )
        stored, duplicate = record_message(state, message)
        feature["pullRequest"] = pull
        feature["codeReviewCycle"] = cycle
        feature["pendingCodeRequestId"] = message["messageId"]
        touch(feature, "CODE_REVIEW_PENDING")
        save_state(paths, state, config)
    return {"ok": True, "duplicate": duplicate, "message": stored}


def command_accept_code_review(args: argparse.Namespace) -> dict[str, Any]:
    def require_current_code(
        state: dict[str, Any],
        payload: dict[str, Any],
        duplicate: bool,
    ) -> None:
        feature = feature_for(state, payload["featureId"])
        if feature.get("pendingCodeRequestId") != payload["messageId"]:
            raise WorkflowError(
                "stale_result", "Code request is not the latest pending snapshot"
            )
        if not duplicate and feature["stage"] not in {
            "CODE_REVIEW_PENDING",
            "MERGE_READY",
        }:
            raise WorkflowError("stale_result", "Code request is not pending review")

    _, _, _, state, payload, duplicate = accept_request(
        args,
        "CodeReviewRequest",
        "main",
        "review",
        require_current_code,
    )
    feature = feature_for(state, payload["featureId"])
    return {
        "ok": True,
        "duplicate": duplicate,
        "messageId": payload["messageId"],
        "stage": feature["stage"],
    }


def require_prior_merge_ready(
    state: Mapping[str, Any],
    feature: Mapping[str, Any],
    request: Mapping[str, Any],
) -> None:
    if (
        feature.get("stage") != "MERGE_READY"
        or feature.get("pendingCodeRequestId") != request["messageId"]
    ):
        raise WorkflowError(
            "invalid_transition",
            "Review-only MERGED proof requires a prior READY result for this request",
        )
    previous_id = require_digest(
        feature.get("codeResultMessageId"), "codeResultMessageId"
    )
    previous_record = dispatch_for(state, previous_id, "CodeReviewResult")
    previous = require_object(
        previous_record.get("payload"), "previous CodeReviewResult"
    )
    previous_body = require_object(
        previous.get("body"), "previous CodeReviewResult.body"
    )
    if (
        previous_record.get("status") != "applied"
        or previous_body.get("requestMessageId") != request["messageId"]
        or previous_body.get("decision") != "APPROVE"
        or previous_body.get("reviewedPullRequest") != request["body"]["pullRequest"]
        or previous_body.get("checks", {}).get("status") != "PASSING"
        or previous_body.get("merge") != {"status": "READY"}
    ):
        raise WorkflowError(
            "invalid_transition",
            "Review-only MERGED proof lacks an applied exact-head APPROVE/READY result",
        )


def command_prepare_code_result(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "review")
    request = validate_message_base(
        load_payload(args.request_file), "CodeReviewRequest", config, "main", "review"
    )
    findings = {
        "blocker": require_int(args.blockers, "blockers"),
        "major": require_int(args.majors, "majors"),
        "minor": require_int(args.minors, "minors"),
    }
    if args.decision == "APPROVE" and findings["blocker"]:
        raise WorkflowError(
            "invalid_payload", "APPROVE cannot contain blocker findings"
        )
    report = report_from_args(args, repository)
    if report["branch"] != request["body"]["reviewRecordBranch"]:
        raise WorkflowError(
            "review_record_conflict", "Code report branch differs from request"
        )
    verify_ancestor(
        repository["root"],
        request["body"]["pullRequest"]["headSha"],
        report["commitSha"],
    )
    checks = {
        "status": args.checks_status,
        "checkedAt": require_timestamp(args.checks_checked_at, "checksCheckedAt"),
    }
    if args.checks_url:
        checks["detailsUrl"] = require_https_url(args.checks_url, "checksUrl")
    merge: dict[str, Any] = {"status": args.merge_status}
    if args.merge_status == "MERGED":
        if args.decision != "APPROVE" or args.checks_status != "PASSING":
            raise WorkflowError(
                "invalid_payload", "MERGED requires APPROVE and passing checks"
            )
        merge_policy = request["body"]["mergePolicy"]
        if (
            merge_policy["mode"] == "merge-on-approve"
            and args.merge_method != merge_policy["method"]
        ):
            raise WorkflowError(
                "invalid_payload", "Merge method differs from request policy"
            )
        merge_url = require_https_url(args.merge_url, "mergeUrl", host="github.com")
        if merge_url.rstrip("/") != request["body"]["pullRequest"]["url"].rstrip("/"):
            raise WorkflowError(
                "snapshot_mismatch", "Merge URL differs from reviewed PR"
            )
        merge.update(
            {
                "method": args.merge_method,
                "url": merge_url,
                "sha": require_sha(args.merge_sha, "mergeSha"),
                "mergedAt": require_timestamp(args.merged_at, "mergedAt"),
            }
        )
    elif args.merge_status == "FAILED":
        merge["error"] = require_string(args.merge_error, "mergeError", maximum=300)
    elif args.merge_status not in {"READY", "NOT_REQUESTED", "STALE"}:
        raise WorkflowError("invalid_payload", "Unsupported merge status")
    body = {
        "requestMessageId": request["messageId"],
        "reviewedPullRequest": request["body"]["pullRequest"],
        "decision": args.decision,
        "findings": findings,
        "report": report,
        "checks": checks,
        "merge": merge,
        "summary": require_string(args.summary, "summary", maximum=500),
    }
    result = build_message(
        config,
        "CodeReviewResult",
        request["featureId"],
        request["cycle"],
        "review",
        "main",
        body,
    )
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        request_record = dispatch_for(state, request["messageId"], "CodeReviewRequest")
        if request_record["status"] != "accepted":
            raise WorkflowError(
                "invalid_transition", "Code request was not accepted for review"
            )
        feature = feature_for(state, request["featureId"])
        if feature.get("pendingCodeRequestId") != request["messageId"]:
            raise WorkflowError(
                "stale_result", "Code request is not the latest pending snapshot"
            )
        merge_mode = request["body"]["mergePolicy"]["mode"]
        if args.merge_status == "READY" and merge_mode != "review-only":
            raise WorkflowError(
                "invalid_transition", "READY is only valid for review-only policy"
            )
        if args.merge_status == "FAILED" and merge_mode != "merge-on-approve":
            raise WorkflowError(
                "invalid_transition", "FAILED merge is only valid for merge-on-approve"
            )
        if args.merge_status == "MERGED" and merge_mode == "review-only":
            require_prior_merge_ready(state, feature, request)
        stored, duplicate = record_message(state, result)
        save_state(paths, state, config)
    return {"ok": True, "duplicate": duplicate, "message": stored}


def command_apply_code_result(args: argparse.Namespace) -> dict[str, Any]:
    repository, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    result = validate_message_base(
        load_payload(args.payload_file), "CodeReviewResult", config, "review", "main"
    )
    body = exact_keys(
        result["body"],
        "CodeReviewResult.body",
        {
            "requestMessageId",
            "reviewedPullRequest",
            "decision",
            "findings",
            "report",
            "checks",
            "merge",
            "summary",
        },
    )
    validate_report(body["report"], "CodeReviewResult.body.report", repository["root"])
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, result["featureId"])
        if feature.get("pendingCodeRequestId") != body["requestMessageId"]:
            raise WorkflowError(
                "stale_result", "Code result does not match pending request"
            )
        request = dispatch_for(state, body["requestMessageId"], "CodeReviewRequest")[
            "payload"
        ]
        if body["reviewedPullRequest"] != request["body"]["pullRequest"]:
            raise WorkflowError(
                "snapshot_mismatch", "Code result reviewed another PR snapshot"
            )
        record = dispatch_for(state, result["messageId"], "CodeReviewResult")
        if record["payloadDigest"] != digest(result):
            raise WorkflowError(
                "replay_conflict", "Code result differs from prepared result"
            )
        duplicate = record["status"] == "applied"
        if not duplicate:
            merge_status = body["merge"].get("status")
            decision = body["decision"]
            if decision == "APPROVE" and merge_status == "MERGED":
                if config["policy"]["merge"]["mode"] == "review-only":
                    require_prior_merge_ready(state, feature, request)
                elif body["merge"]["method"] != config["policy"]["merge"]["method"]:
                    raise WorkflowError(
                        "invalid_payload", "Merge method differs from local policy"
                    )
                if body["merge"]["url"].rstrip("/") != request["body"]["pullRequest"][
                    "url"
                ].rstrip("/"):
                    raise WorkflowError(
                        "snapshot_mismatch", "Merge proof URL differs from reviewed PR"
                    )
                feature["merge"] = {
                    "method": body["merge"]["method"],
                    "prUrl": body["merge"]["url"],
                    "approvedHeadSha": body["reviewedPullRequest"]["headSha"],
                    "mergeCommitSha": body["merge"]["sha"],
                    "mergedAt": body["merge"]["mergedAt"],
                }
                feature["codeResultMessageId"] = result["messageId"]
                touch(feature, "MERGED")
                touch(feature, "RELEASE_AWAITING_AUTHORIZATION")
            elif decision == "APPROVE" and merge_status == "READY":
                if config["policy"]["merge"]["mode"] != "review-only":
                    raise WorkflowError(
                        "invalid_transition",
                        "READY is only valid for review-only policy",
                    )
                feature["codeResultMessageId"] = result["messageId"]
                touch(feature, "MERGE_READY")
            elif decision == "APPROVE" and merge_status == "FAILED":
                if config["policy"]["merge"]["mode"] != "merge-on-approve":
                    raise WorkflowError(
                        "invalid_transition",
                        "FAILED merge is only valid for merge-on-approve",
                    )
                feature["codeResultMessageId"] = result["messageId"]
                touch(feature, "CODE_REVIEW_PENDING")
            elif merge_status == "STALE":
                feature["codeResultMessageId"] = result["messageId"]
                touch(feature, "DEVELOPMENT_COMPLETE")
            elif (
                decision in {"REQUEST_CHANGES", "COMMENT"}
                and merge_status == "NOT_REQUESTED"
            ):
                feature["codeResultMessageId"] = result["messageId"]
                touch(feature, "CODE_CHANGES_REQUESTED")
                add_queue(state, feature["featureId"])
                touch(feature, "DEVELOPMENT_QUEUED")
            else:
                raise WorkflowError(
                    "invalid_transition",
                    "Code result does not authorize a supported transition",
                )
            record["status"] = "applied"
            record["appliedAt"] = utc_now()
        save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": duplicate,
        "featureId": feature["featureId"],
        "stage": feature["stage"],
    }


def normalize_artifacts(value: Any, field: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise WorkflowError("invalid_payload", f"{field} must be a non-empty array")
    artifacts: list[dict[str, str]] = []
    names: set[str] = set()
    for index, item in enumerate(value):
        obj = exact_keys(item, f"{field}[{index}]", {"name", "sha256"})
        name = require_string(obj["name"], f"{field}[{index}].name", maximum=200)
        if not ARTIFACT_NAME_RE.fullmatch(name) or name in names:
            raise WorkflowError(
                "invalid_payload", f"{field} artifact name is invalid or duplicated"
            )
        names.add(name)
        artifacts.append(
            {
                "name": name,
                "sha256": require_digest(obj["sha256"], f"{field}[{index}].sha256"),
            }
        )
    return sorted(artifacts, key=lambda item: item["name"])


def normalize_target(value: Any, field: str, repository_key: str) -> dict[str, Any]:
    obj = require_object(value, field)
    kind = obj.get("kind")
    if kind == "GITHUB_RELEASE":
        target = exact_keys(
            obj,
            field,
            {"kind", "repositoryKey", "tag", "releaseName", "artifacts"},
            {"targetId"},
        )
        if target["repositoryKey"] != repository_key:
            raise WorkflowError("repository_mismatch", f"{field}.repositoryKey differs")
        normalized = {
            "kind": kind,
            "repositoryKey": repository_key,
            "tag": require_string(target["tag"], f"{field}.tag", maximum=200),
            "releaseName": require_string(
                target["releaseName"], f"{field}.releaseName", maximum=200
            ),
            "artifacts": normalize_artifacts(target["artifacts"], f"{field}.artifacts"),
        }
    elif kind == "PYPI":
        target = exact_keys(
            obj,
            field,
            {"kind", "repository", "projectName", "version", "artifacts"},
            {"targetId"},
        )
        if target["repository"] not in {"PYPI", "TEST_PYPI"}:
            raise WorkflowError("invalid_payload", f"{field}.repository is unsupported")
        normalized = {
            "kind": kind,
            "repository": target["repository"],
            "projectName": normalized_project_name(
                require_string(
                    target["projectName"], f"{field}.projectName", maximum=200
                )
            ),
            "version": require_semver(target["version"], f"{field}.version"),
            "artifacts": normalize_artifacts(target["artifacts"], f"{field}.artifacts"),
        }
    else:
        raise WorkflowError("invalid_payload", f"{field}.kind is unsupported")
    target_id = digest(normalized)
    if (
        "targetId" in obj
        and require_digest(obj["targetId"], f"{field}.targetId") != target_id
    ):
        raise WorkflowError(
            "invalid_payload", f"{field}.targetId does not match target"
        )
    return {"targetId": target_id, **normalized}


def command_record_release_authorization(args: argparse.Namespace) -> dict[str, Any]:
    _, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    loaded = load_payload(args.authorization_file)
    validate_release_authorization_shape(loaded)
    draft = exact_keys(
        loaded,
        "ReleaseAuthorizationDraft",
        {
            "schemaVersion",
            "workflowId",
            "featureId",
            "mergeCommitSha",
            "version",
            "tag",
            "targets",
            "authorizedBy",
            "authorizationEvidence",
            "createdAt",
        },
        {"authorizationId"},
    )
    if (
        draft["schemaVersion"] != SCHEMA_VERSION
        or draft["workflowId"] != config["workflowId"]
    ):
        raise WorkflowError(
            "workflow_mismatch", "Release authorization workflow differs"
        )
    feature_id = require_feature_id(draft["featureId"])
    targets = [
        normalize_target(item, f"targets[{index}]", config["repository"]["key"])
        for index, item in enumerate(draft["targets"])
    ]
    targets.sort(key=lambda item: item["targetId"])
    if len({item["targetId"] for item in targets}) != len(targets):
        raise WorkflowError("invalid_payload", "Release targets must be unique")
    for target in targets:
        if target["kind"] == "GITHUB_RELEASE" and target["tag"] != draft["tag"]:
            raise WorkflowError(
                "invalid_payload", "GitHub Release target tag differs from release tag"
            )
        if target["kind"] == "PYPI" and target["version"] != draft["version"]:
            raise WorkflowError(
                "invalid_payload", "PyPI target version differs from release version"
            )
    normalized = {
        "schemaVersion": SCHEMA_VERSION,
        "workflowId": config["workflowId"],
        "featureId": feature_id,
        "mergeCommitSha": require_sha(draft["mergeCommitSha"], "mergeCommitSha"),
        "version": require_semver(draft["version"], "version"),
        "tag": require_string(draft["tag"], "tag", maximum=200),
        "targets": targets,
        "authorizedBy": require_string(
            draft["authorizedBy"], "authorizedBy", maximum=200
        ),
        "authorizationEvidence": require_string(
            draft["authorizationEvidence"], "authorizationEvidence", maximum=500
        ),
        "createdAt": require_timestamp(draft["createdAt"], "createdAt"),
    }
    normalized["authorizationId"] = digest(normalized)
    if (
        "authorizationId" in draft
        and draft["authorizationId"] != normalized["authorizationId"]
    ):
        raise WorkflowError(
            "invalid_payload", "authorizationId does not match authorization"
        )
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, feature_id)
        if feature["stage"] not in {"RELEASE_AWAITING_AUTHORIZATION", "RELEASE_FAILED"}:
            raise WorkflowError(
                "invalid_transition", "Feature is not awaiting release authorization"
            )
        if (
            feature.get("merge", {}).get("mergeCommitSha")
            != normalized["mergeCommitSha"]
        ):
            raise WorkflowError(
                "snapshot_mismatch", "Authorization merge commit differs"
            )
        existing = feature.get("release", {}).get("authorization")
        duplicate = existing == normalized
        if existing and not duplicate and feature["stage"] != "RELEASE_FAILED":
            raise WorkflowError(
                "release_not_authorized",
                "Another release authorization is already active",
            )
        if not duplicate:
            feature["release"] = {"authorization": normalized}
            touch(feature, "RELEASE_AUTHORIZED")
        elif feature["stage"] != "RELEASE_FAILED":
            touch(feature, "RELEASE_AUTHORIZED")
        save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": duplicate,
        "authorization": normalized,
        "stage": feature["stage"],
    }


def normalize_result_artifacts(value: Any, field: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise WorkflowError("invalid_payload", f"{field} must be an array")
    results: list[dict[str, str]] = []
    for index, item in enumerate(value):
        obj = exact_keys(item, f"{field}[{index}]", {"name", "sha256", "url"})
        results.append(
            {
                "name": require_string(
                    obj["name"], f"{field}[{index}].name", maximum=200
                ),
                "sha256": require_digest(obj["sha256"], f"{field}[{index}].sha256"),
                "url": require_https_url(obj["url"], f"{field}[{index}].url"),
            }
        )
    return sorted(results, key=lambda item: item["name"])


def normalize_target_result(
    value: Any, field: str, target: Mapping[str, Any]
) -> dict[str, Any]:
    obj = require_object(value, field)
    status = obj.get("status")
    common = {"targetId", "kind", "status"}
    if status == "FAILED":
        result = exact_keys(obj, field, common | {"error"})
        if result["targetId"] != target["targetId"] or result["kind"] != target["kind"]:
            raise WorkflowError(
                "release_not_authorized", f"{field} target identity differs"
            )
        return {
            "targetId": target["targetId"],
            "kind": target["kind"],
            "status": "FAILED",
            "error": require_string(result["error"], f"{field}.error", maximum=300),
        }
    if status != "PUBLISHED":
        raise WorkflowError("invalid_payload", f"{field}.status is unsupported")
    if target["kind"] == "GITHUB_RELEASE":
        result = exact_keys(
            obj,
            field,
            common | {"artifacts", "publishedAt", "releaseUrl", "tagCommitSha"},
        )
        artifacts = normalize_result_artifacts(
            result["artifacts"], f"{field}.artifacts"
        )
        release_url = require_canonical_https_path(
            result["releaseUrl"],
            f"{field}.releaseUrl",
            host="github.com",
            path=f"/{target['repositoryKey']}/releases/tag/{target['tag']}",
        )
        for index, artifact in enumerate(artifacts):
            require_canonical_https_path(
                artifact["url"],
                f"{field}.artifacts[{index}].url",
                host="github.com",
                path=(
                    f"/{target['repositoryKey']}/releases/download/"
                    f"{target['tag']}/{artifact['name']}"
                ),
            )
        normalized = {
            "targetId": target["targetId"],
            "kind": target["kind"],
            "status": "PUBLISHED",
            "artifacts": artifacts,
            "publishedAt": require_timestamp(
                result["publishedAt"], f"{field}.publishedAt"
            ),
            "releaseUrl": release_url,
            "tagCommitSha": require_sha(
                result["tagCommitSha"], f"{field}.tagCommitSha"
            ),
        }
    else:
        result = exact_keys(
            obj,
            field,
            common
            | {
                "artifacts",
                "publishedAt",
                "projectUrl",
                "repository",
                "projectName",
                "version",
            },
        )
        artifacts = normalize_result_artifacts(
            result["artifacts"], f"{field}.artifacts"
        )
        project_host = "pypi.org" if target["repository"] == "PYPI" else "test.pypi.org"
        project_url = require_canonical_https_path(
            result["projectUrl"],
            f"{field}.projectUrl",
            host=project_host,
            path=f"/project/{target['projectName']}/{target['version']}",
        )
        artifact_host = (
            "files.pythonhosted.org"
            if target["repository"] == "PYPI"
            else "test-files.pythonhosted.org"
        )
        for index, artifact in enumerate(artifacts):
            artifact_url = require_https_url(
                artifact["url"],
                f"{field}.artifacts[{index}].url",
                host=artifact_host,
            )
            parsed = urlsplit(artifact_url)
            try:
                port = parsed.port
            except ValueError as exc:
                raise WorkflowError(
                    "invalid_payload",
                    f"{field}.artifacts[{index}].url contains an invalid port",
                ) from exc
            if (
                port is not None
                or parsed.query
                or parsed.fragment
                or not unquote(parsed.path).endswith(f"/{artifact['name']}")
            ):
                raise WorkflowError(
                    "invalid_payload",
                    f"{field}.artifacts[{index}].url is not canonical for the authorized artifact",
                )
        normalized = {
            "targetId": target["targetId"],
            "kind": target["kind"],
            "status": "PUBLISHED",
            "artifacts": artifacts,
            "publishedAt": require_timestamp(
                result["publishedAt"], f"{field}.publishedAt"
            ),
            "projectUrl": project_url,
            "repository": result["repository"],
            "projectName": result["projectName"],
            "version": result["version"],
        }
        for name in ("repository", "projectName", "version"):
            if normalized[name] != target[name]:
                raise WorkflowError(
                    "release_not_authorized",
                    f"{field}.{name} differs from authorization",
                )
    if result["targetId"] != target["targetId"] or result["kind"] != target["kind"]:
        raise WorkflowError(
            "release_not_authorized", f"{field} target identity differs"
        )
    expected_artifacts = [
        (item["name"], item["sha256"]) for item in target["artifacts"]
    ]
    actual_artifacts = [
        (item["name"], item["sha256"]) for item in normalized["artifacts"]
    ]
    if actual_artifacts != expected_artifacts:
        raise WorkflowError(
            "release_not_authorized", f"{field} artifacts differ from authorization"
        )
    return normalized


def normalize_release_submission(
    value: Any,
    field: str,
    authorization_id: str,
    target_map: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    submission = exact_keys(
        value,
        field,
        {
            "authorizationId",
            "targets",
            "publishedAt",
            "submissionDigest",
        },
    )
    if (
        submission["authorizationId"] != authorization_id
        or not isinstance(submission["targets"], list)
        or not submission["targets"]
    ):
        raise WorkflowError("invalid_state", f"{field} is misbound or has no targets")
    target_values = [
        require_object(item, f"{field}.targets[{index}]")
        for index, item in enumerate(submission["targets"])
    ]
    target_ids = [item.get("targetId") for item in target_values]
    if any(target_id not in target_map for target_id in target_ids) or len(
        target_ids
    ) != len(set(target_ids)):
        raise WorkflowError(
            "invalid_state", f"{field} has unknown or duplicate targets"
        )
    targets = [
        normalize_target_result(
            item,
            f"{field}.targets[{index}]",
            target_map[item["targetId"]],
        )
        for index, item in enumerate(target_values)
    ]
    targets.sort(key=lambda item: item["targetId"])
    canonical = {
        "authorizationId": authorization_id,
        "targets": targets,
        "publishedAt": require_timestamp(
            submission["publishedAt"], f"{field}.publishedAt"
        ),
    }
    canonical["submissionDigest"] = digest(canonical)
    if submission != canonical:
        raise WorkflowError("invalid_state", f"{field} is not canonical")
    return canonical


def command_record_release_result(args: argparse.Namespace) -> dict[str, Any]:
    _, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    draft = load_payload(args.result_file)
    validate_release_result_shape(draft)
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature_id = require_feature_id(draft.get("featureId"))
        feature = feature_for(state, feature_id)
        if feature["stage"] not in {"RELEASE_AUTHORIZED", "RELEASE_FAILED", "RELEASED"}:
            raise WorkflowError(
                "invalid_transition", "Feature has no active release authorization"
            )
        authorization = feature.get("release", {}).get("authorization")
        if not authorization:
            raise WorkflowError(
                "release_not_authorized", "Release authorization is absent"
            )
        value = exact_keys(
            draft,
            "ReleaseResultDraft",
            {
                "schemaVersion",
                "workflowId",
                "featureId",
                "authorizationId",
                "mergeCommitSha",
                "version",
                "tag",
                "targets",
                "publishedAt",
            },
            {"proofDigest"},
        )
        for name in (
            "workflowId",
            "authorizationId",
            "mergeCommitSha",
            "version",
            "tag",
        ):
            expected = (
                authorization["authorizationId"]
                if name == "authorizationId"
                else authorization[name]
            )
            if value[name] != expected:
                raise WorkflowError(
                    "release_not_authorized", f"Release result {name} differs"
                )
        target_map = {item["targetId"]: item for item in authorization["targets"]}
        submitted_ids = (
            {item.get("targetId") for item in value["targets"]}
            if isinstance(value["targets"], list)
            else set()
        )
        previous = feature.get("release", {}).get("result")
        if (
            not submitted_ids
            or not submitted_ids <= set(target_map)
            or len(submitted_ids) != len(value["targets"])
        ):
            raise WorkflowError(
                "release_not_authorized",
                "Release result contains an unauthorized or duplicate target",
            )
        submitted_results = [
            normalize_target_result(
                item, f"targets[{index}]", target_map[item["targetId"]]
            )
            for index, item in enumerate(value["targets"])
        ]
        submitted_results.sort(key=lambda item: item["targetId"])
        submitted_at = require_timestamp(value["publishedAt"], "publishedAt")
        submission = {
            "authorizationId": authorization["authorizationId"],
            "targets": submitted_results,
            "publishedAt": submitted_at,
        }
        submission["submissionDigest"] = digest(submission)
        for item in submitted_results:
            if (
                item["kind"] == "GITHUB_RELEASE"
                and item["status"] == "PUBLISHED"
                and item["tagCommitSha"] != authorization["mergeCommitSha"]
            ):
                raise WorkflowError(
                    "snapshot_mismatch",
                    "GitHub release tag does not target merge commit",
                )
        if feature["stage"] == "RELEASED":
            if not previous or not all(
                item["status"] == "PUBLISHED" for item in previous["targets"]
            ):
                raise WorkflowError(
                    "invalid_state", "RELEASED feature lacks complete release proof"
                )
            last_submission = feature["release"].get("lastSubmission")
            cumulative_replay = (
                submitted_results == previous["targets"]
                and submitted_at == previous["publishedAt"]
                and (
                    "proofDigest" not in value
                    or value["proofDigest"] == previous["proofDigest"]
                )
            )
            if submission != last_submission and not cumulative_replay:
                raise WorkflowError(
                    "replay_conflict",
                    "Release replay must match the final submission or cumulative proof",
                )
            return {
                "ok": True,
                "duplicate": True,
                "result": previous,
                "stage": "RELEASED",
            }
        if (
            feature["stage"] == "RELEASE_FAILED"
            and previous
            and feature["release"].get("lastSubmission") == submission
        ):
            if (
                "proofDigest" in value
                and value["proofDigest"] != previous["proofDigest"]
            ):
                raise WorkflowError(
                    "invalid_payload", "proofDigest does not match stored result"
                )
            return {
                "ok": True,
                "duplicate": True,
                "result": previous,
                "stage": "RELEASE_FAILED",
            }
        if feature["stage"] == "RELEASE_FAILED" and previous:
            previous_by_id = {item["targetId"]: item for item in previous["targets"]}
            expected_ids = {
                target_id
                for target_id, item in previous_by_id.items()
                if item["status"] == "FAILED"
            }
            if submitted_ids != expected_ids:
                raise WorkflowError(
                    "release_not_authorized",
                    "Retry must contain exactly the previously failed release targets",
                )
        else:
            previous_by_id = {}
            if submitted_ids != set(target_map):
                raise WorkflowError(
                    "release_not_authorized", "Release result target set differs"
                )
        results = [
            item
            for target_id, item in previous_by_id.items()
            if target_id not in submitted_ids and item["status"] == "PUBLISHED"
        ] + submitted_results
        if {item["targetId"] for item in results} != set(target_map):
            raise WorkflowError(
                "release_not_authorized", "Cumulative release result target set differs"
            )
        results.sort(key=lambda item: item["targetId"])
        normalized = {
            "schemaVersion": SCHEMA_VERSION,
            "workflowId": config["workflowId"],
            "featureId": feature_id,
            "authorizationId": authorization["authorizationId"],
            "mergeCommitSha": authorization["mergeCommitSha"],
            "version": authorization["version"],
            "tag": authorization["tag"],
            "targets": results,
            "publishedAt": submitted_at,
        }
        normalized["proofDigest"] = digest(normalized)
        if "proofDigest" in value and value["proofDigest"] != normalized["proofDigest"]:
            raise WorkflowError("invalid_payload", "proofDigest does not match result")
        duplicate = (
            feature.get("release", {}).get("result") == normalized
            and feature.get("release", {}).get("lastSubmission") == submission
        )
        if duplicate:
            return {
                "ok": True,
                "duplicate": True,
                "result": normalized,
                "stage": feature["stage"],
            }
        submissions = feature["release"].get("submissions", [])
        if not isinstance(submissions, list):
            raise WorkflowError(
                "invalid_state", "Release submission history is malformed"
            )
        feature["release"]["result"] = normalized
        feature["release"]["lastSubmission"] = submission
        feature["release"]["submissions"] = [*submissions, submission]
        if all(item["status"] == "PUBLISHED" for item in results):
            touch(feature, "RELEASED")
        else:
            touch(feature, "RELEASE_FAILED")
        save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": duplicate,
        "result": normalized,
        "stage": feature["stage"],
    }


def command_close_feature(args: argparse.Namespace) -> dict[str, Any]:
    _, paths, config, _ = load_context(args.repo)
    require_role(config, args.task_id, "main")
    with locked(paths["lock"]):
        state = validate_state(load_json(paths["state"], "state"), config)
        feature = feature_for(state, args.feature_id)
        if feature["stage"] != "RELEASED":
            if feature["stage"] == "CLOSED":
                return {
                    "ok": True,
                    "duplicate": True,
                    "closure": feature["closure"],
                    "stage": "CLOSED",
                }
            raise WorkflowError(
                "invalid_transition", "Feature cannot close before successful release"
            )
        release = feature["release"]["result"]
        if not all(item["status"] == "PUBLISHED" for item in release["targets"]):
            raise WorkflowError(
                "invalid_transition", "Every release target must be PUBLISHED"
            )
        closure = {
            "releaseResultId": release["proofDigest"],
            "requirementsMessageId": feature.get("requirementsMessageId", ""),
            "planReviewResultMessageId": feature.get("planResultMessageId", ""),
            "codeReviewResultMessageId": feature.get("codeResultMessageId", ""),
            "mergeCommitSha": feature["merge"]["mergeCommitSha"],
            "releaseTargets": [item["targetId"] for item in release["targets"]],
            "scenariosSolved": [
                require_string(item, "scenario", maximum=300) for item in args.scenario
            ],
            "followUps": [
                require_string(item, "followUp", maximum=300) for item in args.follow_up
            ],
            "closedAt": utc_now(),
        }
        for name in ("planReviewResultMessageId", "codeReviewResultMessageId"):
            require_digest(closure[name], name)
        require_digest(closure["requirementsMessageId"], "requirementsMessageId")
        closure["closureId"] = digest(closure)
        validate_closure_shape(closure)
        feature["closure"] = closure
        touch(feature, "CLOSED")
        save_state(paths, state, config)
    return {
        "ok": True,
        "duplicate": False,
        "closure": closure,
        "stage": feature["stage"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_repo(
        name: str, help_text: str, *, task: bool = True
    ) -> argparse.ArgumentParser:
        item = sub.add_parser(name, help=help_text)
        item.add_argument("--repo", required=True)
        if task:
            item.add_argument("--task-id", required=True)
        return item

    begin_init = add_repo("begin-init", "Begin recoverable workflow Init", task=False)
    begin_init.add_argument("--goal-mode-authorized", action="store_true")
    begin_init.add_argument("--merge-mode", choices=MERGE_MODES, required=True)
    begin_init.add_argument("--merge-method", choices=MERGE_METHODS, default="squash")
    begin_init.add_argument("--delete-branch", action="store_true")

    record_init = add_repo(
        "record-init-task", "Record one task in the recoverable Init ledger", task=False
    )
    record_init.add_argument("--role", choices=ROLES, required=True)
    record_init.add_argument("--created-task-id", required=True)

    init = add_repo("init", "Finalize workflow Init", task=False)
    init.add_argument("--requirements-task-id", required=True)
    init.add_argument("--main-task-id", required=True)
    init.add_argument("--review-task-id", required=True)
    init.add_argument("--goal-mode-authorized", action="store_true")
    init.add_argument("--merge-mode", choices=MERGE_MODES, required=True)
    init.add_argument("--merge-method", choices=MERGE_METHODS, default="squash")
    init.add_argument("--delete-branch", action="store_true")

    status = add_repo("status", "Show sanitized status", task=False)
    status.add_argument("--task-id")

    ack = add_repo("ack-bootstrap", "Record role bootstrap")
    ack.add_argument("--role", choices=ROLES, required=True)

    req = add_repo("prepare-requirements", "Prepare confirmed requirements")
    req.add_argument("--feature-id", required=True)
    req.add_argument("--title", required=True)
    req.add_argument("--branch", required=True)
    req.add_argument("--requirements-path", required=True)
    req.add_argument("--requirements-commit-sha", required=True)
    req.add_argument("--confirmation-evidence", required=True)

    dispatched = add_repo(
        "mark-dispatched", "Record host-confirmed message delivery", task=False
    )
    dispatched.add_argument("--message-id", required=True)
    failed = add_repo(
        "mark-delivery-failed", "Record message delivery failure", task=False
    )
    failed.add_argument("--message-id", required=True)
    failed.add_argument("--reason", required=True)

    accept_req = add_repo("accept-requirements", "Accept requirements handoff")
    accept_req.add_argument("--payload-file", required=True)

    plan = add_repo("prepare-plan-review", "Prepare technical plan review")
    plan.add_argument("--feature-id", required=True)
    plan.add_argument("--plan-commit-sha", required=True)
    plan.add_argument("--requirements-path", required=True)
    plan.add_argument("--design-path", required=True)
    plan.add_argument("--implementation-plan-path", required=True)
    plan.add_argument("--acceptance-criteria-digest", required=True)
    plan.add_argument("--previous-result-message-id")

    accept_plan = add_repo("accept-plan-review", "Accept technical plan request")
    accept_plan.add_argument("--payload-file", required=True)

    plan_result = add_repo("prepare-plan-result", "Prepare technical plan result")
    plan_result.add_argument("--request-file", required=True)
    plan_result.add_argument("--decision", choices=("PASS", "FAIL"), required=True)
    plan_result.add_argument("--blockers", type=int, default=0)
    plan_result.add_argument("--majors", type=int, default=0)
    plan_result.add_argument("--minors", type=int, default=0)
    add_report_args(plan_result)
    plan_result.add_argument("--summary", required=True)

    apply_plan = add_repo("apply-plan-result", "Apply technical plan result")
    apply_plan.add_argument("--payload-file", required=True)

    start = add_repo("start-development", "Prepare or activate a GoalRun")
    start.add_argument("--feature-id", required=True)
    start.add_argument("--objective", required=True)
    start.add_argument("--activate", action="store_true")
    start.add_argument("--goal-run-id")
    start.add_argument("--goal-thread-id")

    for name in ("block-development", "resume-development", "complete-development"):
        item = add_repo(name, f"{name.replace('-', ' ').title()} GoalRun")
        item.add_argument("--feature-id", required=True)
        item.add_argument("--goal-run-id", required=True)
        if name == "block-development":
            item.add_argument("--reason", required=True)
        if name == "complete-development":
            item.add_argument("--tokens-used", type=int)
            item.add_argument("--time-used-seconds", type=int)

    code = add_repo("prepare-code-review", "Prepare exact-head code review")
    code.add_argument("--feature-id", required=True)
    code.add_argument("--pr-number", type=int, required=True)
    code.add_argument("--pr-url", required=True)
    code.add_argument("--base-ref", required=True)
    code.add_argument("--base-sha", required=True)
    code.add_argument("--head-ref", required=True)
    code.add_argument("--head-sha", required=True)
    code.add_argument("--previous-result-message-id")

    accept_code = add_repo("accept-code-review", "Accept exact-head code review")
    accept_code.add_argument("--payload-file", required=True)

    code_result = add_repo("prepare-code-result", "Prepare code review result")
    code_result.add_argument("--request-file", required=True)
    code_result.add_argument(
        "--decision", choices=("APPROVE", "COMMENT", "REQUEST_CHANGES"), required=True
    )
    code_result.add_argument("--blockers", type=int, default=0)
    code_result.add_argument("--majors", type=int, default=0)
    code_result.add_argument("--minors", type=int, default=0)
    add_report_args(code_result)
    code_result.add_argument(
        "--checks-status",
        choices=("PASSING", "FAILING", "PENDING", "UNAVAILABLE"),
        required=True,
    )
    code_result.add_argument("--checks-checked-at", required=True)
    code_result.add_argument("--checks-url")
    code_result.add_argument(
        "--merge-status",
        choices=("READY", "MERGED", "FAILED", "NOT_REQUESTED", "STALE"),
        required=True,
    )
    code_result.add_argument("--merge-method", choices=MERGE_METHODS)
    code_result.add_argument("--merge-url")
    code_result.add_argument("--merge-sha")
    code_result.add_argument("--merged-at")
    code_result.add_argument("--merge-error")
    code_result.add_argument("--summary", required=True)

    apply_code = add_repo("apply-code-result", "Apply code review result")
    apply_code.add_argument("--payload-file", required=True)

    auth = add_repo(
        "record-release-authorization", "Record exact release authorization"
    )
    auth.add_argument("--authorization-file", required=True)
    result = add_repo("record-release-result", "Record release target results")
    result.add_argument("--result-file", required=True)
    close = add_repo("close-feature", "Close a released feature")
    close.add_argument("--feature-id", required=True)
    close.add_argument("--scenario", action="append", default=[], required=True)
    close.add_argument("--follow-up", action="append", default=[])
    return parser


def add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report-branch", required=True)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--report-commit-sha", required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--report-json-path")
    parser.add_argument("--report-json-sha256")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "begin-init": command_begin_init,
        "record-init-task": command_record_init_task,
        "init": command_init,
        "status": command_status,
        "ack-bootstrap": command_ack_bootstrap,
        "prepare-requirements": command_prepare_requirements,
        "mark-dispatched": lambda item: command_mark_dispatch(item, False),
        "mark-delivery-failed": lambda item: command_mark_dispatch(item, True),
        "accept-requirements": command_accept_requirements,
        "prepare-plan-review": command_prepare_plan_review,
        "accept-plan-review": command_accept_plan_review,
        "prepare-plan-result": command_prepare_plan_result,
        "apply-plan-result": command_apply_plan_result,
        "start-development": command_start_development,
        "block-development": lambda item: command_goal_transition(item, "block"),
        "resume-development": lambda item: command_goal_transition(item, "resume"),
        "complete-development": lambda item: command_goal_transition(item, "complete"),
        "prepare-code-review": command_prepare_code_review,
        "accept-code-review": command_accept_code_review,
        "prepare-code-result": command_prepare_code_result,
        "apply-code-result": command_apply_code_result,
        "record-release-authorization": command_record_release_authorization,
        "record-release-result": command_record_release_result,
        "close-feature": command_close_feature,
    }
    try:
        result = handlers[args.command](args)
    except WorkflowError as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"kind": exc.kind, "message": exc.message}},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
