"""Contamination defense — provenance classification before long-term memory writes."""
from __future__ import annotations

import re
from typing import Any

from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_ENTITY_EXTRACT,
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_INSUFFICIENT,
    annotate_confidence,
)

SOURCE_USER_DIRECT = "user_direct"
SOURCE_MODEL_INFERENCE = "model_inference"
SOURCE_UNTRUSTED_EXTERNAL = "untrusted_external"
SOURCE_WORKFLOW_OUTCOME = "workflow_outcome"
SOURCE_PROBE = "probe"

_UNTRUSTED_MARKERS = (
    "connector:",
    "document:",
    "rag:",
    "untrusted",
    "external_doc",
    "tool_result",
    "web_fetch",
    "ingest:",
)
_PROBE_MARKERS = ("probe", "smoke", "one_brain_workspace_memory_probe")
_USER_MARKERS = ("user_statement", "confirmed_turn", "user_direct", "standing decision")

# Caps — untrusted content must never enter as high-confidence standing memory.
_CONFIDENCE_CAP = {
    SOURCE_USER_DIRECT: 95.0,
    SOURCE_MODEL_INFERENCE: 75.0,
    SOURCE_WORKFLOW_OUTCOME: 80.0,
    SOURCE_UNTRUSTED_EXTERNAL: 45.0,
    SOURCE_PROBE: 50.0,
}


def classify_memory_source(raw: dict[str, Any], *, provenance: str = "") -> str:
    """Classify provenance for a memory write candidate."""
    explicit = str(raw.get("source_class") or "").strip().lower()
    if explicit in _CONFIDENCE_CAP:
        return explicit

    prov = (provenance or str(raw.get("provenance") or "")).strip().lower()
    if any(m in prov for m in _PROBE_MARKERS):
        return SOURCE_PROBE
    if raw.get("from_untrusted_external") or raw.get("untrusted_source"):
        return SOURCE_UNTRUSTED_EXTERNAL
    if any(m in prov for m in _UNTRUSTED_MARKERS):
        return SOURCE_UNTRUSTED_EXTERNAL
    if raw.get("user_direct") or any(m in prov for m in _USER_MARKERS):
        return SOURCE_USER_DIRECT
    if prov.startswith("learn_outcome") or raw.get("outcome_event"):
        return SOURCE_WORKFLOW_OUTCOME
    if raw.get("confirmed") or raw.get("promote_memories"):
        return SOURCE_USER_DIRECT
    return SOURCE_MODEL_INFERENCE


def _confidence_source_for_class(source_class: str) -> str:
    if source_class == SOURCE_UNTRUSTED_EXTERNAL:
        return CONFIDENCE_SOURCE_INSUFFICIENT
    if source_class in {SOURCE_USER_DIRECT, SOURCE_WORKFLOW_OUTCOME}:
        return CONFIDENCE_SOURCE_ENTITY_EXTRACT
    return CONFIDENCE_SOURCE_HEURISTIC


def validate_memory_write(
    raw: dict[str, Any],
    *,
    provenance: str = "",
) -> dict[str, Any]:
    """Apply source classification and confidence cap. Returns enriched dict."""
    out = dict(raw)
    source_class = classify_memory_source(out, provenance=provenance)
    out["source_class"] = source_class

    try:
        conf = float(out.get("confidence") if out.get("confidence") is not None else 80)
    except (TypeError, ValueError):
        conf = 80.0

    cap = _CONFIDENCE_CAP.get(source_class, 75.0)
    conf = max(0.0, min(conf, cap))
    out["confidence"] = conf

    is_estimate = source_class != SOURCE_USER_DIRECT
    labeled = annotate_confidence(
        out,
        value=conf,
        is_estimate=is_estimate,
        source=_confidence_source_for_class(source_class),
    )
    if source_class == SOURCE_UNTRUSTED_EXTERNAL:
        labeled["memory_caution"] = (
            "Sourced from untrusted external content — do not treat as standing user fact."
        )
        labeled["memoryCaution"] = labeled["memory_caution"]
    return labeled


def attach_recall_honesty(row: dict[str, Any]) -> dict[str, Any]:
    """Module C labels on recall — visible lower confidence for untrusted rows."""
    out = dict(row)
    source_class = str(out.get("source_class") or SOURCE_MODEL_INFERENCE).lower()
    try:
        conf = float(out.get("confidence") or 0)
        if conf <= 1.0:
            conf *= 100.0
    except (TypeError, ValueError):
        conf = 0.0

    is_estimate = source_class != SOURCE_USER_DIRECT
    source = _confidence_source_for_class(source_class)
    labeled = annotate_confidence(out, value=conf, is_estimate=is_estimate, source=source)
    labeled["source_class"] = source_class
    if source_class == SOURCE_UNTRUSTED_EXTERNAL:
        labeled["memory_caution"] = (
            "Recalled from untrusted external source — verify before acting."
        )
        labeled["memoryCaution"] = labeled["memory_caution"]
    return labeled


def looks_like_injection(content: str) -> bool:
    """Heuristic guard for plausible false instructions in untrusted text."""
    text = (content or "").strip().lower()
    if not text:
        return False
    patterns = (
        r"ignore (all )?(previous|prior) instructions",
        r"you must (always|never)",
        r"system prompt:",
        r"forget everything",
        r"override (your )?instructions",
    )
    return any(re.search(p, text) for p in patterns)
