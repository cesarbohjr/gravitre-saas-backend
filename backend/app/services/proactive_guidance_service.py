"""In-conversation next-step suggestions — distinct from workflow-level optimization."""
from __future__ import annotations

import hashlib
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.chat_dialogue_settings import load_chat_dialogue_settings
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_SIGNAL_HEURISTIC,
    label_confidence,
)
from app.services.conversation_state_service import get_conversation_state_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class ProactiveGuidanceService:
    """Contextual conversational guidance with suppression rules."""

    MAX_SUGGESTIONS_PER_RESPONSE = 2

    SUGGESTION_TYPES = {
        "missing_connector": {
            "condition": "task requires connector not connected",
            "template": "Connecting {connector} would let me {benefit}.",
            "suppression_key": "missing_connector_{connector}",
        },
        "simulation_available": {
            "condition": "action is reversible and data exists",
            "template": "Want me to simulate the impact before we proceed?",
            "suppression_key": "simulation_available",
        },
        "relevant_template": {
            "condition": "marketplace template matches task",
            "template": "There's a {template_name} template that could accelerate this.",
            "suppression_key": "template_{template_id}",
        },
        "automation_opportunity": {
            "condition": "task is manual and could be automated",
            "template": "This looks like something you do regularly — want me to build a workflow for it?",
            "suppression_key": "automation_{task_type}",
        },
        "next_step": {
            "condition": "obvious follow-up after task completion",
            "template": "{next_step_description}",
            "suppression_key": "next_step_{context_hash}",
        },
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)

    async def get_suggestions(
        self,
        org_id: str,
        user_id: str,
        conversation_id: str | None,
        classification: dict[str, Any],
        dialogue_mode: str,
        response_content: str,
        *,
        connected_integrations: list[str] | None = None,
        business_signals: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if dialogue_mode in ("clarify", "execute", "confirm", "escalate"):
            return []

        dialogue = await load_chat_dialogue_settings(org_id, self.settings)
        if not dialogue.get("proactive_suggestions_enabled", True):
            return []

        max_items = int(dialogue.get("max_suggestions_per_response") or self.MAX_SUGGESTIONS_PER_RESPONSE)
        suppressed = await self._load_suppressed(user_id, org_id, conversation_id)
        candidates: list[dict[str, Any]] = []

        for suggestion_type, config in self.SUGGESTION_TYPES.items():
            rendered = await self._condition_met(
                suggestion_type,
                org_id,
                classification,
                response_content,
                connected_integrations=connected_integrations or [],
            )
            if not rendered:
                continue
            vars_ = rendered.get("vars") or {}
            try:
                key = config["suppression_key"].format(**vars_)
            except KeyError:
                key = f"{suggestion_type}_{hash(response_content[:80]) % 10000}"
            if key in suppressed:
                continue
            try:
                text = config["template"].format(**vars_)
            except KeyError:
                continue
            candidates.append(
                {
                    "type": suggestion_type,
                    "text": text,
                    "suppression_key": key,
                    **label_confidence(0.55, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
                }
            )

        for signal in (business_signals or [])[:3]:
            title = str(signal.get("title") or "")
            if not title:
                continue
            key = f"signal_{hashlib.sha256(title.lower().encode()).hexdigest()[:16]}"
            if key in suppressed:
                continue
            raw_conf = signal.get("quality_score") or signal.get("confidence")
            if raw_conf is not None:
                conf_meta = label_confidence(
                    float(raw_conf),
                    source=CONFIDENCE_SOURCE_SIGNAL_HEURISTIC,
                    is_estimate=True,
                )
            else:
                conf_meta = label_confidence(0.6, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True)
            candidates.append(
                {
                    "type": "business_signal",
                    "text": f"Signal: {title} — want me to dig in?",
                    "suppression_key": key,
                    **conf_meta,
                }
            )

        if candidates:
            from app.services.recommendation_quality_engine import get_recommendation_quality_engine

            ranked = await get_recommendation_quality_engine(self.settings).rank_recommendations(
                candidates,
                org_id=org_id,
                department=str(classification.get("department") or ""),
            )
            return ranked[:max_items]

        return candidates[:max_items]

    async def _load_suppressed(
        self,
        user_id: str,
        org_id: str,
        conversation_id: str | None,
    ) -> set[str]:
        suppressed: set[str] = set()
        if conversation_id:
            state = await self._state.get_task_state(conversation_id, org_id)
            for key in state.get("suppressed_suggestions") or []:
                suppressed.add(str(key))
            memory = state.get("conversation_memory")
            if isinstance(memory, dict):
                for row in memory.get("rejected_recommendations") or []:
                    text = str(row.get("text") or "")
                    if text:
                        suppressed.add(f"rejected_{hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]}")
        try:
            rows = (
                get_supabase_client(self.settings)
                .table("user_preferences")
                .select("personalized_suggestions")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                for item in rows[0].get("personalized_suggestions") or []:
                    if isinstance(item, dict) and item.get("suppressed"):
                        suppressed.add(str(item.get("key") or ""))
        except Exception as exc:  # noqa: BLE001
            logger.debug("load suppressed suggestions skipped: %s", exc)
        return {k for k in suppressed if k}

    async def _condition_met(
        self,
        suggestion_type: str,
        org_id: str,
        classification: dict[str, Any],
        response_content: str,
        *,
        connected_integrations: list[str],
    ) -> dict[str, Any] | None:
        connected = {str(c).lower() for c in connected_integrations}
        intent = str(classification.get("intent") or "")

        if suggestion_type == "missing_connector":
            for connector in ("hubspot", "salesforce", "slack", "stripe"):
                if connector in str(classification.get("request") or "").lower() and connector not in connected:
                    return {
                        "vars": {
                            "connector": connector.replace("_", " ").title(),
                            "benefit": f"pull live {connector} data",
                        }
                    }

        if suggestion_type == "simulation_available" and classification.get("requires_action"):
            if intent in {"workflow_execution", "data_analysis"}:
                return {"vars": {}}

        if suggestion_type == "automation_opportunity":
            request = str(classification.get("request") or "").lower()
            if any(token in request for token in ("every day", "daily", "regularly", "each week")):
                return {"vars": {"task_type": intent or "recurring"}}

        if suggestion_type == "next_step" and response_content.strip():
            digest = hashlib.sha256(response_content[:200].encode()).hexdigest()[:10]
            if "completed" in response_content.lower() or "done" in response_content.lower():
                return {
                    "vars": {
                        "next_step_description": "Want a summary of what we accomplished or suggested next actions?",
                        "context_hash": digest,
                    }
                }

        return None


_proactive_guidance_service: ProactiveGuidanceService | None = None


def get_proactive_guidance_service(settings: Settings | None = None) -> ProactiveGuidanceService:
    global _proactive_guidance_service
    if _proactive_guidance_service is None or settings is not None:
        _proactive_guidance_service = ProactiveGuidanceService(settings)
    return _proactive_guidance_service
