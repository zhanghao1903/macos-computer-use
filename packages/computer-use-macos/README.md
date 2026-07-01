# computer-use-macos

Protocol-first macOS app-control backend package.

This distribution exposes the planned `computer_use_macos` import path and
`computer-use-macos` CLI with its own package-local macOS backend
implementation. The old root package can remain as a compatibility seed, but
this distribution does not depend on it at runtime.

This package must remain independent from `wechat-desktop-tool` and any
product-specific runtime.

## Quick Start

```python
from computer_use_macos import ComputerUseClient, open_app_command

client = ComputerUseClient.from_config("app-control.toml")
observation = client.run_command(
    open_app_command("TextEdit", bundle_id="com.apple.TextEdit")
)
print(observation.to_dict())
```

Use `computer_use_command(...)` when you need to construct a custom command
envelope while keeping the stable `macos.computer_use` tool name:

```python
from computer_use_macos import computer_use_command

command = computer_use_command(
    "open_app",
    {"app": "TextEdit", "bundleId": "com.apple.TextEdit"},
    command_id="cmd_open_textedit",
)
```

Keyboard actions use the same command envelope:

```python
from computer_use_macos import hotkey_command, press_key_command

client.run_command(press_key_command("Return"))
client.run_command(hotkey_command(("Command", "F")))
```

Scoped Accessibility reads are available through `accessibility_query`. Use
this when an application needs a small, bounded set of UI nodes instead of a
full raw Accessibility tree:

```python
from computer_use_macos import accessibility_query_command

observation = client.run_command(
    accessibility_query_command(
        target_app="WeChat",
        bundle_id="com.tencent.xinWeChat",
        root={"kind": "focusedWindow"},
        query={
            "scope": "children",
            "maxDepth": 1,
            "limit": 80,
            "attributes": ["AXRole", "AXDescription", "AXValue"],
            "actions": True,
        },
    )
)
nodes = observation.observation["accessibilityQuery"]["nodes"]
```

Helper manifests can be used directly:

```python
client = ComputerUseClient.from_helper_manifest("helper_config.json")
observation = client.open_app("TextEdit")
```

Helper-backed clients expose `run_command`, `run_stream`, and the same
protocol-first convenience methods as the direct backend. The convenience
methods return `ToolObservation` objects at the helper boundary.

Standalone helper config works as a constructor input:

```python
from computer_use_macos import ComputerUseClient, HelperConfig

client = ComputerUseClient(
    HelperConfig(
        helper_app_path="/Applications/Example Computer Use Helper.app",
        bundle_id="com.example.computer-use-helper",
        allowed_apps=("TextEdit",),
    )
)
```

## CLI

```bash
computer-use-macos helper init ./computer-use-helper \
  --name "Example Computer Use Helper" \
  --bundle-id com.example.computer-use-helper
computer-use-macos helper build ./computer-use-helper
computer-use-macos helper doctor ./computer-use-helper
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness
```

## TextEdit Smoke

The package includes a small manual TextEdit smoke. First verify the installed
entrypoint without touching the desktop:

```bash
COMPUTER_USE_DRY_RUN=1 \
python -m computer_use_macos.examples.textedit_smoke
```

Then run the real smoke on macOS after granting Accessibility permission to the
terminal or host process:

```bash
python -m computer_use_macos.examples.textedit_smoke
```

## Migration Boundary

The current package is the developer-facing macOS backend distribution. Public
imports are available from `computer_use_macos`, and the implementation lives
under `packages/computer-use-macos/src`.

The package provides:

- `ComputerUseClient` / `MacOSComputerUseClient`
- readiness and permission probes with structured `permissions`, `helper`, and
  `enabledOperations` fields
- command runner primitives
- helper manifest, transport, discovery, launcher, doctor, and template APIs
- protocol-compatible `run_command` and `run_stream`, including `press_key`
  and `hotkey`
- scoped `accessibility_query` for bounded macOS AX reads
- observer callbacks compatible with `app_control_protocol.ToolObserver`
- semantic click, bounded Accessibility selector click, and explicitly enabled
  coordinate click
- local Unix socket service mode with `run`, `submit`, `poll`, and `stream`
  actions, a small socket request CLI/client, plus SSE frame formatting helpers
  for application-owned HTTP wrappers
- developer-facing module entrypoints: `commands`, `observations`, `errors`,
  `readiness`, and `transport`
- stable `COMPUTER_USE_FAILURE_KINDS` constants for package-owned failure
  routing

It does not provide WeChat semantics, product authorization, UI, LLM decision
loops, or caller task state.
