"""Canonical Phase A ingress: one resolution decision for every chat turn."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.services.cognitive_resolution_pipeline import CognitiveResolutionResult, run_cognitive_resolution
from app.services.connector_semantic_registry import (
    mentions_analytics_traffic_language,
    mentions_website_performance_language,
    resolve_all_connectors_from_text,
    resolve_analytics_capabilities_for_message,
    resolve_connector_from_text,
)
from app.services.reference_resolver import resolve_reference
from app.services.resolution_trace_service import attach_resolution_trace
from app.services.compiled_task_service import attach_compiled_task

_CHITCHAT_RE = re.compile(
    r"^\s*(hello|hi|hey|thanks|thank you|thankyou|good morning|good afternoon|good evening|"
    r"how are you|what'?s up|sup)\s*[.!?]?\s*$",
    re.I,
)
_SIMPLE_MATH_RE = re.compile(r"^\s*\d+\s*[\+\-\*\/×÷]\s*\d+\s*[.!?]?\s*$")
_GENERAL_KNOWLEDGE_RE = re.compile(
    r"(?is)^\s*(?:what is|what'?s|explain|define|tell me about)\s+"
    r"(?:oauth|api|machine learning|ai|llm|javascript|python|sql)\b"
)


@dataclass(frozen=True)
class CognitiveResolutionNeeds:
    """What Phase A work is required for this turn."""

    run_semantic: bool = True
    run_resource: bool = False
    analytics_short_circuit: bool = False
    reason: str = ""


def assess_cognitive_resolution_needs(
    message: str,
    task_state: dict[str, Any] | None,
    *,
    connected_integrations: list[str] | None = None,
) -> CognitiveResolutionNeeds:
    """Selective resolution — chitchat/math/general-knowledge skip resource discovery."""
    text = (message or "").strip()
    state = task_state if isinstance(task_state, dict) else {}
    if not text:
        return CognitiveResolutionNeeds(run_semantic=False, run_resource=False, reason="empty")

    reference = resolve_reference(text, state)
    if reference.matched and reference.kind in {"confirm", "reject", "select_all_options", "select_option"}:
        return CognitiveResolutionNeeds(
            run_semantic=True,
            run_resource=False,
            reason=f"reference_{reference.kind}",
        )
    if reference.matched and reference.kind == "referent":
        from app.services.task_continuity import frame_is_analytics

        analytics = frame_is_analytics(state)
        return CognitiveResolutionNeeds(
            run_semantic=True,
            run_resource=analytics,
            analytics_short_circuit=analytics,
            reason="reference_referent",
        )

    if _CHITCHAT_RE.match(text):
        return CognitiveResolutionNeeds(run_semantic=True, run_resource=False, reason="chitchat")

    if _SIMPLE_MATH_RE.match(text):
        return CognitiveResolutionNeeds(run_semantic=True, run_resource=False, reason="simple_math")

    if _GENERAL_KNOWLEDGE_RE.match(text) and not resolve_all_connectors_from_text(text):
        return CognitiveResolutionNeeds(run_semantic=True, run_resource=False, reason="general_knowledge")

    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    analytics_caps = resolve_analytics_capabilities_for_message(text, connected_integrations=list(connected))
    connector_id = resolve_connector_from_text(text)
    traffic_ask = mentions_analytics_traffic_language(text) or mentions_website_performance_language(text)
    analytics_vendors = connected.intersection(
        {"google_analytics", "google_search_console", "google_ads"}
    )

    if analytics_caps and connected.intersection(analytics_caps):
        return CognitiveResolutionNeeds(
            run_semantic=True,
            run_resource=True,
            analytics_short_circuit=traffic_ask or "google_analytics" in analytics_caps,
            reason="analytics_capabilities",
        )

    if connector_id:
        if traffic_ask:
            return CognitiveResolutionNeeds(
                run_semantic=True,
                run_resource=bool(analytics_vendors),
                analytics_short_circuit=True,
                reason="analytics_language_named_connector",
            )
        if connector_id in connected:
            return CognitiveResolutionNeeds(
                run_semantic=True,
                run_resource=True,
                reason=f"named_connected_connector:{connector_id}",
            )
        return CognitiveResolutionNeeds(
            run_semantic=True,
            run_resource=False,
            reason=f"named_disconnected_connector:{connector_id}",
        )

    if traffic_ask:
        return CognitiveResolutionNeeds(
            run_semantic=True,
            run_resource=bool(analytics_vendors),
            analytics_short_circuit=True,
            reason="analytics_language",
        )

    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    if pending.get("status") in {
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_params",
        "awaiting_step_confirm",
    }:
        return CognitiveResolutionNeeds(run_semantic=True, run_resource=False, reason="pending_task")

    offered = state.get("offered_action") if isinstance(state.get("offered_action"), dict) else {}
    if offered.get("status") == "awaiting_user_confirmation":
        return CognitiveResolutionNeeds(run_semantic=True, run_resource=False, reason="offered_action")

    return CognitiveResolutionNeeds(run_semantic=True, run_resource=False, reason="default_semantic_only")


def should_skip_unified_live_for_compiled_read(
    message: str,
    task_state: dict[str, Any] | None,
    connected_integrations: list[str] | None,
) -> bool:
    """LIVE must not swallow compiled operational/analytics READs before react_entry."""
    needs = assess_cognitive_resolution_needs(
        message,
        task_state,
        connected_integrations=connected_integrations,
    )
    if needs.analytics_short_circuit:
        return True
    from app.services.capability_evidence_plan import looks_like_ceo_ops_question

    if looks_like_ceo_ops_question(message or ""):
        return True
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    pending_execute = str(pending.get("type") or "") == "execute_workflow" or str(
        params.get("type") or ""
    ) == "execute_workflow"
    if pending_execute and str(pending.get("status") or "") in {
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_step_confirm",
    }:
        return True
    text = " ".join((message or "").lower().split())
    if re.search(
        r"\b(?:run|start|trigger|execute|launch)\b.+\bworkflow\b|\bworkflow\b.+\b(?:named|called)\b",
        text,
    ):
        return True
    from app.capability_ontology.cognitive_recipe_planner import match_recipe_for_query
    from app.services.operational_read_execution import OPERATIONAL_READ_RECIPES
    from app.services.task_continuity import frame_is_analytics

    recipe = match_recipe_for_query(message)
    if recipe is not None and recipe.recipe_id in OPERATIONAL_READ_RECIPES:
        return True
    if frame_is_analytics(task_state):
        return True
    from app.services.operational_read_execution import infer_operational_recipe_id
    from app.services.task_continuity import decide_task_continuity

    if decide_task_continuity(message, task_state) == "continue":
        cap = infer_operational_recipe_id(task_state)
        if cap in OPERATIONAL_READ_RECIPES:
            return True
    return False


async def apply_canonical_cognitive_resolution(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    tenant_id: str,
    user_id: str | None,
    client: Any,
    settings: Settings | None = None,
    conversation_id: str | None = None,
    connected_integrations: list[str] | None = None,
) -> tuple[CognitiveResolutionResult | None, dict[str, Any]]:
    """Run Phase A resolution once at canonical ingress; return updated task_state."""
    state = dict(task_state) if isinstance(task_state, dict) else {}
    needs = assess_cognitive_resolution_needs(
        message,
        state,
        connected_integrations=connected_integrations,
    )
    if not needs.run_semantic:
        return None, state

    result = await run_cognitive_resolution(
        message=message,
        task_state=state,
        tenant_id=tenant_id,
        user_id=user_id,
        client=client,
        settings=settings,
        conversation_id=conversation_id,
        connected_integrations=connected_integrations,
        skip_resource=not needs.run_resource,
    )
    merged = attach_resolution_trace(state, result.trace)
    merged["cognitive_resolution_message"] = (message or "").strip()
    merged["cognitive_resolution_needs"] = {
        "run_resource": needs.run_resource,
        "analytics_short_circuit": needs.analytics_short_circuit,
        "reason": needs.reason,
        "capability_id": "analytics.traffic_overview" if needs.analytics_short_circuit else None,
    }
    if result.resource is not None:
        merged["e1_resource"] = result.resource.as_dict()
    merged = attach_compiled_task(
        merged,
        objective_text=message,
        resolution=result,
        org_id=tenant_id,
    )
    return result, merged


async def try_analytics_short_circuit_turn(
    *,
    message: str,
    resolution: CognitiveResolutionResult | None,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Execute analytics traffic overview before ReAct when resolution says so."""
    needs = (task_state or {}).get("cognitive_resolution_needs") or {}
    if not isinstance(needs, dict) or not needs.get("analytics_short_circuit"):
        return None
    del resolution  # call-site compatibility; handler uses connected_integrations + message

    from app.services.analytics_traffic_overview_service import try_analytics_traffic_overview_turn

    return await try_analytics_traffic_overview_turn(
        message=message,
        org_id=org_id,
        client=client,
        settings=settings or get_settings(),
        connected_integrations=connected_integrations,
        task_state=task_state,
        user_id=user_id,
    )


async def try_compiled_operational_read_turn(
    *,
    message: str,
    resolution: CognitiveResolutionResult | None,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Analytics first, then other F1 department READs, before ReAct."""
    from app.services.capability_evidence_plan import looks_like_ceo_ops_question

    if not looks_like_ceo_ops_question(message or ""):
        analytics = await try_analytics_short_circuit_turn(
            message=message,
            resolution=resolution,
            org_id=org_id,
            client=client,
            settings=settings,
            connected_integrations=connected_integrations,
            task_state=task_state,
            user_id=user_id,
        )
        if analytics:
            return analytics
    from app.services.operational_read_execution import try_operational_read_short_circuit_turn

    operational = await try_operational_read_short_circuit_turn(
        message=message,
        org_id=org_id,
        client=client,
        settings=settings,
        connected_integrations=connected_integrations,
        task_state=task_state,
        user_id=user_id,
    )
    if operational:
        from app.services.capability_evidence_plan import (
            build_capability_evidence_plan,
            looks_like_ceo_ops_question,
            pending_auth_prose,
        )

        if looks_like_ceo_ops_question(message or ""):
            plan = build_capability_evidence_plan(
                message or "",
                connected_integrations=list(connected_integrations or []),
                settings=settings,
            )
            note = pending_auth_prose(plan)
            if note:
                body = str(operational.get("message") or "").rstrip()
                operational["message"] = f"{body}\n\n{note}" if body else note
        return operational
    from app.services.governed_write_compile import try_governed_write_compile_turn

    return await try_governed_write_compile_turn(
        message=message,
        org_id=org_id,
        client=client,
        settings=settings,
        connected_integrations=connected_integrations,
        task_state=task_state,
    )


def resolution_already_applied(task_state: dict[str, Any] | None, message: str) -> bool:
    """True when canonical ingress already ran resolution for this message."""
    state = task_state if isinstance(task_state, dict) else {}
    if state.get("cognitive_resolution_message") != (message or "").strip():
        return False
    return isinstance(state.get("resolution_trace"), dict)
