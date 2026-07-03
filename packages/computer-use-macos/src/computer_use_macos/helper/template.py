"""Helper app project template generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .manifest import DEFAULT_HELPER_API_VERSION

_BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]+[A-Za-z0-9]$")


@dataclass(frozen=True)
class HelperTemplateConfig:
    name: str
    bundle_id: str
    team_id: str | None = None
    api_version: str = DEFAULT_HELPER_API_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _non_empty(self.name, "name"))
        object.__setattr__(self, "bundle_id", _bundle_id(self.bundle_id))
        if self.team_id is not None:
            object.__setattr__(self, "team_id", _non_empty(self.team_id, "team_id"))
        object.__setattr__(
            self,
            "api_version",
            _non_empty(self.api_version, "api_version"),
        )


@dataclass(frozen=True)
class HelperTemplateResult:
    output_dir: Path
    files: tuple[Path, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "outputDir": str(self.output_dir),
            "files": [str(path) for path in self.files],
        }


def init_helper_template(
    output_dir: str | Path,
    *,
    config: HelperTemplateConfig,
    force: bool = False,
) -> HelperTemplateResult:
    target = Path(output_dir).expanduser()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"helper template directory is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for relative_path, content in _template_files(config).items():
        path = target / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            raise FileExistsError(f"helper template file already exists: {path}")
        path.write_text(content, encoding="utf-8")
        files.append(path)
    _chmod_executable(target / "build.sh")
    _chmod_executable(target / "sign.sh")
    _chmod_executable(target / "notarize.sh")
    return HelperTemplateResult(output_dir=target, files=tuple(files))


def build_helper_template(
    template_dir: str | Path,
    *,
    build_dir: str | Path | None = None,
) -> Path:
    source = Path(template_dir).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"helper template directory not found: {source}")
    if not (source / "Info.plist.template").exists():
        raise FileNotFoundError("Info.plist.template is missing")
    output = Path(build_dir).expanduser() if build_dir else source / "build"
    output.mkdir(parents=True, exist_ok=True)
    app_dir = output / _app_bundle_name(source)
    contents = app_dir / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    info = (source / "Info.plist.template").read_text(encoding="utf-8")
    (contents / "Info.plist").write_text(info, encoding="utf-8")
    _copy_required(source / "helper_config.json", resources / "helper_config.json")
    _copy_required(source / "src" / "helper_main.py", resources / "helper_main.py")
    executable = macos / "helper"
    executable.write_text(_helper_executable(), encoding="utf-8")
    _chmod_executable(executable)
    return app_dir


def _template_files(config: HelperTemplateConfig) -> dict[str, str]:
    return {
        "README.md": _readme(config),
        "Info.plist.template": _info_plist(config),
        "entitlements.plist": _entitlements(),
        "helper_config.json": _helper_config(config),
        "build.py": _build_py(),
        "build.sh": _build_sh(),
        "sign.sh": _sign_sh(),
        "notarize.sh": _notarize_sh(config),
        "src/helper_main.py": _helper_main(config),
    }


def _readme(config: HelperTemplateConfig) -> str:
    return f"""# {config.name}

This helper app template is the stable macOS permission subject for local
app-control operations.

Bundle id: `{config.bundle_id}`

## Build

```bash
./build.sh
```

Production helpers should be signed, hardened, and notarized by the application
developer.

```bash
./sign.sh "Developer ID Application: Example Corp (TEAMID)"
APPLE_ID=dev@example.com APP_PASSWORD=app-specific-password ./notarize.sh
```

## Manifest

At runtime the helper should publish a manifest compatible with
`{config.api_version}`. The SDK doctor can inspect that manifest:

```bash
computer-use-macos helper doctor .
```

`src/helper_main.py` is a minimal JSON-lines unix socket server. It supports
`readiness`, `wait`, allowlisted `open_app`, `focus_app`, `observe`, semantic
`click`, bounded Accessibility selector click, `type_text`, `press_key`, and
`hotkey`, and returns structured failures for unsupported operations. Keep
`metadata.allowedApps` and `metadata.allowedAppBundleIds` narrow. Coordinate
click is disabled unless `metadata.allowCoordinateClick` is set to `true`.
"""


def _info_plist(config: HelperTemplateConfig) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>helper</string>
  <key>CFBundleIdentifier</key>
  <string>{config.bundle_id}</string>
  <key>CFBundleName</key>
  <string>{config.name}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.1</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSAppleEventsUsageDescription</key>
  <string>{config.name} sends Apple Events only to execute local app-control commands requested by the calling application.</string>
</dict>
</plist>
"""


def _entitlements() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key>
  <false/>
  <key>com.apple.security.cs.disable-library-validation</key>
  <false/>
</dict>
</plist>
"""


def _helper_config(config: HelperTemplateConfig) -> str:
    team = f',\n  "teamId": "{config.team_id}"' if config.team_id else ""
    return f"""{{
  "bundleId": "{config.bundle_id}",
  "apiVersion": "{config.api_version}",
  "transport": "unix_socket",
  "socketPath": "/tmp/{_slug(config.name)}.sock",
  "tokenRef": "/tmp/{_slug(config.name)}.token",
  "metadata": {{
    "allowedApps": [],
    "allowedAppBundleIds": {{}},
    "allowCoordinateClick": false,
    "maxTextChars": 4000
  }}{team}
}}
"""


def _build_py() -> str:
    return '''from __future__ import annotations

from pathlib import Path
import shutil
import stat


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
APP = BUILD / f"{ROOT.name}.app"
CONTENTS = APP / "Contents"
MACOS = CONTENTS / "MacOS"
RESOURCES = CONTENTS / "Resources"


def main() -> None:
    if APP.exists():
        shutil.rmtree(APP)
    MACOS.mkdir(parents=True, exist_ok=True)
    RESOURCES.mkdir(parents=True, exist_ok=True)
    (CONTENTS / "Info.plist").write_text(
        (ROOT / "Info.plist.template").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "helper_config.json", RESOURCES / "helper_config.json")
    shutil.copy2(ROOT / "src" / "helper_main.py", RESOURCES / "helper_main.py")
    executable = MACOS / "helper"
    executable.write_text(_helper_launcher(), encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    print(APP)


def _helper_launcher() -> str:
    return """#!/bin/sh
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export APP_CONTROL_HELPER_MANIFEST="$DIR/../Resources/helper_config.json"
exec /usr/bin/python3 "$DIR/../Resources/helper_main.py"
"""


if __name__ == "__main__":
    main()
'''


def _build_sh() -> str:
    return """#!/bin/sh
set -eu
python3 build.py
"""


def _sign_sh() -> str:
    return """#!/bin/sh
set -eu

if [ "${1:-}" != "" ] && [ "${1%.app}" != "$1" ]; then
  APP_PATH="$1"
  IDENTITY="${2:-${CODESIGN_IDENTITY:-}}"
else
  APP_PATH="build/$(basename "$PWD").app"
  IDENTITY="${1:-${CODESIGN_IDENTITY:-}}"
fi

if [ -z "$IDENTITY" ]; then
  echo "Usage: $0 [Helper.app] <Developer ID Application identity>" >&2
  echo "Or set CODESIGN_IDENTITY." >&2
  exit 2
fi

codesign \\
  --force \\
  --deep \\
  --options runtime \\
  --timestamp \\
  --entitlements entitlements.plist \\
  --sign "$IDENTITY" \\
  "$APP_PATH"

codesign --verify --deep --strict --verbose=2 "$APP_PATH"
"""


def _notarize_sh(config: HelperTemplateConfig) -> str:
    default_team = config.team_id or ""
    return """#!/bin/sh
set -eu

APP_PATH="${1:-build/$(basename "$PWD").app}"
APPLE_ID="${APPLE_ID:-}"
APP_PASSWORD="${APP_PASSWORD:-}"
TEAM_ID="${TEAM_ID:-""" + default_team + """}"
ZIP_PATH="${APP_PATH%.app}.zip"

if [ -z "$APPLE_ID" ] || [ -z "$APP_PASSWORD" ] || [ -z "$TEAM_ID" ]; then
  echo "Set APPLE_ID, APP_PASSWORD, and TEAM_ID before notarizing." >&2
  exit 2
fi

ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
xcrun notarytool submit "$ZIP_PATH" \\
  --apple-id "$APPLE_ID" \\
  --password "$APP_PASSWORD" \\
  --team-id "$TEAM_ID" \\
  --wait
xcrun stapler staple "$APP_PATH"
spctl --assess --type execute --verbose=4 "$APP_PATH"
"""


def _helper_main(config: HelperTemplateConfig) -> str:
    return f'''from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
from typing import Any


HELPER_NAME = "{config.name}"
BUNDLE_ID = "{config.bundle_id}"
API_VERSION = "{config.api_version}"
HELPER_REQUEST_SCHEMA = "app_control.helper.request.v1"
HELPER_RESPONSE_SCHEMA = "app_control.helper.response.v1"
KEY_CODES = {{
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "escape": 53,
    "esc": 53,
    "delete": 51,
    "backspace": 51,
    "forwarddelete": 117,
    "forward_delete": 117,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "page_up": 116,
    "pagedown": 121,
    "page_down": 121,
    "left": 123,
    "leftarrow": 123,
    "left_arrow": 123,
    "right": 124,
    "rightarrow": 124,
    "right_arrow": 124,
    "down": 125,
    "downarrow": 125,
    "down_arrow": 125,
    "up": 126,
    "uparrow": 126,
    "up_arrow": 126,
}}
MODIFIER_NAMES = {{
    "command": "command down",
    "cmd": "command down",
    "meta": "command down",
    "control": "control down",
    "ctrl": "control down",
    "option": "option down",
    "alt": "option down",
    "shift": "shift down",
}}
ACCESSIBILITY_ROLES = {{
    "axbutton": "button",
    "button": "button",
    "axcheckbox": "checkbox",
    "checkbox": "checkbox",
    "check_box": "checkbox",
    "axmenuitem": "menu item",
    "menuitem": "menu item",
    "menu_item": "menu item",
    "axradiobutton": "radio button",
    "radio_button": "radio button",
    "radiobutton": "radio button",
    "axpopupbutton": "pop up button",
    "pop_up_button": "pop up button",
    "popup_button": "pop up button",
    "axtextfield": "text field",
    "axtextarea": "text field",
    "text_field": "text field",
    "textfield": "text field",
}}


def main() -> None:
    manifest_path = _manifest_path()
    manifest = _load_manifest(manifest_path)
    token = _ensure_token(manifest)
    socket_path = Path(str(manifest.get("socketPath", _default_socket_path())))
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        _restrict_private_file(socket_path)
        server.listen(8)
        print(f"{{HELPER_NAME}} listening on {{socket_path}}", flush=True)
        while True:
            connection, _ = server.accept()
            with connection:
                response = handle_request(_read_line(connection), manifest, token)
                connection.sendall(
                    json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\\n"
                )


def handle_request(
    raw_request: bytes,
    manifest: dict[str, Any],
    token: str | None,
) -> dict[str, Any]:
    try:
        request = json.loads(raw_request.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        command = request.get("command")
        if not isinstance(command, dict):
            raise ValueError("request.command must be a JSON object")
        if token and request.get("token") != token:
            return _helper_response(_failure(command, "unauthorized", "bad token"))
        return _helper_response(handle_command(command, manifest))
    except Exception as exc:  # noqa: BLE001 - helper returns protocol errors.
        return _helper_error(str(exc))


def handle_command(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    operation = str(command.get("operation", ""))
    if operation == "readiness":
        return _ok(
            command,
            "Helper is running.",
            {{
                "helperName": HELPER_NAME,
                "bundleId": manifest.get("bundleId", BUNDLE_ID),
                "apiVersion": manifest.get("apiVersion", API_VERSION),
                "transport": manifest.get("transport", "unix_socket"),
                "helper": {{
                    "installed": True,
                    "running": True,
                    "bundleId": manifest.get("bundleId", BUNDLE_ID),
                }},
                "permissions": {{
                    "accessibility": None,
                    "screenRecording": None,
                    "appleEvents": None,
                }},
                "enabledOperations": [
                    "readiness",
                    "wait",
                    "open_app",
                    "focus_app",
                    "observe",
                    "click",
                    "type_text",
                    "press_key",
                    "hotkey",
                ],
            }},
        )
    if operation == "wait":
        return _wait(command)
    if operation == "open_app":
        return _open_app(command, manifest)
    if operation == "focus_app":
        return _focus_app(command, manifest)
    if operation == "observe":
        return _observe(command)
    if operation == "click":
        return _click(command, manifest)
    if operation == "type_text":
        return _type_text(command, manifest)
    if operation == "press_key":
        return _press_key(command, manifest)
    if operation == "hotkey":
        return _hotkey(command, manifest)
    return _failure(
        command,
        "unsupported_operation",
        f"helper skeleton does not support operation: {{operation}}",
    )


def _wait(command: dict[str, Any]) -> dict[str, Any]:
    try:
        seconds = _seconds(command)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    time.sleep(seconds)
    return _ok(command, f"Waited {{seconds:.2f}} seconds.", {{"seconds": seconds}})


def _open_app(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        input_payload = _input(command)
        app = _required_string(input_payload, "app", "target")
        bundle_id = _optional_string(input_payload, "bundleId", "bundle_id")
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _app_allowlist_failure(command, manifest, app, bundle_id)
    if allowlist_failure is not None:
        return allowlist_failure
    args = ["open", "-b", bundle_id] if bundle_id else ["open", "-a", app]
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=_timeout_seconds(command),
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or "Failed to open allowlisted app.").strip()
        return _failure(command, "open_app_failed", detail[:1000])
    observation = {{"app": app, "actionAttempted": True}}
    if bundle_id:
        observation["bundleId"] = bundle_id
    return _ok(command, f"Opened app: {{app}}", observation)


def _focus_app(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        input_payload = _input(command)
        app = _required_string(input_payload, "app", "target")
        bundle_id = _optional_string(input_payload, "bundleId", "bundle_id")
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _app_allowlist_failure(command, manifest, app, bundle_id)
    if allowlist_failure is not None:
        return allowlist_failure
    if bundle_id:
        script = f"tell application id {{_applescript_string(bundle_id)}} to activate\\n"
    else:
        script = f"tell application {{_applescript_string(app)}} to activate\\n"
    result = _run_osascript(
        script,
        command,
    )
    if result.returncode != 0:
        return _failure(command, "focus_app_failed", _stderr(result))
    observation = {{"app": app, "actionAttempted": True}}
    if bundle_id:
        observation["bundleId"] = bundle_id
    return _ok(
        command,
        f"Focused app: {{app}}",
        observation,
    )


def _observe(command: dict[str, Any]) -> dict[str, Any]:
    try:
        input_payload = _input(command)
        target_app = _optional_string(input_payload, "targetApp", "target_app", "app")
        bundle_id = _optional_string(input_payload, "bundleId", "bundle_id")
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    script = (
        'tell application "System Events"\\n'
        '  set frontApp to first application process whose frontmost is true\\n'
        '  set appName to name of frontApp\\n'
        '  set bundleId to ""\\n'
        '  try\\n'
        '    set bundleId to bundle identifier of frontApp\\n'
        '  end try\\n'
        '  set windowTitle to ""\\n'
        '  try\\n'
        '    set windowTitle to name of front window of frontApp\\n'
        '  end try\\n'
        '  return appName & "\\\\n" & windowTitle & "\\\\n" & bundleId\\n'
        'end tell\\n'
    )
    result = _run_osascript(script, command)
    if result.returncode != 0:
        return _failure(command, "observe_failed", _stderr(result))
    lines = result.stdout.splitlines()
    app_name = lines[0].strip() if lines else ""
    window_title = lines[1].strip() if len(lines) > 1 else ""
    frontmost_bundle_id = lines[2].strip() if len(lines) > 2 else ""
    if bundle_id and frontmost_bundle_id and frontmost_bundle_id != bundle_id:
        return _failure(
            command,
            "target_not_frontmost",
            (
                "Target app bundle id is not frontmost: "
                f"expected {{bundle_id}}, got {{frontmost_bundle_id}}."
            ),
        )
    if (
        target_app
        and (not bundle_id or not frontmost_bundle_id)
        and app_name != target_app
    ):
        return _failure(
            command,
            "target_not_frontmost",
            f"Target app is not frontmost: expected {{target_app}}, got {{app_name}}.",
        )
    snapshot_id = f"frontmost:{{app_name}}:{{window_title}}"
    summary = f"Frontmost app: {{app_name or 'unknown'}}."
    if window_title:
        summary += f" Window: {{window_title}}."
    observation = {{
        "frontmostApp": app_name,
        "frontmostBundleId": frontmost_bundle_id,
        "windowTitle": window_title,
        "snapshotId": snapshot_id,
        "textExtract": summary,
    }}
    if target_app:
        observation["targetApp"] = target_app
    if bundle_id:
        observation["bundleId"] = bundle_id
    return _ok(command, summary, observation)


def _type_text(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        input_payload = _input(command)
        text = _required_text(input_payload)
        target_identity = _target_identity_observation(command)
        if "\\n" in text or "\\r" in text:
            raise ValueError("type_text does not submit newline text")
        max_chars = _max_text_chars(manifest)
        if len(text) > max_chars:
            raise ValueError("text exceeds maxTextChars")
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _target_allowlist_failure(command, manifest)
    if allowlist_failure is not None:
        return allowlist_failure
    focus_failure = _target_focus_failure(command)
    if focus_failure is not None:
        return focus_failure
    result = _run_osascript(_type_text_script(text), command)
    if result.returncode != 0:
        return _failure(command, "type_text_failed", _stderr(result))
    return _ok(
        command,
        "Typed text into the focused editable target.",
        {{
            "chars": len(text),
            "submitted": False,
            "inputMethod": "clipboard",
            **target_identity,
        }},
    )


def _press_key(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        key = _key_from_command(command)
        target_identity = _target_identity_observation(command)
        script = _keyboard_script(key)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _target_allowlist_failure(command, manifest)
    if allowlist_failure is not None:
        return allowlist_failure
    focus_failure = _target_focus_failure(command)
    if focus_failure is not None:
        return focus_failure
    result = _run_osascript(script, command)
    if result.returncode != 0:
        return _failure(command, "press_key_failed", _stderr(result))
    return _ok(
        command,
        f"Pressed key: {{key}}.",
        {{"key": key, **target_identity, "actionAttempted": True}},
    )


def _hotkey(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        keys = _keys_from_command(command)
        target_identity = _target_identity_observation(command)
        modifiers, key = _split_hotkey(keys)
        script = _keyboard_script(key, modifiers=modifiers)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _target_allowlist_failure(command, manifest)
    if allowlist_failure is not None:
        return allowlist_failure
    focus_failure = _target_focus_failure(command)
    if focus_failure is not None:
        return focus_failure
    result = _run_osascript(script, command)
    if result.returncode != 0:
        return _failure(command, "hotkey_failed", _stderr(result))
    return _ok(
        command,
        f"Pressed hotkey: {{'+'.join(keys)}}.",
        {{
            "keys": keys,
            "key": key,
            "modifiers": modifiers,
            **target_identity,
            "actionAttempted": True,
        }},
    )


def _click(command: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        input_payload = _input(command)
        selector = _accessibility_selector_from_input(input_payload)
        if selector is not None:
            return _click_accessibility(command, manifest, selector)
        coordinate = _coordinate_from_input(input_payload)
        if coordinate is not None:
            return _click_coordinate(command, manifest, coordinate[0], coordinate[1])
        target = _required_string(input_payload, "target", "text")
        target_app = _required_string(input_payload, "targetApp", "target_app", "app")
        bundle_id = _optional_string(input_payload, "bundleId", "bundle_id")
        target_identity = _target_identity_from_input(input_payload)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _app_allowlist_failure(
        command,
        manifest,
        target_app,
        bundle_id,
    )
    if allowlist_failure is not None:
        return allowlist_failure
    focus_failure = _target_focus_failure(command)
    if focus_failure is not None:
        return focus_failure
    result = _run_osascript(
        'tell application "System Events"\\n'
        f'  tell process {{_applescript_string(target_app)}}\\n'
        '    set frontmost to true\\n'
        f'    click button {{_applescript_string(target)}} of front window\\n'
        '  end tell\\n'
        'end tell\\n',
        command,
    )
    if result.returncode != 0:
        return _failure(command, "click_failed", _stderr(result))
    return _ok(
        command,
        "Clicked semantic target.",
        {{"target": target, **target_identity, "actionAttempted": True}},
    )


def _click_accessibility(
    command: dict[str, Any],
    manifest: dict[str, Any],
    selector: dict[str, Any],
) -> dict[str, Any]:
    try:
        input_payload = _input(command)
        target_app = _required_string(input_payload, "targetApp", "target_app", "app")
        bundle_id = _optional_string(input_payload, "bundleId", "bundle_id")
        target_identity = _target_identity_from_input(input_payload)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _app_allowlist_failure(
        command,
        manifest,
        target_app,
        bundle_id,
    )
    if allowlist_failure is not None:
        return allowlist_failure
    focus_failure = _target_focus_failure(command)
    if focus_failure is not None:
        return focus_failure
    result = _run_osascript(_accessibility_click_script(target_app, selector), command)
    if result.returncode != 0:
        return _failure(command, "click_failed", _stderr(result))
    return _ok(
        command,
        "Clicked accessibility selector target.",
        {{
            "selector": selector,
            **target_identity,
            "actionAttempted": True,
        }},
    )


def _click_coordinate(
    command: dict[str, Any],
    manifest: dict[str, Any],
    x: int,
    y: int,
) -> dict[str, Any]:
    if not _allow_coordinate_click(manifest):
        return _failure(
            command,
            "coordinate_click_disabled",
            "Raw coordinate click is disabled by default.",
        )
    target_app = _optional_target_app(command)
    try:
        target_identity = _target_identity_observation(command)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    allowlist_failure = _target_allowlist_failure(command, manifest)
    if allowlist_failure is not None:
        return allowlist_failure
    focus_failure = _target_focus_failure(command)
    if focus_failure is not None:
        return focus_failure
    result = _run_osascript(
        'tell application "System Events"\\n'
        "  click at {{" + str(x) + ", " + str(y) + "}}\\n"
        'end tell\\n',
        command,
    )
    if result.returncode != 0:
        return _failure(command, "coordinate_click_failed", _stderr(result))
    return _ok(
        command,
        "Clicked screen coordinate.",
        {{
            "coordinateClick": True,
            "x": x,
            "y": y,
            **target_identity,
            "actionAttempted": True,
        }},
    )


def _ok(
    command: dict[str, Any],
    summary: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {{
        "schema": "app_control.observation.v1",
        "commandId": command.get("commandId", "unknown"),
        "tool": command.get("tool", "macos.computer_use"),
        "operation": command.get("operation", "unknown"),
        "status": "ok",
        "success": True,
        "summary": summary,
        "observation": observation,
    }}


def _failure(
    command: dict[str, Any],
    failure_kind: str,
    message: str,
) -> dict[str, Any]:
    return {{
        "schema": "app_control.observation.v1",
        "commandId": command.get("commandId", "unknown"),
        "tool": command.get("tool", "macos.computer_use"),
        "operation": command.get("operation", "unknown"),
        "status": "failed",
        "success": False,
        "summary": message,
        "observation": {{}},
        "failureKind": failure_kind,
        "message": message,
        "retryable": False,
    }}


def _helper_response(observation: dict[str, Any]) -> dict[str, Any]:
    return {{
        "schema": HELPER_RESPONSE_SCHEMA,
        "success": bool(observation.get("success")),
        "observation": observation,
    }}


def _helper_error(message: str) -> dict[str, Any]:
    return {{
        "schema": HELPER_RESPONSE_SCHEMA,
        "success": False,
        "error": {{
            "failureKind": "helper_error",
            "message": message or "helper request failed",
            "retryable": False,
        }},
    }}


def _input(command: dict[str, Any]) -> dict[str, Any]:
    value = command.get("input", {{}})
    if not isinstance(value, dict):
        raise ValueError("command.input must be a JSON object")
    return value


def _required_string(input_payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = input_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(" or ".join(keys) + " is required")


def _optional_string(input_payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in input_payload:
            value = input_payload[key]
            if isinstance(value, str) and value.strip():
                return value.strip()
            raise ValueError(" or ".join(keys) + " must be a non-empty string")
    return None


def _required_text(input_payload: dict[str, Any]) -> str:
    value = input_payload.get("text")
    if not isinstance(value, str) or not value:
        raise ValueError("text is required")
    return value


def _optional_target_app(command: dict[str, Any]) -> str | None:
    input_payload = _input(command)
    for key in ("targetApp", "target_app", "app"):
        value = input_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _optional_bundle_id(command: dict[str, Any]) -> str | None:
    return _optional_string(_input(command), "bundleId", "bundle_id")


def _target_identity_from_input(input_payload: dict[str, Any]) -> dict[str, Any]:
    identity: dict[str, Any] = {{}}
    target_app = _optional_string(input_payload, "targetApp", "target_app", "app")
    bundle_id = _optional_string(input_payload, "bundleId", "bundle_id")
    if target_app:
        identity["targetApp"] = target_app
    if bundle_id:
        identity["bundleId"] = bundle_id
    return identity


def _target_identity_observation(command: dict[str, Any]) -> dict[str, Any]:
    return _target_identity_from_input(_input(command))


def _target_focus_failure(command: dict[str, Any]) -> dict[str, Any] | None:
    try:
        target_app = _optional_target_app(command)
        bundle_id = _optional_bundle_id(command)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    if not target_app and not bundle_id:
        return None
    target_input: dict[str, Any] = {{}}
    if target_app:
        target_input["targetApp"] = target_app
    if bundle_id:
        target_input["bundleId"] = bundle_id
    observed = _observe({{**command, "input": target_input}})
    if observed.get("success") is True:
        return None
    return observed


def _target_allowlist_failure(
    command: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        target_app = _optional_target_app(command)
        bundle_id = _optional_bundle_id(command)
    except ValueError as exc:
        return _failure(command, "invalid_input", str(exc))
    if target_app:
        return _app_allowlist_failure(command, manifest, target_app, bundle_id)
    if bundle_id and bundle_id not in set(_allowed_app_bundle_ids(manifest).values()):
        return _failure(
            command,
            "app_not_allowlisted",
            f"App bundle id is not allowlisted: {{bundle_id}}",
        )
    return None


def _app_allowlist_failure(
    command: dict[str, Any],
    manifest: dict[str, Any],
    app: str,
    bundle_id: str | None,
) -> dict[str, Any] | None:
    allowed_apps = _allowed_apps(manifest)
    if app not in allowed_apps:
        return _failure(
            command,
            "app_not_allowlisted",
            f"App is not allowlisted: {{app}}",
        )
    expected_bundle_id = _allowed_app_bundle_ids(manifest).get(app)
    if expected_bundle_id and bundle_id and expected_bundle_id != bundle_id:
        return _failure(
            command,
            "app_not_allowlisted",
            (
                "App bundle id is not allowlisted for "
                f"{{app}}: expected {{expected_bundle_id}}, got {{bundle_id}}."
            ),
        )
    return None


def _key_from_command(command: dict[str, Any]) -> str:
    input_payload = _input(command)
    value = input_payload.get("key")
    if isinstance(value, str) and value.strip():
        return value.strip()
    keys = input_payload.get("keys")
    if isinstance(keys, list) and len(keys) == 1:
        only = keys[0]
        if isinstance(only, str) and only.strip():
            return only.strip()
    raise ValueError("press_key requires key or exactly one keys item")


def _keys_from_command(command: dict[str, Any]) -> list[str]:
    input_payload = _input(command)
    value = input_payload.get("keys")
    if not isinstance(value, list):
        raise ValueError("hotkey requires keys")
    keys = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(keys) != len(value):
        raise ValueError("hotkey keys must be non-empty strings")
    return keys


def _seconds(command: dict[str, Any]) -> float:
    input_payload = _input(command)
    value = input_payload.get("seconds", 1.0)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("seconds must be a number")
    seconds = float(value)
    if seconds < 0 or seconds > 60:
        raise ValueError("seconds must be between 0 and 60")
    return seconds


def _coordinate_from_input(input_payload: dict[str, Any]) -> tuple[int, int] | None:
    x = _first(input_payload, "x", "screenX", "screen_x")
    y = _first(input_payload, "y", "screenY", "screen_y")
    if x is not None or y is not None:
        if x is None or y is None:
            raise ValueError("coordinate click requires both x and y")
        return _coordinate_int(x, "x"), _coordinate_int(y, "y")
    raw_coordinate = _first(input_payload, "coordinate", "coordinates", "point")
    if raw_coordinate is None:
        return None
    if isinstance(raw_coordinate, dict):
        x = _first(raw_coordinate, "x", "screenX", "screen_x")
        y = _first(raw_coordinate, "y", "screenY", "screen_y")
        if x is None or y is None:
            raise ValueError("coordinate click requires both x and y")
        return _coordinate_int(x, "x"), _coordinate_int(y, "y")
    if isinstance(raw_coordinate, list) and len(raw_coordinate) == 2:
        return (
            _coordinate_int(raw_coordinate[0], "x"),
            _coordinate_int(raw_coordinate[1], "y"),
        )
    raise ValueError("coordinate must be an object with x/y or a two-item list")


def _coordinate_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{{field_name}} must be an integer")
    if value < 0:
        raise ValueError(f"{{field_name}} must be non-negative")
    return value


def _accessibility_selector_from_input(input_payload: dict[str, Any]) -> dict[str, Any] | None:
    raw_selector = _first(
        input_payload,
        "selector",
        "accessibilitySelector",
        "accessibility_selector",
    )
    if raw_selector is None:
        return None
    if not isinstance(raw_selector, dict):
        raise ValueError("selector must be an object")
    return _normalize_accessibility_selector(raw_selector)


def _normalize_accessibility_selector(selector: dict[str, Any]) -> dict[str, Any]:
    role = _optional_string(selector, "role", "kind", "element") or "button"
    role_name = ACCESSIBILITY_ROLES.get(_key_lookup_name(role))
    if role_name is None:
        raise ValueError(f"unsupported accessibility selector role: {{role}}")
    name = _optional_string(selector, "name", "title", "label", "description")
    raw_index = _first(selector, "index")
    if name is None and raw_index is None:
        raise ValueError(
            "accessibility selector requires name/title/label/description or index"
        )
    normalized: dict[str, Any] = {{"role": role_name}}
    if name is not None:
        normalized["name"] = name
    if raw_index is not None:
        normalized["index"] = _positive_int(raw_index, "index")
    return normalized


def _positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{{field_name}} must be an integer")
    if value <= 0:
        raise ValueError(f"{{field_name}} must be positive")
    return value


def _accessibility_click_script(target_app: str, selector: dict[str, Any]) -> str:
    role = str(selector["role"])
    name = selector.get("name")
    if isinstance(name, str):
        element = f"{{role}} {{_applescript_string(name)}}"
    else:
        element = f"{{role}} {{selector['index']}}"
    return (
        'tell application "System Events"\\n'
        f'  tell process {{_applescript_string(target_app)}}\\n'
        '    set frontmost to true\\n'
        f'    click {{element}} of front window\\n'
        '  end tell\\n'
        'end tell\\n'
    )


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _timeout_seconds(command: dict[str, Any]) -> float:
    value = command.get("timeoutMs")
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return 10.0
    return min(float(value) / 1000.0, 60.0)


def _max_text_chars(manifest: dict[str, Any]) -> int:
    metadata = manifest.get("metadata", {{}})
    value = metadata.get("maxTextChars") if isinstance(metadata, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 4000


def _allow_coordinate_click(manifest: dict[str, Any]) -> bool:
    metadata = manifest.get("metadata", {{}})
    value = metadata.get("allowCoordinateClick") if isinstance(metadata, dict) else None
    return value is True


def _allowed_apps(manifest: dict[str, Any]) -> set[str]:
    metadata = manifest.get("metadata", {{}})
    raw = metadata.get("allowedApps") if isinstance(metadata, dict) else None
    if raw is None:
        raw = manifest.get("allowedApps", [])
    if not isinstance(raw, list):
        allowed = set()
    else:
        allowed = {{
            item.strip() for item in raw if isinstance(item, str) and item.strip()
        }}
    allowed.update(_allowed_app_bundle_ids(manifest).keys())
    return allowed


def _allowed_app_bundle_ids(manifest: dict[str, Any]) -> dict[str, str]:
    metadata = manifest.get("metadata", {{}})
    raw = metadata.get("allowedAppBundleIds") if isinstance(metadata, dict) else None
    if raw is None:
        raw = manifest.get("allowedAppBundleIds", {{}})
    if not isinstance(raw, dict):
        return {{}}
    return {{
        str(app).strip(): bundle_id.strip()
        for app, bundle_id in raw.items()
        if str(app).strip() and isinstance(bundle_id, str) and bundle_id.strip()
    }}


def _run_osascript(
    script: str,
    command: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=_timeout_seconds(command),
        check=False,
    )


def _type_text_script(text: str) -> str:
    escaped_text = _applescript_string(text)
    return (
        "set __computerUseClipboardWasCaptured to false\\n"
        'set __computerUsePreviousClipboard to ""\\n'
        "try\\n"
        "  set __computerUsePreviousClipboard to the clipboard\\n"
        "  set __computerUseClipboardWasCaptured to true\\n"
        "end try\\n"
        "try\\n"
        f"  set the clipboard to {{escaped_text}}\\n"
        "  delay 0.05\\n"
        '  tell application "System Events"\\n'
        '    keystroke "v" using {{command down}}\\n'
        "  end tell\\n"
        "  delay 0.1\\n"
        "on error __computerUseErrorMessage number __computerUseErrorNumber\\n"
        "  if __computerUseClipboardWasCaptured then set the clipboard to "
        "__computerUsePreviousClipboard\\n"
        "  error __computerUseErrorMessage number __computerUseErrorNumber\\n"
        "end try\\n"
        "if __computerUseClipboardWasCaptured then set the clipboard to "
        "__computerUsePreviousClipboard\\n"
    )


def _keyboard_script(key: str, modifiers: list[str] | None = None) -> str:
    modifier_clause = _modifier_clause(modifiers or [])
    key_code = KEY_CODES.get(_key_lookup_name(key))
    if key_code is not None:
        action = f"  key code {{key_code}}{{modifier_clause}}\\n"
    else:
        if len(key) != 1:
            raise ValueError(f"unsupported key name: {{key}}")
        action = f"  keystroke {{_applescript_string(key)}}{{modifier_clause}}\\n"
    return 'tell application "System Events"\\n' + action + "end tell\\n"


def _split_hotkey(keys: list[str]) -> tuple[list[str], str]:
    if len(keys) < 2:
        raise ValueError("hotkey requires at least one modifier and one key")
    modifiers: list[str] = []
    action_keys: list[str] = []
    for key in keys:
        if _modifier_script_name(key) is not None:
            modifiers.append(key)
        else:
            action_keys.append(key)
    if not modifiers:
        raise ValueError("hotkey requires at least one modifier")
    if len(action_keys) != 1:
        raise ValueError("hotkey requires exactly one non-modifier key")
    return modifiers, action_keys[0]


def _modifier_clause(modifiers: list[str]) -> str:
    modifier_names = [_modifier_script_name(modifier) for modifier in modifiers]
    if not modifier_names:
        return ""
    if any(name is None for name in modifier_names):
        raise ValueError("hotkey contains an unsupported modifier")
    return " using {{" + ", ".join(name for name in modifier_names if name) + "}}"


def _modifier_script_name(modifier: str) -> str | None:
    return MODIFIER_NAMES.get(_key_lookup_name(modifier))


def _key_lookup_name(key: str) -> str:
    return key.strip().replace("-", "_").replace(" ", "_").lower()


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\\\", "\\\\\\\\").replace('"', '\\\\"') + '"'


def _stderr(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or "helper command failed").strip()[:1000]


def _read_line(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\\n" in chunk:
            break
    line, _, _ = b"".join(chunks).partition(b"\\n")
    if not line:
        raise ValueError("empty request")
    return line


def _manifest_path() -> Path:
    configured = os.environ.get("APP_CONTROL_HELPER_MANIFEST")
    if configured:
        return Path(configured).expanduser()
    candidates = (
        Path(__file__).with_name("helper_config.json"),
        Path(__file__).resolve().parents[1] / "helper_config.json",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("helper manifest must be a JSON object")
    return payload


def _ensure_token(manifest: dict[str, Any]) -> str | None:
    token = manifest.get("token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    token_ref = manifest.get("tokenRef")
    if not isinstance(token_ref, str) or not token_ref.strip():
        return None
    token_path = Path(token_ref).expanduser()
    if token_path.exists():
        _restrict_private_file(token_path)
        return token_path.read_text(encoding="utf-8").strip()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_hex(24)
    try:
        fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _restrict_private_file(token_path)
        return token_path.read_text(encoding="utf-8").strip()
    with os.fdopen(fd, "w", encoding="utf-8") as token_file:
        token_file.write(generated)
    _restrict_private_file(token_path)
    return generated


def _default_socket_path() -> str:
    return "/tmp/{_slug(config.name)}.sock"


def _restrict_private_file(path: Path) -> None:
    path.chmod(0o600)


if __name__ == "__main__":
    main()
'''


def _helper_executable() -> str:
    return """#!/bin/sh
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export APP_CONTROL_HELPER_MANIFEST="$DIR/../Resources/helper_config.json"
exec /usr/bin/python3 "$DIR/../Resources/helper_main.py"
"""


def _app_bundle_name(source: Path) -> str:
    if source.name.endswith(".app"):
        return source.name
    return f"{source.name}.app"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return slug.lower() or "computer-use-helper"


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _bundle_id(value: str) -> str:
    bundle_id = _non_empty(value, "bundle_id")
    if "." not in bundle_id or not _BUNDLE_ID_RE.match(bundle_id):
        raise ValueError("bundle_id must look like a reverse-DNS identifier")
    return bundle_id


def _copy_required(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"required helper template file is missing: {source}")
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _chmod_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | 0o111)
