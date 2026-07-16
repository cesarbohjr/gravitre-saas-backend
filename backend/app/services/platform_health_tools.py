"""Platform Health pack tip tools — org-local audit/run telemetry only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _count_audit_actions(client: Any, org_id: str, *, prefix: str, since_iso: str) -> int:
    try:
        result = (
            client.table("audit_events")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .like("action", f"{prefix}%")
            .gte("created_at", since_iso)
            .limit(1)
            .execute()
        )
        count = getattr(result, "count", None)
        if count is not None:
            return int(count)
        return len(result.data or [])
    except Exception:  # noqa: BLE001
        return 0


def _stalled_run_count(client: Any, org_id: str, *, older_than_hours: int = 48) -> int:
    cutoff = (_now() - timedelta(hours=older_than_hours)).isoformat()
    try:
        result = (
            client.table("workflow_runs")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .in_("status", ["pending_approval", "running", "queued", "waiting"])
            .lt("created_at", cutoff)
            .limit(1)
            .execute()
        )
        count = getattr(result, "count", None)
        if count is not None:
            return int(count)
        return len(result.data or [])
    except Exception:  # noqa: BLE001
        return 0


def _pending_approvals(client: Any, org_id: str) -> int:
    try:
        result = (
            client.table("workflow_runs")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("status", "pending_approval")
            .limit(1)
            .execute()
        )
        count = getattr(result, "count", None)
        if count is not None:
            return int(count)
        return len(result.data or [])
    except Exception:  # noqa: BLE001
        return 0


def _build_recommendations(health: dict[str, Any], *, stalled: int, pending: int) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    dims = health.get("dimensions") or {}
    approval = dims.get("approvalLatency") or {}
    p95_min = float(
        approval.get("p95LatencyMinutes")
        or approval.get("p95Minutes")
        or approval.get("p95_minutes")
        or 0
    )
    p95_days = round(p95_min / (60 * 24), 2) if p95_min else 0.0
    if p95_days >= 1.0 or int(approval.get("score") or 100) < 65:
        delay_label = f"{p95_days}" if p95_days else "≥1"
        recs.append(
            {
                "id": "rec.approval_sla",
                "severity": "high",
                "title": "Approval latency elevated",
                "body": (
                    f"Approval delays are adding {delay_label} days to the median governed write (p95). "
                    f"Clear the oldest pending approvals ({pending} currently waiting) or raise approver coverage."
                ),
            }
        )
    success = dims.get("workflowSuccessRate") or {}
    if int(success.get("score") or 100) < 70:
        recs.append(
            {
                "id": "rec.step_failures",
                "severity": "high",
                "title": "Workflow success depressed",
                "body": (
                    "Step failures or failed runs are pulling workflow success below a healthy band. "
                    "Inspect recent workflow.execute.step_failed audits and add a dry-run gate before execute."
                ),
            }
        )
    connectors = dims.get("connectorsLive") or {}
    if int(connectors.get("score") or 100) < 70:
        recs.append(
            {
                "id": "rec.flaky_connector",
                "severity": "high",
                "title": "Connector health weak",
                "body": (
                    "Live connector coverage is weak. Re-auth or quarantine flaky connectors before the next batch workflow."
                ),
            }
        )
    if stalled > 0:
        recs.append(
            {
                "id": "rec.stalled_runs",
                "severity": "medium",
                "title": "Stalled workflow runs",
                "body": f"{stalled} runs have been stalled >48h (pending approval or non-terminal). Clear the oldest queue first.",
            }
        )
    if not recs:
        recs.append(
            {
                "id": "rec.healthy",
                "severity": "info",
                "title": "Platform health nominal",
                "body": "No elevated approval-latency, connector, or stalled-run signals in the current lookback.",
            }
        )
    return recs


def exec_platform_health_snapshot(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    """Compute org-local platform health KPIs + recommendations (no external connectors)."""
    _ = params
    if not ctx.org_id:
        raise ToolValidationError("org context required", code="ORG_REQUIRED")

    lookback_days = 30
    since = (_now() - timedelta(days=lookback_days)).isoformat()

    from app.services.integration_health_score_service import get_integration_health_score

    health = get_integration_health_score(ctx.client, ctx.org_id, lookback_days=lookback_days)
    stalled = _stalled_run_count(ctx.client, ctx.org_id)
    pending = _pending_approvals(ctx.client, ctx.org_id)
    step_failed = _count_audit_actions(ctx.client, ctx.org_id, prefix="workflow.execute.step_failed", since_iso=since)
    tool_failed = _count_audit_actions(ctx.client, ctx.org_id, prefix="tool.invoke.failed", since_iso=since)
    auth_failed = _count_audit_actions(ctx.client, ctx.org_id, prefix="connector.auth.failed", since_iso=since)

    approval = (health.get("dimensions") or {}).get("approvalLatency") or {}
    p95_min = float(
        approval.get("p95LatencyMinutes")
        or approval.get("p95Minutes")
        or approval.get("p95_minutes")
        or 0
    )
    approval_p95_days = round(p95_min / (60 * 24), 3) if p95_min else 0.0

    recommendations = _build_recommendations(health, stalled=stalled, pending=pending)
    snapshot_id = str(uuid4())
    result_url = f"/intelligence/reports?tab=platform-health&snapshot={snapshot_id}"

    data = {
        "snapshotId": snapshot_id,
        "packId": "platform-health-intelligence-pack",
        "vendor": "gravitre_platform",
        "lookbackDays": lookback_days,
        "computedAt": _now().isoformat(),
        "score": health.get("score"),
        "grade": health.get("grade"),
        "dimensions": health.get("dimensions"),
        "kpis": {
            "approvalP95Days": approval_p95_days,
            "pendingApprovals": pending,
            "stalledRunCount": stalled,
            "stepFailedAudits": step_failed,
            "toolFailedAudits": tool_failed,
            "authFailedAudits": auth_failed,
            "overallScore": health.get("score"),
            "grade": health.get("grade"),
        },
        "recommendations": recommendations,
        "result_url": result_url,
        "stopLinesHonored": [
            "internal_data_only",
            "zero_new_external_connectors",
            "reuse_sta124_integration_health",
        ],
    }

    try:
        from app.services.intelligence_pack_tools import emit_pack_source_notification

        top = recommendations[0] if recommendations else {}
        emit_pack_source_notification(
            ctx,
            title=str(top.get("title") or "Platform health snapshot"),
            body=str(top.get("body") or "Platform health snapshot ready."),
            result_url=result_url,
            action="platform.health.snapshot",
        )
    except Exception:  # noqa: BLE001
        pass

    return NormalizedResult(
        success=True,
        action="platform.health.snapshot",
        data=data,
    )


PLATFORM_HEALTH_TOOL_EXECUTORS: dict[str, Any] = {
    "platform.health.snapshot": exec_platform_health_snapshot,
}
