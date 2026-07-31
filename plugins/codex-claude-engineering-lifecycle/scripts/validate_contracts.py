#!/usr/bin/env python3
"""Validate Codex-Claude lifecycle schemas and contract fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

CONTRACTS = {
    "requirements-handoff": (
        "requirements-handoff.schema.json",
        "RequirementsHandoff",
        "workflow",
    ),
    "technical-plan-review-request": (
        "technical-plan-review-request.schema.json",
        "TechnicalPlanReviewRequest",
        "workflow",
    ),
    "technical-plan-review-result": (
        "technical-plan-review-result.schema.json",
        "TechnicalPlanReviewResult",
        "workflow",
    ),
    "code-review-request": (
        "code-review-request.schema.json",
        "CodeReviewRequest",
        "workflow",
    ),
    "code-review-result": (
        "code-review-result.schema.json",
        "CodeReviewResult",
        "workflow",
    ),
    "release-authorization": (
        "release-authorization.schema.json",
        "ReleaseAuthorization",
        "workflow",
    ),
    "release-result": ("release-result.schema.json", "ReleaseResult", "workflow"),
    "closure-record": ("closure-record.schema.json", "ClosureRecord", "workflow"),
    "claude-bootstrap-output": (
        "claude-bootstrap-output.schema.json",
        "ClaudeBootstrapOutput",
        "claude",
    ),
    "frontend-work-request": (
        "frontend-work-request.schema.json",
        "FrontendWorkRequest",
        "claude",
    ),
    "claude-frontend-output": (
        "claude-frontend-output.schema.json",
        "ClaudeFrontendOutput",
        "claude",
    ),
    "claude-plan-review-output": (
        "claude-plan-review-output.schema.json",
        "ClaudePlanReviewOutput",
        "claude",
    ),
    "claude-code-review-output": (
        "claude-code-review-output.schema.json",
        "ClaudeCodeReviewOutput",
        "claude",
    ),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_workflowctl(script_dir: Path) -> Any:
    path = script_dir / "workflowctl.py"
    spec = importlib.util.spec_from_file_location(
        "codex_claude_engineering_lifecycle_workflowctl", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_claudectl(script_dir: Path) -> Any:
    path = script_dir / "claudectl.py"
    spec = importlib.util.spec_from_file_location(
        "codex_claude_engineering_lifecycle_claudectl", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_runtime_payload(
    payload: Any,
    contract_key: str,
    workflowctl: Any,
    claudectl: Any,
) -> dict[str, Any]:
    _, runtime_name, owner = CONTRACTS[contract_key]
    runtime = workflowctl if owner == "workflow" else claudectl
    return cast(dict[str, Any], runtime.validate_contract_payload(payload, runtime_name))


def jsonschema_validators(
    schemas: dict[str, Any],
) -> dict[str, Callable[[Any], None]] | None:
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        return None
    validators: dict[str, Callable[[Any], None]] = {}
    for key, schema in schemas.items():
        validator_class = jsonschema.validators.validator_for(schema)
        validator_class.check_schema(schema)
        validator = validator_class(schema, format_checker=jsonschema.FormatChecker())
        validators[key] = validator.validate
    return validators


def fixture_contract(path: Path) -> str:
    matches = [key for key in CONTRACTS if path.name.startswith(f"{key}.")]
    if len(matches) != 1:
        raise ValueError(f"Fixture name must start with one contract key: {path.name}")
    return matches[0]


def capture_validation(callback: Callable[[], None]) -> tuple[bool, str | None]:
    try:
        callback()
    except Exception as exc:  # noqa: BLE001 - validators intentionally expose different exception types
        summary = str(exc).splitlines()[0][:500]
        return False, f"{type(exc).__name__}: {summary}"
    return True, None


def build_parser() -> argparse.ArgumentParser:
    plugin_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", type=Path, default=plugin_root / "schemas")
    parser.add_argument(
        "--fixtures", type=Path, default=plugin_root / "tests" / "fixtures"
    )
    parser.add_argument("--file", type=Path, help="Validate one named fixture")
    parser.add_argument(
        "--require-jsonschema",
        action="store_true",
        help="Fail instead of using runtime-only fallback when jsonschema is unavailable",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schemas = {
        key: load_json(args.schemas / schema_file)
        for key, (schema_file, _, _) in CONTRACTS.items()
    }
    workflowctl = load_workflowctl(Path(__file__).resolve().parent)
    claudectl = load_claudectl(Path(__file__).resolve().parent)
    schema_validators = jsonschema_validators(schemas)
    if args.require_jsonschema and schema_validators is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "jsonschema is required for this contract validation gate",
                    "schemaEngine": "unavailable",
                },
                sort_keys=True,
            )
        )
        return 2

    fixture_paths = [args.file] if args.file else sorted(args.fixtures.glob("*.json"))
    if not fixture_paths:
        print(json.dumps({"ok": False, "error": "No fixtures found"}, sort_keys=True))
        return 2

    results: list[dict[str, Any]] = []
    failures = 0
    for path in fixture_paths:
        schema_valid: bool | None
        schema_detail: str | None
        try:
            contract_key = fixture_contract(path)
            payload = load_json(path)
            expected_valid = ".invalid." not in path.name

            def validate_runtime(
                payload_value: Any = payload,
                key: str = contract_key,
            ) -> None:
                validate_runtime_payload(
                    payload_value,
                    key,
                    workflowctl,
                    claudectl,
                )

            runtime_valid, runtime_detail = capture_validation(validate_runtime)
            if schema_validators is None:
                schema_valid = None
                schema_detail = "jsonschema is unavailable; runtime fallback only"
            else:
                schema_validator = schema_validators[contract_key]

                def validate_schema(
                    payload_value: Any = payload,
                    validator: Callable[[Any], None] = schema_validator,
                ) -> None:
                    validator(payload_value)

                schema_valid, schema_detail = capture_validation(validate_schema)
            passed = runtime_valid == expected_valid and (
                schema_valid is None or schema_valid == expected_valid
            )
        except Exception as exc:  # noqa: BLE001 - report malformed fixture evidence uniformly
            contract_key = "unknown"
            expected_valid = ".invalid." not in path.name
            runtime_valid = False
            runtime_detail = f"{type(exc).__name__}: {str(exc).splitlines()[0][:500]}"
            schema_valid = None
            schema_detail = "fixture could not be routed"
            passed = False
        if not passed:
            failures += 1
        results.append(
            {
                "fixture": path.name,
                "contract": contract_key,
                "expectedValid": expected_valid,
                "runtimeValid": runtime_valid,
                "runtimeDetail": runtime_detail,
                "schemaValid": schema_valid,
                "schemaDetail": schema_detail,
                "passed": passed,
            }
        )

    output = {
        "ok": failures == 0,
        "schemaEngine": "jsonschema+runtime"
        if schema_validators
        else "runtime-fallback",
        "fixtures": len(results),
        "failures": failures,
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
