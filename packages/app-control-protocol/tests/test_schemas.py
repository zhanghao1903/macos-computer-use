from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest

from app_control_protocol import (
    COMMAND_SCHEMA,
    EVENT_SCHEMA,
    HELPER_REQUEST_SCHEMA,
    HELPER_RESPONSE_SCHEMA,
    OBSERVATION_SCHEMA,
    SERVICE_EVENT_SCHEMA,
    SERVICE_REQUEST_SCHEMA,
    SERVICE_RESPONSE_SCHEMA,
    PROTOCOL_SCHEMA_FILES,
    ProtocolValidationError,
    ToolEventType,
    ToolStatus,
    load_protocol_schema,
    load_protocol_schemas,
    protocol_schema_names,
    validate_protocol_payload,
)


ROOT = Path(__file__).resolve().parents[1]


class ProtocolSchemaTests(unittest.TestCase):
    def test_schema_assets_are_packaged_and_loadable(self) -> None:
        self.assertEqual(
            set(protocol_schema_names()),
            {
                "command",
                "observation",
                "event",
                "error",
                "service_request",
                "service_response",
                "service_event",
                "helper_request",
                "helper_response",
            },
        )

        schemas = load_protocol_schemas()

        self.assertEqual(set(schemas), set(protocol_schema_names()))
        for name, filename in PROTOCOL_SCHEMA_FILES.items():
            with self.subTest(name=name):
                path = ROOT / "src" / "app_control_protocol" / "schemas" / filename
                self.assertTrue(path.exists())
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8")),
                    schemas[name],
                )
                self.assertEqual(schemas[name]["$schema"], _JSON_SCHEMA_DRAFT)

    def test_schema_documents_match_protocol_constants(self) -> None:
        command = load_protocol_schema("command")
        observation = load_protocol_schema("observation")
        event = load_protocol_schema("event")

        self.assertEqual(command["properties"]["schema"]["const"], COMMAND_SCHEMA)
        self.assertEqual(
            observation["properties"]["schema"]["const"],
            OBSERVATION_SCHEMA,
        )
        self.assertEqual(event["properties"]["schema"]["const"], EVENT_SCHEMA)
        self.assertEqual(
            set(observation["properties"]["status"]["enum"]),
            {status.value for status in ToolStatus},
        )
        self.assertEqual(
            set(event["properties"]["type"]["enum"]),
            {event_type.value for event_type in ToolEventType},
        )

    def test_service_schema_documents_match_wire_constants(self) -> None:
        service_request = load_protocol_schema("service_request")
        service_response = load_protocol_schema("service_response")
        service_event = load_protocol_schema("service_event")
        helper_request = load_protocol_schema("helper_request")
        helper_response = load_protocol_schema("helper_response")

        self.assertEqual(
            service_request["properties"]["schema"]["const"],
            SERVICE_REQUEST_SCHEMA,
        )
        self.assertEqual(
            service_response["properties"]["schema"]["const"],
            SERVICE_RESPONSE_SCHEMA,
        )
        self.assertEqual(
            service_event["properties"]["schema"]["const"],
            SERVICE_EVENT_SCHEMA,
        )
        self.assertEqual(
            helper_request["properties"]["schema"]["const"],
            HELPER_REQUEST_SCHEMA,
        )
        self.assertEqual(
            helper_response["properties"]["schema"]["const"],
            HELPER_RESPONSE_SCHEMA,
        )
        self.assertEqual(
            service_request["properties"]["action"]["enum"],
            ["run", "submit", "poll", "stream"],
        )
        self.assertEqual(
            service_response["properties"]["status"]["enum"],
            ["complete", "not_found", "failed"],
        )

    def test_schema_required_fields_match_public_envelopes(self) -> None:
        command = load_protocol_schema("command")
        observation = load_protocol_schema("observation")
        event = load_protocol_schema("event")
        error = load_protocol_schema("error")
        service_request = load_protocol_schema("service_request")
        service_response = load_protocol_schema("service_response")
        service_event = load_protocol_schema("service_event")
        helper_request = load_protocol_schema("helper_request")
        helper_response = load_protocol_schema("helper_response")

        self.assertEqual(
            command["required"],
            ["schema", "commandId", "tool", "operation", "input"],
        )
        self.assertEqual(
            observation["required"],
            [
                "schema",
                "commandId",
                "tool",
                "operation",
                "status",
                "success",
                "summary",
                "observation",
            ],
        )
        self.assertEqual(event["required"], ["schema", "commandId", "seq", "type"])
        self.assertEqual(error["required"], ["failureKind", "message", "retryable"])
        self.assertEqual(service_request["required"], ["schema", "action"])
        self.assertEqual(service_response["required"], ["schema", "status", "success"])
        self.assertEqual(
            service_event["required"],
            ["schema", "requestId", "status", "success", "event"],
        )
        self.assertEqual(helper_request["required"], ["schema", "command"])
        self.assertEqual(helper_response["required"], ["schema", "success"])

    def test_project_metadata_includes_schema_package_data(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())

        package_data = project["tool"]["setuptools"]["package-data"]

        self.assertIn("schemas/*.schema.json", package_data["app_control_protocol"])

    def test_unknown_schema_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_protocol_schema("missing")  # type: ignore[arg-type]

    def test_validate_protocol_payload_accepts_valid_command(self) -> None:
        payload = {
            "schema": COMMAND_SCHEMA,
            "commandId": "cmd_1",
            "tool": "macos.computer_use",
            "operation": "click",
            "input": {
                "selector": {"role": "button", "name": "OK"},
                "targetApp": "TextEdit",
            },
            "timeoutMs": 1000,
            "metadata": {"caller": "unit-test"},
        }

        validated = validate_protocol_payload("command", payload)

        self.assertEqual(validated, payload)

    def test_validate_protocol_payload_rejects_missing_required_field(self) -> None:
        with self.assertRaisesRegex(ProtocolValidationError, "commandId"):
            validate_protocol_payload(
                "command",
                {
                    "schema": COMMAND_SCHEMA,
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                    "input": {},
                },
            )

    def test_validate_protocol_payload_rejects_unknown_field(self) -> None:
        with self.assertRaisesRegex(ProtocolValidationError, "not allowed"):
            validate_protocol_payload(
                "command",
                {
                    "schema": COMMAND_SCHEMA,
                    "commandId": "cmd_1",
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                    "input": {},
                    "extra": True,
                },
            )

    def test_validate_protocol_payload_enforces_observation_success_status(self) -> None:
        validate_protocol_payload(
            "observation",
            {
                "schema": OBSERVATION_SCHEMA,
                "commandId": "cmd_1",
                "tool": "macos.computer_use",
                "operation": "readiness",
                "status": "ok",
                "success": True,
                "summary": "ready",
                "observation": {},
            },
        )

        with self.assertRaisesRegex(ProtocolValidationError, "success"):
            validate_protocol_payload(
                "observation",
                {
                    "schema": OBSERVATION_SCHEMA,
                    "commandId": "cmd_1",
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                    "status": "ok",
                    "success": False,
                    "summary": "ready",
                    "observation": {},
                },
            )

    def test_validate_protocol_payload_accepts_observation_nested_error(self) -> None:
        validate_protocol_payload(
            "observation",
            {
                "schema": OBSERVATION_SCHEMA,
                "commandId": "cmd_1",
                "tool": "macos.computer_use",
                "operation": "open_app",
                "status": "failed",
                "success": False,
                "summary": "App is not allowlisted.",
                "failureKind": "app_not_allowed",
                "message": "App is not allowlisted.",
                "recoveryHint": "Add the app to allowed_apps.",
                "retryable": False,
                "observation": {},
                "evidence": {"app": "Messages"},
                "error": {
                    "failureKind": "app_not_allowed",
                    "message": "App is not allowlisted.",
                    "recoveryHint": "Add the app to allowed_apps.",
                    "retryable": False,
                    "phase": "policy",
                    "operation": "open_app",
                    "evidence": {"app": "Messages"},
                },
            },
        )

    def test_validate_protocol_payload_enforces_service_request_conditions(
        self,
    ) -> None:
        validate_protocol_payload(
            "service_request",
            {
                "schema": "app_control.service.request.v1",
                "action": "poll",
                "requestId": "req_1",
            },
        )

        with self.assertRaisesRegex(ProtocolValidationError, "command"):
            validate_protocol_payload(
                "service_request",
                {
                    "schema": "app_control.service.request.v1",
                    "action": "run",
                },
            )

    def test_validate_protocol_payload_enforces_service_response_error(self) -> None:
        validate_protocol_payload(
            "service_response",
            {
                "schema": "app_control.service.response.v1",
                "status": "failed",
                "success": False,
                "error": {
                    "failureKind": "not_ready",
                    "message": "not ready",
                    "recoveryHint": "Try again.",
                    "retryable": True,
                    "phase": "readiness",
                    "operation": "readiness",
                    "evidence": {"permission": "accessibility"},
                },
            },
        )

        with self.assertRaisesRegex(ProtocolValidationError, "error"):
            validate_protocol_payload(
                "service_response",
                {
                    "schema": "app_control.service.response.v1",
                    "status": "failed",
                    "success": False,
                },
            )

    def test_validate_protocol_payload_enforces_helper_request(self) -> None:
        validate_protocol_payload(
            "helper_request",
            {
                "schema": HELPER_REQUEST_SCHEMA,
                "token": "local-token",
                "command": {
                    "schema": COMMAND_SCHEMA,
                    "commandId": "cmd_1",
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                    "input": {},
                },
                "metadata": {"bundleId": "com.example.helper"},
            },
        )

        with self.assertRaisesRegex(ProtocolValidationError, "command"):
            validate_protocol_payload(
                "helper_request",
                {
                    "schema": HELPER_REQUEST_SCHEMA,
                    "token": "local-token",
                },
            )

    def test_validate_protocol_payload_enforces_helper_response(self) -> None:
        validate_protocol_payload(
            "helper_response",
            {
                "schema": HELPER_RESPONSE_SCHEMA,
                "success": True,
                "observation": {
                    "schema": OBSERVATION_SCHEMA,
                    "commandId": "cmd_1",
                    "tool": "macos.computer_use",
                    "operation": "readiness",
                    "status": "ok",
                    "success": True,
                    "summary": "ready",
                    "observation": {},
                },
            },
        )

        with self.assertRaisesRegex(ProtocolValidationError, "observation"):
            validate_protocol_payload(
                "helper_response",
                {
                    "schema": HELPER_RESPONSE_SCHEMA,
                    "success": True,
                },
            )


_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


if __name__ == "__main__":
    unittest.main()
