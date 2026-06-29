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

4. Optional editable config copied from the template:

   ```bash
   cp examples/app-control.toml app-control.toml
   ```

5. Accessibility permission granted to the terminal or host process:
   System Settings > Privacy & Security > Accessibility.

## TextEdit Smoke

Verify the installed `computer-use-macos` example entrypoint without touching
the desktop:

```bash
COMPUTER_USE_DRY_RUN=1 \
python -m computer_use_macos.examples.textedit_smoke
```

Run:

```bash
python -m computer_use_macos.examples.textedit_smoke
```

For release proof, save the real smoke JSON:

```bash
python -m computer_use_macos.examples.textedit_smoke \
  > ./textedit-smoke.json
```

The saved JSON must include `"success": true` to satisfy strict release
preflight. If the smoke fails, the report includes fields such as
`failedCommandId`, `failurePhase`, `failureSummary`, `frontmostApp`, and
`frontmostBundleId` so you can see whether the host app kept focus.

Expected:

1. `readiness` reports `ready`.
2. TextEdit opens.
3. `observe` reports TextEdit as frontmost.
4. `type_text` writes text into the focused TextEdit document.

If `readiness` reports `missing_accessibility`, grant Accessibility permission
and restart the terminal session.

If `observe` reports another host app such as an IDE or agent wrapper as
frontmost after `focus_app` succeeds, that host is stealing focus back from
TextEdit. The smoke retries transient focus races and includes
`retryObservations` in the JSON report. You can tune that retry window:

```bash
COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_ATTEMPTS=5 \
COMPUTER_USE_TEXTEDIT_FRONTMOST_RETRY_DELAY_SECONDS=1 \
python -m computer_use_macos.examples.textedit_smoke
```

For release proof, run the smoke from a normal Terminal session or the signed
helper path that will own the macOS permissions.

The repository also keeps a compatibility smoke at:

```bash
python examples/textedit_smoke.py
```

## Accessibility Troubleshooting

macOS Accessibility trust is evaluated for the process that runs the Python
code. When running the smoke from an agent host, IDE, or terminal wrapper,
granting permission to the visible app may not be enough.

If readiness still reports `missing_accessibility`, identify the exact Python
interpreter:

```bash
python - <<'PY'
import os
import sys

print(sys.executable)
print(os.path.realpath(sys.executable))
PY
```

Then add both paths to:

System Settings > Privacy & Security > Accessibility

If the Python process is launched by a host app, also add the host executable.
For example, a Codex-hosted run may use:

```text
/Applications/Codex.app/Contents/Resources/codex
```

Restart the host app or terminal after changing Accessibility permissions.

## High-Risk Boundary Smoke

Run this from a Python shell:

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient(allowed_apps=("TextEdit",))
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
