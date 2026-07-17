# Accessibility Selector Contract Remediation Implementation Plan

- Status: Approved for F4 implementation
- Written: 2026-07-17
- Feature branch: `codex/accessibility-selector-engine`
- Baseline report:
  [`pr-review-macos-computer-use-3-eb543ec.md`](./pr-review-macos-computer-use-3-eb543ec.md)
- Design:
  [`design-remediation-2026-07-17.md`](./design-remediation-2026-07-17.md)
- Findings: `PRR-039`, `PRR-040`, `PRR-041`, `PRR-042`, `PRR-043`

## Scope

This plan changes internal parsing, normalization, and WeChat target-decision
behavior. It does not add public API methods, protocol fields, package
dependencies, or release versions.

## Slice R10-A: Profile Input Contract

### Production files

- `packages/computer-use-macos/src/computer_use_macos/selectors/profile.py`
  - parse `any_of` by key presence;
  - reject non-finite values in `_float`.
- `packages/computer-use-macos/src/computer_use_macos/selectors/validation.py`
  - defensively reject non-finite relation distances, constraint weights,
    confidence values, and frame members.

### Tests

- `packages/computer-use-macos/tests/test_selectors.py`
  - absent and valid non-empty `any_of` positive controls;
  - empty, `False`, `0`, empty string, mapping, and other wrong-type `any_of`;
  - mapping and TOML-derived `nan`, `inf`, and `-inf` across every float field;
  - directly constructed dataclass validation;
  - assert query runner is never called for rejected profiles.

### Exit criteria

- `PRR-040` and `PRR-041` probes no longer reproduce.
- Existing packaged profiles still parse and package tests remain green.

## Slice R10-B: Query Envelope Contract

### Production files

- `packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py`
  - make unwrapping presence-sensitive;
  - classify canonical v1, narrow legacy success, and coherent failures;
  - reject malformed schema, available/status/failure aliases, nodes,
    diagnostics, and truncation evidence;
  - retain bounded safe messages and original valid failure causes.
- `packages/computer-use-macos/src/computer_use_macos/selectors/collections.py`
  - no intended branch rewrite; verify all consumers fail closed through the
    shared normalizer.

### Tests

- `packages/computer-use-macos/tests/test_selectors.py`
  - canonical and legacy success positive controls;
  - generated-style failure positive controls;
  - the full `PRR-042` malformed/contradictory matrix;
  - malformed wrapper and conflicting duplicate metadata;
  - resolver, cache validation, relation root, and collection consumers;
  - assert failed envelopes publish no element and no cache entry.

### Exit criteria

- Every invalid envelope returns selector status `failed` with
  `selector_query_failed`.
- `PRR-042` probe exits successfully and valid compatibility controls pass.

## Slice R10-C: WeChat Contact Decision Gate

### Production files

- `packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py`
  - add one presence-sensitive target-query validator;
  - stop multi-root traversal on failed, truncated, or invalid evidence;
  - allow strategy continuation only after valid complete zero-candidate
    results;
  - validate candidate set cardinality before frame filtering;
  - require one structurally valid finite in-window frame;
  - remove zero-candidate and invalid-candidate Return behavior;
  - retain Return only behind existing definite-no-effect action proof.

### Tests

- `packages/wechat-desktop-tool/tests/test_tool.py`
  - translate the reviewer `PRR-039` mixed-root/malformed/continuation matrix;
  - translate the seven-case `PRR-043` search candidate matrix;
  - replace the unsafe offscreen-Return expectation with fail-closed behavior;
  - cover malformed nodes, diagnostics, truncation, and frame scalars;
  - cover complete-empty root/visible-query continuation positive controls;
  - run full `send_message` and assert exact operation order, no target
    mutation, no sensitive draft, and no submit for unsafe cases.

### Exit criteria

- `PRR-039` and `PRR-043` probes no longer reproduce.
- Existing valid visible-row and unique in-window search workflows pass.
- No unsafe matrix case executes click, Accessibility action, Return, message
  draft, or submit after the decision query.

## Slice R10-D: Documentation And Release Record

- `CHANGELOG.md`: record fail-closed profile/query/contact-target behavior under
  `Unreleased / Fixed`.
- `docs/api.md`: clarify that malformed selector/query evidence cannot produce
  an actionable target if the existing selector behavior section needs it.
- `docs/wechat-desktop-tool.md`: clarify unique in-window search requirement
  and removal of empty-result Return.
- `docs/feature/accessibility-selector-engine/implementation-notes.md`: map
  findings to commits and implementation details.

Public signatures remain unchanged, so no migration file is required. The
behavioral tightening is documented as a safety fix.

## Verification Matrix

Run after each slice:

1. named counterexample tests for that slice;
2. owning package full suite with `ResourceWarning` promoted to error;
3. the original reviewer probe as supplementary reproduction proof.

Run at the final exact local head:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=packages/app-control-protocol/src \
  python -W error::ResourceWarning -m unittest discover -s packages/app-control-protocol/tests -p 'test_*.py'
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -W error::ResourceWarning -m unittest discover -s packages/computer-use-macos/tests -p 'test_*.py'
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -W error::ResourceWarning -m unittest discover -s packages/wechat-desktop-tool/tests -p 'test_*.py'
```

Also run compileall with an external pycache, `scripts/release_preflight.py`,
the latest review-result validator, `git diff --check origin/main...HEAD`, all
three wheel/API-smoke checks through the root suite, and exact-head GitHub CI.

## Commit And Push Plan

1. `fix: reject malformed selector profiles` - R10-A code, tests, and notes.
2. `fix: validate selector query envelopes` - R10-B code, tests, and notes.
3. `fix: require verified WeChat contact targets` - R10-C code, tests, and
   notes.
4. `docs: record selector contract verification` - R10-D docs, changelog,
   verification, merge-readiness, and PR-description updates.

Push each completed slice to `codex/accessibility-selector-engine` before
starting the next lifecycle phase.

## Rollback And Compatibility

Each slice is independently revertible. A rollback restores permissive legacy
behavior and therefore also restores the corresponding blocker; it must not be
used as a production workaround. Valid packaged profiles, canonical query
responses, narrow legacy-success responses, and verified unique contact paths
are explicit compatibility controls.

## Manual Proof

No live WeChat mutation is required for implementation verification. After all
five findings are independently closed, a read-only selector smoke and a
separately authorized send smoke remain release-candidate proof rather than
merge-blocker substitutes.
