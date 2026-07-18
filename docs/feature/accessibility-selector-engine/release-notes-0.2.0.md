# macOS Computer Use Package Suite 0.2.0

Version `0.2.0` introduces the internal Accessibility selector engine and a
coordinated selector-backed WeChat automation stack across
`app-control-protocol`, `computer-use-macos`, and `wechat-desktop-tool`.

## Highlights

- Add bounded, profile-driven Accessibility selector resolution, collection
  extraction, cache hints, diagnostics, and action references.
- Package WeChat selector profiles while allowing validated application-owned
  profile overrides without rebuilding the package.
- Migrate WeChat contact, conversation, message, contact-open, and action paths
  to bounded queries and stable semantic responses.
- Add indexed root resolution, warm Accessibility workers, control-map paths,
  and per-step timing diagnostics so common WeChat semantic APIs remain within
  the three-second performance target in recorded live proof.
- Harden target-app identity, action evidence, truncation, stale actionRef, and
  compatibility fallback handling.
- Coordinate all package versions and dependency floors at `0.2.0`, with
  wheel/sdist content checks and isolated installed-API smoke coverage.

## Upgrade

Install the three coordinated versions together:

```bash
python -m pip install \
  "app-control-protocol==0.2.0" \
  "computer-use-macos[accessibility]==0.2.0" \
  "wechat-desktop-tool[accessibility]==0.2.0"
```

Restart any long-running local service after upgrading. Existing WeChat
semantic API method signatures remain compatible. Public generic selector
protocol commands are not included in this release.

## Safety And Known Issues

This release is alpha software. The maintainer accepted four open review
findings for publication:

- `PRR-039`: contradictory query completeness aliases are not fully rejected;
- `PRR-042`: duplicate or contradictory query wrappers can still resolve and
  cache;
- `PRR-043`: automated contact targeting does not prove exact identity and
  provenance for every partial, duplicate, or malformed candidate set;
- `PRR-044`: malformed roots or ineffective/version-skewed profile matchers can
  broaden selector overrides.

Use only trusted static profile overrides and the coordinated first-party
package set. Applications remain responsible for recipient confirmation,
authorization, audit, and keeping unattended message submission disabled for
partial or potentially duplicate contact names.

## Verification

The publication gate requires source and package tests, coordinated wheel and
sdist validation, isolated TestPyPI installation, real TextEdit and WeChat
smoke reports, an exact-source selector-engine proof, Trusted Publisher proof,
and strict release-asset validation before PyPI upload.
