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
