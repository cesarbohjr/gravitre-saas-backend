from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.services.model_router import ModelRouter, TaskType, get_model_router
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class DecisionType(StrEnum):
    RULE_BASED = "rule_based"
    AI_ASSISTED = "ai_assisted"
    HYBRID = "hybrid"
    AUTONOMOUS = "autonomous"


class DecisionPath(BaseModel):
    id: str
    label: str
    description: str | None = None


class DecisionAIReasoning(BaseModel):
    selected_path_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str
    key_factors: list[str] = Field(default_factory=list)
    risks_identified: list[str] = Field(default_factory=list)
    alternatives_rejected: list[dict] = Field(default_factory=list)


class DecisionResult(BaseModel):
    id: str
    selected_path: DecisionPath
    confidence: float
    reasoning_summary: str
    key_factors: list[str]
    risks_identified: list[str]
    alternatives_rejected: list[dict]
    requires_human_approval: bool
    rule_matches: list[dict] | None
    ai_reasoning: dict | None


class DecisionService:
    def __init__(self, model_router: ModelRouter | None = None):
        self.model_router = model_router or get_model_router()

    async def evaluate(
        self,
        org_id: str,
        workflow_id: str,
        run_id: str,
        node_id: str,
        objective: str,
        input_data: dict,
        available_paths: list[DecisionPath],
        decision_type: DecisionType = DecisionType.HYBRID,
        rules: list[dict] | None = None,
        rag_context: str | None = None,
    ) -> DecisionResult:
        rule_matches = self._evaluate_rules(input_data, rules or [])
        rule_scores = self._score_paths_from_rules(rule_matches)

        ai_result: DecisionAIReasoning | None = None
        if decision_type in {DecisionType.AI_ASSISTED, DecisionType.HYBRID, DecisionType.AUTONOMOUS}:
            ai_result = await self._get_ai_reasoning(
                org_id=org_id,
                objective=objective,
                input_data=input_data,
                paths=available_paths,
                rag_context=rag_context,
            )

        selected, confidence = self._combine_decision(decision_type, available_paths, ai_result, rule_scores)
        requires_human = decision_type in {DecisionType.AI_ASSISTED, DecisionType.HYBRID} and confidence < 0.75
        if decision_type == DecisionType.AUTONOMOUS and confidence < 0.85:
            requires_human = True

        result = DecisionResult(
            id=f"{run_id}:{node_id}",
            selected_path=selected,
            confidence=round(confidence, 3),
            reasoning_summary=(
                ai_result.reasoning_summary if ai_result else f"Selected {selected.label} using matching rules."
            ),
            key_factors=ai_result.key_factors if ai_result else [m["field"] for m in rule_matches][:5],
            risks_identified=ai_result.risks_identified if ai_result else [],
            alternatives_rejected=ai_result.alternatives_rejected if ai_result else [],
            requires_human_approval=requires_human,
            rule_matches=rule_matches or None,
            ai_reasoning=ai_result.model_dump() if ai_result else None,
        )
        self._persist_decision(org_id, workflow_id, run_id, node_id, decision_type, result)
        return result

    async def _get_ai_reasoning(
        self,
        org_id: str,
        objective: str,
        input_data: dict,
        paths: list[DecisionPath],
        rag_context: str | None,
    ) -> DecisionAIReasoning:
        path_map = [{"id": p.id, "label": p.label, "description": p.description} for p in paths]
        prompt = (
            "You are a decision engine. Select the best path.\n"
            f"Objective: {objective}\n"
            f"Input data: {input_data}\n"
            f"Available paths: {path_map}\n"
            f"Additional context: {rag_context or 'none'}\n"
            "Return strict JSON following the schema."
        )
        response = await self.model_router.complete(
            task_type=TaskType.DECISION_REASONING,
            prompt=prompt,
            system_prompt="Be concise and auditable.",
            response_format=DecisionAIReasoning,
            org_id=org_id,
        )
        payload = response.parsed or {}
        return DecisionAIReasoning.model_validate(payload)

    def _combine_decision(
        self,
        decision_type: DecisionType,
        available_paths: list[DecisionPath],
        ai_result: DecisionAIReasoning | None,
        rule_scores: dict[str, float],
    ) -> tuple[DecisionPath, float]:
        if not available_paths:
            raise ValueError("available_paths must not be empty")
        path_index = {path.id: path for path in available_paths}

        if decision_type == DecisionType.RULE_BASED:
            selected_id = max(rule_scores, key=rule_scores.get, default=available_paths[0].id)
            return path_index.get(selected_id, available_paths[0]), min(1.0, max(rule_scores.values(), default=0.6))

        if ai_result and decision_type in {DecisionType.AI_ASSISTED, DecisionType.AUTONOMOUS}:
            return path_index.get(ai_result.selected_path_id, available_paths[0]), ai_result.confidence

        ai_score_map = {p.id: 0.0 for p in available_paths}
        ai_conf = 0.0
        if ai_result:
            ai_score_map[ai_result.selected_path_id] = ai_result.confidence
            ai_conf = ai_result.confidence
        combined = {pid: (rule_scores.get(pid, 0.0) * 0.4) + (ai_score_map.get(pid, 0.0) * 0.6) for pid in ai_score_map}
        selected_id = max(combined, key=combined.get, default=available_paths[0].id)
        return path_index.get(selected_id, available_paths[0]), max(combined.get(selected_id, 0.0), ai_conf * 0.6)

    def _evaluate_rules(self, input_data: dict, rules: list[dict]) -> list[dict]:
        matches: list[dict] = []
        for rule in rules:
            field = rule.get("field")
            operator = rule.get("operator")
            expected = rule.get("value")
            path_id = rule.get("path_id")
            actual = input_data.get(field)
            if self._match_operator(actual, operator, expected):
                matches.append({"field": field, "operator": operator, "value": expected, "path_id": path_id})
        return matches

    def _score_paths_from_rules(self, rule_matches: list[dict]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for match in rule_matches:
            path_id = str(match.get("path_id") or "")
            if not path_id:
                continue
            scores[path_id] = scores.get(path_id, 0.0) + 0.2
        return scores

    def _match_operator(self, actual: Any, operator: str, expected: Any) -> bool:
        if operator == "equals":
            return actual == expected
        if operator == "not_equals":
            return actual != expected
        if operator == "greater_than":
            return actual is not None and expected is not None and actual > expected
        if operator == "less_than":
            return actual is not None and expected is not None and actual < expected
        if operator == "greater_or_equal":
            return actual is not None and expected is not None and actual >= expected
        if operator == "less_or_equal":
            return actual is not None and expected is not None and actual <= expected
        if operator == "contains":
            return actual is not None and str(expected) in str(actual)
        if operator == "not_contains":
            return actual is None or str(expected) not in str(actual)
        if operator == "in":
            return actual in (expected or [])
        if operator == "not_in":
            return actual not in (expected or [])
        if operator == "is_null":
            return actual is None
        if operator == "is_not_null":
            return actual is not None
        if operator == "matches_regex":
            if actual is None:
                return False
            return bool(re.search(str(expected), str(actual)))
        return False

    def _persist_decision(
        self,
        org_id: str,
        workflow_id: str,
        run_id: str,
        node_id: str,
        decision_type: DecisionType,
        result: DecisionResult,
    ) -> None:
        try:
            settings = get_settings()
            client = get_supabase_client(settings)
            client.table("decisions").insert(
                {
                    "org_id": org_id,
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "decision_type": decision_type.value,
                    "selected_path": result.selected_path.id,
                    "confidence": result.confidence,
                    "reasoning_summary": result.reasoning_summary,
                    "key_factors": result.key_factors,
                    "risks_identified": result.risks_identified,
                    "alternatives_rejected": result.alternatives_rejected,
                    "requires_human_approval": result.requires_human_approval,
                    "rule_matches": result.rule_matches,
                    "ai_reasoning": result.ai_reasoning,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("decision persistence failed: %s", str(exc))


_decision_service_singleton: DecisionService | None = None


def get_decision_service() -> DecisionService:
    global _decision_service_singleton
    if _decision_service_singleton is None:
        _decision_service_singleton = DecisionService()
    return _decision_service_singleton
