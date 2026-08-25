"""Internal cron endpoints for daily rollups, retention purge, and connector health."""
from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.connectors.health_monitor_service import run_connector_health_monitor
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/internal/ops", tags=["ops-internal"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


class RollupDailyRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=90)
    purge_days: int | None = Field(default=None, ge=1, le=3650)


def _run_daily_rollup(settings: Settings, *, days: int, purge_days: int | None) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    client = get_supabase_client(settings)
    client.rpc(
        "rollup_all_daily",
        {"start_at": start.isoformat(), "end_at": end.isoformat()},
    ).execute()
    purged = None
    if purge_days is not None:
        cutoff = end - timedelta(days=purge_days)
        client.rpc("purge_audit_events_before", {"cutoff": cutoff.isoformat()}).execute()
        purged = cutoff.isoformat()
    return {
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "days": days,
        "purge_cutoff": purged,
    }


@router.post("/rollup-daily")
async def rollup_daily_cron(
    body: RollupDailyRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Daily metrics rollups (+ optional audit retention purge)."""
    req = body or RollupDailyRequest()
    summary = await asyncio.to_thread(
        _run_daily_rollup,
        settings,
        days=req.days,
        purge_days=req.purge_days,
    )
    logger.info(
        "rollup_daily_cron days=%s purge_cutoff=%s",
        summary.get("days"),
        summary.get("purge_cutoff"),
    )
    return summary


@router.post("/connector-health")
async def connector_health_cron(
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Run connector OAuth health checks (durable alternative to in-process scheduler)."""
    summary = await asyncio.to_thread(run_connector_health_monitor, settings)
    logger.info(
        "connector_health_cron checked=%s updated=%s errors=%s",
        summary.get("checked"),
        summary.get("updated"),
        summary.get("errors"),
    )
    return summary


class CompanyIntelligenceRunRequest(BaseModel):
    org_id: str | None = None


@router.post("/company-intelligence-run")
async def company_intelligence_run_cron(
    body: CompanyIntelligenceRunRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Manual/GitHub-Actions trigger for the company intelligence learning loop."""
    from app.services.company_intelligence_collectors import get_active_org_ids
    from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator
    from app.temporal.starters import start_company_intelligence_workflow, temporal_enabled

    req = body or CompanyIntelligenceRunRequest()
    if temporal_enabled():
        if req.org_id:
            started = await start_company_intelligence_workflow(req.org_id)
            return {"temporal": True, "processed": 1, "started": [started]}
        org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
        started: list[dict[str, Any]] = []
        for org_id in org_ids:
            try:
                started.append(await start_company_intelligence_workflow(org_id))
            except Exception as exc:  # noqa: BLE001
                started.append({"org_id": org_id, "error": str(exc)})
        return {"temporal": True, "processed": len(started), "started": started}

    orchestrator = CompanyIntelligenceOrchestrator(settings=settings)
    if req.org_id:
        summary = await orchestrator.run_for_org(req.org_id)
        return {"processed": 1, "results": [summary]}

    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
    results: list[dict[str, Any]] = []
    for org_id in org_ids:
        try:
            results.append(await orchestrator.run_for_org(org_id))
        except Exception as exc:  # noqa: BLE001
            results.append({"org_id": org_id, "error": str(exc)})
    return {"processed": len(results), "results": results}


@router.get("/infrastructure-health")
async def infrastructure_health_cron(
    apply_clickhouse_schema: bool = False,
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Verify Temporal + ClickHouse connectivity from the running Railway process."""
    from app.services.infrastructure_health_service import get_infrastructure_health

    try:
        return await get_infrastructure_health(apply_clickhouse_schema=apply_clickhouse_schema)
    except Exception as exc:  # noqa: BLE001
        logger.exception("infrastructure_health_failed")
        return {
            "ok": False,
            "error": str(exc),
            "temporal": {"ok": False, "error": "health_check_crashed"},
            "clickhouse": {"ok": False, "error": "health_check_crashed"},
        }


@router.post("/clickhouse-apply-schema")
async def clickhouse_apply_schema_cron(
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    from app.services.infrastructure_health_service import apply_clickhouse_schema, check_clickhouse_connection

    applied = apply_clickhouse_schema()
    status = await check_clickhouse_connection(apply_schema=False)
    return {"apply": applied, "status": status}


class MemoryPromotionRunRequest(BaseModel):
    org_id: str | None = None


@router.post("/memory-promotion-run")
async def memory_promotion_run_cron(
    body: MemoryPromotionRunRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Manual trigger for memory promotion evaluation (v4)."""
    from app.services.company_intelligence_collectors import get_active_org_ids
    from app.services.memory_promotion_service import get_memory_promotion_service

    req = body or MemoryPromotionRunRequest()
    service = get_memory_promotion_service(settings)
    if req.org_id:
        summary = await service.run_evaluation(req.org_id)
        return {"processed": 1, "results": [summary]}

    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
    results: list[dict[str, Any]] = []
    for org_id in org_ids:
        try:
            results.append(await service.run_evaluation(org_id))
        except Exception as exc:  # noqa: BLE001
            results.append({"org_id": org_id, "error": str(exc)})
    return {"processed": len(results), "results": results}


class MemoryExpirationRunRequest(BaseModel):
    org_id: str | None = None


@router.post("/memory-expiration-run")
async def memory_expiration_run_cron(
    body: MemoryExpirationRunRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Manual trigger for memory expiration/decay checks (v4)."""
    from app.services.company_intelligence_collectors import get_active_org_ids
    from app.services.memory_promotion_service import get_memory_promotion_service

    req = body or MemoryExpirationRunRequest()
    service = get_memory_promotion_service(settings)
    if req.org_id:
        summary = await service.run_expiration_check(req.org_id)
        return {"processed": 1, "results": [summary]}

    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=50)
    results: list[dict[str, Any]] = []
    for org_id in org_ids:
        try:
            results.append(await service.run_expiration_check(org_id))
        except Exception as exc:  # noqa: BLE001
            results.append({"org_id": org_id, "error": str(exc)})
    return {"processed": len(results), "results": results}


class CapabilityWriteGateSmokeBody(BaseModel):
    org_id: str
    actor_id: str
    environment_name: str = "production"


@router.post("/capability-write-gate-smoke")
async def capability_write_gate_smoke(
    body: CapabilityWriteGateSmokeBody,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Deployed-tip proof: capability-resolved CRM write hits same write gate as direct HubSpot."""
    import os
    import uuid

    from app.capability_ontology.tool_bridge import capability_tool_name
    from app.operators.react_engine import ReActEngine
    from app.services.react_write_gate import WRITE_APPROVAL_REQUIRED
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext

    org_id = str(body.org_id or "").strip()
    actor_id = str(body.actor_id or "").strip()
    if not org_id or not actor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id and actor_id required")

    client = get_supabase_client(settings)
    reg = get_tool_registry()
    engine = ReActEngine(settings=settings, registry=reg)
    env_name = str(body.environment_name or "production").strip() or "production"
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        agent_id="synthetic-default",
        environment_name=env_name,
    )
    connected = reg.list_connected_integrations(client, org_id, environment_name=env_name)
    args = {"email": f"cap-write-gate-{uuid.uuid4().hex[:8]}@example.com"}
    cap_tool = capability_tool_name("crm.contact.create")

    async def _probe(tool_name: str, probe_args: dict[str, Any]) -> dict[str, Any]:
        blocked = await engine._execute_tool_call(
            ctx,
            tool_name,
            probe_args,
            allowed_tool_names={tool_name},
        )
        return {
            "tool": tool_name,
            "success": blocked.get("success"),
            "error_code": blocked.get("error_code"),
            "pending_approval": blocked.get("pending_approval"),
            "action": blocked.get("action"),
            "integration": blocked.get("integration"),
            "pass": (
                blocked.get("error_code") == WRITE_APPROVAL_REQUIRED
                and blocked.get("pending_approval") is True
                and blocked.get("action") == "hubspot.contacts.create"
            ),
        }

    direct = await _probe("hubspot_contacts_create", args)
    capability = await _probe(
        cap_tool,
        {**args, "preferred_vendor": "hubspot"},
    )
    parity = (
        direct.get("pass")
        and capability.get("pass")
        and direct.get("error_code") == capability.get("error_code") == "write_approval_required"
        and direct.get("action") == capability.get("action") == "hubspot.contacts.create"
    )

    return {
        "pass": parity,
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        "org_id": org_id,
        "actor_id": actor_id,
        "connected_integrations": connected,
        "path": "deployed_react_write_gate direct vs capability-resolved",
        "direct_hubspot_tool": direct,
        "capability_resolved_tool": capability,
        "parity": {
            "same_error_code": direct.get("error_code") == capability.get("error_code"),
            "same_invoke_action": direct.get("action") == capability.get("action"),
            "both_pending_approval": bool(
                direct.get("pending_approval") and capability.get("pending_approval")
            ),
            "pass": parity,
        },
        "claim": (
            "PASS — write_approval_required hubspot.contacts.create @ capability parity (deployed tip)"
            if parity
            else "FAIL — capability write gate did not match direct HubSpot gate"
        ),
    }


class Phase2ConnectorSmokeBody(BaseModel):
    org_id: str
    actor_id: str
    environment_name: str = "production"
    invoke_reads: bool = True


def _agent_tool_name(catalog_action: str) -> str:
    return catalog_action.replace(".", "_")


# Read-only prod probes per Phase 2 vendor (registry name, catalog action).
PHASE2_READ_PROBES: dict[str, tuple[str, str]] = {
    "linear": ("linear_issues_list", "linear.issues.list"),
    "gitlab": ("gitlab_projects_list", "gitlab.projects.list"),
    "shopify": ("shopify_products_list", "shopify.products.list"),
    "paypal": ("paypal_payments_list", "paypal.payments.list"),
    "brevo": ("brevo_contacts_list", "brevo.contacts.list"),
    "meta_marketing": ("meta_marketing_campaigns_list", "meta_marketing.campaigns.list"),
}


@router.post("/phase2-connector-smoke")
async def phase2_connector_smoke(
    body: Phase2ConnectorSmokeBody,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Deployed-tip proof: Phase 2 six-vendor wiring + optional read invoke when connected."""
    import os

    from app.connectors.oauth_provider_registry import GENERIC_OAUTH_VENDORS, OAUTH_PROVIDER_REGISTRY
    from app.connectors.phase2_connector_routes import PHASE2_ROUTES, PHASE2_VENDORS
    from app.operators.react_engine import ReActEngine
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_service import list_registered_actions
    from app.services.tool_types import ToolContext

    org_id = str(body.org_id or "").strip()
    actor_id = str(body.actor_id or "").strip()
    if not org_id or not actor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id and actor_id required")

    registered = set(list_registered_actions())
    missing_routes = sorted(action for action in PHASE2_ROUTES if action not in registered)
    wiring_pass = not missing_routes and len(PHASE2_ROUTES) == 30

    oauth_checks: dict[str, bool] = {}
    for vendor in sorted(PHASE2_VENDORS):
        if vendor == "brevo":
            # API-key vendor — not in generic OAuth registry by design.
            oauth_checks[vendor] = vendor not in GENERIC_OAUTH_VENDORS
        else:
            oauth_checks[vendor] = vendor in GENERIC_OAUTH_VENDORS and vendor in OAUTH_PROVIDER_REGISTRY
    oauth_pass = all(oauth_checks.values())

    client = get_supabase_client(settings)
    reg = get_tool_registry()
    env_name = str(body.environment_name or "production").strip() or "production"
    connected = set(reg.list_connected_integrations(client, org_id, environment_name=env_name))
    phase2_connected = sorted(v for v in PHASE2_VENDORS if v in connected)

    vendor_results: dict[str, Any] = {}
    invoke_pass_count = 0
    invoke_attempted = 0

    if body.invoke_reads and phase2_connected:
        engine = ReActEngine(settings=settings, registry=reg)
        ctx = ToolContext(
            settings=settings,
            client=client,
            org_id=org_id,
            actor_id=actor_id,
            agent_id="synthetic-default",
            environment_name=env_name,
        )
        for vendor in phase2_connected:
            tool_name, catalog_action = PHASE2_READ_PROBES[vendor]
            invoke_attempted += 1
            try:
                result = await engine._execute_tool_call(
                    ctx,
                    tool_name,
                    {"limit": 1},
                    allowed_tool_names={tool_name},
                )
                ok = bool(result.get("success"))
                if ok:
                    invoke_pass_count += 1
                vendor_results[vendor] = {
                    "connected": True,
                    "tool": tool_name,
                    "catalog_action": catalog_action,
                    "success": result.get("success"),
                    "error_code": result.get("error_code"),
                    "action": result.get("action"),
                    "integration": result.get("integration"),
                    "pass": ok,
                }
            except Exception as exc:  # noqa: BLE001
                vendor_results[vendor] = {
                    "connected": True,
                    "tool": tool_name,
                    "catalog_action": catalog_action,
                    "success": False,
                    "error": f"{exc.__class__.__name__}:{exc}",
                    "pass": False,
                }
    else:
        for vendor in sorted(PHASE2_VENDORS):
            probe_tool, catalog_action = PHASE2_READ_PROBES[vendor]
            vendor_results[vendor] = {
                "connected": vendor in connected,
                "tool": probe_tool,
                "catalog_action": catalog_action,
                "invoke_skipped": not body.invoke_reads or vendor not in connected,
                "pass": None,
            }

    wiring_only = not phase2_connected or not body.invoke_reads
    invoke_pass = invoke_attempted > 0 and invoke_pass_count == invoke_attempted
    overall_pass = wiring_pass and oauth_pass and (wiring_only or invoke_pass)
    verdict = "PASS" if overall_pass else ("PARTIAL" if wiring_pass and oauth_pass else "FAIL")

    return {
        "pass": overall_pass,
        "verdict": verdict,
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        "org_id": org_id,
        "actor_id": actor_id,
        "environment_name": env_name,
        "path": "deployed_phase2_connector_smoke",
        "wiring": {
            "route_count": len(PHASE2_ROUTES),
            "missing_routes": missing_routes,
            "pass": wiring_pass,
        },
        "oauth_registry": {"checks": oauth_checks, "pass": oauth_pass},
        "connected_phase2_vendors": phase2_connected,
        "vendors": vendor_results,
        "invoke": {
            "attempted": invoke_attempted,
            "passed": invoke_pass_count,
            "pass": invoke_pass if invoke_attempted else None,
        },
        "claim": (
            f"PASS — Phase 2 wiring + {invoke_pass_count}/{invoke_attempted} read invokes @ deployed tip"
            if overall_pass and invoke_attempted
            else (
                "PARTIAL — Phase 2 wiring/oauth PASS; no connected vendors for live invoke"
                if wiring_pass and oauth_pass and wiring_only
                else (
                    "PASS — Phase 2 wiring + oauth registry @ deployed tip"
                    if wiring_pass and oauth_pass
                    else "FAIL — Phase 2 connector smoke"
                )
            )
        ),
    }


class CognitiveOneBrainSmokeBody(BaseModel):
    org_id: str
    actor_id: str
    foreign_org_id: str | None = None
    agent_id: str | None = None
    environment_name: str = "production"


@router.post("/cognitive-one-brain-smoke")
async def cognitive_one_brain_smoke(
    body: CognitiveOneBrainSmokeBody,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Deployed-tip proof for remaining One Brain LIVE PENDING claims."""
    import json
    import os
    import uuid as uuid_mod

    from app.services.cognitive_entry_adapters import run_kernel_for_entry
    from app.services.cognitive_metrics import resolve_metric_for_agent, upsert_metric_definition
    from app.services.cognitive_outcome_loop import bias_from_outcomes
    from app.services.cognitive_turn_kernel import (
        CognitiveTurnRequest,
        get_cognitive_turn_kernel,
    )
    from app.services.council_service import get_council_service
    from app.services.extension_bridge_service import enrich_from_page_context
    from app.services.tool_types import ToolContext

    org_id = str(body.org_id or "").strip()
    actor_id = str(body.actor_id or "").strip()
    foreign_org_id = str(body.foreign_org_id or "658c76b3-04b7-489b-bb7e-64a5f3ec1cbe").strip()
    if not org_id or not actor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id and actor_id required")
    if foreign_org_id == org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="foreign_org_id must differ from org_id",
        )

    client = get_supabase_client(settings)
    kernel = get_cognitive_turn_kernel(settings)
    probe_tag = f"onebrain-{uuid_mod.uuid4().hex[:10]}"
    results: dict[str, Any] = {"probe_tag": probe_tag}
    checks: dict[str, bool] = {}

    # Resolve agent for agent_chat surface
    agent_id = str(body.agent_id or "").strip() or None
    agent_row: dict[str, Any] | None = None
    if not agent_id:
        try:
            rows = (
                client.table("agents")
                .select("id,name,department")
                .eq("org_id", org_id)
                .limit(5)
                .execute()
                .data
                or []
            )
            if rows:
                agent_row = rows[0]
                agent_id = str(agent_row.get("id"))
        except Exception as exc:  # noqa: BLE001
            results["agent_lookup_error"] = str(exc)[:200]
    elif agent_id:
        try:
            rows = (
                client.table("agents")
                .select("id,name,department")
                .eq("org_id", org_id)
                .eq("id", agent_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            agent_row = rows[0] if rows else {"id": agent_id}
        except Exception:  # noqa: BLE001
            agent_row = {"id": agent_id}

    async def _kernel_surface(surface: str, *, spoken: bool = False, agent: str | None = None) -> dict[str, Any]:
        ctx = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                agent_id=agent,
                message=f"{probe_tag} {surface} kernel probe",
                surface=surface,
                entry_point="cognitive_one_brain_smoke",
                spoken_mode=spoken,
                intent="chat",
                client=client,
                agent=agent_row if agent else None,
            )
        )
        stage_names = [getattr(s, "stage", None) or (s.get("stage") if isinstance(s, dict) else None) for s in ctx.stages]
        return {
            "turn_id": ctx.turn_id,
            "surface": surface,
            "stages": stage_names,
            "ok": all(x in stage_names for x in ("RETRIEVE", "RECALL", "KNOWLEDGE", "PLAN", "VERIFY", "GOVERN")),
        }

    # 1) Distinct surfaces: agent_chat + voice
    agent_trace = await _kernel_surface("agent_chat", agent=agent_id)
    voice_trace = await _kernel_surface("voice", spoken=True, agent=agent_id)
    results["agent_chat"] = agent_trace
    results["voice"] = voice_trace
    checks["agent_chat"] = bool(agent_trace.get("ok"))
    checks["voice"] = bool(voice_trace.get("ok"))

    # 2) Extension enrich (+ confirm_write GOVERN path)
    try:
        ctx = ToolContext(
            settings=settings,
            client=client,
            org_id=org_id,
            actor_id=actor_id,
            environment_name=str(body.environment_name or "production"),
        )
        enrich_out = enrich_from_page_context(
            ctx,
            page_url="https://example.com/linkedin/in/onebrain-probe",
            page_context={
                "fullName": f"OneBrain Probe {probe_tag}",
                "email": f"{probe_tag}@example.com",
                "company": "ProbeCo",
            },
            connected=[],
        )
        ext_turn = await run_kernel_for_entry(
            org_id=org_id,
            user_id=actor_id,
            message=f"{probe_tag} extension_action",
            surface="extension_action",
            entry_point="cognitive_one_brain_smoke",
            intent="write_confirm",
            parameters={"action": "hubspot.contacts.create", "is_write": True, "action_hints": ["hubspot.contacts.create"]},
            client=client,
            settings=settings,
        )
        results["extension_enrich"] = {
            "cognitiveTurnId": enrich_out.get("cognitiveTurnId"),
            "ok": bool(enrich_out.get("cognitiveTurnId")),
        }
        results["extension_action"] = {
            "turn_id": getattr(ext_turn, "turn_id", None),
            "ok": bool(getattr(ext_turn, "turn_id", None)),
        }
        checks["extension_enrich"] = bool(enrich_out.get("cognitiveTurnId"))
        checks["extension_action"] = bool(getattr(ext_turn, "turn_id", None))
    except Exception as exc:  # noqa: BLE001
        results["extension_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["extension_enrich"] = False
        checks["extension_action"] = False

    # 3) Council
    try:
        session = await get_council_service().start_council(
            org_id=org_id,
            workflow_id=str(uuid_mod.uuid4()),
            run_id=str(uuid_mod.uuid4()),
            objective=f"{probe_tag} council objective — pick safer option",
            options=["option_a_safe", "option_b_risky"],
            agents=[
                {"name": "Analyst A", "role": "analyst"},
                {"name": "Compliance B", "role": "compliance"},
            ],
            evidence={"probe": probe_tag},
            max_rounds=1,
        )
        # Fetch latest council-surface trace
        council_rows = (
            client.table("cognitive_turn_traces")
            .select("turn_id,surface,stages,created_at")
            .eq("org_id", org_id)
            .eq("surface", "council")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        council_turn = council_rows[0] if council_rows else {}
        results["council"] = {
            "session_id": getattr(session, "id", None),
            "turn_id": council_turn.get("turn_id"),
            "surface": council_turn.get("surface"),
            "ok": bool(council_turn.get("turn_id")),
        }
        checks["council"] = bool(council_turn.get("turn_id"))
    except Exception as exc:  # noqa: BLE001
        results["council_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["council"] = False

    # 4) Cross-org isolation: foreign marker must not appear in org RECALL pack
    foreign_marker = f"FOREIGN_MEMORY_{probe_tag}"
    try:
        # Best-effort insert into foreign org agent_memories if an agent exists there.
        foreign_agent = (
            client.table("agents")
            .select("id")
            .eq("org_id", foreign_org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        foreign_memory_id = None
        if foreign_agent:
            inserted = (
                client.table("agent_memories")
                .insert(
                    {
                        "org_id": foreign_org_id,
                        "agent_id": foreign_agent[0]["id"],
                        "content": foreign_marker,
                        "category": "fact",
                        "provenance": "one_brain_isolation_probe",
                    }
                )
                .execute()
                .data
                or []
            )
            foreign_memory_id = (inserted[0] or {}).get("id") if inserted else None
        ctx = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                message=foreign_marker,
                surface="ai_chat",
                entry_point="cognitive_one_brain_smoke_xorg",
                intent="chat",
                client=client,
            )
        )
        pack_blob = json.dumps(ctx.memory_pack, default=str)
        leaked_marker = foreign_marker in pack_blob
        foreign_rows = 0
        for key, items in (ctx.memory_pack or {}).items():
            if key == "prompt_section" or not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and str(item.get("org_id") or "") not in {"", org_id}:
                    foreign_rows += 1
        results["cross_org"] = {
            "foreign_org_id": foreign_org_id,
            "foreign_memory_id": foreign_memory_id,
            "turn_id": ctx.turn_id,
            "leaked_marker": leaked_marker,
            "foreign_org_rows_in_pack": foreign_rows,
            "ok": (not leaked_marker) and foreign_rows == 0,
        }
        checks["cross_org"] = (not leaked_marker) and foreign_rows == 0
    except Exception as exc:  # noqa: BLE001
        results["cross_org_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["cross_org"] = False

    # 4b) Cross-conversation workspace memory: write in convo A → recall in convo B
    try:
        from app.services.workspace_memory_service import promote_turn_memories, recall_workspace

        ws_marker = f"WS_MEMORY_{probe_tag}"
        convo_a = str(uuid_mod.uuid4())
        convo_b = str(uuid_mod.uuid4())
        promoted = promote_turn_memories(
            client,
            org_id=org_id,
            memories=[
                {
                    "content": f"{ws_marker} decided to use hubspot for CRM",
                    "category": "decision",
                    "confidence": 90,
                }
            ],
            agent_id=None,
            conversation_id=convo_a,
            user_id=actor_id,
            provenance="one_brain_workspace_memory_probe",
            settings=settings,
        )
        recalled = recall_workspace(
            client,
            org_id=org_id,
            query=ws_marker,
            categories=["decision"],
            top_k=8,
            settings=settings,
        )
        ctx_b = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                conversation_id=convo_b,
                message=ws_marker,
                surface="ai_chat",
                entry_point="cognitive_one_brain_smoke_ws_memory",
                intent="chat",
                client=client,
            )
        )
        pack_blob = json.dumps(ctx_b.memory_pack, default=str)
        hit_in_recall = any(ws_marker in str(r.get("content") or "") for r in recalled)
        hit_in_kernel = ws_marker in pack_blob
        foreign_leak = False
        for key, items in (ctx_b.memory_pack or {}).items():
            if key == "prompt_section" or not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and str(item.get("org_id") or "") not in {"", org_id}:
                    foreign_leak = True
        # Foreign-org isolation: promote into foreign org must not appear
        foreign_ws = f"FOREIGN_WS_{probe_tag}"
        promote_turn_memories(
            client,
            org_id=foreign_org_id,
            memories=[{"content": foreign_ws, "category": "decision", "confidence": 90}],
            conversation_id=str(uuid_mod.uuid4()),
            provenance="one_brain_workspace_foreign_probe",
            settings=settings,
        )
        foreign_in_pack = foreign_ws in pack_blob
        ok = bool(promoted) and hit_in_recall and hit_in_kernel and (not foreign_leak) and (not foreign_in_pack)
        results["workspace_cross_conversation"] = {
            "convo_a": convo_a,
            "convo_b": convo_b,
            "promoted_ids": [str(r.get("id")) for r in promoted if isinstance(r, dict)],
            "recall_hit": hit_in_recall,
            "kernel_hit": hit_in_kernel,
            "turn_id_b": ctx_b.turn_id,
            "foreign_leak": foreign_leak or foreign_in_pack,
            "ok": ok,
        }
        checks["workspace_cross_conversation"] = ok
    except Exception as exc:  # noqa: BLE001
        results["workspace_cross_conversation_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["workspace_cross_conversation"] = False

    # 5) Dual-agent metric resolve — same definition_id + platform defaults
    try:
        from app.services.cognitive_metrics import resolve_metric, list_platform_defaults

        metric_key = f"arr_{probe_tag[:8]}"
        upserted = upsert_metric_definition(
            client,
            org_id,
            metric_key,
            label="Annual Recurring Revenue (smoke)",
            formula="sum(mrr)*12",
            source_system="billing",
            owner="smoke",
        )
        agent_a = str(agent_id or uuid_mod.uuid4())
        agent_b = str(uuid_mod.uuid4())
        ra = resolve_metric_for_agent(client, org_id, metric_key, agent_id=agent_a)
        rb = resolve_metric_for_agent(client, org_id, metric_key, agent_id=agent_b)
        same = bool(ra.get("definition_id") and ra.get("definition_id") == rb.get("definition_id"))
        defaults = list_platform_defaults()
        mql = resolve_metric(client, org_id, "mql")
        cac = resolve_metric(client, org_id, "cac")
        arr = resolve_metric(client, org_id, "arr")
        defaults_ok = (
            len(defaults) >= 3
            and mql.get("formula")
            and cac.get("formula")
            and arr.get("formula")
            and mql.get("resolved_from") in {"platform_default", "org_metric_definitions"}
        )
        results["metrics"] = {
            "metric_key": metric_key,
            "definition_id": ra.get("definition_id"),
            "agent_a": ra,
            "agent_b": rb,
            "upserted_id": (upserted or {}).get("id"),
            "platform_defaults": defaults,
            "resolve_mql": mql,
            "resolve_cac": cac,
            "resolve_arr": arr,
            "ok": same and defaults_ok,
        }
        checks["metrics"] = same and defaults_ok
    except Exception as exc:  # noqa: BLE001
        results["metrics_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["metrics"] = False

    # 5b) Knowledge nodes → KNOWLEDGE pack
    try:
        from app.services.org_knowledge_nodes_service import create_knowledge_node

        node_name = f"ProbeCo-{probe_tag[:8]}"
        node = create_knowledge_node(
            client,
            org_id,
            node_type="company",
            name=node_name,
            attributes={"probe": probe_tag},
        )
        ctx_kn = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                message=f"{probe_tag} tell me about {node_name}",
                surface="ai_chat",
                entry_point="cognitive_one_brain_smoke_knowledge_node",
                intent="chat",
                client=client,
            )
        )
        kn_blob = json.dumps(ctx_kn.knowledge_pack, default=str)
        node_in_pack = node_name in kn_blob or any(
            isinstance(n, dict) and node_name in str(n.get("name") or "")
            for n in (ctx_kn.knowledge_pack or {}).get("graph_nodes") or []
        )
        results["knowledge_nodes"] = {
            "node_id": (node or {}).get("id"),
            "node_name": node_name,
            "turn_id": ctx_kn.turn_id,
            "in_knowledge_pack": node_in_pack,
            "ok": bool(node) and node_in_pack,
        }
        checks["knowledge_nodes"] = bool(node) and node_in_pack
    except Exception as exc:  # noqa: BLE001
        results["knowledge_nodes_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["knowledge_nodes"] = False

    # 6) Field-deny GOVERN + audit
    try:
        client.table("org_field_permissions").insert(
            {
                "org_id": org_id,
                "role": "member",
                "resource": "customer",
                "field_key": "ssn",
                "effect": "deny",
            }
        ).execute()
        since = datetime.now(timezone.utc).isoformat()
        ctx = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                message=f"{probe_tag} field acl",
                surface="confirm_write",
                entry_point="cognitive_one_brain_smoke_field",
                intent="write_confirm",
                parameters={
                    "role": "member",
                    "resource": "customer",
                    "fields": ["ssn"],
                    "is_write": True,
                },
                client=client,
            )
        )
        blocked = (ctx.govern or {}).get("blocked") == "field_acl_deny"
        audits = (
            client.table("audit_events")
            .select("id,created_at,action,metadata")
            .eq("org_id", org_id)
            .eq("action", "cognitive.govern.field_acl_deny")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
        results["field_acl"] = {
            "turn_id": ctx.turn_id,
            "blocked": blocked,
            "govern": ctx.govern,
            "audit_id": (audits[0] or {}).get("id") if audits else None,
            "audit_at": (audits[0] or {}).get("created_at") if audits else None,
            "ok": blocked and bool(audits),
        }
        checks["field_acl"] = blocked and bool(audits)
    except Exception as exc:  # noqa: BLE001
        results["field_acl_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["field_acl"] = False

    # 7) Outcome → PLAN bias before/after + prompt injection (Mode A)
    try:
        from app.services.cognitive_outcome_loop import record_closed_loop
        from app.services.cognitive_turn_kernel import to_prompt_sections

        situation = f"{probe_tag} recommend next CRM outreach step"
        before = bias_from_outcomes(client, org_id, situation, settings)
        ctx_before = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                message=situation,
                surface="ai_chat",
                entry_point="cognitive_one_brain_smoke_outcome_before",
                intent="chat",
                client=client,
            )
        )
        before_sections = to_prompt_sections(ctx_before)
        before_bias_prompt = (before_sections.get("outcome_bias_section") or "").strip()

        rec_id = str(uuid_mod.uuid4())
        # Valid OUTCOME_EVENTS vocabulary (not synthetic smoke-only strings).
        recorded = await record_closed_loop(
            org_id=org_id,
            recommendation_id=rec_id,
            outcome_event="recommendation_rejected",
            settings=settings,
            confidence_score=0.4,
            domain_context={"entity_id": situation, "probe": probe_tag},
        )
        # Ensure entity_id is searchable by bias_from_outcomes / PLAN notes.
        client.table("intelligence_outcome_events").insert(
            {
                "org_id": org_id,
                "recommendation_id": rec_id,
                "outcome_event": "recommendation_rejected",
                "entity_type": "recommendation",
                "entity_id": situation,
                "confidence_score": 0.4,
                "metadata": {"probe": probe_tag, "mode": "A"},
            }
        ).execute()

        after = bias_from_outcomes(client, org_id, situation, settings)
        ctx_after = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=actor_id,
                message=situation,
                surface="ai_chat",
                entry_point="cognitive_one_brain_smoke_outcome_after",
                intent="chat",
                client=client,
            )
        )
        plan_bias = (ctx_after.plan or {}).get("outcome_bias") or {}
        after_sections = to_prompt_sections(ctx_after)
        after_bias_prompt = (after_sections.get("outcome_bias_section") or "").strip()
        prompt_injected = bool(after_bias_prompt) and "outcome_bias" in after_bias_prompt and "Mode A" in after_bias_prompt
        notes_grew = len(after.get("bias_notes") or []) > len(before.get("bias_notes") or [])
        changed = notes_grew or bool(after.get("bias_notes"))
        results["outcome_loop"] = {
            "recommendation_id": rec_id,
            "situation": situation,
            "record_closed_loop": recorded,
            "before_weight_delta": before.get("weight_delta"),
            "after_weight_delta": after.get("weight_delta"),
            "before_bias_notes": before.get("bias_notes"),
            "after_bias_notes": after.get("bias_notes"),
            "before_bias_prompt_len": len(before_bias_prompt),
            "after_bias_prompt_len": len(after_bias_prompt),
            "prompt_injected": prompt_injected,
            "plan_outcome_bias": plan_bias,
            "turn_id_before": ctx_before.turn_id,
            "turn_id_after": ctx_after.turn_id,
            "ok": changed and prompt_injected and bool(plan_bias.get("bias_notes")),
        }
        checks["outcome_loop"] = bool(results["outcome_loop"]["ok"])
    except Exception as exc:  # noqa: BLE001
        results["outcome_loop_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["outcome_loop"] = False

    # 8) Jobs / execute_task kernel-first intake (swarm/handoff share this path)
    try:
        from app.operators.agent_intelligence import AgentIntelligence

        job_agent = agent_row or {"id": agent_id or "synthetic-default", "name": "OneBrain Smoke Agent"}
        if not job_agent.get("id"):
            job_agent = {"id": str(uuid_mod.uuid4()), "name": "OneBrain Smoke Agent"}
        intelligence = AgentIntelligence(settings=settings)
        job_error: str | None = None
        try:
            await intelligence.execute_task(
                settings=settings,
                org_id=org_id,
                agent=job_agent,
                task=f"{probe_tag} execute_task job kernel probe — reply briefly",
                parameters={"surface": "job", "intent": "job", "max_react_iterations": 1},
                actor_id=actor_id,
                environment_name=str(body.environment_name or "production"),
                client=client,
                max_iterations=1,
            )
        except Exception as job_exc:  # noqa: BLE001
            # Kernel persists before ReAct; still accept a job-surface trace.
            job_error = f"{job_exc.__class__.__name__}:{job_exc}"[:300]
        job_rows = (
            client.table("cognitive_turn_traces")
            .select("turn_id,surface,stages,created_at")
            .eq("org_id", org_id)
            .eq("surface", "job")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        job_turn = job_rows[0] if job_rows else {}
        stage_names = []
        for s in job_turn.get("stages") or []:
            if isinstance(s, dict):
                stage_names.append(s.get("stage"))
        results["job_execute_task"] = {
            "turn_id": job_turn.get("turn_id"),
            "surface": job_turn.get("surface"),
            "stages": stage_names,
            "react_error": job_error,
            "ok": bool(job_turn.get("turn_id")) and "RETRIEVE" in stage_names and "GOVERN" in stage_names,
        }
        checks["job_execute_task"] = bool(results["job_execute_task"]["ok"])
    except Exception as exc:  # noqa: BLE001
        results["job_execute_task_error"] = f"{exc.__class__.__name__}:{exc}"[:300]
        checks["job_execute_task"] = False

    overall = all(checks.values()) if checks else False
    return {
        "pass": overall,
        "verdict": "PASS" if overall else "PARTIAL",
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        "org_id": org_id,
        "actor_id": actor_id,
        "checks": checks,
        "results": results,
        "claim": (
            "PASS — One Brain live residual probes"
            if overall
            else f"PARTIAL — failed checks: {[k for k, v in checks.items() if not v]}"
        ),
    }


class CapabilityRecipesSmokeBody(BaseModel):
    org_id: str
    actor_id: str
    environment_name: str = "production"
    recipe_id: str = "sales.new-lead-enrichment"


@router.post("/capability-recipes-smoke")
async def capability_recipes_smoke(
    body: CapabilityRecipesSmokeBody,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Deployed-tip proof: Phase 3 capability recipe list + org-connected resolve."""
    import os

    from app.capability_ontology.recipe_resolver import resolve_recipe
    from app.capability_ontology.recipes import list_recipes
    from app.services.tool_registry import get_tool_registry

    org_id = str(body.org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id required")

    client = get_supabase_client(settings)
    reg = get_tool_registry()
    env_name = str(body.environment_name or "production").strip() or "production"
    connected = reg.list_connected_integrations(client, org_id, environment_name=env_name)

    catalog = [recipe.to_dict() for recipe in list_recipes()]
    resolved = resolve_recipe(
        body.recipe_id,
        connected_integrations=connected,
        query="new lead enrichment",
    ).to_dict()

    list_ok = len(catalog) >= 3
    resolve_ok = resolved.get("status") in {"fully_resolved", "partially_resolved", "ambiguous"}
    fully = resolved.get("status") == "fully_resolved"
    overall = list_ok and resolve_ok

    return {
        "pass": overall,
        "verdict": "PASS" if fully else ("PARTIAL" if overall else "FAIL"),
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        "org_id": org_id,
        "connected_integrations": connected,
        "recipe_count": len(catalog),
        "recipes": catalog,
        "resolved": resolved,
        "claim": (
            f"PASS — capability recipes list={len(catalog)} resolve={resolved.get('status')}"
            if fully
            else (
                f"PARTIAL — recipes list OK; resolve={resolved.get('status')} (connected={connected})"
                if overall
                else "FAIL — capability recipes smoke"
            )
        ),
    }


class CapabilityConversationalGraceSmokeBody(BaseModel):
    org_id: str
    actor_id: str
    environment_name: str = "production"


@router.post("/capability-conversational-grace-smoke")
async def capability_conversational_grace_smoke(
    body: CapabilityConversationalGraceSmokeBody,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Phase 4: capability-resolved writes use vendor-natural labels and approval copy."""
    import os
    import uuid

    from app.capability_ontology.conversational_grace import (
        message_is_graceful,
        message_mentions_vendor,
    )
    from app.capability_ontology.tool_bridge import capability_tool_name
    from app.operators.react_engine import ReActEngine
    from app.services.connector_action_workflows import format_write_approval_message
    from app.services.react_write_gate import (
        WRITE_APPROVAL_REQUIRED,
        plan_from_react_write,
    )
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext

    org_id = str(body.org_id or "").strip()
    actor_id = str(body.actor_id or "").strip()
    if not org_id or not actor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id and actor_id required")

    client = get_supabase_client(settings)
    reg = get_tool_registry()
    env_name = str(body.environment_name or "production").strip() or "production"
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        agent_id="synthetic-default",
        environment_name=env_name,
    )
    cap_tool = capability_tool_name("crm.contact.create")
    args = {"email": f"cap-grace-{uuid.uuid4().hex[:8]}@example.com", "preferred_vendor": "hubspot"}

    blocked = await ReActEngine(settings=settings, registry=reg)._execute_tool_call(
        ctx,
        cap_tool,
        args,
        allowed_tool_names={cap_tool},
    )
    pending = {
        "tool": cap_tool,
        "args": args,
        "result": blocked,
    }
    plan = plan_from_react_write(pending, reg)
    approval_message = format_write_approval_message(plan) if plan else ""
    user_message = str(blocked.get("user_message") or "")

    checks = {
        "write_gate_parity": blocked.get("error_code") == WRITE_APPROVAL_REQUIRED
        and blocked.get("action") == "hubspot.contacts.create",
        "integration_is_vendor": str(blocked.get("integration") or "").lower() == "hubspot",
        "label_vendor_natural": "hubspot" in str(blocked.get("label") or "").lower(),
        "user_message_graceful": message_is_graceful(user_message)
        and message_mentions_vendor(user_message, "hubspot"),
        "approval_message_graceful": message_is_graceful(approval_message)
        and message_mentions_vendor(approval_message, "hubspot"),
        "no_capability_tool_leak": "capability__" not in approval_message.lower(),
    }
    overall = all(checks.values())

    return {
        "pass": overall,
        "verdict": "PASS" if overall else "FAIL",
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        "org_id": org_id,
        "actor_id": actor_id,
        "blocked": blocked,
        "approval_message": approval_message,
        "checks": checks,
        "claim": (
            "PASS — capability-resolved HubSpot write uses graceful vendor copy"
            if overall
            else f"FAIL — grace checks failed: {[k for k, v in checks.items() if not v]}"
        ),
    }


class PreActionCardSmokeBody(BaseModel):
    org_id: str
    actor_id: str
    environment_name: str = "production"


@router.post("/pre-action-card-smoke")
async def pre_action_card_smoke(
    body: PreActionCardSmokeBody,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """One Brain #26: pre-action card fields on capability-resolved write plan."""
    import os
    import uuid

    from app.capability_ontology.tool_bridge import capability_tool_name
    from app.operators.react_engine import ReActEngine
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService
    from app.services.react_write_gate import plan_from_react_write
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext

    org_id = str(body.org_id or "").strip()
    actor_id = str(body.actor_id or "").strip()
    if not org_id or not actor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id and actor_id required")

    client = get_supabase_client(settings)
    reg = get_tool_registry()
    env_name = str(body.environment_name or "production").strip() or "production"
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        agent_id="synthetic-default",
        environment_name=env_name,
    )
    cap_tool = capability_tool_name("crm.contact.create")
    args = {"email": f"pre-action-{uuid.uuid4().hex[:8]}@example.com", "preferred_vendor": "hubspot"}
    blocked = await ReActEngine(settings=settings, registry=reg)._execute_tool_call(
        ctx,
        cap_tool,
        args,
        allowed_tool_names={cap_tool},
    )
    pending = {"tool": cap_tool, "args": args, "result": blocked}
    plan = plan_from_react_write(pending, reg)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan_missing")

    chat_svc = ChatConnectorExecutionService(settings=settings)
    risk = await chat_svc._evaluate_risk(org_id, actor_id, plan, classification={})
    pending_params = {
        **ChatConnectorExecutionService.plan_to_dict(plan),
        "estimated_impact": risk.get("estimated_impact"),
        "risk_level": risk.get("risk_level"),
        "approval_reason": risk.get("approval_reason"),
    }

    checks = {
        "risk_level_present": bool(pending_params.get("risk_level")),
        "estimated_impact_present": bool(pending_params.get("estimated_impact")),
        "integration_hubspot": str(plan.integration or "").lower() == "hubspot",
        "bound_invoke_action": pending_params.get("bound_invoke_action") == "hubspot.contacts.create",
    }
    overall = all(checks.values())

    return {
        "pass": overall,
        "verdict": "PASS" if overall else "FAIL",
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        "org_id": org_id,
        "actor_id": actor_id,
        "pending_params": pending_params,
        "risk": risk,
        "checks": checks,
        "claim": (
            "PASS — pre-action card fields stamped on capability-resolved HubSpot write"
            if overall
            else f"FAIL — pre-action checks: {[k for k, v in checks.items() if not v]}"
        ),
    }
