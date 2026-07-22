"""Aggregated status for AI OS, learning, and predictive operations admin endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.ai_architecture_registry import AI_ARCHITECTURE_REGISTRY, count_by_status
from app.config import Settings, get_settings
from app.ml.model_catalog import get_catalog
from app.workflows.repository import get_supabase_client


class AIArchitectureStatusService:
    """Honest aggregation over existing tables — no synthetic metrics."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _since(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    async def get_ai_os_status(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        catalog = get_catalog()
        ml_live = sum(1 for meta in catalog.values() if meta.get("status") in {"trained", "ready", "deployed"})
        ml_planned = sum(
            1 for meta in catalog.values() if str(meta.get("status", "")).lower() in {"planned", "disabled"}
        )
        arch_counts = count_by_status()

        runs = (
            client.table("org_intelligence_runs")
            .select("id, status, completed_at, started_at")
            .eq("org_id", org_id)
            .order("started_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        snapshots = (
            client.table("org_intelligence_snapshots")
            .select("updated_at")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        pending_promotions = (
            client.table("agent_memory_promotion_audit")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("status", "pending")
            .execute()
        )
        last_run = runs[0].get("completed_at") or runs[0].get("started_at") if runs else None
        snapshot_updated = snapshots[0].get("updated_at") if snapshots else None
        freshness = "missing"
        if snapshot_updated:
            try:
                updated_dt = datetime.fromisoformat(str(snapshot_updated).replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - updated_dt
                freshness = "fresh" if age <= timedelta(hours=24) else "stale"
            except (TypeError, ValueError):
                freshness = "stale"

        return {
            "intelligence_engine": {
                "last_run": last_run,
                "orgs_with_snapshots": 1 if snapshots else 0,
                "snapshot_freshness": freshness,
            },
            "ml_models_live": ml_live,
            "ml_models_planned": ml_planned,
            "memory_promotions_pending": int(getattr(pending_promotions, "count", None) or 0),
            "active_temporal_workflows": None,
            "cache_hit_rate_24h": None,
            "mcp_servers_connected": None,
            "architecture_systems_live": arch_counts.get("live", 0),
            "architecture_systems_planned": arch_counts.get("planned", 0),
            "architecture_systems_partial": arch_counts.get("partial", 0),
        }

    async def get_learning_status(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        since_7d = self._since(7)

        feedback = (
            client.table("message_feedback")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .gte("created_at", since_7d)
            .execute()
        )
        promotions = (
            client.table("agent_memory_promotion_audit")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .gte("created_at", since_7d)
            .eq("status", "approved")
            .execute()
        )
        intel_runs = (
            client.table("org_intelligence_runs")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .gte("started_at", since_7d)
            .execute()
        )
        ranker_examples = (
            client.table("retrieval_ranker_examples")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )
        feedback_n = int(getattr(feedback, "count", None) or 0)
        promotions_n = int(getattr(promotions, "count", None) or 0)
        runs_n = int(getattr(intel_runs, "count", None) or 0)
        examples_n = int(getattr(ranker_examples, "count", None) or 0)
        if runs_n >= 2 and (feedback_n + promotions_n) > 0:
            velocity = "improving"
        elif runs_n == 0 and feedback_n == 0:
            velocity = "stalled"
        else:
            velocity = "stable"

        return {
            "feedback_collected_7d": feedback_n,
            "memories_promoted_7d": promotions_n,
            "source_reliability_updates_7d": None,
            "retrieval_ranker_examples": examples_n,
            "retrieval_ranker_active": examples_n >= 20,
            "intelligence_runs_7d": runs_n,
            "learning_velocity": velocity,
        }

    async def get_predictive_ops_status(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        snapshot = (
            client.table("org_intelligence_snapshots")
            .select("signals_json, updated_at")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        # Migration column is signals_json (not payload_json).
        raw_signals = snapshot[0].get("signals_json") if snapshot else None
        payload = raw_signals if isinstance(raw_signals, dict) else {}
        last_computed = snapshot[0].get("updated_at") if snapshot else None
        freshness = "missing"
        if last_computed:
            try:
                updated_dt = datetime.fromisoformat(str(last_computed).replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - updated_dt
                freshness = "fresh" if age <= timedelta(hours=48) else "stale"
            except (TypeError, ValueError):
                freshness = "stale"

        return {
            "at_risk_workflows": payload.get("workflowAnomalies") or payload.get("anomalies") or [],
            "duration_forecasts": payload.get("workflowForecasts") or payload.get("forecasts") or [],
            "anomalies_detected": payload.get("workflowAnomalies") or payload.get("anomalies") or [],
            "churn_risk_signals": payload.get("churnRiskSignals") or [],
            "last_computed": last_computed,
            "data_freshness": freshness,
            "advisory_only": True,
        }

    async def get_registry_with_runtime(self, org_id: str) -> dict[str, Any]:
        runtime: dict[str, dict[str, Any]] = {}
        for key, meta in AI_ARCHITECTURE_REGISTRY.items():
            runtime[key] = {
                **meta,
                "org_id": org_id,
                "runtime_status": meta.get("status"),
            }
        return {
            "registry": runtime,
            "counts": count_by_status(),
        }


_status_service: AIArchitectureStatusService | None = None


def get_ai_architecture_status_service(
    settings: Settings | None = None,
) -> AIArchitectureStatusService:
    global _status_service
    if _status_service is None or settings is not None:
        _status_service = AIArchitectureStatusService(settings)
    return _status_service
