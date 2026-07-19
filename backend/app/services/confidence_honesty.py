"""Module C — confidence provenance helpers (STA-286 estimate labeling pattern).

Hard rule: a numeric confidence either comes from a real computation over
outcome/feedback/model probability, or is explicitly marked as an estimate.
Silent constants presented as live intelligence scores are forbidden.
"""
from __future__ import annotations

from typing import Any

CONFIDENCE_SOURCE_HEURISTIC = "heuristic"
CONFIDENCE_SOURCE_TYPE_PRIOR = "type_reliability_prior"
CONFIDENCE_SOURCE_FEEDBACK = "feedback_acceptance_rate"
CONFIDENCE_SOURCE_MODEL = "loaded_model_artifact"
CONFIDENCE_SOURCE_OUTCOME = "module_a_outcomes"
CONFIDENCE_SOURCE_INSUFFICIENT = "insufficient_data"

LIVE_PATH_HEURISTIC = "heuristic"
LIVE_PATH_LOADED_ARTIFACT = "loaded_model_artifact"
LIVE_PATH_DATA_GATE = "data_gate"


def estimated_confidence(
    value: float,
    *,
    source: str = CONFIDENCE_SOURCE_HEURISTIC,
) -> dict[str, Any]:
    """Wrap a heuristic/static score so callers cannot present it as learned."""
    return {
        "confidence": float(value),
        "confidence_is_estimate": True,
        "confidence_source": source,
    }


def computed_confidence(
    value: float,
    *,
    source: str,
) -> dict[str, Any]:
    """Wrap a score derived from real feedback, outcomes, or a loaded model."""
    return {
        "confidence": float(value),
        "confidence_is_estimate": False,
        "confidence_source": source,
    }


def annotate_confidence(
    payload: dict[str, Any],
    *,
    is_estimate: bool,
    source: str,
) -> dict[str, Any]:
    """Attach provenance fields without dropping existing keys."""
    out = dict(payload)
    out["confidence_is_estimate"] = bool(is_estimate)
    out["confidenceIsEstimate"] = bool(is_estimate)
    out["confidence_source"] = source
    out["confidenceSource"] = source
    return out
