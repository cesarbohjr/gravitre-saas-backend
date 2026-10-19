"""Read models behind Settings > Enterprise (Settings Pages Redesign, Oct 2026).

Aggregates that the redesigned Knowledge sync, Data residency, Workforce,
Cost attribution and Agent ROI sections need and the older enterprise
endpoints do not return. Everything is computed from real rows:

- knowledge sync: ``connectors`` + ``knowledge_sync_jobs`` (+ ``rag_documents`` count)
- workforce: completed ``agent_jobs`` grouped by agent and department
- cost: measured ``model_calls.cost_usd`` (``usage_events`` fallback, as the
  existing ``/cost-attribution`` route does)
- agent ROI: measured cost and completed tasks; labor rate and minutes per
  task are admin-entered estimate inputs stored in ``organizations.settings``
  (no defaults are applied: missing inputs are reported as missing)

This router has no prefix of its own; ``app.routers.enterprise`` includes it,
so every path lives under ``/api/enterprise/insights``. All routes require an
org admin (the Enterprise page is admin-only).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.ingestion_kill_switch import ingestion_disabled
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.data_residency_service import SUPPORTED_REGIONS, get_org_data_region, storage_prefix
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/insights", tags=["enterprise"])

PAGE_SIZE = 1000
MAX_ROWS = 20_000
KNOWLEDGE_DAYS = 14
LIVE_CONNECTOR_STATUSES = {"active", "healthy", "connected"}
REGION_LABELS = {"us": "United States", "eu": "European Union"}
RATE_KEY = "roi_labor_usd_per_hour"
LEGACY_RATE_KEY = "labor_usd_per_hour"
MINUTES_KEY = "roi_minutes_per_task_by_agent"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _read_pages(build_query: Any, *, page_size: int = PAGE_SIZE, max_rows: int = MAX_ROWS) -> tuple[list[dict[str, Any]], bool]:
    """Read every page of a query. Returns (rows, truncated). Missing tables read as empty."""
    rows: list[dict[str, Any]] = []
    start = 0
    while start < max_rows:
        try:
            batch = build_query().range(start, start + page_size - 1).execute().data or []
        except Exception:  # noqa: BLE001 - optional tables / columns read as empty
            return rows, False
        rows.extend(dict(row) for row in batch)
        if len(batch) < page_size:
            return rows, False
        start += page_size
    return rows, True


def _safe_rows(build_query: Any) -> list[dict[str, Any]]:
    try:
        return [dict(row) for row in (build_query().execute().data or [])]
    except Exception:  # noqa: BLE001
        return []


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    rows = client.table("organizations").select("id,settings,data_region").eq("id", org_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    return dict(rows[0])


def _money(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def agent_id_from_job(row: dict[str, Any]) -> str | None:
    """Agent behind an agent_jobs row (same payload keys as the agent ROI report)."""
    payload = safe_normalize_stored_dict(row.get("payload"))
    for key in ("agent_id", "agentId", "operator_id", "operatorId"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def load_agent_directory(client: Any, org_id: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Agents and operators by id with their department, plus the org's department names.

    Department comes from department_resource_assignments when an agent is assigned,
    otherwise from agents.department. Agents with neither have department None.
    """
    directory: dict[str, dict[str, Any]] = {}
    agents = _safe_rows(lambda: client.table("agents").select("id,name,department,created_at").eq("org_id", org_id))
    if not agents:
        agents = _safe_rows(lambda: client.table("agents").select("id,name").eq("org_id", org_id))
    for row in agents:
        aid = str(row.get("id") or "")
        if not aid:
            continue
        department = str(row.get("department") or "").strip() or None
        directory[aid] = {"name": str(row.get("name") or aid), "department": department, "createdAt": row.get("created_at")}
    for row in _safe_rows(lambda: client.table("operators").select("id,name,created_at").eq("org_id", org_id)):
        oid = str(row.get("id") or "")
        if oid and oid not in directory:
            directory[oid] = {"name": str(row.get("name") or oid), "department": None, "createdAt": row.get("created_at")}

    departments = _safe_rows(lambda: client.table("departments").select("id,name").eq("org_id", org_id))
    names_by_id = {str(d.get("id")): str(d.get("name") or "").strip() for d in departments if d.get("id")}
    assignments = _safe_rows(
        lambda: client.table("department_resource_assignments")
        .select("department_id,resource_id,resource_type")
        .eq("org_id", org_id)
        .eq("resource_type", "agent")
    )
    for row in assignments:
        aid = str(row.get("resource_id") or "")
        name = names_by_id.get(str(row.get("department_id") or ""))
        if aid in directory and name:
            directory[aid]["department"] = name
    department_names = sorted({name for name in names_by_id.values() if name}, key=str.lower)
    return directory, department_names


def _agent_name(directory: dict[str, dict[str, Any]], agent_id: str) -> str:
    entry = directory.get(agent_id)
    return str(entry["name"]) if entry else "Unknown agent"


def _agent_department(directory: dict[str, dict[str, Any]], agent_id: str) -> str | None:
    entry = directory.get(agent_id)
    return entry.get("department") if entry else None


def _completed_jobs(client: Any, org_id: str, since: datetime) -> tuple[list[dict[str, Any]], bool]:
    return _read_pages(
        lambda: client.table("agent_jobs")
        .select("id,status,payload,created_at")
        .eq("org_id", org_id)
        .eq("status", "completed")
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
    )


def _cost_rows(client: Any, org_id: str, since: datetime) -> tuple[list[dict[str, Any]], str | None, bool]:
    """Measured cost rows as {agent_id, cost_usd, run_id}. Source is model_calls, else usage_events."""
    model_rows, truncated = _read_pages(
        lambda: client.table("model_calls")
        .select("cost_usd,agent_id,run_id,created_at")
        .eq("org_id", org_id)
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
    )
    if model_rows:
        rows = [
            {"agent_id": r.get("agent_id"), "cost_usd": _money(r.get("cost_usd")), "run_id": r.get("run_id")}
            for r in model_rows
        ]
        return rows, "model_calls", truncated
    usage_rows, truncated = _read_pages(
        lambda: client.table("usage_events")
        .select("category,cost_usd,amount_usd,metadata,created_at")
        .eq("org_id", org_id)
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
    )
    rows = []
    for r in usage_rows:
        meta = safe_normalize_stored_dict(r.get("metadata"))
        amount = _money(r.get("cost_usd") if r.get("cost_usd") is not None else r.get("amount_usd"))
        rows.append(
            {
                "agent_id": meta.get("agent_id") or meta.get("agentId"),
                "cost_usd": amount,
                "run_id": meta.get("run_id") or meta.get("runId"),
            }
        )
    return rows, ("usage_events" if rows else None), truncated


# ---------------------------------------------------------------------------
# Knowledge sync
# ---------------------------------------------------------------------------


def schedule_label(sync_frequency: str | None) -> str:
    """Human text for connectors.sync_frequency, matching parse_sync_interval (default 24h)."""
    from app.services.knowledge_sync_service import parse_sync_interval

    hours = int(parse_sync_interval(sync_frequency).total_seconds() // 3600)
    if hours == 1:
        return "Every hour"
    if hours == 24:
        return "Daily"
    if hours == 168:
        return "Weekly"
    if hours % 24 == 0:
        return f"Every {hours // 24} days"
    return f"Every {hours} hours"


def sync_configured(connector: dict[str, Any]) -> bool:
    """Whether scheduled sync can run for this connector (targets / vendor toggle set)."""
    from app.services.hubspot_knowledge_sync_service import hubspot_knowledge_sync_enabled
    from app.services.knowledge_sync_service import SOURCE_REGISTRY
    from app.services.zendesk_knowledge_sync_service import zendesk_knowledge_sync_enabled

    vendor = str(connector.get("type") or "").lower()
    spec = SOURCE_REGISTRY.get(vendor)
    if not spec:
        return False
    if vendor == "hubspot":
        return hubspot_knowledge_sync_enabled(connector)
    if vendor == "zendesk":
        return zendesk_knowledge_sync_enabled(connector)
    targets = safe_normalize_stored_dict(connector.get("config")).get(spec.get("targets_key") or "")
    return isinstance(targets, list) and bool(targets)


def build_knowledge_sync_overview(
    *,
    connectors: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    documents_indexed: int | None,
    ingestion_off: bool,
    hold_reason_for: Any,
    now: datetime,
) -> dict[str, Any]:
    """Pure aggregation for the Knowledge sync section (jobs: last 14 days, newest first)."""
    today = now.date()
    days = [today - timedelta(days=offset) for offset in range(KNOWLEDGE_DAYS - 1, -1, -1)]
    per_day: dict[str, int] = {d.isoformat(): 0 for d in days}
    window_start = datetime.combine(days[0], datetime.min.time(), tzinfo=timezone.utc)

    latest_by_connector: dict[str, dict[str, Any]] = {}
    docs_by_connector: dict[str, int] = defaultdict(int)
    last_completed: datetime | None = None
    failed = 0
    for job in jobs:
        cid = str(job.get("connector_id") or "")
        created = _parse_dt(job.get("created_at"))
        if cid and cid not in latest_by_connector:
            latest_by_connector[cid] = job
        status = str(job.get("status") or "")
        if created is None or created < window_start:
            continue
        if status == "failed":
            failed += 1
        if status != "completed":
            continue
        done = _parse_dt(job.get("completed_at")) or created
        pages = int(job.get("pages_synced") or 0)
        key = done.date().isoformat()
        if key in per_day:
            per_day[key] += pages
        docs_by_connector[cid] += pages
        if last_completed is None or done > last_completed:
            last_completed = done

    sources: list[dict[str, Any]] = []
    for connector in connectors:
        cid = str(connector.get("id") or "")
        vendor = str(connector.get("type") or "").lower()
        latest = latest_by_connector.get(cid)
        latest_status = str((latest or {}).get("status") or "")
        connector_status = str(connector.get("status") or "").lower()
        configured = sync_configured(connector)
        held = hold_reason_for(vendor)
        if latest_status in {"queued", "running"}:
            status = "syncing"
        elif connector_status not in LIVE_CONNECTOR_STATUSES:
            status = "paused"
        elif latest_status == "failed":
            status = "failed"
        elif not configured:
            status = "not_configured"
        elif latest_status == "completed":
            status = "healthy"
        else:
            status = "never_synced"
        last_sync = connector.get("last_sync_at") or (latest or {}).get("completed_at")
        sources.append(
            {
                "connectorId": cid,
                "name": str(connector.get("name") or vendor.title() or cid),
                "type": vendor,
                "connectorStatus": connector_status or None,
                "status": status,
                "syncConfigured": configured,
                "schedule": schedule_label(connector.get("sync_frequency")),
                "docs14d": docs_by_connector.get(cid, 0),
                "lastSyncAt": last_sync,
                "lastJobStatus": latest_status or None,
                "lastError": (latest or {}).get("error_message") if latest_status == "failed" else None,
                "heldReason": held,
            }
        )
    sources.sort(key=lambda s: s["name"].lower())

    return {
        "ingestionDisabled": ingestion_off,
        "heldReason": hold_reason_for(None),
        "sourcesSyncing": sum(
            1 for s in sources if s["syncConfigured"] and s["status"] not in {"paused", "not_configured"}
        ),
        "sourceCount": len(sources),
        "documentsIndexed": documents_indexed,
        "lastSyncAt": last_completed.isoformat() if last_completed else None,
        "failedJobs": failed,
        "days": [{"date": key, "documents": value} for key, value in per_day.items()],
        "totalDocuments": sum(per_day.values()),
        "windowDays": KNOWLEDGE_DAYS,
        "sources": sources,
    }


@router.get("/knowledge-sync")
def knowledge_sync_overview(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Knowledge sources, 14-day ingest volume and the ingestion kill-switch state."""
    from app.services.ingestion_interlock import existing_ingestion_hold_reason
    from app.services.knowledge_sync_service import SOURCE_REGISTRY

    _user, org_id = admin
    client = shared_service_client(settings, create_client)
    now = _now()
    connectors = _safe_rows(
        lambda: client.table("connectors")
        .select("id,name,type,status,config,sync_frequency,last_sync_at")
        .eq("org_id", org_id)
        .in_("type", list(SOURCE_REGISTRY.keys()))
        .is_("deleted_at", "null")
    )
    since = datetime.combine((now - timedelta(days=KNOWLEDGE_DAYS - 1)).date(), datetime.min.time(), tzinfo=timezone.utc)
    jobs, _truncated = _read_pages(
        lambda: client.table("knowledge_sync_jobs")
        .select("id,connector_id,status,created_at,completed_at,pages_synced,error_message")
        .eq("org_id", org_id)
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
    )
    documents_indexed: int | None
    try:
        counted = client.table("rag_documents").select("id", count="exact").eq("org_id", org_id).limit(1).execute()
        documents_indexed = int(counted.count) if getattr(counted, "count", None) is not None else None
    except Exception:  # noqa: BLE001
        documents_indexed = None

    def hold_reason_for(vendor: str | None) -> str | None:
        try:
            return existing_ingestion_hold_reason(settings, vendor)
        except Exception:  # noqa: BLE001
            return None

    return build_knowledge_sync_overview(
        connectors=connectors,
        jobs=jobs,
        documents_indexed=documents_indexed,
        ingestion_off=ingestion_disabled(settings),
        hold_reason_for=hold_reason_for,
        now=now,
    )


# ---------------------------------------------------------------------------
# Data residency
# ---------------------------------------------------------------------------


def build_residency(*, org_id: str, org_region: str, deployment_region: str) -> dict[str, Any]:
    regions = []
    for rid in sorted(SUPPORTED_REGIONS):
        regions.append(
            {
                "id": rid,
                "label": REGION_LABELS.get(rid, rid.upper()),
                "current": rid == org_region,
                # Only the region this deployment runs in actually stores data; another
                # region needs its own deployment, which Gravitre support arranges.
                "available": rid == deployment_region,
            }
        )
    return {
        "region": org_region,
        "deploymentRegion": deployment_region,
        "storagePrefix": storage_prefix(org_id, org_region),
        "regions": regions,
        "migrationSupported": False,
    }


@router.get("/residency")
def residency(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """The org's data region next to the region this deployment actually runs in."""
    _user, org_id = admin
    client = shared_service_client(settings, create_client)
    org = _org_settings(client, org_id)
    org_region = get_org_data_region(safe_normalize_stored_dict(org.get("settings")), data_region=org.get("data_region"))
    deployment = str(getattr(settings, "deployment_data_region", "us") or "us").strip().lower()
    if deployment not in SUPPORTED_REGIONS:
        deployment = "us"
    return build_residency(org_id=org_id, org_region=org_region, deployment_region=deployment)


# ---------------------------------------------------------------------------
# Workforce
# ---------------------------------------------------------------------------


def build_workforce(
    *,
    jobs: list[dict[str, Any]],
    directory: dict[str, dict[str, Any]],
    department_names: list[str],
    period_days: int,
    now: datetime,
    truncated: bool = False,
) -> dict[str, Any]:
    """Completed task counts for this period and the one before it (jobs cover both)."""
    start = now - timedelta(days=period_days)
    previous_start = start - timedelta(days=period_days)
    current_by_agent: dict[str, int] = defaultdict(int)
    previous_total = 0
    unattributed = 0
    for job in jobs:
        created = _parse_dt(job.get("created_at"))
        if created is None or created < previous_start or created > now:
            continue
        if created < start:
            previous_total += 1
            continue
        aid = agent_id_from_job(job)
        if aid is None:
            unattributed += 1
            continue
        current_by_agent[aid] += 1

    total = sum(current_by_agent.values()) + unattributed
    change_pct = round((total - previous_total) / previous_total * 100) if previous_total > 0 else None

    by_department: dict[str, int] = defaultdict(int)
    for aid, count in current_by_agent.items():
        by_department[_agent_department(directory, aid) or "No department"] += count
    if unattributed:
        by_department["No agent recorded"] += unattributed
    teams = sorted(({"name": k, "tasks": v} for k, v in by_department.items()), key=lambda r: (-r["tasks"], r["name"]))

    using = {name for name in by_department if name in department_names}
    idle = [name for name in department_names if name not in using]
    busiest = sorted(
        (
            {
                "agentId": aid,
                "name": _agent_name(directory, aid),
                "department": _agent_department(directory, aid),
                "tasks": count,
            }
            for aid, count in current_by_agent.items()
        ),
        key=lambda r: (-r["tasks"], r["name"].lower()),
    )[:5]
    new_agents = sum(
        1 for entry in directory.values() if (created := _parse_dt(entry.get("createdAt"))) is not None and created >= start
    )
    return {
        "periodDays": period_days,
        "periodStart": start.isoformat(),
        "periodEnd": now.isoformat(),
        "tasksCompleted": total,
        "previousTasksCompleted": previous_total,
        "changePct": change_pct,
        "activeAgents": len(current_by_agent),
        "newAgents": new_agents,
        "departmentsTotal": len(department_names),
        "departmentsUsing": len(using),
        "departmentsIdle": idle,
        "byDepartment": teams,
        "busiestAgents": busiest,
        "unattributedTasks": unattributed,
        "truncated": truncated,
    }


@router.get("/workforce")
def workforce(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Completed agent tasks by team and agent, with the previous period for comparison."""
    _user, org_id = admin
    client = shared_service_client(settings, create_client)
    now = _now()
    jobs, truncated = _completed_jobs(client, org_id, now - timedelta(days=days * 2))
    directory, departments = load_agent_directory(client, org_id)
    return build_workforce(
        jobs=jobs, directory=directory, department_names=departments, period_days=days, now=now, truncated=truncated
    )


# ---------------------------------------------------------------------------
# Cost attribution
# ---------------------------------------------------------------------------


def build_cost_attribution(
    *,
    rows: list[dict[str, Any]],
    directory: dict[str, dict[str, Any]],
    source: str | None,
    period_start: datetime,
    now: datetime,
    truncated: bool = False,
) -> dict[str, Any]:
    by_agent: dict[str, dict[str, Any]] = {}
    for row in rows:
        aid = str(row.get("agent_id") or "") or "unassigned"
        bucket = by_agent.setdefault(aid, {"cost": 0.0, "calls": 0, "runs": set()})
        bucket["cost"] += _money(row.get("cost_usd"))
        bucket["calls"] += 1
        if row.get("run_id"):
            bucket["runs"].add(str(row["run_id"]))

    agents = []
    departments: dict[str, dict[str, Any]] = {}
    for aid, bucket in by_agent.items():
        assigned = aid != "unassigned"
        name = _agent_name(directory, aid) if assigned else "No agent recorded"
        dept = (_agent_department(directory, aid) if assigned else None) or "No department"
        agents.append(
            {
                "id": aid,
                "name": name,
                "department": dept,
                "costUsd": round(bucket["cost"], 6),
                "calls": bucket["calls"],
                "runs": len(bucket["runs"]),
            }
        )
        group = departments.setdefault(dept, {"cost": 0.0, "calls": 0, "runs": set(), "agents": set()})
        group["cost"] += bucket["cost"]
        group["calls"] += bucket["calls"]
        group["runs"] |= bucket["runs"]
        if assigned:
            group["agents"].add(aid)
    agents.sort(key=lambda r: (-r["costUsd"], r["name"].lower()))
    dept_rows = sorted(
        (
            {
                "id": name,
                "name": name,
                "costUsd": round(g["cost"], 6),
                "calls": g["calls"],
                "runs": len(g["runs"]),
                "agentCount": len(g["agents"]),
            }
            for name, g in departments.items()
        ),
        key=lambda r: (-r["costUsd"], r["name"].lower()),
    )
    return {
        "periodStart": period_start.isoformat(),
        "periodEnd": now.isoformat(),
        "source": source,
        "totalCostUsd": round(sum(a["costUsd"] for a in agents), 6),
        "agentCount": sum(1 for a in agents if a["id"] != "unassigned"),
        "byAgent": agents,
        "byDepartment": dept_rows,
        "truncated": truncated,
    }


@router.get("/cost")
def cost_attribution(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Month-to-date measured spend by agent and by department."""
    _user, org_id = admin
    client = shared_service_client(settings, create_client)
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows, source, truncated = _cost_rows(client, org_id, month_start)
    directory, _departments = load_agent_directory(client, org_id)
    return build_cost_attribution(
        rows=rows, directory=directory, source=source, period_start=month_start, now=now, truncated=truncated
    )


# ---------------------------------------------------------------------------
# Agent ROI
# ---------------------------------------------------------------------------


def read_roi_inputs(org_settings: dict[str, Any]) -> tuple[float | None, dict[str, float]]:
    raw = org_settings.get(RATE_KEY)
    if raw is None:
        raw = org_settings.get(LEGACY_RATE_KEY)
    rate: float | None
    try:
        rate = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        rate = None
    if rate is not None and rate <= 0:
        rate = None
    minutes: dict[str, float] = {}
    for key, value in safe_normalize_stored_dict(org_settings.get(MINUTES_KEY)).items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            minutes[str(key)] = number
    return rate, minutes


def build_agent_roi(
    *,
    jobs: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
    directory: dict[str, dict[str, Any]],
    rate: float | None,
    minutes: dict[str, float],
    period_days: int,
    period_start: datetime,
    now: datetime,
    truncated: bool = False,
) -> dict[str, Any]:
    tasks: dict[str, int] = defaultdict(int)
    for job in jobs:
        created = _parse_dt(job.get("created_at"))
        if created is None or created < period_start:
            continue
        aid = agent_id_from_job(job)
        if aid:
            tasks[aid] += 1
    cost: dict[str, float] = defaultdict(float)
    for row in cost_rows:
        aid = str(row.get("agent_id") or "")
        if aid:
            cost[aid] += _money(row.get("cost_usd"))

    agent_ids = set(directory) | set(tasks) | set(cost)
    agents = []
    included = []
    for aid in agent_ids:
        mins = minutes.get(aid)
        task_count = tasks.get(aid, 0)
        agent_cost = round(cost.get(aid, 0.0), 6)
        value = round(task_count * mins / 60.0 * rate, 4) if (mins and rate) else None
        multiple = round(value / agent_cost, 4) if (value is not None and agent_cost > 0) else None
        row = {
            "agentId": aid,
            "name": _agent_name(directory, aid),
            "department": _agent_department(directory, aid),
            "tasks": task_count,
            "minutesPerTask": mins,
            "costUsd": agent_cost,
            "laborValueUsd": value,
            "returnMultiple": multiple,
        }
        agents.append(row)
        if value is not None and task_count > 0:
            included.append(row)
    agents.sort(key=lambda r: (-r["tasks"], r["name"].lower()))
    included.sort(key=lambda r: (-(r["laborValueUsd"] or 0), r["name"].lower()))

    total_cost = round(sum(r["costUsd"] for r in included), 6)
    total_value = round(sum(r["laborValueUsd"] or 0 for r in included), 4)
    return {
        "periodDays": period_days,
        "periodStart": period_start.isoformat(),
        "periodEnd": now.isoformat(),
        "laborUsdPerHour": rate,
        "agents": agents,
        "rows": included,
        "hiddenWithoutEstimate": sum(1 for r in agents if r["tasks"] > 0 and r["minutesPerTask"] is None),
        "totals": {
            "agentCostUsd": total_cost if included else None,
            "laborValueUsd": total_value if included else None,
            "netValueUsd": round(total_value - total_cost, 4) if included else None,
            "returnMultiple": round(total_value / total_cost, 4) if included and total_cost > 0 else None,
        },
        "truncated": truncated,
    }


@router.get("/agent-roi")
def agent_roi(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Measured agent cost against labor value from the org's own rate and minutes per task."""
    _user, org_id = admin
    client = shared_service_client(settings, create_client)
    now = _now()
    start = now - timedelta(days=days)
    org = _org_settings(client, org_id)
    rate, minutes = read_roi_inputs(safe_normalize_stored_dict(org.get("settings")))
    jobs, jobs_truncated = _completed_jobs(client, org_id, start)
    cost_rows, _source, cost_truncated = _cost_rows(client, org_id, start)
    directory, _departments = load_agent_directory(client, org_id)
    return build_agent_roi(
        jobs=jobs,
        cost_rows=cost_rows,
        directory=directory,
        rate=rate,
        minutes=minutes,
        period_days=days,
        period_start=start,
        now=now,
        truncated=jobs_truncated or cost_truncated,
    )


class AgentRoiInputsUpdate(BaseModel):
    labor_usd_per_hour: float | None = Field(default=None, alias="laborUsdPerHour", gt=0, le=10_000)
    clear_rate: bool = Field(default=False, alias="clearRate")
    minutes_per_task: dict[str, float | None] = Field(default_factory=dict, alias="minutesPerTask")

    model_config = {"populate_by_name": True}


@router.put("/agent-roi")
def update_agent_roi_inputs(
    body: AgentRoiInputsUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Save the hourly labor rate and per-agent minutes per task (admin estimate inputs)."""
    from app.core.org_state_cache import invalidate_org_state

    user, org_id = admin
    client = shared_service_client(settings, create_client)
    org = _org_settings(client, org_id)
    org_settings = safe_normalize_stored_dict(org.get("settings"))
    changed: dict[str, Any] = {}
    if body.clear_rate:
        org_settings.pop(RATE_KEY, None)
        org_settings.pop(LEGACY_RATE_KEY, None)
        changed["laborUsdPerHour"] = None
    elif body.labor_usd_per_hour is not None:
        org_settings[RATE_KEY] = round(float(body.labor_usd_per_hour), 2)
        changed["laborUsdPerHour"] = org_settings[RATE_KEY]
    if body.minutes_per_task:
        current = safe_normalize_stored_dict(org_settings.get(MINUTES_KEY))
        for agent_id, value in body.minutes_per_task.items():
            key = str(agent_id).strip()
            if not key or len(key) > 80:
                raise HTTPException(status_code=400, detail="Invalid agent id")
            if value is None:
                current.pop(key, None)
                continue
            if not (0 < float(value) <= 1440):
                raise HTTPException(status_code=400, detail="Minutes per task must be between 0 and 1440")
            current[key] = round(float(value), 2)
        org_settings[MINUTES_KEY] = current
        changed["minutesPerTaskAgents"] = sorted(body.minutes_per_task.keys())
    if changed:
        client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
        invalidate_org_state(org_id)
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user["user_id"],
            action="enterprise.agent_roi.inputs_updated",
            resource_type="organization",
            resource_id=org_id,
            metadata=changed,
        )
    rate, minutes = read_roi_inputs(org_settings)
    return {"laborUsdPerHour": rate, "minutesPerTask": minutes}
