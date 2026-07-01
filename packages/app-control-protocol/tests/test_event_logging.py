from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import tempfile
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

    def test_text_logging_includes_observation_window_details(self) -> None:
        stream = StringIO()
        observer = LoggingToolObserver(
            config=LoggingConfig(json=False, redact_text=True),
            stream=stream,
        )

        observer.on_event(
            ToolEvent(
                command_id="cmd_observe",
                seq=1,
                event_type="observation",
                phase="observe",
                status="ok",
                summary="Frontmost app: WeChat.",
                data={
                    "observation": {
                        "schema": "app_control.observation.v1",
                        "commandId": "cmd_inner",
                        "tool": "macos.computer_use",
                        "operation": "observe",
                        "status": "ok",
                        "success": True,
                        "summary": "Frontmost app: WeChat.",
                        "observation": {
                            "frontmostApp": "WeChat",
                            "frontmostBundleId": "com.tencent.xinWeChat",
                            "windowTitle": "微信 (聊天)",
                            "accessibility": {
                                "available": False,
                                "failureKind": "accessibility_snapshot_timeout",
                            },
                            "textExtract": "secret visible text",
                        }
                    }
                },
            )
        )

        line = stream.getvalue().strip()
        self.assertIn("observation=", line)
        self.assertIn("rawObservation=", line)
        self.assertIn('"schema": "app_control.observation.v1"', line)
        self.assertIn('"tool": "macos.computer_use"', line)
        self.assertIn('"frontmostApp": "WeChat"', line)
        self.assertIn('"windowTitle": "微信 (聊天)"', line)
        self.assertIn('"accessibility"', line)
        self.assertIn('"textExtract": "[redacted]"', line)
        self.assertNotIn("secret visible text", line)

    def test_raw_data_log_file_receives_unredacted_observation_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_log_path = Path(tmpdir) / "app-control-rawdata.jsonl"
            stream = StringIO()
            observer = LoggingToolObserver(
                config=LoggingConfig(
                    json=False,
                    redact_text=True,
                    raw_data_log_path=str(raw_log_path),
                ),
                stream=stream,
            )

            observer.on_event(
                ToolEvent(
                    command_id="cmd_raw",
                    seq=1,
                    event_type="observation",
                    phase="observe",
                    status="ok",
                    summary="Frontmost app: WeChat.",
                    data={
                        "observation": {
                            "schema": "app_control.observation.v1",
                            "commandId": "cmd_raw",
                            "tool": "macos.computer_use",
                            "operation": "observe",
                            "status": "ok",
                            "success": True,
                            "summary": "Frontmost app: WeChat.",
                            "observation": {
                                "frontmostApp": "WeChat",
                                "textExtract": "raw visible text",
                            },
                        }
                    },
                )
            )

            terminal_line = stream.getvalue()
            raw_record = json.loads(raw_log_path.read_text(encoding="utf-8"))

        self.assertIn('"textExtract": "[redacted]"', terminal_line)
        self.assertEqual(raw_record["commandId"], "cmd_raw")
        self.assertEqual(raw_record["phase"], "observe")
        self.assertEqual(
            raw_record["rawObservation"]["observation"]["textExtract"],
            "raw visible text",
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
