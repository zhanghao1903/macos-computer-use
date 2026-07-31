#!/usr/bin/env python3
"""Offline Claude Code CLI stub used only by bridge tests."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

SELF = Path(__file__).resolve()
MODE_PATH = SELF.with_suffix(".mode")
LOG_PATH = SELF.with_suffix(".log")


def mode() -> str:
    try:
        return MODE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "success"


def option(name: str) -> str | None:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError):
        return None


def parse_prompt() -> tuple[dict, str]:
    prompt = sys.argv[-1]
    marker = "Transport JSON:\n"
    if marker not in prompt:
        raise ValueError("transport marker missing")
    request = json.loads(prompt.split(marker, 1)[1])
    digest_marker = "Canonical request SHA-256: "
    request_digest = prompt.split(digest_marker, 1)[1].splitlines()[0]
    return request, request_digest


def record() -> None:
    value = {
        "argv": sys.argv[1:-1],
        "promptLength": len(sys.argv[-1]) if len(sys.argv) > 1 else 0,
        "credentialEnvironment": sorted(
            key
            for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
            if key in os.environ
        ),
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def review_common(request: dict, request_digest: str, session_id: str) -> dict:
    return {
        "schemaVersion": 1,
        "messageId": request["messageId"],
        "requestDigest": request_digest,
        "workflowId": request["workflowId"],
        "repositoryKey": request["repositoryKey"],
        "featureId": request["featureId"],
        "cycle": request["cycle"],
        "sessionId": session_id,
        "counts": {"blocker": 0, "major": 0, "minor": 0},
        "findings": [],
        "verification": [
            {
                "name": "offline-fake",
                "status": "SKIPPED",
                "evidence": "Test fixture produced deterministic output.",
            }
        ],
        "reportMarkdown": "# Offline Review\n\nNo findings in the fake fixture.\n",
        "summary": "Offline fake review completed.",
    }


def structured_output(request: dict, request_digest: str, session_id: str) -> dict:
    schema = json.loads(option("--json-schema") or "{}")
    title = schema.get("title")
    if title == "ClaudeBootstrapOutput":
        return {
            "schemaVersion": 1,
            "type": "ClaudeRoleReady",
            "messageId": request["messageId"],
            "requestDigest": request_digest,
            "workflowId": request["workflowId"],
            "repositoryKey": request["repositoryKey"],
            "sessionId": session_id,
            "role": request["role"],
            "status": "READY",
        }
    if title == "ClaudeFrontendOutput":
        return {
            "schemaVersion": 1,
            "type": "ClaudeFrontendOutput",
            "messageId": request["messageId"],
            "requestDigest": request_digest,
            "workflowId": request["workflowId"],
            "repositoryKey": request["repositoryKey"],
            "featureId": request["featureId"],
            "cycle": request["cycle"],
            "sessionId": session_id,
            "status": "BLOCKED",
            "startHeadSha": request["startHeadSha"],
            "endHeadSha": None,
            "commitShas": [],
            "modifiedPaths": [],
            "verification": [
                {
                    "name": "offline-fake",
                    "status": "SKIPPED",
                    "evidence": "No repository mutation in dispatch fixture.",
                }
            ],
            "summary": "Offline fake intentionally blocked frontend execution.",
            "questions": ["Provide the real Claude environment."],
            "error": None,
        }
    if title == "ClaudePlanReviewOutput":
        result = review_common(request, request_digest, session_id)
        result.update(
            {
                "type": "ClaudePlanReviewOutput",
                "decision": "PASS",
                "reviewedSnapshot": {
                    "planCommitSha": request["body"]["plan"]["planCommitSha"],
                    "compositeSha256": request["body"]["plan"]["compositeSha256"],
                },
            }
        )
        return result
    if title == "ClaudeCodeReviewOutput":
        pull = request["body"]["pullRequest"]
        result = review_common(request, request_digest, session_id)
        result.update(
            {
                "type": "ClaudeCodeReviewOutput",
                "decision": "APPROVE",
                "reviewedSnapshot": {
                    "pullRequestUrl": pull["url"],
                    "baseSha": pull["baseSha"],
                    "headSha": pull["headSha"],
                },
            }
        )
        return result
    raise ValueError(f"unsupported schema title {title!r}")


def main() -> int:
    current_mode = mode()
    if sys.argv[1:] == ["--version"]:
        print("2.1.999 (offline fake)")
        return 0
    if sys.argv[1:] == ["auth", "status"]:
        if current_mode == "auth-fail":
            return 1
        print('{"loggedIn":true}')
        return 0

    record()
    if current_mode == "nonzero":
        return 7
    if current_mode == "timeout":
        time.sleep(5)
        return 0
    if current_mode == "malformed":
        print("not-json")
        return 0

    request, request_digest = parse_prompt()
    session_id = option("--session-id") or option("--resume")
    if session_id is None:
        raise ValueError("session option missing")
    result = structured_output(request, request_digest, session_id)
    if current_mode == "invalid-structured":
        result.pop("requestDigest", None)
    if current_mode == "wrong-snapshot" and "reviewedSnapshot" in result:
        snapshot = result["reviewedSnapshot"]
        first_key = next(iter(snapshot))
        snapshot[first_key] = "f" * (
            64 if first_key == "compositeSha256" else 40
        )
    wrapper_session = (
        "00000000-0000-4000-8000-000000000000"
        if current_mode == "wrong-session"
        else session_id
    )
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "session_id": wrapper_session,
                "structured_output": result,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
