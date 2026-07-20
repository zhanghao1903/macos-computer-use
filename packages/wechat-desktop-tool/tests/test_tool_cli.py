from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    LocalServiceAppControl,
    Path,
    ToolCommand,
    ToolObservation,
    _app_control_for_args,
    argparse,
    cli_module,
    tempfile,
)


class WeChatDesktopCliServiceClientTests(unittest.TestCase):
    def test_app_control_args_use_helper_endpoint_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[computer_use]",
                        "timeout_ms = 2500",
                        "",
                        "[helper]",
                        'transport = "unix_socket"',
                        'endpoint = "/tmp/config.sock"',
                        'token = "config-token"',
                    ]
                ),
                encoding="utf-8",
            )

            client = _app_control_for_args(
                argparse.Namespace(
                    config=str(config_path),
                    dry_run=False,
                    socket_path=None,
                    token=None,
                    token_file=None,
                ),
                argparse.ArgumentParser(),
            )

        self.assertIsInstance(client, LocalServiceAppControl)
        self.assertEqual(str(client._socket_path), "/tmp/config.sock")
        self.assertEqual(client._token, "config-token")
        self.assertEqual(client._timeout, 2.5)

    def test_app_control_args_prefer_cli_socket_and_token_over_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app-control.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[computer_use]",
                        "timeout_ms = 2500",
                        "",
                        "[helper]",
                        'transport = "unix_socket"',
                        'endpoint = "/tmp/config.sock"',
                        'token = "config-token"',
                    ]
                ),
                encoding="utf-8",
            )

            client = _app_control_for_args(
                argparse.Namespace(
                    config=str(config_path),
                    dry_run=False,
                    socket_path="/tmp/cli.sock",
                    token="cli-token",
                    token_file=None,
                ),
                argparse.ArgumentParser(),
            )

        self.assertIsInstance(client, LocalServiceAppControl)
        self.assertEqual(str(client._socket_path), "/tmp/cli.sock")
        self.assertEqual(client._token, "cli-token")
        self.assertEqual(client._timeout, 2.5)

    def test_local_service_socket_timeout_covers_command_timeout(self) -> None:
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
            timeout_ms=30_000,
        )
        payload = {
            "schema": "app_control.service.request.v1",
            "action": "run",
            "command": command.to_dict(),
        }

        timeout = cli_module._socket_timeout_for_payload(payload, default=10.0)

        self.assertEqual(timeout, 35.0)

    def test_local_service_socket_timeout_does_not_shrink_config_timeout(self) -> None:
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
            timeout_ms=1_000,
        )
        payload = {
            "schema": "app_control.service.request.v1",
            "action": "run",
            "command": command.to_dict(),
        }

        timeout = cli_module._socket_timeout_for_payload(payload, default=10.0)

        self.assertEqual(timeout, 10.0)

    def test_local_service_client_validates_response_and_observation(self) -> None:
        client = LocalServiceAppControl("/tmp/app-control.sock")
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
        )
        observation = ToolObservation.ok(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
            summary="observed",
            observation={"frontmostApp": "WeChat"},
        )
        client._round_trip = lambda payload: {  # type: ignore[method-assign]
            "schema": "app_control.service.response.v1",
            "requestId": payload["requestId"],
            "status": "complete",
            "success": True,
            "observation": observation.to_dict(),
        }

        result = client.run_command(command)

        self.assertEqual(result.to_dict(), observation.to_dict())

    def test_local_service_client_rejects_invalid_service_response(self) -> None:
        client = LocalServiceAppControl("/tmp/app-control.sock")
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
        )
        client._round_trip = lambda payload: {  # type: ignore[method-assign]
            "schema": "app_control.service.response.v1",
            "success": True,
            "observation": {},
        }

        with self.assertRaisesRegex(RuntimeError, "invalid local service response"):
            client.run_command(command)

    def test_local_service_client_rejects_invalid_observation(self) -> None:
        client = LocalServiceAppControl("/tmp/app-control.sock")
        command = ToolCommand(
            command_id="cmd_cli",
            tool="macos.computer_use",
            operation="observe",
        )
        client._round_trip = lambda payload: {  # type: ignore[method-assign]
            "schema": "app_control.service.response.v1",
            "requestId": payload["requestId"],
            "status": "complete",
            "success": True,
            "observation": {"schema": "app_control.observation.v1"},
        }

        with self.assertRaisesRegex(RuntimeError, "invalid local service observation"):
            client.run_command(command)


if __name__ == "__main__":
    unittest.main()
