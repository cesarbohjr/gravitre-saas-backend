"""Department specialist reasoning — persona, KPIs, and domain modifiers."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.operators.agent_prompts import DEPARTMENT_PERSONA_METADATA

DEPARTMENT_KPIS: dict[str, list[str]] = {
    "marketing": ["CAC", "ROAS", "pipeline contribution", "campaign velocity"],
    "sales": ["win rate", "pipeline coverage", "deal velocity", "forecast accuracy"],
    "support": ["CSAT", "first response time", "resolution rate", "ticket backlog"],
    "operations": ["throughput", "SLA adherence", "automation rate", "incident volume"],
    "finance": ["cash runway", "margin", "DSO", "budget variance"],
    "hr": ["time-to-hire", "retention", "engagement score", "headcount plan"],
    "engineering": ["deployment frequency", "incident MTTR", "PR cycle time", "defect escape rate"],
}


class SpecialistReasoningEngine:
    """Applies department-specific reasoning constraints to assistant turns."""

    def __init__(self, settings: Settings | None = None) -> None:
        _ = settings or get_settings()

    def resolve_department(self, agent: dict[str, Any], classification: dict[str, Any]) -> str:
        dept = str(agent.get("department") or classification.get("department") or "").lower()
        if dept:
            return dept.replace("_agent", "").replace("_", " ").split()[0]
        name = str(agent.get("name") or "").lower()
        for agent_key in DEPARTMENT_PERSONA_METADATA:
            token = agent_key.replace("_agent", "")
            if token in name or token in str(classification.get("intent") or ""):
                return token
        return "operations"

    def build_modifier(
        self,
        agent: dict[str, Any],
        classification: dict[str, Any],
        *,
        business_signals: list[dict[str, Any]] | None = None,
    ) -> str:
        department = self.resolve_department(agent, classification)
        persona_meta = self._persona_for_department(department)
        kpis = DEPARTMENT_KPIS.get(department, DEPARTMENT_KPIS["operations"])
        lines = [
            f"You are operating as a {persona_meta.get('role') or department.title() + ' specialist'}.",
            f"Prioritize KPIs: {', '.join(kpis)}.",
            "Ground recommendations in measurable business impact and cite evidence when available.",
        ]
        capabilities = persona_meta.get("capabilities") or []
        if capabilities:
            lines.append(f"Focus capabilities: {', '.join(str(item) for item in capabilities[:6])}.")
        if business_signals:
            signal_titles = [row.get("title") for row in business_signals[:3] if row.get("title")]
            if signal_titles:
                lines.append(f"Active business signals to weigh: {'; '.join(signal_titles)}.")
        return "\n".join(lines)

    def enrich_classification(
        self,
        classification: dict[str, Any],
        agent: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(classification)
        enriched["department"] = self.resolve_department(agent, classification)
        enriched["specialist_persona"] = self._persona_for_department(enriched["department"]).get("persona_key")
        return enriched

    @staticmethod
    def _persona_for_department(department: str) -> dict[str, Any]:
        key = f"{department.lower()}_agent"
        if key in DEPARTMENT_PERSONA_METADATA:
            return DEPARTMENT_PERSONA_METADATA[key]
        for agent_key, meta in DEPARTMENT_PERSONA_METADATA.items():
            if agent_key.replace("_agent", "") == department.lower():
                return meta
        return DEPARTMENT_PERSONA_METADATA.get("operations_agent", {})


_engine: SpecialistReasoningEngine | None = None


def get_specialist_reasoning_engine(settings: Settings | None = None) -> SpecialistReasoningEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = SpecialistReasoningEngine(settings)
    return _engine
