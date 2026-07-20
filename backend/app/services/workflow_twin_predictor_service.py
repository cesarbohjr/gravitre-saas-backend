"""LLM outcome prediction for workflow digital-twin steps (STA-120)."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_MODEL,
    annotate_confidence,
    estimated_confidence,
)
from app.services.model_router import TaskType, get_model_router

logger = logging.getLogger(__name__)


class TwinStepPrediction(BaseModel):
    summary: str
    predicted_output: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    risks: list[str] = Field(default_factory=list)


def resolve_step_tool_action(step_type: str, config: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (connector_type, action) for fixture lookup."""
    from app.services.tool_service import STEP_TYPE_TO_ACTION

    action = str(config.get("action") or STEP_TYPE_TO_ACTION.get(step_type) or "").strip()
    if not action:
        return None, None
    connector_type = action.split(".", 1)[0] if "." in action else step_type
    return connector_type, action


async def predict_step_outcome(
    settings: Settings,
    *,
    org_id: str,
    step_type: str,
    step_name: str,
    config: dict[str, Any],
    parameters: dict[str, Any],
    step_outputs: dict[str, Any],
    objective: str | None = None,
) -> dict[str, Any]:
    """Predict step output with LLM; no connector side effects."""
    prompt = (
        f"Workflow objective: {objective or 'Simulate workflow step'}\n"
        f"Step: {step_name} ({step_type})\n"
        f"Config: {config}\n"
        f"Parameters: {parameters}\n"
        f"Prior step outputs: {step_outputs}\n"
        "Predict the most likely output JSON this step would produce on a successful live run. "
        "Do not invent secrets or PII. Return strict JSON only."
    )
    fallback_confidence = float(
        estimated_confidence(0.5, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"]
    )
    fallback = TwinStepPrediction(
        summary=f"{step_name} simulated with default twin prediction",
        predicted_output={"simulated": True, "stepType": step_type, "status": "predicted"},
        confidence=fallback_confidence,
        risks=["insufficient context for high-confidence prediction"],
    )
    router = get_model_router()
    try:
        response = await router.complete(
            task_type=TaskType.WORKFLOW_PLANNING,
            prompt=prompt,
            system_prompt=(
                "You are a workflow digital twin. Predict plausible connector/agent step outcomes "
                "without executing anything. Output must be safe to show operators."
            ),
            response_format=TwinStepPrediction,
            org_id=org_id,
        )
        if response.parsed:
            parsed = TwinStepPrediction.model_validate(response.parsed)
            return annotate_confidence(
                {
                    "simulated": True,
                    "source": "llm_prediction",
                    "predicted": True,
                    "summary": parsed.summary,
                    "risks": parsed.risks,
                    "output": parsed.predicted_output,
                },
                is_estimate=True,
                source=CONFIDENCE_SOURCE_MODEL,
                value=parsed.confidence,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("twin llm prediction fallback step=%s error=%s", step_type, str(exc))
    return annotate_confidence(
        {
            "simulated": True,
            "source": "llm_prediction",
            "predicted": True,
            "summary": fallback.summary,
            "risks": fallback.risks,
            "output": fallback.predicted_output,
        },
        is_estimate=True,
        source=CONFIDENCE_SOURCE_HEURISTIC,
        value=fallback.confidence,
    )
