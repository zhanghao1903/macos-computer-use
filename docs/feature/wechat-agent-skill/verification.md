# WeChat Agent Skill Verification

## Phase Status

| Field | Value |
| --- | --- |
| Lifecycle phase | F5 verification, examples, and documentation |
| Status | Complete |
| Branch | `codex/wechat-agent-skill` |
| Requirements | [requirements.md](./requirements.md) |
| Design | [design.md](./design.md) |
| Implementation | [implementation-notes.md](./implementation-notes.md) |
| Verified | 2026-07-18 |

## Consumer Proof

`examples/wechat_agent_skill_test.py` exercises the public package contract
without opening WeChat or connecting to the local service. It:

1. loads the packaged skill with `load_wechat_use_skill()`;
2. converts the immutable model to a framework-neutral registration payload;
3. exports a complete standard `wechat-use` directory into a temporary
   application-owned parent;
4. reports only schema, version, paths, and completion status.

The example completed successfully with schema `wechat.agent-skill.v1`, skill
name `wechat-use`, version `1.0.0`, entrypoint `SKILL.md`, and the complete
manifest-declared resource list.

## Automated Verification

The following checks passed from the repository root:

| Check | Result |
| --- | --- |
| Agent skill unit tests | 12 passed |
| `wechat-desktop-tool` package suite | 171 passed |
| Root SDK and boundary suite | 132 passed |
| `app-control-protocol` package suite | 55 passed |
| `computer-use-macos` package suite | 168 passed, 1 skipped |
| Package-boundary tests for the new API | 8 passed during F4 |
| Ruff checks for changed Python files | Passed |
| Strict mypy check for `agent_skill.py` | Passed |
| Skill Creator `quick_validate.py` | `Skill is valid` |
| Offline SDK example | Passed |
| Source release preflight | Passed |
| Wheel content and clean-install smoke | Passed for all three packages |
| Sdist content preflight | Passed for all three packages |

The wheel smoke imported the public loader from a clean installed wheel and
validated the schema, name, version, entrypoint, instructions, and recovery
reference. The combined artifact preflight confirmed that `agent_skill.py`,
`manifest.json`, `SKILL.md`, `agents/openai.yaml`, and both reference files are
present in the `wechat-desktop-tool` wheel and sdist.

Build artifacts were created only below `/tmp` and are not repository files.
The first wheel-check attempt through the repository `.venv` could not run
because that environment did not contain `pip`; the isolated `uv` build
environment completed the same wheel build, install, and smoke path
successfully.

## Safety And Privacy Verification

Deterministic tests and content inspection confirm that the skill:

- routes Agents through normalized `wechat-desktop-tool` operations;
- does not contain raw Accessibility paths, coordinates, tokens, local paths,
  real contacts, or message text;
- distinguishes contact lists from recent conversations;
- limits guided contact and message reads to 30 items;
- requires exact target, exact content, and explicit send intent;
- assigns authorization, confirmation, privacy, and audit policy to the
  embedding application;
- forbids automatic replay after `submit_unknown`, `send_unverified`,
  `status=unknown`, or transport loss after a possible submit.

No isolated LLM/subagent forward evaluation was run. The available validation
surface was used for deterministic bundle, content-contract, SDK example, and
installed-artifact checks; behavioral Agent-runtime evaluation remains an
optional downstream integration test because the package intentionally does
not depend on or configure an Agent runtime.

## Manual And External Proof

No live WeChat smoke was run. Loading and exporting this static skill performs
no desktop action, and live contact or send behavior remains covered by the
existing semantic operation examples rather than this feature's loader path.

No TestPyPI installation was performed during F5. The installed-distribution
smoke code was extended and validated against locally built wheels; TestPyPI
proof remains part of a future version-release phase.

Setuptools emitted an existing deprecation warning for the TOML table form of
`project.license`. It did not affect the build or skill artifact checks and is
outside this feature's scope.

## F5 Exit Decision

F5 is complete. The public API, application example, stable developer docs,
package metadata, release preflight, clean-wheel smoke, and sdist proof agree
with the F2 contract. The feature can enter F6 review and merge-readiness work.
