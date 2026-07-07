"""Domain optimization engine — advisory-only recommendations per domain segment (Wave D5)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.learning_confidence_service import get_learning_confidence_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

TABLE = "domain_optimization_recommendations"
ALLOWED_STATUSES = frozenset({"pending_review", "applied", "dismissed"})

RECOMMENDATION_TYPES = frozenset(
    {
        "refresh_stale_knowledge_source",
        "add_missing_source",
        "promote_memory",
        "retire_memory",
        "adjust_assignment_confidence_weight",
        "retrain_model",
        "improve_workflow_template",
        "add_connector",
        "change_default_agent",
        "weak_segment_performance",
        "insufficient_learning_data",
    }
)


class DomainOptimizationEngine:
    """
    Continuously evaluates domain intelligence quality and emits advisory recommendations.
    Never auto-applies changes — humans remain in control.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._confidence = get_learning_confidence_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def is_enabled(self) -> bool:
        return bool(getattr(self.settings, "domain_adaptive_learning_enabled", False))

    async def evaluate_recommendations_for_org(self, org_id: str) -> list[dict[str, Any]]:
        if not self.is_enabled():
            return []
        created: list[dict[str, Any]] = []
        created.extend(await self._recommendations_from_freshness(org_id))
        created.extend(await self._recommendations_from_knowledge_gaps(org_id))
        created.extend(await self._recommendations_from_learning_segments(org_id))
        created.extend(await self._recommendations_from_training_signals(org_id))
        created.extend(await self._recommendations_from_outcomes(org_id))
        created.extend(await self._recommendations_from_meta_learning(org_id))
        return created

    async def get_admin_summary(self, org_id: str, *, refresh: bool = False) -> dict[str, Any]:
        if refresh and self.is_enabled():
            await self.evaluate_recommendations_for_org(org_id)

        try:
            rows = (
                self._client()
                .table(TABLE)
                .select("*")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []

        pending = [row for row in rows if row.get("status") == "pending_review"]
        by_type: dict[str, int] = {}
        insufficient_warnings: list[str] = []
        for row in pending:
            rec_type = str(row.get("recommendation_type") or "unknown")
            by_type[rec_type] = by_type.get(rec_type, 0) + 1
            if rec_type == "insufficient_learning_data":
                insufficient_warnings.append(str(row.get("segment_key") or "unknown"))

        return {
            "status": "ok" if self.is_enabled() else "disabled",
            "org_id": org_id,
            "advisory_only": True,
            "auto_execution_enabled": False,
            "pending_count": len(pending),
            "total_count": len(rows),
            "recommendations_by_type": by_type,
            "pending_recommendations": pending[:25],
            "insufficient_data_warnings": insufficient_warnings,
            "last_updated_at": rows[0].get("created_at") if rows else None,
        }

    async def _recommendations_from_freshness(self, org_id: str) -> list[dict[str, Any]]:
        from app.services.knowledge_freshness_service import get_knowledge_freshness_service

        summary = await get_knowledge_freshness_service(self.settings).load_admin_summary(org_id)
        created: list[dict[str, Any]] = []
        for source in summary.get("stale_sources") or []:
            segment_key = self._segment_from_assignment(source)
            row = await self._insert_recommendation(
                org_id,
                segment_key=segment_key,
                recommendation_type="refresh_stale_knowledge_source",
                title=f"Refresh stale knowledge source: {source.get('label') or 'source'}",
                description="Knowledge source sync is stale — refresh or revalidate before relying on it in retrieval.",
                evidence={
                    "assignment_id": source.get("assignment_id"),
                    "freshness_score": source.get("freshness_score"),
                    "stale_reason": source.get("stale_reason"),
                    "agent_id": source.get("agent_id"),
                    "department": source.get("department"),
                    "subdomain": source.get("subdomain"),
                },
            )
            if row:
                created.append(row)
        for source in summary.get("inaccessible_sources") or []:
            segment_key = self._segment_from_assignment(source)
            row = await self._insert_recommendation(
                org_id,
                segment_key=segment_key,
                recommendation_type="refresh_stale_knowledge_source",
                title=f"Revalidate inaccessible source: {source.get('label') or 'source'}",
                description="Source is inaccessible or permission denied — revalidate connector permissions.",
                evidence={
                    "assignment_id": source.get("assignment_id"),
                    "stale_reason": source.get("stale_reason"),
                    "agent_id": source.get("agent_id"),
                },
            )
            if row:
                created.append(row)
        return created

    async def _recommendations_from_knowledge_gaps(self, org_id: str) -> list[dict[str, Any]]:
        try:
            gaps = (
                self._client()
                .table("org_knowledge_gaps")
                .select("*")
                .eq("org_id", org_id)
                .eq("status", "open")
                .limit(20)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            gaps = []
        created: list[dict[str, Any]] = []
        for gap in gaps:
            dept = str(gap.get("department") or "default").lower()
            segment_key = f"default:{dept}:general:general"
            row = await self._insert_recommendation(
                org_id,
                segment_key=segment_key,
                recommendation_type="add_missing_source",
                title=f"Add missing knowledge source for {dept}",
                description=str(gap.get("description") or "Open knowledge gap detected from failed searches."),
                evidence={"gap_id": gap.get("id"), "query_pattern": gap.get("query_pattern")},
            )
            if row:
                created.append(row)
        return created

    async def _recommendations_from_learning_segments(self, org_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                self._client()
                .table("domain_segment_learning_state")
                .select("*")
                .eq("org_id", org_id)
                .limit(100)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []
        created: list[dict[str, Any]] = []
        for state in rows:
            segment_key = str(state.get("segment_key") or "default")
            assessment = self._confidence.assess(
                sample_count=int(state.get("sample_count") or 0),
                positive_count=int(state.get("positive_count") or 0),
                negative_count=int(state.get("negative_count") or 0),
                noise_score=float(state.get("noise_score") or 0),
            )
            if assessment.insufficient_data:
                row = await self._insert_recommendation(
                    org_id,
                    segment_key=segment_key,
                    recommendation_type="insufficient_learning_data",
                    title=f"Collect more outcomes for segment {segment_key}",
                    description="Adaptive learning has insufficient segment evidence — continue monitoring before adjusting weights.",
                    evidence={
                        "sample_count": state.get("sample_count"),
                        "min_samples_required": assessment.min_samples_required,
                    },
                )
                if row:
                    created.append(row)
                continue

            negative = int(state.get("negative_count") or 0)
            positive = int(state.get("positive_count") or 0)
            if negative > positive and int(state.get("sample_count") or 0) >= assessment.min_samples_required:
                row = await self._insert_recommendation(
                    org_id,
                    segment_key=segment_key,
                    recommendation_type="weak_segment_performance",
                    title=f"Review weak segment performance: {segment_key}",
                    description="Negative outcomes exceed positive outcomes for this segment — review assignments and retrieval weights.",
                    evidence={
                        "positive_count": positive,
                        "negative_count": negative,
                        "adaptive_weight_delta": state.get("adaptive_weight_delta"),
                        "outcome_multiplier": state.get("outcome_multiplier"),
                    },
                )
                if row:
                    created.append(row)

            boost_deltas = state.get("assignment_boost_deltas") or {}
            for assignment_id, delta in boost_deltas.items():
                if float(delta or 1.0) < 0.85:
                    row = await self._insert_recommendation(
                        org_id,
                        segment_key=segment_key,
                        recommendation_type="adjust_assignment_confidence_weight",
                        title=f"Review assignment confidence for {assignment_id}",
                        description="Adaptive learning reduced assignment boost — consider updating confidence weight or refreshing source.",
                        evidence={"assignment_id": assignment_id, "boost_delta": delta},
                    )
                    if row:
                        created.append(row)
        return created

    async def _recommendations_from_training_signals(self, org_id: str) -> list[dict[str, Any]]:
        from app.services.training_signal_service import get_training_signal_service

        signals = await get_training_signal_service(self.settings).get_domain_optimization_signals(org_id)
        created: list[dict[str, Any]] = []
        for candidate in signals.get("retrain_candidates") or []:
            model_name = str(candidate.get("model_name") or "unknown")
            row = await self._insert_recommendation(
                org_id,
                segment_key=f"default:operations:general:model_training",
                recommendation_type="retrain_model",
                title=f"Consider retraining model: {model_name}",
                description="Training thresholds met — human approval required before retraining.",
                evidence={"model_name": model_name, "reason": candidate.get("reason"), "requires_approval": True},
            )
            if row:
                created.append(row)
        return created

    async def _recommendations_from_outcomes(self, org_id: str) -> list[dict[str, Any]]:
        from app.services.outcome_learning_service import get_outcome_learning_service

        metrics = await get_outcome_learning_service(self.settings).get_domain_optimization_metrics(org_id)
        created: list[dict[str, Any]] = []
        if float(metrics.get("insufficient_data_rate") or 0) >= 0.5:
            row = await self._insert_recommendation(
                org_id,
                segment_key="default:operations:general:outcomes",
                recommendation_type="insufficient_learning_data",
                title="High insufficient-data rate in outcome tracking",
                description="Many outcomes lack measurable before/after values — improve outcome instrumentation.",
                evidence=metrics,
            )
            if row:
                created.append(row)
        return created

    async def _recommendations_from_meta_learning(self, org_id: str) -> list[dict[str, Any]]:
        from app.services.meta_learning_service import get_meta_learning_service

        summary = await get_meta_learning_service(self.settings).get_meta_learning_summary(org_id)
        created: list[dict[str, Any]] = []
        for agent in summary.get("best_agents") or []:
            segment_key = str(agent.get("segment_key") or "default")
            if int(agent.get("sample_count") or 0) < self._confidence.min_samples():
                continue
            row = await self._insert_recommendation(
                org_id,
                segment_key=segment_key,
                recommendation_type="change_default_agent",
                title=f"Meta-learning suggests agent {agent.get('strategy_key')} for {segment_key}",
                description="Advisory only — review agent routing defaults; do not auto-change persona selection.",
                evidence={
                    "strategy_key": agent.get("strategy_key"),
                    "win_rate": agent.get("win_rate"),
                    "sample_count": agent.get("sample_count"),
                    "requires_approval": True,
                },
            )
            if row:
                created.append(row)

        profile_rows = await self._load_domain_profiles_with_connectors(org_id)
        for profile in profile_rows:
            prefs = profile.get("connector_preferences") or []
            if not prefs:
                segment_key = f"default:{profile.get('department') or 'operations'}:general:connectors"
                row = await self._insert_recommendation(
                    org_id,
                    segment_key=segment_key,
                    recommendation_type="add_connector",
                    title=f"Add connector for {profile.get('label') or profile.get('profile_id')}",
                    description="Domain profile lists connector preferences but org may be missing integrations.",
                    evidence={"profile_id": profile.get("profile_id"), "connector_preferences": prefs},
                )
                if row:
                    created.append(row)
        return created

    async def _insert_recommendation(
        self,
        org_id: str,
        *,
        segment_key: str,
        recommendation_type: str,
        title: str,
        description: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if recommendation_type not in RECOMMENDATION_TYPES:
            return None
        if await self._duplicate_pending(org_id, segment_key, recommendation_type, title):
            return None
        row = {
            "id": str(uuid4()),
            "org_id": org_id,
            "segment_key": segment_key,
            "recommendation_type": recommendation_type,
            "title": title,
            "description": description,
            "evidence": evidence or {},
            "status": "pending_review",
            "advisory_only": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            inserted = self._client().table(TABLE).insert(row).execute()
            saved = inserted.data[0] if inserted.data else row
            await self._record_advisory_outcome(org_id, saved)
            return saved
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "domain_optimization_insert_skipped org=%s type=%s error=%s",
                org_id,
                recommendation_type,
                exc,
            )
            return None

    async def _duplicate_pending(
        self,
        org_id: str,
        segment_key: str,
        recommendation_type: str,
        title: str,
    ) -> bool:
        try:
            rows = (
                self._client()
                .table(TABLE)
                .select("id, title")
                .eq("org_id", org_id)
                .eq("segment_key", segment_key)
                .eq("recommendation_type", recommendation_type)
                .eq("status", "pending_review")
                .limit(20)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            return False
        title_hash = hashlib.sha256(title.encode()).hexdigest()[:12]
        for row in rows:
            existing_hash = hashlib.sha256(str(row.get("title") or "").encode()).hexdigest()[:12]
            if existing_hash == title_hash:
                return True
        return False

    async def _record_advisory_outcome(self, org_id: str, recommendation: dict[str, Any]) -> None:
        try:
            from app.services.outcome_learning_service import get_outcome_learning_service

            await get_outcome_learning_service(self.settings).record_recommendation_outcome(
                org_id=org_id,
                recommendation_id=str(recommendation.get("id") or ""),
                outcome_event="recommendation_created",
                task_type=str(recommendation.get("recommendation_type") or "domain_optimization"),
                department=str(recommendation.get("segment_key") or "").split(":")[1]
                if ":" in str(recommendation.get("segment_key") or "")
                else None,
                metadata={
                    "advisory_only": True,
                    "domain_optimization": True,
                    "segment_key": recommendation.get("segment_key"),
                    "evidence": recommendation.get("evidence"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("domain_optimization_outcome_skipped error=%s", exc)

    async def _load_domain_profiles_with_connectors(self, org_id: str) -> list[dict[str, Any]]:
        _ = org_id
        try:
            from app.domain.loader import list_profile_ids, load_domain_profile

            profiles: list[dict[str, Any]] = []
            for profile_id in list_profile_ids():
                profile = load_domain_profile(profile_id)
                if not profile or not profile.get("connector_preferences"):
                    continue
                profiles.append(
                    {
                        "profile_id": profile.get("profile_id") or profile_id,
                        "label": profile.get("label"),
                        "department": profile.get("department") or profile_id,
                        "connector_preferences": profile.get("connector_preferences") or [],
                    }
                )
            return profiles
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _segment_from_assignment(source: dict[str, Any]) -> str:
        dept = str(source.get("department") or "default").lower()
        sub = str(source.get("subdomain") or "general").lower()
        return f"default:{dept}:{sub}:knowledge_freshness"


_engine: DomainOptimizationEngine | None = None


def get_domain_optimization_engine(settings: Settings | None = None) -> DomainOptimizationEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = DomainOptimizationEngine(settings)
    return _engine
