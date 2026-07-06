"""Collection extraction for internal selector profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .diagnostics import selector_diagnostics
from .matching import (
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
    SelectorDiagnostics,
)
from .resolver import SelectorResolver, _normalize_query_payload
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
                    node_count=root.diagnostics.node_count,
                    truncated=root.diagnostics.truncated,
                    truncation_reason=root.diagnostics.truncation_reason,
                    failure_kind=root.diagnostics.failure_kind or "selector_not_found",
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
        has_more = len(item_nodes) > effective_limit
        item_nodes = item_nodes[:effective_limit]

        items: list[dict[str, JsonValue]] = []
        skipped = 0
        field_failures = 0
        field_query_count = 0
        field_node_count = 0
        field_truncated = False
        field_truncation_reason: str | None = None
        for item_node in item_nodes:
            item, field_diagnostics = self._extract_item(
                collection,
                item_node,
                debug=debug,
            )
            field_query_count += field_diagnostics.query_count
            field_node_count += field_diagnostics.node_count
            if field_diagnostics.truncated:
                field_truncated = True
                field_truncation_reason = field_diagnostics.truncation_reason
            if item is None:
                skipped += 1
                field_failures += 1
                continue
            items.append(item)

        status = "resolved"
        truncated = item_diagnostics.truncated or field_truncated
        truncation_reason = (
            item_diagnostics.truncation_reason
            or field_truncation_reason
        )
        if skipped or truncated:
            status = "partial" if items else "failed"
        diagnostics = selector_diagnostics(
            tried_selectors=(collection.root_selector_id,),
            query_count=(
                root.diagnostics.query_count
                + item_diagnostics.query_count
                + field_query_count
            ),
            node_count=(
                root.diagnostics.node_count
                + item_diagnostics.node_count
                + field_node_count
            ),
            truncated=truncated,
            truncation_reason=truncation_reason,
            cache_status=root.diagnostics.cache_status,
            failure_kind=(
                "selector_field_missing"
                if skipped
                else (
                    "selector_query_truncated"
                    if truncated
                    else item_diagnostics.failure_kind
                )
            ),
            message=(
                f"skipped {skipped} item(s); field failures {field_failures}"
                if skipped
                else item_diagnostics.message
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
                "attributes": [
                    "AXRole",
                    "AXTitle",
                    "AXValue",
                    "AXDescription",
                    "AXPlaceholderValue",
                    "AXFrame",
                    "AXEnabled",
                    "AXFocused",
                ],
                "actions": bool(step.match.actions_include)
                or _collection_needs_item_actions(collection),
                "match": {"roleIn": list(step.role_in or step.match.role_in)},
            },
            include_raw=debug,
        )
        normalized = _normalize_query_payload(payload)
        match = effective_step_match(step)
        nodes = [
            node
            for node in normalized["nodes"]
            if match_node(node, match, self.resolver.profile.locale_aliases)[0]
        ]
        diagnostics = normalized["diagnostics"]
        return nodes, selector_diagnostics(
            query_count=1,
            node_count=len(normalized["nodes"]),
            truncated=bool(diagnostics.get("truncated", False)),
            truncation_reason=(
                str(
                    diagnostics.get("truncationReason")
                    or diagnostics.get("truncation_reason")
                )
                if diagnostics.get("truncated", False)
                else None
            ),
            failure_kind=(
                "selector_query_truncated"
                if diagnostics.get("truncated", False)
                else None
            ),
        )

    def _extract_item(
        self,
        collection: CollectionDefinition,
        item_node: Mapping[str, Any],
        *,
        debug: bool,
    ) -> tuple[dict[str, JsonValue] | None, SelectorDiagnostics]:
        output: dict[str, JsonValue] = {}
        query_count = 0
        node_count = 0
        truncated = False
        truncation_reason: str | None = None
        for field_name, field in collection.fields.items():
            field_result = self._extract_field(item_node, field, debug=debug)
            query_count += field_result.query_count
            node_count += field_result.node_count
            if field_result.truncated:
                truncated = True
                truncation_reason = field_result.truncation_reason
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
        step = field.selector.steps[0]
        match = effective_step_match(step)
        payload = self.resolver.query_runner(
            root={"kind": "axPath", "axPath": item_path},
            query={
                "scope": step.scope,
                "maxDepth": step.max_depth,
                "limit": step.limit,
                "timeBudgetMs": step.time_budget_ms,
                "attributes": [
                    "AXRole",
                    "AXTitle",
                    "AXValue",
                    "AXDescription",
                    "AXPlaceholderValue",
                ],
                "actions": bool(step.match.actions_include),
                "match": {"roleIn": list(step.role_in or step.match.role_in)},
            },
            include_raw=debug,
        )
        normalized = _normalize_query_payload(payload)
        diagnostics = normalized["diagnostics"]
        truncated = bool(diagnostics.get("truncated", False))
        truncation_reason = (
            str(
                diagnostics.get("truncationReason")
                or diagnostics.get("truncation_reason")
            )
            if truncated
            else None
        )
        for node in normalized["nodes"]:
            if match_node(node, match, self.resolver.profile.locale_aliases)[0]:
                if field.attribute is not None:
                    return _FieldExtraction(
                        value=node_attribute(node, field.attribute),
                        query_count=1,
                        node_count=len(normalized["nodes"]),
                        truncated=truncated,
                        truncation_reason=truncation_reason,
                    )
                return _FieldExtraction(
                    value=_node_summary(node),
                    query_count=1,
                    node_count=len(normalized["nodes"]),
                    truncated=truncated,
                    truncation_reason=truncation_reason,
                )
        return _FieldExtraction(
            query_count=1,
            node_count=len(normalized["nodes"]),
            truncated=truncated,
            truncation_reason=truncation_reason,
            failure_kind="selector_query_truncated" if truncated else None,
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


def _collection_needs_item_actions(collection: CollectionDefinition) -> bool:
    return any(
        field.source == "computed" and field.attribute == "elementRef"
        for field in collection.fields.values()
    )


@dataclass(frozen=True)
class _FieldExtraction:
    value: JsonValue | None = None
    query_count: int = 0
    node_count: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
    failure_kind: str | None = None
