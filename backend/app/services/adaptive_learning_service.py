"""Adaptive domain learning — org-local segment weight updates from outcomes and retrieval effectiveness."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.learning_confidence_service import get_learning_confidence_service
from app.services.learning_strategy_keys import parse_base_segment_key_from_segment
from app.workflows.repository import get_supabase_client
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

TABLE = "domain_segment_learning_state"
BASE_LEARNING_STEP = 0.02
MULTIPLIER_MIN = 0.7
MULTIPLIER_MAX = 1.3
BOOST_MIN = 0.7
BOOST_MAX = 1.4


class AdaptiveLearningService:
    """Uses real outcome and retrieval effectiveness data to adjust future retrieval weights."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._confidence = get_learning_confidence_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def is_enabled(self) -> bool:
        return bool(getattr(self.settings, "domain_adaptive_learning_enabled", False))

    async def is_enabled_for_org(self, org_id: str) -> bool:
        from app.services.org_learning_profile_service import get_org_learning_profile_service

        return await get_org_learning_profile_service(self.settings).is_adaptive_learning_enabled(org_id)

    @staticmethod
    def _parse_segment_parts(segment_key: str) -> tuple[str | None, str | None, str | None, str | None]:
        base = parse_base_segment_key_from_segment(segment_key)
        parts = str(base).split(":")
        if len(parts) >= 4:
            return parts[0], parts[1], parts[2], parts[3]
        if len(parts) == 2:
            return None, parts[0], None, parts[1]
        return None, None, None, None

    async def load_segment_state(self, org_id: str, segment_key: str) -> dict[str, Any]:
        try:
            rows = (
                self._client()
                .table(TABLE)
                .select("*")
                .eq("org_id", org_id)
                .eq("segment_key", segment_key)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("adaptive_learning_load_skipped org=%s segment=%s error=%s", org_id, segment_key, exc)
        return self._default_state(org_id, segment_key)

    def _default_state(self, org_id: str, segment_key: str) -> dict[str, Any]:
        industry, department, subdomain, task_type = self._parse_segment_parts(segment_key)
        return {
            "org_id": org_id,
            "segment_key": segment_key,
            "industry": industry,
            "department": department,
            "subdomain": subdomain,
            "task_type": task_type,
            "source_weight_deltas": {},
            "assignment_boost_deltas": {},
            "memory_category_boost_deltas": {},
            "connector_priority_deltas": {},
            "adaptive_weight_delta": 1.0,
            "outcome_multiplier": 1.0,
            "meta_learning_delta": 1.0,
            "freshness_aggregate": 1.0,
            "graph_weight_delta": 1.0,
            "confidence_threshold_delta": 0.0,
            "sample_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "noise_score": 0.0,
            "learning_confidence": "insufficient_data",
            "meta_learning_state": {},
            "optimization_snapshot": {},
        }

    async def ingest_response_outcome(
        self,
        org_id: str,
        *,
        segment_key: str,
        classification: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        polarity: str | None = None,
        signal_weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled"}

        resolved_polarity = polarity or self._infer_polarity(response, metadata)
        if resolved_polarity not in {"positive", "negative"}:
            return {"status": "neutral_skipped"}

        state = await self.load_segment_state(org_id, segment_key)
        noise = self._estimate_noise(response, metadata, signal_weight)
        sample_count = int(state.get("sample_count") or 0) + 1
        positive_count = int(state.get("positive_count") or 0) + (1 if resolved_polarity == "positive" else 0)
        negative_count = int(state.get("negative_count") or 0) + (1 if resolved_polarity == "negative" else 0)
        noise_score = round(
            ((float(state.get("noise_score") or 0) * max(sample_count - 1, 0)) + noise) / max(sample_count, 1),
            4,
        )

        assessment = self._confidence.assess(
            sample_count=sample_count,
            positive_count=positive_count,
            negative_count=negative_count,
            noise_score=noise_score,
        )
        if assessment.insufficient_data:
            await self._persist_state(
                org_id,
                segment_key,
                {
                    **state,
                    "sample_count": sample_count,
                    "positive_count": positive_count,
                    "negative_count": negative_count,
                    "noise_score": noise_score,
                    "learning_confidence": assessment.level,
                },
            )
            return {"status": "insufficient_data", "assessment": assessment.to_dict()}

        step = self._confidence.scale_delta(BASE_LEARNING_STEP * float(signal_weight), assessment)
        direction = 1.0 if resolved_polarity == "positive" else -1.0
        adaptive_delta = self._clamp_multiplier(
            float(state.get("adaptive_weight_delta") or 1.0) + (direction * step),
        )
        outcome_multiplier = self._clamp_multiplier(
            float(state.get("outcome_multiplier") or 1.0) + (direction * step),
        )

        assignment_deltas = safe_normalize_stored_dict(state, key="assignment_boost_deltas")
        source_deltas = safe_normalize_stored_dict(state, key="source_weight_deltas")
        retrieval_effectiveness = (response or {}).get("retrieval_effectiveness") or (metadata or {}).get(
            "retrieval_effectiveness"
        )
        if isinstance(retrieval_effectiveness, dict):
            freshness_factor = self._freshness_learning_factor(retrieval_effectiveness)
            effective_step = step * freshness_factor
            for assignment_id in retrieval_effectiveness.get("assignment_ids_used") or []:
                aid = str(assignment_id)
                current = float(assignment_deltas.get(aid) or 1.0)
                assignment_deltas[aid] = round(
                    self._clamp_boost(current + (direction * effective_step)),
                    4,
                )
            for source in retrieval_effectiveness.get("top_sources") or []:
                if not isinstance(source, dict):
                    continue
                source_key = str(source.get("source_type") or source.get("source_name") or "").lower()
                if not source_key:
                    continue
                current = float(source_deltas.get(source_key) or 1.0)
                source_deltas[source_key] = round(
                    self._clamp_boost(current + (direction * effective_step)),
                    4,
                )

        await self._persist_state(
            org_id,
            segment_key,
            {
                **state,
                "sample_count": sample_count,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "noise_score": noise_score,
                "learning_confidence": assessment.level,
                "adaptive_weight_delta": adaptive_delta,
                "outcome_multiplier": outcome_multiplier,
                "assignment_boost_deltas": assignment_deltas,
                "source_weight_deltas": source_deltas,
            },
        )
        return {
            "status": "updated",
            "learning_confidence": assessment.level,
            "adaptive_weight_delta": adaptive_delta,
            "outcome_multiplier": outcome_multiplier,
        }

    async def apply_to_retrieval_plan(
        self,
        plan: Any,
        org_id: str,
        segment_key: str,
        assignments: list[dict[str, Any]] | None = None,
        *,
        client: Any | None = None,
    ) -> Any:
        from app.services.domain_retrieval_policy import RetrievalPlan
        from app.services.knowledge_freshness_service import get_knowledge_freshness_service

        if not isinstance(plan, RetrievalPlan):
            return plan

        if not self.is_enabled():
            return plan

        freshness_service = get_knowledge_freshness_service(self.settings)
        if assignments:
            assessments = freshness_service.assess_assignments(assignments, client=client, org_id=org_id)
            for aid, assessment in assessments.items():
                plan.assignment_freshness_multipliers[aid] = assessment.freshness_multiplier
                if assessment.trust_warning:
                    plan.assignment_stale_warnings[aid] = assessment.trust_warning
            plan.freshness_label = freshness_service.aggregate_freshness_label(assessments)
            plan.freshness_trust_warnings = freshness_service.collect_trust_warnings(assessments)

        state = await self.load_segment_state(org_id, segment_key)
        assessment = self._confidence.assess(
            sample_count=int(state.get("sample_count") or 0),
            positive_count=int(state.get("positive_count") or 0),
            negative_count=int(state.get("negative_count") or 0),
            noise_score=float(state.get("noise_score") or 0),
        )
        plan.learning_confidence = assessment.level
        plan.insufficient_data = assessment.insufficient_data
        if assessment.insufficient_data:
            return plan

        plan.adaptive_weight_delta = float(state.get("adaptive_weight_delta") or 1.0)
        plan.outcome_multiplier = float(state.get("outcome_multiplier") or 1.0)
        plan.meta_learning_delta = float(state.get("meta_learning_delta") or 1.0)

        assignment_deltas = state.get("assignment_boost_deltas") or {}
        for aid, delta in assignment_deltas.items():
            current = float(plan.assignment_boosts.get(aid) or 1.0)
            plan.assignment_boosts[aid] = round(min(BOOST_MAX, max(BOOST_MIN, current * float(delta))), 4)

        source_deltas = state.get("source_weight_deltas") or {}
        for source_type, delta in source_deltas.items():
            key = str(source_type).lower()
            if key in plan.source_type_weights:
                current = float(plan.source_type_weights[key])
                plan.source_type_weights[key] = round(min(BOOST_MAX, max(BOOST_MIN, current * float(delta))), 4)

        return plan

    async def get_admin_summary(self, org_id: str) -> dict[str, Any]:
        try:
            rows = (
                self._client()
                .table(TABLE)
                .select("*")
                .eq("org_id", org_id)
                .order("last_updated_at", desc=True)
                .limit(100)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []

        segments = []
        insufficient = []
        for row in rows:
            assessment = self._confidence.assess(
                sample_count=int(row.get("sample_count") or 0),
                positive_count=int(row.get("positive_count") or 0),
                negative_count=int(row.get("negative_count") or 0),
                noise_score=float(row.get("noise_score") or 0),
            )
            entry = {
                "segment_key": row.get("segment_key"),
                "sample_count": row.get("sample_count"),
                "learning_confidence": assessment.level,
                "adaptive_weight_delta": row.get("adaptive_weight_delta"),
                "outcome_multiplier": row.get("outcome_multiplier"),
                "positive_count": row.get("positive_count"),
                "negative_count": row.get("negative_count"),
            }
            segments.append(entry)
            if assessment.insufficient_data:
                insufficient.append(row.get("segment_key"))

        return {
            "status": "ok" if self.is_enabled() else "disabled",
            "org_id": org_id,
            "segment_summaries": segments,
            "insufficient_data_warnings": insufficient,
            "last_updated_at": rows[0].get("last_updated_at") if rows else None,
        }

    async def _persist_state(self, org_id: str, segment_key: str, state: dict[str, Any]) -> None:
        industry, department, subdomain, task_type = self._parse_segment_parts(segment_key)
        row = {
            "id": state.get("id") or str(uuid4()),
            "org_id": org_id,
            "segment_key": segment_key,
            "industry": industry,
            "department": department,
            "subdomain": subdomain,
            "task_type": task_type,
            "source_weight_deltas": state.get("source_weight_deltas") or {},
            "assignment_boost_deltas": state.get("assignment_boost_deltas") or {},
            "memory_category_boost_deltas": state.get("memory_category_boost_deltas") or {},
            "connector_priority_deltas": state.get("connector_priority_deltas") or {},
            "adaptive_weight_delta": float(state.get("adaptive_weight_delta") or 1.0),
            "outcome_multiplier": float(state.get("outcome_multiplier") or 1.0),
            "meta_learning_delta": float(state.get("meta_learning_delta") or 1.0),
            "freshness_aggregate": float(state.get("freshness_aggregate") or 1.0),
            "graph_weight_delta": float(state.get("graph_weight_delta") or 1.0),
            "confidence_threshold_delta": float(state.get("confidence_threshold_delta") or 0.0),
            "sample_count": int(state.get("sample_count") or 0),
            "positive_count": int(state.get("positive_count") or 0),
            "negative_count": int(state.get("negative_count") or 0),
            "noise_score": float(state.get("noise_score") or 0),
            "learning_confidence": str(state.get("learning_confidence") or "insufficient_data"),
            "meta_learning_state": state.get("meta_learning_state") or {},
            "optimization_snapshot": state.get("optimization_snapshot") or {},
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._client().table(TABLE).upsert(row, on_conflict="org_id,segment_key").execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("adaptive_learning_persist_skipped org=%s segment=%s error=%s", org_id, segment_key, exc)

    @staticmethod
    def _infer_polarity(
        response: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> str:
        meta = metadata or {}
        if meta.get("polarity") in {"positive", "negative"}:
            return str(meta["polarity"])
        helpful = meta.get("helpful")
        if helpful is True:
            return "positive"
        if helpful is False:
            return "negative"
        retrieval = (response or {}).get("retrieval_effectiveness") or meta.get("retrieval_effectiveness") or {}
        if isinstance(retrieval, dict):
            score = float(retrieval.get("retrieval_score") or 0)
            if score >= 0.75:
                return "positive"
            if score <= 0.35:
                return "negative"
        return "neutral"

    @staticmethod
    def _estimate_noise(
        response: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        signal_weight: float,
    ) -> float:
        noise = 0.0
        if float(signal_weight) < 0.6:
            noise += 0.35
        meta = metadata or {}
        if meta.get("confidence_mismatch"):
            noise += 0.2
        retrieval = (response or {}).get("retrieval_effectiveness") or meta.get("retrieval_effectiveness") or {}
        if isinstance(retrieval, dict):
            stale_sources = retrieval.get("stale_sources") or []
            if stale_sources:
                noise += min(0.4, 0.1 * len(stale_sources))
        return min(1.0, noise)

    @staticmethod
    def _freshness_learning_factor(retrieval_effectiveness: dict[str, Any]) -> float:
        stale_sources = retrieval_effectiveness.get("stale_sources") or []
        if not stale_sources:
            return 1.0
        return max(0.25, 1.0 - (0.15 * len(stale_sources)))

    @staticmethod
    def _clamp_multiplier(value: float) -> float:
        return round(max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, float(value))), 4)

    @staticmethod
    def _clamp_boost(value: float) -> float:
        return max(BOOST_MIN, min(BOOST_MAX, float(value)))


_service: AdaptiveLearningService | None = None


def get_adaptive_learning_service(settings: Settings | None = None) -> AdaptiveLearningService:
    global _service
    if _service is None or settings is not None:
        _service = AdaptiveLearningService(settings)
    return _service
