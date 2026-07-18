# WeChat Agent Skill Implementation Plan

## Plan Status

| Field | Value |
| --- | --- |
| Lifecycle phase | F3 implementation plan |
| Status | Ready for implementation |
| Requirements | [requirements.md](./requirements.md) |
| Approved design | [design.md](./design.md) |
| Implementation package | `wechat-desktop-tool` |
| Compatibility | Additive; no existing operation changes |

## Implementation Objective

Deliver the smallest coherent slice that lets a package consumer load the
versioned `wechat-use` skill into memory or export it into a filesystem-based
Agent skill root. The slice includes static skill content, public loader models
and functions, package metadata, deterministic tests, wheel/sdist proof, and
application-developer documentation.

No app-control protocol, selector, desktop operation, permission, service, or
message-send implementation will change.

## Contract Freeze

Implementation must preserve these F2 decisions:

- manifest schema: `wechat.agent-skill.v1`;
- skill name: `wechat-use`;
- initial skill version: `1.0.0`;
- public models: `WeChatAgentSkillFile`, `WeChatAgentSkill`;
- public functions: `load_wechat_use_skill`, `export_wechat_use_skill`;
- loader uses packaged resources only and performs no desktop or network work;
- export target is `<resolved-parent>/wechat-use`;
- export never overwrites or merges an existing target;
- unknown send outcomes are never retried automatically;
- no Agent/LLM SDK dependency is added.

Any change to these decisions requires updating `design.md` before code.

## Files To Add

| File | Planned change |
| --- | --- |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/agent_skill.py` | Add immutable models, manifest/path validation, resource loading, hashing, and no-overwrite export. |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/skills/wechat-use/manifest.json` | Define skill identity, version, entrypoint, and payload files. |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/skills/wechat-use/SKILL.md` | Add concise Agent workflow and safety rules. |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/skills/wechat-use/agents/openai.yaml` | Add standard display metadata without runtime coupling. |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/skills/wechat-use/references/operations.md` | Document operation selection, inputs, normalized schemas, and limits. |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/skills/wechat-use/references/recovery.md` | Document failure routing, confirmation, and no-replay recovery. |
| `packages/wechat-desktop-tool/tests/test_agent_skill.py` | Add loader, model, validation, export, safety-content, and resource-size tests. |
| `examples/wechat_agent_skill_test.py` | Show an application loading and exporting the skill without touching WeChat. |
| `docs/feature/wechat-agent-skill/implementation-notes.md` | Record the implemented slice and deviations. |
| `docs/feature/wechat-agent-skill/verification.md` | Record F5 commands and proof. |
| `docs/feature/wechat-agent-skill/merge-readiness.md` | Record F6 review and release status. |

## Files To Modify

| File | Planned change |
| --- | --- |
| `packages/wechat-desktop-tool/src/wechat_desktop_tool/__init__.py` | Export constants, models, loader, and exporter through the stable package root. |
| `packages/wechat-desktop-tool/pyproject.toml` | Include every skill asset through explicit package-data patterns. |
| `packages/wechat-desktop-tool/README.md` | Add a short package-consumer loading and export example. |
| `packages/wechat-desktop-tool/tests/test_package_boundary.py` | Assert all skill package-data patterns and no new forbidden dependency. |
| `tests/test_package_boundary.py` | Assert suite-level package-data and public-boundary expectations. |
| `tests/test_sdk_examples.py` | Execute the application-side skill example deterministically. |
| `scripts/release_preflight.py` | Require public exports and every skill file in wheel and sdist. |
| `scripts/testpypi_install_report.py` | Load the packaged skill in the installed-distribution API smoke. |
| `tests/test_release_preflight.py` | Assert the new public surface and packaged artifact checks. |
| `docs/api.md` | Document models, loader/export APIs, errors, and no-side-effect behavior. |
| `docs/agent-integration-guide.md` | Explain how an application registers operations and then loads the skill. |
| `docs/wechat-desktop-tool.md` | Add the package-specific integration contract and safety boundary. |
| `docs/feature/README.md` | Index this feature design. |
| `CHANGELOG.md` | Add the F6 `Added` release record. |

The implementation should update only files proven necessary by tests. If an
expected root test already derives its behavior from preflight constants, avoid
editing it solely to create churn.

## Implementation Slice A: Static Skill Bundle

1. Initialize `skills/wechat-use` with the standard skill structure.
2. Write a manifest containing only the approved schema fields and file list.
3. Keep `SKILL.md` under 500 lines and focused on Agent decisions.
4. Put exact operation inputs and output limitations in `operations.md`.
5. Put failure and retry routing in `recovery.md`.
6. Ensure no asset contains local paths, tokens, real contacts, real messages,
   raw AX paths, or coordinate instructions.
7. Generate or validate `agents/openai.yaml` against `SKILL.md` metadata.

Initialize the source directory with the repository-available skill creator
before replacing its placeholders:

```bash
uv run --with pyyaml python \
  /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  wechat-use \
  --path packages/wechat-desktop-tool/src/wechat_desktop_tool/skills \
  --resources references \
  --interface display_name="WeChat Use" \
  --interface short_description="Operate WeChat through registered semantic tools" \
  --interface default_prompt="Use registered WeChat semantic tools to complete the request safely."
```

Required content assertions:

- all required semantic operation names appear in the bundle;
- `includeRaw=false`, bounded limits, and visible-data limitations are explicit;
- `contact_ambiguous` and `contact_not_found` have different recovery;
- draft-only intent never reaches submit;
- `submit_unknown`, `send_unverified`, and `status=unknown` forbid replay;
- message send requires exact contact, exact content, and explicit send intent;
- skill loading is not described as tool registration or authorization.

## Implementation Slice B: Loader And Model

Create `agent_skill.py` with no imports from desktop, Agent, or LLM modules.

### Model Construction

- validate all string fields as non-empty;
- store files in manifest order as a tuple;
- reject duplicate model file paths;
- require exactly one entrypoint match;
- compute SHA-256 from UTF-8 bytes;
- return fresh immutable objects from each public load call;
- make `to_dict()` deterministic and JSON-compatible.

### Manifest Validation

Use `json.loads` and structured mapping/list checks. Do not parse JSON with
regular expressions or string splitting.

Use `PurePosixPath` plus checks against the original path text to reject:

- absolute paths;
- backslashes;
- empty path or empty segments;
- leading or trailing slash;
- `.` and `..` segments;
- duplicate paths;
- unsupported suffixes.

Internal helpers may accept an `importlib.resources.abc.Traversable` root so
temporary-directory fixtures can exercise malformed bundles without patching
global package resources. Only the zero-argument packaged loader is public.

### Export Behavior

1. Load and fully validate all source resources first.
2. Expand and resolve the caller-selected parent path.
3. Create the parent recursively.
4. Create `wechat-use` with `exist_ok=False`.
5. Write `manifest.json`, then payload files in manifest order.
6. Create nested directories only beneath the newly created target.
7. If any write fails, remove only that newly created target and re-raise.
8. Return the resolved target path.

Keep the manifest serialization deterministic with UTF-8, two-space JSON
indentation, and a final newline. Do not add an overwrite option in v1.

## Implementation Slice C: Package Surface And Artifact Gates

1. Add the public symbols to `wechat_desktop_tool.__init__` and `__all__`.
2. Add explicit skill package-data patterns to package `pyproject.toml`.
3. Update package-boundary tests to assert those patterns.
4. Add `agent_skill.py` and every skill asset to
   `EXPECTED_WHEEL_CONTENT`; sdist expectations will derive from that list.
5. Add the public symbols to `EXPECTED_PUBLIC_API`.
6. Extend the clean-installed-package smoke snippet to call the loader and
   assert schema, name, version, entrypoint, and required resources.
7. Add explicit preflight tests that fail when `agent_skill.py` or a required
   skill asset is missing from a fake wheel/sdist.

Do not change package dependencies. `json`, `hashlib`, `importlib.resources`,
`pathlib`, `shutil`, and dataclasses are all standard-library capabilities on
Python 3.11+.

## Implementation Slice D: Application Example And Stable Docs

The example must be safe to run on any supported platform:

```text
load packaged skill
  -> construct framework-neutral registration payload
  -> export into a temporary application skill root
  -> verify exported files
  -> print a privacy-safe summary
```

It must not open WeChat, read local service configuration, access a token, or
write a persistent output file.

Stable docs must answer:

- which package/import path owns the skill;
- how an application registers the existing WeChat operations;
- how it loads in-memory content or exports a standard directory;
- what the skill can and cannot teach the Agent;
- what failures the application must route;
- who owns authorization, confirmation, and audit;
- how skill versioning differs from package versioning.

The package README gets only the quick path. `docs/api.md` owns the precise API.
`docs/agent-integration-guide.md` owns runtime integration. The feature folder
retains design and proof history.

## Test Matrix

| Test | Surface | Expected proof |
| --- | --- | --- |
| Packaged load | Public API | Identity, version, entrypoint, files, and hashes are valid. |
| Model serialization | Public data model | `to_dict()` is stable and JSON-compatible. |
| Manifest negative cases | Package integrity | Every malformed schema/path/file case fails before export. |
| Existing target | Filesystem safety | Raises `FileExistsError`; sentinel content remains unchanged. |
| Partial write failure | Filesystem recovery | Only newly created incomplete target is removed. |
| Source export | Runtime integration | Exported standard directory is complete and UTF-8 exact. |
| Skill content contract | Agent behavior | Required operations, limits, safety gates, and no-replay rules are present. |
| Bundle size | Context budget | Total listed text remains below 64 KiB; `SKILL.md` below 500 lines. |
| Package boundary | Dependency safety | No Agent/LLM SDK dependency or forbidden package import. |
| SDK example | Consumer usability | Example runs without macOS or live WeChat state. |
| Wheel/sdist content | Packaging | Every source asset exists in built artifacts. |
| Clean wheel load | Distribution | Installed package loads the same name/version/resources. |
| Existing suite | Regression | Current protocol, computer-use, and WeChat tests remain green. |

## Planned Verification Commands

Targeted implementation loop:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p 'test_agent_skill.py'

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_agent_skill_test.py
```

Package and repository regression:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover -s tests

.venv/bin/python scripts/release_preflight.py
```

Skill and artifact proof:

```bash
uv run --with pyyaml python \
  /Users/zhanghao/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/skills/wechat-use

.venv/bin/python scripts/wheel_check.py --wheel-dir /tmp/wechat-agent-skill-wheels
```

The absolute `quick_validate.py` path is a developer-workstation check, not a
portable CI dependency. Repository-owned unit tests remain the enforceable CI
gate.

## Forward Test Scenarios

Use a fresh Agent context with only the proposed skill and stub semantic tools:

1. "列出我当前可见的微信联系人。"
2. "读取文件传输助手最近 30 条消息。"
3. "打开 Alex" where two verified candidates are returned.
4. "给文件传输助手写一条 hello 草稿，不要发送。"
5. "给文件传输助手发送 hello" with application confirmation available.
6. The send tool returns `send_unverified` after `sendAttempted=true`.
7. A user asks for complete historical messages or a raw coordinate click.

Success means the Agent chooses only registered semantic operations, respects
visible-data limits, asks for ambiguity/confirmation where required, and never
replays scenario 6.

Forward testing must not connect to a live WeChat client or perform a real send.

## Compatibility And Rollback

Compatibility strategy:

- only additive package-root exports are introduced;
- no existing method, command, schema, config, or dependency changes;
- consumers opt in by importing the new API;
- static resources are loaded only on explicit function calls.

Rollback strategy before release:

- revert the feature commits, package-data entries, public exports, docs, and
  release record together;
- no data migration or desktop cleanup is needed because loading has no side
  effects and export writes only to caller-selected directories.

Rollback strategy after release:

- publish a patch that corrects skill content or loader validation while
  retaining the public API;
- increment the independent skill patch version when Agent-visible content
  changes;
- do not silently replace application-exported directories; applications must
  export the new version into a clean target they control.

## Risks And Controls

| Risk | Control |
| --- | --- |
| Skill drifts from public operations | Contract tests assert operation names, limits, and failure kinds. |
| Skill is absent from wheel | Explicit package-data and preflight content checks. |
| Framework coupling enters package | Boundary scans and no new dependencies. |
| Export overwrites user changes | Exclusive target creation and sentinel test. |
| Manifest path traversal | Validate all paths before target creation. |
| Agent repeats uncertain send | Normative SKILL and recovery text plus forward test. |
| Skill consumes excessive context | 64 KiB bundle and 500-line entrypoint limits. |
| Example accidentally touches desktop | Stub-only example and subprocess test without config/token. |
| Static instructions are mistaken for authorization | Docs and skill state caller-owned policy boundary. |

## Phase Execution And Commit Plan

| Phase | Commit contents | Push gate |
| --- | --- | --- |
| F4 | skill assets, loader/models, public exports, package metadata, deterministic tests, implementation notes | Targeted and package tests pass. |
| F5 | application example, stable docs, preflight/artifact gates, verification record | Full tests, skill validation, release preflight, and wheel proof pass or exact external gap is recorded. |
| F6 | changelog, merge readiness, PR description, review remediation | Worktree scope clean, all phase commits pushed, review decision recorded. |

## F3 Exit Criteria

- Every design responsibility maps to a specific file and test.
- Implementation order keeps desktop behavior out of the change.
- Packaging proof covers source, wheel, sdist, and clean install.
- Safety and no-replay behavior have deterministic content assertions and
  forward-test scenarios.
- Compatibility, rollback, docs, release record, and phase commit boundaries
  are explicit.
- No unresolved API or protocol decision remains before F4.
