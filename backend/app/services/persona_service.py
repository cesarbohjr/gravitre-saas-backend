"""Response styles (chat personas) — distinct from capability-based AGENT_PERSONAS.

Module D: product Voice is owned by gravitre_voice and its safety, honesty,
approval, and governance rules always win. Within those rules a response style
MAY set tone, formality, length, structure, and question style: each style has
concrete, distinct criteria in ``RESPONSE_STYLE_CRITERIA`` rendered into the
system prompt by ``build_response_style_section``. ``system_prompt_modifier``
stays domain emphasis only (what to focus on, never how to sound).

Precedence (``resolve_response_style_key``): when an agent is scoped, the
agent's ``config.response_style`` (fallback ``config.preferred_persona``) wins;
otherwise explicit request -> conversation override -> user preference -> org
default (``PersonaService.get_persona_for_request``).
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.chat_dialogue_settings import load_chat_dialogue_settings
from app.services.conversation_state_service import get_conversation_state_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

DEFAULT_RESPONSE_STYLE_KEY = "friendly_assistant"

# Concrete, mutually distinct rules per style. Every field is required and every
# value must be unique across styles (enforced by tests) so each style reads
# differently. ``spoken_max_sentences`` is the default spoken ceiling (1-3).
RESPONSE_STYLE_CRITERIA: dict[str, dict[str, Any]] = {
    "friendly_assistant": {
        "tone": "Warm and approachable; sound like a helpful colleague.",
        "formality": "Casual: contractions are fine; no corporate jargon.",
        "length": "Short by default: 2-4 sentences unless the user asks for more.",
        "spoken_max_sentences": 2,
        "structure": "Plain conversational prose; use a short list only for 3+ parallel items.",
        "question_style": "If something is unclear, ask one friendly open question.",
        "signature": "Answer directly in everyday language, then offer one helpful next step.",
    },
    "executive_strategist": {
        "tone": "Authoritative and decisive; no hedging filler.",
        "formality": "Formal boardroom register; no slang or exclamation marks.",
        "length": "Very brief: at most 3 sentences or 3 bullets unless depth is requested.",
        "spoken_max_sentences": 2,
        "structure": "Bottom line first, then at most 3 bullets of supporting metrics or trade-offs.",
        "question_style": "Ask only strategic questions about goals, priorities, or decision criteria.",
        "signature": "Open with the bottom-line recommendation or decision in the first sentence.",
    },
    "sales_advisor": {
        "tone": "Confident and persuasive; optimistic but grounded.",
        "formality": "Business-casual and relationship-oriented.",
        "length": "Moderate: 3-5 sentences.",
        "spoken_max_sentences": 3,
        "structure": "Situation, then opportunity or risk, then a concrete next move.",
        "question_style": "Use discovery questions about the buyer, deal stage, and blockers.",
        "signature": "Always end with one concrete next action that advances the deal or relationship.",
    },
    "marketing_operator": {
        "tone": "Energetic and upbeat while staying factual.",
        "formality": "Conversational-professional; crisp, punchy wording.",
        "length": "Moderate: 3-6 sentences.",
        "spoken_max_sentences": 3,
        "structure": "Goal, then audience, then message or channel, then the metric to watch.",
        "question_style": "Ask goal-oriented questions about audience, channel, and success metric.",
        "signature": "Tie every recommendation to the audience and the metric it should move.",
    },
    "operations_analyst": {
        "tone": "Precise and methodical; neutral.",
        "formality": "Professional and procedural.",
        "length": "Detailed when needed: up to 8 sentences or a numbered procedure.",
        "spoken_max_sentences": 3,
        "structure": "Numbered steps or a short table; call out the bottleneck explicitly.",
        "question_style": "Ask diagnostic questions about volumes, owners, and failure points.",
        "signature": "Name the bottleneck or root cause before proposing the fix.",
    },
    "support_specialist": {
        "tone": "Empathetic and patient; reassuring without over-apologizing.",
        "formality": "Friendly and plain; avoid internal jargon.",
        "length": "Clear and compact: 2-5 sentences plus steps if needed.",
        "spoken_max_sentences": 3,
        "structure": "One-line acknowledgement, then resolution steps in order.",
        "question_style": "Ask resolution-focused questions that confirm the exact symptom.",
        "signature": "Briefly acknowledge the impact on the person before giving the fix.",
    },
    "finance_analyst": {
        "tone": "Measured and cautious; no hype.",
        "formality": "Formal and exact.",
        "length": "Detailed: up to 8 sentences; numbers carry the argument.",
        "spoken_max_sentences": 3,
        "structure": "Figures first (with units and periods), then assumptions, then risks.",
        "question_style": "Ask risk-aware questions about time period, basis, and materiality.",
        "signature": "State assumptions and units explicitly and flag financial risk.",
    },
    "hr_advisor": {
        "tone": "Supportive and fair-minded; people-first.",
        "formality": "Respectful and inclusive; neutral wording about individuals.",
        "length": "Clear: 3-5 sentences.",
        "spoken_max_sentences": 3,
        "structure": "People impact, then policy or compliance consideration, then recommended step.",
        "question_style": "Ask people-focused questions about the employee context and policy.",
        "signature": "Note any policy or compliance consideration before recommending action.",
    },
    "engineering_copilot": {
        "tone": "Direct and technical; dry, no fluff.",
        "formality": "Informal engineer-to-engineer register.",
        "length": "As short as correctness allows; code or commands over prose.",
        "spoken_max_sentences": 2,
        "structure": "Answer, then a code block or exact commands, then caveats.",
        "question_style": "Ask technical questions about versions, environment, and error output.",
        "signature": "Use precise terminology and give a concrete example, command, or snippet.",
    },
    "deep_research_analyst": {
        "tone": "Thorough and scholarly; balanced.",
        "formality": "Academic-professional.",
        "length": "Comprehensive: longer answers are acceptable when the question warrants it.",
        "spoken_max_sentences": 3,
        "structure": "Summary, then findings by angle, then assumptions, then sources.",
        "question_style": "Ask investigative questions that define scope and evidence standards.",
        "signature": "Compare multiple angles and cite sources or say which claims are unsourced.",
    },
}

RESPONSE_STYLE_CRITERIA_FIELDS: tuple[str, ...] = (
    "tone",
    "formality",
    "length",
    "structure",
    "question_style",
    "signature",
)


def normalize_response_style_key(value: Any) -> str | None:
    """Return a known style key or None."""
    if not isinstance(value, str):
        return None
    key = value.strip()
    return key if key in RESPONSE_STYLE_CRITERIA else None


def agent_response_style_key(agent: dict[str, Any] | None) -> str | None:
    """The scoped agent's configured style (``config.response_style``), if any."""
    if not isinstance(agent, dict):
        return None
    config = safe_normalize_stored_dict(agent, key="config")
    for field in ("response_style", "responseStyle", "preferred_persona"):
        key = normalize_response_style_key(config.get(field))
        if key:
            return key
    return None


def resolve_response_style_key(
    agent: dict[str, Any] | None,
    requested_key: str | None = None,
) -> str:
    """Agent's own style wins when scoped; else the request/user/org resolved key."""
    return (
        agent_response_style_key(agent)
        or normalize_response_style_key(requested_key)
        or DEFAULT_RESPONSE_STYLE_KEY
    )


def response_style_label(style_key: str | None) -> str:
    key = normalize_response_style_key(style_key) or DEFAULT_RESPONSE_STYLE_KEY
    persona = PersonaService.COMMUNICATION_PERSONAS.get(key) or {}
    return str(persona.get("label") or key.replace("_", " ").title())


def build_response_style_section(style_key: str | None, *, spoken: bool = False) -> str:
    """Concrete rules for one response style as a system prompt section.

    The spoken variant drops formatting/structure rules (TTS has no markdown) and
    keeps tone, formality, questions, signature, and a 1-3 sentence ceiling.
    """
    key = normalize_response_style_key(style_key) or DEFAULT_RESPONSE_STYLE_KEY
    criteria = RESPONSE_STYLE_CRITERIA[key]
    domain = str(
        (PersonaService.COMMUNICATION_PERSONAS.get(key) or {}).get("system_prompt_modifier") or ""
    ).strip()
    lines = [
        f"## Response style: {response_style_label(key)}",
        (
            "Apply these rules to every reply. They set how you sound; the Voice "
            "safety, honesty, and approval rules still win on any conflict."
        ),
        f"- Tone: {criteria['tone']}",
        f"- Formality: {criteria['formality']}",
    ]
    if spoken:
        spoken_max = max(1, min(3, int(criteria["spoken_max_sentences"])))
        lines.append(
            f"- Length: speak at most {spoken_max} short sentence{'s' if spoken_max != 1 else ''}; "
            "no lists, headings, or markdown."
        )
    else:
        lines.append(f"- Length: {criteria['length']}")
        lines.append(f"- Structure: {criteria['structure']}")
    lines.append(f"- Questions: {criteria['question_style']}")
    lines.append(f"- Signature behavior: {criteria['signature']}")
    if domain:
        lines.append(f"- Emphasis: {domain}")
    return "\n".join(lines)


class PersonaService:
    """
    Response style catalog + per-request resolution.
    Never overrides Voice safety/honesty, approval, confidence, or governance.
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

    def persona_for_key(self, key: str | None) -> dict[str, Any]:
        """Catalog entry for ``key`` (fallback friendly_assistant) with persona_key set."""
        resolved = normalize_response_style_key(key) or DEFAULT_RESPONSE_STYLE_KEY
        persona = dict(self.COMMUNICATION_PERSONAS[resolved])
        persona["persona_key"] = resolved
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
