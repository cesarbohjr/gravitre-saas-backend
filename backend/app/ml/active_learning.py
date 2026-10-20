"""Uncertainty sampling over real inference probability distributions.

Sampling prioritizes review; it never manufactures labels or approves actions.
"""
from __future__ import annotations

import math
from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class ActiveLearningCoordinator(CatalogScaffoldModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.READY
    catalog_name = "active_learning"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        candidates = kwargs.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return {"status": "dormant", "model": self.catalog_name,
                    "reason": "inference_distributions_required", "advisory_only": True}
        limit = kwargs.get("limit", 10)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        ranked = []
        seen = set()
        for candidate in candidates[:10000]:
            if not isinstance(candidate, dict):
                continue
            identifier = candidate.get("id")
            probabilities = candidate.get("probabilities")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                continue
            if not isinstance(probabilities, dict) or len(probabilities) < 2:
                continue
            try:
                values = [float(value) for value in probabilities.values()]
            except (TypeError, ValueError):
                continue
            if any(not math.isfinite(p) or p < 0 or p > 1 for p in values):
                continue
            if not math.isclose(sum(values), 1.0, abs_tol=1e-5):
                continue
            seen.add(identifier)
            entropy = -sum(p * math.log(p) for p in values if p > 0) / math.log(len(values))
            ranked.append({"id": identifier, "uncertainty": entropy})
        ranked.sort(key=lambda row: (-row["uncertainty"], row["id"]))
        return {"status": "ok" if ranked else "dormant", "model": self.catalog_name,
                "method": "normalized_entropy", "candidates": ranked[:limit],
                "eligible_count": len(ranked), "advisory_only": True,
                "reason": None if ranked else "valid_probability_distributions_required"}
