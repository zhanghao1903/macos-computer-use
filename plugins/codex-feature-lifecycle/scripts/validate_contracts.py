#!/usr/bin/env python3
"""Validate workflow JSON Schemas and positive/negative payload fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_workflowctl(script_dir: Path) -> Any:
    path = script_dir / "workflowctl.py"
    spec = importlib.util.spec_from_file_location("codex_feature_lifecycle_workflowctl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jsonschema_validators(schemas: dict[str, Any]) -> dict[str, Callable[[Any], None]] | None:
    try:
        import jsonschema
    except ImportError:
        return None
    validators: dict[str, Callable[[Any], None]] = {}
    for message_type, schema in schemas.items():
        validator_class = jsonschema.validators.validator_for(schema)
        validator_class.check_schema(schema)
        validator = validator_class(schema, format_checker=jsonschema.FormatChecker())
        validators[message_type] = validator.validate
    return validators


def validate_runtime(payload: Any, *, workflowctl: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object")
    message_type = payload.get("messageType")
    if message_type == "ReviewRequest":
        workflowctl.validate_review_request(payload)
    elif message_type == "ReviewResult":
        workflowctl.validate_review_result(payload)
    else:
        raise ValueError("Unsupported or missing messageType")


def validate_schema(payload: Any, *, schema_validators: dict[str, Callable[[Any], None]]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object")
    message_type = payload.get("messageType")
    if message_type not in schema_validators:
        raise ValueError("Unsupported or missing messageType")
    schema_validators[message_type](payload)


def capture_validation(callback: Callable[[], None]) -> tuple[bool, str | None]:
    try:
        callback()
    except Exception as exc:  # fixture reports must retain validator-specific evidence
        summary = str(exc).splitlines()[0][:500]
        return False, f"{type(exc).__name__}: {summary}"
    return True, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request_schema_path = args.schemas / "review-request.schema.json"
    result_schema_path = args.schemas / "review-result.schema.json"
    schemas = {
        "ReviewRequest": load_json(request_schema_path),
        "ReviewResult": load_json(result_schema_path),
    }
    workflowctl = load_workflowctl(Path(__file__).resolve().parent)
    schema_validators = jsonschema_validators(schemas)

    fixture_paths = sorted(args.fixtures.glob("*.json"))
    if not fixture_paths:
        print(json.dumps({"ok": False, "error": "No fixtures found"}))
        return 2

    results: list[dict[str, Any]] = []
    failures = 0
    for path in fixture_paths:
        expected_valid = ".invalid." not in path.name
        payload = load_json(path)
        runtime_valid, runtime_detail = capture_validation(
            lambda: validate_runtime(payload, workflowctl=workflowctl)
        )
        if schema_validators is None:
            schema_valid = None
            schema_detail = "jsonschema is unavailable; runtime fallback only"
        else:
            schema_valid, schema_detail = capture_validation(
                lambda: validate_schema(payload, schema_validators=schema_validators)
            )
        actual_valid = runtime_valid and schema_valid is not False
        passed = runtime_valid == expected_valid and (
            schema_valid is None or schema_valid == expected_valid
        )
        if not passed:
            failures += 1
        results.append(
            {
                "fixture": path.name,
                "expectedValid": expected_valid,
                "actualValid": actual_valid,
                "passed": passed,
                "runtimeValid": runtime_valid,
                "runtimeDetail": runtime_detail,
                "schemaValid": schema_valid,
                "schemaDetail": schema_detail,
            }
        )

    output = {
        "ok": failures == 0,
        "schemaEngine": "jsonschema+runtime" if schema_validators is not None else "runtime-fallback",
        "fixtures": len(results),
        "failures": failures,
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
