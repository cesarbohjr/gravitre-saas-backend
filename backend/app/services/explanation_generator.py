"""Unified explanation generation for answers, suggestions, and predictions."""
from __future__ import annotations

from typing import Any

from app.services.answer_explanation import generate_answer_explanation, generate_suggestion_explanation
from app.services.optimization_suggestion_service import _serialize_suggestion


class ExplanationGenerator:
    """
    Selects the correct explanation type per response.
    Never exposes raw chain-of-thought.
    """

    async def explain(
        self,
        response_type: str,
        org_id: str,
        sources: list[dict[str, Any]],
        model_output: dict[str, Any],
        classification: dict[str, Any] | None = None,
    ) -> str:
        _ = org_id, classification
        if response_type == "answer":
            return await self._explain_answer(sources, model_output)
        if response_type == "suggestion":
            return self._explain_suggestion(model_output)
        if response_type == "prediction":
            return self._explain_prediction(model_output)
        if response_type == "risk_signal":
            return self._explain_risk(model_output, sources)
        return await self._explain_generic(sources, model_output)

    async def _explain_answer(self, sources: list[dict], model_output: dict[str, Any]) -> str:
        return generate_answer_explanation(
            sources,
            reasoning_trace=model_output.get("reasoning_trace"),
            conflicts=model_output.get("conflicts"),
            refined_query=model_output.get("refined_query"),
        )

    def _explain_suggestion(self, model_output: dict[str, Any]) -> str:
        suggestion = model_output if model_output.get("suggestion_type") else _serialize_suggestion(model_output)
        return generate_suggestion_explanation(suggestion)

    def _explain_prediction(self, model_output: dict[str, Any]) -> str:
        return (
            f"This forecast is based on "
            f"{model_output.get('data_points_used', '?')} historical data points using "
            f"{model_output.get('model_used', 'ML model')}. "
            f"{model_output.get('confidence_note', '')}"
        ).strip()

    def _explain_risk(self, model_output: dict[str, Any], sources: list[dict]) -> str:
        signal = model_output.get("signal") or model_output.get("title") or "Risk signal"
        source_count = len(sources)
        return (
            f"{signal} was surfaced from {source_count} supporting source(s). "
            "Review before acting — advisory only."
        )

    async def _explain_generic(self, sources: list[dict], model_output: dict[str, Any]) -> str:
        return generate_answer_explanation(sources, reasoning_trace=model_output.get("reasoning_trace"))


_explanation_generator: ExplanationGenerator | None = None


def get_explanation_generator() -> ExplanationGenerator:
    global _explanation_generator
    if _explanation_generator is None:
        _explanation_generator = ExplanationGenerator()
    return _explanation_generator
