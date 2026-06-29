from __future__ import annotations

from io import StringIO
import json
import unittest

from app_control_protocol import (
    AppControlConfig,
    LoggingConfig,
    LoggingToolObserver,
    ToolEvent,
    build_logging_observer,
)


class EventLoggingTests(unittest.TestCase):
    def test_json_logging_redacts_sensitive_payload(self) -> None:
        stream = StringIO()
        observer = LoggingToolObserver(
            config=LoggingConfig(json=True, redact_text=True),
            stream=stream,
        )
        event = ToolEvent(
            command_id="cmd_1",
            seq=1,
            event_type="observation",
            data={
                "messageText": "hello",
                "safe": "visible",
                "nested": {"textExtract": "secret text"},
            },
        )

        observer.on_event(event)

        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["data"]["messageText"], "[redacted]")
        self.assertEqual(payload["data"]["safe"], "visible")
        self.assertEqual(payload["data"]["nested"]["textExtract"], "[redacted]")

    def test_text_logging_writes_compact_line(self) -> None:
        stream = StringIO()
        observer = LoggingToolObserver(
            config=LoggingConfig(json=False, redact_text=True),
            stream=stream,
        )

        observer.on_event(
            ToolEvent(
                command_id="cmd_2",
                seq=0,
                event_type="started",
                phase="open_app",
                summary="Started.",
            )
        )

        self.assertEqual(
            stream.getvalue().strip(),
            "started | cmd_2 | open_app | Started.",
        )

    def test_build_logging_observer_accepts_app_config(self) -> None:
        stream = StringIO()
        observer = build_logging_observer(
            AppControlConfig.from_dict(
                {
                    "logging": {
                        "json": True,
                        "event_sink": "stdout",
                    }
                }
            ),
            stream=stream,
        )

        observer.on_event(ToolEvent(command_id="cmd_3", seq=0, event_type="started"))

        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["commandId"], "cmd_3")

    def test_build_logging_observer_rejects_unknown_sink(self) -> None:
        with self.assertRaises(ValueError):
            build_logging_observer(
                LoggingConfig(event_sink="file"),
            )


if __name__ == "__main__":
    unittest.main()
