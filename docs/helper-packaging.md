# Helper App Lifecycle

macOS grants Accessibility, Automation, and Screen Recording permissions to the
process that performs GUI control. A Python package is not a stable permission
subject, so production callers should run desktop control through their own
signed helper app.

This repository now provides the first helper lifecycle layer:

- helper template initialization;
- helper app skeleton build;
- helper endpoint manifest parsing;
- JSON-lines unix socket transport client;
- manifest discovery through explicit path or environment variables;
- helper app launch wrapper;
- helper setup doctor report;
- `computer-use-macos doctor` CLI.

## Initialize

```bash
computer-use-macos helper init ./computer-use-helper \
  --name "Example Computer Use Helper" \
  --bundle-id com.example.computer-use-helper \
  --team-id ABCDE12345
```

Generated files:

```text
computer-use-helper/
  README.md
  Info.plist.template
  entitlements.plist
  helper_config.json
  build.py
  build.sh
  sign.sh
  notarize.sh
  src/helper_main.py
```

The generated `src/helper_main.py` is a minimal JSON-lines unix socket server.
It reads `helper_config.json`, creates the token file if `tokenRef` is present,
restricts the token file to `0600`, listens on `socketPath`, restricts the
socket path to `0600`, supports `readiness`, `wait`, allowlisted `open_app`,
`focus_app`, `observe`, `click`, `type_text`, `press_key`, and `hotkey`, and
returns structured failures for unsupported operations. Keep
`metadata.allowedApps` and `metadata.allowedAppBundleIds` narrow; empty
allowlists mean app-targeted operations are refused by default. If an operation
provides `bundleId`, the helper verifies it against the configured mapping
before executing. Coordinate click is refused unless
`metadata.allowCoordinateClick` is set to `true`. Desktop observation, click,
and keyboard operations still require the signed helper app to have the
relevant macOS Accessibility/Automation permissions.
The generated `Info.plist.template` includes an Apple Events usage description;
Accessibility permission is still granted by users to the final signed helper
app in System Settings.

Build the development skeleton:

```bash
computer-use-macos helper build ./computer-use-helper
```

Sign and notarize the release helper with your own Apple Developer account:

```bash
cd ./computer-use-helper
./build.sh
./sign.sh "build/computer-use-helper.app" \
  "Developer ID Application: Example Corp (ABCDE12345)"
APPLE_ID=dev@example.com \
  APP_PASSWORD=app-specific-password \
  TEAM_ID=ABCDE12345 \
  ./notarize.sh "build/computer-use-helper.app"
```

`sign.sh` runs hardened runtime `codesign` with `entitlements.plist` and then
verifies the signature. It accepts either `./sign.sh <identity>` for the default
`build/<template-directory>.app` path or `./sign.sh <Helper.app> <identity>` for
an explicit app path. `notarize.sh` creates a zip, submits it with `xcrun
notarytool`, staples the ticket, and runs Gatekeeper assessment. The developer
owns the identity, credentials, and final distribution channel.

## Manifest

Example helper manifest:

```json
{
  "bundleId": "com.example.computer-use-helper",
  "apiVersion": "app_control.helper.v1",
  "transport": "unix_socket",
  "socketPath": "/tmp/example-computer-use-helper.sock",
  "tokenRef": "/tmp/example-computer-use-helper.token",
  "metadata": {
    "allowedApps": ["TextEdit"],
    "allowedAppBundleIds": {
      "TextEdit": "com.apple.TextEdit"
    }
  }
}
```

Supported discovery environment variables:

- `APP_CONTROL_HELPER_MANIFEST`
- `MACOS_COMPUTER_USE_HELPER_MANIFEST`
- `COMPUTER_USE_MACOS_HELPER_MANIFEST`

When using `ComputerUseClient.from_config(...)`, helper runtime values can also
be supplied through `APP_CONTROL_HELPER_APP_PATH`,
`APP_CONTROL_HELPER_BUNDLE_ID`, `APP_CONTROL_HELPER_ENDPOINT`,
`APP_CONTROL_HELPER_TOKEN`, and `APP_CONTROL_HELPER_ALLOWED_APPS`. If
`computer_use.allowed_app_bundle_ids` is configured, the SDK passes it to helper
manifests as `metadata.allowedAppBundleIds`.

## Doctor

```bash
computer-use-macos helper doctor ./computer-use-helper
```

The positional target may be a helper template directory, a manifest JSON file,
or a built `.app` bundle. Explicit `--manifest` and `--helper-app` values take
precedence when both are provided.

JSON output:

```bash
computer-use-macos helper doctor ./computer-use-helper --json
```

The doctor verifies the manifest can be read, helper identity matches expected
values, endpoint/socket metadata exists, token metadata is usable, and an
optional helper app path exists. With `--auto-launch`, it requests launch via
macOS `open`.

Release verification is opt-in because it calls macOS developer tooling:

```bash
computer-use-macos helper doctor \
  --manifest ./helper.json \
  --helper-app "/Applications/Example Computer Use Helper.app" \
  --expected-bundle-id com.example.computer-use-helper \
  --verify-signature \
  --verify-notarization \
  --json
```

`--verify-signature` runs `codesign --verify --deep --strict --verbose=2`.
`--verify-notarization` runs
`spctl --assess --type execute --verbose=4`. Both checks are included in the
JSON report so release automation can archive the evidence before setting the
external proof flags.

## Transport

The SDK can connect to a helper that publishes a `unix_socket` manifest. The
transport sends one JSON object per command and expects one JSON object response
terminated by a newline:

```json
{
  "schema": "app_control.helper.request.v1",
  "token": "optional-local-token",
  "metadata": {
    "bundleId": "com.example.computer-use-helper",
    "apiVersion": "app_control.helper.v1"
  },
  "command": {
    "schema": "app_control.command.v1",
    "commandId": "cmd_1",
    "tool": "macos.computer_use",
    "operation": "readiness",
    "input": {}
  }
}
```

The preferred response is a helper response envelope. The transport validates
this envelope against `app_control.helper.response.v1` and extracts the nested
`ToolObservation`:

```json
{
  "schema": "app_control.helper.response.v1",
  "success": true,
  "observation": {
    "schema": "app_control.observation.v1",
    "commandId": "cmd_1",
    "tool": "macos.computer_use",
    "operation": "readiness",
    "status": "ok",
    "success": true,
    "summary": "ready",
    "observation": {}
  }
}
```

For older helper builds, the SDK still accepts either a raw `ToolObservation`
payload or an object with only an `observation` field.

Python callers can use the manifest directly:

```python
from app_control_protocol import ToolCommand
from computer_use_macos.helper import (
    helper_transport_from_manifest,
    load_helper_manifest,
)

manifest = load_helper_manifest("./helper_config.json")
helper = helper_transport_from_manifest(manifest)
result = helper.run_command(
    ToolCommand(
        command_id="cmd_1",
        tool="macos.computer_use",
        operation="readiness",
    )
)
```

The helper transport also exposes `run_stream(command)`, the same
protocol-first convenience methods as the direct backend (`readiness`,
`open_app`, `observe`, `type_text`, `press_key`, `hotkey`, `click`, and
`wait`), and accepts the same observer callback shape. Helper convenience
methods return `ToolObservation` objects because the helper boundary is
command/observation based. Because the first helper template returns one
observation per request, the transport emits client-side `started` and final
`observation` events around the helper round-trip.

The helper template provides a working local JSON-lines server skeleton for the
M1 protocol surface, including semantic click, bounded Accessibility selector
click, and explicitly enabled coordinate click. Signing, notarization, and any
application-specific desktop operations remain owned by the application team
that ships the helper app.
