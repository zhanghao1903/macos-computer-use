"""Internal selector resolver built on bounded Accessibility queries."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .cache import SelectorCache
from .diagnostics import selector_diagnostics
from .matching import (
    constraints_match,
    confidence_score,
    effective_step_match,
    match_node,
    node_actions,
    node_ax_path,
    node_attribute,
    node_frame,
    node_label,
    node_role,
    relation_match,
)
from .models import (
    AccessibilitySelectorProfile,
    ElementRef,
    ElementSignature,
    Frame,
    JsonValue,
    ResolvedElement,
    SelectorCacheEntry,
    SelectorConstraint,
    SelectorDefinition,
    SelectorDiagnostics,
    SelectorEvidence,
    SelectorResult,
    SelectorRoot,
    SelectorStep,
)


class AccessibilityQueryRunner(Protocol):
    def __call__(
        self,
        *,
        root: Mapping[str, JsonValue],
        query: Mapping[str, JsonValue],
        include_raw: bool = False,
    ) -> Mapping[str, Any]:
        """Run one bounded Accessibility query and return its payload."""


@dataclass(frozen=True)
class _NormalizedQueryOutcome:
    available: bool
    snapshot_id: str | None
    nodes: tuple[Mapping[str, Any], ...]
    diagnostics: Mapping[str, Any]
    failure_kind: str | None = None
    message: str | None = None
    retryable: bool | None = None

    @property
    def succeeded(self) -> bool:
        return self.available and self.failure_kind is None


class SelectorResolver:
    """Resolve internal selector profiles using bounded query payloads."""

    def __init__(
        self,
        profile: AccessibilitySelectorProfile,
        query_runner: AccessibilityQueryRunner,
        *,
        cache: SelectorCache | None = None,
        app_bundle_id: str = "",
        window_fingerprint: str = "",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.profile = profile
        self.query_runner = query_runner
        self.cache = cache or SelectorCache()
        self.app_bundle_id = app_bundle_id
        self.window_fingerprint = window_fingerprint
        self._now = now or (lambda: datetime.now(UTC))

    def resolve(
        self,
        selector_id: str,
        *,
        debug: bool = False,
    ) -> SelectorResult:
        return self._resolve(selector_id, debug=debug, stack=())

    def _resolve(
        self,
        selector_id: str,
        *,
        debug: bool,
        stack: tuple[str, ...],
    ) -> SelectorResult:
        selector = self.profile.selectors.get(selector_id)
        if selector is None:
            return self._failed(
                selector_id,
                "selector_not_found",
                f"selector not found: {selector_id}",
                tried=stack + (selector_id,),
            )
        if selector_id in stack:
            return self._failed(
                selector_id,
                "selector_not_found",
                f"selector recursion includes {selector_id}",
                tried=stack + (selector_id,),
            )

        cache_status = "disabled"
        query_count = 0
        node_count = 0
        relation_anchors = self._resolve_relation_anchors(
            selector,
            debug=debug,
            stack=stack + (selector_id,),
        )
        if isinstance(relation_anchors, SelectorResult):
            return relation_anchors
        relation_anchor_elements, relation_query_count, relation_node_count = (
            relation_anchors
        )
        query_count += relation_query_count
        node_count += relation_node_count

        cached = self._cached_result(selector)
        if cached is not None:
            cache_status = "stale"
            if not self._cache_entry_expired(cached):
                validation = self._validate_cached(
                    selector,
                    cached,
                    debug=debug,
                    relation_anchor_elements=relation_anchor_elements.get(
                        len(selector.steps) - 1,
                        (),
                    ),
                )
                query_count += validation.diagnostics.query_count
                node_count += validation.diagnostics.node_count
                if validation.status == "resolved":
                    return self._with_resolution_context(
                        validation,
                        tried=stack + (selector_id,),
                        query_count=query_count,
                        node_count=node_count,
                        cache_status="hit",
                    )
                self.cache.delete(cached)
                if validation.diagnostics.failure_kind == "selector_query_failed":
                    return self._with_resolution_context(
                        validation,
                        tried=stack + (selector_id,),
                        query_count=query_count,
                        node_count=node_count,
                        cache_status="stale",
                    )
                cache_status = "stale"
            else:
                self.cache.delete(cached)
        elif selector.cache.mode != "disabled":
            cache_status = "miss"

        root_result = self._root_payload(selector.root, debug=debug, stack=stack)
        if isinstance(root_result, SelectorResult):
            return root_result
        root_payload = root_result

        all_candidates: list[ResolvedElement] = []
        current_roots: list[Mapping[str, JsonValue]] = [root_payload]
        for step_index, step in enumerate(selector.steps):
            step_candidates: list[ResolvedElement] = []
            is_final_step = step_index == len(selector.steps) - 1
            for step_root in current_roots:
                query_payload = self._query_payload(
                    step,
                    constraints=selector.constraints if is_final_step else (),
                )
                payload = self.query_runner(
                    root=step_root,
                    query=query_payload,
                    include_raw=debug,
                )
                query_count += 1
                normalized = _normalize_query_payload(payload)
                node_count += len(normalized.nodes)
                if not normalized.succeeded:
                    return self._query_failure_result(
                        selector,
                        normalized,
                        tried=stack + (selector_id,),
                        query_count=query_count,
                        node_count=node_count,
                        cache_status=cache_status,
                    )
                nodes = normalized.nodes
                diagnostics = normalized.diagnostics
                if diagnostics.get("truncated") is True:
                    return self._truncated_query_result(
                        selector,
                        diagnostics,
                        tried=stack + (selector_id,),
                        query_count=query_count,
                        node_count=node_count,
                        cache_status=cache_status,
                    )
                for node in nodes:
                    candidate = self._candidate_from_node(
                        selector,
                        step,
                        node,
                        normalized,
                        debug,
                        apply_constraints=is_final_step,
                        relation_anchor_elements=relation_anchor_elements.get(
                            step_index,
                            (),
                        ),
                    )
                    if candidate is not None:
                        step_candidates.append(candidate)
            if not step_candidates:
                all_candidates = []
                break
            if is_final_step:
                all_candidates = step_candidates
            else:
                current_roots = [
                    {
                        "kind": "axPath",
                        "axPath": candidate.element_ref.ax_path,
                    }
                    for candidate in step_candidates
                ]

        final_relation_anchors = relation_anchor_elements.get(
            len(selector.steps) - 1,
            (),
        )
        picked = self._pick(
            selector,
            all_candidates,
            anchor_elements=final_relation_anchors,
        )
        if picked is None:
            for fallback in selector.fallbacks:
                fallback_result = self._resolve(
                    fallback,
                    debug=debug,
                    stack=stack + (selector_id,),
                )
                if fallback_result.status == "resolved":
                    return fallback_result
                if fallback_result.diagnostics.failure_kind in {
                    "selector_query_failed",
                    "selector_query_truncated",
                }:
                    return self._with_resolution_context(
                        fallback_result,
                        tried=stack + (selector_id, fallback),
                        query_count=(
                            query_count + fallback_result.diagnostics.query_count
                        ),
                        node_count=(
                            node_count + fallback_result.diagnostics.node_count
                        ),
                        cache_status=fallback_result.diagnostics.cache_status,
                    )
            return SelectorResult(
                selector_id=selector.selector_id,
                profile_id=self.profile.profile_id,
                profile_version=self.profile.profile_version,
                status="not_found",
                diagnostics=selector_diagnostics(
                    tried_selectors=stack + (selector_id,),
                    query_count=query_count,
                    node_count=node_count,
                    cache_status=cache_status,
                    failure_kind="selector_not_found",
                    message="selector not found",
                ),
            )
        if picked == "ambiguous":
            return SelectorResult(
                selector_id=selector.selector_id,
                profile_id=self.profile.profile_id,
                profile_version=self.profile.profile_version,
                status="ambiguous",
                elements=tuple(all_candidates),
                snapshot_id=_first_snapshot_id(all_candidates),
                diagnostics=selector_diagnostics(
                    tried_selectors=stack + (selector_id,),
                    query_count=query_count,
                    node_count=node_count,
                    cache_status=cache_status,
                    failure_kind="selector_ambiguous",
                    message="selector matched multiple equivalent candidates",
                ),
            )

        elements = tuple(picked)
        for element in elements:
            self._update_cache(selector, element)
        return SelectorResult(
            selector_id=selector.selector_id,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            status="resolved",
            elements=elements,
            snapshot_id=elements[0].element_ref.snapshot_id if elements else None,
            diagnostics=selector_diagnostics(
                tried_selectors=stack + (selector_id,),
                query_count=query_count,
                node_count=node_count,
                cache_status=cache_status,
            ),
        )

    def _candidate_from_node(
        self,
        selector: SelectorDefinition,
        step: SelectorStep,
        node: Mapping[str, Any],
        outcome: _NormalizedQueryOutcome,
        debug: bool,
        *,
        apply_constraints: bool,
        relation_anchor_elements: tuple[ResolvedElement, ...] = (),
    ) -> ResolvedElement | None:
        step_match = effective_step_match(step)
        matched, evidence = match_node(node, step_match, self.profile.locale_aliases)
        if not matched:
            return None
        matched_constraints: list[str] = []
        score_breakdown = dict(evidence.score_breakdown)
        constraint_score = 0.0
        if apply_constraints:
            constraints_ok, constraint_names, constraint_score = constraints_match(
                node,
                selector.constraints,
            )
            if not constraints_ok:
                return None
            matched_constraints.extend(constraint_names)
        if step.relation is not None:
            candidate_frame = node_frame(node)
            anchor_frames = tuple(
                anchor.frame
                for anchor in relation_anchor_elements
                if anchor.frame is not None
            )
            if not relation_match(candidate_frame, anchor_frames, step.relation):
                return None
            matched_constraints.append(f"relation:{step.relation.relation}")
            score_breakdown["geometry"] = 1.0
            evidence = SelectorEvidence(
                matched_attributes=evidence.matched_attributes,
                matched_actions=evidence.matched_actions,
                matched_constraints=evidence.matched_constraints,
                score_breakdown=score_breakdown,
                debug_attributes=evidence.debug_attributes,
            )
        confidence = confidence_score(
            evidence,
            constraint_score=constraint_score,
            policy=selector.confidence,
            include_structure=bool(selector.constraints) and apply_constraints,
            include_geometry=step.relation is not None,
        )
        if confidence < selector.confidence.minimum:
            return None
        path = node_ax_path(node)
        if path is None:
            return None
        snapshot_id = outcome.snapshot_id or ""
        role = node_role(node)
        actions = node_actions(node)
        signature = ElementSignature(
            role=role,
            attributes=self._signature_attributes(selector, node),
            actions=actions,
            ancestor_hints=tuple(str(item) for item in node.get("ancestorHints", ())),
            frame_hash=_frame_hash(node),
        )
        if matched_constraints:
            evidence = SelectorEvidence(
                matched_attributes=evidence.matched_attributes,
                matched_actions=evidence.matched_actions,
                matched_constraints=tuple(matched_constraints),
                score_breakdown=evidence.score_breakdown,
                debug_attributes=dict(node) if debug else None,
            )
        return ResolvedElement(
            element_ref=ElementRef(
                kind="accessibilityElement",
                snapshot_id=snapshot_id,
                ax_path=path,
                role=role,
                signature=signature,
            ),
            selector_id=selector.selector_id,
            label=node_label(node),
            frame=node_frame(node),
            role=role,
            actions=actions,
            confidence=confidence,
            evidence=evidence,
        )

    def _cached_result(
        self,
        selector: SelectorDefinition,
    ) -> SelectorCacheEntry | None:
        if (
            selector.cache.mode == "disabled"
            or selector.pick == "all"
            or len(selector.steps) != 1
        ):
            return None
        return self.cache.get(
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            selector_id=selector.selector_id,
            app_bundle_id=self.app_bundle_id,
            window_fingerprint=self.window_fingerprint,
        )

    def _validate_cached(
        self,
        selector: SelectorDefinition,
        entry: SelectorCacheEntry,
        *,
        debug: bool,
        relation_anchor_elements: tuple[ResolvedElement, ...] = (),
    ) -> SelectorResult:
        if not selector.steps:
            return self._failed(
                selector.selector_id,
                "selector_cache_stale",
                "cached selector has no validation step",
                cache_status="stale",
            )
        step = selector.steps[-1]
        payload = self.query_runner(
            root={"kind": "axPath", "axPath": entry.element_ref.ax_path},
            query=self._cache_validation_query(selector, step),
            include_raw=debug,
        )
        normalized = _normalize_query_payload(payload)
        if not normalized.succeeded:
            return self._query_failure_result(
                selector,
                normalized,
                tried=(selector.selector_id,),
                query_count=1,
                node_count=len(normalized.nodes),
                cache_status="stale",
            )
        nodes = normalized.nodes
        if normalized.diagnostics.get("truncated") is True and not (
            len(nodes) == 1
            and _normalized_truncation_reason(normalized.diagnostics) == "limit"
        ):
            return self._truncated_query_result(
                selector,
                normalized.diagnostics,
                tried=(selector.selector_id,),
                query_count=1,
                node_count=len(nodes),
                cache_status="stale",
            )
        if not nodes:
            return self._failed(
                selector.selector_id,
                "selector_cache_stale",
                "cached selector path is stale",
                query_count=1,
                cache_status="stale",
            )
        node = nodes[0]
        if node_role(node) != entry.element_ref.signature.role:
            return self._failed(
                selector.selector_id,
                "selector_cache_stale",
                "cached selector signature no longer matches",
                query_count=1,
                node_count=1,
                cache_status="stale",
            )
        for attribute, expected in entry.element_ref.signature.attributes.items():
            if node_attribute(node, attribute) != expected:
                return self._failed(
                    selector.selector_id,
                    "selector_cache_stale",
                    "cached selector attributes no longer match",
                    query_count=1,
                    node_count=1,
                    cache_status="stale",
                )
        element = self._candidate_from_node(
            selector,
            step,
            node,
            normalized,
            debug,
            apply_constraints=True,
            relation_anchor_elements=relation_anchor_elements,
        )
        if element is None:
            return self._failed(
                selector.selector_id,
                "selector_cache_stale",
                "cached selector no longer satisfies the selector predicate",
                query_count=1,
                node_count=1,
                cache_status="stale",
            )
        return SelectorResult(
            selector_id=selector.selector_id,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            status="resolved",
            elements=(element,),
            snapshot_id=element.element_ref.snapshot_id,
            diagnostics=selector_diagnostics(
                tried_selectors=(selector.selector_id,),
                query_count=1,
                node_count=1,
                cache_status="hit",
            ),
        )

    def _cache_validation_query(
        self,
        selector: SelectorDefinition,
        step: SelectorStep,
    ) -> dict[str, JsonValue]:
        query = self._query_payload(step, constraints=selector.constraints)
        query["scope"] = "self"
        query["maxDepth"] = 0
        query["limit"] = 1
        query["timeBudgetMs"] = min(step.time_budget_ms, 500)
        attributes = {
            str(attribute)
            for attribute in query.get("attributes", [])
            if isinstance(attribute, str)
        }
        attributes.update(selector.cache.key_attributes)
        query["attributes"] = sorted(attributes)
        return query

    def _cache_entry_expired(self, entry: SelectorCacheEntry) -> bool:
        if entry.expires_at is None:
            return False
        try:
            expires_at = datetime.fromisoformat(entry.expires_at)
        except ValueError:
            return True
        now = self._now()
        if expires_at.tzinfo is None and now.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        if expires_at.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=expires_at.tzinfo)
        return now >= expires_at

    def _root_payload(
        self,
        root: SelectorRoot,
        *,
        debug: bool,
        stack: tuple[str, ...],
    ) -> Mapping[str, JsonValue] | SelectorResult:
        if root.kind == "focusedWindow":
            return {"kind": "focusedWindow"}
        if root.kind == "frontmostApp":
            return {"kind": "frontmostApp"}
        if root.kind == "axPath":
            return {"kind": "axPath", "axPath": root.ax_path or ""}
        if root.kind == "selector" and root.selector_id:
            resolved = self._resolve(root.selector_id, debug=debug, stack=stack)
            if resolved.status != "resolved" or not resolved.elements:
                return resolved
            return {
                "kind": "axPath",
                "axPath": resolved.elements[0].element_ref.ax_path,
            }
        return self._failed(
            root.selector_id or "unknown",
            "selector_not_found",
            "selector root could not be resolved",
        )

    def _resolve_relation_anchors(
        self,
        selector: SelectorDefinition,
        *,
        debug: bool,
        stack: tuple[str, ...],
    ) -> tuple[
        dict[int, tuple[ResolvedElement, ...]],
        int,
        int,
    ] | SelectorResult:
        anchors: dict[int, tuple[ResolvedElement, ...]] = {}
        query_count = 0
        node_count = 0
        for step_index, step in enumerate(selector.steps):
            if step.relation is None:
                continue
            anchor_selector_id = step.relation.anchor_selector_id
            anchor_result = self._resolve(
                anchor_selector_id,
                debug=debug,
                stack=stack,
            )
            query_count += anchor_result.diagnostics.query_count
            node_count += anchor_result.diagnostics.node_count
            if anchor_result.status != "resolved" or not anchor_result.elements:
                return SelectorResult(
                    selector_id=selector.selector_id,
                    profile_id=self.profile.profile_id,
                    profile_version=self.profile.profile_version,
                    status=(
                        "failed"
                        if anchor_result.status in {"failed", "ambiguous"}
                        else "not_found"
                    ),
                    diagnostics=selector_diagnostics(
                        tried_selectors=stack + (anchor_selector_id,),
                        query_count=query_count,
                        node_count=node_count,
                        truncated=anchor_result.diagnostics.truncated,
                        truncation_reason=anchor_result.diagnostics.truncation_reason,
                        cache_status=anchor_result.diagnostics.cache_status,
                        failure_kind=(
                            anchor_result.diagnostics.failure_kind
                            or "selector_not_found"
                        ),
                        cause_failure_kind=(
                            anchor_result.diagnostics.cause_failure_kind
                        ),
                        retryable=anchor_result.diagnostics.retryable,
                        message=(
                            "relation anchor could not be resolved: "
                            f"{anchor_selector_id}"
                        ),
                    ),
                )
            anchors[step_index] = anchor_result.elements
        return anchors, query_count, node_count

    def _query_payload(
        self,
        step: SelectorStep,
        *,
        constraints: tuple[SelectorConstraint, ...] = (),
    ) -> dict[str, JsonValue]:
        attributes = {
            "AXFrame",
            "AXRole",
            "AXTitle",
            "AXValue",
            "AXDescription",
            "AXPlaceholderValue",
        }
        for attribute in step.match.attributes:
            attributes.add(attribute)
        if step.match.enabled is not None:
            attributes.add("AXEnabled")
        if step.match.visible is not None:
            attributes.add("AXHidden")
        if any(
            getattr(constraint, "kind", None) == "selected"
            for constraint in constraints
        ):
            attributes.add("AXSelected")
        payload: dict[str, JsonValue] = {
            "scope": step.scope,
            "maxDepth": step.max_depth,
            "limit": step.limit,
            "timeBudgetMs": step.time_budget_ms,
            "attributes": sorted(attributes),
            "actions": bool(step.match.actions_include),
            "match": {
                "roleIn": list(step.role_in or step.match.role_in),
            },
        }
        if any(
            getattr(constraint, "kind", None) == "hasChildRole"
            for constraint in constraints
        ):
            payload["includeChildRoles"] = True
        if any(
            getattr(constraint, "kind", None) == "hasDescendantRole"
            for constraint in constraints
        ):
            payload["includeDescendantRoles"] = True
        if any(
            getattr(constraint, "kind", None) == "minChildren"
            for constraint in constraints
        ):
            payload["includeChildrenCount"] = True
        return payload

    def _signature_attributes(
        self,
        selector: SelectorDefinition,
        node: Mapping[str, Any],
    ) -> dict[str, JsonValue]:
        attributes: dict[str, JsonValue] = {}
        for attr in selector.cache.key_attributes:
            attributes[attr] = node_attribute(node, attr)
        return attributes

    def _update_cache(
        self,
        selector: SelectorDefinition,
        element: ResolvedElement,
    ) -> None:
        if (
            selector.cache.mode != "readWrite"
            or selector.pick == "all"
            or len(selector.steps) != 1
        ):
            return
        now = self._now()
        expires_at = None
        if selector.cache.ttl_seconds is not None:
            expires_at = (
                now + timedelta(seconds=selector.cache.ttl_seconds)
            ).isoformat()
        self.cache.put(
            SelectorCacheEntry(
                profile_id=self.profile.profile_id,
                profile_version=self.profile.profile_version,
                selector_id=selector.selector_id,
                app_bundle_id=self.app_bundle_id,
                window_fingerprint=self.window_fingerprint,
                element_ref=element.element_ref,
                created_at=now.isoformat(),
                expires_at=expires_at,
            )
        )

    def _pick(
        self,
        selector: SelectorDefinition,
        candidates: list[ResolvedElement],
        *,
        anchor_elements: tuple[ResolvedElement, ...] = (),
    ) -> tuple[ResolvedElement, ...] | str | None:
        if not candidates:
            return None
        if selector.pick == "all":
            return tuple(candidates)
        if selector.pick == "first":
            return (candidates[0],)
        if selector.pick == "largestArea":
            return (max(candidates, key=_area),)
        if selector.pick == "nearestToAnchor":
            return _nearest_to_anchor(candidates, anchor_elements)
        candidates = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        if len(candidates) > 1 and candidates[0].confidence == candidates[1].confidence:
            return "ambiguous"
        return (candidates[0],)

    def _query_failure_result(
        self,
        selector: SelectorDefinition,
        outcome: _NormalizedQueryOutcome,
        *,
        tried: tuple[str, ...],
        query_count: int,
        node_count: int,
        cache_status: str,
    ) -> SelectorResult:
        cause = outcome.failure_kind or "accessibility_query_unavailable"
        message = outcome.message or f"Accessibility query failed: {cause}"
        return SelectorResult(
            selector_id=selector.selector_id,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            status="failed",
            diagnostics=selector_diagnostics(
                tried_selectors=tried,
                query_count=query_count,
                node_count=node_count,
                cache_status=cache_status,
                failure_kind="selector_query_failed",
                cause_failure_kind=cause,
                retryable=outcome.retryable,
                message=message,
            ),
        )

    def _truncated_query_result(
        self,
        selector: SelectorDefinition,
        diagnostics: Mapping[str, Any],
        *,
        tried: tuple[str, ...],
        query_count: int,
        node_count: int,
        cache_status: str,
    ) -> SelectorResult:
        reason = _normalized_truncation_reason(diagnostics)
        return SelectorResult(
            selector_id=selector.selector_id,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            status="failed",
            diagnostics=selector_diagnostics(
                tried_selectors=tried,
                query_count=query_count,
                node_count=node_count,
                truncated=True,
                truncation_reason=reason,
                cache_status=cache_status,
                failure_kind="selector_query_truncated",
                message=f"selector query truncated: {reason}",
            ),
        )

    def _with_resolution_context(
        self,
        result: SelectorResult,
        *,
        tried: tuple[str, ...],
        query_count: int,
        node_count: int,
        cache_status: str,
    ) -> SelectorResult:
        diagnostics = result.diagnostics
        return SelectorResult(
            selector_id=result.selector_id,
            profile_id=result.profile_id,
            profile_version=result.profile_version,
            status=result.status,
            elements=result.elements,
            snapshot_id=result.snapshot_id,
            diagnostics=selector_diagnostics(
                tried_selectors=tried,
                query_count=query_count,
                node_count=node_count,
                truncated=diagnostics.truncated,
                truncation_reason=diagnostics.truncation_reason,
                cache_status=cache_status,
                failure_kind=diagnostics.failure_kind,
                cause_failure_kind=diagnostics.cause_failure_kind,
                retryable=diagnostics.retryable,
                message=diagnostics.message,
            ),
        )

    def _failed(
        self,
        selector_id: str,
        failure_kind: str,
        message: str,
        *,
        tried: tuple[str, ...] = (),
        query_count: int = 0,
        node_count: int = 0,
        cache_status: str = "disabled",
        cause_failure_kind: str | None = None,
        retryable: bool | None = None,
    ) -> SelectorResult:
        return SelectorResult(
            selector_id=selector_id,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            status="failed",
            diagnostics=selector_diagnostics(
                tried_selectors=tried or (selector_id,),
                query_count=query_count,
                node_count=node_count,
                cache_status=cache_status,
                failure_kind=failure_kind,
                cause_failure_kind=cause_failure_kind,
                retryable=retryable,
                message=message,
            ),
        )


def _normalize_query_payload(payload: Mapping[str, Any]) -> _NormalizedQueryOutcome:
    query_payload, unwrap_error = _unwrap_query_payload(payload)
    if unwrap_error is not None:
        return _invalid_query_outcome(unwrap_error)

    schema = query_payload.get("schema")
    if "schema" in query_payload and (
        not isinstance(schema, str)
        or schema != "macos.accessibility.query.v1"
    ):
        return _invalid_query_outcome("Accessibility query schema is invalid.")

    diagnostics_value = query_payload.get("diagnostics")
    if "diagnostics" in query_payload and not isinstance(
        diagnostics_value,
        Mapping,
    ):
        return _invalid_query_outcome(
            "Accessibility query diagnostics must be a mapping."
        )
    diagnostics = (
        dict(diagnostics_value) if isinstance(diagnostics_value, Mapping) else {}
    )

    error_value = query_payload.get("error")
    if "error" in query_payload and not isinstance(error_value, Mapping):
        return _invalid_query_outcome(
            "Accessibility query error must be a mapping."
        )
    error = dict(error_value) if isinstance(error_value, Mapping) else {}

    failure_kind, failure_error = _consistent_query_string(
        (query_payload, diagnostics, error),
        ("failureKind", "failure_kind"),
        "failure kind",
    )
    if failure_error is not None:
        return _invalid_query_outcome(failure_error)

    retryable, retryable_error = _consistent_query_bool(
        (query_payload, diagnostics, error),
        ("retryable",),
        "retryable",
    )
    if retryable_error is not None:
        return _invalid_query_outcome(retryable_error)

    available_value = query_payload.get("available")
    if "available" in query_payload and not isinstance(available_value, bool):
        return _invalid_query_outcome(
            "Accessibility query available must be a boolean."
        )
    available = available_value if isinstance(available_value, bool) else None

    status_value = query_payload.get("status")
    if "status" in query_payload and (
        not isinstance(status_value, str) or status_value not in {"ok", "failed"}
    ):
        return _invalid_query_outcome(
            "Accessibility query status must be 'ok' or 'failed'."
        )
    status = status_value if isinstance(status_value, str) else None
    if schema is None and status is not None:
        return _invalid_query_outcome(
            "Legacy Accessibility query responses must not include status."
        )

    is_failure = available is False or status == "failed" or failure_kind is not None
    if available is True and (status == "failed" or failure_kind is not None):
        return _invalid_query_outcome(
            "Accessibility query success fields contradict failure evidence."
        )
    if status == "ok" and (available is False or failure_kind is not None):
        return _invalid_query_outcome(
            "Accessibility query status contradicts failure evidence."
        )

    raw_nodes = query_payload.get("nodes")
    if "nodes" in query_payload:
        if not isinstance(raw_nodes, list | tuple):
            return _invalid_query_outcome(
                "Accessibility query nodes must be a list."
            )
        if any(not isinstance(node, Mapping) for node in raw_nodes):
            return _invalid_query_outcome(
                "Accessibility query nodes must contain only mappings."
            )
        nodes = tuple(dict(node) for node in raw_nodes)
    else:
        nodes = ()

    message = _bounded_message(
        _first_non_empty_string(
            query_payload.get("message"),
            diagnostics.get("message"),
            error.get("message"),
        )
    )

    if is_failure:
        return _NormalizedQueryOutcome(
            available=False,
            snapshot_id=_first_non_empty_string(
                query_payload.get("snapshotId"),
                query_payload.get("snapshot_id"),
            ),
            nodes=nodes,
            diagnostics=diagnostics,
            failure_kind=failure_kind,
            message=message,
            retryable=retryable,
        )

    if "nodes" not in query_payload:
        return _invalid_query_outcome(
            "Accessibility query success response is missing nodes."
        )
    if "diagnostics" not in query_payload:
        return _invalid_query_outcome(
            "Accessibility query success response is missing diagnostics."
        )
    if "truncated" not in diagnostics or not isinstance(
        diagnostics.get("truncated"),
        bool,
    ):
        return _invalid_query_outcome(
            "Accessibility query diagnostics.truncated must be a boolean."
        )

    snapshot_id = _first_non_empty_string(
        query_payload.get("snapshotId"),
        query_payload.get("snapshot_id"),
    )
    return _NormalizedQueryOutcome(
        available=True,
        snapshot_id=snapshot_id,
        nodes=nodes,
        diagnostics=diagnostics,
        failure_kind=failure_kind,
        message=message,
        retryable=retryable,
    )


def _unwrap_query_payload(
    payload: Mapping[str, Any],
) -> tuple[Mapping[str, Any], str | None]:
    if "accessibilityQuery" in payload:
        direct = payload.get("accessibilityQuery")
        if not isinstance(direct, Mapping):
            return {}, "Accessibility query wrapper must contain a mapping."
        return direct, None
    if "observation" in payload:
        observation = payload.get("observation")
        if not isinstance(observation, Mapping):
            return {}, "Accessibility query observation must be a mapping."
        if "accessibilityQuery" in observation:
            wrapped = observation.get("accessibilityQuery")
            if not isinstance(wrapped, Mapping):
                return {}, "Accessibility query observation wrapper is malformed."
            return wrapped, None
        if any(
            key in observation
            for key in (
                "schema",
                "available",
                "status",
                "failureKind",
                "failure_kind",
                "nodes",
                "diagnostics",
            )
        ):
            return observation, None
        return {}, "Accessibility query observation payload is missing."
    return payload, None


def _invalid_query_outcome(message: str) -> _NormalizedQueryOutcome:
    return _NormalizedQueryOutcome(
        available=False,
        snapshot_id=None,
        nodes=(),
        diagnostics={},
        failure_kind="accessibility_query_failed",
        message=_bounded_message(message),
        retryable=False,
    )


def _consistent_query_string(
    containers: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
    field_name: str,
) -> tuple[str | None, str | None]:
    values: list[str] = []
    for container in containers:
        for key in keys:
            if key not in container:
                continue
            value = container[key]
            if not isinstance(value, str) or not value.strip():
                return None, f"Accessibility query {field_name} must be a string."
            values.append(value.strip())
    if len(set(values)) > 1:
        return None, f"Accessibility query {field_name} values conflict."
    return (values[0] if values else None), None


def _consistent_query_bool(
    containers: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
    field_name: str,
) -> tuple[bool | None, str | None]:
    values: list[bool] = []
    for container in containers:
        for key in keys:
            if key not in container:
                continue
            value = container[key]
            if not isinstance(value, bool):
                return None, f"Accessibility query {field_name} must be a boolean."
            values.append(value)
    if len(set(values)) > 1:
        return None, f"Accessibility query {field_name} values conflict."
    return (values[0] if values else None), None


def _first_non_empty_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_bool(*values: object) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
    return None


def _bounded_message(value: str | None, *, limit: int = 500) -> str | None:
    if value is None:
        return None
    if len(value) <= limit:
        return value
    marker = "...<truncated>"
    return f"{value[: limit - len(marker)]}{marker}"


def _normalized_truncation_reason(diagnostics: Mapping[str, Any]) -> str:
    raw_reason = diagnostics.get("truncationReason") or diagnostics.get(
        "truncation_reason"
    )
    if not isinstance(raw_reason, str) or not raw_reason.strip():
        return "query_truncated"
    normalized = raw_reason.strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized.startswith("limit"):
        return "limit"
    if normalized in {"timebudget", "time_budget_exceeded"}:
        return "time_budget"
    return normalized


def _area(element: ResolvedElement) -> float:
    if element.frame is None:
        return 0.0
    return element.frame.width * element.frame.height


def _nearest_to_anchor(
    candidates: list[ResolvedElement],
    anchor_elements: tuple[ResolvedElement, ...],
) -> tuple[ResolvedElement, ...] | str | None:
    anchor_frames = tuple(
        element.frame for element in anchor_elements if element.frame is not None
    )
    if not anchor_frames:
        return None
    scored: list[tuple[float, ResolvedElement]] = []
    for candidate in candidates:
        if candidate.frame is None:
            continue
        scored.append(
            (
                min(
                    _center_distance(candidate.frame, anchor_frame)
                    for anchor_frame in anchor_frames
                ),
                candidate,
            )
        )
    if not scored:
        return None
    scored = sorted(scored, key=lambda item: item[0])
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return "ambiguous"
    return (scored[0][1],)


def _center_distance(first: Frame, second: Frame) -> float:
    first_center_x = first.x + first.width / 2
    first_center_y = first.y + first.height / 2
    second_center_x = second.x + second.width / 2
    second_center_y = second.y + second.height / 2
    return (
        (first_center_x - second_center_x) ** 2
        + (first_center_y - second_center_y) ** 2
    ) ** 0.5


def _frame_hash(node: Mapping[str, Any]) -> str | None:
    frame = node_frame(node)
    if frame is None:
        return None
    return f"{frame.x:.0f}:{frame.y:.0f}:{frame.width:.0f}:{frame.height:.0f}"


def _first_snapshot_id(elements: list[ResolvedElement]) -> str | None:
    if not elements:
        return None
    return elements[0].element_ref.snapshot_id
