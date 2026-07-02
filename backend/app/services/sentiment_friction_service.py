"""Rule-based sentiment and friction detection for dialogue adaptation."""
from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

FRUSTRATION_PHRASES = (
    "not working",
    "doesn't work",
    "doesnt work",
    "still not",
    "again",
    "still wrong",
    "forget it",
    "never mind",
    "this is broken",
)
URGENCY_PHRASES = ("urgent", "asap", "immediately", "right now", "today")
UNCERTAINTY_PHRASES = ("not sure", "maybe", "i think", "i'm confused", "dont understand", "don't understand")


class SentimentFrictionService:
    """
    Detects user emotional state from conversation context.
    Rule-based fast path only — never changes facts or governance.
    """

    def analyze(
        self,
        message: str,
        conversation_history: list[dict] | None = None,
    ) -> dict[str, Any]:
        signals: list[str] = []
        frustration = 0.0
        uncertainty = 0.0
        urgency = 0.0
        text = (message or "").strip()
        lowered = text.lower()
        history = conversation_history or []

        if text == text.upper() and len(text) > 10 and re.search(r"[A-Z]", text):
            signals.append("all_caps")
            frustration += 0.3
        if any(phrase in lowered for phrase in FRUSTRATION_PHRASES):
            signals.append("frustration_phrase")
            frustration += 0.4
        if self._is_repeated_question(text, history):
            signals.append("repeated_question")
            frustration += 0.3
        if any(phrase in lowered for phrase in URGENCY_PHRASES):
            signals.append("urgency_phrase")
            urgency += 0.5
        if any(phrase in lowered for phrase in UNCERTAINTY_PHRASES):
            signals.append("uncertainty_phrase")
            uncertainty += 0.4

        frustration = min(frustration, 1.0)
        uncertainty = min(uncertainty, 1.0)
        urgency = min(urgency, 1.0)
        health = max(0.0, 1.0 - frustration * 0.6 - uncertainty * 0.2)

        return {
            "frustration_score": round(frustration, 3),
            "uncertainty_score": round(uncertainty, 3),
            "urgency_score": round(urgency, 3),
            "conversation_health": round(health, 3),
            "signals": signals,
            "recommended_adaptation": self._select_adaptation(frustration, uncertainty, urgency),
        }

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().strip())

    def _is_repeated_question(self, message: str, history: list[dict]) -> bool:
        normalized = self._normalize_for_compare(message)
        if len(normalized) < 12:
            return False
        user_messages = [
            self._normalize_for_compare(str(row.get("content") or ""))
            for row in reversed(history)
            if row.get("role") == "user"
        ][:3]
        return normalized in user_messages

    @staticmethod
    def _select_adaptation(frustration: float, uncertainty: float, urgency: float) -> str:
        if frustration >= 0.6:
            return "acknowledge_briefly"
        if uncertainty >= 0.5:
            return "offer_options"
        if urgency >= 0.5:
            return "reduce_verbosity"
        return "none"


_sentiment_friction_service: SentimentFrictionService | None = None


def get_sentiment_friction_service() -> SentimentFrictionService:
    global _sentiment_friction_service
    if _sentiment_friction_service is None:
        _sentiment_friction_service = SentimentFrictionService()
    return _sentiment_friction_service
