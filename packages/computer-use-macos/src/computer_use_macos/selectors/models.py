"""Internal dataclasses for Accessibility selector profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

PickStrategy: TypeAlias = Literal[
    "first",
    "best",
    "largestArea",
    "all",
    "nearestToAnchor",
]
CacheMode: TypeAlias = Literal["disabled", "read", "readWrite"]
SelectorRootKind: TypeAlias = Literal[
    "focusedWindow",
    "frontmostApp",
    "selector",
    "axPath",
]
SelectorScope: TypeAlias = Literal["self", "children", "descendants"]
RelationKind: TypeAlias = Literal[
    "rightOf",
    "leftOf",
    "above",
    "below",
    "inside",
    "near",
]
ConstraintKind: TypeAlias = Literal[
    "hasChildRole",
    "hasDescendantRole",
    "minChildren",
    "frameWithin",
    "rightOf",
    "below",
    "selected",
]
FieldSource: TypeAlias = Literal["self", "descendant", "attribute", "computed"]
PaginationMode: TypeAlias = Literal["none", "visibleWindow", "cursor"]
SelectorResultStatus: TypeAlias = Literal[
    "resolved",
    "not_found",
    "ambiguous",
    "stale",
    "failed",
]
CollectionResultStatus: TypeAlias = Literal[
    "resolved",
    "partial",
    "not_found",
    "failed",
]
CacheStatus: TypeAlias = Literal["hit", "miss", "stale", "disabled"]
ActionRisk: TypeAlias = Literal[
    "read_only",
    "changes_focus",
    "changes_current_chat",
    "submits_text",
]
ActionPreconditionKind: TypeAlias = Literal[
    "appFrontmost",
    "windowTitleMatches",
    "signatureMatches",
    "selectorStillMatches",
]


@dataclass(frozen=True)
class AppIdentity:
    app_id: str
    bundle_ids: tuple[str, ...]
    app_names: tuple[str, ...] = ()
    supported_locales: tuple[str, ...] = ()
    window_title_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class Frame:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class SelectorEvidence:
    matched_attributes: dict[str, JsonValue] = field(default_factory=dict)
    matched_actions: tuple[str, ...] = ()
    matched_constraints: tuple[str, ...] = ()
    score_breakdown: dict[str, float] = field(default_factory=dict)
    debug_attributes: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class ActionPrecondition:
    kind: ActionPreconditionKind
    value: JsonValue


@dataclass(frozen=True)
class CachePolicy:
    mode: CacheMode = "readWrite"
    ttl_seconds: int | None = 60
    validate_signature: bool = True
    key_attributes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationRule:
    anchor_selector_id: str
    relation: RelationKind
    max_distance: float | None = None


@dataclass(frozen=True)
class PaginationPolicy:
    mode: PaginationMode = "visibleWindow"
    default_limit: int = 30
    max_limit: int = 100


@dataclass(frozen=True)
class CollectionDiagnosticsPolicy:
    include_skipped_count: bool = True
    include_field_failures: bool = True
    include_candidate_counts: bool = True


@dataclass(frozen=True)
class ConfidencePolicy:
    minimum: float = 0.85
    attribute_weight: float = 0.4
    action_weight: float = 0.2
    structure_weight: float = 0.25
    geometry_weight: float = 0.1
    cache_weight: float = 0.05


@dataclass(frozen=True)
class AttributeMatcher:
    equals: JsonValue | None = None
    any_of: tuple[JsonValue, ...] | None = None
    contains: str | None = None
    regex: str | None = None
    exists: bool | None = None
    alias_ref: str | None = None


@dataclass(frozen=True)
class MatchRule:
    role: str | None = None
    role_in: tuple[str, ...] = ()
    attributes: dict[str, AttributeMatcher] = field(default_factory=dict)
    actions_include: tuple[str, ...] = ()
    enabled: bool | None = None
    visible: bool | None = None


@dataclass(frozen=True)
class SelectorRoot:
    kind: SelectorRootKind
    selector_id: str | None = None
    ax_path: str | None = None


@dataclass(frozen=True)
class SelectorStep:
    scope: SelectorScope
    max_depth: int
    limit: int
    time_budget_ms: int
    role_in: tuple[str, ...] = ()
    match: MatchRule = field(default_factory=MatchRule)
    relation: RelationRule | None = None


@dataclass(frozen=True)
class SelectorConstraint:
    kind: ConstraintKind
    value: JsonValue
    weight: float = 1.0
    required: bool = False


@dataclass(frozen=True)
class SelectorDefinition:
    selector_id: str
    root: SelectorRoot
    steps: tuple[SelectorStep, ...]
    description: str | None = None
    constraints: tuple[SelectorConstraint, ...] = ()
    pick: PickStrategy = "best"
    confidence: ConfidencePolicy = field(default_factory=ConfidencePolicy)
    fallbacks: tuple[str, ...] = ()
    cache: CachePolicy = field(default_factory=CachePolicy)


@dataclass(frozen=True)
class FieldDefinition:
    source: FieldSource
    selector: SelectorDefinition | None = None
    attribute: str | None = None
    required: bool = False
    transform: str | None = None


@dataclass(frozen=True)
class CollectionDefinition:
    collection_id: str
    root_selector_id: str
    item_selector: SelectorDefinition
    fields: dict[str, FieldDefinition]
    pagination: PaginationPolicy = field(default_factory=PaginationPolicy)
    diagnostics: CollectionDiagnosticsPolicy = field(
        default_factory=CollectionDiagnosticsPolicy
    )


@dataclass(frozen=True)
class ElementSignature:
    role: str
    attributes: dict[str, JsonValue] = field(default_factory=dict)
    actions: tuple[str, ...] = ()
    ancestor_hints: tuple[str, ...] = ()
    frame_hash: str | None = None


@dataclass(frozen=True)
class ElementRef:
    kind: Literal["accessibilityElement"]
    snapshot_id: str
    ax_path: str
    role: str
    signature: ElementSignature


@dataclass(frozen=True)
class ResolvedElement:
    element_ref: ElementRef
    selector_id: str
    role: str
    actions: tuple[str, ...]
    confidence: float
    evidence: SelectorEvidence
    label: str | None = None
    frame: Frame | None = None


@dataclass(frozen=True)
class SelectorDiagnostics:
    tried_selectors: tuple[str, ...] = ()
    query_count: int = 0
    node_count: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
    cache_status: CacheStatus = "disabled"
    failure_kind: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class SelectorResult:
    selector_id: str
    profile_id: str
    profile_version: str
    status: SelectorResultStatus
    elements: tuple[ResolvedElement, ...] = ()
    snapshot_id: str | None = None
    diagnostics: SelectorDiagnostics = field(default_factory=SelectorDiagnostics)
    schema: Literal["app_control.selector_result.v1"] = (
        "app_control.selector_result.v1"
    )


@dataclass(frozen=True)
class PaginationState:
    limit: int
    returned: int
    has_more: bool
    next_cursor: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    collection_id: str
    profile_id: str
    profile_version: str
    status: CollectionResultStatus
    items: tuple[dict[str, JsonValue], ...] = ()
    pagination: PaginationState = field(
        default_factory=lambda: PaginationState(limit=0, returned=0, has_more=False)
    )
    snapshot_id: str | None = None
    diagnostics: SelectorDiagnostics = field(default_factory=SelectorDiagnostics)
    schema: Literal["app_control.collection_result.v1"] = (
        "app_control.collection_result.v1"
    )


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    selector_id: str
    ax_action: str
    risk: ActionRisk
    preconditions: tuple[ActionPrecondition, ...] = ()
    enabled_by_default: bool = False
    description: str | None = None


@dataclass(frozen=True)
class ActionRef:
    id: str
    kind: str
    target: ElementRef
    action: str
    preconditions: tuple[ActionPrecondition, ...]
    risk: ActionRisk
    target_summary: str
    schema: Literal["app_control.action_ref.v1"] = "app_control.action_ref.v1"


@dataclass(frozen=True)
class SelectorCacheEntry:
    profile_id: str
    profile_version: str
    selector_id: str
    app_bundle_id: str
    window_fingerprint: str
    element_ref: ElementRef
    created_at: str
    expires_at: str | None = None


@dataclass(frozen=True)
class AccessibilitySelectorProfile:
    schema_version: str
    profile_id: str
    profile_version: str
    app: AppIdentity
    locale_aliases: dict[str, tuple[str, ...]]
    selectors: dict[str, SelectorDefinition]
    collections: dict[str, CollectionDefinition] = field(default_factory=dict)
    actions: dict[str, ActionDefinition] = field(default_factory=dict)
