"""G1 — IntelligenceProjectionService: canonical intelligence state composition."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.intelligence_projection import (
    IntelligenceGraph,
    IntelligenceMetrics,
    IntelligencePageContext,
    IntelligenceProvenance,
    IntelligenceQualityFlag,
    IntelligenceSnapshot,
    LearningInsight,
)
from app.services.business_signals_engine import get_business_signals_engine
from app.services.intelligence_agent_roster import load_canonical_agents
from app.services.intelligence_graph_builder import build_intelligence_graph, filter_graph_for_lens
from app.services.intelligence_outcome_path import build_outcome_paths
from app.services.intelligence_prediction_dedup import normalize_signals_to_predictions
from app.services.intelligence_semantics import model_business_label
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.memory_promotion_service import MemoryPromotionStatus, get_memory_promotion_service
from app.services.outcome_learning_service import POSITIVE_EVENTS, get_outcome_learning_service
from app.services.swarm_coordinator_service import SWARM_AGGREGATING, SWARM_RUNNING, list_swarm_runs
from app.services.training_signal_service import get_training_signal_service
from app.workflows.constants import RUN_STATUS_PENDING_APPROVAL, RUN_TYPE_EXECUTE
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 45


def learning_rows_from_promotion_payload(promo: dict[str, Any] | None) -> list[dict[str, Any]]:
    """list_candidates returns `items`; older mocks used `candidates`."""
    if not isinstance(promo, dict):
        return []
    rows = promo.get("items")
    if not isinstance(rows, list):
        rows = promo.get("candidates")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


class _CacheEntry:
    def __init__(self, snapshot: IntelligenceSnapshot, graph: IntelligenceGraph, expires_at: float) -> None:
        self.snapshot = snapshot
        self.graph = graph
        self.expires_at = expires_at


class IntelligenceProjectionService:
    """Compose canonical intelligence from authoritative sources — no duplicate DB."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: dict[str, _CacheEntry] = {}

    def invalidate(self, org_id: str) -> None:
        prefix = f"{org_id}:"
        for key in list(self._cache):
            if key.startswith(prefix):
                del self._cache[key]

    async def build_snapshot(
        self,
        org_id: str,
        *,
        environment_name: str = "production",
        window_hours: int = 24,
        use_cache: bool = True,
    ) -> IntelligenceSnapshot:
        cache_key = f"{org_id}:{environment_name}:{window_hours}"
        if use_cache:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return entry.snapshot

        window_hours = min(max(window_hours, 1), 168)
        client = get_supabase_client(self.settings)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        quality_flags: list[IntelligenceQualityFlag] = []

        agents, _running_ids = load_canonical_agents(
            client, org_id, environment_name=environment_name
        )

        # Departments + core visual state (reuse outcome events aggregation).
        outcome_service = get_outcome_learning_service(self.settings)
        recent_events = await outcome_service.fetch_recent_events(org_id, since_hours=window_hours)
        _CORE_INFLOW = frozenset({"recommendation_created", "prediction_generated"})
        by_department: dict[str, dict[str, Any]] = {}
        for row in recent_events:
            dept_id = str(row.get("department") or "").strip().lower()
            if not dept_id:
                continue
            bucket = by_department.setdefault(
                dept_id,
                {"total": 0, "inflow": 0, "resolved": 0, "confidence_sum": 0.0, "confidence_count": 0},
            )
            bucket["total"] += 1
            event_name = row.get("outcome_event")
            if event_name in _CORE_INFLOW:
                bucket["inflow"] += 1
            if event_name in POSITIVE_EVENTS:
                bucket["resolved"] += 1
            confidence = row.get("confidence_score")
            if confidence is not None:
                try:
                    bucket["confidence_sum"] += float(confidence)
                    bucket["confidence_count"] += 1
                except (TypeError, ValueError):
                    pass

        departments: list[dict[str, Any]] = []
        for dept_id, bucket in sorted(by_department.items()):
            confidence_avg = (
                round(bucket["confidence_sum"] / bucket["confidence_count"], 3)
                if bucket["confidence_count"]
                else None
            )
            if bucket["inflow"] > 0:
                visual_state = "flow-inward"
            elif bucket["resolved"] > 0:
                visual_state = "resolved"
            elif confidence_avg is not None and confidence_avg < 0.5:
                visual_state = "low-confidence"
            else:
                visual_state = "idle"
            departments.append(
                {
                    "id": dept_id,
                    "eventsInWindow": bucket["total"],
                    "recentInflow": bucket["inflow"],
                    "recentResolved": bucket["resolved"],
                    "confidence": confidence_avg,
                    "state": visual_state,
                }
            )

        pending_workflow_approvals = 0
        running_workflows = 0
        actions_completed = 0
        try:
            pending_resp = (
                client.table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("run_type", RUN_TYPE_EXECUTE)
                .eq("status", RUN_STATUS_PENDING_APPROVAL)
                .eq("approval_status", RUN_STATUS_PENDING_APPROVAL)
                .execute()
            )
            pending_workflow_approvals = int(pending_resp.count or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_workflow_approvals_skipped org_id=%s error=%s", org_id, exc)

        try:
            running_resp = (
                client.table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .eq("status", "running")
                .execute()
            )
            running_workflows = int(running_resp.count or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_running_workflows_skipped org_id=%s error=%s", org_id, exc)

        actions_completed = sum(
            1 for row in recent_events if str(row.get("outcome_event") or "") in {"action_completed", "workflow_completed"}
        )

        pending_memory_approvals = 0
        try:
            memory_result = get_memory_promotion_service(self.settings).list_candidates(
                org_id, status=MemoryPromotionStatus.PENDING_APPROVAL.value, limit=1
            )
            pending_memory_approvals = int(memory_result.get("total") or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_memory_candidates_skipped org_id=%s error=%s", org_id, exc)

        currently_running_agents = sum(1 for a in agents if a.isCurrentlyRunning)
        configured_active_agents = sum(1 for a in agents if a.isConfiguredActive)
        swarm_runs_active = 0
        try:
            swarm_runs = list_swarm_runs(client, org_id, limit=50)
            swarm_runs_active = sum(
                1 for run in swarm_runs if run.get("status") in {SWARM_RUNNING, SWARM_AGGREGATING}
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_swarm_runs_skipped org_id=%s error=%s", org_id, exc)

        pending_approvals_total = pending_workflow_approvals + pending_memory_approvals
        if currently_running_agents > 0 or swarm_runs_active > 0:
            core_state = "trace"
        elif pending_approvals_total > 0:
            core_state = "pending-approval"
        elif any(d.get("state") == "flow-inward" for d in departments):
            core_state = "flow-inward"
        elif recent_events:
            core_state = "resolved" if any(d.get("state") == "resolved" for d in departments) else "idle"
        else:
            core_state = "idle"

        if configured_active_agents > 0 and swarm_runs_active == 0 and currently_running_agents == 0:
            # Not a contradiction — configured active ≠ currently running; no flag needed.
            pass

        # Knowledge graph summary + I1 field sample (same org scope)
        entity_count = 0
        relationship_count = 0
        knowledge_entity_types: list[str] = []
        field_sample: list[dict[str, Any]] = []
        try:
            kg_service = get_knowledge_graph_service()
            kg = await kg_service.get_admin_summary(org_id, settings=self.settings)
            entity_count = int(kg.get("entity_count") or 0)
            relationship_count = int(kg.get("relationship_count") or 0)
            knowledge_entity_types = [
                str(et).strip()
                for et in (kg.get("entity_types") or [])
                if str(et).strip()
            ][:12]
            if entity_count > 0:
                try:
                    field_sample = await kg_service.get_field_sample(
                        org_id, limit=80, settings=self.settings
                    )
                except Exception as field_exc:  # noqa: BLE001
                    logger.warning(
                        "projection_kg_field_sample_failed org_id=%s error=%s",
                        org_id,
                        field_exc,
                    )
                    field_sample = []
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_knowledge_graph_skipped org_id=%s error=%s", org_id, exc)
            quality_flags.append("MISSING_RELATIONSHIP")

        # Business signals → deduped predictions
        signals_payload: dict[str, Any] = {}
        try:
            signals_payload = await get_business_signals_engine(self.settings).collect_signals(
                org_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_business_signals_skipped org_id=%s error=%s", org_id, exc)

        raw_signals = list(signals_payload.get("signals") or [])
        predictions = normalize_signals_to_predictions(raw_signals, fetched_at=now_iso)
        unscoped = [p for p in predictions if "UNSCOPED_PREDICTION" in p.qualityFlags]
        if unscoped:
            quality_flags.append("UNSCOPED_PREDICTION")

        # Models (business labels)
        models: list[dict[str, Any]] = []
        models_improved = 0
        try:
            readiness = await get_training_signal_service(self.settings).get_training_readiness(org_id)
            by_model = readiness.get("by_model") or {}
            for slug, row in by_model.items():
                if not isinstance(row, dict):
                    continue
                status = str(row.get("status") or "unknown")
                models.append(
                    {
                        "id": slug,
                        "businessLabel": model_business_label(slug),
                        "status": status,
                        "technicalLabel": slug,
                    }
                )
                if status in {"ready", "recently_trained"}:
                    models_improved += 0  # readiness ≠ improvement; count only explicit outcomes below
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_training_readiness_skipped org_id=%s error=%s", org_id, exc)

        # Business learnings — memory promotion / optimization only when present
        learnings: list[LearningInsight] = []
        try:
            promo = get_memory_promotion_service(self.settings).list_candidates(
                org_id, status=MemoryPromotionStatus.AUTO_PROMOTED.value, limit=5
            )
            for row in learning_rows_from_promotion_payload(promo):
                content = str(row.get("content") or "").strip()
                if not content:
                    continue
                learnings.append(
                    LearningInsight(
                        id=str(row.get("id") or content[:32]),
                        businessStatement=content[:500],
                        learnedFrom=[str(row.get("source_table") or "memory_promotion")],
                        evidence=[str(row.get("memory_category") or "")] if row.get("memory_category") else [],
                        confidence=str(row.get("status") or ""),
                        learnedAt=row.get("updated_at"),
                        source=IntelligenceProvenance(
                            system="memory_promotion",
                            recordId=str(row.get("id") or ""),
                            fetchedAt=now_iso,
                        ),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("projection_learnings_skipped org_id=%s error=%s", org_id, exc)

        if not learnings:
            quality_flags.append("NO_BUSINESS_LEARNING_YET")
        if not recent_events:
            quality_flags.append("NO_OUTCOME_ATTRIBUTION")

        measured_outcomes = sum(d.get("recentResolved", 0) for d in departments)
        recommendations = sum(
            1 for row in recent_events if str(row.get("outcome_event") or "") == "recommendation_created"
        )

        metrics = IntelligenceMetrics(
            knowledge={
                "knownEntities": entity_count,
                "knownRelationships": relationship_count,
                "knowledgeSources": len({s.get("source") for s in raw_signals if s.get("source")}),
            },
            learning={
                "recentLearnings": len(learnings),
                "relationshipsLearned": relationship_count,
                "modelsImproved": models_improved,
                "modelsTracked": len(models),
            },
            predictions={
                "activePredictions": len(predictions),
                "highPriorityPredictions": sum(
                    1 for p in predictions if (p.confidence or 0) >= 0.65
                ),
                "predictionsNeedingEvidence": sum(
                    1 for p in predictions if "UNSCOPED_PREDICTION" in p.qualityFlags or not p.evidence
                ),
            },
            execution={
                "configuredActiveAgents": configured_active_agents,
                "currentlyRunningAgents": currently_running_agents,
                "runningWorkflows": running_workflows,
                "concurrentSwarmRuns": swarm_runs_active,
                "actionsCompleted": actions_completed,
                "recommendationsCreated": recommendations,
                "awaitingApproval": pending_approvals_total,
            },
            outcomes={
                "measuredOutcomes": measured_outcomes,
                "outcomeEventsInWindow": len(recent_events),
                "departmentsWithActivity": len(departments),
            },
        )

        snapshot = IntelligenceSnapshot(
            generatedAt=now_iso,
            tenantId=org_id,
            timeWindowHours=window_hours,
            coreState=core_state,
            agents=agents,
            predictions=predictions,
            learnings=learnings,
            metrics=metrics,
            qualityFlags=list(dict.fromkeys(quality_flags)),
            departments=departments,
            models=models,
            signals=raw_signals,
            workflows=[],
            outcomes=[
                {
                    "id": r.get("id"),
                    "event": r.get("outcome_event"),
                    "department": r.get("department"),
                    "agentId": r.get("agent_id"),
                    "entityType": r.get("entity_type"),
                    "entityId": r.get("entity_id"),
                    "confidence": r.get("confidence_score"),
                    "createdAt": r.get("created_at"),
                }
                for r in recent_events[:40]
            ],
            knowledgeEntityTypes=knowledge_entity_types,
        )

        graph = build_intelligence_graph(snapshot, field_sample=field_sample)
        self._cache[cache_key] = _CacheEntry(snapshot, graph, time.time() + _CACHE_TTL_SECONDS)
        return snapshot

    async def build_page_context(
        self,
        org_id: str,
        *,
        environment_name: str = "production",
        window_hours: int = 24,
        active_lens: str = "knows",
    ) -> IntelligencePageContext:
        snapshot = await self.build_snapshot(
            org_id, environment_name=environment_name, window_hours=window_hours
        )
        cache_key = f"{org_id}:{environment_name}:{window_hours}"
        entry = self._cache.get(cache_key)
        graph = entry.graph if entry else build_intelligence_graph(snapshot)
        lens = active_lens if active_lens in {"knows", "learns", "predicts", "acts", "improves"} else "knows"
        graph = filter_graph_for_lens(graph, lens)  # G3 — lens is a projection of one graph

        exec_metrics = snapshot.metrics.execution
        configured = int(exec_metrics.get("configuredActiveAgents") or 0)
        suggested = [
            "What agents are currently active?",
            "What predictions need attention?",
            "What has Gravitre learned recently?",
        ]
        if lens == "improves":
            suggested = [
                "Is Gravitre making the business better?",
                "Which outcomes can we attribute?",
                "What has Gravitre learned recently?",
            ]
        if configured == 0:
            suggested[0] = "What should I connect first?" if lens != "improves" else suggested[0]

        outcome_paths = build_outcome_paths(snapshot)

        return IntelligencePageContext(
            snapshot=snapshot,
            graph=graph,
            activeLens=lens,  # type: ignore[arg-type]
            metrics=snapshot.metrics,
            qualityFlags=snapshot.qualityFlags,
            suggestedQuestions=suggested,
            outcomePaths=outcome_paths,
        )


_service: IntelligenceProjectionService | None = None


def get_intelligence_projection_service(settings: Settings | None = None) -> IntelligenceProjectionService:
    global _service
    if _service is None or settings is not None:
        _service = IntelligenceProjectionService(settings)
    return _service
