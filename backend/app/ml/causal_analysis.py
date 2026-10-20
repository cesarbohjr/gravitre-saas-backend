"""Measured paired before/after impact, with explicit non-causal limitations."""
from __future__ import annotations

import asyncio
import math
from statistics import mean, stdev
from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel
from app.workflows.repository import get_supabase_client

MIN_PRE_POST_POINTS = 30
CONFIDENCE_NOTE = (
    "Paired observational before/after differences are not causal proof. "
    "No randomized control; confounders and selection bias may remain."
)


class CausalImpactAnalyzer(CatalogScaffoldModel):
    model_type = ModelType.CAUSAL_MODEL
    catalog_status = ModelStatus.READY
    advisory_only = True
    catalog_name = "causal_impact_analyzer"

    def _load_pairs(self, org_id: str, metric_name: str, settings: Settings) -> list[tuple[float, float]]:
        client = get_supabase_client(settings)
        rows = (client.table("agent_action_outcomes")
                .select("metric_value_before,metric_value_after,measured_at")
                .eq("org_id", org_id).eq("metric_name", metric_name)
                .not_.is_("measured_at", "null")
                .order("measured_at").limit(10000).execute().data or [])
        pairs = []
        for row in rows:
            if row.get("measured_at") is None:
                continue
            try:
                before, after = float(row["metric_value_before"]), float(row["metric_value_after"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(before) and math.isfinite(after):
                pairs.append((before, after))
        return pairs

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        org_id = str(kwargs.get("org_id") or "")
        metric_name = str(kwargs.get("metric_name") or "deal_amount")
        base = {"model": self.catalog_name, "advisory_only": True,
                "confidence_note": CONFIDENCE_NOTE, "method": "paired_observational_difference"}
        if not org_id:
            return {**base, "status": "not_available", "reason": "org_id required"}
        try:
            pairs = await asyncio.to_thread(self._load_pairs, org_id, metric_name, kwargs.get("settings") or get_settings())
        except Exception:  # read errors must never imply zero measured outcomes
            return {**base, "status": "not_available", "reason": "measurement_read_failed"}
        if len(pairs) < MIN_PRE_POST_POINTS:
            return {**base, "status": "not_available", "reason": "insufficient_measured_pairs",
                    "data_gate": {"current": len(pairs), "required": MIN_PRE_POST_POINTS, "met": False}}
        changes = [after-before for before, after in pairs]
        delta = mean(changes)
        standard_error = stdev(changes) / math.sqrt(len(changes))
        return {**base, "status": "ok", "metric_name": metric_name,
                "pre_mean": mean(before for before, _ in pairs),
                "post_mean": mean(after for _, after in pairs),
                "estimated_effect": delta, "sample_size": len(pairs),
                "confidence": None,  # no calibrated causal confidence available
                "confounder_flags": ["non_randomized", "uncontrolled_confounding"],
                "uncertainty_band": {"low": delta-1.96*standard_error, "high": delta+1.96*standard_error,
                                     "note": "Approximate sampling interval; excludes confounding uncertainty."}}
