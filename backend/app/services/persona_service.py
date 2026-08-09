"""Department domain-focus overlays — distinct from capability-based AGENT_PERSONAS.

Module D: product Voice is owned by gravitre_voice. These personas only choose
what to emphasize (pipeline vs campaigns). They must not redefine tone, humor,
or formality — base Voice always wins.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.chat_dialogue_settings import load_chat_dialogue_settings
from app.services.conversation_state_service import get_conversation_state_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class PersonaService:
    """
    Domain-focus overlays for department context.
    Never overrides Voice, safety, approval, confidence, or governance.
    """

    COMMUNICATION_PERSONAS: dict[str, dict[str, Any]] = {
        "executive_strategist": {
            "tone": "authoritative",
            "verbosity": "concise",
            "formality": "high",
            "data_forward": True,
            "question_style": "strategic",
            "humor": "none",
            "default_for_departments": ["executive"],
            "label": "Executive Strategist",
            "system_prompt_modifier": (
                "Emphasize business outcomes, metrics, and strategic trade-offs. "
                "Prefer insight over process detail. Keep answers short unless depth is requested."
            ),
        },
        "marketing_operator": {
            "tone": "energetic",
            "verbosity": "moderate",
            "formality": "medium",
            "data_forward": True,
            "question_style": "goal-oriented",
            "humor": "light",
            "default_for_departments": ["marketing"],
            "label": "Marketing Operator",
            "system_prompt_modifier": (
                "Emphasize campaign performance, audience, and creative outcomes."
            ),
        },
        "sales_advisor": {
            "tone": "confident",
            "verbosity": "moderate",
            "formality": "medium",
            "data_forward": True,
            "question_style": "discovery",
            "humor": "light",
            "default_for_departments": ["sales"],
            "label": "Sales Advisor",
            "system_prompt_modifier": (
                "Emphasize pipeline, conversion, and customer relationships. "
                "Surface opportunities and risks."
            ),
        },
        "operations_analyst": {
            "tone": "precise",
            "verbosity": "detailed",
            "formality": "medium",
            "data_forward": True,
            "question_style": "diagnostic",
            "humor": "none",
            "default_for_departments": ["operations"],
            "label": "Operations Analyst",
            "system_prompt_modifier": (
                "Emphasize efficiency, bottlenecks, and process improvement."
            ),
        },
        "support_specialist": {
            "tone": "empathetic",
            "verbosity": "clear",
            "formality": "low",
            "data_forward": False,
            "question_style": "resolution-focused",
            "humor": "none",
            "default_for_departments": ["support"],
            "label": "Support Specialist",
            "system_prompt_modifier": (
                "Emphasize resolution steps and customer impact."
            ),
        },
        "finance_analyst": {
            "tone": "measured",
            "verbosity": "detailed",
            "formality": "high",
            "data_forward": True,
            "question_style": "risk-aware",
            "humor": "none",
            "default_for_departments": ["finance"],
            "label": "Finance Analyst",
            "system_prompt_modifier": (
                "Emphasize financial metrics, risk, and numeric precision."
            ),
        },
        "hr_advisor": {
            "tone": "supportive",
            "verbosity": "clear",
            "formality": "medium",
            "data_forward": False,
            "question_style": "people-focused",
            "humor": "light",
            "default_for_departments": ["hr"],
            "label": "HR Advisor",
            "system_prompt_modifier": (
                "Emphasize people, culture, and compliance considerations."
            ),
        },
        "engineering_copilot": {
            "tone": "direct",
            "verbosity": "technical",
            "formality": "low",
            "data_forward": True,
            "question_style": "technical",
            "humor": "dry",
            "default_for_departments": ["engineering"],
            "label": "Engineering Copilot",
            "system_prompt_modifier": (
                "Emphasize technical accuracy and precise terminology. "
                "Prefer concrete examples when explaining systems."
            ),
        },
        "friendly_assistant": {
            "tone": "warm",
            "verbosity": "adaptive",
            "formality": "low",
            "data_forward": False,
            "question_style": "open",
            "humor": "light",
            "default_for_departments": ["general"],
            "label": "Friendly Assistant",
            "system_prompt_modifier": (
                "Match the user's level of detail. Prefer plain language over jargon."
            ),
        },
        "deep_research_analyst": {
            "tone": "thorough",
            "verbosity": "comprehensive",
            "formality": "medium",
            "data_forward": True,
            "question_style": "investigative",
            "humor": "none",
            "default_for_departments": [],
            "label": "Deep Research Analyst",
            "system_prompt_modifier": (
                "Emphasize multiple angles, explicit assumptions, and cited sources."
            ),
        },
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def get_persona_for_request(
        self,
        org_id: str,
        user_id: str,
        department: str | None,
        conversation_id: str | None,
        explicit_persona: str | None = None,
    ) -> dict[str, Any]:
        key = (explicit_persona or "").strip()
        if not key and conversation_id:
            state = await get_conversation_state_service(self.settings).get_task_state(
                conversation_id, org_id
            )
            override = state.get("persona_override")
            if isinstance(override, str) and override.strip():
                key = override.strip()

        if not key:
            key = await self._load_user_preference(user_id)

        dialogue = await load_chat_dialogue_settings(org_id, self.settings)
        org_default = str(dialogue.get("default_persona") or "friendly_assistant")

        if not key:
            key = org_default

        if not key or key not in self.COMMUNICATION_PERSONAS:
            if department:
                key = self._department_default(department) or org_default
            else:
                key = org_default

        persona_source = (
            self.COMMUNICATION_PERSONAS[key]
            if key in self.COMMUNICATION_PERSONAS
            else self.COMMUNICATION_PERSONAS["friendly_assistant"]
        )
        persona = dict(persona_source)
        persona["persona_key"] = key if key in self.COMMUNICATION_PERSONAS else "friendly_assistant"
        return persona

    async def _load_user_preference(self, user_id: str) -> str | None:
        if not user_id:
            return None
        try:
            rows = (
                get_supabase_client(self.settings)
                .table("user_preferences")
                .select("preferred_persona")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                pref = rows[0].get("preferred_persona")
                return str(pref).strip() if pref else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("load user preferred_persona skipped user_id=%s error=%s", user_id, exc)
        return None

    def _department_default(self, department: str) -> str | None:
        dept = department.lower().strip()
        for key, persona in self.COMMUNICATION_PERSONAS.items():
            defaults = persona.get("default_for_departments") or []
            if dept in defaults:
                return key
        return None

    def get_persona_modifier_for_prompt(self, persona_key: str) -> str:
        persona = self.COMMUNICATION_PERSONAS.get(
            persona_key,
            self.COMMUNICATION_PERSONAS["friendly_assistant"],
        )
        return str(persona.get("system_prompt_modifier") or "")

    def list_personas(self, org_default: str | None = None) -> list[dict[str, Any]]:
        default_key = org_default or "friendly_assistant"
        catalog = []
        for key, persona in self.COMMUNICATION_PERSONAS.items():
            catalog.append(
                {
                    "persona_key": key,
                    "label": persona.get("label") or key.replace("_", " ").title(),
                    "tone": persona.get("tone"),
                    "verbosity": persona.get("verbosity"),
                    "formality": persona.get("formality"),
                    "is_org_default": key == default_key,
                }
            )
        return catalog


_persona_service: PersonaService | None = None


def get_persona_service(settings: Settings | None = None) -> PersonaService:
    global _persona_service
    if _persona_service is None or settings is not None:
        _persona_service = PersonaService(settings)
    return _persona_service
