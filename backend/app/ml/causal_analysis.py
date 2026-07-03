"""Causal impact analysis from agent_action_outcomes pre/post windows."""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel
from app.workflows.repository import get_supabase_client

MIN_PRE_POST_POINTS = 30
CONFIDENCE_NOTE = (
    "Effect estimate uses pre/post mean comparison — not a randomized experiment. "
    "Confounders may remain; treat as directional evidence only."
)


class CausalImpactAnalyzer(CatalogScaffoldModel):
    """
    Estimates directional metric impact using pre/post windows on agent_action_outcomes.
    Honest substitute until full ITS/DiD pipeline is validated at scale.
    """

    model_type = ModelType.CAUSAL_MODEL
    catalog_status = ModelStatus.PLANNED
    advisory_only = True
    catalog_name = "causal_impact_analyzer"

    async def _load_metric_series(self, org_id: str, metric_name: str, settings: Settings) -> list[float]:
        client = get_supabase_client(settings)
        try:
            rows = (
                client.table("agent_action_outcomes")
                .select("after_value, measured_at")
                .eq("org_id", org_id)
                .eq("metric_name", metric_name)
                .not_.is_("after_value", "null")
                .order("measured_at")
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            return []
        return [float(row.get("after_value") or 0) for row in rows]

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        metric_name = str(kwargs.get("metric_name") or "deal_amount")
        settings = kwargs.get("settings") or get_settings()
        if not org_id:
            return {
                "status": "not_available",
                "model": self.catalog_name,
                "reason": "org_id required",
                "advisory_only": True,
            }
        series = await self._load_metric_series(org_id, metric_name, settings)
        if len(series) < MIN_PRE_POST_POINTS * 2:
            return {
                "status": "not_available",
                "model": self.catalog_name,
                "reason": (
                    f"Need {MIN_PRE_POST_POINTS}+ pre and post observations per metric; "
                    f"have {len(series)} total for {metric_name}."
                ),
                "data_gate": {
                    "current": len(series),
                    "required": MIN_PRE_POST_POINTS * 2,
                    "met": False,
                },
                "current_alternative": "correlational_causal_context v8 fallback",
                "advisory_only": True,
            }
        midpoint = len(series) // 2
        pre = series[:midpoint]
        post = series[midpoint:]
        pre_mean = mean(pre)
        post_mean = mean(post)
        delta = post_mean - pre_mean
        pct = (delta / pre_mean) if pre_mean else 0.0
        spread = pstdev(series) if len(series) > 1 else 0.0
        confidence = round(min(0.85, 0.45 + min(0.4, abs(pct)) + min(0.1, len(series) / 200)), 4)
        return {
            "status": "ok",
            "model": self.catalog_name,
            "metric_name": metric_name,
            "pre_mean": round(pre_mean, 4),
            "post_mean": round(post_mean, 4),
            "estimated_effect": round(delta, 4),
            "estimated_effect_pct": round(pct, 4),
            "confidence": confidence,
            "confounder_flags": ["non_randomized_pre_post_split"],
            "confidence_note": CONFIDENCE_NOTE,
            "method": "pre_post_mean_comparison",
            "sample_size": len(series),
            "uncertainty_band": {
                "low": round(post_mean - spread, 4),
                "high": round(post_mean + spread, 4),
            },
            "advisory_only": True,
        }
