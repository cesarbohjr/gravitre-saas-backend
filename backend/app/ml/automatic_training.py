"""Background lifecycle checks within the existing company-intelligence job.

No model toggles, no new engine. Each trainer owns label validation and the
shared registry owns held-out champion/challenger promotion. Redis serializes
checks across workers; a missing coordination service fails closed.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.core.redis_client import get_sync_redis

logger = get_logger(__name__)

# Existing company-intelligence steps already cover intent, workflow, memory,
# ranker and clustering. Do not train them again in a second loop.
AUTOMATIC_MODELS = (
    "revenue_forecaster", "churn_risk_scorer", "cf_matrix_factorizer",
    "capacity_forecaster", "agentic_planning", "world_model",
    "graph_neural_network", "self_supervised_embeddings", "meta_learning",
)
# These already train in CompanyIntelligenceOrchestrator; require the same
# reviewed consent without adding duplicate training work.
CONSENT_MANAGED_MODELS = (*AUTOMATIC_MODELS,
    "intent_classifier", "workflow_anomaly_detector", "workflow_duration_forecaster",
    "workflow_success_predictor", "retrieval_ranker", "query_clusterer",
    "memory_promotion_scorer", "retrieval_memory_learner",
)
COOLDOWN = timedelta(days=14)


async def reconcile_automatic_models(org_id: str, settings: Settings) -> dict[str, Any]:
    from app.ml.intelligence_training import CATALOG_MODEL_NAMES, train_catalog_model
    from app.ml.registry import get_model_registry
    from app.ml.training_consent import load_training_consents, consent_is_approved

    if not org_id or not org_id.strip():
        raise ValueError("org_id required")
    redis = await asyncio.to_thread(get_sync_redis, settings)
    if redis is None:
        return {"status": "dormant", "reason": "training_coordination_unavailable", "models": {}}
    # No short expiring lease: it must cover the whole bounded job. Redis lock
    # release checks ownership, so an old worker cannot release a newer lease.
    lock = redis.lock(f"ml:auto:{org_id}", timeout=7200, blocking_timeout=0, thread_local=False)
    if not await asyncio.to_thread(lock.acquire, blocking=False):
        return {"status": "already_running", "models": {}}
    results = {}
    try:
        consents = await asyncio.to_thread(load_training_consents, org_id, settings)
        models = await get_model_registry().list_models(org_id=org_id)
        now = datetime.now(timezone.utc)
        for name in AUTOMATIC_MODELS:
            if not consent_is_approved(consents, name):
                results[name] = {"status": "awaiting_consent"}
                continue
            registered = next((m for m in models if m.name == CATALOG_MODEL_NAMES[name]), None)
            updated = registered.updated_at if registered else None
            # An explicitly bound target starts as a draft registry row. Its
            # creation timestamp is not a previous training run and must not
            # delay the first valid, consented training attempt for 14 days.
            if updated is not None and registered.current_version > 0:
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if now - updated < COOLDOWN:
                    results[name] = {"status": "cooldown"}
                    continue
            try:
                results[name] = await train_catalog_model(org_id, name, settings=settings)
            except Exception as exc:
                logger.warning("automatic_model_check_failed org_id=%s model=%s error=%s", org_id, name, exc)
                results[name] = {"trained": False, "reason": "training_check_failed"}
        return {"status": "checked", "models": results}
    finally:
        try:
            await asyncio.to_thread(lock.release)
        except Exception as exc:
            logger.warning("automatic_training_lock_release_failed org_id=%s error=%s", org_id, exc)
