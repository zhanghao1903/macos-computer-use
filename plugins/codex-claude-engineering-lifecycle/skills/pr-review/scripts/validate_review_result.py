#!/usr/bin/env python3
"""Validate a pr-review result schema and its decision/re-review invariants."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable


class DuplicateKeyError(ValueError):
    """Raised when a JSON object repeats a key."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def _pointer(parts: Iterable[Any]) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _find_repository_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _unique_map(
    items: list[dict[str, Any]],
    key: str,
    path: str,
    code: str,
    errors: list[tuple[str, str, str]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        item_key = item.get(key)
        if item_key in result:
            errors.append((code, f"{path}/{index}/{key}", f"duplicate identifier {item_key!r}"))
        elif isinstance(item_key, str):
            result[item_key] = item
    return result


def _schema_errors(
    data: dict[str, Any],
    schema: dict[str, Any],
    prefix: str = "",
) -> list[tuple[str, str, str]]:
    from jsonschema import Draft202012Validator, FormatChecker

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[tuple[str, str, str]] = []
    for error in validator.iter_errors(data):
        pointer = _pointer(error.absolute_path)
        if prefix:
            pointer = prefix.rstrip("/") + (pointer if pointer != "/" else "")
        errors.append(("SCHEMA", pointer or "/", error.message))
    return errors


def _validate_common(
    data: dict[str, Any],
    errors: list[tuple[str, str, str]],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    findings = data.get("findings", [])
    finding_map = _unique_map(findings, "id", "/findings", "DUPLICATE_FINDING", errors)
    open_blockers = {
        finding_id
        for finding_id, finding in finding_map.items()
        if finding.get("blocking") is True and finding.get("status") == "open"
    }
    declared_blockers = set(data.get("decision", {}).get("blocking_finding_ids", []))
    if open_blockers != declared_blockers:
        errors.append(
            (
                "BLOCKER_SET_MISMATCH",
                "/decision/blocking_finding_ids",
                f"expected {sorted(open_blockers)}, got {sorted(declared_blockers)}",
            )
        )

    open_actions = {
        action.get("finding_id")
        for action in data.get("required_actions", [])
        if action.get("status") == "open"
    }
    if open_actions != open_blockers:
        errors.append(
            (
                "ACTION_SET_MISMATCH",
                "/required_actions",
                f"open action IDs must equal open blockers: {sorted(open_blockers)}",
            )
        )

    decision = data.get("decision", {})
    status = decision.get("status")
    mergeable = decision.get("mergeable")
    report_status = data.get("review", {}).get("report_status")
    if open_blockers and (status != "REQUEST_CHANGES" or mergeable is not False):
        errors.append(
            (
                "BLOCKER_DECISION_MISMATCH",
                "/decision",
                "open blockers require REQUEST_CHANGES and mergeable=false",
            )
        )
    if not open_blockers and status == "REQUEST_CHANGES":
        errors.append(
            (
                "REQUEST_CHANGES_WITHOUT_BLOCKER",
                "/decision/status",
                "REQUEST_CHANGES requires at least one open blocking finding",
            )
        )
    if status == "APPROVE":
        if open_blockers or mergeable is not True or report_status != "CURRENT":
            errors.append(
                (
                    "INVALID_APPROVAL",
                    "/decision",
                    "APPROVE requires no open blockers, mergeable=true, and a CURRENT report",
                )
            )
    if status == "INCOMPLETE" and mergeable is not None:
        errors.append(
            (
                "INCOMPLETE_MERGEABLE",
                "/decision/mergeable",
                "INCOMPLETE requires mergeable=null",
            )
        )
    if report_status == "STALE" and (status != "INCOMPLETE" or mergeable is not None):
        errors.append(
            (
                "STALE_DECISION",
                "/review/report_status",
                "a STALE report must be INCOMPLETE with mergeable=null",
            )
        )
    return finding_map, open_blockers


def _validate_v11(
    data: dict[str, Any],
    result_path: Path,
    schema: dict[str, Any],
    errors: list[tuple[str, str, str]],
    finding_map: dict[str, dict[str, Any]],
    open_blockers: set[str],
) -> None:
    review = data["review"]
    decision = data["decision"]
    head_sha = review["head_sha"]
    context = data["review_context"]

    for index, finding in enumerate(data["findings"]):
        if finding["location"]["commit_sha"] != head_sha:
            errors.append(
                (
                    "FINDING_HEAD_MISMATCH",
                    f"/findings/{index}/location/commit_sha",
                    "finding location must use the current reviewed head SHA",
                )
            )

    for index, run in enumerate(data["validation"]["reviewer_runs"]):
        if run["head_sha"] != head_sha:
            errors.append(
                (
                    "RUN_HEAD_MISMATCH",
                    f"/validation/reviewer_runs/{index}/head_sha",
                    "reviewer run must use the current reviewed head SHA",
                )
            )
        if (
            decision["status"] == "APPROVE"
            and run["required_for_approval"]
            and run["status"] != "PASS"
        ):
            errors.append(
                (
                    "REQUIRED_RUN_FAILED",
                    f"/validation/reviewer_runs/{index}/status",
                    "a required approval check did not pass",
                )
            )

    for index, check in enumerate(data["validation"]["ci_checks"]):
        if check["head_sha"] != head_sha:
            errors.append(
                (
                    "CI_HEAD_MISMATCH",
                    f"/validation/ci_checks/{index}/head_sha",
                    "CI check must use the current reviewed head SHA",
                )
            )
        if decision["status"] == "APPROVE" and check["status"] != "PASS":
            errors.append(
                (
                    "CI_NOT_PASSING",
                    f"/validation/ci_checks/{index}/status",
                    "all recorded current-head CI checks must pass before approval",
                )
            )

    assumptions = _unique_map(
        data["assumptions"],
        "id",
        "/assumptions",
        "DUPLICATE_ASSUMPTION",
        errors,
    )
    for index, assumption in enumerate(data["assumptions"]):
        if assumption["status"] == "VERIFIED" and (
            not assumption.get("method") or not assumption.get("evidence")
        ):
            errors.append(
                (
                    "UNSUPPORTED_VERIFICATION",
                    f"/assumptions/{index}",
                    "VERIFIED assumptions require both method and evidence",
                )
            )
        if (
            decision["status"] == "APPROVE"
            and assumption["decision_critical"]
            and assumption["status"] != "VERIFIED"
        ):
            errors.append(
                (
                    "MATERIAL_ASSUMPTION_UNRESOLVED",
                    f"/assumptions/{index}/status",
                    "decision-critical assumptions must be VERIFIED before approval",
                )
            )
    surface_finding_ids: set[str] = set()
    surface_paths: set[str] = set()
    high_risk_surface = False
    for index, surface in enumerate(context["forward_risk_review"]):
        refs = set(surface["finding_ids"])
        surface_finding_ids.update(refs)
        surface_paths.update(surface["affected_paths"])
        missing_refs = refs - set(finding_map)
        if missing_refs:
            errors.append(
                (
                    "UNKNOWN_SURFACE_FINDING",
                    f"/review_context/forward_risk_review/{index}/finding_ids",
                    f"unknown finding IDs: {sorted(missing_refs)}",
                )
            )
        if surface["result"] == "FAIL" and not refs:
            errors.append(
                (
                    "FAILED_SURFACE_WITHOUT_FINDING",
                    f"/review_context/forward_risk_review/{index}",
                    "a failed risk surface must reference at least one finding",
                )
            )
        if set(surface["risk_triggers"]) & {
            "public-contract",
            "trust-boundary",
            "mutation-recovery",
        }:
            high_risk_surface = True

    if context["kind"] == "INITIAL":
        unexpected = {
            key
            for key in (
                "previous_review",
                "delta_review",
                "finding_revalidation",
                "approval_renewal",
            )
            if key in context
        }
        if unexpected:
            errors.append(
                (
                    "INITIAL_HAS_REREVIEW_STATE",
                    "/review_context",
                    f"INITIAL review must not contain {sorted(unexpected)}",
                )
            )
        if decision["status"] == "APPROVE" and any(
            surface["result"] != "PASS" for surface in context["forward_risk_review"]
        ):
            errors.append(
                (
                    "INCOMPLETE_FORWARD_REVIEW",
                    "/review_context/forward_risk_review",
                    "APPROVE requires every forward-risk surface to pass",
                )
            )
        return

    previous = context["previous_review"]
    delta = context["delta_review"]
    revalidations = context["finding_revalidation"]
    renewal = context["approval_renewal"]

    if previous["repository"] != review["repository"] or previous["pr_number"] != review["pr_number"]:
        errors.append(
            (
                "PREVIOUS_REVIEW_TARGET_MISMATCH",
                "/review_context/previous_review",
                "previous review repository and PR must match the current review",
            )
        )

    relative = Path(previous["result_path"])
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(
            (
                "UNSAFE_PREVIOUS_PATH",
                "/review_context/previous_review/result_path",
                "previous result path must be repository-relative without '..'",
            )
        )
        previous_data = None
    else:
        repository_root = _find_repository_root(result_path.parent)
        previous_path = (repository_root / relative).resolve()
        try:
            previous_path.relative_to(repository_root)
        except ValueError:
            errors.append(
                (
                    "UNSAFE_PREVIOUS_PATH",
                    "/review_context/previous_review/result_path",
                    "previous result path escapes the repository",
                )
            )
            previous_data = None
        else:
            if not previous_path.is_file():
                errors.append(
                    (
                        "PREVIOUS_RESULT_MISSING",
                        "/review_context/previous_review/result_path",
                        f"previous result does not exist: {previous_path}",
                    )
                )
                previous_data = None
            else:
                digest = hashlib.sha256(previous_path.read_bytes()).hexdigest()
                if digest != previous["result_sha256"]:
                    errors.append(
                        (
                            "PREVIOUS_RESULT_HASH_MISMATCH",
                            "/review_context/previous_review/result_sha256",
                            f"expected {digest}",
                        )
                    )
                try:
                    previous_data = _load_json(previous_path)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(
                        (
                            "PREVIOUS_RESULT_INVALID_JSON",
                            "/review_context/previous_review/result_path",
                            str(exc),
                        )
                    )
                    previous_data = None

    previous_finding_map: dict[str, dict[str, Any]] = {}
    if previous_data is not None:
        errors.extend(_schema_errors(previous_data, schema, "/review_context/previous_result"))
        declared_pairs = (
            ("repository", previous_data.get("review", {}).get("repository")),
            ("pr_number", previous_data.get("review", {}).get("pr_number")),
            ("base_sha", previous_data.get("review", {}).get("base_sha")),
            ("head_sha", previous_data.get("review", {}).get("head_sha")),
            ("reviewed_at", previous_data.get("review", {}).get("reviewed_at")),
            ("decision", previous_data.get("decision", {}).get("status")),
        )
        for key, actual in declared_pairs:
            if previous.get(key) != actual:
                errors.append(
                    (
                        "PREVIOUS_SNAPSHOT_MISMATCH",
                        f"/review_context/previous_review/{key}",
                        f"declared {previous.get(key)!r}, previous result has {actual!r}",
                    )
                )
        previous_finding_map = {
            finding["id"]: finding for finding in previous_data.get("findings", [])
        }
        previous_ids = set(previous_finding_map)
        if set(previous["finding_ids"]) != previous_ids:
            errors.append(
                (
                    "PREVIOUS_FINDING_SET_MISMATCH",
                    "/review_context/previous_review/finding_ids",
                    f"expected {sorted(previous_ids)}",
                )
            )
        prior_blockers = set(
            previous_data.get("decision", {}).get("blocking_finding_ids", [])
        )
        if set(previous["blocking_finding_ids"]) != prior_blockers:
            errors.append(
                (
                    "PREVIOUS_BLOCKER_SET_MISMATCH",
                    "/review_context/previous_review/blocking_finding_ids",
                    f"expected {sorted(prior_blockers)}",
                )
            )

    endpoint_pairs = (
        ("previous_base_sha", previous["base_sha"]),
        ("previous_head_sha", previous["head_sha"]),
        ("current_base_sha", review["base_sha"]),
        ("current_head_sha", review["head_sha"]),
    )
    for key, expected in endpoint_pairs:
        if delta[key] != expected:
            errors.append(
                (
                    "DELTA_ENDPOINT_MISMATCH",
                    f"/review_context/delta_review/{key}",
                    f"expected {expected}",
                )
            )

    triggers = set(delta["triggers"])
    head_changed = previous["head_sha"] != review["head_sha"]
    base_changed = previous["base_sha"] != review["base_sha"]
    if head_changed != ("HEAD_CHANGED" in triggers):
        errors.append(
            (
                "HEAD_TRIGGER_MISMATCH",
                "/review_context/delta_review/triggers",
                "HEAD_CHANGED must exactly match whether the head SHA changed",
            )
        )
    if base_changed != ("BASE_CHANGED" in triggers):
        errors.append(
            (
                "BASE_TRIGGER_MISMATCH",
                "/review_context/delta_review/triggers",
                "BASE_CHANGED must exactly match whether the base SHA changed",
            )
        )
    if not head_changed and not base_changed and not triggers & {
        "EVIDENCE_CHANGED",
        "REVIEW_CORRECTION",
        "MANUAL_REVIEW",
    }:
        errors.append(
            (
                "REREVIEW_TRIGGER_MISSING",
                "/review_context/delta_review/triggers",
                "same-snapshot re-review requires an evidence, correction, or manual trigger",
            )
        )
    expected_range = f"{previous['head_sha']}..{review['head_sha']}"
    if delta["commit_range"] != expected_range:
        errors.append(
            (
                "DELTA_RANGE_MISMATCH",
                "/review_context/delta_review/commit_range",
                f"expected {expected_range}",
            )
        )
    if head_changed and not delta["commits_reviewed"]:
        errors.append(
            (
                "DELTA_COMMITS_MISSING",
                "/review_context/delta_review/commits_reviewed",
                "a changed head requires the delta commit list",
            )
        )

    changed = set(delta["changed_files"])
    reviewed = set(delta["reviewed_files"])
    excluded_paths = [item["path"] for item in delta["excluded_files"]]
    excluded = set(excluded_paths)
    unclassified = set(delta["unclassified_changes"])
    if len(excluded) != len(excluded_paths):
        errors.append(
            (
                "DUPLICATE_EXCLUDED_PATH",
                "/review_context/delta_review/excluded_files",
                "excluded paths must be unique",
            )
        )
    if (reviewed & excluded) or (reviewed & unclassified) or (excluded & unclassified):
        errors.append(
            (
                "DELTA_PATH_OVERLAP",
                "/review_context/delta_review",
                "reviewed, excluded, and unclassified delta paths must be disjoint",
            )
        )
    if reviewed | excluded | unclassified != changed:
        errors.append(
            (
                "DELTA_PATH_COVERAGE",
                "/review_context/delta_review",
                "reviewed, excluded, and unclassified paths must exactly cover changed_files",
            )
        )
    uncovered_surface_paths = reviewed - surface_paths
    if uncovered_surface_paths:
        errors.append(
            (
                "RISK_SURFACE_PATH_COVERAGE",
                "/review_context/forward_risk_review",
                f"reviewed delta paths lack a risk surface: {sorted(uncovered_surface_paths)}",
            )
        )

    revalidation_map = _unique_map(
        revalidations,
        "finding_id",
        "/review_context/finding_revalidation",
        "DUPLICATE_REVALIDATION",
        errors,
    )
    previous_ids = set(previous_finding_map) or set(previous["finding_ids"])
    if set(revalidation_map) != previous_ids:
        errors.append(
            (
                "REVALIDATION_SET_MISMATCH",
                "/review_context/finding_revalidation",
                f"revalidation IDs must equal prior finding IDs: {sorted(previous_ids)}",
            )
        )
    missing_current = previous_ids - set(finding_map)
    if missing_current:
        errors.append(
            (
                "PRIOR_FINDING_DROPPED",
                "/findings",
                f"prior finding IDs missing from current result: {sorted(missing_current)}",
            )
        )
    for finding_id, transition in revalidation_map.items():
        prior = previous_finding_map.get(finding_id)
        current = finding_map.get(finding_id)
        if prior and transition["previous_status"] != prior["status"]:
            errors.append(
                (
                    "PREVIOUS_STATUS_MISMATCH",
                    f"/review_context/finding_revalidation/{finding_id}",
                    f"expected previous status {prior['status']}",
                )
            )
        if current and transition["current_status"] != current["status"]:
            errors.append(
                (
                    "CURRENT_STATUS_MISMATCH",
                    f"/review_context/finding_revalidation/{finding_id}",
                    f"expected current status {current['status']}",
                )
            )
        if prior and current and prior.get("fingerprint") and current.get("fingerprint"):
            if prior["fingerprint"] != current["fingerprint"]:
                errors.append(
                    (
                        "FINGERPRINT_DRIFT",
                        f"/findings/{finding_id}/fingerprint",
                        "a preserved finding ID must keep its fingerprint",
                    )
                )
        if transition["current_status"] == "accepted-risk" and not all(
            transition.get(key) for key in ("accepted_by", "acceptance_rationale", "accepted_at")
        ):
            errors.append(
                (
                    "UNAUTHORIZED_RISK_ACCEPTANCE",
                    f"/review_context/finding_revalidation/{finding_id}",
                    "accepted-risk requires accepter, rationale, and time",
                )
            )

    new_ids = set(finding_map) - previous_ids
    missing_forward_findings = new_ids - surface_finding_ids
    if missing_forward_findings:
        errors.append(
            (
                "NEW_FINDING_NOT_IN_FORWARD_REVIEW",
                "/review_context/forward_risk_review",
                f"new findings lack a forward-risk surface: {sorted(missing_forward_findings)}",
            )
        )
    for finding_id in new_ids:
        if finding_map[finding_id].get("origin") == "BASE_DIFF":
            errors.append(
                (
                    "INVALID_NEW_FINDING_ORIGIN",
                    f"/findings/{finding_id}/origin",
                    "a re-review-only finding must describe whether it was introduced, exposed, or previously missed",
                )
            )

    revalidation_complete = set(revalidation_map) == previous_ids
    forward_complete = all(
        surface["result"] != "PARTIAL" for surface in context["forward_risk_review"]
    )
    classified = (
        not unclassified
        and reviewed | excluded == changed
        and delta["full_pr_diff_reconciled"]
    )
    expected_flags = {
        "previous_findings_revalidated": revalidation_complete,
        "forward_risk_review_completed": forward_complete,
        "all_delta_changes_classified": classified,
    }
    if renewal["old_decision_invalidated"] is not True:
        errors.append(
            (
                "OLD_DECISION_NOT_INVALIDATED",
                "/review_context/approval_renewal/old_decision_invalidated",
                "every re-review must invalidate the previous decision",
            )
        )
    for key, expected in expected_flags.items():
        if renewal[key] is not expected:
            errors.append(
                (
                    "RENEWAL_GATE_MISMATCH",
                    f"/review_context/approval_renewal/{key}",
                    f"expected {expected}",
                )
            )

    if decision["status"] == "APPROVE":
        required_flags = (
            "old_decision_invalidated",
            "previous_findings_revalidated",
            "forward_risk_review_completed",
            "all_delta_changes_classified",
            "current_head_validation_complete",
        )
        if not all(renewal[key] for key in required_flags):
            errors.append(
                (
                    "APPROVAL_RENEWAL_GATE_FAILED",
                    "/review_context/approval_renewal",
                    "all approval-renewal gates must pass before APPROVE",
                )
            )
        if renewal["decision_blocking_limitations"]:
            errors.append(
                (
                    "APPROVAL_HAS_BLOCKING_LIMITATION",
                    "/review_context/approval_renewal/decision_blocking_limitations",
                    "APPROVE cannot retain a decision-blocking limitation",
                )
            )
        if renewal["result"] != "GRANTED":
            errors.append(
                (
                    "RENEWAL_NOT_GRANTED",
                    "/review_context/approval_renewal/result",
                    "APPROVE requires approval renewal GRANTED",
                )
            )
        if any(surface["result"] != "PASS" for surface in context["forward_risk_review"]):
            errors.append(
                (
                    "APPROVAL_FORWARD_RISK_FAILED",
                    "/review_context/forward_risk_review",
                    "every forward-risk surface must pass before APPROVE",
                )
            )
        if high_risk_surface and renewal["independent_pass"]["status"] != "PASS":
            errors.append(
                (
                    "INDEPENDENT_PASS_REQUIRED",
                    "/review_context/approval_renewal/independent_pass/status",
                    "public-contract, trust-boundary, or mutation-recovery approval requires an independent pass",
                )
            )
    elif renewal["result"] == "GRANTED":
        errors.append(
            (
                "GRANTED_WITHOUT_APPROVAL",
                "/review_context/approval_renewal/result",
                "approval renewal can be GRANTED only when the current decision is APPROVE",
            )
        )
    elif decision["status"] == "REQUEST_CHANGES" and renewal["result"] != "WITHHELD":
        errors.append(
            (
                "RENEWAL_RESULT_MISMATCH",
                "/review_context/approval_renewal/result",
                "REQUEST_CHANGES requires approval renewal WITHHELD",
            )
        )
    elif decision["status"] == "INCOMPLETE" and renewal["result"] != "INCOMPLETE":
        errors.append(
            (
                "RENEWAL_RESULT_MISMATCH",
                "/review_context/approval_renewal/result",
                "INCOMPLETE requires approval renewal INCOMPLETE",
            )
        )

    if open_blockers and renewal["result"] == "GRANTED":
        errors.append(
            (
                "BLOCKER_RENEWAL_GRANTED",
                "/review_context/approval_renewal/result",
                "approval renewal cannot be granted with open blockers",
            )
        )


def validate_result(result_path: Path) -> list[tuple[str, str, str]]:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "pr-review-result.schema.json"
    schema = _load_json(schema_path)
    data = _load_json(result_path)
    errors = _schema_errors(data, schema)
    if errors:
        return sorted(errors, key=lambda item: (item[1], item[0], item[2]))
    if data["schema_version"] == "1.0":
        return []
    finding_map, open_blockers = _validate_common(data, errors)
    _validate_v11(data, result_path, schema, errors, finding_map, open_blockers)
    return sorted(errors, key=lambda item: (item[1], item[0], item[2]))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_review_result.py <pr-review-result.json>", file=sys.stderr)
        return 2
    result_path = Path(argv[1])
    try:
        from jsonschema import Draft202012Validator  # noqa: F401
    except ImportError:
        print("error: jsonschema is required to validate review results", file=sys.stderr)
        return 2
    try:
        errors = validate_result(result_path)
    except (OSError, ValueError, json.JSONDecodeError, DuplicateKeyError) as exc:
        print(f"INVALID {result_path}", file=sys.stderr)
        print(f"JSON / {exc}", file=sys.stderr)
        return 1
    if errors:
        print(f"INVALID {result_path}", file=sys.stderr)
        for code, pointer, message in errors:
            print(f"{code} {pointer} {message}", file=sys.stderr)
        return 1
    print(f"VALID {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
