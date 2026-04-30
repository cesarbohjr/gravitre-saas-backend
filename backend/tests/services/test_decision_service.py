from app.services.decision_service import DecisionPath, DecisionService, DecisionType


class _DummyRouter:
    async def complete(self, *args, **kwargs):  # pragma: no cover - not used
        raise RuntimeError("not used")


def test_rule_matching_operators():
    service = DecisionService(model_router=_DummyRouter())  # type: ignore[arg-type]
    rules = [
        {"field": "score", "operator": "greater_or_equal", "value": 80, "path_id": "sales"},
        {"field": "country", "operator": "equals", "value": "US", "path_id": "sales"},
        {"field": "email", "operator": "matches_regex", "value": r".+@.+", "path_id": "sales"},
    ]
    matches = service._evaluate_rules({"score": 90, "country": "US", "email": "x@y.com"}, rules)  # noqa: SLF001
    assert len(matches) == 3


def test_hybrid_combines_ai_and_rules():
    service = DecisionService(model_router=_DummyRouter())  # type: ignore[arg-type]
    paths = [DecisionPath(id="sales", label="Sales"), DecisionPath(id="nurture", label="Nurture")]
    selected, confidence = service._combine_decision(  # noqa: SLF001
        DecisionType.HYBRID,
        paths,
        ai_result=None,
        rule_scores={"sales": 0.8},
    )
    assert selected.id == "sales"
    assert confidence > 0.0
