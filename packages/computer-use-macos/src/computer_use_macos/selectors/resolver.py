"""Internal selector resolver built on bounded Accessibility queries."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
)
from .models import (
    AccessibilitySelectorProfile,
    ElementRef,
    ElementSignature,
    JsonValue,
    ResolvedElement,
    SelectorCacheEntry,
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
        cached = self._cached_result(selector)
        if cached is not None:
            cache_status = "hit"
            query_count += 1
            validation = self._validate_cached(selector, cached, debug=debug)
            query_count += validation.diagnostics.query_count
            node_count += validation.diagnostics.node_count
            if validation.status == "resolved":
                return validation
            cache_status = "stale"
            self.cache.delete(cached)
        elif selector.cache.mode != "disabled":
            cache_status = "miss"

        root_result = self._root_payload(selector.root, debug=debug, stack=stack)
        if isinstance(root_result, SelectorResult):
            return root_result
        root_payload = root_result

        all_candidates: list[ResolvedElement] = []
        current_roots: list[Mapping[str, JsonValue]] = [root_payload]
        truncated = False
        truncation_reason: str | None = None
        for step_index, step in enumerate(selector.steps):
            step_candidates: list[ResolvedElement] = []
            is_final_step = step_index == len(selector.steps) - 1
            for step_root in current_roots:
                query_payload = self._query_payload(step)
                payload = self.query_runner(
                    root=step_root,
                    query=query_payload,
                    include_raw=debug,
                )
                query_count += 1
                normalized = _normalize_query_payload(payload)
                nodes = normalized["nodes"]
                node_count += len(nodes)
                diagnostics = normalized["diagnostics"]
                if bool(diagnostics.get("truncated", False)):
                    truncated = True
                    truncation_reason = str(
                        diagnostics.get("truncationReason")
                        or diagnostics.get("truncation_reason")
                        or "query truncated"
                    )
                for node in nodes:
                    candidate = self._candidate_from_node(
                        selector,
                        step,
                        node,
                        normalized,
                        debug,
                        apply_constraints=is_final_step,
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

        picked = self._pick(selector, all_candidates)
        if picked is None:
            for fallback in selector.fallbacks:
                fallback_result = self._resolve(
                    fallback,
                    debug=debug,
                    stack=stack + (selector_id,),
                )
                if fallback_result.status == "resolved":
                    return fallback_result
            failure_kind = "selector_query_truncated" if truncated else "selector_not_found"
            return SelectorResult(
                selector_id=selector.selector_id,
                profile_id=self.profile.profile_id,
                profile_version=self.profile.profile_version,
                status="failed" if truncated else "not_found",
                diagnostics=selector_diagnostics(
                    tried_selectors=stack + (selector_id,),
                    query_count=query_count,
                    node_count=node_count,
                    truncated=truncated,
                    truncation_reason=truncation_reason,
                    cache_status=cache_status,
                    failure_kind=failure_kind,
                    message="selector query truncated" if truncated else "selector not found",
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
                    truncated=truncated,
                    truncation_reason=truncation_reason,
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
                truncated=truncated,
                truncation_reason=truncation_reason,
                cache_status=cache_status,
            ),
        )

    def _candidate_from_node(
        self,
        selector: SelectorDefinition,
        step: SelectorStep,
        node: Mapping[str, Any],
        payload: Mapping[str, Any],
        debug: bool,
        *,
        apply_constraints: bool,
    ) -> ResolvedElement | None:
        step_match = effective_step_match(step)
        matched, evidence = match_node(node, step_match, self.profile.locale_aliases)
        if not matched:
            return None
        matched_constraints: tuple[str, ...] = ()
        constraint_score = 0.0
        if apply_constraints:
            constraints_ok, matched_constraints, constraint_score = constraints_match(
                node,
                selector.constraints,
            )
            if not constraints_ok:
                return None
        confidence = confidence_score(evidence, constraint_score=constraint_score)
        if confidence < selector.confidence.minimum:
            return None
        path = node_ax_path(node)
        if path is None:
            return None
        snapshot_id = str(payload.get("snapshotId") or "")
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
                matched_constraints=matched_constraints,
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
        if selector.cache.mode == "disabled":
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
    ) -> SelectorResult:
        payload = self.query_runner(
            root={"kind": "axPath", "axPath": entry.element_ref.ax_path},
            query={
                "scope": "self",
                "maxDepth": 0,
                "limit": 1,
                "timeBudgetMs": 500,
                "attributes": ["AXRole", *selector.cache.key_attributes],
                "actions": True,
            },
            include_raw=debug,
        )
        normalized = _normalize_query_payload(payload)
        nodes = normalized["nodes"]
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
        element = ResolvedElement(
            element_ref=entry.element_ref,
            selector_id=selector.selector_id,
            label=None,
            frame=None,
            role=entry.element_ref.role,
            actions=entry.element_ref.signature.actions,
            confidence=1.0,
            evidence=SelectorEvidence(),
        )
        return SelectorResult(
            selector_id=selector.selector_id,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            status="resolved",
            elements=(element,),
            snapshot_id=entry.element_ref.snapshot_id,
            diagnostics=selector_diagnostics(
                tried_selectors=(selector.selector_id,),
                query_count=1,
                node_count=1,
                cache_status="hit",
            ),
        )

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
            return {"kind": "focusedWindow"}
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

    def _query_payload(self, step: object) -> dict[str, JsonValue]:
        step_obj = step
        attributes = {
            "AXFrame",
            "AXRole",
            "AXTitle",
            "AXValue",
            "AXDescription",
            "AXPlaceholderValue",
        }
        for attribute in step_obj.match.attributes:  # type: ignore[attr-defined]
            attributes.add(attribute)
        return {
            "scope": step_obj.scope,  # type: ignore[attr-defined]
            "maxDepth": step_obj.max_depth,  # type: ignore[attr-defined]
            "limit": step_obj.limit,  # type: ignore[attr-defined]
            "timeBudgetMs": step_obj.time_budget_ms,  # type: ignore[attr-defined]
            "attributes": sorted(attributes),
            "actions": bool(step_obj.match.actions_include),  # type: ignore[attr-defined]
            "match": {
                "roleIn": list(step_obj.role_in or step_obj.match.role_in),  # type: ignore[attr-defined]
            },
        }

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
        if selector.cache.mode != "readWrite":
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
    ) -> tuple[ResolvedElement, ...] | str | None:
        if not candidates:
            return None
        if selector.pick == "all":
            return tuple(candidates)
        if selector.pick == "first":
            return (candidates[0],)
        if selector.pick == "largestArea":
            return (max(candidates, key=_area),)
        candidates = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        if len(candidates) > 1 and candidates[0].confidence == candidates[1].confidence:
            return "ambiguous"
        return (candidates[0],)

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
                message=message,
            ),
        )


def _normalize_query_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if "accessibilityQuery" in payload and isinstance(payload["accessibilityQuery"], Mapping):
        payload = payload["accessibilityQuery"]
    return {
        "snapshotId": payload.get("snapshotId"),
        "nodes": list(payload.get("nodes") or ()),
        "diagnostics": dict(payload.get("diagnostics") or {}),
    }


def _area(element: ResolvedElement) -> float:
    if element.frame is None:
        return 0.0
    return element.frame.width * element.frame.height


def _frame_hash(node: Mapping[str, Any]) -> str | None:
    frame = node_frame(node)
    if frame is None:
        return None
    return f"{frame.x:.0f}:{frame.y:.0f}:{frame.width:.0f}:{frame.height:.0f}"


def _first_snapshot_id(elements: list[ResolvedElement]) -> str | None:
    if not elements:
        return None
    return elements[0].element_ref.snapshot_id
