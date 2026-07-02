"""Explicit dialogue mode selection from all available signals."""
from __future__ import annotations

from typing import Any

from app.services.clarification_engine import ClarificationEngine


class DialoguePolicyEngine:
    """
    Single source of truth for what Gravitre should do next in conversation.
    """

    DIALOGUE_MODES = [
        "answer",
        "clarify",
        "confirm",
        "guide",
        "recommend",
        "execute",
        "simulate",
        "research",
        "escalate",
        "summarize",
    ]

    def __init__(
        self,
        clarification_threshold: float = ClarificationEngine.CLARIFICATION_THRESHOLD,
        escalation_threshold: float = ClarificationEngine.ESCALATION_THRESHOLD,
    ) -> None:
        self.clarification_threshold = clarification_threshold
        self.escalation_threshold = escalation_threshold

    def select_mode(
        self,
        classification: dict[str, Any],
        clarification_result: dict[str, Any],
        sentiment: dict[str, Any],
        risk_evaluation: dict[str, Any],
        confidence: float,
        conversation_history: list[dict] | None,
    ) -> dict[str, Any]:
        _ = sentiment, conversation_history

        if clarification_result.get("should_clarify"):
            return {
                "mode": "clarify",
                "reason": clarification_result.get("reason") or "Clarification needed.",
                "next_move": clarification_result.get("question") or "Ask clarifying question.",
                "approval_required": False,
            }

        if risk_evaluation.get("requires_approval") and not risk_evaluation.get(
            "can_proceed_without_approval"
        ):
            return {
                "mode": "confirm",
                "reason": risk_evaluation.get("approval_reason")
                or risk_evaluation.get("reason")
                or "Approval required before action.",
                "next_move": "Present action plan and request approval.",
                "approval_required": True,
            }

        if confidence < self.escalation_threshold:
            return {
                "mode": "escalate",
                "reason": f"Confidence {confidence:.0%} is below threshold.",
                "next_move": "Route to human review or retrieve more context.",
                "approval_required": False,
            }

        needs_research = confidence < self.clarification_threshold and (
            classification.get("requires_prediction") or classification.get("requires_causal")
        )
        if needs_research:
            return {
                "mode": "research",
                "reason": "More context needed before confident response.",
                "next_move": "Retrieve additional sources.",
                "approval_required": False,
            }

        if classification.get("intent") in {
            "workflow_planning",
            "document_generation",
            "marketing_task",
            "sales_task",
            "workflow_execution",
        } and not classification.get("requires_action"):
            return {
                "mode": "guide",
                "reason": "Multi-step task requiring structured plan.",
                "next_move": "Decompose into steps and confirm approach.",
                "approval_required": False,
            }

        if classification.get("requires_action"):
            if risk_evaluation.get("simulation_available"):
                return {
                    "mode": "simulate",
                    "reason": "Reversible action with simulation data available.",
                    "next_move": "Run simulation before execution.",
                    "approval_required": True,
                }
            return {
                "mode": "execute",
                "reason": "Action approved and ready.",
                "next_move": "Execute via ToolRegistry with approval gate.",
                "approval_required": True,
            }

        if classification.get("intent") in {"data_analysis", "analytics"}:
            return {
                "mode": "recommend",
                "reason": "Analytical task — suggest options with evidence.",
                "next_move": "Present recommendations with trade-offs.",
                "approval_required": False,
            }

        return {
            "mode": "answer",
            "reason": "Clear question, sufficient context, high confidence.",
            "next_move": "Generate direct response.",
            "approval_required": False,
        }


_dialogue_policy_engine: DialoguePolicyEngine | None = None


def get_dialogue_policy_engine(
    *,
    clarification_threshold: float = ClarificationEngine.CLARIFICATION_THRESHOLD,
    escalation_threshold: float = ClarificationEngine.ESCALATION_THRESHOLD,
) -> DialoguePolicyEngine:
    return DialoguePolicyEngine(
        clarification_threshold=clarification_threshold,
        escalation_threshold=escalation_threshold,
    )
