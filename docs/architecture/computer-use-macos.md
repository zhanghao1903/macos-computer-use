# computer-use-macos Architecture

`computer-use-macos` is the generic macOS backend for the app-control package
suite. It owns desktop primitives, local execution modes, safety policy, and
bounded macOS Accessibility access. It does not own product-specific semantics
such as WeChat contacts, chat records, or business authorization.

## Position In The Stack

The package sits below semantic tools and above macOS APIs:

```text
Application / Agent runtime
  -> semantic tools such as wechat-desktop-tool
    -> app-control-protocol ToolCommand / ToolObservation
      -> computer-use-macos
        -> macOS Accessibility, AppleScript, keyboard, mouse, local helper
```

The stable tool name is `macos.computer_use`. Public callers should build
protocol commands with `computer_use_macos.commands` or use
`ComputerUseClient` convenience methods instead of constructing backend payloads
by hand.

## Public Surfaces

The package exposes these developer-facing surfaces:

- `ComputerUseClient` / `MacOSComputerUseClient` for direct in-process use.
- Command builders such as `open_app_command`, `hotkey_command`,
  `accessibility_query_command`, and `accessibility_action_command`.
- Local Unix socket service mode through `UnixSocketCommandService` and
  `UnixSocketServiceClient`.
- Helper manifest, helper transport, and helper doctor APIs for applications
  that package a separate permission subject.
- Readiness, permission, policy, error, and observation models.
- CLI entry point `computer-use-macos`.

All command execution returns `app_control_protocol.ToolObservation`.

## Runtime Modes

### Direct Client

Direct mode runs inside the caller's Python process. It is useful for local
development, tests, and applications where the same process is granted macOS
permissions.

### Helper Transport

Helper mode lets an application talk to a separately packaged helper app. The
helper is the macOS permission subject and is configured through a helper
manifest. This is the preferred shape for production apps that need a stable
permission identity.

### Local Socket Service

Service mode exposes a local Unix socket for non-Python callers. It accepts
service envelopes, executes `ToolCommand` payloads, and returns final
observations or streamed event envelopes.

## Component Map

- `commands.py`: protocol command builders for the `macos.computer_use` tool.
- `client.py`: direct backend implementation and operation dispatch.
- `service.py`: local command service, Unix socket client, and streaming
  service envelopes.
- `transport.py`: helper transport interfaces and payload movement.
- `policy.py`: local safety policy decisions for risky desktop operations.
- `readiness.py`: permission and environment probing.
- `models.py`: public dataclasses and operation enums.
- `observations.py`: observation helpers and normalized response construction.
- `errors.py`: stable package-owned failure kinds.
- `cli.py`: developer CLI for helper, service, and request workflows.

## Command Lifecycle

1. A caller creates a `ToolCommand` with a command builder or client method.
2. The client validates operation input and applies package policy where
   relevant.
3. The backend performs the macOS action or read.
4. The result is normalized into `ToolObservation`.
5. Direct callers receive the observation immediately. Service callers receive
   a service response or event stream wrapping the same observation contract.

The backend should preserve enough evidence for diagnostics without exposing
unbounded raw UI trees by default.

## Accessibility Architecture

The package currently exposes three related capabilities:

- `observe`: coarse frontmost app/window state and optional visible text or
  Accessibility summary.
- `accessibility_query`: bounded queries over a selected Accessibility root.
- `accessibility_action`: execute an Accessibility action such as `AXPress` on
  a resolved target with optional snapshot and precondition checks.

`accessibility_query` is intentionally scoped. Callers provide:

- `root`: focused window, frontmost app, or an element path.
- `scope`: self, children, or descendants.
- `maxDepth`, `limit`, and `timeBudgetMs`: performance bounds.
- `attributes`: the AX attributes to read.
- `actions`: whether to include supported AX action names.
- `match`: optional role or attribute filters.

This shape avoids full-tree dumps and lets semantic packages ask for the next
small region they need.

## Selector Direction

The graph search problem should be solved here as a reusable Accessibility
selector engine. Product packages should not implement their own low-level graph
walkers for every app.

The intended direction is:

- A selector describes a target by role, attributes, actions, structural
  constraints, visibility, and relative anchors.
- A path such as `0/12/2/0` is treated as a cache hint, not as authority.
- The resolver validates cached paths against the selector before reuse.
- The resolver returns normalized element references and action references.
- Semantic packages own app-specific selector profiles and data mapping.

This keeps generic graph search, path validation, and action execution in
`computer-use-macos`, while keeping app semantics out of the backend.

## Safety Boundary

The package owns local desktop operation safety, including:

- blocking raw coordinate clicks unless explicitly enabled;
- separating semantic click, bounded Accessibility click, and raw coordinate
  click;
- exposing failure kinds that callers can route;
- preserving audit-friendly command and observation envelopes.

It does not decide whether a business workflow is authorized. Applications and
semantic tools must own user confirmation, contact/message authorization, and
durable audit records.

## Performance Principles

- Prefer scoped Accessibility queries over full raw dumps.
- Anchor follow-up queries to the smallest known region.
- Bound every query by depth, node limit, and time budget.
- Return diagnostics when traversal is truncated.
- Let semantic tools page list-like data instead of reading entire app state.

## Package Boundary

`computer-use-macos` must not depend on `wechat-desktop-tool`, LLM SDKs, product
apps, or application state stores. It should remain a reusable macOS
app-control backend that can serve WeChat today and other app adapters later.
