"""Orchestrates prioritized ML/AI platform upgrades across existing Gravitre services."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

MIN_OUTCOMES_FOR_ORG_LEARNING = 50
MIN_CAUSAL_SERIES_POINTS = 60
MIN_RETRIEVAL_RANKER_EXAMPLES = 20


class MLUpgradeService:
    """Runs upgrade steps idempotently against org-scoped data gates."""

    UPGRADE_STEPS = (
        "hybrid_memory_fusion",
        "org_adaptive_learning",
        "causal_training",
        "retrieval_ranker_sync",
        "process_conformance",
        "industry_knowledge",
        "multimodal_audio",
        "predictive_training_queue",
        "confidence_calibration",
        "event_intelligence",
        "long_horizon_gates",
        "provider_ab_routing",
        "generative_review_gate",
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def run_all_upgrades(self, org_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for step in self.UPGRADE_STEPS:
            try:
                results[step] = await getattr(self, f"upgrade_{step}")(org_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ml_upgrade_step_failed org=%s step=%s error=%s", org_id, step, exc)
                results[step] = {"status": "error", "error": str(exc)}
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        results["org_id"] = org_id
        return results

    async def upgrade_hybrid_memory_fusion(self, org_id: str) -> dict[str, Any]:
        from app.services.hybrid_memory_service import get_hybrid_memory_service

        service = get_hybrid_memory_service(self.settings)
        sample = await service.query_all_memory(org_id, None, "health check", top_k=1)
        return {
            "status": "live",
            "fusion": "rrf_across_rag_hybrid_graph",
            "stores_queried": list(sample.keys()),
        }

    async def upgrade_org_adaptive_learning(self, org_id: str) -> dict[str, Any]:
        from app.services.org_learning_profile_service import get_org_learning_profile_service

        outcomes = await self._count_outcome_events(org_id)
        profile_svc = get_org_learning_profile_service(self.settings)
        profile = await profile_svc.load_profile(org_id)
        already = bool(profile.get("domain_adaptive_learning_enabled"))
        global_on = bool(getattr(self.settings, "domain_adaptive_learning_enabled", False))
        if global_on or already:
            return {
                "status": "enabled",
                "outcome_events": outcomes,
                "source": "global" if global_on else "org_profile",
            }
        if outcomes < MIN_OUTCOMES_FOR_ORG_LEARNING:
            return {
                "status": "waiting",
                "outcome_events": outcomes,
                "required": MIN_OUTCOMES_FOR_ORG_LEARNING,
            }
        enabled = await profile_svc.enable_domain_adaptive_learning(
            org_id,
            reason=f"auto_enabled_at_{outcomes}_outcomes",
        )
        return {
            "status": "enabled" if enabled else "failed",
            "outcome_events": outcomes,
            "source": "org_profile_auto",
        }

    async def upgrade_causal_training(self, org_id: str) -> dict[str, Any]:
        from app.ml.intelligence_training import train_causal_impact_analyzer

        result = await train_causal_impact_analyzer(org_id, settings=self.settings)
        return {"status": "trained" if result.get("trained") else "waiting", **result}

    async def upgrade_retrieval_ranker_sync(self, org_id: str) -> dict[str, Any]:
        from app.ml.intelligence_training import sync_retrieval_ranker_examples

        synced = await sync_retrieval_ranker_examples(org_id, settings=self.settings)
        from app.ml.intelligence_training import train_v5_retrieval_ranker

        train_result = {"trained": False, "reason": "insufficient_examples"}
        if synced.get("example_count", 0) >= MIN_RETRIEVAL_RANKER_EXAMPLES:
            train_result = await train_v5_retrieval_ranker(org_id, settings=self.settings)
        return {"sync": synced, "training": train_result}

    async def upgrade_process_conformance(self, org_id: str) -> dict[str, Any]:
        from app.services.process_mining_service import get_process_mining_service

        report = await get_process_mining_service(self.settings).check_process_conformance(org_id)
        return {"status": "ok", "report": report}

    async def upgrade_industry_knowledge(self, org_id: str) -> dict[str, Any]:
        from app.services.external_knowledge_service import INDUSTRY_KNOWLEDGE_SOURCES

        return {
            "status": "live",
            "providers": INDUSTRY_KNOWLEDGE_SOURCES,
            "note": "Wikipedia, PubMed, SEC EDGAR wired via external_knowledge_service",
        }

    async def upgrade_multimodal_audio(self, org_id: str) -> dict[str, Any]:
        from app.services.model_router import ModelRouter

        router = ModelRouter(self.settings)
        route = await router.route_for_modality(has_audio=True)
        return {"status": "live", "audio_route": route, "org_id": org_id}

    async def upgrade_predictive_training_queue(self, org_id: str) -> dict[str, Any]:
        from app.services.training_signal_service import get_training_signal_service
        from app.ml.intelligence_training import train_catalog_model

        readiness = await get_training_signal_service(self.settings).get_training_readiness(org_id)
        queued: list[dict[str, Any]] = []
        for model_name, meta in (readiness.get("models") or {}).items():
            if meta.get("status") != "ready":
                continue
            try:
                result = await train_catalog_model(org_id, model_name, settings=self.settings)
                queued.append({"model": model_name, **result})
            except Exception as exc:  # noqa: BLE001
                queued.append({"model": model_name, "trained": False, "error": str(exc)})
        return {"status": "ok", "attempted": queued}

    async def upgrade_confidence_calibration(self, org_id: str) -> dict[str, Any]:
        from app.services.confidence_calibrator import get_confidence_calibrator
        from app.services.ai_trust_layer import get_ai_trust_layer
        from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, annotate_confidence

        multiplier = get_confidence_calibrator(self.settings).get_multiplier(org_id, "assistant")
        probe_confidence = 0.72
        sample = get_ai_trust_layer().wrap_response_calibrated(
            org_id,
            answer="Calibration probe",
            sources=[],
            confidence=probe_confidence,
            reasoning_summary="Calibration active",
            actions_taken=[],
            actions_pending_approval=[],
            advisory_only=True,
        )
        sample = annotate_confidence(
            sample,
            is_estimate=True,
            source=CONFIDENCE_SOURCE_HEURISTIC,
            value=probe_confidence,
        )
        return {
            "status": "live",
            "multiplier": multiplier,
            "sample_band": sample.get("confidence_band"),
        }

    async def upgrade_event_intelligence(self, org_id: str) -> dict[str, Any]:
        from app.services.event_intelligence_service import EventIntelligenceService

        handlers = list(EventIntelligenceService.EVENT_HANDLERS.keys())
        return {"status": "live", "typed_handlers": handlers, "org_id": org_id}

    async def upgrade_long_horizon_gates(self, org_id: str) -> dict[str, Any]:
        from app.ml.world_models import WorldModelScaffold
        from app.services.rl_policy_gate import get_rl_policy_status

        world = await WorldModelScaffold().check_activation_status(org_id)
        rl = get_rl_policy_status()
        return {
            "status": "ok",
            "world_models": world,
            "reinforcement_learning": rl,
            "federated_learning": "disabled_by_policy",
            "autonomous_optimization": "human_gated_slow_step_only",
            "generative_agents": "requires_human_review",
        }

    async def upgrade_provider_ab_routing(self, org_id: str) -> dict[str, Any]:
        from app.services.strategy_performance_ledger import PROVIDER_STRATEGY_KEYS

        return {
            "status": "live",
            "provider_candidates": PROVIDER_STRATEGY_KEYS,
            "note": "Ledger UCB selects among openai/anthropic/google provider keys per segment",
        }

    async def upgrade_generative_review_gate(self, org_id: str) -> dict[str, Any]:
        from app.operators.generative_agent_coordinator import get_generative_agent_coordinator

        result = await get_generative_agent_coordinator(self.settings).execute_generative_task(
            org_id,
            "create_plan",
            {"goal": "ML upgrade validation", "prompt": "Summarize intelligence health"},
            department="engineering",
        )
        return {
            "status": "ok",
            "requires_human_review": result.get("requiresHumanReview"),
            "approval_required": True,
        }

    async def _count_outcome_events(self, org_id: str) -> int:
        try:
            resp = (
                self._client()
                .table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def sync_retrieval_ranker_examples_table(self, org_id: str) -> dict[str, Any]:
        from app.ml.intelligence_training import sync_retrieval_ranker_examples

        return await sync_retrieval_ranker_examples(org_id, settings=self.settings)


_ml_upgrade_service: MLUpgradeService | None = None


def get_ml_upgrade_service(settings: Settings | None = None) -> MLUpgradeService:
    global _ml_upgrade_service
    if _ml_upgrade_service is None or settings is not None:
        _ml_upgrade_service = MLUpgradeService(settings)
    return _ml_upgrade_service
