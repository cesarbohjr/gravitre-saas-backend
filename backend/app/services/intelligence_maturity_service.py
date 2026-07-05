"""Intelligence maturity model — executive-friendly platform growth indicator."""
from __future__ import annotations

from typing import Any

MATURITY_LEVELS: list[dict[str, Any]] = [
    {"level": 1, "label": "Connected", "description": "Integrations and knowledge sources are connected."},
    {"level": 2, "label": "Learning", "description": "The org is collecting outcomes and learning signals."},
    {"level": 3, "label": "Adaptive", "description": "Domain-segment learning is producing confident adaptations."},
    {"level": 4, "label": "Optimizing", "description": "Freshness, retrieval, and optimization loops are active."},
    {"level": 5, "label": "Autonomous Intelligence", "description": "Mature intelligence across domains with strong trust and workflow adoption."},
]


class IntelligenceMaturityService:
    """Calculates org intelligence maturity from observable platform signals."""

    async def compute_maturity(self, org_id: str, *, settings: Any | None = None) -> dict[str, Any]:
        from app.config import get_settings
        from app.workflows.repository import get_supabase_client

        cfg = settings or get_settings()
        client = get_supabase_client(cfg)

        connector_count = self._count_connectors(client, org_id)
        assignment_count = self._count_assignments(client, org_id)
        workflow_runs = self._count_workflow_runs(client, org_id)
        learning_segments = await self._learning_segment_stats(org_id, cfg)
        freshness = await self._freshness_stats(org_id, cfg)
        optimization_pending = await self._optimization_pending(org_id, cfg)
        retrieval_score = learning_segments.get("avg_retrieval_effectiveness")

        factors = {
            "connector_coverage": connector_count,
            "knowledge_assignments": assignment_count,
            "learning_segments": learning_segments.get("segment_count", 0),
            "high_confidence_segments": learning_segments.get("high_confidence_segments", 0),
            "avg_retrieval_effectiveness": retrieval_score,
            "freshness_label": freshness.get("freshness_label"),
            "stale_source_count": len(freshness.get("stale_sources") or []),
            "optimization_pending": optimization_pending,
            "workflow_runs": workflow_runs,
        }

        level = 1
        if connector_count > 0 or assignment_count > 0:
            level = 1
        if learning_segments.get("segment_count", 0) > 0 or learning_segments.get("total_samples", 0) >= 5:
            level = max(level, 2)
        if learning_segments.get("high_confidence_segments", 0) >= 1:
            level = max(level, 3)
        if optimization_pending >= 0 and freshness.get("freshness_label") in {"fresh", "mixed"}:
            if learning_segments.get("medium_or_high_segments", 0) >= 1:
                level = max(level, 4)
        if (
            level >= 4
            and learning_segments.get("high_confidence_segments", 0) >= 2
            and (retrieval_score or 0) >= 0.7
            and workflow_runs >= 10
            and len(freshness.get("stale_sources") or []) <= 1
        ):
            level = 5

        entry = next((row for row in MATURITY_LEVELS if row["level"] == level), MATURITY_LEVELS[0])
        return {
            "level": entry["level"],
            "label": entry["label"],
            "description": entry["description"],
            "factors": factors,
        }

    @staticmethod
    def _count_connectors(client: Any, org_id: str) -> int:
        try:
            rows = (
                client.table("connectors")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("status", "connected")
                .execute()
            )
            return int(rows.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _count_assignments(client: Any, org_id: str) -> int:
        try:
            rows = (
                client.table("agent_knowledge_assignments")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("enabled", True)
                .execute()
            )
            return int(rows.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _count_workflow_runs(client: Any, org_id: str) -> int:
        try:
            rows = (
                client.table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            return int(rows.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def _learning_segment_stats(self, org_id: str, settings: Any) -> dict[str, Any]:
        try:
            from app.workflows.repository import get_supabase_client
            from app.services.learning_confidence_service import get_learning_confidence_service

            rows = (
                get_supabase_client(settings)
                .table("domain_segment_learning_state")
                .select("sample_count, positive_count, negative_count, noise_score, outcome_multiplier")
                .eq("org_id", org_id)
                .limit(200)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []
        confidence = get_learning_confidence_service(settings)
        high = medium = 0
        total_samples = 0
        for row in rows:
            assessment = confidence.assess(
                sample_count=int(row.get("sample_count") or 0),
                positive_count=int(row.get("positive_count") or 0),
                negative_count=int(row.get("negative_count") or 0),
                noise_score=float(row.get("noise_score") or 0),
            )
            total_samples += int(row.get("sample_count") or 0)
            if assessment.level == "high":
                high += 1
            elif assessment.level == "medium":
                medium += 1
        return {
            "segment_count": len(rows),
            "high_confidence_segments": high,
            "medium_or_high_segments": high + medium,
            "total_samples": total_samples,
            "avg_retrieval_effectiveness": None,
        }

    async def _freshness_stats(self, org_id: str, settings: Any) -> dict[str, Any]:
        from app.services.knowledge_freshness_service import get_knowledge_freshness_service

        return await get_knowledge_freshness_service(settings).load_admin_summary(org_id)

    async def _optimization_pending(self, org_id: str, settings: Any) -> int:
        from app.services.domain_optimization_engine import get_domain_optimization_engine

        summary = await get_domain_optimization_engine(settings).get_admin_summary(org_id)
        return int(summary.get("pending_count") or 0)


_service: IntelligenceMaturityService | None = None


def get_intelligence_maturity_service() -> IntelligenceMaturityService:
    global _service
    if _service is None:
        _service = IntelligenceMaturityService()
    return _service
