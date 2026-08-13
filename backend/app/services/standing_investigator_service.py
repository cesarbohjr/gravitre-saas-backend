"""Standing unprompted investigators — read-scoped, advisory-only, admin-notified."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.intelligence_engine_settings import load_intelligence_engine_settings
from app.services.notification_emitter import emit_notification
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

FINDING_ADVISORY_NOTE = (
    "Standing investigator findings are advisory only. "
    "No writes are auto-executed from this path."
)


class StandingInvestigatorService:
    """Run read-scoped org investigations and notify admins. Never auto-execute writes."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def is_enabled(self, org_id: str) -> bool:
        current = await load_intelligence_engine_settings(org_id, self.settings)
        return bool(getattr(current, "standing_investigators_enabled", True))

    async def run_investigation_for_org(self, org_id: str) -> dict[str, Any]:
        if not await self.is_enabled(org_id):
            return {
                "status": "disabled",
                "org_id": org_id,
                "findings": [],
                "advisory_only": True,
                "writes_executed": False,
            }

        findings = await self._collect_read_scoped_findings(org_id)
        persisted = self._persist_findings(org_id, findings)
        notified = self._notify_admins(org_id, persisted)
        return {
            "status": "ok",
            "org_id": org_id,
            "finding_count": len(persisted),
            "findings": persisted,
            "admins_notified": notified,
            "advisory_only": True,
            "writes_executed": False,
            "note": FINDING_ADVISORY_NOTE,
        }

    async def _collect_read_scoped_findings(self, org_id: str) -> list[dict[str, Any]]:
        """Read-only scans. Never invoke connector writes or mutate production config."""
        client = self._client()
        findings: list[dict[str, Any]] = []

        # Failed runs (last 24h)
        try:
            since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            failed = (
                client.table("workflow_runs")
                .select("id,status,created_at")
                .eq("org_id", org_id)
                .eq("status", "failed")
                .gte("created_at", since.isoformat())
                .limit(50)
                .execute()
                .data
                or []
            )
            if failed:
                findings.append(
                    {
                        "finding_type": "failed_workflow_runs",
                        "title": f"{len(failed)} failed workflow run(s) today",
                        "body": (
                            f"Standing investigator observed {len(failed)} failed workflow run(s). "
                            "Review run logs; no automatic remediation was applied."
                        ),
                        "evidence": {
                            "count": len(failed),
                            "run_ids": [str(r.get("id")) for r in failed[:10]],
                            "advisory_only": True,
                        },
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("standing_investigator_failed_runs_skipped org_id=%s error=%s", org_id, exc)

        # Pending approvals backlog
        try:
            pending = (
                client.table("approvals")
                .select("id,status,created_at")
                .eq("org_id", org_id)
                .eq("status", "pending")
                .limit(50)
                .execute()
                .data
                or []
            )
            if len(pending) >= 3:
                findings.append(
                    {
                        "finding_type": "approval_backlog",
                        "title": f"{len(pending)} pending approval(s)",
                        "body": (
                            f"Standing investigator observed {len(pending)} pending approval(s). "
                            "Human review required; investigator did not approve or reject any."
                        ),
                        "evidence": {
                            "count": len(pending),
                            "advisory_only": True,
                        },
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("standing_investigator_approvals_skipped org_id=%s error=%s", org_id, exc)

        # Process mining bottlenecks (advisory)
        try:
            from app.services.process_mining_service import get_process_mining_service

            bottlenecks = await get_process_mining_service(self.settings).detect_process_bottlenecks(org_id)
            top = (bottlenecks.get("bottlenecks") or [])[:3]
            if top:
                findings.append(
                    {
                        "finding_type": "process_bottlenecks",
                        "title": f"{len(top)} process bottleneck(s) flagged",
                        "body": (
                            "Standing investigator flagged recurring slow steps from process mining. "
                            "Suggestions are advisory only and were not adopted."
                        ),
                        "evidence": {
                            "bottlenecks": top,
                            "advisory_only": True,
                        },
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("standing_investigator_mining_skipped org_id=%s error=%s", org_id, exc)

        return findings

    def _persist_findings(self, org_id: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not findings:
            return []
        client = self._client()
        rows = []
        for finding in findings:
            rows.append(
                {
                    "org_id": org_id,
                    "finding_type": finding["finding_type"],
                    "title": finding["title"],
                    "body": finding["body"],
                    "evidence": {**(finding.get("evidence") or {}), "advisory_only": True},
                    "advisory_only": True,
                    "status": "open",
                }
            )
        try:
            inserted = client.table("standing_investigator_findings").insert(rows).execute()
            return list(inserted.data or rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("standing_investigator_persist_failed org_id=%s error=%s", org_id, exc)
            return rows

    def _notify_admins(self, org_id: str, findings: list[dict[str, Any]]) -> int:
        if not findings:
            return 0
        client = self._client()
        admins = (
            client.table("organization_members")
            .select("user_id,role")
            .eq("org_id", org_id)
            .in_("role", ["owner", "admin"])
            .limit(20)
            .execute()
            .data
            or []
        )
        count = len(findings)
        title = f"Standing investigator: {count} issue(s) found"
        body = "; ".join(str(f.get("title") or "") for f in findings[:5])[:2000]
        notified = 0
        for admin in admins:
            user_id = str(admin.get("user_id") or "")
            if not user_id:
                continue
            try:
                emit_notification(
                    client,
                    org_id=org_id,
                    user_id=user_id,
                    event_type="system",
                    title=title,
                    body=body or FINDING_ADVISORY_NOTE,
                    entity_ref={
                        "type": "standing_investigator",
                        "advisory_only": True,
                        "finding_count": count,
                    },
                    channel_hints={"bell": True},
                )
                notified += 1
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "standing_investigator_notify_skipped org_id=%s user_id=%s error=%s",
                    org_id,
                    user_id,
                    exc,
                )
        return notified


_service: StandingInvestigatorService | None = None


def get_standing_investigator_service(settings: Settings | None = None) -> StandingInvestigatorService:
    global _service
    if _service is None or settings is not None:
        _service = StandingInvestigatorService(settings)
    return _service


async def run_standing_investigators_tick(settings: Settings | None = None) -> dict[str, Any]:
    """Scheduler/Temporal-friendly entry: investigate active orgs with setting enabled."""
    from app.services.company_intelligence_collectors import get_active_org_ids

    cfg = settings or get_settings()
    org_ids = get_active_org_ids(cfg, since_days=7, limit=20)
    service = get_standing_investigator_service(cfg)
    results = []
    for org_id in org_ids:
        try:
            results.append(await service.run_investigation_for_org(org_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("standing_investigator_org_failed org_id=%s error=%s", org_id, exc)
            results.append({"org_id": org_id, "status": "error", "advisory_only": True, "error": str(exc)[:200]})
    return {
        "status": "ok",
        "orgs": len(org_ids),
        "results": results,
        "advisory_only": True,
        "writes_executed": False,
    }
