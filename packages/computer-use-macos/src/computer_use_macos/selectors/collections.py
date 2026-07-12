"""Collection extraction for internal selector profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..accessibility_limits import MAX_ACCESSIBILITY_QUERY_DEPTH
from .diagnostics import selector_diagnostics
from .matching import (
    constraints_match,
    effective_step_match,
    match_node,
    node_actions,
    node_attribute,
    node_ax_path,
    node_frame,
    node_label,
    node_role,
)
from .models import (
    CollectionDefinition,
    CollectionResult,
    FieldDefinition,
    JsonValue,
    PaginationState,
    SelectorConstraint,
    SelectorDiagnostics,
    SelectorStep,
)
from .resolver import (
    SelectorResolver,
    _NormalizedQueryOutcome,
    _normalize_query_payload,
)
from .transforms import apply_transform


class CollectionExtractor:
    """Extract repeated semantic items from a selector collection definition."""

    def __init__(self, resolver: SelectorResolver) -> None:
        self.resolver = resolver

    def extract(
        self,
        collection_id: str,
        *,
        limit: int | None = None,
        debug: bool = False,
    ) -> CollectionResult:
        collection = self.resolver.profile.collections.get(collection_id)
        if collection is None:
            return self._failed(
                collection_id,
                "selector_not_found",
                f"collection not found: {collection_id}",
            )
        root = self.resolver.resolve(collection.root_selector_id, debug=debug)
        if root.status != "resolved" or not root.elements:
            return CollectionResult(
                collection_id=collection.collection_id,
                profile_id=self.resolver.profile.profile_id,
                profile_version=self.resolver.profile.profile_version,
                status="failed",
                diagnostics=selector_diagnostics(
                    tried_selectors=(collection.root_selector_id,),
                    query_count=root.diagnostics.query_count,
                    node_count=_collection_node_count(
                        collection,
                        root.diagnostics.node_count,
                    ),
                    truncated=root.diagnostics.truncated,
                    truncation_reason=root.diagnostics.truncation_reason,
                    cache_status=root.diagnostics.cache_status,
                    failure_kind=root.diagnostics.failure_kind or "selector_not_found",
                    cause_failure_kind=root.diagnostics.cause_failure_kind,
                    retryable=root.diagnostics.retryable,
                    message=root.diagnostics.message or "collection root not found",
                ),
            )
        requested_limit = limit or collection.pagination.default_limit
        effective_limit = min(requested_limit, collection.pagination.max_limit)
        root_path = root.elements[0].element_ref.ax_path
        item_nodes, item_diagnostics = self._query_items(
            collection,
            root_path,
            effective_limit + 1,
            debug=debug,
        )
        if item_diagnostics.failure_kind == "selector_query_failed":
            return self._query_failed_collection(
                collection,
                item_diagnostics,
                root_diagnostics=root.diagnostics,
            )
        has_more = len(item_nodes) > effective_limit
        field_cache, batch_field_diagnostics = self._batch_extract_fields(
            collection,
            root_path,
            item_nodes,
            debug=debug,
        )
        if batch_field_diagnostics.failure_kind == "selector_query_failed":
            return self._query_failed_collection(
                collection,
                batch_field_diagnostics,
                root_diagnostics=root.diagnostics,
                item_diagnostics=item_diagnostics,
            )

        items: list[dict[str, JsonValue]] = []
        skipped = 0
        field_failures = 0
        batch_query_count = batch_field_diagnostics.query_count
        fallback_query_count = 0
        batch_node_count = batch_field_diagnostics.node_count
        fallback_node_count = 0
        field_truncated = batch_field_diagnostics.truncated
        field_truncation_reason = batch_field_diagnostics.truncation_reason
        field_query_failure: SelectorDiagnostics | None = None
        for item_node in item_nodes:
            if len(items) >= effective_limit:
                break
            item, field_diagnostics = self._extract_item(
                collection,
                item_node,
                debug=debug,
                field_cache=field_cache,
            )
            fallback_query_count += field_diagnostics.query_count
            fallback_node_count += field_diagnostics.node_count
            if field_diagnostics.truncated:
                field_truncated = True
                field_truncation_reason = field_diagnostics.truncation_reason
            if field_diagnostics.failure_kind == "selector_query_failed":
                field_query_failure = field_diagnostics
                break
            if item is None:
                skipped += 1
                field_failures += 1
                continue
            items.append(item)

        if field_query_failure is not None:
            combined_field_diagnostics = selector_diagnostics(
                query_count=batch_query_count + fallback_query_count,
                node_count=batch_node_count + fallback_node_count,
                failure_kind="selector_query_failed",
                cause_failure_kind=field_query_failure.cause_failure_kind,
                retryable=field_query_failure.retryable,
                message=field_query_failure.message,
            )
            return self._query_failed_collection(
                collection,
                combined_field_diagnostics,
                root_diagnostics=root.diagnostics,
                item_diagnostics=item_diagnostics,
            )

        status = "resolved"
        truncated = item_diagnostics.truncated or field_truncated
        truncation_reason = (
            item_diagnostics.truncation_reason
            or field_truncation_reason
        )
        if skipped or truncated:
            status = "partial" if items else "failed"
        field_query_count = batch_query_count + fallback_query_count
        field_node_count = batch_node_count + fallback_node_count
        diagnostics = selector_diagnostics(
            tried_selectors=(collection.root_selector_id,),
            query_count=(
                root.diagnostics.query_count
                + item_diagnostics.query_count
                + field_query_count
            ),
            node_count=_collection_node_count(
                collection,
                root.diagnostics.node_count
                + item_diagnostics.node_count
                + field_node_count,
            ),
            truncated=truncated,
            truncation_reason=truncation_reason,
            cache_status=root.diagnostics.cache_status,
            failure_kind=(
                "selector_query_truncated"
                if truncated
                else (
                    "selector_field_missing"
                    if skipped
                    else item_diagnostics.failure_kind
                )
            ),
            message=_collection_message(
                collection,
                skipped=skipped,
                field_failures=field_failures,
                fallback=item_diagnostics.message,
            ),
        )
        return CollectionResult(
            collection_id=collection.collection_id,
            profile_id=self.resolver.profile.profile_id,
            profile_version=self.resolver.profile.profile_version,
            status=status,  # type: ignore[arg-type]
            items=tuple(items),
            snapshot_id=root.snapshot_id,
            pagination=PaginationState(
                limit=effective_limit,
                returned=len(items),
                has_more=has_more,
                next_cursor=None,
            ),
            diagnostics=diagnostics,
        )

    def _query_items(
        self,
        collection: CollectionDefinition,
        root_path: str,
        limit: int,
        *,
        debug: bool,
    ) -> tuple[list[Mapping[str, Any]], SelectorDiagnostics]:
        item_selector = collection.item_selector
        if not item_selector.steps:
            return [], selector_diagnostics(
                failure_kind="selector_not_found",
                message="collection item selector has no steps",
            )
        step = item_selector.steps[0]
        payload = self.resolver.query_runner(
            root={"kind": "axPath", "axPath": root_path},
            query={
                "scope": step.scope,
                "maxDepth": step.max_depth,
                "limit": limit,
                "timeBudgetMs": step.time_budget_ms,
                "attributes": _query_attributes(step, item_selector.constraints),
                "actions": bool(step.match.actions_include)
                or _collection_needs_item_actions(collection),
                "match": {"roleIn": list(step.role_in or step.match.role_in)},
                **_constraint_query_flags(item_selector.constraints),
            },
            include_raw=debug,
        )
        normalized = _normalize_query_payload(payload)
        if not normalized.succeeded:
            return [], _query_failure_diagnostics(normalized)
        match = effective_step_match(step)
        nodes = []
        for node in normalized.nodes:
            if not match_node(node, match, self.resolver.profile.locale_aliases)[0]:
                continue
            constraints_ok, _, _ = constraints_match(
                node,
                item_selector.constraints,
            )
            if constraints_ok:
                nodes.append(node)
        diagnostics = normalized.diagnostics
        backend_truncated = bool(diagnostics.get("truncated", False))
        backend_truncation_reason = _normalized_truncation_reason(diagnostics)
        completed_lookahead = (
            backend_truncated
            and backend_truncation_reason == "limit"
            and len(nodes) >= limit
        )
        truncated = backend_truncated and not completed_lookahead
        return nodes, selector_diagnostics(
            query_count=1,
            node_count=len(normalized.nodes),
            truncated=truncated,
            truncation_reason=backend_truncation_reason if truncated else None,
            failure_kind="selector_query_truncated" if truncated else None,
            message=(
                f"collection item query truncated: {backend_truncation_reason}"
                if truncated
                else None
            ),
        )

    def _extract_item(
        self,
        collection: CollectionDefinition,
        item_node: Mapping[str, Any],
        *,
        debug: bool,
        field_cache: Mapping[tuple[str, str], "_FieldExtraction"] | None = None,
    ) -> tuple[dict[str, JsonValue] | None, SelectorDiagnostics]:
        output: dict[str, JsonValue] = {}
        query_count = 0
        node_count = 0
        truncated = False
        truncation_reason: str | None = None
        for field_name, field in collection.fields.items():
            field_result = self._extract_field(
                item_node,
                field,
                debug=debug,
                field_name=field_name,
                field_cache=field_cache,
            )
            query_count += field_result.query_count
            node_count += field_result.node_count
            if field_result.truncated:
                truncated = True
                truncation_reason = field_result.truncation_reason
            if field_result.failure_kind == "selector_query_failed":
                return None, selector_diagnostics(
                    query_count=query_count,
                    node_count=node_count,
                    failure_kind="selector_query_failed",
                    cause_failure_kind=field_result.cause_failure_kind,
                    retryable=field_result.retryable,
                    message=field_result.message,
                )
            if field_result.value is None:
                if field.required:
                    return None, selector_diagnostics(
                        query_count=query_count,
                        node_count=node_count,
                        truncated=truncated,
                        truncation_reason=truncation_reason,
                        failure_kind="selector_field_missing",
                        message=f"required field missing: {field_name}",
                    )
                continue
            output[field_name] = apply_transform(field_result.value, field.transform)
        return output, selector_diagnostics(
            query_count=query_count,
            node_count=node_count,
            truncated=truncated,
            truncation_reason=truncation_reason,
        )

    def _extract_field(
        self,
        item_node: Mapping[str, Any],
        field: FieldDefinition,
        *,
        debug: bool,
        field_name: str | None = None,
        field_cache: Mapping[tuple[str, str], "_FieldExtraction"] | None = None,
    ) -> "_FieldExtraction":
        if field.source == "self":
            return _FieldExtraction(value=_node_summary(item_node))
        if field.source == "attribute" and field.attribute is not None:
            return _FieldExtraction(value=node_attribute(item_node, field.attribute))
        if field.source == "computed":
            return _FieldExtraction(value=_computed_value(item_node, field.attribute))
        if field.source != "descendant" or field.selector is None:
            return _FieldExtraction()
        item_path = node_ax_path(item_node)
        if item_path is None or not field.selector.steps:
            return _FieldExtraction()
        if field_name is not None and field_cache is not None:
            cached = field_cache.get((item_path, field_name))
            if cached is not None:
                return cached
        step = field.selector.steps[0]
        match = effective_step_match(step)
        payload = self.resolver.query_runner(
            root={"kind": "axPath", "axPath": item_path},
            query={
                "scope": step.scope,
                "maxDepth": step.max_depth,
                "limit": step.limit,
                "timeBudgetMs": step.time_budget_ms,
                "attributes": _query_attributes(step, field.selector.constraints),
                "actions": bool(step.match.actions_include),
                "match": {"roleIn": list(step.role_in or step.match.role_in)},
                **_constraint_query_flags(field.selector.constraints),
            },
            include_raw=debug,
        )
        normalized = _normalize_query_payload(payload)
        if not normalized.succeeded:
            return _field_query_failure(normalized)
        diagnostics = normalized.diagnostics
        truncated = bool(diagnostics.get("truncated", False))
        truncation_reason = (
            _normalized_truncation_reason(diagnostics) if truncated else None
        )
        for node in normalized.nodes:
            matched, _ = match_node(node, match, self.resolver.profile.locale_aliases)
            if not matched:
                continue
            constraints_ok, _, _ = constraints_match(
                node,
                field.selector.constraints,
            )
            if constraints_ok:
                if field.attribute is not None:
                    return _FieldExtraction(
                        value=node_attribute(node, field.attribute),
                        query_count=1,
                        node_count=len(normalized.nodes),
                        truncated=truncated,
                        truncation_reason=truncation_reason,
                    )
                return _FieldExtraction(
                    value=_node_summary(node),
                    query_count=1,
                    node_count=len(normalized.nodes),
                    truncated=truncated,
                    truncation_reason=truncation_reason,
                )
        return _FieldExtraction(
            query_count=1,
            node_count=len(normalized.nodes),
            truncated=truncated,
            truncation_reason=truncation_reason,
            failure_kind="selector_query_truncated" if truncated else None,
        )

    def _batch_extract_fields(
        self,
        collection: CollectionDefinition,
        root_path: str,
        item_nodes: list[Mapping[str, Any]],
        *,
        debug: bool,
    ) -> tuple[dict[tuple[str, str], "_FieldExtraction"], SelectorDiagnostics]:
        if len(item_nodes) <= 1 or not collection.item_selector.steps:
            return {}, selector_diagnostics()
        item_paths = [path for item in item_nodes if (path := node_ax_path(item))]
        if not item_paths:
            return {}, selector_diagnostics()

        cache: dict[tuple[str, str], _FieldExtraction] = {}
        query_count = 0
        node_count = 0
        truncated = False
        truncation_reason: str | None = None
        item_step = collection.item_selector.steps[0]
        for field_name, field in collection.fields.items():
            if not _can_batch_descendant_field(field):
                continue
            assert field.selector is not None
            step = field.selector.steps[0]
            match = effective_step_match(step)
            payload = self.resolver.query_runner(
                root={"kind": "axPath", "axPath": root_path},
                query={
                    "scope": "descendants",
                    "maxDepth": min(
                        MAX_ACCESSIBILITY_QUERY_DEPTH,
                        item_step.max_depth + step.max_depth,
                    ),
                    "limit": max(len(item_paths), len(item_paths) * step.limit),
                    "timeBudgetMs": step.time_budget_ms,
                    "attributes": _query_attributes(step, field.selector.constraints),
                    "actions": bool(step.match.actions_include),
                    "match": {"roleIn": list(step.role_in or step.match.role_in)},
                    **_constraint_query_flags(field.selector.constraints),
                },
                include_raw=debug,
            )
            normalized = _normalize_query_payload(payload)
            query_count += 1
            node_count += len(normalized.nodes)
            if not normalized.succeeded:
                return cache, selector_diagnostics(
                    query_count=query_count,
                    node_count=node_count,
                    failure_kind="selector_query_failed",
                    cause_failure_kind=(
                        normalized.failure_kind
                        or "accessibility_query_unavailable"
                    ),
                    retryable=normalized.retryable,
                    message=(
                        normalized.message
                        or "Accessibility query failed during field extraction"
                    ),
                )
            diagnostics = normalized.diagnostics
            if diagnostics.get("truncated", False):
                truncated = True
                truncation_reason = _normalized_truncation_reason(diagnostics)
            for node in normalized.nodes:
                item_path = _owning_item_path(node, item_paths)
                if item_path is None or (item_path, field_name) in cache:
                    continue
                matched, _ = match_node(
                    node,
                    match,
                    self.resolver.profile.locale_aliases,
                )
                if not matched:
                    continue
                constraints_ok, _, _ = constraints_match(
                    node,
                    field.selector.constraints,
                )
                if not constraints_ok:
                    continue
                value = (
                    node_attribute(node, field.attribute)
                    if field.attribute is not None
                    else _node_summary(node)
                )
                cache[(item_path, field_name)] = _FieldExtraction(value=value)
        return cache, selector_diagnostics(
            query_count=query_count,
            node_count=node_count,
            truncated=truncated,
            truncation_reason=truncation_reason,
            failure_kind="selector_query_truncated" if truncated else None,
        )

    def _query_failed_collection(
        self,
        collection: CollectionDefinition,
        failure: SelectorDiagnostics,
        *,
        root_diagnostics: SelectorDiagnostics,
        item_diagnostics: SelectorDiagnostics | None = None,
    ) -> CollectionResult:
        item_diagnostics = item_diagnostics or selector_diagnostics()
        return CollectionResult(
            collection_id=collection.collection_id,
            profile_id=self.resolver.profile.profile_id,
            profile_version=self.resolver.profile.profile_version,
            status="failed",
            diagnostics=selector_diagnostics(
                tried_selectors=(collection.root_selector_id,),
                query_count=(
                    root_diagnostics.query_count
                    + item_diagnostics.query_count
                    + failure.query_count
                ),
                node_count=_collection_node_count(
                    collection,
                    root_diagnostics.node_count
                    + item_diagnostics.node_count
                    + failure.node_count,
                ),
                cache_status=root_diagnostics.cache_status,
                failure_kind="selector_query_failed",
                cause_failure_kind=failure.cause_failure_kind,
                retryable=failure.retryable,
                message=failure.message,
            ),
        )

    def _failed(
        self,
        collection_id: str,
        failure_kind: str,
        message: str,
    ) -> CollectionResult:
        return CollectionResult(
            collection_id=collection_id,
            profile_id=self.resolver.profile.profile_id,
            profile_version=self.resolver.profile.profile_version,
            status="failed",
            diagnostics=selector_diagnostics(
                failure_kind=failure_kind,
                message=message,
            ),
        )


def _node_summary(node: Mapping[str, Any]) -> JsonValue:
    for attribute in ("AXDescription", "AXTitle", "AXValue", "AXPlaceholderValue"):
        value = node_attribute(node, attribute)
        if value is not None:
            return value
    return node_ax_path(node)


def _computed_value(node: Mapping[str, Any], attribute: str | None) -> JsonValue:
    if attribute in {None, "summary"}:
        return _node_summary(node)
    if attribute == "elementRef":
        return _element_ref(node)
    return None


def _element_ref(node: Mapping[str, Any]) -> JsonValue:
    path = node_ax_path(node)
    if path is None:
        return None
    payload: dict[str, JsonValue] = {
        "kind": "accessibilityElement",
        "axPath": path,
        "role": node_role(node),
    }
    label = node_label(node)
    if label is not None:
        payload["label"] = label
    frame = node_frame(node)
    if frame is not None:
        payload["frame"] = {
            "x": frame.x,
            "y": frame.y,
            "width": frame.width,
            "height": frame.height,
        }
    actions = node_actions(node)
    if actions:
        payload["actions"] = list(actions)
    for key in ("enabled", "focused"):
        value = node.get(key)
        if isinstance(value, bool):
            payload[key] = value
    return payload


def _can_batch_descendant_field(field: FieldDefinition) -> bool:
    return (
        field.source == "descendant"
        and field.selector is not None
        and len(field.selector.steps) == 1
    )


def _owning_item_path(
    node: Mapping[str, Any],
    item_paths: list[str],
) -> str | None:
    node_path = node_ax_path(node)
    if node_path is None:
        return None
    matches = [
        item_path
        for item_path in item_paths
        if node_path.startswith(f"{item_path}/")
    ]
    if not matches:
        return None
    return max(matches, key=len)


def _collection_needs_item_actions(collection: CollectionDefinition) -> bool:
    return any(
        field.source == "computed" and field.attribute == "elementRef"
        for field in collection.fields.values()
    )


def _query_attributes(
    step: SelectorStep,
    constraints: tuple[SelectorConstraint, ...],
) -> list[str]:
    attributes = {
        "AXRole",
        "AXTitle",
        "AXValue",
        "AXDescription",
        "AXPlaceholderValue",
        "AXFrame",
        "AXHidden",
        "AXEnabled",
        "AXFocused",
    }
    attributes.update(step.match.attributes)
    if any(constraint.kind == "selected" for constraint in constraints):
        attributes.add("AXSelected")
    return sorted(attributes)


def _constraint_query_flags(
    constraints: tuple[SelectorConstraint, ...],
) -> dict[str, JsonValue]:
    flags: dict[str, JsonValue] = {}
    if any(constraint.kind == "hasChildRole" for constraint in constraints):
        flags["includeChildRoles"] = True
    if any(constraint.kind == "hasDescendantRole" for constraint in constraints):
        flags["includeDescendantRoles"] = True
    if any(constraint.kind == "minChildren" for constraint in constraints):
        flags["includeChildrenCount"] = True
    return flags


def _collection_node_count(
    collection: CollectionDefinition,
    node_count: int,
) -> int:
    if not collection.diagnostics.include_candidate_counts:
        return 0
    return node_count


def _collection_message(
    collection: CollectionDefinition,
    *,
    skipped: int,
    field_failures: int,
    fallback: str | None,
) -> str | None:
    if not skipped:
        return fallback
    parts: list[str] = []
    if collection.diagnostics.include_skipped_count:
        parts.append(f"skipped {skipped} item(s)")
    if collection.diagnostics.include_field_failures:
        parts.append(f"field failures {field_failures}")
    if parts:
        return "; ".join(parts)
    return "collection field extraction failed"


def _normalized_truncation_reason(
    diagnostics: Mapping[str, Any],
) -> str:
    raw_reason = diagnostics.get("truncationReason") or diagnostics.get(
        "truncation_reason"
    )
    if not isinstance(raw_reason, str) or not raw_reason.strip():
        return "query_truncated"
    reason = raw_reason.strip()
    normalized = reason.casefold().replace("-", "_").replace(" ", "_")
    if normalized.startswith("limit"):
        return "limit"
    if normalized in {"timebudget", "time_budget_exceeded"}:
        return "time_budget"
    return normalized


def _query_failure_diagnostics(
    outcome: _NormalizedQueryOutcome,
) -> SelectorDiagnostics:
    return selector_diagnostics(
        query_count=1,
        node_count=len(outcome.nodes),
        failure_kind="selector_query_failed",
        cause_failure_kind=(
            outcome.failure_kind or "accessibility_query_unavailable"
        ),
        retryable=outcome.retryable,
        message=outcome.message or "Accessibility query failed",
    )


def _field_query_failure(
    outcome: _NormalizedQueryOutcome,
) -> "_FieldExtraction":
    return _FieldExtraction(
        query_count=1,
        node_count=len(outcome.nodes),
        failure_kind="selector_query_failed",
        cause_failure_kind=(
            outcome.failure_kind or "accessibility_query_unavailable"
        ),
        retryable=outcome.retryable,
        message=outcome.message or "Accessibility query failed",
    )


@dataclass(frozen=True)
class _FieldExtraction:
    value: JsonValue | None = None
    query_count: int = 0
    node_count: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
    failure_kind: str | None = None
    cause_failure_kind: str | None = None
    retryable: bool | None = None
    message: str | None = None
