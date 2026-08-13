"""Uniform evidence envelope for LIVE + classical assistant answers (Phase D item 6).

Shape: {recommendation, why, sources, confidence} with Module C honesty stamps.
Does not invent citations or scores — callers pass what they already have.
"""
from __future__ import annotations

from typing import Any

from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_INSUFFICIENT,
    label_confidence,
)


def build_evidence_envelope(
    *,
    recommendation: str | None = None,
    why: str | None = None,
    sources: list[dict[str, Any]] | list[str] | None = None,
    confidence: float | dict[str, Any] | None = None,
    confidence_source: str | None = None,
    confidence_is_estimate: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a uniform evidence DTO attached to chat / turn responses.

    ``confidence`` may be a float or an existing honesty dict from label_confidence /
    finalize_confidence. Missing scores are stamped insufficient_data (never invented).
    """
    source_rows = _normalize_sources(sources)
    conf_block = _normalize_confidence(
        confidence,
        source=confidence_source,
        is_estimate=confidence_is_estimate,
    )
    envelope: dict[str, Any] = {
        "recommendation": (recommendation or "").strip() or None,
        "why": (why or "").strip() or None,
        "sources": source_rows,
        "confidence": conf_block.get("confidence"),
        "confidence_is_estimate": conf_block.get("confidence_is_estimate"),
        "confidenceIsEstimate": conf_block.get("confidenceIsEstimate"),
        "confidence_source": conf_block.get("confidence_source"),
        "confidenceSource": conf_block.get("confidenceSource"),
        "evidence_schema": "cognitive_evidence_v1",
    }
    if extra:
        for key, value in extra.items():
            if key not in envelope and value is not None:
                envelope[key] = value
    return envelope


def attach_evidence_envelope(
    payload: dict[str, Any],
    *,
    recommendation: str | None = None,
    why: str | None = None,
    sources: list[dict[str, Any]] | list[str] | None = None,
    confidence: float | dict[str, Any] | None = None,
    confidence_source: str | None = None,
    confidence_is_estimate: bool | None = None,
) -> dict[str, Any]:
    """Return a shallow copy of ``payload`` with ``evidence`` set."""
    out = dict(payload) if isinstance(payload, dict) else {}
    rec = recommendation
    if rec is None:
        rec = str(out.get("message") or out.get("content") or out.get("answer") or "") or None
    why_text = why
    if why_text is None:
        why_text = str(out.get("answer_explanation") or out.get("explanation") or "") or None
    src = sources
    if src is None:
        raw = out.get("sources") or out.get("rag_sources") or out.get("citations")
        if isinstance(raw, list):
            src = raw
    conf = confidence
    if conf is None:
        conf = out.get("confidence")
    out["evidence"] = build_evidence_envelope(
        recommendation=rec,
        why=why_text,
        sources=src,
        confidence=conf,
        confidence_source=confidence_source,
        confidence_is_estimate=confidence_is_estimate,
    )
    return out


def _normalize_sources(
    sources: list[dict[str, Any]] | list[str] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in sources or []:
        if isinstance(item, str) and item.strip():
            out.append({"label": item.strip()[:300]})
            continue
        if not isinstance(item, dict):
            continue
        label = (
            item.get("citation")
            or item.get("title")
            or item.get("publisher")
            or item.get("source_name")
            or item.get("label")
            or item.get("id")
        )
        row: dict[str, Any] = {
            "label": str(label)[:300] if label else None,
            "source_id": item.get("source_id") or item.get("id"),
            "citation": item.get("citation"),
            "score": item.get("score") or item.get("freshness_score"),
        }
        # Drop empty keys for a compact envelope.
        out.append({k: v for k, v in row.items() if v is not None})
    return out[:12]


def _normalize_confidence(
    confidence: float | dict[str, Any] | None,
    *,
    source: str | None,
    is_estimate: bool | None,
) -> dict[str, Any]:
    if isinstance(confidence, dict):
        score = confidence.get("confidence")
        if score is None:
            score = confidence.get("score")
        src = (
            source
            or confidence.get("confidence_source")
            or confidence.get("confidenceSource")
            or CONFIDENCE_SOURCE_HEURISTIC
        )
        est = (
            is_estimate
            if is_estimate is not None
            else confidence.get("confidence_is_estimate")
            if confidence.get("confidence_is_estimate") is not None
            else confidence.get("confidenceIsEstimate")
            if confidence.get("confidenceIsEstimate") is not None
            else True
        )
        if score is None:
            return label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)
        try:
            return label_confidence(float(score), source=str(src), is_estimate=bool(est))
        except (TypeError, ValueError):
            return label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)

    if confidence is None:
        return label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)

    try:
        return label_confidence(
            float(confidence),
            source=str(source or CONFIDENCE_SOURCE_HEURISTIC),
            is_estimate=True if is_estimate is None else bool(is_estimate),
        )
    except (TypeError, ValueError):
        return label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)
