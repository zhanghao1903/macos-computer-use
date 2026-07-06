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

## Slice 4A: WeChat Packaged Profile Loading

Status: implemented.

Commit scope:

- add packaged `profiles/wechat-macos.toml` under `wechat-desktop-tool`;
- add `wechat_desktop_tool.profiles.load_packaged_selector_profile`;
- include profile TOML files in package data;
- declare the `computer-use-macos` selector model dependency for
  `wechat-desktop-tool`;
- update package-boundary tests to allow only the generic selector profile
  import path while continuing to reject backend/client/service imports;
- update WeChat architecture documentation for the narrowed selector dependency
  boundary.

Public surface:

- no top-level `wechat_desktop_tool.__all__` export;
- no WeChat operation response shape change;
- no new app-control protocol command;
- package metadata now includes a runtime dependency on `computer-use-macos`
  because the packaged profile is validated through
  `computer_use_macos.selectors`.

Implemented behavior:

- packaged profile covers navigation tabs, main content, search box, chat
  panel, contacts, conversations, visible messages, and navigation press
  actions;
- profile loading uses `importlib.resources` so installed wheels can read the
  same TOML asset;
- profile validation rejects schema, reference, bound, transform, cache, and
  action-risk mistakes through the generic selector validator.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 2 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_package_boundary.py
```

Result: 5 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 80 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py \
  packages/wechat-desktop-tool/tests/test_profiles.py \
  packages/wechat-desktop-tool/tests/test_package_boundary.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

Remaining Slice 4 work:

- migrate `list_contacts`, `list_conversations`, `read_visible_messages`, and
  `open_contact` lookup internals to the packaged profile;
- add fixture-backed parity tests for migrated operations;
- map generic selector failures into WeChat failure diagnostics;
- run real WeChat smoke proof before merge readiness.

## Slice 4B: Selector-Backed WeChat Contacts Listing

Status: implemented.

Commit scope:

- add a WeChat selector query runner that bridges generic selector queries to
  existing `accessibility_query` app-control phases;
- add packaged resolver construction for the default WeChat selector profile;
- migrate `list_contacts` navigation and main-content lookup to packaged
  selectors while preserving the existing `wechat.contacts.v1` response shape;
- keep contact row parsing and `element` / `actionRef` mapping in
  `wechat-desktop-tool` so existing callers remain compatible;
- map selector lookup failures to WeChat semantic failure observations with
  normalized diagnostics;
- add parity tests for the selector-backed contacts path and selector failure
  mapping.

Public surface:

- no command builder or method signature change;
- no `wechat.contacts.v1` response field removal or rename;
- no top-level selector API export;
- internal phase evidence now includes `selectors.contacts:*` query phases for
  migrated contacts listing.

Implemented behavior:

- `list_contacts` opens/focuses WeChat as before;
- resolves `navigation.contacts` through the packaged profile;
- presses the resolved contacts navigation item through the existing validated
  `accessibility_action` path;
- resolves `regions.mainContent` through the packaged profile;
- queries visible contact rows under the resolved main content region;
- preserves contact item ids, display names, kind, action ids, element refs,
  action refs, and pagination fields;
- returns `wechat_navigation_failed` with selector diagnostics when the
  contacts navigation selector cannot be resolved.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k list_contacts
```

Result: 2 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 3 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_profiles.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 82 tests passed.

Remaining Slice 4 work:

- migrate `list_conversations`, `read_visible_messages`, and `open_contact`
  lookup internals to packaged selectors;
- add generic collection item element/actionRef support or an equivalent
  internal adapter so WeChat list APIs can consume collection extraction
  without losing action references;
- add fixture-backed parity tests for migrated operations;
- run real WeChat smoke proof before merge readiness.

## Slice 4C: Selector-Backed WeChat Conversation Listing

Status: implemented.

Commit scope:

- extend the packaged profile navigation selectors to capture `AXValue` so
  selected navigation state can be read without raw AX exposure;
- refactor contacts/conversations list APIs onto a shared selector-backed row
  listing helper;
- migrate `list_conversations` navigation and main-content lookup to packaged
  selectors while preserving the existing `wechat.conversations.v1` response
  shape;
- skip redundant navigation presses when the packaged selector evidence shows
  the target tab is already selected;
- update profile and operation tests for selector-backed conversation listing.

Public surface:

- no command builder or method signature change;
- no `wechat.contacts.v1` or `wechat.conversations.v1` response field removal
  or rename;
- no top-level selector API export;
- internal phase evidence now includes `selectors.contacts:*` query phases for
  both migrated row-list APIs.

Implemented behavior:

- `list_contacts` still switches to contacts when `AXValue` shows the contacts
  navigation item is not selected;
- `list_conversations` resolves `navigation.chats` and skips pressing it when
  already selected;
- both row-list APIs resolve `regions.mainContent` through the packaged
  profile before querying visible rows;
- existing contact and conversation parsing, item ids, action refs, and
  pagination fields remain compatible.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k list_contacts
```

Result: 2 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k list_conversations
```

Result: 1 test passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 3 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_profiles.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 82 tests passed.

Remaining Slice 4 work:

- migrate `read_visible_messages` and `open_contact` lookup internals to
  packaged selectors;
- add generic collection item element/actionRef support or an equivalent
  internal adapter so WeChat list APIs can consume collection extraction
  without losing action references;
- add fixture-backed parity tests for migrated operations;
- run real WeChat smoke proof before merge readiness.

## Slice 4D: Selector-Backed Visible Message Reading

Status: implemented.

Commit scope:

- migrate `read_visible_messages` region lookup to packaged selectors;
- resolve `regions.chatPanel` through `regions.mainContent` before querying
  message rows;
- preserve the existing `wechat.messages.v1` response shape, pagination fields,
  truncation flag, and message parsing behavior;
- update direct and composed message-reading tests for the new selector query
  sequence.

Public surface:

- no command builder or method signature change;
- no `wechat.messages.v1` response field removal or rename;
- no top-level selector API export;
- internal phase evidence now includes `selectors.messages:*` query phases for
  visible-message reads.

Implemented behavior:

- `read_visible_messages` opens/focuses WeChat as before;
- resolves `regions.chatPanel` from the packaged profile using bounded
  `accessibility_query` calls;
- queries visible message rows under the resolved chat panel instead of the
  broader main-content region;
- maps selector lookup failure to `message_region_not_found` with normalized
  selector diagnostics;
- composed flows such as `read_contact_messages` and send-message verification
  consume the selector-backed visible-message read path.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k read_visible_messages
```

Result: 2 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 82 tests passed.

Remaining Slice 4 work:

- migrate `open_contact` lookup internals to packaged selectors;
- add generic collection item element/actionRef support or an equivalent
  internal adapter so WeChat list APIs can consume collection extraction
  without losing action references;
- add fixture-backed parity tests for migrated operations;
- run real WeChat smoke proof before merge readiness.

## Slice 4E: Selector-Backed Contact Opening

Status: implemented.

Commit scope:

- migrate `open_contact` main-content and search-box lookup to packaged
  selectors;
- resolve `regions.mainContent` and `regions.searchBox` through the selector
  profile before typing search text;
- remove the dead legacy row-list helper that still contained the old
  top-level navigation/main-content lookup path;
- disable per-operation caching for `regions.mainContent` in the packaged
  profile because a new resolver is built per WeChat operation and same-operation
  cache validation added queries without cross-operation reuse;
- add parity and failure tests for selector-backed contact opening.

Public surface:

- no command builder or method signature change;
- no `wechat.open_contact.v1` response field removal or rename;
- no top-level selector API export;
- internal phase evidence now includes `selectors.open_contact:*` query phases
  for contact opening.

Implemented behavior:

- `open_contact` opens/focuses WeChat as before;
- resolves `regions.mainContent` through the packaged profile;
- resolves `regions.searchBox` through the packaged profile and focuses it
  through the existing validated click/action path;
- searches, handles disambiguation, opens a selected result, and verifies the
  chat title with the existing semantic response shape;
- maps missing search-box selector results to `search_focus_failed` with
  normalized selector diagnostics;
- keeps search-result parsing and row action execution in
  `wechat-desktop-tool`.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k open_contact
```

Result: 3 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 3 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_tool.py \
  packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 83 tests passed.

Remaining Slice 4 work:

- add generic collection item element/actionRef support or an equivalent
  internal adapter so WeChat list APIs can consume collection extraction
  without losing action references;
- add fixture-backed parity tests for generic collection extraction against
  WeChat-style rows;
- run real WeChat smoke proof before merge readiness.
