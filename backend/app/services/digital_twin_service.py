"""Admin-entered organizational process inventory — not a simulation engine."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

SIMULATION_REFUSAL = (
    "DigitalTwinService reads declared process inventory only. "
    "Predictive simulation and multi-step what-if modeling remain out of scope (v9 boundary)."
)


class DigitalTwinService:
    """
    Admin-entered organizational model from organization_process_inventory.
    NOT a predictive simulation engine — answers what processes exist and depend on what.
    """

    async def get_automation_opportunities(
        self,
        org_id: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        active = settings or get_settings()
        db = client or get_supabase_client(active)
        rows = (
            db.table("organization_process_inventory")
            .select("*")
            .eq("org_id", org_id)
            .order("automation_potential_score", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        suggestions = (
            db.table("optimization_suggestions")
            .select("id, title, suggestion_type, status")
            .eq("org_id", org_id)
            .eq("status", "pending_review")
            .limit(10)
            .execute()
            .data
            or []
        )
        return {
            "status": "ok",
            "advisory_only": True,
            "scopeNote": SIMULATION_REFUSAL,
            "processes": rows,
            "relatedOptimizationSuggestions": suggestions,
        }

    async def get_department_summary(
        self,
        org_id: str,
        department: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        active = settings or get_settings()
        db = client or get_supabase_client(active)
        rows = (
            db.table("organization_process_inventory")
            .select("*")
            .eq("org_id", org_id)
            .eq("department", department)
            .execute()
            .data
            or []
        )
        manual = sum(1 for row in rows if str(row.get("automation_level") or "") == "manual")
        automated = sum(1 for row in rows if str(row.get("automation_level") or "") == "automated")
        return {
            "status": "ok",
            "advisory_only": True,
            "department": department,
            "processCount": len(rows),
            "manualCount": manual,
            "automatedCount": automated,
            "processes": rows,
            "scopeNote": SIMULATION_REFUSAL,
        }

    async def simulate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "status": "not_available",
            "reason": SIMULATION_REFUSAL,
            "advisory_only": True,
        }


_digital_twin_service: DigitalTwinService | None = None


def get_digital_twin_service() -> DigitalTwinService:
    global _digital_twin_service
    if _digital_twin_service is None:
        _digital_twin_service = DigitalTwinService()
    return _digital_twin_service
