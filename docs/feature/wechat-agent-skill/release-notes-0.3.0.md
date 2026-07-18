# macOS Computer Use Package Suite 0.3.0

Version `0.3.0` is the next published release after `0.1.1`. It combines the
coordinated selector-backed macOS/WeChat runtime prepared in the repository's
unpublished `0.2.0` source milestone with a new packaged `wechat-use` Agent
skill.

## Agent Skill

`wechat-desktop-tool` now includes a versioned, framework-neutral skill that
teaches an Agent how to:

- inspect normalized WeChat window state;
- list visible contacts or recent conversations without conflating them;
- open an exact contact and handle ambiguous/not-found results;
- read bounded, visible message history;
- prepare a draft without sending it;
- send exact text only after application-owned authorization and confirmation;
- require manual verification instead of replay after an unknown send result.

Applications can load the immutable bundle in memory:

```python
from wechat_desktop_tool import load_wechat_use_skill

skill = load_wechat_use_skill()
registration = skill.to_dict()
```

Filesystem-based Agent runtimes can export it without overwriting an existing
application directory:

```python
from wechat_desktop_tool import export_wechat_use_skill

skill_dir = export_wechat_use_skill(".agents/skills")
```

Loading and export do not open WeChat, connect to the local service, read a
token, register tools, request permissions, or authorize a message send.

## Selector-Backed Runtime

The release also includes the coordinated changes prepared after `0.1.1`:

- bounded, profile-driven Accessibility selector resolution and collection
  extraction;
- packaged WeChat selector/control-map data with validated application-owned
  overrides;
- semantic contact, conversation, message, contact-open, draft, and send
  workflows;
- indexed root resolution, warm Accessibility workers, and query timing
  diagnostics;
- action-reference, target-app, truncation, ambiguity, and unknown-mutation
  safety checks;
- wheel/sdist content validation and clean installed-package API smoke.

## Upgrade

Install the coordinated package set together:

```bash
python -m pip install --upgrade \
  "app-control-protocol==0.3.0" \
  "computer-use-macos[accessibility]==0.3.0" \
  "wechat-desktop-tool[accessibility]==0.3.0"
```

Restart any long-running local app-control service after upgrading. No protocol
schema or application data migration is required. Existing WeChat semantic
method signatures remain compatible, and Agent-skill loading is opt-in.

Helper-backed execution remains unsupported for selector-backed WeChat
operations in `0.3.0`; direct execution and a local service backed by the
direct runtime are supported.

## Safety And Known Issues

This release remains alpha software. The previously accepted selector findings
`PRR-039`, `PRR-042`, `PRR-043`, and `PRR-044` remain open. Use only trusted
selector profile overrides and the coordinated first-party package set.

Applications remain responsible for recipient confirmation, authorization,
privacy, and audit. Do not run unattended sends for partial or potentially
duplicate contact names. Never replay a send automatically after
`submit_unknown`, `send_unverified`, `status=unknown`, or transport loss after
a possible submit.

## Verification

Publication requires source and package tests, coordinated wheel/sdist checks,
clean installed-package API smoke, isolated TestPyPI installation, exact-head
TextEdit and WeChat reports, selector-engine performance proof, Trusted
Publisher verification, and strict release-asset validation before PyPI upload.
