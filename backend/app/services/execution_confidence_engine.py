"""Unified execution confidence — pre/post response scoring for assistant and intelligence API."""
from __future__ import annotations

from typing import Any

from app.services.confidence_scorer import get_confidence_scorer
from app.services.sync_confidence import compute_sync_confidence


class ExecutionConfidenceEngine:
    """Single confidence surface for live assistant and governed execution paths."""

    def assess_response(
        self,
        *,
        query: str,
        answer: str,
        rag_sources: list[dict[str, Any]] | None,
        validation_confidence: float | None = None,
        conflict_count: int = 0,
        context_profile: dict[str, Any] | None = None,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        sync = compute_sync_confidence(
            query=query,
            answer=answer,
            chunks=rag_sources,
            validation_confidence=validation_confidence,
            conflict_count=conflict_count,
        )
        context_confidence = self._context_confidence(context_profile)
        blended = round(min(1.0, 0.75 * float(sync.get("score") or 0.0) + 0.25 * context_confidence), 4)
        missing_context = self._missing_context(context_profile)
        risk = str(risk_level or "low").lower()

        return {
            "confidence": blended,
            "score": blended,
            "band": sync.get("band"),
            "needs_clarification": bool(sync.get("needs_clarification")) or blended < 0.4,
            "rag_quality_score": sync.get("rag_quality_score"),
            "context_confidence": context_confidence,
            "reason": self._reason(blended, missing_context, risk),
            "missing_context": missing_context,
            "risk_level": risk,
        }

    def assess_pre_execution(
        self,
        *,
        classification: dict[str, Any],
        context_profile: dict[str, Any] | None = None,
        requires_approval: bool = False,
    ) -> dict[str, Any]:
        context_confidence = self._context_confidence(context_profile)
        base = float(classification.get("classification_confidence") or 0.55)
        approval_penalty = 0.05 if requires_approval else 0.0
        score = round(max(0.0, min(1.0, 0.6 * base + 0.4 * context_confidence - approval_penalty)), 4)
        return {
            "confidence": score,
            "context_confidence": context_confidence,
            "missing_context": self._missing_context(context_profile),
            "risk_level": str(classification.get("risk_level") or "medium").lower(),
            "requires_approval": requires_approval,
        }

    def assess_with_trust_signals(
        self,
        *,
        query: str,
        answer: str,
        sources: list[dict[str, Any]],
        model_output: dict[str, Any],
        classification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scorer = get_confidence_scorer()
        weighted = scorer.compute(
            rag_quality=float(model_output.get("rag_quality_score") or 0.0),
            source_reliability=None,
            ml_confidence=None,
            classification_confidence=float((classification or {}).get("classification_confidence") or 0.55),
        )
        live = self.assess_response(
            query=query,
            answer=answer,
            rag_sources=sources,
            validation_confidence=model_output.get("validation_confidence"),
            conflict_count=len(model_output.get("conflicts") or []),
        )
        score = round((float(live["score"]) + float(weighted or 0.0)) / 2, 4)
        live["score"] = score
        live["confidence"] = score
        live["trust_signals"] = {"score": weighted}
        return live

    @staticmethod
    def _context_confidence(context_profile: dict[str, Any] | None) -> float:
        if not context_profile:
            return 0.45
        ranked = context_profile.get("ranked_sources") or context_profile.get("sourcesUsed") or []
        if not ranked:
            return 0.4
        scores = [float(row.get("score") or 0.5) for row in ranked if isinstance(row, dict)]
        if not scores and hasattr(ranked[0], "score"):
            scores = [float(item.score) for item in ranked]
        return round(sum(scores) / max(len(scores), 1), 4)

    @staticmethod
    def _missing_context(context_profile: dict[str, Any] | None) -> list[str]:
        if not context_profile:
            return ["org_context", "knowledge"]
        used_types = {
            str(row.get("type") or row.get("source_type") or "")
            for row in (context_profile.get("sourcesUsed") or [])
            if isinstance(row, dict)
        }
        missing: list[str] = []
        if "rag" not in used_types:
            missing.append("knowledge")
        if "org_context" not in used_types:
            missing.append("org_context")
        if "conversation_memory" not in used_types:
            missing.append("conversation_memory")
        return missing

    @staticmethod
    def _reason(score: float, missing_context: list[str], risk_level: str) -> str:
        parts = [f"Confidence {int(score * 100)}% based on retrieved context and answer grounding."]
        if missing_context:
            parts.append(f"Missing: {', '.join(missing_context)}.")
        if risk_level in {"high", "critical"}:
            parts.append("Elevated risk — approval may be required before execution.")
        return " ".join(parts)


_engine: ExecutionConfidenceEngine | None = None


def get_execution_confidence_engine() -> ExecutionConfidenceEngine:
    global _engine
    if _engine is None:
        _engine = ExecutionConfidenceEngine()
    return _engine
