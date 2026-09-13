"""G1 — Semantic deduplication for predictions and business signals."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from app.schemas.intelligence_projection import CanonicalPrediction, IntelligenceProvenance, IntelligenceQualityFlag


def _semantic_key(title: str, summary: str, department: str | None, source: str) -> str:
    base = f"{source}|{department or ''}|{title}|{summary[:80]}"
    normalized = re.sub(r"\s+", " ", base.lower()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _is_unscoped(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return "unscoped" in text or not title.strip()


def normalize_signals_to_predictions(
    signals: list[dict[str, Any]],
    *,
    fetched_at: str,
) -> list[CanonicalPrediction]:
    """Convert business signals to canonical predictions with semantic dedup."""
    by_key: dict[str, CanonicalPrediction] = {}
    for signal in signals:
        title = str(signal.get("title") or "").strip()
        summary = str(signal.get("summary") or "").strip()
        if not title and not summary:
            continue
        dept_raw = signal.get("department") or signal.get("department_id")
        department = str(dept_raw).strip() if dept_raw else None
        source = str(signal.get("source") or signal.get("signal_type") or "business_signals")
        key = _semantic_key(title, summary, department, source)
        quality: list[IntelligenceQualityFlag] = []
        if _is_unscoped(title, summary):
            quality.append("UNSCOPED_PREDICTION")
        confidence_raw = signal.get("confidence") or signal.get("quality_score")
        confidence: float | None = None
        if confidence_raw is not None:
            try:
                confidence = float(confidence_raw)
                if confidence > 1:
                    confidence = confidence / 100.0
            except (TypeError, ValueError):
                confidence = None
        business_statement = title if title else summary
        if summary and summary.lower() not in business_statement.lower():
            business_statement = f"{title}: {summary}" if title else summary

        existing = by_key.get(key)
        if existing:
            # Keep higher-confidence duplicate; flag if titles differ materially.
            if confidence is not None and (existing.confidence or 0) < confidence:
                by_key[key] = CanonicalPrediction(
                    id=str(signal.get("id") or key),
                    type=str(signal.get("signal_type") or "prediction"),
                    businessStatement=business_statement[:240],
                    subject=title[:120] or None,
                    department=department,
                    confidence=confidence,
                    evidence=[summary] if summary else [],
                    sourceModel=signal.get("model"),
                    createdAt=signal.get("created_at"),
                    freshness=signal.get("freshness"),
                    status="active",
                    recommendedActions=[],
                    qualityFlags=list(set(existing.qualityFlags + quality)),
                    source=IntelligenceProvenance(
                        system="business_signals_engine",
                        recordId=str(signal.get("id") or ""),
                        fetchedAt=fetched_at,
                    ),
                    semanticKey=key,
                )
            continue

        by_key[key] = CanonicalPrediction(
            id=str(signal.get("id") or key),
            type=str(signal.get("signal_type") or "prediction"),
            businessStatement=business_statement[:240],
            subject=title[:120] or None,
            department=department,
            confidence=confidence,
            evidence=[summary] if summary else [],
            sourceModel=signal.get("model"),
            createdAt=signal.get("created_at"),
            freshness=signal.get("freshness"),
            status="active",
            recommendedActions=[],
            qualityFlags=quality,
            source=IntelligenceProvenance(
                system="business_signals_engine",
                recordId=str(signal.get("id") or ""),
                fetchedAt=fetched_at,
            ),
            semanticKey=key,
        )
    return list(by_key.values())
