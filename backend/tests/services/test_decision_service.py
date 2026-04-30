from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.decision_service import DecisionAIReasoning, DecisionPath, DecisionService, DecisionType


class _DummyRouter:
    async def complete(self, *args, **kwargs):  # pragma: no cover - used when patched methods bypass model calls
        raise RuntimeError("not used")


@pytest.fixture
def service() -> DecisionService:
    return DecisionService(model_router=_DummyRouter())  # type: ignore[arg-type]


def test_rule_matching_multiple_operators(service: DecisionService):
    rules = [
        {"field": "score", "operator": "greater_or_equal", "value": 80, "path_id": "sales"},
        {"field": "country", "operator": "equals", "value": "US", "path_id": "sales"},
        {"field": "email", "operator": "matches_regex", "value": r".+@.+", "path_id": "sales"},
        {"field": "tags", "operator": "contains", "value": "vip", "path_id": "sales"},
    ]
    matches = service._evaluate_rules(  # noqa: SLF001
        {"score": 90, "country": "US", "email": "x@y.com", "tags": ["vip", "priority"]},
        rules,
    )
    assert len(matches) == 4


def test_score_paths_from_rules(service: DecisionService):
    scores = service._score_paths_from_rules(  # noqa: SLF001
        [{"path_id": "sales"}, {"path_id": "sales"}, {"path_id": "nurture"}]
    )
    assert scores["sales"] > scores["nurture"]


def test_hybrid_combines_ai_and_rules(service: DecisionService):
    paths = [DecisionPath(id="sales", label="Sales"), DecisionPath(id="nurture", label="Nurture")]
    selected, confidence = service._combine_decision(  # noqa: SLF001
        DecisionType.HYBRID,
        paths,
        ai_result=DecisionAIReasoning(
            selected_path_id="sales",
            confidence=0.8,
            reasoning_summary="Fit is strong",
            key_factors=["score"],
            risks_identified=[],
            alternatives_rejected=[],
        ),
        rule_scores={"sales": 0.5, "nurture": 0.1},
    )
    assert selected.id == "sales"
    assert confidence >= 0.48


@pytest.mark.asyncio
async def test_evaluate_rule_based(service: DecisionService):
    with patch.object(service, "_persist_decision"):
        result = await service.evaluate(
            org_id="org-1",
            workflow_id="wf-1",
            run_id="run-1",
            node_id="node-1",
            objective="Route lead",
            input_data={"score": 95},
            available_paths=[DecisionPath(id="sales", label="Sales"), DecisionPath(id="nurture", label="Nurture")],
            decision_type=DecisionType.RULE_BASED,
            rules=[{"field": "score", "operator": "greater_than", "value": 80, "path_id": "sales"}],
        )
    assert result.selected_path.id == "sales"
    assert result.requires_human_approval is False
    assert result.rule_matches is not None


@pytest.mark.asyncio
async def test_evaluate_hybrid_with_ai(service: DecisionService):
    ai_reasoning = DecisionAIReasoning(
        selected_path_id="sales",
        confidence=0.88,
        reasoning_summary="Strong fit",
        key_factors=["lead score", "company size"],
        risks_identified=[],
        alternatives_rejected=[{"id": "nurture", "reason": "lower score"}],
    )
    with patch.object(service, "_get_ai_reasoning", AsyncMock(return_value=ai_reasoning)):
        with patch.object(service, "_persist_decision"):
            result = await service.evaluate(
                org_id="org-1",
                workflow_id="wf-1",
                run_id="run-1",
                node_id="node-1",
                objective="Route lead",
                input_data={"score": 88},
                available_paths=[DecisionPath(id="sales", label="Sales"), DecisionPath(id="nurture", label="Nurture")],
                decision_type=DecisionType.HYBRID,
                rules=[{"field": "score", "operator": "greater_than", "value": 80, "path_id": "sales"}],
            )
    assert result.selected_path.id == "sales"
    assert result.ai_reasoning is not None


@pytest.mark.asyncio
async def test_autonomous_low_confidence_requires_human(service: DecisionService):
    ai_reasoning = DecisionAIReasoning(
        selected_path_id="sales",
        confidence=0.6,
        reasoning_summary="Uncertain match",
        key_factors=[],
        risks_identified=["insufficient data"],
        alternatives_rejected=[],
    )
    with patch.object(service, "_get_ai_reasoning", AsyncMock(return_value=ai_reasoning)):
        with patch.object(service, "_persist_decision"):
            result = await service.evaluate(
                org_id="org-1",
                workflow_id="wf-1",
                run_id="run-1",
                node_id="node-1",
                objective="Route lead",
                input_data={"score": 60},
                available_paths=[DecisionPath(id="sales", label="Sales")],
                decision_type=DecisionType.AUTONOMOUS,
            )
    assert result.requires_human_approval is True
