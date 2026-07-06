from __future__ import annotations

import unittest

from app_control_protocol import (
    COMMAND_SCHEMA,
    EVENT_SCHEMA,
    OBSERVATION_SCHEMA,
    SERVICE_EVENT_SCHEMA,
    SERVICE_REQUEST_SCHEMA,
    SERVICE_RESPONSE_SCHEMA,
    AppControlClient,
    ServiceAction,
    ServiceEventEnvelope,
    ServiceRequest,
    ServiceResponse,
    ServiceResponseStatus,
    StreamingAppControlClient,
    ToolCommand,
    ToolError,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolObserver,
    ToolStatus,
    validate_protocol_payload,
)


class ToolCommandTests(unittest.TestCase):
    def test_command_round_trips_camel_case_payload(self) -> None:
        command = ToolCommand(
            command_id="cmd_1",
            tool="macos.computer_use",
            operation="open_app",
            input={"app": "TextEdit"},
            timeout_ms=10_000,
            idempotency_key="client-key",
            metadata={"caller": "unit-test"},
        )

        payload = command.to_dict()
        restored = ToolCommand.from_dict(payload)

        self.assertEqual(payload["schema"], COMMAND_SCHEMA)
        self.assertEqual(payload["commandId"], "cmd_1")
        self.assertEqual(payload["timeoutMs"], 10_000)
        self.assertEqual(restored, command)

    def test_command_rejects_empty_command_id(self) -> None:
        with self.assertRaises(ValueError):
            ToolCommand(
                command_id="",
                tool="macos.computer_use",
                operation="open_app",
            )

    def test_command_from_dict_rejects_zero_timeout(self) -> None:
        with self.assertRaises(ValueError):
            ToolCommand.from_dict(
                {
                    "commandId": "cmd_1",
                    "tool": "macos.computer_use",
                    "operation": "open_app",
                    "timeoutMs": 0,
                }
            )


class ToolObservationTests(unittest.TestCase):
    def test_planned_status_values_are_stable(self) -> None:
        self.assertEqual(
            {status.value for status in ToolStatus},
            {
                "ok",
                "not_found",
                "not_ready",
                "permission_missing",
                "timeout",
                "failed",
                "unknown",
            },
        )

    def test_ok_observation_round_trips(self) -> None:
        observation = ToolObservation.ok(
            command_id="cmd_1",
            tool="macos.computer_use",
            operation="open_app",
            summary="Opened app.",
            observation={"app": "TextEdit"},
            timing={"durationMs": 12},
        )

        payload = observation.to_dict()
        restored = ToolObservation.from_dict(payload)

        self.assertEqual(payload["schema"], OBSERVATION_SCHEMA)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["success"])
        self.assertEqual(restored, observation)

    def test_failure_observation_round_trips_classified_statuses(self) -> None:
        for status in (ToolStatus.NOT_FOUND, ToolStatus.TIMEOUT):
            with self.subTest(status=status.value):
                observation = ToolObservation.failure(
                    command_id=f"cmd_{status.value}",
                    tool="wechat.desktop",
                    operation="focus_contact",
                    status=status,
                    error=ToolError(
                        failure_kind=status.value,
                        message=f"{status.value} failure.",
                        retryable=True,
                    ),
                )

                payload = observation.to_dict()
                restored = ToolObservation.from_dict(payload)

                self.assertEqual(payload["status"], status.value)
                self.assertFalse(payload["success"])
                self.assertEqual(restored, observation)


    def test_failure_observation_embeds_tool_error(self) -> None:
        error = ToolError(
            failure_kind="app_not_allowed",
            message="App is not allowlisted.",
            recovery_hint="Add the app to allowed_apps.",
            retryable=False,
            phase="policy",
            operation="open_app",
            evidence={"app": "Messages"},
        )

        observation = ToolObservation.failure(
            command_id="cmd_2",
            tool="macos.computer_use",
            operation="open_app",
            status=ToolStatus.FAILED,
            error=error,
        )

        payload = observation.to_dict()
        restored = ToolObservation.from_dict(payload)

        self.assertFalse(payload["success"])
        self.assertEqual(payload["failureKind"], "app_not_allowed")
        self.assertEqual(payload["recoveryHint"], "Add the app to allowed_apps.")
        self.assertEqual(payload["evidence"], {"app": "Messages"})
        self.assertEqual(
            payload["error"],
            {
                "failureKind": "app_not_allowed",
                "message": "App is not allowlisted.",
                "recoveryHint": "Add the app to allowed_apps.",
                "retryable": False,
                "phase": "policy",
                "operation": "open_app",
                "evidence": {"app": "Messages"},
            },
        )
        validate_protocol_payload("observation", payload)
        self.assertEqual(restored, observation)

    def test_observation_rejects_conflicting_nested_error(self) -> None:
        with self.assertRaises(ValueError):
            ToolObservation(
                command_id="cmd_2",
                tool="macos.computer_use",
                operation="open_app",
                status=ToolStatus.FAILED,
                success=False,
                summary="App is not allowlisted.",
                failure_kind="different_failure",
                error=ToolError(
                    failure_kind="app_not_allowed",
                    message="App is not allowlisted.",
                    retryable=False,
                ),
            )

    def test_observation_rejects_success_status_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            ToolObservation(
                command_id="cmd_3",
                tool="macos.computer_use",
                operation="open_app",
                status=ToolStatus.UNKNOWN,
                success=True,
                summary="Unknown result.",
            )

    def test_observation_from_dict_rejects_string_success(self) -> None:
        with self.assertRaises(TypeError):
            ToolObservation.from_dict(
                {
                    "commandId": "cmd_3",
                    "tool": "macos.computer_use",
                    "operation": "open_app",
                    "status": "failed",
                    "success": "false",
                    "summary": "Failed.",
                }
            )


class ToolEventTests(unittest.TestCase):
    def test_event_round_trips_type_and_status(self) -> None:
        event = ToolEvent(
            command_id="cmd_1",
            seq=1,
            event_type=ToolEventType.PROGRESS,
            phase="open_app",
            status=ToolStatus.OK,
            summary="Launch requested.",
            data={"app": "TextEdit"},
        )

        payload = event.to_dict()
        restored = ToolEvent.from_dict(payload)

        self.assertEqual(payload["schema"], EVENT_SCHEMA)
        self.assertEqual(payload["type"], "progress")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(restored, event)

    def test_event_rejects_negative_sequence(self) -> None:
        with self.assertRaises(ValueError):
            ToolEvent(
                command_id="cmd_1",
                seq=-1,
                event_type="progress",
            )

    def test_observer_protocol_is_exported(self) -> None:
        class Observer:
            def __init__(self) -> None:
                self.events: list[ToolEvent] = []

            def on_event(self, event: ToolEvent) -> None:
                self.events.append(event)

        observer: ToolObserver = Observer()
        event = ToolEvent(command_id="cmd_1", seq=0, event_type="started")

        observer.on_event(event)

        self.assertEqual(observer.events, [event])
        self.assertIsInstance(observer, ToolObserver)


class ServiceEnvelopeTests(unittest.TestCase):
    def test_service_request_run_round_trips(self) -> None:
        command = ToolCommand(
            command_id="cmd_1",
            tool="macos.computer_use",
            operation="readiness",
        )
        request = ServiceRequest.run(command, token="local-token")

        payload = request.to_dict()
        restored = ServiceRequest.from_dict(payload)

        self.assertEqual(payload["schema"], SERVICE_REQUEST_SCHEMA)
        self.assertEqual(payload["action"], ServiceAction.RUN.value)
        validate_protocol_payload("service_request", payload)
        self.assertEqual(restored, request)

    def test_service_request_poll_requires_request_id(self) -> None:
        request = ServiceRequest.poll("req_1")

        payload = request.to_dict()

        self.assertEqual(payload["action"], "poll")
        self.assertEqual(payload["requestId"], "req_1")
        validate_protocol_payload("service_request", payload)
        with self.assertRaises(ValueError):
            ServiceRequest(action="poll")

    def test_service_response_complete_round_trips(self) -> None:
        observation = ToolObservation.ok(
            command_id="cmd_1",
            tool="macos.computer_use",
            operation="readiness",
            summary="ready",
        )
        response = ServiceResponse.complete(observation, request_id="req_1")

        payload = response.to_dict()
        restored = ServiceResponse.from_dict(payload)

        self.assertEqual(payload["schema"], SERVICE_RESPONSE_SCHEMA)
        self.assertEqual(payload["status"], ServiceResponseStatus.COMPLETE.value)
        self.assertTrue(payload["success"])
        validate_protocol_payload("service_response", payload)
        self.assertEqual(restored.to_dict(), payload)

    def test_service_response_failed_accepts_full_tool_error(self) -> None:
        error = ToolError(
            failure_kind="permission_missing",
            message="Accessibility permission is missing.",
            recovery_hint="Grant Accessibility permission.",
            retryable=True,
            phase="readiness",
            operation="readiness",
            evidence={"permission": "accessibility"},
        )
        response = ServiceResponse.failed(error, request_id="req_1")

        payload = response.to_dict()
        restored = ServiceResponse.from_dict(payload)

        self.assertEqual(payload["status"], "failed")
        self.assertFalse(payload["success"])
        validate_protocol_payload("service_response", payload)
        self.assertEqual(restored.error, error)

    def test_service_response_rejects_success_status_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            ServiceResponse(status="complete", success=False)
        with self.assertRaises(ValueError):
            ServiceResponse(status="not_found", success=True)

    def test_service_response_failed_requires_error(self) -> None:
        with self.assertRaises(ValueError):
            ServiceResponse(status="failed", success=False)

    def test_service_event_envelope_round_trips(self) -> None:
        event = ToolEvent(
            command_id="cmd_1",
            seq=1,
            event_type=ToolEventType.PROGRESS,
            summary="working",
        )
        envelope = ServiceEventEnvelope(request_id="req_1", event=event)

        payload = envelope.to_dict()
        restored = ServiceEventEnvelope.from_dict(payload)

        self.assertEqual(payload["schema"], SERVICE_EVENT_SCHEMA)
        self.assertEqual(payload["status"], "event")
        self.assertTrue(payload["success"])
        validate_protocol_payload("service_event", payload)
        self.assertEqual(restored, envelope)


class ClientProtocolTests(unittest.TestCase):
    def test_app_control_client_protocol_is_exported(self) -> None:
        class Client:
            def run_command(
                self,
                command: ToolCommand,
                *,
                observer: ToolObserver | None = None,
            ) -> ToolObservation:
                del observer
                return ToolObservation.ok(
                    command_id=command.command_id,
                    tool=command.tool,
                    operation=command.operation,
                    summary="ok",
                )

        client: AppControlClient = Client()
        command = ToolCommand(
            command_id="cmd_1",
            tool="macos.computer_use",
            operation="readiness",
        )

        observation = client.run_command(command)

        self.assertTrue(observation.success)
        self.assertEqual(observation.command_id, "cmd_1")
        self.assertIsInstance(client, AppControlClient)
        self.assertNotIsInstance(object(), AppControlClient)

    def test_streaming_client_protocol_is_exported(self) -> None:
        class Client:
            def run_command(
                self,
                command: ToolCommand,
                *,
                observer: ToolObserver | None = None,
            ) -> ToolObservation:
                del observer
                return ToolObservation.ok(
                    command_id=command.command_id,
                    tool=command.tool,
                    operation=command.operation,
                    summary="ok",
                )

            def run_stream(
                self,
                command: ToolCommand,
                *,
                observer: ToolObserver | None = None,
            ) -> list[ToolEvent]:
                del observer
                return [
                    ToolEvent(
                        command_id=command.command_id,
                        seq=0,
                        event_type=ToolEventType.STARTED,
                    )
                ]

        client: StreamingAppControlClient = Client()
        command = ToolCommand(
            command_id="cmd_2",
            tool="macos.computer_use",
            operation="readiness",
        )

        events = list(client.run_stream(command))

        self.assertEqual(events[0].command_id, "cmd_2")
        self.assertIsInstance(client, StreamingAppControlClient)
        self.assertIsInstance(client, AppControlClient)


if __name__ == "__main__":
    unittest.main()
