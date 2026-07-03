"""Causal enrichment slot with honest correlational fallback."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.ml.causal_analysis import CausalImpactAnalyzer
from app.services.outcome_attribution_service import CONFIDENCE_NOTE, get_outcome_attribution_service


async def load_causal_enrichment_context(
    org_id: str,
    request: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Prefer PLANNED causal analyzer when available; otherwise surface v8 correlational
    attribution with mandatory disclosure — never imply causality.
    """
    _ = request
    analyzer = CausalImpactAnalyzer()
    causal = await analyzer.predict_structured()
    if causal.get("status") != "not_available":
        return causal

    snapshot = await get_outcome_attribution_service(settings).load_admin_outcomes_snapshot(
        org_id,
        settings=settings or get_settings(),
    )
    summaries = [
        row
        for row in snapshot.get("agentSummaries") or []
        if row.get("sufficientData") and row.get("winRate") is not None
    ]
    if not summaries:
        return {
            **causal,
            "status": "correlational_insufficient_data",
            "current_alternative": "outcome_attribution_v8",
            "confidence_note": CONFIDENCE_NOTE,
            "pending_measurements": snapshot.get("pendingMeasurements"),
            "advisory_only": True,
        }

    best = max(summaries, key=lambda row: float(row.get("winRate") or 0))
    avg_win_rate = sum(float(row.get("winRate") or 0) for row in summaries) / len(summaries)
    return {
        "status": "correlational_fallback",
        "model": "outcome_attribution_v8",
        "reason": causal.get("reason"),
        "confidence_note": CONFIDENCE_NOTE,
        "best_agent_win_rate": best.get("winRate"),
        "best_agent_id": best.get("agentId"),
        "best_agent_sample_size": best.get("sampleSize"),
        "org_avg_win_rate": round(avg_win_rate, 4),
        "agents_with_data": len(summaries),
        "pending_measurements": snapshot.get("pendingMeasurements"),
        "advisory_only": True,
    }
