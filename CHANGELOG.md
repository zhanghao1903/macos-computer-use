# Changelog

## Unreleased

### Added

- Add an SDK-style WeChat contacts list example that opens WeChat, runs
  `list_contacts`, writes a JSON report, and prints contact names.
- Add `wechat.selector_profile_path` and
  `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH` so applications can inject a local
  WeChat selector profile without rebuilding `wechat-desktop-tool`.
- Add `frontmostApp` root support to scoped `accessibility_query` so selector
  profiles can inspect app-level Accessibility nodes without a focused window.
- Add an SDK-style WeChat selector-engine smoke checklist example that writes
  one JSON report for conversations, contact opening, visible messages, profile
  override checks, and expired actionRef rejection.
- Add a read-only WeChat live prerequisite probe example that reports whether
  the current desktop can expose a frontmost WeChat `AXWindow` before live
  selector-engine smoke tests run.

### Internal

- Add the internal Accessibility selector engine, packaged WeChat selector
  profile, collection extraction, and selector-backed WeChat semantic operation
  migration while keeping public selector protocol commands deferred.
- Recognize selector-engine WeChat smoke reports in strict release proof
  preflight, release proof bundles, and the GitHub Release publishing gate.
- Add a `feature-lifecycle` agent skill to manage features from requirements
  through design, implementation, review, merge, release readiness, and
  traceable release notes.
- Tighten the `feature-lifecycle` workflow so every phase requires a
  documentation carrier, a dedicated feature branch, and a phase-level
  commit/push.
- Rework the product workflow gate skill for this package suite, emphasizing
  public API contracts, developer documentation, tests, release records, and
  package publishing hygiene.

### Docs

- Add a remediation record that maps the failed Accessibility Selector Engine
  technical review items to revised design sections, implementation gates, and
  required proof.
- Record the latest live WeChat selector-engine smoke retry evidence and the
  remaining Codex-frontmost desktop blocker.
- Record the continuation live WeChat selector-engine smoke retry and separate
  the Codex-hosted probe permission result from the trusted local-service
  frontmost blocker.
- Add a documentation index, refresh README installation/API guidance, and
  expand the API reference for package roles and command builders.
- Add architecture documents for `computer-use-macos` and
  `wechat-desktop-tool`.
- Document the docs placement rules and new feature workflow, separating stable
  architecture documents from detailed feature designs.
- Add a feature design for WeChat Accessibility action APIs, including public
  response contracts, action references, performance strategy, and fake-service
  test coverage.

### Fixed

- Track the `examples/app-control.toml` template so CI release preflight checks
  pass in clean checkouts.
- Make release preflight and CI WeChat package-test checks inject all workspace
  package source roots so WeChat checks can import `computer_use_macos` in
  clean CI checkouts.
- Install CI build tooling before no-isolation wheel builds so package
  verification can import the configured `setuptools.build_meta` backend.
- Allow selector-backed WeChat row actionRefs and `open_contact` to work when
  live `AXRow` targets omit action names or reject `AXPress`, falling back to
  the selected search result instead of raw coordinates.
- Allow scoped Accessibility queries to use a longer bounded timeout and give
  WeChat contact/conversation row queries larger time budgets, avoiding
  `list_contacts` failures on slower real WeChat windows.
- Batch selector collection descendant field extraction and trim unused
  selector query attributes so WeChat contact listing no longer performs one
  Accessibility query per visible row.
- Add a WeChat control-map fast path for mapped navigation/list/message table
  AX paths so normal semantic reads avoid broad selector discovery and nested
  per-row searches.
- Avoid slow WeChat mapped navigation `AXPress` calls by skipping already-active
  tabs, using bounded frame-based coordinate clicks for mapped navigation, and
  limiting Accessibility-action fallback to 2 seconds.
- Add direct screen-coordinate hints to the WeChat navigation control map and
  stop falling back to the old selector path when mapped navigation fails, so
  navigation failures stay bounded instead of expanding into long selector
  searches.
- Reject expired or malformed WeChat `actionRef` payloads before backend or
  fallback execution, while adding `createdAt` and `expiresAt` metadata to new
  refs.

## 0.1.1 - 2026-07-02

- Add scoped `macos.computer_use/accessibility_query` for bounded macOS
  Accessibility reads.
- Update WeChat `inspect_window` to use scoped queries instead of full raw
  Accessibility tree dumps.
- Add WeChat semantic APIs for `list_contacts`, `list_conversations`,
  `open_contact`, `read_visible_messages`, and `read_contact_messages`.
- Add SDK-style WeChat window inspection example and stub tests for each
  WeChat semantic API.
- Update API documentation for the scoped query and WeChat read/action model.

## 0.1.0 - 2026-07-02

- Add initial LLM-free `macos-computer-use` Python package.
- Add public dataclass models for readiness, results, risk, operations, and
  statuses.
- Add `MacOSComputerUseClient` with conservative `readiness`, `observe`,
  `open_app`, `focus_app`, `click`, `type_text`, `press_key`, `hotkey`, and
  `wait` operations.
- Add default high-risk safety policy for send/pay/delete/submit/install,
  password/security, and raw coordinate click boundaries.
- Add unit tests, CI, README, manual TextEdit smoke example, and package
  metadata.
- Add `app-control-protocol` package with `ToolCommand`, `ToolObservation`,
  `ToolEvent`, structured errors, app-control client protocols, observers,
  logging, and shared config.
- Add packaged JSON Schema documents for protocol command, observation, event,
  error, and local service envelopes.
- Add lightweight packaged-schema payload validation for protocol and local
  service envelopes without adding a runtime JSON Schema dependency.
- Add nested `ToolError` support to failed `ToolObservation` payloads while
  preserving top-level failure fields for simpler callers.
- Add public `ServiceRequest`, `ServiceResponse`, and `ServiceEventEnvelope`
  models for local service wire envelopes, with service responses accepting the
  full structured `ToolError` shape.
- Add `computer-use-macos` migration distribution with the planned
  `computer_use_macos` import path and `computer-use-macos` CLI.
- Move the `computer-use-macos` backend implementation into the package-local
  source tree so it no longer depends on the old `macos-computer-use`
  distribution at runtime.
- Add `ComputerUseClient` factory with shared `AppControlConfig`,
  `HelperConfig`, `from_config(...)`, and `from_helper_manifest(...)` entrypoints
  for the planned developer-facing API.
- Add package-level `computer-use-macos` coverage and examples for
  `AppControlConfig`-driven `press_key` and `hotkey` protocol commands.
- Add `computer-use-macos` command builder helpers for constructing
  `macos.computer_use` protocol envelopes without hand-writing payloads.
- Add a distributable `computer_use_macos.examples.textedit_smoke` entrypoint
  with dry-run validation for installed-package smoke checks.
- Prefer the `computer-use-macos` CLI in helper, service, smoke, and release
  documentation while keeping `macos-computer-use` as the compatibility seed.
- Add explicitly enabled coordinate click support to the macOS protocol/direct
  backend while keeping raw coordinate click blocked by default.
- Add bounded Accessibility selector click support for the macOS protocol/direct
  backend.
- Add helper manifest discovery, launch, doctor, transport, and helper template
  generation.
- Add package-level CLI coverage for `computer-use-macos helper init/build`
  producing a helper `.app` skeleton.
- Add generated helper `sign.sh` and concrete `notarize.sh` scripts to make the
  developer-owned signing and notarization path explicit.
- Add Apple Events usage description metadata to generated helper app
  `Info.plist` templates.
- Add opt-in helper doctor release checks for code signature and Gatekeeper
  notarization assessment.
- Add helper template support for allowlisted semantic click and explicitly
  enabled coordinate click.
- Add helper app path manifest discovery and helper allowlist config propagation.
- Add local Unix socket service mode with `run`, `submit`, and `poll` request
  actions for non-Python callers.
- Add local service `stream` action that emits protocol events as JSON-lines
  service event envelopes before the final observation response.
- Add local service socket client API and `computer-use-macos request` CLI for
  run, submit, poll, and stream smoke checks.
- Validate local service request, response, and event envelopes against the
  packaged app-control protocol schemas.
- Add SSE frame formatting helpers for applications that wrap local service
  event envelopes in their own HTTP layer.
- Add `examples/app-control.toml` as a parse-tested editable configuration
  template for logging, macOS backend, helper, and WeChat settings.
- Add environment overrides for runtime config fields such as helper endpoint,
  helper token, macOS backend timeout, coordinate-click opt-in, and WeChat
  message limits.
- Add SDK-populated `timing.startedAt` and `timing.durationMs` to protocol
  observations from macOS and WeChat tools.
- Add a local release preflight script with optional strict external proof
  checks for helper signing/notarization, WeChat smoke, TestPyPI, and PyPI
  Trusted Publisher readiness.
- Gate PyPI publishing in the release workflow on strict external proof
  preflight using JSON proof assets attached to the GitHub Release.
- Add release preflight wheel artifact checks for package metadata, typed
  markers, packaged schemas, and CLI entry points.
- Add release preflight public API import checks and command-builder schema
  smoke checks.
- Allow release preflight to consume helper doctor JSON as helper signing and
  notarization proof.
- Allow release preflight to consume real WeChat smoke JSON while rejecting
  dry-run smoke as external proof.
- Allow release preflight to consume a clean TestPyPI install JSON report.
- Add a TestPyPI install report generator for clean-environment release proof.
- Extend the TestPyPI install report with installed-package public API and
  command-builder smoke checks.
- Add a release proof bundle generator that prepares the exact JSON assets
  consumed by the strict GitHub Release publishing workflow.
- Allow release preflight to consume a PyPI Trusted Publisher JSON report.
- Add `wechat-desktop-tool` package with protocol-first WeChat semantic
  operations, dry-run/service CLI examples, and fake app-control tests.
- Add WeChat command builder helpers for constructing protocol envelopes
  without hand-writing `ToolCommand` payloads.
- Add WeChat window verification after `open_wechat` and contact-window
  verification after `focus_contact`.
- Allow verified WeChat send-message flows to match submitted text from either
  structured `messages` or visible `textExtract`.
- Split WeChat `textExtract` into line-based visible messages with best-effort
  direction and timestamp parsing.
- Return `contact_not_found` when `focus_contact` verifies a mismatched chat
  title instead of reporting a low-confidence success, using protocol
  `not_found` status for verified misses.
- Return protocol `timeout` observations when macOS command execution exceeds
  the configured timeout.
- Add opt-in WeChat manual smoke script with dry-run, focus/draft, and
  explicit submit gating.
