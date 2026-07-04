"""Pre-classification entity, goal, and format extraction."""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CONNECTOR_ALIASES: dict[str, str] = {
    "hubspot": "hubspot",
    "salesforce": "salesforce",
    "slack": "slack",
    "notion": "notion",
    "stripe": "stripe",
    "zendesk": "zendesk",
    "github": "github",
    "microsoft 365": "microsoft365",
    "microsoft365": "microsoft365",
    "google analytics": "google_analytics",
}

OUTPUT_FORMAT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("report", re.compile(r"\b(report|analysis report)\b", re.I)),
    ("plan", re.compile(r"\b(plan|roadmap|step.by.step)\b", re.I)),
    ("summary", re.compile(r"\b(summary|summarize|recap)\b", re.I)),
    ("data", re.compile(r"\b(table|csv|spreadsheet|metrics|numbers)\b", re.I)),
    ("action", re.compile(r"\b(run|execute|trigger|send|update|delete)\b", re.I)),
]

CONVERSATIONAL_CREATE_PATTERN = re.compile(
    r"\b(create|build|make|set up|spin up|provision|add|generate|draft)\b.*\b(agent|workflow|automation|playbook|operator)\b",
    re.I,
)

DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": ("revenue", "budget", "invoice", "mrr", "arr", "forecast"),
    "sales": ("pipeline", "deal", "prospect", "crm", "quota"),
    "marketing": ("campaign", "audience", "ads", "content", "seo"),
    "engineering": ("deploy", "bug", "api", "code", "incident"),
    "support": ("ticket", "customer", "escalation", "sla"),
    "hr": ("hiring", "employee", "onboarding", "payroll"),
    "operations": ("workflow", "process", "efficiency", "bottleneck"),
}


class ContextualUnderstandingService:
    """Fast structured understanding before TaskClassifier runs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def understand(
        self,
        message: str,
        conversation_history: list[dict] | None,
        org_id: str,
    ) -> dict[str, Any]:
        entities = self._extract_entities_rule_based(message)
        temporal = self._extract_temporal(message)
        format_hint = self._detect_output_format(message, self._is_conversational_create(message))
        connectors = self._detect_connector_refs(message)
        known = self._extract_from_history(message, conversation_history or [])

        goal = self._infer_goal_from_rules(message)
        constraints: list[str] = []
        conversational_create = self._is_conversational_create(message)
        if not goal and len(message.split()) > 8:
            extracted = await self._model_extract(message, entities, temporal)
            goal = extracted.get("goal")
            constraints = extracted.get("constraints") or []

        department_inference = self._infer_department(entities, message)
        partial = {
            "entities": entities,
            "goal": goal,
            "constraints": constraints,
            "temporal_references": temporal,
            "expected_output_format": format_hint,
            "conversational_create": conversational_create,
            "department_inference": department_inference,
            "connector_dependencies": connectors,
            "already_known_from_history": known,
        }
        from app.services.domain_intelligence_service import get_domain_intelligence_service

        domain = await get_domain_intelligence_service(self.settings).classify(
            org_id,
            message,
            conversation_history,
            understanding=partial,
        )
        if domain.get("department_key") and not department_inference:
            department_inference = domain.get("department_key")

        return {
            **partial,
            "expected_output_format": self._detect_output_format(message, conversational_create),
            "department_inference": department_inference,
            "domain": domain,
        }

    def _extract_entities_rule_based(self, message: str) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        lowered = message.lower()
        if "workflow" in lowered:
            entities.append({"type": "workflow", "name": "workflow", "confidence": 0.7})
        if re.search(r"\bagent\b", lowered):
            entities.append({"type": "agent", "name": "agent", "confidence": 0.7})
        if re.search(r"\bconnector\b", lowered):
            entities.append({"type": "connector", "name": "connector", "confidence": 0.65})
        quoted = re.findall(r'"([^"]{2,80})"|\'([^\']{2,80})\'', message)
        for pair in quoted[:3]:
            name = pair[0] or pair[1]
            if name:
                entities.append({"type": "named_entity", "name": name, "confidence": 0.8})
        return entities

    @staticmethod
    def _extract_temporal(message: str) -> list[str]:
        refs: list[str] = []
        for pattern in (
            r"\btoday\b",
            r"\byesterday\b",
            r"\blast (week|month|quarter|year)\b",
            r"\bnext (week|month|quarter|year)\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
        ):
            for match in re.finditer(pattern, message, re.I):
                refs.append(match.group(0))
        return refs[:5]

    @staticmethod
    def _is_conversational_create(message: str) -> bool:
        return bool(CONVERSATIONAL_CREATE_PATTERN.search(message))

    @staticmethod
    def _detect_output_format(message: str, conversational_create: bool = False) -> str | None:
        if conversational_create:
            return "plan"
        for label, pattern in OUTPUT_FORMAT_PATTERNS:
            if pattern.search(message):
                return label
        if message.strip().endswith("?"):
            return "question_answer"
        return None

    @staticmethod
    def _detect_connector_refs(message: str) -> list[str]:
        lowered = message.lower()
        found: list[str] = []
        for alias, connector_id in CONNECTOR_ALIASES.items():
            if alias in lowered and connector_id not in found:
                found.append(connector_id)
        return found

    @staticmethod
    def _extract_from_history(message: str, history: list[dict]) -> dict[str, Any]:
        known: dict[str, Any] = {}
        lowered = message.lower()
        for row in reversed(history[-6:]):
            if row.get("role") != "assistant":
                continue
            content = str(row.get("content") or "")
            if "workflow" in content.lower() and "workflow" in lowered:
                known["workflow_context"] = True
            if "connector" in content.lower() and "connector" in lowered:
                known["connector_context"] = True
        return known

    @staticmethod
    def _can_infer_goal_from_rules(message: str) -> bool:
        text = message.strip()
        if not text:
            return False
        if text.endswith("?"):
            return True
        return len(text.split()) <= 12

    def _infer_goal_from_rules(self, message: str) -> str | None:
        text = message.strip()
        if not text:
            return None
        if self._can_infer_goal_from_rules(message):
            return text.rstrip("?").strip()
        return None

    async def _model_extract(
        self,
        message: str,
        entities: list[dict[str, Any]],
        temporal: list[str],
    ) -> dict[str, Any]:
        try:
            from app.services.model_router import TaskType, get_model_router

            prompt = (
                "Extract goal and constraints from the user message. "
                'Return JSON only: {"goal": "...", "constraints": ["..."]}\n\n'
                f"Message: {message}\nEntities: {entities}\nTemporal: {temporal}"
            )
            response = await get_model_router(self.settings).complete(
                task_type=TaskType.CLASSIFICATION,
                prompt=prompt,
                system_prompt="Extract structured understanding. JSON only.",
                org_id=None,
                temperature=0.0,
                max_tokens=200,
            )
            import json

            clean = (response.content or "").strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:  # noqa: BLE001
            logger.debug("contextual model extract skipped: %s", exc)
        return {}

    @staticmethod
    def _infer_department(entities: list[dict[str, Any]], message: str) -> str | None:
        _ = entities
        lowered = message.lower()
        for dept, keywords in DEPARTMENT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return dept
        return None


_contextual_understanding_service: ContextualUnderstandingService | None = None


def get_contextual_understanding_service(settings: Settings | None = None) -> ContextualUnderstandingService:
    global _contextual_understanding_service
    if _contextual_understanding_service is None or settings is not None:
        _contextual_understanding_service = ContextualUnderstandingService(settings)
    return _contextual_understanding_service
