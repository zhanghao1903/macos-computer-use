# Manual macOS Smoke

This smoke verifies the real macOS path. It is intentionally manual because CI
should not require desktop permissions.

## Prerequisites

1. macOS host.
2. Python 3.11+.
3. Package installed:

   ```bash
   python -m pip install -e .
   ```

4. Accessibility permission granted to the terminal or host process:
   System Settings > Privacy & Security > Accessibility.

## TextEdit Smoke

Run:

```bash
python examples/textedit_smoke.py
```

Expected:

1. `readiness` reports `ready`.
2. TextEdit opens.
3. `observe` reports TextEdit as frontmost.
4. `type_text` writes text into the focused TextEdit document.

If `readiness` reports `missing_accessibility`, grant Accessibility permission
and restart the terminal session.

## High-Risk Boundary Smoke

Run this from a Python shell:

```python
from macos_computer_use import MacOSComputerUseClient

client = MacOSComputerUseClient(allowed_apps=("TextEdit",))
print(client.click("Send", target_app="TextEdit").to_dict())
```

Expected:

- result status is `blocked`;
- metadata contains `confirmation_required=True`;
- no click is performed.

## Non-Goals For Manual Smoke

- No WeChat sending.
- No screenshot capture.
- No password entry.
- No system dialog automation.
- No network ExecutionEnv.

