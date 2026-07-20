# Implementation Plan: WeChat Tool Internal Modularization

## Status

| Field | Value |
| --- | --- |
| Feature directory | `docs/feature/wechat-tool-modularization/` |
| Branch | `codex/wechat-tool-modularization` |
| Design | [`design.md`](./design.md) |
| Current phase | F4 implementation (I7a window complete; I7b collections next) |
| Baseline source | `23d293d01245f3c46c67c5be6a6553a989d14e0a` |
| Baseline tests | 172 `wechat-desktop-tool` tests passed |
| Delivery model | One documented commit and push per implementation slice |

## Scope

### In Scope

- Add private modules under `wechat_desktop_tool` for cohesive runtime,
  operation, parsing, safety, and diagnostic responsibilities.
- Reduce `tool.py` to the supported facade and dispatcher.
- Split the monolithic `test_tool.py` along the same ownership boundaries.
- Add deterministic equivalence, import-boundary, and package-content tests.
- Update the stable package architecture map and add an `Internal` changelog
  record.

### Out Of Scope

- Any command, payload, observation, failure, timeout, selector, fallback,
  event, or safety behavior change.
- Changes to `app-control-protocol` or `computer-use-macos` production code.
- New public exports or configuration.
- Live WeChat selector tuning or performance optimization.

## Delivery Invariants

Every slice must satisfy all of the following before it is committed:

1. Update `implementation-notes.md` with moved symbols, behavior checks, test
   count, deviations, and rollback command.
2. Run the full `wechat-desktop-tool` test suite from workspace sources.
3. Run focused tests for the moved responsibility.
4. Run `git diff --check` and a Python compile check for changed modules.
5. Inspect the diff for semantic edits, import cycles, public exports, and
   accidental generated files.
6. Commit only that slice and its documentation record.
7. Push the commit before starting the next slice.

If a deterministic assertion changes, the slice is not complete. The old
implementation remains the oracle unless a separate behavior-change feature is
approved.

## Implementation Slices

| Slice | Production files | Test files | Required proof | Rollback |
| --- | --- | --- | --- | --- |
| I0 Behavior lock | None | Add `tests/_tool_test_support.py`, `test_tool_equivalence.py`, and test inventory helper | Exact command/event/result cases pass; baseline test ids retained | Revert I0 only |
| I1 Diagnostics extraction | Add `_diagnostics.py`; trim `tool.py` | Add `test_diagnostics.py`; update helper imports | Safe evidence, redaction, failures, timing, and event tests pass | Revert I1 |
| I2 Query mapping extraction | Add `_query_mapping.py`; trim `tool.py` | Add `test_query_mapping.py` | Window/navigation/node/actionRef output equivalence | Revert I2 |
| I3 Row parsing extraction | Add `_row_parsing.py`; trim `tool.py` | Add `test_row_parsing.py` | Contact/conversation/message/pagination fixtures are byte-equivalent after canonical JSON serialization | Revert I3 |
| I4 Action safety extraction | Add `_action_safety.py`; trim `tool.py` | Add `test_action_safety.py` | Existing dispatch/effect truth table and no-replay cases pass | Revert I4 |
| I5 Runtime extraction | Add `_runtime.py`; update facade construction | Add `test_runtime.py`; update profile tests | Complete ordered app-control command traces match | Revert I5 |
| I6 Action and mapped controls | Add `_action_operations.py`, `_mapped_controls.py`; trim `tool.py` | Add `test_action_operations.py`, `test_mapped_controls.py` | ActionRef, coordinate fallback, mapped navigation, and response-loss cases pass | Revert I6 |
| I7 Domain workflows | Add `_window_operations.py`, `_collection_operations.py`, `_contact_operations.py`, `_message_operations.py`; reduce `tool.py` to facade | Add domain operation tests and facade dispatch tests | All operations, failures, events, and call traces match | Revert I7 or its domain subcommit |
| I8 Test/docs/package finish | Split remaining CLI/example tests; update architecture and changelog; add size/import/package tests | Final test modules below limits | Full repository, lint/type, preflight, wheel/sdist, test-id inventory | Revert I8 |

I7 may be committed as four ordered sub-slices (`I7a` through `I7d`) when the
diff would otherwise be too large. Each sub-slice follows the same document,
test, commit, and push gates.

## Symbol Migration Map

The list below is the ownership contract. It uses current private symbol names
so extraction can be reviewed mechanically.

### `_diagnostics.py`

- Contact-query context: `_ContactQueryFailureContext`.
- Time/event helpers: `_utc_now`, `_utc_now_datetime`, `_isoformat_utc`,
  `_duration_ms`, `_with_timing`, `_event`, `_emit`, `_PhaseEventCollector`.
- Safe projections and redaction: `_safe_app_control_observation`,
  `_safe_app_control_envelope`, `_safe_accessibility_query_payload`,
  `_safe_accessibility_action_payload`, `_safe_executed_action_result`,
  `_safe_accessibility_status`, `_safe_app_control_event_summary`,
  `_redact_input_text`.
- Input/value extraction: `_coerce_command`, `_required_input`,
  `_string_input`, `_optional_string_input`, `_action_ref_input`,
  `_optional_string_from_mapping`, `_bool_input`, `_positive_int`,
  `_string_value`, `_number_value`, `_contains_any`, observation mapping and
  scalar access helpers.
- Failure construction/translation: `_failure`, `_nested_failure`,
  `_from_app_control_failure`, `_open_wechat_phase_failure`,
  `_wechat_not_ready_failure`, `_send_unverified`, selector/contact/query/input
  failure builders, and identity/login/readiness failure helpers.

Message text parsing moves to `_row_parsing.py`, and action proof extraction
moves to `_action_safety.py`, keeping `_diagnostics.py` below the module-size
limit.

### `_query_mapping.py`

- Selector resolver/query payload conversion and selector diagnostics.
- Query node/payload/snapshot helpers.
- Navigation, main-content, search-node, window, environment, and element
  normalization.
- Node path, role, label, selected state, actions, frame, geometry, target
  window, selector fallback, stable id, and actionRef construction helpers.
- Public Accessibility element normalization and focused text-field geometry.

### `_row_parsing.py`

- Mapped collection item conversion and extraction limits.
- Row synthesis, row/path association, labels, filtering, and sort keys.
- Contact rows, visible candidates, normalization, ambiguity-name inputs, and
  special-label exclusion.
- Conversation rows and parsed preview metadata.
- Visible-message extraction from query nodes, observations, raw mappings, and
  text lines; direction and hash inputs.
- Pagination token and collection continuation helpers.

### `_action_safety.py`

- ActionRef time bounds, expiry parsing/failure, target identity validation,
  and fallback selector construction.
- Native-action attempted/dispatched/effect evidence reconciliation.
- Required/optional boolean, integer, and string proof extraction.
- Consistency validation, failure classification, fallback decisions, Return
  fallback decision, and coordinate-after-action decision.

The proof constants and evidence types move with these functions. No proof key
or decision branch is renamed while moving.

### `_runtime.py`

- `WeChatToolRuntime` construction and selector-asset loading.
- App-control command construction/emission.
- Open/focus/readiness phase shared by operations.
- Target-app, open-app, query, Accessibility action, and child command input
  builders.
- Top-level, child, descendant, and bounded generic Accessibility query
  methods.
- Selector query runner and its exact phase counter semantics.

### `_action_operations.py`

- Public `execute_action` implementation.
- Node click routing.
- ActionRef execution and existing selector/coordinate fallback execution.

### `_mapped_controls.py`

- Mapped navigation press and postcondition verification.
- Mapped control execution.
- Mapped collection and conversation-target query.
- Mapped region node construction.

### Domain Operation Modules

- `_window_operations.py`: `_open_wechat`, `_inspect_window`.
- `_collection_operations.py`: `_list_contacts`, `_list_conversations`, and
  selector/control-map row listing.
- `_contact_operations.py`: `_open_contact`, visible/control-map opening,
  opened-contact verification, search focus/action/coordinate phases,
  `_focus_contact`, and the retained legacy focus implementation.
- `_message_operations.py`: `_observe_current_chat`, visible message reads,
  contact-message composition, draft, submit, and send.

The facade dispatch table imports these functions explicitly. Public wrapper
methods and their signatures remain in `tool.py`.

## Runtime Construction Detail

I5 performs constructor migration in one step:

```python
self._runtime = WeChatToolRuntime.create(app_control, config)
```

The facade exposes private read-only properties during migration:

```python
@property
def _config(self) -> WeChatDesktopConfig:
    return self._runtime.config
```

Equivalent properties are provided for existing private state names used by
tests. Operations receive `self._runtime`; no operation receives the public
facade and no low-level module imports `tool.py`.

Constructor characterization tests lock:

- default config creation;
- selector override loading;
- helper-backend exception class and exact message;
- load timing (construction, not first command);
- object identity for the app-control client and selector assets.

## Facade Dispatch Detail

`tool.py` retains `_execute`, with a typed handler table declared at module
scope. The table contains exactly the thirteen currently supported operations.
The handler lookup remains inside the existing `try` block so `TypeError` and
`ValueError` conversion does not move.

Before replacing the current `if` chain, tests lock:

- every operation routes to the same implementation;
- unsupported tool and unsupported operation failures;
- invalid input conversion;
- unexpected exception propagation;
- `run_command` and `run_stream` event behavior.

If a table changes exception scope or static typing materially, keep the
explicit `if` chain; reducing line count is not more important than behavior.

## Test Reorganization

### Shared Support

`tests/_tool_test_support.py` owns only reusable fakes and fixture builders:

- `FakeAppControl` and cross-package clients/probes;
- synthetic Accessibility query/action responses;
- canonical WeChat window tree and node builders;
- common timing and source-path helpers.

It contains no discovered test case and no production import side effects.

### Target Test Modules

| Test module | Ownership |
| --- | --- |
| `test_tool_facade.py` | Constructor, public wrappers, dispatch, timing, streams, public compatibility |
| `test_diagnostics.py` | Safe projection, redaction, input validation, semantic failure mapping |
| `test_query_mapping.py` | Query payload, window/navigation/element/actionRef normalization |
| `test_row_parsing.py` | Contact/conversation/message parsing and pagination |
| `test_action_safety.py` | Proof reconciliation, fallback gates, no-replay truth table |
| `test_runtime.py` | Exact child-command envelopes and phase events |
| `test_action_operations.py` | ActionRef and click orchestration |
| `test_mapped_controls.py` | Control-map query/action/postcondition behavior |
| `test_window_operations.py` | Open and inspect workflows |
| `test_collection_operations.py` | Contact and conversation listing |
| `test_contact_operations.py` | Open/focus/search/disambiguation workflows |
| `test_message_operations.py` | Read/draft/submit/send workflows |
| `test_tool_cli.py` | CLI and local-service client cases currently in `test_tool.py` |
| `test_tool_examples.py` | Smoke/example loader cases currently in `test_tool.py` |

Existing `test_profiles.py`, `test_contact_target_contract.py`,
`test_package_boundary.py`, and `test_agent_skill.py` remain separate.

Before and after the split, verbose discovery output is normalized to test ids
and compared. The total test count may increase from new characterization
tests, but no baseline test id may disappear without a documented one-to-one
rename.

## Equivalence Proof

### Command Trace

The fake client records each `ToolCommand`. Tests compare canonical dictionaries
for:

- command id;
- tool and operation;
- complete input payload;
- timeout;
- metadata including parent command and phase.

The comparison covers at least one success and every existing safety-relevant
failure branch for each mutating workflow.

### Observation And Event Trace

Tests compare `ToolObservation.to_dict()` and `ToolEvent.to_dict()` after a
test-only canonicalizer replaces `startedAt` and `durationMs` with fixed
sentinels. No production field is ignored. Evidence key order is irrelevant;
list and event order is significant.

### Mutation Count

Each mutation test asserts counts and ordering for `click`,
`accessibility_action`, `type_text`, `press_key`, and `hotkey`. Unknown-effect
cases assert that no later mutation is dispatched.

## Verification Commands

Use the available repository Python explicitly; do not depend on editable
install state.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  /opt/anaconda3/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p 'test_*.py'

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  /opt/anaconda3/bin/python -W error::ResourceWarning -m unittest discover \
  -s tests -p 'test_*.py'

PYTHONPATH=packages/app-control-protocol/src \
  /opt/anaconda3/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/app-control-protocol/tests -p 'test_*.py'

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  /opt/anaconda3/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/computer-use-macos/tests -p 'test_*.py'

/opt/anaconda3/bin/python -m compileall \
  packages/wechat-desktop-tool/src/wechat_desktop_tool \
  packages/wechat-desktop-tool/tests

uv run ruff check packages/wechat-desktop-tool/src packages/wechat-desktop-tool/tests
uv run mypy packages/wechat-desktop-tool/src/wechat_desktop_tool

env -u PYTHONPATH /opt/anaconda3/bin/python scripts/release_preflight.py
```

Final packaging verification uses fresh output directories outside tracked
source and runs release preflight with both wheel and sdist directories.

## Size And Dependency Gates

I8 adds deterministic repository tests that enforce:

- `tool.py` is below 1000 physical lines;
- each new private implementation module is below 1500 physical lines unless
  this feature document records an exception;
- each newly split test module is below 2500 physical lines;
- low-level modules do not import `tool.py` or operation modules;
- `wechat-desktop-tool` does not import backend/service implementation modules;
- public `__all__` and public module import paths are unchanged;
- every new private module is present in wheel and sdist contents.

The line limits are maintenance alarms, not code-format incentives. Functions
must not be compressed or obscured merely to pass them.

## Documentation And Release Record

- Append every implementation slice to `implementation-notes.md`.
- Create `verification.md` during F5 with commands, counts, durations, module
  sizes, packaging proof, and deferred live proof.
- Update `docs/architecture/wechat-desktop-tool.md` only after final module
  ownership is stable.
- Add one `CHANGELOG.md` entry under `Unreleased / Internal` stating that the
  package implementation and tests were modularized without API or behavior
  changes.
- No migration note, API guide change, or version bump is required for this
  maintenance MR.

## Rollout And Rollback

### Rollout

1. Complete and push each slice on the feature branch.
2. Run final source and built-artifact verification.
3. Perform an implementation self-review against requirements R1-R7.
4. Open a PR with the internal-maintenance changelog entry and verification
   document.
5. Require green CI before merge.
6. Include the change in the next coordinated package release.

### Rollback

- Before merge, revert the latest failing slice only.
- After merge but before release, revert the modularization PR as a unit if a
  consumer-visible difference is found.
- After release, publish a coordinated patch only if reverting source is
  insufficient for affected installations.
- Do not patch around a safety discrepancy with a retry or alternate action.

## Open Decisions

| Decision | Owner | Needed by | Default assumption |
| --- | --- | --- | --- |
| Whether I7 needs four subcommits | Implementer | Before I7 | Split by domain if the production diff exceeds a reviewable unit |
| Whether private facade aliases remain after I8 | Implementer | I8 | Remove aliases unused by production/tests; keep only compatibility needed by existing repository tests |
| Live smoke availability | Release owner | Next release | Deterministic proof is required now; live proof is refreshed in the supported macOS release environment |

No open decision permits public or behavioral change.
