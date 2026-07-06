# Accessibility Selector Engine Implementation Notes

## Slice 1: Internal Contract And Profile Validation

Status: implemented.

Commit scope:

- add package-private selector dataclasses under
  `computer_use_macos.selectors.models`;
- add profile parsing helpers under `computer_use_macos.selectors.profile`;
- add fail-closed validation under `computer_use_macos.selectors.validation`;
- add focused selector profile unit tests.

Public surface:

- no top-level `computer_use_macos` export;
- no new command builder;
- no protocol schema change;
- no CLI change;
- no stable API docs update.

Implemented design rows:

- `AccessibilitySelectorProfile`, `AppIdentity`, `SelectorDefinition`,
  `SelectorRoot`, `SelectorStep`, `MatchRule`, `AttributeMatcher`,
  `SelectorConstraint`, `ConfidencePolicy`, `CachePolicy`, `RelationRule`,
  `CollectionDefinition`, `FieldDefinition`, `PaginationPolicy`,
  `CollectionDiagnosticsPolicy`, `ElementRef`, `ElementSignature`,
  `ResolvedElement`, `SelectorDiagnostics`, `SelectorResult`,
  `CollectionResult`, `ActionDefinition`, `ActionRef`, `ActionPrecondition`,
  and `SelectorCacheEntry`;
- profile schema version validation;
- selector reference validation;
- fallback cycle validation;
- regex validation;
- bounded step validation;
- alias reference validation;
- cache signature validation policy;
- transform allowlist validation;
- action risk validation.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 11 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 62 tests passed, 1 skipped.

Remaining slices:

- implement selector resolution over bounded Accessibility queries;
- implement collection extraction;
- add WeChat packaged profile and semantic migration;
- add profile override config after packaged profile migration is proven;
- defer public selector protocol until parity tests and real WeChat smoke proof.

## Slice 2: Selector Resolver Over Bounded Queries

Status: implemented.

Commit scope:

- add `SelectorResolver` for internal selector resolution;
- add in-memory `SelectorCache`;
- add candidate matching/scoring helpers;
- add resolver diagnostics helpers;
- add fake-query tests for resolver behavior.

Public surface:

- no top-level `computer_use_macos` export;
- no new app-control protocol command;
- no new JSON Schema;
- no CLI change;
- no stable API docs update.

Implemented behavior:

- resolves selector roots from focused window, AX path, or another selector;
- converts selector steps into bounded `accessibility_query` payloads;
- applies role/action/attribute/alias hard filters;
- returns redacted `SelectorResult` evidence by default;
- detects ambiguous candidates;
- follows fallback selectors;
- stores and validates in-memory cache hints;
- falls back to fresh queries when cache validation is stale;
- reports truncation through `selector_query_truncated` diagnostics.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 17 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/*.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 68 tests passed, 1 skipped.

Remaining slices:

- implement collection extraction;
- add WeChat packaged profile and semantic migration;
- add profile override config after packaged profile migration is proven;
- defer public selector protocol until parity tests and real WeChat smoke proof.

## Slice 3: Collection Extraction

Status: implemented.

Commit scope:

- add `CollectionExtractor` for internal collection extraction;
- add allowlisted scalar field transforms;
- apply step-level role filters consistently when matching resolver and
  collection candidates;
- aggregate diagnostics across root, item, and descendant field queries;
- add fake-query tests for semantic item extraction, required-field failures,
  and visible-window pagination.

Public surface:

- no top-level `computer_use_macos` export;
- no new app-control protocol command;
- no new JSON Schema;
- no CLI change;
- no stable API docs update;
- `computer_use_macos.selectors.CollectionExtractor` remains package-internal
  MVP surface alongside `SelectorResolver`.

Implemented behavior:

- resolves a collection root through the selector resolver;
- queries item candidates relative to the resolved root with a bounded
  `limit + 1` pagination probe;
- extracts field values from self, attribute, computed, or descendant sources;
- returns normalized semantic item dictionaries instead of raw AX nodes;
- skips items missing required fields and reports partial collections when any
  valid item remains;
- fails with `selector_field_missing` when every item is rejected because
  required fields are missing;
- carries `query_count`, `node_count`, truncation state, cache state, and
  skipped-item messages in normalized diagnostics.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 21 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/*.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 72 tests passed, 1 skipped.

Remaining slices:

- add WeChat packaged profile and semantic migration;
- add profile override config after packaged profile migration is proven;
- defer public selector protocol until parity tests and real WeChat smoke proof.
