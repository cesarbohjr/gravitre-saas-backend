"""Structured explainability envelope — no chain-of-thought exposure (Wave 9)."""
from __future__ import annotations

from typing import Any

from app.services.explanation_generator import get_explanation_generator


class ExplainabilityEngine:
    """User-facing explanation envelope over existing ExplanationGenerator."""

    async def explain_turn(
        self,
        *,
        response_type: str,
        org_id: str,
        sources: list[dict[str, Any]],
        model_output: dict[str, Any],
        classification: dict[str, Any] | None = None,
        context_profile: dict[str, Any] | None = None,
        confidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        summary = await get_explanation_generator().explain(
            response_type,
            org_id,
            sources,
            model_output,
            classification,
        )
        used = context_profile.get("sourcesUsed") if context_profile else sources
        missing = list((confidence or {}).get("missing_context") or [])
        raw_score = (confidence or {}).get("score")
        if raw_score is None:
            raw_score = (confidence or {}).get("confidence")
        score = float(raw_score) if raw_score is not None else 0.0

        evidence = []
        for row in (used or [])[:8]:
            if isinstance(row, dict):
                evidence.append(
                    {
                        "label": row.get("title") or row.get("label") or row.get("kind"),
                        "kind": row.get("kind") or row.get("type"),
                        "relevance": row.get("relevance") or row.get("score"),
                    }
                )

        envelope = {
            "summary": summary,
            "evidence": evidence,
            "confidence_note": self._confidence_note(score, missing),
            "missing_context": missing,
            "advisory_only": True,
            "response_type": response_type,
            "domain_metadata": self._domain_metadata(classification),
            "retrieval_metadata": self._retrieval_metadata(classification, context_profile),
        }
        return await self._maybe_enrich_with_visibility(
            org_id,
            envelope,
            classification=classification,
            context_profile=context_profile,
        )

    async def _maybe_enrich_with_visibility(
        self,
        org_id: str,
        envelope: dict[str, Any],
        *,
        classification: dict[str, Any] | None = None,
        context_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.config import get_settings
        from app.services.intelligence_visibility_service import get_intelligence_visibility_service

        visibility = get_intelligence_visibility_service(get_settings())
        if not visibility.is_enabled():
            return envelope
        return await visibility.enrich_legacy_explainability(
            org_id,
            envelope,
            classification=classification,
            context=context_profile,
        )

    def format_user_facing(self, envelope: dict[str, Any] | None) -> str:
        if not envelope:
            return ""
        parts = [str(envelope.get("summary") or "").strip()]
        note = envelope.get("confidence_note")
        if note:
            parts.append(str(note))
        missing = envelope.get("missing_context") or []
        if missing:
            parts.append(f"Missing context: {', '.join(str(item) for item in missing)}.")
        parts.append("Advisory only — verify before acting on recommendations.")
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _confidence_note(score: float, missing: list[str]) -> str:
        pct = int(round(score * 100))
        if score >= 0.75:
            base = f"High confidence ({pct}%) based on grounded sources."
        elif score >= 0.5:
            base = f"Moderate confidence ({pct}%) — additional context may improve the answer."
        else:
            base = f"Lower confidence ({pct}%) — treat as preliminary guidance."
        if missing:
            return f"{base} Gaps: {', '.join(missing)}."
        return base

    @staticmethod
    def _domain_metadata(classification: dict[str, Any] | None) -> dict[str, Any] | None:
        domain = (classification or {}).get("domain")
        if not domain:
            return None
        return {
            "industry": domain.get("industry"),
            "department": domain.get("department"),
            "subdomain": domain.get("subdomain"),
            "confidence": domain.get("confidence"),
            "profile_id": domain.get("profile_id"),
            "routing_active": domain.get("routing_active"),
            "source": domain.get("source"),
        }


    @staticmethod
    def _retrieval_metadata(
        classification: dict[str, Any] | None,
        context_profile: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        effectiveness = (classification or {}).get("retrieval_effectiveness")
        if not effectiveness and context_profile:
            effectiveness = context_profile.get("retrieval_effectiveness")
        if not effectiveness:
            return None
        return {
            "retrieval_policy": effectiveness.get("retrieval_policy"),
            "retrieval_score": effectiveness.get("retrieval_score"),
            "assignment_ids_used": effectiveness.get("assignment_ids_used"),
            "top_sources": (effectiveness.get("top_sources") or [])[:5],
        }


_engine: ExplainabilityEngine | None = None


def get_explainability_engine() -> ExplainabilityEngine:
    global _engine
    if _engine is None:
        _engine = ExplainabilityEngine()
    return _engine
