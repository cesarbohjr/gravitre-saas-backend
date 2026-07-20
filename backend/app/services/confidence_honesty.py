"""Module C — one shared confidence-labeling authority (STA-331).

Hard rule: a numeric confidence either comes from a real computation over
outcome/feedback/model probability, or is explicitly marked as an estimate.
Silent constants presented as live intelligence scores are forbidden.

Every call site that attaches confidence to an API/UI payload must go through
``label_confidence`` (or the thin estimated_/computed_ wrappers below).
"""
from __future__ import annotations

from typing import Any

CONFIDENCE_SOURCE_HEURISTIC = "heuristic"
CONFIDENCE_SOURCE_TYPE_PRIOR = "type_reliability_prior"
CONFIDENCE_SOURCE_EDGE_HEURISTIC = "entity_relationship_heuristic"
CONFIDENCE_SOURCE_FEEDBACK = "feedback_acceptance_rate"
CONFIDENCE_SOURCE_MODEL = "loaded_model_artifact"
CONFIDENCE_SOURCE_OUTCOME = "module_a_outcomes"
CONFIDENCE_SOURCE_INSUFFICIENT = "insufficient_data"
CONFIDENCE_SOURCE_MODEL_SELECTION = "model_selection_heuristic"
CONFIDENCE_SOURCE_SIGNAL_HEURISTIC = "business_signal_heuristic"
CONFIDENCE_SOURCE_ENTITY_EXTRACT = "rule_based_entity_extract"
CONFIDENCE_SOURCE_OPTIMIZATION = "optimization_heuristic"
CONFIDENCE_SOURCE_ADVISOR = "advisor_signal_aggregate"

LIVE_PATH_HEURISTIC = "heuristic"
LIVE_PATH_LOADED_ARTIFACT = "loaded_model_artifact"
LIVE_PATH_DATA_GATE = "data_gate"

# KG scoring: stored edge confidence (entity_relationship_builder constants) and
# type reliability priors are BOTH estimates — the blend is not more authoritative
# than either input alone.
KG_BLEND_NOTE = (
    "KG relationship score blends estimated edge confidence with an estimated "
    "type reliability prior — both estimates until Module A outcomes season weights."
)


def label_confidence(
    value: float | None,
    *,
    source: str,
    is_estimate: bool = True,
    key: str = "confidence",
) -> dict[str, Any]:
    """
    Canonical Module C attachment for any confidence number.

    Prefer this over hand-written confidence_is_estimate / confidence_source fields.
    Pass value=None for honest insufficient-data (never invent a fallback float).
    """
    if value is None:
        return {
            key: None,
            "confidence_is_estimate": False,
            "confidenceIsEstimate": False,
            "confidence_source": CONFIDENCE_SOURCE_INSUFFICIENT,
            "confidenceSource": CONFIDENCE_SOURCE_INSUFFICIENT,
        }
    return {
        key: float(value),
        "confidence_is_estimate": bool(is_estimate),
        "confidenceIsEstimate": bool(is_estimate),
        "confidence_source": source,
        "confidenceSource": source,
    }


def estimated_confidence(
    value: float,
    *,
    source: str = CONFIDENCE_SOURCE_HEURISTIC,
) -> dict[str, Any]:
    """Wrap a heuristic/static score so callers cannot present it as learned."""
    return label_confidence(value, source=source, is_estimate=True)


def computed_confidence(
    value: float,
    *,
    source: str,
) -> dict[str, Any]:
    """Wrap a score derived from real feedback, outcomes, or a loaded model."""
    return label_confidence(value, source=source, is_estimate=False)


def annotate_confidence(
    payload: dict[str, Any],
    *,
    is_estimate: bool,
    source: str,
    value: float | None = None,
    key: str = "confidence",
) -> dict[str, Any]:
    """Merge provenance onto an existing payload (optionally overwrite the score)."""
    out = dict(payload)
    labeled = label_confidence(
        value if value is not None else out.get(key),
        source=source,
        is_estimate=is_estimate,
        key=key,
    )
    out.update(labeled)
    return out


def model_selection_ml_confidence(primary_model: str | None) -> dict[str, Any]:
    """Honest ml_confidence input for ConfidenceScorer — always labeled estimate."""
    if primary_model == "ml_internal":
        return estimated_confidence(0.65, source=CONFIDENCE_SOURCE_MODEL_SELECTION)
    return estimated_confidence(0.45, source=CONFIDENCE_SOURCE_MODEL_SELECTION)
