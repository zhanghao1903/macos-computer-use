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

## Slice 1B: Action Definition Safe Defaults

Status: implemented.

Commit scope:

- align `ActionDefinition.enabled_by_default` with the field matrix by making
  profile actions disabled by default;
- parse `enabled_by_default` as a strict boolean instead of relying on Python
  truthiness;
- reject profiles that enable mutating action risks by default;
- add selector-profile tests for read/focus action defaults and fail-closed
  mutating actions.

Public surface:

- no top-level `computer_use_macos` export;
- no new command builder;
- no protocol schema change;
- no CLI change;
- no stable API docs update.

Implemented behavior:

- omitted `enabled_by_default` now parses to `False`;
- `read_only` and `changes_focus` actions may explicitly set
  `enabled_by_default = true`;
- `changes_current_chat` and `submits_text` actions cannot be enabled by
  default during the internal MVP;
- non-boolean `enabled_by_default` values are rejected before validation.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 30 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/models.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/profile.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/validation.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

## Slice 1C: Profile Policy Validation Hardening

Status: implemented.

Commit scope:

- reject `PaginationPolicy.mode = "cursor"` during the internal MVP because
  cursor continuation semantics are still future-only in the design;
- require `RelationRule.max_distance` for `near` relations and require any
  provided relation distance to be positive;
- reject `pick = "best"` selectors whose confidence weights are all zero;
- add focused selector-profile tests for these fail-closed validation rules.

Public surface:

- no top-level `computer_use_macos` export;
- no new command builder;
- no protocol schema change;
- no CLI change;
- no stable API docs update.

Implemented behavior:

- visible-window and none pagination remain valid;
- cursor pagination remains represented in the model as a future design value
  but is rejected by profile validation until a public cursor lifecycle exists;
- `near` relation profiles must define a positive maximum distance before they
  can be activated;
- `pick = "best"` profiles must provide at least one scoring signal.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 34 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/validation.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

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

## Slice 2B: Selector Cache TTL Enforcement

Status: implemented.

Commit scope:

- enforce `SelectorCacheEntry.expires_at` during selector resolution;
- delete expired in-memory cache entries before running a fresh selector query;
- avoid validating expired AX paths because a TTL expiry is already a stale
  cache state;
- correct cache-validation query accounting so a single stale validation query
  is counted once.

Public surface:

- no top-level `computer_use_macos` export;
- no new app-control protocol command;
- no new JSON Schema;
- no CLI change;
- no stable API docs update.

Implemented behavior:

- non-expired cache entries still validate by AX path and signature before use;
- expired cache entries are marked through `cache_status = "stale"` and
  refreshed from the selector root;
- malformed cache expiry timestamps fail safe as expired;
- cache hit validation and fresh fallback now report accurate query counts.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 35 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

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

## Slice 3B: Collection Item Element References

Status: implemented.

Commit scope:

- add allowlisted `computed` collection field support for `elementRef`;
- return normalized item element references from collection extraction without
  exposing raw AX nodes or attribute-name dumps;
- request item actions and frame attributes when a collection asks for
  `elementRef`;
- reject unknown computed field attributes fail-closed during profile
  validation;
- add focused selector tests for normalized item element references.

Public surface:

- no top-level `computer_use_macos` export;
- no new app-control protocol command;
- no new JSON Schema;
- no CLI change;
- no stable API docs update;
- `elementRef` remains an internal selector-profile field for the MVP.

Implemented behavior:

- collection profiles can define a field with
  `source = "computed"` and `attribute = "elementRef"`;
- collection extraction returns a normalized element dictionary with
  `kind`, `axPath`, `role`, optional label, optional frame, optional actions,
  and safe boolean state fields;
- collection extraction still returns semantic item dictionaries, not raw AX
  nodes;
- unknown computed fields such as `rawNode` are rejected by profile validation.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 23 tests passed.

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

Result: 74 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 3 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 83 tests passed.

Remaining slices:

- wire WeChat list APIs to generic collection extraction using normalized
  `elementRef` while preserving WeChat action refs;
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

## Slice 4F: WeChat List APIs Use Collection Extraction

Status: implemented.

Commit scope:

- add `build_packaged_collection_extractor` as the WeChat-owned factory for the
  generic selector `CollectionExtractor`;
- add computed `elementRef` fields to the packaged `contacts` and
  `conversations` collection definitions;
- migrate `list_contacts` and `list_conversations` from hand-written row
  descendant scans to packaged collection extraction;
- map collection items back into the existing WeChat `element` and `actionRef`
  shapes without exposing raw AX attributes or `attributeNames`;
- update selector-profile and list API parity tests for the new collection
  query sequence.

Public surface:

- no command builder or method signature change;
- no `wechat.contacts.v1` or `wechat.conversations.v1` field removal or rename;
- no raw AX node, `attributeNames`, or selector engine type is exposed to API
  callers;
- `wechat-desktop-tool` still imports `computer_use_macos.selectors` only from
  `wechat_desktop_tool.profiles`.

Implemented behavior:

- list operations still open/focus WeChat and switch the requested navigation
  tab through the packaged navigation selector;
- collection extraction resolves `regions.mainContent`, queries bounded
  visible rows, and extracts configured fields;
- contacts use a descendant `AXStaticText` value as `displayName` so row labels
  with noisy structure do not leak into the public contact name;
- conversations use row `AXDescription` as `rawLabel`, then preserve the
  existing WeChat parsing for display name, preview, timestamp, pin, and mute
  flags;
- collection pagination now uses the collection visible-window state plus
  query truncation diagnostics to populate `hasMore` and `nextPageToken`.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m py_compile \
    packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py \
    packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
    packages/wechat-desktop-tool/tests/test_tool.py \
    packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 4 tests passed.

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
  python -m unittest packages/wechat-desktop-tool/tests/test_package_boundary.py
```

Result: 5 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 84 tests passed.

Remaining Slice 4 work:

- run real WeChat smoke proof for selector-backed contacts, conversations,
  visible messages, and open-contact flows;
- add profile override configuration after packaged-profile parity is proven;
- defer public selector protocol until smoke proof and release-readiness review.

## Slice 5: Selector Profile Override Configuration

Status: implemented.

Commit scope:

- add `wechat.selector_profile_path` to shared `AppControlConfig` and
  `WeChatDesktopConfig`;
- add `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH` as the environment override
  for smoke tests and CI;
- load a configured selector profile path when constructing WeChat selector
  resolvers;
- fall back to the packaged WeChat selector profile if the override file cannot
  be read, parsed, or validated;
- document the field in the protocol docs, package README files, and example
  TOML;
- add config, loader, and WeChat config propagation tests.

Public surface:

- new optional config field: `wechat.selector_profile_path`;
- new optional environment override:
  `APP_CONTROL_WECHAT_SELECTOR_PROFILE_PATH`;
- no new app-control command, WeChat command, or public selector protocol;
- invalid override files do not expose raw validation errors to WeChat API
  callers and do not block packaged-profile fallback.

Implemented behavior:

- application code can point `[wechat] selector_profile_path` at a local TOML
  selector profile without rebuilding `wechat-desktop-tool`;
- `WeChatDesktopTool.from_config(...)` carries the configured path into the
  WeChat runtime config;
- selector-backed WeChat operations use the configured profile when it validates;
- malformed TOML, unreadable files, and selector-profile validation failures
  fall back to the packaged `wechat.macos` profile.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest packages/app-control-protocol/tests/test_config.py
```

Result: 7 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Frontmost App Query Root

Status: implemented; automated verification passed.

Commit scope:

- add `frontmostApp` to direct `accessibility_query` request normalization as
  an additive query root kind;
- make the direct PyObjC query script resolve `frontmostApp` to the
  application AX element instead of requiring a focused AX window;
- support app-root query paths such as `app` and `app/0` for scoped reads;
- restrict the no-focused-window app-root bypass to exactly `app` or `app/...`
  paths so malformed paths do not skip window-root validation;
- preserve focused-window paths such as `0/12/0` for existing query and action
  behavior;
- make `SelectorResolver` pass `SelectorRoot(kind="frontmostApp")` through to
  the query runner instead of rewriting it to `focusedWindow`;
- update developer docs to distinguish focused-window paths from app-root
  read paths.

Public surface:

- additive `accessibility_query` root behavior in `computer-use-macos`;
- no new command builder, protocol command, JSON Schema, or CLI command;
- no change to `accessibility_action`, which continues to execute only
  focused-window `axPath` targets;
- generic public selector protocol commands remain deferred.

Implemented behavior:

- selector profiles can inspect app-level AX nodes when the live app has no
  focused AX window;
- app-root reads return normalized `axPath` values rooted at `app`;
- app-root `axPath` values can be used for follow-up scoped reads through
  `accessibility_query`;
- malformed `axPath` values that only start with the letters `app` no longer
  bypass the focused-window requirement;
- app-root paths are documented as read-only query paths and not action
  targets.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 51 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_package.py
```

Result: 55 tests passed, 1 skipped.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/client.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/tests/test_selectors.py \
  packages/computer-use-macos/tests/test_package.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 106 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python scripts/release_preflight.py
```

Result: passed with existing external-proof warnings.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 86 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest discover -s packages/app-control-protocol/tests
```

Result: 54 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m py_compile \
    packages/app-control-protocol/src/app_control_protocol/config.py \
    packages/wechat-desktop-tool/src/wechat_desktop_tool/models.py \
    packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py \
    packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
    packages/app-control-protocol/tests/test_config.py \
    packages/wechat-desktop-tool/tests/test_profiles.py \
    packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

```bash
git diff --check -- packages/app-control-protocol/src/app_control_protocol/config.py \
  packages/app-control-protocol/tests/test_config.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/models.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/profiles.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_profiles.py \
  packages/wechat-desktop-tool/tests/test_tool.py \
  examples/app-control.toml docs/protocol.md \
  packages/wechat-desktop-tool/README.md \
  packages/app-control-protocol/README.md
```

Result: passed.

Remaining work:

- record real macOS/WeChat smoke evidence in `verification.md`;
- attach or link the real smoke reports in the PR/MR description before merge;
- keep public `resolve_selector` / `extract_collection` protocol commands
  deferred until a separate API proposal.

## Slice 5B: Live WeChat Smoke Hardening

Status: implemented; real smoke partially proven.

Commit scope:

- prefer the frontmost running app when it matches the requested bundle id in
  Accessibility query/action/tree scripts;
- fail closed when a focused Accessibility element is not an `AXWindow`
  instead of treating the application root as a successful window root;
- make the shared WeChat open phase verify the window after `open_app` and
  retry with `focus_app` when the observation has no window title;
- focus WeChat search through the configured search hotkey plus an
  Accessibility-backed observe check instead of the old name-based click path;
- let descendant collection fields use a normalized node summary when a profile
  intentionally omits a fixed AX attribute;
- adjust the packaged conversation collection to read nested `AXStaticText` or
  `AXCell` content, matching the live WeChat conversation row structure;
- update SDK example fake-service tests for the new window verification and
  search-focus command sequence.

Public surface:

- no new public selector command;
- no WeChat semantic response schema change;
- no raw coordinate click requirement added;
- `wechat.selector_profile_path` behavior remains unchanged.

Implemented behavior:

- `inspect_window` no longer reports a false success when the matched running
  app has no focused AX window;
- live WeChat window inspection can normalize navigation tabs and regions from
  the actual focused WeChat window;
- live contact listing can extract visible contacts through packaged selector
  profiles and collection extraction;
- open-contact search focus avoids the older System Events selector that was
  brittle against WeChat's localized UI labels.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 75 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 86 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest tests.test_sdk_examples
```

Result: 6 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover -s tests
```

Result: 101 tests passed.

Real WeChat smoke evidence:

- passed: `inspect_window` normalized `wechat.window.v1` from live WeChat with
  navigation labels `chats`, `contacts`, and `favorites`, plus `mainContent`
  and `searchBox` regions;
- passed: `list_contacts(limit=30)` returned 29 visible contacts from live
  WeChat;
- incomplete: later `list_conversations`, `open_contact`, and
  `read_visible_messages` smoke attempts could not continue because the current
  desktop state reported WeChat as frontmost but exposed no focused AX window,
  even after `focus_app`.

Remaining work:

- repeat real smoke after restoring a focused WeChat chat window;
- record live proof for conversations, opening `文件传输助手`, visible messages,
  valid override loading, invalid override fallback, and stale actionRef
  precondition failure before requesting merge.

## Slice 5C: No-Focused-Window Open Phase Failure

Status: implemented; live blocker reproduced.

Commit scope:

- route `open_wechat` through the shared WeChat open phase so the explicit
  operation follows the same window verification behavior as `inspect_window`,
  `list_contacts`, `open_contact`, and message reads;
- after `open_app`, `observe`, `focus_app`, and a second `observe`, return
  `wechat_not_ready` if WeChat is frontmost but still has no focused window
  title;
- stop selector-backed operations before sending `accessibility_query` when the
  open phase proves that no focused WeChat AX window is available;
- update SDK fake-service fixtures so normal `observe` stubs include a window
  title and failure stubs expect the focus retry.

Public surface:

- no new command, config field, or protocol schema;
- existing WeChat semantic operations now return a clearer
  `wechat_not_ready` failure for the no-focused-window desktop state instead
  of surfacing the lower-level `accessibility_query_no_focused_window`.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest packages/wechat-desktop-tool/tests/test_tool.py
```

Result: 77 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 88 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest tests.test_sdk_examples
```

Result: 6 tests passed.

Live smoke evidence:

- `/private/tmp/selector-live-inspect-open-phase-fail.json` returns
  `status=not_ready`, `failureKind=wechat_not_ready`, and summary
  `WeChat is frontmost but no focused window is available.`;
- the evidence stops at `open_wechat`, `verify_wechat_window`, `focus_wechat`,
  and `verify_wechat_window_after_focus`; no selector `accessibility_query` is
  sent in this state.

Remaining work:

- restore or manually open a real WeChat chat window on the desktop, then rerun
  the remaining live smoke checklist for conversations, contact switching,
  visible messages, override behavior, and stale actionRef preconditions.

## Slice 5D: Search Hotkey And Open-Phase Window Recovery

Status: implemented.

Commit scope:

- change the default WeChat contact search hotkey from `Command+K` to the
  verified WeChat search shortcut `Command+F`;
- remove the live CLI guard that rejected `Command+F` when
  `--allow-focus-select` was explicitly enabled;
- keep the existing search-focus verification before any contact text is typed;
- when `observe` reports an empty window title during the WeChat open phase,
  verify the focused AX window through a bounded `accessibility_query` before
  failing with `wechat_not_ready`;
- update default config/docs/tests while preserving support for explicit
  custom search hotkeys.

Public surface:

- changes the default value of `[wechat].search_hotkey` to `["Command", "F"]`;
- no command builder, protocol schema, or WeChat semantic response shape change;
- live automated contact selection remains opt-in through
  `WECHAT_TOOL_ALLOW_FOCUS_SELECT=1` or `--allow-focus-select`;
- the tool still refuses to type a contact unless the focused AX element is the
  WeChat search field.

Implemented behavior:

- default config now matches the live WeChat shortcut that focuses search;
- application config and environment variables can still override the search
  hotkey;
- open-phase readiness can recover when `observe` omits `windowTitle` but
  Accessibility can prove that the focused element is an `AXWindow`;
- failed no-window states still stop before selector queries, typing, or
  message submission.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest packages/app-control-protocol/tests/test_config.py
```

Result: 7 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 84 tests passed.

## Selector Engine Corrective Slice: Multi-Step Resolution

Status: implemented.

Commit scope:

- change `SelectorResolver` so selector steps execute as a chain;
- use each matched intermediate element as the AX-path root for the next step;
- apply selector-level structural constraints only to final-step candidates;
- add focused unit coverage for a two-step selector that resolves a region
  first and then queries the table under that region.

Public surface:

- no top-level `computer_use_macos` export;
- no app-control protocol command or schema change;
- no CLI change;
- no WeChat semantic response shape change.

Implemented behavior:

- multi-step selectors now model bounded graph search as
  `root -> step[0] candidates -> step[1] under candidate paths -> final result`;
- failed intermediate steps stop the chain and return existing
  `selector_not_found` or truncation diagnostics;
- cache behavior and result schemas remain unchanged;
- this allows future and packaged profiles to express stable landmark chains
  without falling back to full-window scans.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 25 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 76 tests passed, 1 skipped.

## Selector Engine Corrective Slice: Contact Collection Fill And Search Focus Fallbacks

Status: implemented; automated verification passed; live WeChat smoke remains
blocked by search focus behavior in the current WeChat client.

Commit scope:

- make generic collection extraction apply `limit` after valid items are
  accepted, so invalid candidates can be skipped without shortening the page;
- add WeChat contact-list overscan before semantic trimming so headers and
  special rows do not consume the caller's requested contact count;
- keep WeChat row semantics in `wechat-desktop-tool` by filtering likely
  non-contact rows after collection extraction rather than adding WeChat policy
  to the generic selector engine;
- include `AXFrame` in ordinary selector resolver queries so resolved elements
  can support verified frame-derived fallback behavior;
- make Accessibility selector click preserve `AXTextArea` as a text-area role
  and match element names through `name`, `description`, `title`, or `value`
  inside a role-specific System Events collection;
- add `AXSetFocus` as a verified Accessibility action for already-resolved AX
  paths;
- focus the WeChat search box by first trying a safe Accessibility selector
  click, then trying `AXSetFocus`, then falling back to the configured search
  hotkey, then optionally a config-gated coordinate click derived from the
  resolved selector frame;
- preserve the existing focus verification before contact text is typed.

Public surface:

- no new app-control protocol command or schema field;
- `accessibility_action` now accepts `AXSetFocus` in addition to `AXPress`;
- no WeChat semantic response field removal or rename;
- no raw AX `attributeNames` exposure to WeChat API callers;
- raw coordinate clicking remains governed by the backend
  `allow_coordinate_click` setting and is not required for normal operation.

Implemented behavior:

- a collection with noisy leading candidates can still return `limit` valid
  semantic items when later visible candidates contain the required fields;
- `list_contacts(limit=N)` requests a bounded contact overscan internally, then
  returns at most `N` semantic contact rows and computes `hasMore` after
  semantic filtering;
- special WeChat rows and section headers can be skipped without exposing the
  underlying AX tree to applications;
- `open_contact` no longer depends solely on a keyboard shortcut when a
  packaged `regions.searchBox` selector is available;
- the safe selector click path fails quickly instead of scanning the entire
  WeChat window when System Events does not expose the target as a text area;
- the `AXSetFocus` path can run through the same target, snapshot, role, label,
  and action precondition checks as existing `accessibility_action` calls;
- the adapter still fails closed with `search_focus_failed` when focus
  verification does not prove that the WeChat search input is active.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 26 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 80 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 86 tests passed.

Live smoke evidence:

- `examples/wechat_contacts_recent_messages_test.py --max-contacts 1` returned
  one semantic contact after contact-row filtering and overscan;
- the same smoke still failed at `readContactMessages` because the live WeChat
  search box at `0/12/0` remained `AXFocused=false` after safe selector click,
  `AXSetFocus`, `Command+F`, `Command+K`, and multiple coordinate clicks inside
  the resolved frame;
- the failure is recorded as `search_not_focused`, and no contact text is typed
  into the current chat when focus verification fails.

## Example Corrective Slice: Listed Contact ActionRef Recent Messages

Status: implemented; automated SDK example verification passed; live WeChat
rerun still required.

Commit scope:

- update `examples/wechat_contacts_recent_messages_test.py` so contacts
  returned by `list_contacts` are opened through their row `actionRef` when
  available;
- keep the previous `read_contact_messages(contact)` search path as a fallback
  for contact items that do not include an actionRef;
- update SDK example fixtures so contact rows use realistic row heights and
  are not filtered as section/header rows;
- update SDK expectations for the current safe selector-click search focus
  path and open-phase Accessibility recovery query.

Public surface:

- no package command builder, protocol schema, or WeChat semantic API shape is
  changed;
- the example output now records `openMethod`, `openListedContact`, and
  `readVisibleMessages` when it follows a contact row actionRef;
- the example still records `readContactMessages` when it falls back to
  name-based search.

Implemented behavior:

- the recent-messages SDK example now uses the actionable data returned by
  `list_contacts` instead of immediately re-entering the search-box workflow;
- for listed contacts with actionRefs, the example runs
  `execute_action(actionRef)` and then `read_visible_messages(limit=N)`;
- the fake-service SDK test asserts that this path does not issue `type_text`
  for the contact name, which keeps the example independent of the current
  WeChat search focus blocker;
- this does not remove the merge requirement for arbitrary
  `open_contact("文件传输助手")` live proof.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_sdk_examples
```

Result: 6 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m py_compile examples/wechat_contacts_recent_messages_test.py tests/test_sdk_examples.py
```

Result: passed.

Live smoke impact:

- rerun `examples/wechat_contacts_recent_messages_test.py --max-contacts 1`
  after restoring a focused WeChat chat window; the listed-contact path should
  now exercise `execute_action` plus `read_visible_messages` before falling
  back to search;
- `open_contact` and send-message smoke still need separate real desktop proof.

## WeChat Corrective Slice: Visible Row OpenContact Fallback

Status: implemented; automated verification passed; live WeChat rerun still
required.

Commit scope:

- update `open_contact(contact)` to try visible row actionRefs before entering
  the search-box workflow;
- query only under the selector-resolved `regions.mainContent` region with a
  bounded row/static-text query;
- exact-match visible row display names before executing a row actionRef;
- keep the existing search-box path as the fallback when no visible exact match
  exists;
- update SDK send fixtures so sending to `文件传输助手` can exercise the
  actionRef path instead of typing the contact into search.

Public surface:

- no new command builder, protocol command, or schema name;
- `wechat.open_contact.v1` adds an optional `openMethod` field with values
  such as `visible_action_ref` or `search`;
- existing callers that only read `status`, `target`, `currentChat`, or
  `availableActions` remain compatible.

Implemented behavior:

- `open_contact("文件传输助手")` can open a currently visible conversation row
  by executing the row's `AXPress` actionRef;
- the visible-row path does not issue `type_text`, click raw coordinates, or
  require the WeChat search box to become focused;
- ambiguous visible exact matches return `needs_disambiguation` instead of
  clicking;
- if no exact visible row exists, the original selector-backed search path still
  runs, including focus verification before any contact text is typed.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k open_contact
```

Result: 5 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 87 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_sdk_examples
```

Result: 6 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m py_compile packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py packages/wechat-desktop-tool/tests/test_tool.py tests/test_sdk_examples.py
```

Result: passed.

Live smoke impact:

- rerun `examples/wechat_file_transfer_send_test.py` after restoring a focused
  WeChat chat window; if `文件传输助手` is visible in the conversation list, the
  smoke should use `openMethod=visible_action_ref` before drafting/submitting;
- rerun `examples/wechat_contacts_recent_messages_test.py --max-contacts 1` to
  verify listed/visible row opening followed by `read_visible_messages`;
- arbitrary contacts that are not visible still require the search-box path and
  its real desktop proof.

## WeChat Corrective Slice: ActionRef Precondition Failure Mapping

Status: implemented; automated verification passed; live WeChat stale-actionRef
proof still required.

Commit scope:

- map backend Accessibility `precondition_failed` results from
  `execute_action(actionRef)` to the semantic
  `wechat_action_precondition_failed` failure kind;
- keep unsupported-backend fallback behavior for `unsupported_operation` and
  `unsupported_accessibility_action`;
- ensure stale or invalid actionRefs do not continue into selector-click
  fallback when preconditions fail;
- preserve backend diagnostics in the action failure evidence.

Public surface:

- no new command builder, protocol command, or schema name;
- `execute_action` failure mapping is more specific for stale/precondition
  failures;
- existing successful `wechat.execute_action.v1` responses are unchanged.

Implemented behavior:

- stale actionRefs that fail backend role, label, action, or enabled
  preconditions now fail closed as `wechat_action_precondition_failed`;
- selector-click fallback remains available only when the backend does not
  support `accessibility_action`;
- a precondition failure produces no raw-coordinate or selector-click fallback.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k execute_action
```

Result: 3 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

## WeChat Corrective Slice: ActionRef Expiry Enforcement

Status: implemented; automated verification passed; live WeChat expired-actionRef
proof still required.

Commit scope:

- add `createdAt` and `expiresAt` metadata to generated WeChat actionRefs from
  `inspect_window`, available actions, contact rows, conversation rows, and
  selector-backed window models;
- keep legacy caller-supplied actionRefs without `expiresAt` executable for
  compatibility;
- reject actionRefs with expired or malformed `expiresAt` before calling the
  app-control backend or selector-click fallback;
- return `wechat_action_ref_expired` with redacted actionRef evidence and a
  recovery hint to re-run a read-model operation.

Public surface:

- no new command builder, protocol command, or schema name;
- generated `wechat.action_ref.v1` payloads now include time-bound lifecycle
  metadata;
- `execute_action` can fail with `wechat_action_ref_expired` before any desktop
  mutation is attempted;
- `WECHAT_FAILURE_KINDS` now declares both
  `wechat_action_precondition_failed` and `wechat_action_ref_expired` for
  caller-side routing.

Implemented behavior:

- generated actionRefs are short-lived recommendations instead of durable
  capabilities;
- malformed expiry values fail closed the same way as expired refs;
- stale precondition failures remain distinct as
  `wechat_action_precondition_failed`;
- backend and fallback execution are skipped when expiry validation fails.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py -k execute_action
```

Result: 5 tests passed.

```bash
python -m py_compile \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/window_model.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/errors.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 95 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python scripts/release_preflight.py
```

Result: passed with existing external-proof warnings for real desktop, TestPyPI,
and PyPI publisher checks.

## Selector Corrective Slice: Relation Anchor Matching

Status: implemented; automated verification passed; live WeChat relation-based
profile proof still required.

Commit scope:

- resolve `SelectorStep.relation.anchor_selector_id` before running the related
  selector step;
- apply frame-based relation filtering for `rightOf`, `leftOf`, `above`,
  `below`, `inside`, and `near`;
- enforce `max_distance` during matching, not only during profile validation;
- record matched relation evidence as `relation:<kind>`;
- include `AXFrame` in cache validation queries so cached selector hits can
  still expose normalized frames to downstream relation consumers;
- skip selector cache hits for selectors that contain relation rules so stale
  cached final elements cannot bypass geometry checks.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- relation matching remains internal to the selector MVP.

Implemented behavior:

- relation anchors are resolved through the same bounded selector resolver and
  contribute to selector diagnostics query/node counts;
- unresolved or ambiguous anchors fail the dependent selector before candidate
  selection;
- directional relations require the expected axis position and overlapping
  range on the opposite axis;
- `near` uses center-point distance and the already-required positive
  `max_distance`;
- relation matching rejects candidates or anchors without normalized frames.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 36 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 90 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Enabled Match Filter

Status: implemented; automated verification passed.

Commit scope:

- apply `MatchRule.enabled` as a fail-closed hard filter in selector matching;
- read enabled evidence from normalized `enabled`, top-level `AXEnabled`, or
  raw `AXEnabled`;
- reject candidates with missing enabled evidence when a profile asks for an
  enabled-state filter;
- add `AXEnabled` to selector and descendant-field collection query attributes
  so real Accessibility queries can supply enabled-state evidence;
- record `enabled` in selector evidence score breakdown when the filter is
  applied;
- add resolver and collection fixtures proving missing enabled evidence is not
  treated as disabled/enabled by Python truthiness.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- behavior remains inside the internal selector-profile MVP.

Implemented behavior:

- `enabled = true` rejects candidates without enabled-state evidence;
- `enabled = true` rejects explicitly disabled candidates;
- candidates can pass using normalized `enabled = true`, top-level
  `AXEnabled = true`, or raw `AXEnabled = true`;
- descendant collection fields can use enabled filters without relying on raw
  full-tree dumps.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 45 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/collections.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 99 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Selected Constraint Evidence

Status: implemented; automated verification passed.

Commit scope:

- apply `SelectorConstraint.kind = "selected"` using explicit selected-state
  evidence instead of Python truthiness;
- read selected evidence from normalized `selected`, top-level `AXSelected`, or
  raw `AXSelected`;
- reject candidates with missing selected evidence when a required selected
  constraint is applied;
- add `AXSelected` to selector query attributes so real Accessibility queries
  can supply selected-state evidence;
- add resolver fixtures proving `selected = false` does not match candidates
  whose selected-state evidence is missing.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- behavior remains inside the internal selector-profile MVP.

Implemented behavior:

- required `selected = false` constraints no longer treat missing selected
  evidence as false;
- raw `AXSelected = true` rejects a `selected = false` constraint;
- top-level `AXSelected = false` satisfies a `selected = false` constraint;
- matched selected constraints are recorded in selector evidence.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 46 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 100 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Structural Role Constraint Evidence

Status: implemented; automated verification passed.

Commit scope:

- add optional `accessibility_query` structural summaries:
  `includeChildRoles` and `includeDescendantRoles`;
- return normalized `childRoles` and `descendantRoles` role-name lists without
  exposing full child nodes;
- make `hasChildRole` read only direct-child role evidence;
- make `hasDescendantRole` read only descendant-role evidence;
- make role structural constraints fail closed when their required evidence is
  absent;
- make selector resolver request structural summaries only for final selector
  steps whose constraints need them;
- document the new query flags in `docs/api.md` and
  `packages/computer-use-macos/README.md`.

Public surface:

- additive `accessibility_query` query flags;
- no command builder signature change;
- no protocol schema or CLI change;
- structural summaries contain role names only, not raw Accessibility child
  nodes or app text.

Implemented behavior:

- descendant role evidence no longer satisfies `hasChildRole`;
- child role evidence no longer satisfies `hasDescendantRole` unless the query
  also supplied descendant role evidence;
- real Accessibility queries can provide structural role evidence for selector
  constraints without full tree dumps;
- selector queries keep the structural summary flags disabled unless the final
  selector constraints require them.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 47 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_package.py
```

Result: 54 tests passed, 1 skipped.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/client.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/tests/test_selectors.py \
  packages/computer-use-macos/tests/test_package.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 101 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python scripts/release_preflight.py
```

Result: passed with existing external-proof warnings for real desktop/PyPI
proof that remain outside this automated slice.

## Selector Corrective Slice: Confidence Policy Weights

Status: implemented; automated verification passed.

Commit scope:

- apply `ConfidencePolicy` weights during selector candidate scoring;
- include attribute, action, structure, geometry, and cache score categories
  only when the selector asks for that signal;
- make structural constraint scores contribute according to
  `structure_weight`;
- make relation geometry evidence contribute according to `geometry_weight`;
- keep hard filters such as role, enabled, visible, and selected as
  fail-closed filters rather than independent confidence weights;
- add resolver fixtures proving a candidate that passes hard filters can still
  fail the confidence minimum when the profile weights require structural
  evidence.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- behavior remains inside the internal selector-profile MVP.

Implemented behavior:

- `attribute_weight`, `action_weight`, `structure_weight`,
  `geometry_weight`, and `cache_weight` are no longer validation-only fields;
- optional structural constraints can raise or lower candidate confidence
  without becoming hard rejects;
- selectors without weighted scoring signals still retain the previous
  hard-filter-only confidence behavior.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 48 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 102 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Nearest-To-Anchor Pick Strategy

Status: implemented; automated verification passed; live profile proof still
required only if a packaged profile starts using this pick strategy.

Commit scope:

- make `pick = "nearestToAnchor"` fail profile validation unless the final
  selector step has a relation anchor;
- pass final-step relation anchors into resolver candidate selection;
- implement nearest-candidate selection by center-point distance to the nearest
  anchor frame;
- return `ambiguous` when two candidates are equally near;
- return `not_found` through the existing resolver path when anchor or
  candidate frames are unavailable.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- `nearestToAnchor` remains an internal selector-profile strategy.

Implemented behavior:

- profile authors can no longer activate `nearestToAnchor` without supplying
  an executable final-step relation;
- candidate order no longer decides nearest-anchor selectors when confidence
  ties;
- the strategy uses the same bounded relation-anchor resolution path and
  diagnostics query accounting as relation filtering.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 38 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/validation.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 92 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Collection Diagnostics Policy Enforcement

Status: implemented; automated verification passed.

Commit scope:

- parse remaining boolean profile fields with strict boolean validation instead
  of Python truthiness;
- reject string-like boolean values for collection fields and diagnostics
  policy entries;
- apply `CollectionDiagnosticsPolicy.include_candidate_counts` to collection
  result `node_count`;
- apply `include_skipped_count` and `include_field_failures` to collection
  failure messages;
- keep default diagnostics behavior unchanged for existing profiles.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- behavior remains inside the internal selector-profile MVP.

Implemented behavior:

- profile config such as `required = "true"` or
  `include_skipped_count = "false"` now fails closed during parsing;
- collection profiles can suppress candidate node counts while preserving query
  counts and status/failure kind;
- collection profiles can suppress skipped-item and field-failure counts from
  human diagnostic messages;
- default policy still reports safe counts such as
  `skipped 1 item(s); field failures 1`.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 40 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/profile.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/collections.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 94 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Structural Constraint Enforcement

Status: implemented; automated verification passed.

Commit scope:

- implement runtime matching for `SelectorConstraint.kind = "frameWithin"`;
- implement runtime matching for frame-based `rightOf` and `below` constraints;
- make unknown or malformed runtime constraints fail closed instead of passing;
- validate constraint value shapes during profile parsing/validation;
- add resolver fixtures proving required frame constraints reject non-matching
  candidates.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- frame constraint value shape remains internal to the selector-profile MVP:
  `{x, y, width, height}` with numeric values.

Implemented behavior:

- `frameWithin` requires the candidate frame to sit fully inside the configured
  frame;
- `rightOf` requires the candidate to be to the right of the configured frame
  and vertically overlap it;
- `below` requires the candidate to be below the configured frame and
  horizontally overlap it;
- required frame constraints now reject candidates without frames;
- invalid frame constraint values are rejected before profile activation.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 42 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/validation.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 96 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Visible Match Filter

Status: implemented; automated verification passed.

Commit scope:

- apply `MatchRule.visible` as a hard filter in selector matching;
- infer visibility from explicit `visible`, `hidden`/`AXHidden`, raw
  `AXHidden`, or positive frame dimensions when AX visibility is absent;
- add `AXHidden` to selector and collection query attributes so real
  Accessibility queries can supply hidden-state evidence;
- record `visible` in selector evidence score breakdown when the filter is
  applied;
- add resolver fixtures proving hidden and zero-sized candidates are rejected
  when `visible = true`.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- behavior remains inside the internal selector-profile MVP.

Implemented behavior:

- `visible = true` rejects explicitly hidden candidates;
- candidates without explicit visibility can still pass when they have a
  positive normalized frame;
- zero-sized candidates fail the visibility heuristic;
- candidates with no visibility evidence fail closed when a profile asks for a
  visibility filter.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 43 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/matching.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/resolver.py \
  packages/computer-use-macos/src/computer_use_macos/selectors/collections.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 97 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Selector Corrective Slice: Collection Selector Constraints

Status: implemented; automated verification passed.

Commit scope:

- apply `SelectorDefinition.constraints` when filtering collection
  `item_selector` candidates;
- apply descendant field selector constraints before extracting field values;
- request `AXSelected` only when a collection selector needs selected-state
  evidence;
- request structural summary flags such as `includeChildRoles`,
  `includeDescendantRoles`, and `includeChildrenCount` when collection
  constraints need that evidence;
- include custom step match attributes in collection query attributes so
  collection extraction does not rely on absent evidence.

Public surface:

- no top-level `computer_use_macos` export;
- no command builder, protocol command, JSON Schema, or CLI change;
- behavior remains inside the internal selector-profile MVP and packaged
  profile consumption path.

Implemented behavior:

- collection item candidates now fail closed when required structural
  constraints are missing or false;
- descendant field extraction skips nodes that match role/attribute filters but
  fail selector constraints;
- contacts/messages/conversation list profiles can use the same constraint
  language for repeated rows and nested field values as standalone selectors;
- collection query payloads stay bounded and request only the extra evidence
  required by the profile constraints.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 50 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/collections.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 104 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 6 tests passed.

## Example Corrective Slice: Selector Engine Smoke Checklist

Status: implemented; fake-service verification passed; real WeChat checklist
still requires a focused live WeChat `AXWindow`.

Commit scope:

- add `examples/wechat_selector_engine_smoke_test.py` as a consolidated live
  smoke checklist for the remaining selector-engine merge gate;
- cover `open_wechat`, `inspect_window`, `list_conversations`,
  `open_contact("文件传输助手")`, `read_visible_messages`, `list_contacts`,
  valid selector-profile override loading, invalid override fallback, and
  expired actionRef rejection in one JSON report;
- keep the checklist non-submitting: it does not draft text or call
  `submit_draft`;
- add SDK fake-service coverage proving the checklist follows selector-backed
  actionRef paths and does not type text or submit messages.

Public surface:

- no package API, protocol schema, or command builder change;
- the new root-level example is a developer smoke/proof helper for F5/F6;
- live merge readiness still depends on running the script against a real
  Accessibility-trusted WeChat desktop.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_sdk_examples -k selector_engine
```

Result: 1 test passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_sdk_examples
```

Result: 7 tests passed.

```bash
python -m py_compile \
  examples/wechat_selector_engine_smoke_test.py \
  tests/test_sdk_examples.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
```

Result: 102 tests passed.

## Historical Release Proof Slice: Selector Engine Smoke Report

Status: superseded by F4 Remediation Slice 5. This section records the original
v1 implementation; v1 is no longer accepted as strict or bundleable proof.

Commit scope:

- add `wechat_selector_engine_smoke` as a strict external proof key in
  `scripts/release_preflight.py`;
- make `--wechat-smoke-report` recognize the
  `macos_computer_use.sdk.wechat_selector_engine_smoke_test.v1` report written
  by `examples/wechat_selector_engine_smoke_test.py`;
- validate the report schema, successful summary, required checklist booleans,
  protocol-shaped WeChat observations, valid/invalid profile override checks,
  and expired actionRef failure kind before accepting the proof;
- update `scripts/release_proof_bundle.py`, `scripts/dev_check.py`, and the
  GitHub Release workflow so `wechat-selector-engine-smoke.json` is copied,
  downloaded, and passed to strict release preflight;
- update release docs and feature merge-readiness docs with the new asset name
  and proof contract.

Public surface:

- no public selector command, protocol schema, or SDK method is added;
- release tooling now treats the selector-engine checklist as a separate
  release proof from the older focus/draft and submit WeChat smokes;
- `release-proof.json` now accepts `wechat_selector_engine_smoke` as a known
  boolean key.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_release_preflight -k wechat_selector
```

Result: 2 tests passed.

```bash
python -m py_compile \
  scripts/release_preflight.py \
  scripts/release_proof_bundle.py \
  scripts/dev_check.py \
  tests/test_release_preflight.py \
  tests/test_dev_check.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_release_preflight
```

Result: 78 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest tests.test_dev_check
```

Result: 7 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
```

Result: 104 tests passed.

## Slice 5D: AXRow ActionRef And Search Result Recovery

Status: implemented; live WeChat selector-engine smoke passed.

Commit scope:

- allow scoped Accessibility queries to request `AXHidden` so selector
  visibility checks work against the local service;
- accept `AXRow` as a normalized Accessibility selector/action role in
  `computer-use-macos`;
- allow WeChat row actionRefs to be created when live `AXRow` nodes do not
  expose `AXPress` in `AXActionNames`;
- keep fixed controls such as navigation radio buttons label-validated, but do
  not add `labelIn` preconditions to `AXRow` actionRefs because WeChat often
  stores visible row text on child cells instead of the row target itself;
- when a unique WeChat search result row is found but `AXUIElementPerformAction`
  returns `accessibility_action_failed`, press the configured submit key
  (`Return` by default) to open the selected search result instead of falling
  back to raw coordinates.

Public surface:

- no public selector protocol command is added;
- no JSON Schema or stable `computer_use_macos` export is added;
- existing WeChat semantic operations keep their response shapes;
- actionRefs remain bounded and expire; risky message submission is not
  introduced.

Implemented behavior:

- `list_conversations` and `list_contacts` return row actionRefs even when
  live row nodes do not expose actions;
- expired actionRefs fail closed before backend execution;
- `open_contact("文件传输助手")` can open the target chat through the current
  visible/search result flow without requiring coordinate click;
- `read_visible_messages(limit=30)` works after the contact is opened by the
  selector-engine flow;
- the consolidated selector-engine smoke report now satisfies strict release
  preflight proof recognition.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_package.py \
  packages/computer-use-macos/tests/test_selectors.py
```

Result: 108 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest packages/wechat-desktop-tool/tests/test_tool.py \
  packages/wechat-desktop-tool/tests/test_profiles.py
```

Result: 91 tests passed.

```bash
python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/client.py \
  packages/computer-use-macos/tests/test_package.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python examples/wechat_selector_engine_smoke_test.py \
  --socket-path /private/tmp/app-control-selector-return-20260708.sock \
  --token-file ./app-control.token \
  --output /private/tmp/selector-live-selector-engine-smoke-return-20260708.json \
  --contact "文件传输助手" \
  --conversation-limit 30 \
  --contact-limit 30 \
  --message-limit 30
```

Result: passed with `conversationCount=30`, `contactCount=30`,
`messageCount=30`, and all checklist items true.

```bash
python scripts/release_preflight.py \
  --wechat-smoke-report /private/tmp/selector-live-selector-engine-smoke-return-20260708.json
```

Result: passed; `external-proof:wechat_selector_engine_smoke` verified.

## Release Preflight And CI Source Path Recovery

Status: implemented; local CI-equivalent release preflight passed without an
external `PYTHONPATH`.

Commit scope:

- add a single `WORKSPACE_SOURCE_PATHS` helper for release-preflight subprocess
  checks that run package entrypoints from source;
- make module-entrypoint checks, helper-template smoke checks, and dry-run
  smoke checks use that helper instead of target-package-only paths;
- cover the WeChat module entrypoint and both WeChat dry-run smokes with tests
  that assert the subprocess environment includes `computer-use-macos/src` as
  well as the protocol and WeChat package sources.
- update the GitHub Actions WeChat package-test step so it uses the same
  workspace source roots as the root tests;
- add a release-preflight workflow gate that fails if the CI WeChat package
  tests omit `computer-use-macos/src`.

Public surface:

- no package API, protocol schema, command builder, CLI flag, or selector
  profile change;
- this only affects local/CI release preflight behavior for source-tree
  subprocess checks.

Implemented behavior:

- CI can run `python scripts/release_preflight.py` from a clean checkout
  without relying on editable installs or ambient `PYTHONPATH`;
- CI can run `python -m unittest discover -s packages/wechat-desktop-tool/tests`
  from source without relying on editable installs;
- `wechat_desktop_tool` entrypoints can import
  `computer_use_macos.selectors` during preflight because all workspace package
  source roots are injected consistently;
- wheel/sdist install verification remains isolated from source-tree
  `PYTHONPATH` injection.

Validation evidence:

```bash
uv run pytest tests/test_release_preflight.py \
  -k "wechat_module_entrypoint or wechat_dry_run_smokes or default_preflight_passes_local_checks"
```

Result: 3 tests passed.

```bash
uv run pytest tests/test_release_preflight.py \
  -k "workflow_check_requires_wechat_test_dependency_path or default_preflight_passes_local_checks"
```

Result: 2 tests passed.

```bash
env -u PYTHONPATH python scripts/release_preflight.py
```

Result: passed; WeChat module-entrypoint, dry-run smoke, and workflow source
path checks were `OK`.

```bash
python -m py_compile \
  scripts/release_preflight.py \
  tests/test_release_preflight.py
```

Result: passed.

## Selector Collection Batch Field Extraction

Status: implemented; targeted package tests passed.

Commit scope:

- teach `CollectionExtractor` to batch one-step descendant field queries for
  visible collection items;
- group batch field candidates back to their owning row by normalized AX path
  prefix, then reuse cached field values during item extraction;
- keep the original per-item descendant query as a fallback when a required
  field is not found in the batch result;
- reduce selector resolver query attributes so `AXHidden`, `AXEnabled`, and
  `AXSelected` are requested only when the profile explicitly needs visible,
  enabled, or selected evidence;
- update selector and WeChat tests so `list_contacts`/collection extraction
  prove batched text extraction instead of per-row descendant queries.

Public surface:

- no package API, command builder, protocol schema, or WeChat response schema
  change;
- `wechat.contacts.v1` and `wechat.conversations.v1` item shapes remain
  unchanged;
- this is an internal performance optimization for selector-backed semantic
  reads.

Implemented behavior:

- contact/conversation collection extraction now performs one descendant field
  query per field instead of one query per candidate row when the field selector
  has a single step;
- missing fields still fail closed or produce partial collection results using
  the existing diagnostics behavior;
- selector navigation queries avoid expensive unused AX attributes unless the
  profile requires them.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest packages/computer-use-macos/tests/test_selectors.py
```

Result: 51 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 108 tests passed, 1 skipped.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests
```

Result: 96 tests passed.

## WeChat Control Map Fast Path

Status: implemented for list-style reads and visible-row contact opening.

Commit scope:

- add a WeChat-private control map loader under `wechat_desktop_tool`;
- extend the packaged `wechat-macos.toml` profile with `[control_map]`
  entries derived from `examples/window.json.bak` and
  `examples/window-contact.json`;
- route `list_contacts`, `list_conversations`, and `read_visible_messages`
  through mapped AX paths before falling back to selector search;
- let `open_contact` use the mapped conversations table for already visible
  conversation rows before falling back to the existing search workflow;
- fix row label extraction so `row/cell/staticText` contact names are mapped
  back to their nearest `AXRow`.

Public surface:

- no protocol schema, command builder, or top-level package API change;
- existing WeChat semantic response shapes remain compatible;
- list/message responses now include an additive `source.mode = "control_map"`
  payload when the fast path succeeds;
- applications can override the map by passing a `selector_profile_path` TOML
  that contains a `[control_map]` section, without rebuilding the package.

Implemented behavior:

- navigation actions use direct paths `0/1`, `0/2`, and `0/3` with role/action
  and label preconditions;
- contacts query the mapped table roots `0/12/2/0` and fallback candidate
  `0/11/2/0` instead of scanning the whole window or main split group;
- conversations query `0/11/1/0`;
- visible messages query `0/11/4/0/0`;
- mapped collection queries use bounded role filters and a 2200 ms query budget;
- selector-backed behavior remains the fallback when a mapped path fails or
  returns unusable nodes.

Performance intent:

- normal list-style API paths should require only `open_app`, `observe`, one
  mapped `accessibility_action` where navigation is needed, and one mapped
  `accessibility_query`;
- this replaces the previous selector-discovery and per-row field-query shape,
  which could take tens of seconds on large WeChat contact tables.

Remaining work:

- live macOS smoke must confirm wall-clock API times on the user's WeChat
  client;
- non-visible `open_contact` search still uses the existing selector/search
  fallback path and should get a separate mapped search-result slice.

## Historical WeChat Mapped Navigation Click Performance

Status: superseded by F4 Remediation Slice 1. The fixed-coordinate behavior
below is retained only as historical performance context and is not executable
in the current runtime.

Current behavior ignores packaged `screen_coordinates`, resolves the mapped AX
element, validates role/label/frame containment, uses `AXPress` or the current
validated frame center, and requires a semantic postcondition.

Problem observed in live smoke:

- `list_contacts` used the control map, but still spent about 11.9 seconds in
  `macos.computer_use/accessibility_action` while repeating `AXPress` on the
  already-selected `0/2` Contacts radio button;
- the contact table read itself completed in about 1.8 seconds, so the slow
  phase was the button action path rather than control discovery or row
  extraction.

Implemented behavior:

- mapped navigation first checks the current WeChat window title from the
  `open_wechat` verification evidence; if the target section is already active,
  the navigation phase records `already_selected` and sends no desktop action;
- when a navigation switch is still required, the tool queries only the mapped
  navigation control itself with `scope = "self"` and an 800 ms command budget;
- packaged navigation controls can provide direct `screen_coordinates` derived
  from live rawdata; when present, those coordinates are clicked first with a
  1200 ms command budget and no Accessibility frame query;
- if direct coordinates are not configured, and the frame query returns the
  expected role/label, the tool clicks the control center with a 1200 ms
  coordinate-click command;
- if coordinate click is disabled by the application policy, the tool falls
  back to `AXPress` with a 2000 ms command timeout instead of inheriting the
  parent command timeout;
- if mapped navigation still fails, the API returns `wechat_navigation_failed`
  instead of falling back to the old selector navigation path, preventing a
  50-second broad-search fallback;
- coordinate fallback is limited to control-map navigation controls and does
  not apply to message submission or arbitrary actionRefs.

Performance intent:

- already-active sections avoid the navigation click entirely;
- required navigation switches avoid the slow `AXUIElementPerformAction`
  path when coordinate click is enabled, because direct control-map coordinates
  do not require an AX frame lookup;
- when coordinate click is not enabled, the `AXPress` fallback is bounded to
  2 seconds so a slow WeChat Accessibility action cannot consume the full API
  timeout.

## WeChat Contact List Query Performance

Status: implemented as a follow-up performance fix for mapped contact listing.

Problem observed in live smoke:

- after mapped navigation was skipped successfully, `list_contacts` still took
  about 12.8 seconds end to end;
- the slow phase was `control_map_contacts_0`, whose app-control wrapper
  reported about 12.4 seconds while the inner Accessibility query diagnostics
  reported about 1.4 seconds;
- the query returned row, cell, and static-text nodes for the contact table,
  producing a larger traversal, response payload, and rawdata log record than
  the semantic API needs.

Implemented behavior:

- the packaged contacts control-map collection now queries only `AXStaticText`
  nodes under the mapped contacts root;
- the query uses a reduced attribute set: `AXRole`, `AXValue`, `AXPosition`,
  `AXSize`, and `AXFrame`;
- the contacts query disables action-name collection because static text nodes
  do not need actions;
- the WeChat extractor synthesizes `AXRow` action targets from stable contact
  text paths such as `0/12/2/0/<row>/0/<text>`, preserving the existing
  `actionRef` shape for application callers;
- known Contacts utility rows, section labels, and status text remain filtered
  before applying the caller's limit;
- the lower-level `computer-use-macos` Accessibility query script now uses
  `match.role` / `match.roleIn` as a prefilter, so nodes with non-matching roles
  avoid full attribute and action reads.

Performance intent:

- normal contact listing should return far fewer nodes and write much smaller
  rawdata records;
- `control_map_contacts_0` should spend its Accessibility work on contact names
  rather than row/cell scaffolding;
- public WeChat APIs and response shapes remain compatible while improving the
  internal query path.

## Indexed Root Resolver And Visible Row Traversal

Status: implemented as a follow-up performance fix for stable mapped paths.

Problem observed in live smoke:

- after contact reads were narrowed to `AXStaticText`, the real
  `list_contacts` API still spent about 12.1 seconds end to end;
- `control_map_contacts_0` reported about 11.8 seconds while the inner
  Accessibility query diagnostics reported about 277 ms;
- the remaining cost was consistent with resolving stable root paths and
  materializing large table child collections around the mapped
  `0/12/2/0` contact table.

Implemented behavior:

- `macos.computer_use/accessibility_query` accepts an opt-in
  `root.resolver.strategy = "attributePath"` payload for `axPath` roots;
- resolver steps can walk bounded Accessibility attributes such as
  `AXChildren`, `AXContents`, `AXRows`, and `AXVisibleRows`;
- each resolver step carries an `index` for the attribute list and an optional
  `pathIndex` so a fast attribute path can still produce the stable public
  `axPath` used by existing actionRefs;
- the query script caches AX attribute reads within a single query process, so
  root resolution, role filtering, node reads, and child traversal do not
  repeatedly ask macOS for the same attribute;
- queries can opt into `preferVisibleRows`, causing `AXTable` traversal to use
  `AXVisibleRows` when available instead of materializing all table children;
- when visible rows expose `AXIndex`, child paths preserve the table row index
  instead of using only the visible-window offset;
- query diagnostics now include `rootResolution` timing and strategy details;
- the packaged WeChat contacts control-map collection uses resolver hints for
  `0/12/2/0` and `0/11/2/0`, with the final scroll-area step reading
  `AXContents[0]`;
- the packaged contacts collection opts into visible-row traversal;
- WeChat contact extraction filters the Contacts utility row label
  `联系人` / `contacts` before applying caller limits.

Performance intent:

- stable mapped roots avoid broad tree walking and can use the cheapest known
  attribute path for the current WeChat layout;
- visible-window contact listing should avoid forcing WeChat to materialize
  hundreds or thousands of off-screen contact rows;
- the optimization is control-map driven, so a future WeChat layout change can
  be handled by updating the profile rather than changing code;
- public WeChat list-contact response contracts and actionRef shapes remain
  unchanged.

## Accessibility Query Step Timing Diagnostics

Status: implemented as a diagnostics slice for the remaining query-wrapper
latency.

Problem observed in live smoke:

- after indexed root resolution and visible-row traversal landed,
  `list_contacts` still took about 11.2 seconds end to end;
- `control_map_contacts_0` still reported about 10.6 seconds at the app-control
  command layer;
- the inner Accessibility collect diagnostics showed only 16 ms, with
  `rootResolution.strategy = "attributePath"` and `preferVisibleRows = true`;
- existing diagnostics could prove that tree traversal was fast, but could not
  explain where the remaining wrapper time was spent.

Implemented behavior:

- `macos.computer_use/accessibility_query` now returns
  `diagnostics.stepTimings` on successful responses;
- failure responses also include `diagnostics.stepTimings` when the script has
  progressed far enough to record timings;
- each timing record contains:
  - `name`: stable internal step name;
  - `startedMs`: offset from script start;
  - `durationMs`: duration since the previous recorded step;
- recorded steps include request parsing, PyObjC import, permission check,
  AppKit load, running-app selection, process identifier lookup,
  AX application creation, root request parsing, focused-window lookup,
  root resolution, window title read, collect, response metadata, response
  build, and response serialization estimate;
- existing rawdata logging automatically persists these timings because the
  raw observation stores the full Accessibility query payload.

Performance intent:

- the next real WeChat smoke can distinguish Python/PyObjC startup,
  permissions, AppKit initialization, app/window lookup, root resolution,
  collect, and response serialization costs;
- future optimization should target the largest step in
  `diagnostics.stepTimings` instead of guessing from the outer command timing.

## Persistent Accessibility Query Worker

Status: implemented as a performance slice after step timing identified Python
and PyObjC cold-start cost as the dominant delay.

Problem observed in live smoke:

- the latest real `examples/wechat-contacts-list-test.json` showed
  `listContacts.timing.durationMs = 12575`;
- the mapped contact-table query itself collected only 75 nodes and reported
  `diagnostics.durationMs = 19`;
- `diagnostics.stepTimings` showed `pyobjcImport` at about 10914 ms and
  `appKitLoad` at about 952 ms, so the remaining latency was process and
  framework startup rather than Accessibility tree traversal.

Implemented behavior:

- direct `computer-use-macos` clients created with the default runner on macOS
  start a warm `accessibility_query` worker subprocess;
- the worker imports PyObjC and preloads AppKit once, then accepts one query
  request per stdin line and returns one JSON response per stdout line;
- each worker request still executes the same bounded query script, preserving
  request normalization, allowlists, diagnostics, and failure payloads;
- custom test runners and injected probes do not start the worker, keeping unit
  tests and embedded fake transports on the original subprocess path;
- if the worker returns a non-timeout protocol failure, the client falls back to
  the existing one-shot subprocess path;
- worker timeouts terminate the worker and preserve the original timeout
  behavior instead of adding a second slow fallback attempt;
- successful and failed query payloads now include
  `diagnostics.transport.mode`, `durationMs`, and fallback details when
  applicable;
- the query script skips repeated AppKit `loadBundle` work when
  `NSWorkspace` is already available in the warm process.

Performance intent:

- long-running local service mode should pay PyObjC/AppKit startup once at
  service startup instead of once per WeChat API call;
- mapped WeChat APIs should now spend their budget on the bounded query and
  semantic extraction, not Python framework import time;
- fallback keeps the public `macos.computer_use/accessibility_query` contract
  compatible if the worker cannot start or crashes.

## File Transfer Recent Messages Workflow Correction

Status: implemented as an F4 correctness and performance follow-up.

Problem confirmed by live output:

- `read_contact_messages("文件传输助手")` reported success while
  `openContact.currentChat.title` was another conversation;
- the method then returned 30 rows from that unrelated active conversation;
- the SDK example printed only its summary, so the returned message records
  were not visible in the terminal;
- the current WeChat layout uses the `0/12` main-content branch, while the
  conversations, chat-panel, and message-list control-map entries only named
  their older `0/11` variants;
- WeChat conversation rows expose no `AXPress` action. The previous fallback
  used AppleScript `System Events click at`, which reported success without
  selecting the row.

Implemented behavior:

- the packaged control map now includes both `0/12` and `0/11` variants for
  conversations, chat panel, and visible messages;
- `open_contact` explicitly ensures that WeChat is on the Chats navigation
  section before resolving a conversation;
- visible-contact resolution runs a bounded target query under the mapped
  conversations root, matching an `AXCell` description containing the target
  contact and stopping after the first result;
- matching cells are normalized back to their parent conversation-row path so
  the existing semantic candidate model and exact display-name check remain in
  use;
- rows that do not advertise `AXPress` go directly to their AX-frame center
  coordinate, still subject to `allow_coordinate_click` policy;
- `computer-use-macos` coordinate clicks now post native Quartz mouse-down and
  mouse-up events from an internal package module instead of using AppleScript;
- every successful `open_contact` now requires the queried chat title to match
  the requested contact with at least the existing 0.9 confidence threshold;
- a missing or mismatched title returns `contact_not_found`, and composed
  `read_contact_messages` stops before reading any message rows;
- `examples/wechat_contacts_recent_messages_test.py` now performs and records
  explicit `openContact` and `readVisibleMessages` steps for one configurable
  contact, defaults to `文件传输助手` and 30 messages, and prints each returned
  message in the terminal.

Public and safety impact:

- the existing `open_contact`, `read_visible_messages`, and
  `read_contact_messages` method signatures and package response schemas remain
  compatible;
- `open_contact` no longer reports a false successful target when the active
  title is different;
- coordinate execution remains disabled unless the application configuration
  opts into `allow_coordinate_click`;
- the workflow changes focus and reads visible data only; it does not draft or
  submit messages;
- live message payloads remain local smoke evidence and are not committed.

## F6 Review Remediation: Alternate Control-Map Roots

Status: implemented after the merge-readiness review found an empty-result
fallback regression.

Review finding:

- the packaged conversations and visible-message maps now contain current
  `0/12` and older `0/11` root variants;
- the first implementation returned immediately after the first successful
  query even when that root produced no nodes;
- a layout where the first path exists but is empty and the second path holds
  the collection would therefore return an empty list or fall into the search
  workflow without trying the compatible mapped path;
- this weakened the map-variant compatibility that the profile was intended to
  provide.

Remediation:

- generic mapped collection queries now continue through configured roots
  until one returns nodes;
- targeted mapped conversation queries use the same non-empty-result rule;
- when every mapped root fails or is empty, the existing selector/search
  fallback remains available;
- regression tests cover `0/12` returning an empty query followed by a
  successful `0/11` conversation collection;
- regression tests cover the same root sequence for `open_contact`, including
  target-title verification under the matching `0/11/4` chat panel.

Public impact:

- no API, schema, failure-kind, config, or safety-policy change;
- the remediation restores the intended compatibility behavior for packaged
  control-map alternatives.

## F4 Remediation Slice 1: WeChat Navigation Safety

Status: implemented and ready for a slice-scoped commit.

Review findings closed:

- `PRR-002`: unknown Accessibility focus is fail closed before clear, type, or
  Return;
- `PRR-003`: packaged fixed-coordinate navigation is removed from execution;
  every coordinate is derived from a current AX frame contained by the current
  window, and navigation success requires a selected-state postcondition;
- `PRR-004`: two same-name mapped or search candidates return
  `contact_ambiguous` before any candidate action.

Implemented behavior:

- mapped navigation first queries the stable AX path with `limit=1` and validates
  role, localized label, frame finiteness, positive dimensions, and window
  containment;
- the query response now includes the focused window frame in both one-shot and
  persistent-worker transports;
- a real advertised `AXPress` remains preferred; coordinate fallback uses only
  the center of the just-queried AX frame and remains subject to the existing
  coordinate-click policy;
- the packaged WeChat control map no longer contains fixed navigation screen
  coordinates, and a legacy override value is ignored by execution;
- post-action navigation state is queried again and must be selected;
- mapped conversation lookup reads up to two exact candidates so ambiguity is
  observable before action;
- semantic ambiguity responses contain bounded candidate summaries and do not
  expose raw AX nodes;
- rows without advertised `AXPress` no longer publish an `AXPress` actionRef.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p test_tool.py
```

Result: 98 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p test_profiles.py
```

Result: 8 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 112 tests passed, 1 skipped.

Real moved/resized-window smoke remains deferred to the authorized F5
verification phase; no live contact action was executed in this slice.

## F4 Remediation Slice 2: Selector Cache And Query Failure Semantics

Status: implemented and ready for a slice-scoped commit.

Review findings closed:

- `PRR-006`: a cached AX path is a hint only and must satisfy the same final
  matcher, required actions, enabled/visible state, required constraints,
  relation, and frame rules as a fresh candidate;
- `PRR-007`: backend permission, timeout, and transport failures remain failed
  query outcomes, while only a successful empty query becomes
  `selector_not_found`.

Internal model changes:

- `SelectorDiagnostics` adds nullable `cause_failure_kind` and `retryable`
  fields while retaining `failure_kind="selector_query_failed"` as the generic
  selector-level category;
- `_NormalizedQueryOutcome` is a private frozen resolver object that preserves
  availability, snapshot id, bounded nodes, backend diagnostics, cause,
  bounded message, and retryability across direct, wrapped, and observation-
  wrapped query payloads;
- no selector command, protocol schema, package top-level export, or public
  selector API was added.

Implemented behavior:

- failed query outcomes stop fresh traversal, cache validation, fallback
  traversal, item extraction, batch field extraction, and per-item field
  extraction immediately;
- cache validation now builds its self-query from matcher attributes, cache key
  attributes, role/action needs, enabled/visible/selected state, structural
  constraint flags, and frame data;
- cached candidates use the same candidate builder and confidence predicate as
  fresh candidates, then retain cache-signature role and key-attribute checks;
- matcher changes, required-action loss, state changes, relation/frame changes,
  expiry, and backend failure evict the old entry; backend failure does not
  trigger a second automatic query;
- multi-step selectors bypass the single-path cache because validating only the
  final node cannot prove all intermediate predicates;
- selectors with `pick="all"` neither read nor write the single-element cache,
  preserving cold/hot result equivalence;
- collection diagnostics preserve query causes from root, item, batch, and
  field queries instead of converting them to missing fields;
- WeChat selector and collection failures map to stable top-level kinds for
  missing permission, query timeout, transport failure, or an uncategorized
  query failure; they retain the exact backend cause as `causeFailureKind`
  alongside `selector_query_failed` in bounded diagnostics and provide
  category-specific recovery guidance;
- the public WeChat failure-kind declaration now includes those stable query
  categories and the two navigation-internal failure values added in Slice 1.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -m unittest discover \
  -s packages/computer-use-macos/tests -p test_selectors.py
```

Result: 60 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p test_tool.py
```

Result: 100 tests passed.

The full `wechat-desktop-tool` test discovery also passed 113 tests, including
the public failure-kind boundary contract.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -m unittest discover -s packages/computer-use-macos/tests
```

Result: 121 tests passed, 1 skipped.

```bash
.venv/bin/python -m py_compile \
  packages/computer-use-macos/src/computer_use_macos/selectors/*.py \
  packages/computer-use-macos/tests/test_selectors.py \
  packages/wechat-desktop-tool/src/wechat_desktop_tool/tool.py \
  packages/wechat-desktop-tool/tests/test_tool.py
```

Result: passed. Ruff remains unavailable in the current environment. No live
WeChat operation was required for deterministic cache/failure semantics.

## F4 Remediation Slice 3: Collection Batch And Pagination Correctness

Status: implemented and ready for a slice-scoped commit.

Review findings closed:

- `PRR-008`: combined item/field batch depth can no longer exceed the real
  Accessibility query normalizer's maximum depth;
- `PRR-009`: an N+1 limit probe is pagination evidence rather than an
  incomplete-query failure when the accepted lookahead candidate is present.

Implemented behavior:

- `computer_use_macos.accessibility_limits` defines the package-private
  `MAX_ACCESSIBILITY_QUERY_DEPTH = 8` used by the client normalizer, selector
  profile validation, and collection batch planning;
- selector profiles now reject a step depth outside `0..8`, preventing a valid
  override from generating a request the client will reject;
- batch field depth is
  `min(MAX_ACCESSIBILITY_QUERY_DEPTH, item_depth + field_depth)`;
- packaged contacts `8+3`, conversations `6+3`, and visible messages `6+3`
  all generate depth 8 batch requests that pass the real client normalizer;
- batch values remain keyed by owning item AX path; only missing values run an
  item-rooted fallback with the field selector's own depth and limit;
- batch and fallback query counts are accumulated separately during extraction
  and their sum remains exposed through existing `diagnostics.query_count`;
- item-query truncation normalizes its reason. `limit` plus at least N+1
  accepted item candidates clears truncation, returns the first N items,
  reports `has_more=true`, and remains `resolved`;
- time-budget and other incomplete item or field queries remain `partial` when
  complete items exist and `failed` otherwise, with
  `selector_query_truncated` taking precedence over field-skip diagnostics;
- pagination `returned` remains equal to the semantic item count when rows are
  skipped.

Public surface:

- no new command, protocol schema, public selector API, or top-level package
  export;
- the maximum depth remains an internal implementation limit shared across
  package modules.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -m unittest discover \
  -s packages/computer-use-macos/tests -p test_selectors.py
```

Result: 63 tests passed.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest discover \
  -s packages/wechat-desktop-tool/tests -p test_profiles.py
```

Result: 9 tests passed. Each packaged collection executed one normalized batch
query, populated two owning-item cache entries, and used fewer field queries
than unconditional per-item extraction.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -m unittest packages/computer-use-macos/tests/test_package.py
```

Result: 62 tests passed, 1 skipped.

Full package discovery results:

- `computer-use-macos`: 125 passed, 1 skipped;
- `wechat-desktop-tool`: 114 passed.

`py_compile` and `git diff --check` passed. Ruff remains unavailable in the
current environment. No live WeChat operation was required for deterministic
depth and pagination semantics.

## F4 Remediation Slice 4: Runtime Support And Release Compatibility

Status: implemented and ready for a slice-scoped commit.

Review findings closed:

- `PRR-005`: shared WeChat configuration preserves
  `computer_use.backend`, and helper mode fails during tool construction before
  any app-control command;
- `PRR-010`: all three distributions use version `0.2.0` with coordinated
  `>=0.2.0` runtime dependency floors, clean wheel smoke verifies the installed
  set, and a local `0.1.1` dependency-only wheelhouse is rejected;
- `PRR-011`: release WeChat tests include the protocol, macOS backend, and
  WeChat source roots, and preflight detects removal of the backend path.

Implemented behavior:

- direct and direct-backed local-service WeChat construction remain supported;
- shared helper configuration raises a bounded `ValueError` before profile
  loading or transport calls; generic `computer-use-macos` helper support is
  unchanged;
- package metadata, import versions, helper bundle version metadata, package
  boundary checks, fake release artifacts, and release preflight agree on
  `0.2.0`;
- wheel verification checks selector/profile package contents, exact imported
  versions, public API smoke, and dependency-resolution rejection for mixed
  `0.2.0`/`0.1.1` sets;
- root SDK fixtures now model current AX target queries, current-window frames,
  `AXPress`, and selected-state postconditions instead of the removed fixed
  coordinate path.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest \
  tests.test_package_boundary tests.test_release_preflight
```

Result: 92 tests passed in 47.313 seconds.

A new Python 3.12.7 virtual environment under `/tmp` first reported all three
workspace imports as absent. The four `release.yml` unit-test commands then ran
with only their declared `PYTHONPATH` values:

- root tests: 114 passed in 46.922 seconds;
- `app-control-protocol`: 55 passed;
- `computer-use-macos`: 125 passed, 1 skipped;
- `wechat-desktop-tool`: 116 passed.

The first clean root run exposed three stale SDK fixtures; after the fixtures
were updated to the fail-closed AX navigation contract, the exact clean command
passed. No installed editable package was available to mask missing release
paths.

```bash
/opt/anaconda3/bin/python scripts/wheel_check.py
```

Result: passed in 9.789 seconds. The script built all three `0.2.0` wheels,
validated metadata and selector/profile contents, installed and smoke-tested
the coordinated set in a clean virtual environment, and observed pip reject
the local `0.1.1` dependency-only wheelhouse. The planned `.venv/bin/python`
invocation could not start because the uv-managed project environment contains
no `pip`, `setuptools`, or `wheel`; the system Python was used only as the build
driver.

`uv lock` was also attempted as planned, but current uv rejects the repository
root because its `pyproject.toml` contains only tool configuration and no
`[project]` or workspace table. The tracked three-line root lock therefore
remains unchanged. The untracked package-local lock is intentionally excluded;
adding a synthetic root project is outside this reviewed compatibility slice.

Documentation now records the coordinated upgrade and rollback set, helper
runtime boundary, clean source-path proof, and wheel compatibility gate. Real
helper selector smoke is intentionally excluded because helper parity is not a
supported `0.2.0` runtime.

## F4 Remediation Slice 5: Privacy-Safe Strict Release Proof

Status: implemented and ready for a slice-scoped commit.

Review findings closed:

- `PRR-001`: the selector-engine smoke writes a whitelist-only public proof v2
  by default; contact names, message content, titles, command data, service
  paths, tokens, AX paths, and operation observations remain in memory or an
  explicitly requested private debug file only;
- `PRR-012`: strict preflight and release bundling require non-zero,
  count-consistent, source-bound proof from the exact release head and reject
  v1, malformed, failed, stale, slow, unknown, or sensitive evidence.

Implemented behavior:

- `examples/wechat_selector_engine_smoke_test.py` separates live collection
  from `_build_selector_proof_v2`; `--head-sha` is mandatory unless
  `GITHUB_SHA` is set, limits are constrained to `1..30`, and the default output
  contains only the reviewed v2 schema;
- `--private-debug-output` is explicit, must differ from the public output, is
  ignored by Git, has no bundle path, and is documented as non-publishable;
- collection evidence contains structural booleans only and requires at least
  one contact, conversation, and visible message; safety evidence records the
  focus gate, target postcondition, expired ref rejection, frame-derived
  coordinate rule, raw-data absence, and sensitive scan;
- strict validation uses exact object keys and types, exact `0.2.0` package
  versions, RFC 3339 UTC time, a 40-character lowercase source SHA, count/item
  consistency, `0..3000` millisecond timings, recursive forbidden-key checks,
  absolute-path rejection, and optional sensitive canaries;
- `release-proof.json` can no longer substitute its selector boolean when
  source-bound strict mode is active; proof v1 returns false;
- `release_proof_bundle.py` validates selector proof before creating its output
  directory or invoking `_copy_asset` and remains fail closed even with
  `--allow-incomplete`;
- the release workflow passes `${{ github.sha }}`, while local `dev_check`
  resolves `GITHUB_SHA` from the current repository head;
- publishing, checklist, smoke, and reviewed design documents now describe the
  exact v2 structure and private-debug boundary.

Public and compatibility impact:

- no package import, command, protocol schema, or semantic WeChat API changed;
- the standalone release example intentionally changes its default JSON output
  from the private v1 diagnostic envelope to public proof v2;
- callers that need raw diagnostics must opt into a separate private path;
- release tooling that supplies selector proof must pass the exact source SHA.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest tests.test_sdk_examples
```

Result: 12 tests passed in 0.190 seconds.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest tests.test_release_preflight
```

Result: 90 tests passed in 42.300 seconds. Negative coverage includes zero or
inconsistent counts, missing items, count above request, request above 30,
false structural/safety evidence, non-null `failedStep`, timing above 3000 ms,
mixed versions, malformed/wrong SHA, unknown and forbidden keys, absolute
paths, sensitive canaries, v1 proof, and validation-before-copy.

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest tests.test_dev_check
```

Result: 7 tests passed in 0.018 seconds.

`scripts/release_preflight.py`, `py_compile`, and `git diff --check` passed.
The default preflight retained warnings for external desktop, TestPyPI, and
publisher evidence as expected. No real WeChat UI operation ran in this slice;
the moved/resized-window proof v2 smoke remains an explicitly authorized F5
verification step.

## F5 Release Wheel Source Isolation

Status: implemented after integration verification exposed generated bytecode
inside locally built wheels.

Problem found during F5:

- the required `compileall` check created ignored `__pycache__` trees under
  package sources;
- setuptools could reuse a stale package-local `build/lib` tree, so excluding
  discovered cache packages alone did not prevent `.pyc` files from entering a
  wheel;
- the affected wheels still imported successfully, meaning install smoke alone
  could not detect the release-content defect.

Implemented behavior:

- `wheel_check.py` copies each package into a temporary sanitized source tree
  before invoking `pip wheel`;
- generated `build`, `dist`, `*.egg-info`, `__pycache__`, `.pyc`, `.pyo`, and
  package-local `uv.lock` artifacts are excluded from that staged source;
- all three package discovery configurations explicitly exclude cache-package
  names as defense in depth;
- release preflight inspects every wheel member and fails
  `wheel-no-bytecode:<package>` when a cache directory or compiled bytecode file
  is present;
- tests prove both source staging and rejection of a deliberately contaminated
  wheel.

Verification evidence:

```bash
.venv/bin/python -m compileall -q packages examples scripts tests
/opt/anaconda3/bin/python scripts/wheel_check.py \
  --wheel-dir /tmp/accessibility-selector-f5-wheels-final
```

Result: passed in 9.10 seconds after `compileall`. The three generated `0.2.0`
wheels contained no bytecode caches, installed and passed API smoke in a clean
environment, and the mixed `0.2.0`/`0.1.1` dependency set remained rejected.
The build used temporary staged paths and did not delete or rewrite generated
files in the developer worktree.

## F5 Live Corrective Slice: AX Frame Edge Rounding

Status: implemented after the exact-head moved/resized-window smoke exposed a
one-point WeChat AX frame discrepancy; targeted tests passed and an exact-head
live rerun remains required.

Live failure evidence:

- the first proof-v2 run passed system open, readiness, `open_wechat`, and
  `inspect_window`, then failed closed at `list_conversations` with
  `wechat_navigation_failed`;
- the queried Chats control was the expected enabled `AXRadioButton`, had the
  localized `聊天` label, exposed `AXPress`, and belonged to the current WeChat
  `AXWindow`;
- WeChat reported the window left edge at `x=307` and the navigation control
  left edge at `x=306`, while the control center remained inside the window;
- strict zero-tolerance rectangle containment rejected the target before any
  press or coordinate click.

Implemented behavior:

- mapped navigation accepts at most one Accessibility point of edge rounding
  around the current window frame;
- the action center must still lie strictly within the reported window bounds;
- missing, non-finite, empty, disabled, wrong-app, or more-than-one-point
  outside frames continue to fail closed;
- packaged fixed coordinates remain ignored, and any coordinate action still
  comes only from the current validated AX frame and requires a semantic
  postcondition.

Public and compatibility impact:

- no public API, command, schema, config, or failure kind changed;
- this only prevents a valid current WeChat control from being rejected due to
  macOS AX border rounding.

Validation evidence:

```bash
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  .venv/bin/python -m unittest packages/wechat-desktop-tool/tests/test_tool.py
```

Result: 103 tests passed. Dedicated cases accept exactly one point of edge
rounding and reject a 1.1-point edge overrun alongside the existing missing,
empty, disabled, wrong-app, and far-outside frame cases.

The failed public proof and private diagnostic remain under `/private/tmp` and
are not tracked. They do not satisfy F5 because the run failed before any
collection or target-postcondition evidence was produced.

## F5 Live Corrective Slice: Bounded Focus And Visible-Row Resolution

Status: implementation and automated verification passed; exact-head live
rerun is pending because the Mac became locked during verification.

Live findings addressed:

- `list_conversations(limit=30)` returned in 2928 ms, but the collection walked
  non-visible table rows and returned off-screen frames, including the target
  row at a negative y coordinate;
- `open_contact` spent 7321 ms because it retried an off-screen coordinate,
  scanned the same conversation area again, then ran selector click,
  `AXSetFocus`, hotkey, coordinate click, and four whole-window focus checks;
- WeChat's whole-window observation exposed only a generic focused window, even
  though the known search element at `0/12/0` could be queried directly;
- live conversation rows did not expose `AXPress`, so the strict expired-ref
  proof could not legitimately source an actionRef from the conversation list;
- coordinate proof inferred frame provenance from phase names instead of an
  explicit command field.

Implemented behavior:

- conversation collections set `preferVisibleRows=true`, and the targeted
  conversation lookup uses the same AX table capability with a 450 ms budget;
- selector fallback scanning is bounded to visible rows, 40 nodes, and 350 ms;
- mapped navigation returns immediately when the current verified radio button
  is already selected, avoiding a redundant one-second AX action;
- search focus now tries the configured hotkey first and verifies the already
  resolved search element with a 500 ms `scope=self` query containing
  `AXFocused`; whole-window observation remains only for elements without an AX
  path;
- typing remains fail closed unless the exact search element is text-like, has
  a search marker, and reports `focused=true`;
- off-screen mapped and selector rows are not clicked;
- every coordinate command derived from a current AX frame records
  `coordinateSource=accessibility_frame`, and strict proof checks that field;
- expired-ref proof takes a real executable navigation actionRef from
  `inspect_window` before considering list output;
- conversation proof treats an executable actionRef or the existing semantic
  `*.open` action plus a valid current element/frame as actionable, while still
  refusing to fabricate AXPress for rows that do not expose it.

Public and compatibility impact:

- no public method, protocol schema, command input, semantic response field, or
  failure kind changed;
- list results are aligned with their documented visible-row semantics;
- the added command metadata is internal diagnostic evidence;
- fallback behavior remains bounded and fail closed when targeted focus cannot
  be proven.

Automated verification evidence:

```bash
uv run pytest tests -q
```

Result: 126 tests passed in 68.07 seconds.

```bash
uv run pytest packages/app-control-protocol/tests -q
uv run pytest packages/computer-use-macos/tests -q
uv run pytest packages/wechat-desktop-tool/tests -q
```

Results: 55, 125, and 119 tests passed respectively. New cases cover an
already-selected navigation node under a generic window title, visible-row
query configuration, targeted focused/blurred/unknown search states, explicit
coordinate provenance, inspected-navigation expired refs, and semantic open
proof without a fabricated AXPress ref.

`py_compile` and `git diff --check` passed. Ruff is configured but not installed
in the current uv environment, so `uv run ruff format --check ...` could not
start and is recorded as an environment limitation rather than a passing gate.

The first live retry did not reach the semantic operations: macOS reported
Codex as frontmost after activation, and Computer Use then reported that the
Mac was locked. That artifact remains under `/private/tmp`; it is not release
evidence. F5 still requires an unlocked, moved/resized WeChat exact-head run in
which every timed API is at most 3000 ms.

## F5 Live Corrective Slice: Global Search And Proof Canary Precision

Status: implementation and targeted verification passed; an exact-head live
proof rerun remains required after this slice is committed.

Additional live findings:

- WeChat maps `Command+F` to a separate `搜索聊天记录` window, so using it as a
  global-search accelerator changed the active window and invalidated mapped
  roots;
- the resolved global search box becomes focused after a current-frame click,
  while `AXSetFocus` reports success without changing `AXFocused` on this client;
- repeated diagnostic runs appended contact text because the focused search
  value was not selected before clipboard paste;
- closing the global-search overlay can change the chat panel between reviewed
  paths `0/12/4` and `0/11/4`;
- proof privacy scanning treated generic values `Window` and `0` as sensitive
  canaries, causing a false failure against the `inspectWindow` key and numeric
  proof values.

Implemented behavior:

- global search starts with the resolved search-box current-frame click;
- `AXSetFocus` and selector click remain bounded fallbacks, but `Command+F` is
  not used by `open_contact`;
- after exact-element focus verification, `Command+A` selects any previous
  query and `type_text` clipboard-pastes the requested contact;
- search-result inspection is limited to visible rows, 40 nodes, and 350 ms;
  off-screen candidates are ignored, and Return is followed by the same strict
  chat-title postcondition;
- chat-title verification retries all reviewed chat-panel paths and accepts a
  result only when the requested contact matches;
- sensitive canaries exclude generic AX window labels and all-numeric strings,
  while contact, message, path, and token canaries remain active.

Targeted automated evidence:

```bash
uv run pytest packages/wechat-desktop-tool/tests tests/test_sdk_examples.py -q
```

Result: 137 tests passed. Added regressions cover frame-click-before-AXSetFocus,
off-screen search candidates, search replacement, layout-path changes, and
generic-canary filtering.

```bash
uv run pytest tests -q
```

Result: 127 tests passed in 75.82 seconds.

Live diagnostic evidence, intentionally not release evidence because the code
was not yet committed:

- all checklist operations passed;
- contacts: 11, visible conversations: 14, visible messages: 30;
- `openWeChat=533 ms`, `inspectWindow=336 ms`,
  `listConversations=330 ms`, `openContact=823 ms`,
  `readVisibleMessages=1080 ms`, and `listContacts=1472 ms`;
- focus gate, target postcondition, expired-ref rejection, frame provenance,
  and raw-observation absence all passed;
- rebuilding the whitelist proof with the corrected canary filter changed
  `sensitiveFieldScanPassed` from false to true and made strict proof evaluation
  pass without changing the captured live operations.

A second live diagnostic explicitly scrolled the target conversation out of
the visible table before calling the API. It exercised `openMethod=search`,
selected and replaced the existing query, opened `文件传输助手`, verified the
chat title, and returned 30 visible messages. `openContact` completed in
2457 ms and `readVisibleMessages` in 1282 ms, so the non-visible-contact search
branch also satisfies the 3000 ms API target.

The diagnostic public and private files remain under `/private/tmp`. F5 is not
complete until the same checks pass against the exact commit SHA produced by
this slice and strict release preflight accepts that public proof.

## F5 Exact-Head Live Closure

Status: complete at commit
`6a74c1d677c767bc68b993f038739fe092c9c204`.

The exact-head public proof passed all checklist, collection, safety, privacy,
source-binding, and timing gates. It recorded 11 contacts, 14 visible
conversations, 30 visible messages, and no failed step. Timings were 251 ms for
`openWeChat`, 330 ms for `inspectWindow`, 336 ms for `listConversations`,
829 ms for `openContact`, 1095 ms for `readVisibleMessages`, and 1446 ms for
`listContacts`.

Strict release preflight accepted the public proof for the exact SHA. A local
partial release bundle copied the selector proof byte-for-byte, evaluated
`wechat_selector_engine_smoke=true`, passed the explicit target-name canary,
and contained no forbidden raw/private fields or local path values. Private
diagnostics remain only under `/private/tmp`.

GitHub Actions run `29196280097`, job `86659712229`, passed the same source head
in 2m25s.

F6 new-head review and merge-readiness refresh are now unblocked.

## F6 Review Remediation: Public Focus, Target Identity, Row Identity, And Pagination

Status: F4 implementation and deterministic verification complete. Authorized
live send proof was attempted but did not execute because the Codex local-action
approval service rejected the escalation after its usage limit was reached. No
message was sent by that attempt.

Findings addressed:

- `PRR-013`: public `focus_contact` now delegates to the same verified
  `open_contact` control-map/selector flow used by semantic contact opening.
  `send_message` therefore verifies the target chat before drafting or
  submitting and no longer enters the obsolete `Command+F`/coarse-observe
  sequence.
- `PRR-014`: `accessibility_query` and `accessibility_action` now validate an
  explicit target against the configured app allowlist, infer its configured
  bundle id when available, and require a target-app-only request to match the
  frontmost application when no bundle identity is available.
- `PRR-015`: executable `AXRow` actionRefs require a concrete row label and
  carry that label in `preconditions.labelIn`. Execution rejects row refs that
  lack matching identity evidence before any backend or selector fallback.
  Parsed conversation items retain the original AX row label for execution
  while continuing to expose a semantic `displayName`.
- `PRR-016`: contact and conversation lists explicitly report
  `pagination.mode="visibleWindow"`, always return `nextPageToken=null`, and
  reject non-null page tokens with `pagination_not_supported`. The APIs no
  longer advertise a cursor that cannot advance UI state.

Additional integration work:

- dry-run app-control responses now model the selector-backed visible-contact
  query, action, and target-title verification path;
- CLI help and recovery guidance describe verified selector-backed contact
  selection rather than a search shortcut;
- release preflight and the root SDK contract test now validate the new
  selector-backed command sequence;
- new stable failure kinds are `wechat_action_target_unverified` and
  `pagination_not_supported`.

Compatibility notes:

- public method names and command schemas are unchanged;
- `focus_contact` retains its existing result fields and adds the nested
  `openContact` semantic result as evidence;
- `search_hotkey`, `search_clear_hotkey`, and `clear_key` remain accepted in
  shared configuration for compatibility, but normal public contact switching
  no longer depends on them;
- callers that previously replayed a synthetic list token must stop and refresh
  the visible window instead. A non-null token now fails explicitly rather than
  returning a duplicate first page.

Deterministic proof:

- root suite: 127 tests passed;
- `app-control-protocol`: 55 tests passed;
- `computer-use-macos`: 128 tests passed, with one platform-conditional skip;
- `wechat-desktop-tool`: 122 tests passed;
- release preflight, `compileall`, and `git diff --check` passed;
- Ruff was unavailable in the current environment;
- strict mypy still reports the repository's existing broad baseline (184
  errors across 15 files), so it is not a passing gate for this slice.

The remaining F5 evidence is one real `send_message` call to
`文件传输助手` through the restarted local service. It must be run exactly once;
an unknown post-submit result must not be retried.

### Fresh-head fail-closed hardening

The first F6 static pass found one ordering weakness before the review report
was finalized: `_click_node_phase` could attempt a current-frame coordinate for
an unlabeled `AXRow` before reaching its row-identity failure. Normal contact
candidates already have semantic labels, but the helper violated the global
fail-closed invariant for malformed or future callers.

The follow-up moves the missing-row-label rejection ahead of every action and
coordinate path. It also makes visible-contact opening execute the candidate's
existing actionRef, which already contains the exact raw AX row label and
preconditions, instead of rebuilding a weaker ref from the public semantic
element. Public `element.label` remains the clean `displayName`; raw combined
row labels remain confined to the short-lived actionRef identity contract.

The new regression proves an unlabeled row with a valid frame emits zero
app-control commands and returns `wechat_action_target_unverified`. The complete
WeChat package suite passes with 123 tests after this hardening.

## F6 Performance Remediation: Warm Accessibility Action Worker

Status: deterministic implementation and authorized post-change live timing
complete.

The successful public send proof on `f2b98ed` measured `3116 ms`, opening
`PRR-017` against the `<=3000 ms` semantic API contract. The largest removable
transport gap was the Chats `AXPress`: `1042 ms` wall time versus `734 ms`
inside the action backend, or about `308 ms` of one-shot process startup and
transport overhead.

`computer-use-macos` now starts an independent prewarmed Accessibility action
worker alongside the existing query worker in default direct/service mode. The
worker executes the unchanged action script, so allowlist checks, bundle/app
selection, snapshot validation, AX path resolution, role/label/action
preconditions, and `AXUIElementPerformAction` behavior remain identical.

Failure behavior is deliberately asymmetric:

- the original subprocess is used when no action worker is available before a
  request is dispatched;
- after dispatch, worker protocol failure or timeout is returned immediately
  and is never replayed, because the action may already have mutated the
  desktop;
- read-only query workers retain their existing protocol-failure fallback;
- helper-backed execution remains unchanged and continues to be owned by the
  helper transport.

Deterministic tests cover worker success, protocol failure without retry,
timeout without retry, generated worker-script compilation, and existing
subprocess compatibility when no worker is configured. Current results:

- `computer-use-macos`: 132 tests passed, 1 skipped;
- root repository: 127 tests passed in 41.695 seconds;
- `wechat-desktop-tool`: 123 tests passed.

The expected representative saving was approximately `308 ms`. Exact-head live
verification subsequently measured the warm Chats `AXPress` at `58 ms` wall
time (`44 ms` worker transport, `42 ms` backend) instead of the previous
`1042 ms`, with `fallback=false` and all preconditions verified. A separate
authorized public `send_message` completed in `2461 ms`, below the `3000 ms`
contract. The send started while Chats was already selected, so a separate
non-submit probe first switched to Contacts and then measured `open_contact`
back to `文件传输助手` at `1272 ms`; no text or Return action occurred in that
probe. The verification document records both runs and their boundary.

## F4 Review Remediation: Warm-Worker Protocol Framing

Status: implementation, repository-wide verification, and new-head review
complete. That review closed `PRR-018` and opened the follow-up deadline finding
`PRR-019`, addressed below.

`PRR-018` identified a race between `select()` on the subprocess file
descriptor and `TextIOWrapper.readline()`. The text wrapper could prefetch both
the readiness line and a fast response, return only readiness, and leave the
response in its private buffer while the next `select()` waited on an empty
kernel pipe. A valid query or an already-executed action could therefore be
reported as timed out.

The worker protocol now has explicit phases:

1. process startup reads and validates exactly one readiness frame before
   `start()` returns or any request is written;
2. request and response framing uses `os.read()` plus a worker-owned byte
   buffer, checking buffered complete lines before waiting on the descriptor;
3. one UTF-8 newline-delimited response is consumed for each serialized
   request under the existing worker lock;
4. invalid readiness JSON, non-`ok` readiness, invalid UTF-8, EOF, and frames
   above 16 MiB fail the worker protocol;
5. the request deadline includes a required worker restart and handshake;
6. stop, failed readiness, protocol failure, and timeout clear framing state
   and close all subprocess pipes.

The action safety boundary is unchanged. If no warm action worker exists, the
client may use the one-shot subprocess before dispatch. Once a request has
been written to the action worker, timeout or protocol failure is returned as
an unknown outcome and the request is never replayed through the subprocess
runner. Read-only query protocol failures retain their existing fallback.

New real-subprocess regression coverage proves:

- a readiness frame and following response delivered in one OS write remain
  separately consumable;
- failed readiness is rejected during `start()` before request dispatch;
- 100 immediate query responses and 100 immediate action responses have zero
  false timeouts, dropped frames, or response cross-wiring;
- a synthetic action worker can record dispatch and then withhold its response;
  the client returns `TIMEOUT` and makes zero fallback runner calls;
- subprocess pipes produce no `ResourceWarning` under warning-as-error tests.

Focused result:

```text
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/computer-use-macos/tests

Ran 137 tests in 0.702s
OK (skipped=1)
```

No real Accessibility action or WeChat message was executed for this
remediation. All new protocol workers are synthetic subprocesses.

## F4 Review Remediation: Pre-Dispatch Worker Deadline

Status: implementation, exact-head deterministic verification, and new-head
review complete. `PRR-019` is resolved by the `a77f5d4` Review Contract.

`PRR-019` found that the worker deadline was calculated before acquiring the
per-worker lock, but the lock wait itself was unbounded. A queued request could
therefore exhaust its timeout, acquire the lock later, and still be written to
the worker. For a mutating Accessibility action, that contradicted the caller's
timeout result and could mutate the desktop after the request was already
considered expired.

The worker now applies one monotonic deadline to request serialization, lock
contention, worker startup/readiness, dispatch, and response:

1. the request is serialized before entering the worker critical section;
2. lock acquisition is bounded by the remaining request budget;
3. the deadline is checked immediately after lock acquisition;
4. startup and readiness receive the same deadline, followed by one final
   deadline check immediately before `stdin.write()`;
5. a deadline exhausted before dispatch returns code `124` with
   `timed_out=true`, writes zero request frames, and leaves an existing healthy
   worker running;
6. once a request frame has been written, the existing unknown-outcome safety
   boundary remains unchanged: response timeout terminates the worker and a
   mutating action is never replayed.

New real-subprocess regression coverage proves both required zero-write cases:

- a request whose complete budget is consumed waiting for the worker lock
  returns while the lock is still held, does not reach the worker, and a
  follow-up request succeeds through the same worker process;
- a newly started worker emits valid readiness, startup completion is then
  held past the request deadline, and the final pre-write check prevents
  dispatch while preserving that healthy worker for a follow-up request.

The existing coalesced-frame, 100 immediate query/action response, failed
readiness, and post-dispatch no-replay tests continue to pass. Focused package
verification with resource warnings promoted to errors produced:

```text
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/computer-use-macos/tests

Ran 139 tests in 1.474s
OK (skipped=1)
```

This remediation does not change a public API, protocol schema, configuration
key, package dependency, or package version. No live Accessibility action or
WeChat message was executed; all added workers are synthetic subprocesses.

## F4 Review Remediation: Action Timeout Retryability

Status: implementation and focused package verification complete; exact-head
repository verification and re-review remain pending.

`PRR-020` found that the warm action worker correctly suppressed internal
fallback after dispatch, but the public protocol still classified every
timeout as retryable. A consumer following that recovery hint could therefore
repeat an action whose first UI outcome was unknown.

The worker result now preserves whether the request crossed the dispatch
boundary. Every result before a write attempt carries
`request_dispatched=false`; once `stdin.write()` is attempted, every success,
protocol failure, EOF, or response timeout carries
`request_dispatched=true`. The action transport publishes this state as
`requestDispatched` when known.

Protocol retryability is now fail-closed for mutating action timeouts:

- a reliably identified pre-dispatch zero-write timeout remains retryable;
- a post-dispatch timeout is not retryable because its UI outcome is unknown;
- a timeout with no dispatch evidence, including legacy fake workers and the
  one-shot subprocess transport, is conservatively not retryable;
- non-action timeout behavior is unchanged;
- one computed value populates both the top-level observation and nested
  `ToolError`, preventing contradictory recovery guidance.

Real-subprocess regressions prove both sides of the boundary. The pre-dispatch
case exhausts its deadline while the worker lock is held, records zero request
frames, performs zero fallback calls, and returns both retryability fields as
`true`. The post-dispatch case records exactly one `AXPress`, withholds the
response, performs zero fallback calls, and returns both fields as `false`.
Focused verification produced:

```text
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/computer-use-macos/tests

Ran 141 tests in 1.612s
OK (skipped=1)
```

No live Accessibility action or WeChat message was executed. All new behavior
was exercised with synthetic subprocess workers and temporary request markers.

## F4 Review Remediation: Downstream Mutating No-Replay

Status: implementation and focused package verification complete; exact-head
repository verification and re-review remain pending.

`PRR-021` found that the macOS action transport correctly returned
`requestDispatched=true` and `retryable=false` after a lost worker response,
but several WeChat recovery paths looked only at a generic failure kind. They
could therefore execute a coordinate click, selector click, Return keypress, or
next contact-opening strategy after the first action may already have mutated
the desktop.

The WeChat adapter now uses one fail-closed recovery predicate:

| Lower action evidence | Automatic mutating fallback |
| --- | --- |
| `actionAttempted=true` | Blocked |
| `requestDispatched=true` | Blocked unless the result explicitly reports an unsupported action and no attempt |
| `retryable=false` or missing/contradictory dispatch evidence | Blocked |
| `requestDispatched=false` and `retryable=true` | One configured fallback allowed |
| Explicit unsupported action with no attempted-action evidence | One configured fallback allowed |

Mapped navigation, visible-contact opening through both control-map and
selector paths, search-box focus, search-result selection, coordinate fallback,
and public actionRef execution all use that predicate. Once an allowed selector
fallback is issued, its result is final; a failed click is no longer discarded
in favor of another mutation.

The generated native action script also records
`actionAttempted=true` when `AXUIElementPerformAction` or
`AXUIElementSetAttributeValue` has been invoked and returns an error. Failures
that occur before the native call retain `actionAttempted=false`.

Cross-package tests run the real `ComputerUseClient` against synthetic warm
worker subprocesses. Dispatch followed by EOF, response timeout, malformed
JSON, and a structured native-action failure each records exactly one
`AXPress`, performs zero one-shot runner calls, and produces zero additional
WeChat mutations. Separate cross-package cases prove that an explicit
pre-dispatch timeout and an explicit unsupported action still execute exactly
one configured selector fallback. Path-specific tests cover mapped navigation,
both visible-contact strategies, search focus, search-result Return recovery,
and a failed selector fallback.

Focused verification produced:

```text
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:\
packages/wechat-desktop-tool/src .venv/bin/python -m unittest discover \
  -s packages/wechat-desktop-tool/tests

Ran 132 tests in 0.827s
OK

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  .venv/bin/python -W error::ResourceWarning -m unittest discover \
  -s packages/computer-use-macos/tests

Ran 141 tests in 1.557s
OK (skipped=1)
```

This remediation changes recovery behavior but adds no command, schema,
configuration key, dependency, package version, or live desktop proof. No real
Accessibility action or WeChat message was executed.

## F4 Review Remediation: Definite Unsupported Action Semantics

Status: implementation and focused package verification complete; exact-head
repository verification pending.

`PRR-022` identified that the no-replay remediation treated Apple's definite
unsupported errors as uncertain native outcomes. In particular, a WeChat
`AXRow` may pass identity and frame checks but return
`kAXErrorActionUnsupported` (`-25206`) when `AXPress` is invoked. The call is
unsuccessful and has no UI effect, so suppressing the existing selector or
current-frame fallback regressed the compatibility behavior introduced for
those rows.

The native action result now separates three effect states:

| Native result | Normalized evidence | Recovery |
| --- | --- | --- |
| success | `actionEffect=performed` | no fallback |
| `AXPress/-25206` or `AXSetFocus/-25205` | `failureKind=accessibility_action_unsupported`, `actionAttempted=true`, `actionEffect=none`, `nativeErrorCode` | one configured fallback |
| any other native error, including `-25204` | `failureKind=accessibility_action_failed`, `actionAttempted=true`, `actionEffect=unknown`, `nativeErrorCode` | blocked |

The WeChat recovery predicate gives the definite unsupported/no-effect tuple a
narrow precedence exception. It requires at least one `actionEffect` value and
requires every direct, metadata, and nested value to be `none`; missing or
contradictory effect evidence remains blocked. Legacy backend-level
`unsupported_operation` and pre-call `unsupported_accessibility_action`
results continue to allow one fallback only when no positive attempt evidence
exists.

Cross-package regressions use the real `ComputerUseClient` and warm worker
protocol to prove one selector fallback for native `AXPress/-25206`, one search
focus fallback for `AXSetFocus/-25205`, and zero downstream mutations for
`-25204`, EOF, timeout, malformed response, and contradictory unsupported
effect evidence. Path tests also cover mapped navigation and public actionRef
recovery. No real Accessibility action or WeChat message is required for this
classification fix.

Focused verification after implementation:

```text
computer-use-macos: 142 tests passed, 1 skipped
wechat-desktop-tool: 137 tests passed
```

## F4 Review Remediation: Strict Unsupported Action Proof

Status: implementation and focused package verification complete; exact-head
repository verification and replacement review remain pending.

`PRR-025` found that `computer-use-macos` emitted
`accessibility_action_unsupported` without including it in the stable public
failure tuple. The package now declares
`errors.ACCESSIBILITY_ACTION_UNSUPPORTED`, includes its value in
`COMPUTER_USE_FAILURE_KINDS`, and verifies both real normalized native cases
against that routing contract.

`PRR-026` found that WeChat recovery accepted any collected string
`actionEffect=none` while ignoring malformed duplicates or contradictory
native codes. The recovery boundary now requires one complete, internally
consistent proof:

| Proof field | Accepted value |
| --- | --- |
| failure kind | `accessibility_action_unsupported` |
| action and code | `AXPress/-25206` or `AXSetFocus/-25205` |
| attempted state | `true` |
| effect | `none` |

Every present camel-case, snake-case, metadata, and nested occurrence must have
the expected type and value. Missing action, attempted state, effect, or native
code; `-25204`; wrong action/code pairing; empty or non-string effects;
non-integer codes; malformed proof containers; and contradictory duplicates
all stop recovery before a second mutation.

The macOS result metadata parser also checks the type of `actionEffect` before
normalizing it. A malformed object is retained in the nested raw result for
diagnosis without raising or being promoted into trusted top-level proof.

Focused verification after implementation:

```text
computer-use-macos: 143 tests passed, 1 skipped
wechat-desktop-tool: 138 tests passed
```

The two valid native unsupported cases still execute exactly one configured
fallback. Synthetic package and cross-package tests cover missing,
contradictory, empty, non-string, non-integer, wrong-code, `-25204`, timeout,
EOF, malformed-response, and legacy-attempted outcomes with zero downstream
mutation. No live Accessibility action or WeChat message was executed.

## F4 Review Remediation: End-To-End Action And Boolean Evidence

Status: implementation and focused package verification complete; exact-head
repository verification and replacement review remain pending.

The current-head review reopened `PRR-021`, `PRR-022`, and `PRR-026` after
reproducing three gaps in the mutation recovery boundary:

- the generated native failure producer omitted `action`, while WeChat required
  it for definite-no-effect recovery;
- the strict response proof was internally checked but not compared with the
  action sent in the request;
- malformed attempted or dispatch values were ignored, and the direct client
  coerced raw `actionAttempted` with `bool(...)`.

The native generated `fail()` path now includes the validated requested action
on both unsupported and uncertain post-call failures. `ComputerUseClient`
promotes attempted evidence only when the source is an actual Boolean and keeps
the unmodified raw action result available in `accessibilityAction`.

The WeChat recovery policy now receives `expected_action` from each exact
outbound command. A definite unsupported proof is accepted only when all action
copies agree with each other and with that expected action, in addition to the
existing failure-kind, attempt, effect, and native-code checks. Both mismatch
directions therefore stop after the one `accessibility_action` operation.

Attempt and dispatch parsing now produces an internal immutable evidence object
with `present`, `valid`, and `value`. This distinguishes absent evidence from a
valid Boolean and from invalid evidence. Relevant metadata, nested action,
diagnostics, transport, camel-case, and snake-case containers are checked
presence-sensitively. Non-Boolean truthy or falsey values, malformed containers,
and conflicting duplicates invalidate the shared fallback policy before any
coordinate click, selector click, Return keypress, focus fallback, or next open
strategy.

The cross-package native compatibility tests now execute the production
`_accessibility_action_worker_script()` against temporary fake macOS framework
modules. They no longer synthesize the previously missing action field. The
real generated `AXPress/-25206` and `AXSetFocus/-25205` payloads pass through
`ComputerUseClient`, bind to their matching WeChat request, and each authorize
exactly one configured fallback. Adversarial tests cover both action mismatch
directions, truthy and falsey malformed attempted strings, malformed and
conflicting dispatch aliases, malformed action/metadata containers, and the
existing uncertain native outcomes with operation-count assertions.

Focused verification after implementation:

```text
computer-use-macos: 144 tests passed, 1 skipped
wechat-desktop-tool: 140 tests passed
```

No real Accessibility action or WeChat message was executed. The change adds
no command, schema version, configuration key, dependency, or semantic API.
