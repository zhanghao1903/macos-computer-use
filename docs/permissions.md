# Permissions Guide

macOS grants GUI automation permissions to the process that performs the
desktop action. A Python package name is not a permission subject.

## Permission Subjects

Development mode:

- Subject: the Python process, terminal app, IDE, or test runner.
- Good for: local smoke tests and early development.
- Tradeoff: the subject changes when the launcher changes, so TCC prompts can
  reappear.

Helper mode:

- Subject: the developer's signed helper app.
- Good for: production use and stable end-user setup.
- Tradeoff: the application team owns signing, notarization, installation, and
  user-facing setup instructions.

Local service mode:

- Subject: whichever process hosts the service backend.
- Good for: non-Python callers on the same machine.
- Tradeoff: the service does not add business authorization; it only exposes
  local command transport.

## Permissions

Accessibility:

- Required for UI observation and keyboard/mouse control.
- Needed by direct Python process in direct mode.
- Needed by the helper app in helper mode.

Automation / Apple Events:

- May be required when AppleScript targets another application.
- The prompt is tied to the executing process identity.

Screen Recording:

- Not required by the current default operations.
- Keep disabled unless a future backend explicitly needs screenshots.
- `readiness()` uses the macOS non-prompting Screen Capture preflight API when
  available. The reported value can be `true`, `false`, or `null` when the host
  cannot probe it.

`readiness()` reports Apple Events as `null` unless a backend can evaluate a
specific target app. macOS Automation permission is target-app specific, so a
global yes/no value would be misleading.

## Recommended Flow

1. Start with direct mode for TextEdit smoke tests.
2. Generate a helper template with `computer-use-macos helper init`.
3. Sign and ship a helper app owned by your application.
4. Ask users to grant Accessibility to that helper app.
5. Use `computer-use-macos helper doctor` to verify manifest and setup.

## Security Boundaries

These packages provide low-level safety boundaries:

- app allowlists;
- local token checks for service/helper transports;
- `computer-use-macos serve` requires a local token unless the caller explicitly
  passes `--allow-unauthenticated` for isolated local tests;
- generated helper token/socket paths and local service socket paths are
  restricted to private `0600` filesystem permissions;
- bounded timeouts;
- no remote access by default;
- no screenshots by default;
- structured failures for unknown or unsafe states.

They do not decide whether a business action is allowed. The caller must run
its own `authorize(command)` or confirmation flow before sending commands.
