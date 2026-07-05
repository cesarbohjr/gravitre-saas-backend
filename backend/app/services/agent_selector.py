"""Agent persona selection with connector availability validation."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.operators.agent_prompts import (
    AGENT_PERSONAS,
    DEPARTMENT_PERSONA_METADATA,
    infer_task_persona_key,
)
from app.workflows.repository import get_supabase_client
from app.services.domain_routing_policy import apply_agent_selection_policy
from app.services.learning_strategy_keys import parse_segment_key

SWARM_ELIGIBLE_TASKS = frozenset(
    {
        "workflow_execution",
        "document_generation",
        "marketing_task",
        "sales_task",
        "data_analysis",
    }
)


class AgentSelector:
    """Selects persona(s) for a classified task; validates org connectors."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def select(self, org_id: str, classification: dict[str, Any]) -> dict[str, Any]:
        department = classification.get("department")
        task_type = str(classification.get("intent") or "")
        requires_action = bool(classification.get("requires_action"))
        persona_key = infer_task_persona_key(f"{department or ''} {task_type}")
        persona_meta = DEPARTMENT_PERSONA_METADATA.get(
            f"{department}_agent" if department else "",
            {},
        )
        persona = AGENT_PERSONAS.get(persona_key, AGENT_PERSONAS["DEFAULT"])
        required = list(persona_meta.get("preferred_connectors") or persona.preferred_tools)
        available = await self._get_connected(org_id)
        missing = [connector for connector in required if connector not in available]
        result = {
            "persona_key": persona_key,
            "persona": {
                "key": persona.key,
                "display_name": persona.display_name,
                "preferred_connectors": list(persona.preferred_tools),
                "requires_approval_for": list(persona_meta.get("requires_approval_for") or []),
                "advisory_only": bool(persona_meta.get("advisory_only", False)),
                "role": persona_meta.get("role") or persona.display_name,
            },
            "missing_connectors": missing,
            "requires_swarm": requires_action and task_type in SWARM_ELIGIBLE_TASKS,
        }
        routed = apply_agent_selection_policy(result, classification)
        from app.services.meta_learning_service import get_meta_learning_service

        meta = get_meta_learning_service(self.settings)
        if meta.is_enabled():
            segment_key = parse_segment_key(classification)
            candidates = [
                meta.build_agent_strategy_key(key)
                for key in AGENT_PERSONAS.keys()
                if key != "DEFAULT"
            ]
            guidance = await meta.get_selection_guidance(
                org_id,
                segment_key,
                "agent",
                candidates,
                default_key=meta.build_agent_strategy_key(str(routed.get("persona_key") or persona_key)),
                classification=classification,
            )
            routed = meta.apply_agent_soft_prior(routed, guidance)
        return routed

    async def _get_connected(self, org_id: str) -> set[str]:
        client = get_supabase_client(self.settings)
        rows = (
            client.table("connectors")
            .select("provider, status")
            .eq("org_id", org_id)
            .eq("status", "connected")
            .execute()
            .data
            or []
        )
        connected = {str(row.get("provider") or "").lower() for row in rows if row.get("provider")}
        connected.add("platform")
        return connected


_agent_selector: AgentSelector | None = None


def get_agent_selector(settings: Settings | None = None) -> AgentSelector:
    global _agent_selector
    if _agent_selector is None or settings is not None:
        _agent_selector = AgentSelector(settings)
    return _agent_selector
