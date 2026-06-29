# App Control Tool Packages

LLM-free macOS desktop automation primitives for agent applications.

## Package Suite

This repository contains a protocol-first app-control tools suite:

- `packages/app-control-protocol`: shared `ToolCommand`, `ToolObservation`,
  `ToolEvent`, error, schema, and configuration contracts.
- `packages/computer-use-macos`: macOS app-control backend, helper tooling,
  local service, CLI, and TextEdit smoke entrypoint.
- `packages/wechat-desktop-tool`: WeChat Desktop semantic tools built on top of
  the protocol and an injected app-control client.

The suite is deliberately small. It provides local macOS capability only:

- readiness and permission checks;
- bounded structure-first observation;
- allowlisted app opening and activation;
- conservative text input;
- conservative click attempts;
- high-risk action classification metadata.

It does **not** include an LLM, planner, task queue, UI, confirmation store,
network worker, or business workflow. Applications such as Plato should consume
this package through a normal package dependency and map package results into
their own task, confirmation, evidence, and audit systems.

## Install

During local development:

```bash
python -m pip install -e packages/app-control-protocol
python -m pip install -e packages/computer-use-macos
python -m pip install -e packages/wechat-desktop-tool
```

For a new developer-preview setup, follow [docs/quickstart.md](docs/quickstart.md).
It covers the 30 minute TextEdit smoke, local service mode, helper path, and
60 minute WeChat focus/draft smoke.

## Quick Start

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient(
    allowed_apps=("TextEdit",),
)

print(client.readiness().to_dict())
print(client.open_app("TextEdit").to_dict())
print(client.observe(target_app="TextEdit").to_dict())
```

With shared app-control configuration:

```python
client = ComputerUseClient.from_config("app-control.toml")
```

Start from the editable template:

```bash
cp examples/app-control.toml app-control.toml
```

Helper-backed clients expose the same protocol-first convenience methods as
the direct backend (`readiness`, `open_app`, `type_text`, `press_key`,
`hotkey`, and the other computer-use operations). These helper methods return
`ToolObservation` objects because the helper boundary is command/observation
based.

## Safety Defaults

The default policy is intentionally conservative:

- non-allowlisted apps are blocked;
- raw coordinate click is disabled;
- high-risk targets such as send, pay, delete, submit, install, and permission
  controls are blocked with `confirmation_required` metadata;
- `type_text` does not press Enter and rejects newline text;
- password/security/system-dialog targets are blocked;
- screenshots are not captured.

The caller owns user confirmation. This package only returns risk metadata.

## macOS Permissions

Most operations require macOS Accessibility permission for the Python process or
the app launching it.

The package reports missing permissions through `readiness()` instead of trying
to bypass them.

Production callers should use a signed helper app as the stable macOS
permission subject. The permission model is documented in
[docs/permissions.md](docs/permissions.md). The helper manifest, JSON-lines
unix socket transport, and doctor workflow are documented in
[docs/helper-packaging.md](docs/helper-packaging.md).

```bash
computer-use-macos helper init ./computer-use-helper \
  --name "Example Computer Use Helper" \
  --bundle-id com.example.computer-use-helper
computer-use-macos helper build ./computer-use-helper
computer-use-macos helper doctor ./computer-use-helper
```

Non-Python callers can use the local Unix socket service mode documented in
[docs/local-service.md](docs/local-service.md):

```bash
computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness
```

When `[helper] endpoint` and optional `token` are set in `app-control.toml`,
both `serve` and `request` can read the local service connection settings from
`--config`; explicit CLI socket/token values still take precedence.

## API

See [docs/api.md](docs/api.md) for the API contract.

```python
client.readiness()
client.run_command(command)
client.run_stream(command)
client.observe(target_app=None)
client.open_app("TextEdit")
client.focus_app("TextEdit")
client.type_text("hello", target_app="TextEdit")
client.press_key("Return", target_app="TextEdit")
client.hotkey(("Command", "K"), target_app="TextEdit")
client.click("OK", target_app="TextEdit")
client.click_accessibility({"role": "button", "name": "OK"}, target_app="TextEdit")
client.click_coordinate(120, 240)  # requires allow_coordinate_click=True
client.wait(seconds=1.0)
```

All methods return dataclass models with `.to_dict()` for JSON-friendly
transport.

## Development

```bash
python scripts/dev_check.py
```

For targeted debugging, the unified check runs these underlying suites:

```bash
python -m unittest discover -s tests
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest discover -s packages/app-control-protocol/tests
PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
python scripts/release_preflight.py
```

To see optional checks, including the strict external-proof release gate:

```bash
python scripts/dev_check.py --list
python scripts/dev_check.py --check wheel-preflight
python scripts/dev_check.py --check release-proof-preflight
```

`wheel-preflight` builds all local wheels in a temporary directory, verifies
their packaged contents, installs them from the local wheelhouse into a clean
virtual environment, and runs the API smoke snippets. `release-proof-preflight`
expects the JSON assets in `./release-proof/` as prepared by
`scripts/release_proof_bundle.py`.

## Build And Publish

See [docs/release-checklist.md](docs/release-checklist.md) for the release
checklist and [docs/publishing.md](docs/publishing.md) for the PyPI release
flow. Migration guidance is in
[docs/migration-notes.md](docs/migration-notes.md).

Local wheel check:

```bash
python -m pip wheel --no-build-isolation --no-deps packages/app-control-protocol -w dist
python -m pip wheel --no-build-isolation --no-deps packages/computer-use-macos -w dist
python -m pip wheel --no-build-isolation --no-deps packages/wechat-desktop-tool -w dist
python scripts/release_preflight.py --wheel-dir dist
```

Manual macOS validation is documented in
[docs/manual-smoke.md](docs/manual-smoke.md). Manual WeChat validation is
documented in [docs/wechat-smoke.md](docs/wechat-smoke.md).

Recommended public release flow:

1. run tests;
2. build wheel and sdist in a clean environment;
3. publish to TestPyPI first;
4. install from TestPyPI in a clean macOS virtual environment;
5. publish the tagged release to PyPI after the smoke check passes.

Prefer PyPI trusted publishing from GitHub Actions for public release. Do not
commit PyPI tokens to this repository.

## Package Boundary

These packages must not depend on:

- Plato / Taskweavn;
- LLM SDKs;
- Agent frameworks;
- UI frameworks;
- network task systems.

Consumers should wrap the package suite with their own adapter.
