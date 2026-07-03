"""Shared reviewer personas for intelligence consensus paths."""
from __future__ import annotations

from typing import Any

REVIEWER_PERSONAS: dict[str, dict[str, Any]] = {
    "validator": {"label": "Validator", "weight": 1.0, "focus": "factual accuracy"},
    "planner": {"label": "Planner", "weight": 1.0, "focus": "execution feasibility"},
    "risk": {"label": "Risk Analyst", "weight": 1.1, "focus": "downside exposure"},
    "fact_checker": {"label": "Fact Checker", "weight": 1.2, "focus": "source verification"},
    "compliance_reviewer": {
        "label": "Compliance Reviewer",
        "weight": 1.15,
        "focus": "policy and approval alignment",
    },
    "devils_advocate": {
        "label": "Devil's Advocate",
        "weight": 0.9,
        "focus": "counterarguments and failure modes",
    },
}

CHAT_CONSENSUS_PERSONAS: tuple[str, ...] = ("validator", "fact_checker")
HIGH_STAKES_DEBATE_PERSONAS: tuple[str, ...] = (
    "validator",
    "planner",
    "risk",
    "compliance_reviewer",
    "devils_advocate",
)


def persona_vote_weights(persona_keys: list[str]) -> dict[str, float]:
    return {
        key: float(REVIEWER_PERSONAS.get(key, {}).get("weight") or 1.0)
        for key in persona_keys
    }


def build_agent_defs(persona_keys: list[str]) -> list[dict[str, Any]]:
    keys = persona_keys or list(CHAT_CONSENSUS_PERSONAS)
    return [
        {
            "name": str(REVIEWER_PERSONAS.get(key, {}).get("label") or key.title()),
            "role": key,
            "weight": float(REVIEWER_PERSONAS.get(key, {}).get("weight") or 1.0),
        }
        for key in keys
    ]
