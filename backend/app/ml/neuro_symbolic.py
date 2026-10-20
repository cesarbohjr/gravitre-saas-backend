"""Symbolic constraint evaluation for the existing neural response pipeline.

No alternate LLM or action executor: decisions are advisory constraints consumed
by IntelligenceRouter alongside its existing contextual/sentiment enrichment.
"""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


class NeuroSymbolicReasoningEngine(CatalogScaffoldModel):
    model_type = ModelType.CLASSIFIER
    catalog_status = ModelStatus.READY
    catalog_name = "neuro_symbolic"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        facts, rules = kwargs.get("facts"), kwargs.get("rules")
        if not isinstance(facts, dict) or not isinstance(rules, list):
            return {"status": "dormant", "model": self.catalog_name,
                    "reason": "trusted_facts_and_rules_required", "advisory_only": True}
        matches = []
        for rule in rules[:100]:
            if not isinstance(rule, dict):
                continue
            key, operator, expected = rule.get("field"), rule.get("operator"), rule.get("value")
            if not isinstance(key, str) or key not in facts:
                continue
            actual = facts[key]
            matched = False
            if operator == "eq":
                matched = type(actual) is type(expected) and actual == expected
            elif operator == "in" and isinstance(expected, list):
                matched = any(type(actual) is type(value) and actual == value for value in expected)
            elif operator in {"gt", "gte", "lt", "lte"}:
                import math
                if type(actual) in {int, float} and type(expected) in {int, float}:
                    if math.isfinite(actual) and math.isfinite(expected):
                        matched = {"gt": actual > expected, "gte": actual >= expected,
                                   "lt": actual < expected, "lte": actual <= expected}[operator]
            if matched and isinstance(rule.get("id"), str):
                matches.append({"rule_id": rule["id"], "effect": rule.get("effect", "review")})
        return {"status": "ok", "model": self.catalog_name, "matches": matches,
                "method": "structured_constraint_evaluation", "advisory_only": True,
                "note": "Constraints supplement the existing neural pipeline; they never authorize execution."}
