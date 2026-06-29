# Packages

This repository is moving toward a monorepo for app-control developer tools.

Current package targets:

- `app-control-protocol`: shared command, observation, event, error, and
  configuration contracts.
- `computer-use-macos`: macOS app-control backend package. It exposes the
  planned `computer_use_macos` import path and CLI with a package-local
  implementation.
- `wechat-desktop-tool`: WeChat Desktop semantic tool package built on the
  app-control protocol and a compatible app-control client.

The protocol package is intentionally independent from the concrete macOS and
WeChat implementations. Higher-level packages must depend on the protocol, not
on Taskweavn, Plato, LLM providers, or a product-specific runtime.

`wechat-desktop-tool` is intentionally a higher-level package than
`computer-use-macos`: it may consume an app-control client through the protocol
surface, but it must not import the concrete macOS backend directly.
