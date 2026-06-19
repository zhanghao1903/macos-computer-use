# Changelog

## 0.1.0 - Unreleased

- Add initial LLM-free `macos-computer-use` Python package.
- Add public dataclass models for readiness, results, risk, operations, and
  statuses.
- Add `MacOSComputerUseClient` with conservative `readiness`, `observe`,
  `open_app`, `click`, `type_text`, and `wait` operations.
- Add default high-risk safety policy for send/pay/delete/submit/install,
  password/security, and raw coordinate click boundaries.
- Add unit tests, CI, README, manual TextEdit smoke example, and package
  metadata.
