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
