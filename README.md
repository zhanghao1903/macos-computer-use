# macos-computer-use

LLM-free macOS desktop automation primitives for agent applications.

This package is deliberately small. It provides local macOS capability only:

- readiness and permission checks;
- bounded structure-first observation;
- allowlisted app opening;
- conservative text input;
- conservative click attempts;
- high-risk action classification metadata.

It does **not** include an LLM, planner, task queue, UI, confirmation store,
network worker, or business workflow. Applications such as Plato should consume
this package through a normal package dependency and map package results into
their own task, confirmation, evidence, and audit systems.

## Install

The package is intended for PyPI publication. During local development:

```bash
python -m pip install -e .
```

## Quick Start

```python
from macos_computer_use import MacOSComputerUseClient

client = MacOSComputerUseClient(
    allowed_apps=("TextEdit",),
)

print(client.readiness().to_dict())
print(client.open_app("TextEdit").to_dict())
print(client.observe(target_app="TextEdit").to_dict())
```

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

## API

See [docs/api.md](docs/api.md) for the API contract.

```python
client.readiness()
client.observe(target_app=None)
client.open_app("TextEdit")
client.type_text("hello", target_app="TextEdit")
client.click("OK", target_app="TextEdit")
client.wait(seconds=1.0)
```

All methods return dataclass models with `.to_dict()` for JSON-friendly
transport.

## Development

```bash
python -m unittest discover -s tests
python -c "import macos_computer_use; print(macos_computer_use.__version__)"
```

## Build And Publish

See [docs/release-checklist.md](docs/release-checklist.md) for the release
checklist.

Local wheel check:

```bash
python -m pip wheel . -w dist
```

Manual macOS validation is documented in
[docs/manual-smoke.md](docs/manual-smoke.md).

Recommended public release flow:

1. run tests;
2. build wheel and sdist in a clean environment;
3. publish to TestPyPI first;
4. install from TestPyPI in a clean macOS virtual environment;
5. publish the tagged release to PyPI after the smoke check passes.

Prefer PyPI trusted publishing from GitHub Actions for public release. Do not
commit PyPI tokens to this repository.

## Package Boundary

This package must not depend on:

- Plato / Taskweavn;
- LLM SDKs;
- Agent frameworks;
- UI frameworks;
- network task systems.

Consumers should wrap this package with their own adapter.
