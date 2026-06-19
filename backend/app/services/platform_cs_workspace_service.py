"""Cross-org CS workspace rollups for Gravitre platform operators (Tier 6)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.integration_health_score_service import backfill_missing_integration_health_snapshots

logger = logging.getLogger(__name__)

GRADE_ORDER = {"critical": 0, "at_risk": 1, "healthy": 2}


class PlatformCsWorkspaceError(Exception):
    code = "PLATFORM_CS_WORKSPACE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def _select_rows(client: Any, table: str, build_query) -> list[dict[str, Any]]:
    try:
        result = build_query(client.table(table)).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise
    if _is_missing_table_error(getattr(result, "error", None)):
        return []
    data = getattr(result, "data", None)
    return list(data or [])


def _latest_snapshots_by_org(client: Any, *, limit: int) -> dict[str, dict[str, Any]]:
    rows = _select_rows(
        client,
        "integration_health_snapshots",
        lambda table: table.select("org_id, score, grade, risks, recorded_at, lookback_days")
        .order("recorded_at", desc=True)
        .limit(max(limit * 4, 40)),
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        org_id = str(row.get("org_id") or "")
        if org_id and org_id not in latest:
            latest[org_id] = row
    return latest


def _load_queue_actions(client: Any, org_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not org_ids:
        return {}
    rows = _select_rows(
        client,
        "platform_cs_tenant_queue",
        lambda table: table.select(
            "org_id, assigned_to, assigned_email, assigned_at, snoozed_until, note, updated_at"
        ).in_("org_id", org_ids),
    )
    return {str(row.get("org_id")): row for row in rows if row.get("org_id")}


def _serialize_queue(row: dict[str, Any]) -> dict[str, Any]:
    snoozed_until = row.get("snoozed_until")
    is_snoozed = False
    if snoozed_until:
        try:
            until = datetime.fromisoformat(str(snoozed_until).replace("Z", "+00:00"))
            is_snoozed = until > _now()
        except ValueError:
            is_snoozed = False
    return {
        "orgId": row.get("org_id"),
        "assignedTo": row.get("assigned_to"),
        "assignedEmail": row.get("assigned_email"),
        "assignedAt": row.get("assigned_at"),
        "snoozedUntil": snoozed_until,
        "isSnoozed": is_snoozed,
        "note": row.get("note"),
        "updatedAt": row.get("updated_at"),
    }


def _open_alert_counts(client: Any, org_ids: list[str]) -> dict[str, dict[str, int]]:
    if not org_ids:
        return {}
    suggestions = _select_rows(
        client,
        "integration_suggestions",
        lambda table: table.select("org_id").eq("status", "open").in_("org_id", org_ids),
    )
    suggestion_counts: dict[str, int] = {}
    for row in suggestions:
        org_id = str(row.get("org_id") or "")
        suggestion_counts[org_id] = suggestion_counts.get(org_id, 0) + 1

    failures = _select_rows(
        client,
        "workflow_failure_alerts",
        lambda table: table.select("org_id").eq("status", "open").in_("org_id", org_ids),
    )
    failure_counts: dict[str, int] = {}
    for row in failures:
        org_id = str(row.get("org_id") or "")
        failure_counts[org_id] = failure_counts.get(org_id, 0) + 1

    return {
        org_id: {
            "openSuggestions": suggestion_counts.get(org_id, 0),
            "activeFailureAlerts": failure_counts.get(org_id, 0),
        }
        for org_id in org_ids
    }


def list_platform_tenant_summaries(
    client: Any,
    *,
    limit: int = 50,
    grade: str | None = None,
    hide_snoozed: bool = False,
) -> dict[str, Any]:
    """Return cross-org health rollups for platform operators."""
    limit = max(1, min(limit, 100))
    orgs = _select_rows(
        client,
        "organizations",
        lambda table: table.select("id, name, slug, created_at").order("created_at", desc=True).limit(limit),
    )
    org_ids = [str(row["id"]) for row in orgs if row.get("id")]
    snapshots = _latest_snapshots_by_org(client, limit=limit)
    alert_counts = _open_alert_counts(client, org_ids)
    queue_actions = _load_queue_actions(client, org_ids)

    tenants: list[dict[str, Any]] = []
    for org in orgs:
        org_id = str(org.get("id") or "")
        snap = snapshots.get(org_id)
        risks = snap.get("risks") if snap else []
        counts = alert_counts.get(org_id, {})
        tenant_grade = snap.get("grade") if snap else None
        queue_row = queue_actions.get(org_id)
        queue = _serialize_queue(queue_row) if queue_row else {
            "orgId": org_id,
            "assignedTo": None,
            "assignedEmail": None,
            "assignedAt": None,
            "snoozedUntil": None,
            "isSnoozed": False,
            "note": None,
            "updatedAt": None,
        }
        if hide_snoozed and queue.get("isSnoozed"):
            continue
        if grade and tenant_grade and tenant_grade != grade:
            continue
        needs_attention = tenant_grade in {"critical", "at_risk"} and not queue.get("isSnoozed")
        tenants.append(
            {
                "orgId": org_id,
                "name": org.get("name") or "Organization",
                "slug": org.get("slug"),
                "createdAt": org.get("created_at"),
                "healthScore": snap.get("score") if snap else None,
                "healthGrade": tenant_grade,
                "healthRecordedAt": snap.get("recorded_at") if snap else None,
                "lookbackDays": snap.get("lookback_days") if snap else None,
                "riskCount": len(risks or []),
                "openSuggestions": counts.get("openSuggestions", 0),
                "activeFailureAlerts": counts.get("activeFailureAlerts", 0),
                "assignedTo": queue.get("assignedTo"),
                "assignedEmail": queue.get("assignedEmail"),
                "assignedAt": queue.get("assignedAt"),
                "snoozedUntil": queue.get("snoozedUntil"),
                "isSnoozed": queue.get("isSnoozed"),
                "queueNote": queue.get("note"),
                "needsAttention": needs_attention,
            }
        )

    tenants.sort(
        key=lambda row: (
            0 if row.get("needsAttention") else 1,
            GRADE_ORDER.get(str(row.get("healthGrade") or ""), 99),
            row.get("healthScore") if row.get("healthScore") is not None else 101,
            row.get("name") or "",
        ),
    )

    at_risk = sum(1 for row in tenants if row.get("healthGrade") == "at_risk")
    critical = sum(1 for row in tenants if row.get("healthGrade") == "critical")
    healthy = sum(1 for row in tenants if row.get("healthGrade") == "healthy")
    no_snapshot = sum(1 for row in tenants if row.get("healthGrade") is None)
    needs_attention = sum(1 for row in tenants if row.get("needsAttention"))

    return {
        "tenants": tenants,
        "summary": {
            "total": len(tenants),
            "healthy": healthy,
            "atRisk": at_risk,
            "critical": critical,
            "noSnapshot": no_snapshot,
            "needsAttention": needs_attention,
        },
    }


def assign_platform_tenant(
    client: Any,
    org_id: str,
    *,
    assignee_user_id: str,
    assignee_email: str | None = None,
    note: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "assigned_to": assignee_user_id,
        "assigned_email": assignee_email,
        "assigned_at": _now_iso(),
        "note": note,
        "updated_at": _now_iso(),
        "updated_by": actor_id,
    }
    try:
        result = client.table("platform_cs_tenant_queue").upsert(row, on_conflict="org_id").execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise PlatformCsWorkspaceError(
                "Platform CS queue table missing — run migrations",
                code="QUEUE_TABLE_MISSING",
            ) from exc
        raise
    saved = (result.data or [row])[0]
    return _serialize_queue(saved)


def snooze_platform_tenant(
    client: Any,
    org_id: str,
    *,
    hours: int = 24,
    actor_id: str | None = None,
) -> dict[str, Any]:
    hours = max(1, min(hours, 24 * 14))
    until = (_now() + timedelta(hours=hours)).isoformat()
    existing = _load_queue_actions(client, [org_id]).get(org_id, {})
    row = {
        "org_id": org_id,
        "assigned_to": existing.get("assigned_to"),
        "assigned_email": existing.get("assigned_email"),
        "assigned_at": existing.get("assigned_at"),
        "snoozed_until": until,
        "note": existing.get("note"),
        "updated_at": _now_iso(),
        "updated_by": actor_id,
    }
    try:
        result = client.table("platform_cs_tenant_queue").upsert(row, on_conflict="org_id").execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise PlatformCsWorkspaceError(
                "Platform CS queue table missing — run migrations",
                code="QUEUE_TABLE_MISSING",
            ) from exc
        raise
    saved = (result.data or [row])[0]
    payload = _serialize_queue(saved)
    payload["snoozeHours"] = hours
    return payload


def backfill_platform_health_snapshots(
    client: Any,
    *,
    limit: int = 25,
    lookback_days: int = 30,
    actor_id: str | None = None,
) -> dict[str, Any]:
    return backfill_missing_integration_health_snapshots(
        client,
        limit=limit,
        lookback_days=lookback_days,
        actor_id=actor_id,
    )


def _org_name_map(client: Any, org_ids: list[str]) -> dict[str, str]:
    if not org_ids:
        return {}
    rows = _select_rows(
        client,
        "organizations",
        lambda table: table.select("id, name").in_("id", org_ids),
    )
    return {str(row["id"]): str(row.get("name") or "Organization") for row in rows if row.get("id")}


def list_platform_cs_alerts(
    client: Any,
    *,
    limit: int = 50,
    offset: int = 0,
    alert_type: str | None = None,
) -> dict[str, Any]:
    """Cross-org open failure alerts and integration suggestions for platform operators."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    alerts: list[dict[str, Any]] = []

    if alert_type in (None, "failure"):
        failure_rows = _select_rows(
            client,
            "workflow_failure_alerts",
            lambda table: table.select(
                "id, org_id, workflow_id, alert_type, severity, title, message, predicted_at, status"
            )
            .eq("status", "open")
            .order("predicted_at", desc=True)
            .limit(limit + offset),
        )
        for row in failure_rows[offset : offset + limit]:
            alerts.append(
                {
                    "id": str(row.get("id")),
                    "orgId": str(row.get("org_id")),
                    "kind": "failure",
                    "severity": row.get("severity"),
                    "title": row.get("title"),
                    "message": row.get("message"),
                    "workflowId": str(row.get("workflow_id")) if row.get("workflow_id") else None,
                    "alertType": row.get("alert_type"),
                    "occurredAt": row.get("predicted_at"),
                }
            )

    if alert_type in (None, "suggestion") and len(alerts) < limit:
        suggestion_rows = _select_rows(
            client,
            "integration_suggestions",
            lambda table: table.select(
                "id, org_id, suggestion_type, title, message, priority, suggested_at, status"
            )
            .eq("status", "open")
            .order("priority", desc=False)
            .order("suggested_at", desc=True)
            .limit(limit + offset),
        )
        for row in suggestion_rows[offset : offset + limit]:
            alerts.append(
                {
                    "id": str(row.get("id")),
                    "orgId": str(row.get("org_id")),
                    "kind": "suggestion",
                    "severity": "medium" if (row.get("priority") or 3) <= 2 else "low",
                    "title": row.get("title"),
                    "message": row.get("message"),
                    "suggestionType": row.get("suggestion_type"),
                    "priority": row.get("priority"),
                    "occurredAt": row.get("suggested_at"),
                }
            )

    org_ids = list({str(item["orgId"]) for item in alerts if item.get("orgId")})
    names = _org_name_map(client, org_ids)
    for item in alerts:
        item["orgName"] = names.get(str(item.get("orgId")), "Organization")

    alerts.sort(
        key=lambda row: (
            0 if row.get("kind") == "failure" and row.get("severity") in {"critical", "high"} else 1,
            row.get("occurredAt") or "",
        ),
        reverse=True,
    )
    return {"alerts": alerts[:limit], "count": len(alerts[:limit])}


def escalate_platform_tenant(
    client: Any,
    org_id: str,
    *,
    actor_id: str | None = None,
    actor_email: str | None = None,
    note: str | None = None,
    webhook_url: str | None = None,
    app_base_url: str | None = None,
) -> dict[str, Any]:
    """Notify on-call via webhook and record escalation on the tenant queue row."""
    org_rows = _select_rows(
        client,
        "organizations",
        lambda table: table.select("id, name, slug").eq("id", org_id).limit(1),
    )
    if not org_rows:
        raise PlatformCsWorkspaceError("Organization not found", code="ORG_NOT_FOUND")

    org = org_rows[0]
    org_name = str(org.get("name") or "Organization")
    snapshots = _latest_snapshots_by_org(client, limit=1).get(org_id, {})
    alert_counts = _open_alert_counts(client, [org_id]).get(org_id, {})
    deep_link = None
    if app_base_url:
        base = app_base_url.rstrip("/")
        deep_link = f"{base}/platform/cs-workspace?org={org_id}"

    escalation_note = note or f"Escalated by {actor_email or actor_id or 'platform operator'}"
    existing = _load_queue_actions(client, [org_id]).get(org_id, {})
    row = {
        "org_id": org_id,
        "assigned_to": existing.get("assigned_to") or actor_id,
        "assigned_email": existing.get("assigned_email") or actor_email,
        "assigned_at": existing.get("assigned_at") or _now_iso(),
        "snoozed_until": None,
        "note": escalation_note,
        "updated_at": _now_iso(),
        "updated_by": actor_id,
    }
    try:
        client.table("platform_cs_tenant_queue").upsert(row, on_conflict="org_id").execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise PlatformCsWorkspaceError(
                "Platform CS queue table missing — run migrations",
                code="QUEUE_TABLE_MISSING",
            ) from exc
        raise

    delivered = False
    delivery_error: str | None = None
    url = (webhook_url or "").strip()
    if url:
        payload = {
            "text": f"CS escalation: {org_name} ({org.get('slug') or org_id})",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*CS escalation* — *{org_name}*\n"
                            f"Grade: `{snapshots.get('grade') or 'no snapshot'}` · "
                            f"Score: `{snapshots.get('score') or '—'}`\n"
                            f"Open suggestions: `{alert_counts.get('openSuggestions', 0)}` · "
                            f"Failure alerts: `{alert_counts.get('activeFailureAlerts', 0)}`\n"
                            f"By: {actor_email or actor_id or 'platform operator'}"
                        ),
                    },
                },
            ],
        }
        if deep_link:
            payload["blocks"].append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Open CS workspace"},
                            "url": deep_link,
                        }
                    ],
                }
            )
        if note:
            payload["blocks"].insert(
                1,
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Note: {note}"}},
            )
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            delivered = response.is_success
            if not delivered:
                delivery_error = f"Webhook returned {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            delivery_error = str(exc)
            logger.warning("platform_cs_escalation_webhook_failed org_id=%s error=%s", org_id, exc)
    else:
        delivery_error = "PLATFORM_CS_ESCALATION_WEBHOOK_URL not configured"

    return {
        "orgId": org_id,
        "orgName": org_name,
        "delivered": delivered,
        "deliveryError": delivery_error,
        "deepLink": deep_link,
        "note": escalation_note,
        "escalatedAt": _now_iso(),
    }
