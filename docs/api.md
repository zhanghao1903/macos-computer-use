# API Contract

`macos-computer-use` exposes deterministic primitives. It does not expose an
LLM action interpreter.

## Client

```python
from macos_computer_use import MacOSComputerUseClient

client = MacOSComputerUseClient(
    allowed_apps=("TextEdit",),
    enabled=True,
    allow_coordinate_click=False,
)
```

## Methods

| Method | Purpose | Mutates Desktop |
|---|---|---:|
| `readiness()` | Report platform and permission state. | No |
| `observe(target_app=None)` | Return bounded frontmost-app/window summary. | No |
| `open_app(app)` | Open an allowlisted app. | Yes |
| `click(target, target_app=...)` | Click a low-risk semantic target. | Yes |
| `type_text(text, target_app=None)` | Type bounded text into focused input. | Yes |
| `wait(seconds=1.0)` | Sleep for bounded workflow pacing. | No |

## Result Statuses

| Status | Meaning |
|---|---|
| `ok` | Operation completed. |
| `blocked` | Operation was refused by policy, permission, or risk gate. |
| `needs_user` | Manual setup, app focus, login, or disambiguation is needed. |
| `not_available` | Platform, backend, or permission readiness is unavailable. |
| `failed` | Operation failed unexpectedly with sanitized diagnostics. |

## Confirmation Boundary

The package does not create or store confirmations. For high-risk operations it
returns `status="blocked"` with risk metadata:

```json
{
  "status": "blocked",
  "risk": {
    "level": "high",
    "requires_confirmation": true,
    "risk_label": "high_risk_click"
  },
  "metadata": {
    "confirmation_required": true,
    "confirmation_title": "Confirm desktop action"
  }
}
```

The caller must own:

- user-facing confirmation UI;
- durable confirmation storage;
- action authorization;
- audit/evidence records;
- retry behavior after confirmation resolves.

## Package Boundary

This package must remain independent from:

- Plato / Taskweavn;
- LLM providers;
- Agent frameworks;
- UI frameworks;
- remote task networking.

