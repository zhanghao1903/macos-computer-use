# Migration Notes

This repository has moved from a single compatibility package to a three-package
app-control tool suite.

## Current Packages

Backend distribution:

```python
from computer_use_macos import ComputerUseClient
```

Shared protocol distribution:

```python
from app_control_protocol import ToolCommand, ToolObservation
```

WeChat semantic distribution:

```python
from wechat_desktop_tool import WeChatDesktopTool
```

## Recommended New Code

Use the shared protocol and the backend import path:

```python
from app_control_protocol import ToolCommand
from computer_use_macos import ComputerUseClient

client = ComputerUseClient.from_config("app-control.toml")
result = client.run_command(
    ToolCommand(
        command_id="cmd_1",
        tool="macos.computer_use",
        operation="focus_app",
        input={"app": "TextEdit"},
    )
)
```

For WeChat semantics, inject an app-control client instead of importing product
or backend internals inside the WeChat package:

```python
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import WeChatDesktopTool

app_control = ComputerUseClient.from_config("app-control.toml")
wechat = WeChatDesktopTool.from_config(app_control, "app-control.toml")
wechat.focus_contact("File Transfer")
wechat.draft_message("hello")
```

Generic `computer-use-macos` helper deployments can be configured through the
shared config file or with a standalone helper config object:

```python
from computer_use_macos import ComputerUseClient, HelperConfig

app_control = ComputerUseClient(
    HelperConfig(
        helper_app_path="/Applications/Example Computer Use Helper.app",
        bundle_id="com.example.computer-use-helper",
        allowed_apps=("TextEdit",),
    )
)
```

This helper example does not imply helper parity for the selector-backed
WeChat APIs. See the coordinated `0.3.0` migration below.

## Coordinated 0.3.0 Upgrade

PyPI users upgrading from the last published `0.1.1` package set should install
all three `0.3.0` distributions together:

```bash
python -m pip install --upgrade \
  "app-control-protocol>=0.3.0,<0.4" \
  "computer-use-macos>=0.3.0,<0.4" \
  "wechat-desktop-tool>=0.3.0,<0.4"
```

Version `0.3.0` includes the coordinated selector-backed runtime prepared in
the repository's `0.2.0` source milestone and adds the packaged `wechat-use`
Agent skill. The `0.2.0` package set was not published to PyPI, so applications
do not need an intermediate upgrade.

Existing semantic WeChat method signatures remain compatible. Applications
that want Agent guidance can opt in with `load_wechat_use_skill()` or
`export_wechat_use_skill(...)`; applications that do not load the skill have no
new runtime behavior. The embedding application continues to own tool
registration, authorization, confirmation, privacy, audit, and unknown-send
recovery.

To roll back before relying on new `0.3.0` behavior, pin the complete previous
published set rather than mixing versions:

```bash
python -m pip install --force-reinstall \
  "app-control-protocol==0.1.1" \
  "computer-use-macos==0.1.1" \
  "wechat-desktop-tool==0.1.1"
```

## Historical 0.2.0 Source Milestone

Accessibility Selector Engine support was prepared in the repository as one
coordinated `0.2.0` package set, but those artifacts were not published to
PyPI. The installable successor is `0.3.0` above.

The dependency floors are intentional:

- `computer-use-macos 0.2.0` requires `app-control-protocol>=0.2.0`;
- `wechat-desktop-tool 0.2.0` requires both
  `app-control-protocol>=0.2.0` and `computer-use-macos>=0.2.0`;
- a new WeChat package with a `0.1.x` protocol or macOS backend must fail
  dependency resolution instead of reaching runtime with an incomplete
  selector contract.

`WeChatDesktopTool.from_config(...)` now reads
`computer_use.backend`. `backend="helper"` raises `ValueError` during tool
construction because helper selector parity is outside the `0.2.0` scope.
Supported WeChat modes are direct execution and a local service backed by the
direct runtime. Generic non-WeChat `computer-use-macos` helper operations are
unchanged.

## Compatibility Decision

- `computer_use_macos` is now the developer-facing backend distribution with
  its own package-local implementation.
- The old compatibility distribution published in v0.1.0 is not part of the
  active monorepo release matrix after this cleanup.
- `ComputerUseClient` is the developer-facing factory for direct, shared-config,
  and helper-config clients.
- `wechat_desktop_tool` depends only on the protocol and a compatible client
  surface. It must not import the concrete macOS backend.
- The command/observation schema is versioned as `app_control.*.v1`.

## Behavior Notes

- `submit_draft` and `send_message --submit` can have side effects. Callers must
  perform authorization and confirmation before invoking them.
- `unknown` observations should be reviewed manually before retrying commands
  that may have side effects.
- Helper mode remains appropriate for generic production computer-use
  operations because macOS permissions attach to the executing process
  identity. It is not a supported WeChat selector runtime in `0.3.0`.

## WeChat Navigation Safety Changes

- `focus_contact` now delegates to verified `open_contact`, and `send_message`
  uses that same target-switch path before drafting. Legacy search-hotkey
  configuration remains accepted but no longer drives normal contact switching.
- Search focus is now fail closed. `focus_contact` and `open_contact` return
  `failureKind="search_not_focused"` for every unknown Accessibility focus
  state and do not clear, type, or press Return.
- `open_contact` now reports duplicate semantic matches as a failed
  `contact_ambiguous` result with `status="needs_disambiguation"`; callers must
  no longer interpret that state as a successful open.
- Navigation no longer executes packaged absolute screen coordinates. It
  re-queries the mapped AX path, validates the current element frame against
  the current window, and verifies the selected state after the action.
- Contact and conversation rows that do not advertise `AXPress` no longer
  include an `actionRef` with an unexecutable `AXPress` precondition.
- Executable row actionRefs now include the exact row label in
  `preconditions.labelIn`; refs without verifiable row identity are rejected
  before backend execution.
- Contact and conversation list pagination is explicitly visible-window only.
  `nextPageToken` is always null, and non-null page tokens now return
  `pagination_not_supported` instead of replaying the first visible page.
