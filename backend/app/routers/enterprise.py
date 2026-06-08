"""Enterprise platform APIs — Tier 4 compliance, branding, analytics, SIEM (STA-80–95)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.billing.service import get_plan_for_org, require_feature
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.services.autonomous_budget_service import (
    get_org_autonomous_budget_defaults,
    list_operator_budget_statuses,
    update_org_autonomous_budget_defaults,
)
from app.services.branding_service import (
    ensure_domain_verification_token,
    get_org_branding,
    mark_domain_verified,
    merge_branding,
)
from app.services.compliance_service import build_soc2_evidence_bundle
from app.services.data_residency_service import (
    get_org_data_region,
    normalize_region,
    resolve_execution_region,
    storage_prefix,
)
from app.services.domain_verification_service import build_verification_instructions, verify_custom_domain
from app.services.enterprise_secrets_service import encrypt_enterprise_secret, resolve_siem_secret
from app.services.siem_export_service import build_siem_event, dispatch_siem_event
from app.services.workforce_analytics_service import build_workforce_analytics
from app.services.integration_suggestion_service import (
    IntegrationSuggestionError,
    dismiss_integration_suggestion,
    list_integration_suggestions,
    scan_integration_suggestions,
)
from app.services.hipaa_service import accept_baa, get_hipaa_status, set_hipaa_enabled, set_connector_phi_capable
from app.services.transparency_service import build_transparency_export_bundle, list_decision_logs
from app.workers.queue import is_queue_available
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


class DataRegionUpdate(BaseModel):
    region: str = Field(..., pattern="^(us|eu)$")


class BrandingUpdate(BaseModel):
    logo_url: str | None = Field(default=None, alias="logoUrl")
    primary_color: str | None = Field(default=None, alias="primaryColor")
    custom_domain: str | None = Field(default=None, alias="customDomain")
    hide_powered_by: bool | None = Field(default=None, alias="hidePoweredBy")
    email_from_name: str | None = Field(default=None, alias="emailFromName")


class SiemConfigUpdate(BaseModel):
    endpoint: str
    secret: str | None = None
    enabled: bool = True


class SiemTestRequest(BaseModel):
    endpoint: str
    secret: str


class AutonomousRunBudgetUpdate(BaseModel):
    max_actions_per_day: int | None = Field(default=None, ge=0, alias="maxActionsPerDay")
    max_tokens_per_day: int | None = Field(default=None, ge=0, alias="maxTokensPerDay")
    max_spend_usd_per_day: float | None = Field(default=None, ge=0, alias="maxSpendUsdPerDay")
    unset: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AgentRunBudgetUpdate(AutonomousRunBudgetUpdate):
    agent_id: str = Field(alias="agentId")

    model_config = {"populate_by_name": True}


class HipaaAcceptBaaRequest(BaseModel):
    baa_version: str | None = Field(default=None, alias="baaVersion")

    model_config = {"populate_by_name": True}


class HipaaModeUpdate(BaseModel):
    enabled: bool


class ConnectorPhiUpdate(BaseModel):
    phi_capable: bool = Field(alias="phiCapable")

    model_config = {"populate_by_name": True}


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings,data_region").eq("id", org_id).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    settings = row.data[0].get("settings") or {}
    return settings if isinstance(settings, dict) else {}


def _org_data_region_column(client: Any, org_id: str) -> str | None:
    row = client.table("organizations").select("data_region").eq("id", org_id).limit(1).execute()
    if not row.data:
        return None
    value = row.data[0].get("data_region")
    return str(value) if value else None


def _save_org_settings(client: Any, org_id: str, settings: dict[str, Any], *, data_region: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"settings": settings}
    if data_region is not None:
        payload["data_region"] = data_region
    updated = client.table("organizations").update(payload).eq("id", org_id).execute()
    if not updated.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    return updated.data[0].get("settings") or {}


def _parse_window(from_ts: str | None, to_ts: str | None) -> tuple[str | None, str | None]:
    return from_ts, to_ts


def _filter_rows_by_window(rows: list[dict[str, Any]], from_ts: str | None, to_ts: str | None) -> list[dict[str, Any]]:
    if not from_ts and not to_ts:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        created_at = str(row.get("created_at") or "")
        if from_ts and created_at and created_at < from_ts:
            continue
        if to_ts and created_at and created_at > to_ts:
            continue
        filtered.append(row)
    return filtered


@router.get("/data-region")
async def get_data_region(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    column_region = _org_data_region_column(client, org_id)
    region = get_org_data_region(org_settings, data_region=column_region)
    return {"region": region, "storagePrefix": storage_prefix(org_id, region)}


@router.put("/data-region")
async def update_data_region(
    body: DataRegionUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    region = normalize_region(body.region)
    enterprise = dict(org_settings.get("enterprise") or {})
    enterprise["dataResidency"] = {"region": region}
    org_settings["enterprise"] = enterprise
    org_settings["data_region"] = region
    saved = _save_org_settings(client, org_id, org_settings, data_region=region)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="enterprise.data_region.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"region": region},
    )
    return {"region": get_org_data_region(saved), "storagePrefix": storage_prefix(org_id, region)}


@router.get("/execution-region")
async def get_execution_region(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    region = resolve_execution_region(org_settings, data_region=_org_data_region_column(client, org_id))
    return {"region": region, "queueAvailable": is_queue_available()}


@router.get("/compliance/soc2-export")
async def export_soc2_bundle(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    audit_logs = client.table("audit_logs").select("*").eq("org_id", org_id).execute().data or []
    audit_logs = _filter_rows_by_window(audit_logs, from_ts, to_ts)
    tool_events = [row for row in audit_logs if str(row.get("action") or "").startswith("tool.invoke")]
    connector_events = [row for row in audit_logs if "connector" in str(row.get("action") or "")]
    admin_events = [row for row in audit_logs if str(row.get("action") or "").startswith(("settings.", "enterprise.", "sso."))]
    return build_soc2_evidence_bundle(
        org_id=org_id,
        audit_logs=audit_logs,
        tool_events=tool_events,
        connector_events=connector_events,
        admin_events=admin_events,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/branding")
async def get_branding(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    raw_settings = _org_settings(client, org_id)
    org_settings = ensure_domain_verification_token(raw_settings)
    if org_settings != raw_settings:
        _save_org_settings(client, org_id, org_settings)
    branding = get_org_branding(org_settings)
    token = branding.get("domainVerificationToken")
    domain = branding.get("customDomain")
    if domain and token:
        branding["domainVerification"] = build_verification_instructions(
            domain=str(domain),
            token=str(token),
            cname_target=settings.enterprise_custom_domain_cname_target,
        )
    return branding


@router.get("/branding/domain-instructions")
async def get_domain_verification_instructions(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    raw_settings = _org_settings(client, org_id)
    org_settings = ensure_domain_verification_token(raw_settings)
    if org_settings != raw_settings:
        _save_org_settings(client, org_id, org_settings)
    branding = get_org_branding(org_settings)
    domain = branding.get("customDomain")
    token = branding.get("domainVerificationToken")
    if not domain or not token:
        raise HTTPException(status_code=400, detail="Set a custom domain before requesting verification instructions")
    return build_verification_instructions(
        domain=str(domain),
        token=str(token),
        cname_target=settings.enterprise_custom_domain_cname_target,
    )


@router.post("/branding/verify-domain")
async def verify_branding_domain(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    raw_settings = _org_settings(client, org_id)
    org_settings = ensure_domain_verification_token(raw_settings)
    if org_settings != raw_settings:
        _save_org_settings(client, org_id, org_settings)
    branding = get_org_branding(org_settings)
    domain = branding.get("customDomain")
    token = branding.get("domainVerificationToken")
    if not domain or not token:
        raise HTTPException(status_code=400, detail="Custom domain and verification token required")
    result = verify_custom_domain(
        domain=str(domain),
        token=str(token),
        cname_target=settings.enterprise_custom_domain_cname_target,
    )
    if result.get("verified"):
        saved = mark_domain_verified(org_settings, verified_at=datetime.now(timezone.utc).isoformat())
        _save_org_settings(client, org_id, saved)
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=_user["user_id"],
            action="enterprise.branding.domain_verified",
            resource_type="organization",
            resource_id=org_id,
            metadata={"domain": domain, "method": result.get("method")},
        )
    return result


@router.put("/branding")
async def update_branding(
    body: BrandingUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    updates = body.model_dump(by_alias=True, exclude_none=True)
    merged = ensure_domain_verification_token(merge_branding(org_settings, updates))
    _save_org_settings(client, org_id, merged)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="enterprise.branding.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"keys": sorted(updates.keys())},
    )
    return get_org_branding(merged)


@router.get("/workforce-analytics")
async def workforce_analytics(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    jobs = client.table("agent_jobs").select("status,kind,created_at").eq("org_id", org_id).execute().data or []
    audit_logs = client.table("audit_logs").select("action,details,created_at").eq("org_id", org_id).execute().data or []
    handoffs = [row for row in audit_logs if "handoff" in str(row.get("action") or "")]
    return build_workforce_analytics(agent_jobs=jobs, audit_logs=audit_logs, handoff_events=handoffs)


class IntegrationSuggestionScanResponse(BaseModel):
    lookback_days: int = Field(alias="lookbackDays")
    usage: dict[str, Any]
    suggestion_count: int = Field(alias="suggestionCount")
    suggestions: list[dict[str, Any]]
    scanned_at: str = Field(alias="scannedAt")

    model_config = {"populate_by_name": True}


@router.get("/integration-suggestions")
async def get_integration_suggestions(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status: str = Query(default="open"),
    connector_type: str | None = Query(default=None, alias="connectorType"),
) -> dict[str, Any]:
    """List audit-driven connector and workflow suggestions (STA-123)."""
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    if status not in {"open", "dismissed", "applied"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    suggestions = list_integration_suggestions(
        client,
        org_id,
        status=status,
        connector_type=connector_type,
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@router.post("/integration-suggestions/scan", response_model=IntegrationSuggestionScanResponse)
async def scan_integration_suggestions_route(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    lookback_days: int = Query(default=30, ge=7, le=90, alias="lookbackDays"),
) -> IntegrationSuggestionScanResponse:
    """Analyze audit tool usage and persist integration suggestions (STA-123)."""
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    summary = scan_integration_suggestions(
        client,
        org_id,
        lookback_days=lookback_days,
        actor_id=current_user["user_id"],
    )
    return IntegrationSuggestionScanResponse(**summary)


@router.post("/integration-suggestions/{suggestion_id}/dismiss")
async def dismiss_integration_suggestion_route(
    suggestion_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Dismiss an integration suggestion (STA-123)."""
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        suggestion = dismiss_integration_suggestion(client, org_id, suggestion_id)
    except IntegrationSuggestionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"suggestion": suggestion}


@router.get("/cost-attribution")
async def cost_attribution(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = (
        client.table("usage_events")
        .select("category,cost_usd,amount_usd,metadata,created_at")
        .eq("org_id", org_id)
        .gte("created_at", month_start.isoformat())
        .execute()
        .data
        or []
    )
    return aggregate_agent_costs(usage_rows=usage)


@router.get("/autonomous-run-budgets")
async def get_autonomous_run_budgets(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {
        "orgDefaults": get_org_autonomous_budget_defaults(client, org_id),
        "agents": list_operator_budget_statuses(client, org_id),
    }


@router.put("/autonomous-run-budgets")
async def update_autonomous_run_budgets(
    body: AutonomousRunBudgetUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_defaults = update_org_autonomous_budget_defaults(
        client,
        org_id=org_id,
        max_actions_per_day=body.max_actions_per_day,
        max_tokens_per_day=body.max_tokens_per_day,
        max_spend_usd_per_day=body.max_spend_usd_per_day,
        actor_id=user["user_id"],
        unset=set(body.unset or []),
    )
    return {
        "orgDefaults": org_defaults,
        "agents": list_operator_budget_statuses(client, org_id),
    }


@router.get("/hipaa")
async def get_hipaa_status_route(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return get_hipaa_status(client, org_id)


@router.post("/hipaa/accept-baa")
async def accept_hipaa_baa_route(
    body: HipaaAcceptBaaRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return accept_baa(client, org_id=org_id, actor_id=user["user_id"], baa_version=body.baa_version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/hipaa")
async def update_hipaa_mode_route(
    body: HipaaModeUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return set_hipaa_enabled(client, org_id=org_id, actor_id=user["user_id"], enabled=body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/connectors/{connector_id}/phi")
async def update_connector_phi_route(
    connector_id: UUID,
    body: ConnectorPhiUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        row = set_connector_phi_capable(
            client,
            org_id=org_id,
            connector_id=str(connector_id),
            phi_capable=body.phi_capable,
            actor_id=user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"connectorId": str(connector_id), "phiCapable": bool(row.get("phi_capable"))}


@router.get("/transparency-logs")
async def get_transparency_logs_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    logs = list_decision_logs(client, org_id, from_ts=from_ts, to_ts=to_ts, limit=limit)
    return {"decisions": logs, "count": len(logs)}


@router.get("/transparency-logs/export")
async def export_transparency_logs_route(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    return build_transparency_export_bundle(
        client,
        org_id,
        actor_id=user["user_id"],
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/siem")
async def get_siem_config(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    enterprise = org_settings.get("enterprise") if isinstance(org_settings.get("enterprise"), dict) else {}
    siem = enterprise.get("siem") if isinstance(enterprise.get("siem"), dict) else {}
    has_secret = bool(resolve_siem_secret(siem, settings) or siem.get("secretEnc") or siem.get("secret"))
    return {
        "enabled": bool(siem.get("enabled")),
        "endpoint": siem.get("endpoint"),
        "hasSecret": has_secret,
    }


@router.put("/siem")
async def update_siem_config(
    body: SiemConfigUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    enterprise = dict(org_settings.get("enterprise") or {})
    existing_siem = enterprise.get("siem") if isinstance(enterprise.get("siem"), dict) else {}
    secret_plain = (body.secret or "").strip()
    if not secret_plain:
        secret_plain = resolve_siem_secret(existing_siem, settings) or ""
    if not secret_plain:
        raise HTTPException(status_code=400, detail="SIEM signing secret is required")
    enterprise["siem"] = {
        "enabled": body.enabled,
        "endpoint": body.endpoint.strip(),
        "secretEnc": encrypt_enterprise_secret(secret_plain, settings),
    }
    org_settings["enterprise"] = enterprise
    _save_org_settings(client, org_id, org_settings)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="enterprise.siem.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"enabled": body.enabled},
    )
    return {"enabled": body.enabled, "endpoint": body.endpoint.strip(), "hasSecret": True}


@router.post("/siem/test")
async def test_siem_delivery(
    body: SiemTestRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    event = build_siem_event(
        org_id=org_id,
        action="enterprise.siem.test",
        resource_type="organization",
        resource_id=org_id,
        metadata={"actorId": _user["user_id"]},
    )
    return dispatch_siem_event(endpoint=body.endpoint.strip(), secret=body.secret.strip(), event=event)
