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

Helper deployments can be configured through the shared config file or with a
standalone helper config object:

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
- Helper mode is recommended for production because macOS permissions attach to
  the executing process identity.

## WeChat Navigation Safety Changes

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
