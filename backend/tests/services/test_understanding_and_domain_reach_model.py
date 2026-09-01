"""Sites 9 and 10 must genuinely reach the model router.

Both were dormant: get_model_router(self.settings) raised TypeError inside a
broad `except Exception`, so the services silently returned their benign
defaults. The pre-existing tests in this area did not catch it because a
MagicMock router accepts any signature, which is exactly how the bug survived at
the query rewriter too.

So the fake here is strict: it raises TypeError on ANY argument, mirroring the
real zero-arg factory. A test using a permissive mock would pass with the bug
restored and is worthless as a guard.
"""
from __future__ import annotations

import json

import pytest

from app.services import contextual_understanding_service as cus
from app.services import domain_intelligence_service as dis

# Long, non-question text: _infer_goal_from_rules returns None only when the
# message does not end in "?" and exceeds 12 words, which is site 9's gate.
LONG_STATEMENT = (
    "we need to tighten up the renewal motion for the mid market accounts "
    "before the quarter closes and make sure nothing slips through"
)


class StrictRouter:
    """Stands in for the real zero-arg factory, including its signature."""

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.completions = 0
        self.arg_calls = 0

    def factory(self, *args, **kwargs):
        if args or kwargs:
            self.arg_calls += 1
            raise TypeError(
                f"get_model_router() takes 0 positional arguments but {len(args)} was given"
            )
        return self

    async def complete(self, **kwargs):
        self.completions += 1
        payload = self.payload

        class R:
            content = payload

        return R()


@pytest.fixture
def strict(monkeypatch):
    def _install(payload: str) -> StrictRouter:
        router = StrictRouter(payload)
        import app.services.model_router as mr

        monkeypatch.setattr(mr, "get_model_router", router.factory)
        return router

    return _install


def _settings():
    from app.config import get_settings

    return get_settings()


# --------------------------------------------------------------------------
# Site 9 — contextual_understanding_service._model_extract
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_extract_reaches_router_with_zero_args(strict):
    router = strict(json.dumps({"goal": "tighten renewals", "constraints": ["mid market"]}))
    svc = cus.ContextualUnderstandingService(_settings())

    result = await svc._model_extract(LONG_STATEMENT, [], [])

    assert router.arg_calls == 0, "factory must never be called with an argument"
    assert router.completions == 1, "the model call must actually execute"
    assert result.get("goal") == "tighten renewals"
    assert result.get("constraints") == ["mid market"]


@pytest.mark.asyncio
async def test_model_extract_returns_empty_when_router_rejects_args(strict):
    """Pins the dormant behaviour so a regression is visible, not silent."""
    router = strict("{}")
    svc = cus.ContextualUnderstandingService(_settings())

    import app.services.model_router as mr

    original = mr.get_model_router
    mr.get_model_router = lambda *a, **k: original(object())  # force the old shape
    try:
        result = await svc._model_extract(LONG_STATEMENT, [], [])
    finally:
        mr.get_model_router = original

    assert result == {}
    assert router.completions == 0


@pytest.mark.asyncio
async def test_model_extract_handles_fenced_json(strict):
    strict('```json\n{"goal": "fenced", "constraints": []}\n```')
    svc = cus.ContextualUnderstandingService(_settings())

    result = await svc._model_extract(LONG_STATEMENT, [], [])

    assert result.get("goal") == "fenced"


@pytest.mark.asyncio
async def test_understand_populates_goal_from_model(strict, monkeypatch):
    """End-to-end through understand(): the gate must let the model through."""
    strict(json.dumps({"goal": "model goal", "constraints": ["c1"]}))
    svc = cus.ContextualUnderstandingService(_settings())

    async def no_domain(*a, **k):
        return {}

    class FakeDomain:
        async def classify(self, *a, **k):
            return {}

    monkeypatch.setattr(
        dis, "get_domain_intelligence_service", lambda *a, **k: FakeDomain()
    )

    out = await svc.understand(LONG_STATEMENT, [], "org-1")

    assert out.get("goal") == "model goal"
    assert out.get("constraints") == ["c1"]


@pytest.mark.asyncio
async def test_short_question_does_not_call_model(strict):
    """The rule path must still short-circuit; the fix must not add model calls."""
    router = strict(json.dumps({"goal": "should not be used"}))
    svc = cus.ContextualUnderstandingService(_settings())

    goal = svc._infer_goal_from_rules("what are my open deals?")

    assert goal, "a short question must be answered by rules"
    assert router.completions == 0


# --------------------------------------------------------------------------
# Site 10 — domain_intelligence_service._classify_by_llm
# --------------------------------------------------------------------------

LOW_CONF_RULES = {
    "industry": None,
    "department": None,
    "subdomain": None,
    "business_objective": None,
    "execution_type": None,
    "confidence": 0.1,
    "source": "rules",
    "profile_id": None,
}


@pytest.mark.asyncio
async def test_classify_by_llm_reaches_router_with_zero_args(strict):
    router = strict(
        json.dumps(
            {
                "industry": "software",
                "department": "customer_success",
                "subdomain": "renewals",
                "business_objective": "retention",
                "execution_type": "analysis",
                "confidence": 0.82,
            }
        )
    )
    svc = dis.DomainIntelligenceService(_settings())

    result = await svc._classify_by_llm(LONG_STATEMENT, {}, dict(LOW_CONF_RULES))

    assert router.arg_calls == 0
    assert router.completions == 1
    assert result.get("department") == "customer_success"
    assert float(result.get("confidence") or 0) > 0.55, (
        "the LLM tier exists to lift low-confidence rule guesses above the "
        "routing threshold; if it cannot, it is not doing its job"
    )


@pytest.mark.asyncio
async def test_classify_by_llm_falls_back_to_rules_on_bad_json(strict):
    router = strict("not json at all")
    svc = dis.DomainIntelligenceService(_settings())

    result = await svc._classify_by_llm(LONG_STATEMENT, {}, dict(LOW_CONF_RULES))

    assert router.completions == 1
    assert result.get("confidence") == 0.1, "must degrade to the rule result"


@pytest.mark.asyncio
async def test_dormant_llm_tier_leaves_confidence_below_threshold(strict):
    """The exact production symptom: the fallback tier never lifts confidence."""
    router = strict("{}")
    svc = dis.DomainIntelligenceService(_settings())

    import app.services.model_router as mr

    original = mr.get_model_router
    mr.get_model_router = lambda *a, **k: original(object())
    try:
        result = await svc._classify_by_llm(LONG_STATEMENT, {}, dict(LOW_CONF_RULES))
    finally:
        mr.get_model_router = original

    assert router.completions == 0
    assert float(result.get("confidence") or 0) < dis.DOMAIN_CONFIDENCE_THRESHOLD


@pytest.mark.asyncio
async def test_high_confidence_rules_skip_the_model(strict, monkeypatch):
    """classify() must not spend a model call when rules are already confident."""
    router = strict(json.dumps({"department": "unused"}))
    svc = dis.DomainIntelligenceService(_settings())

    async def hints(_org):
        return {}

    monkeypatch.setattr(svc, "_load_org_domain_hints", hints)
    monkeypatch.setattr(
        svc,
        "_classify_by_rules",
        lambda *a, **k: {**LOW_CONF_RULES, "confidence": 0.9, "department": "sales"},
    )

    out = await svc.classify("org-1", LONG_STATEMENT)

    assert router.completions == 0
    assert str(out.get("department") or "").lower() == "sales"


@pytest.mark.asyncio
async def test_low_confidence_rules_do_reach_the_model(strict, monkeypatch):
    router = strict(
        json.dumps({"department": "customer_success", "confidence": 0.8})
    )
    svc = dis.DomainIntelligenceService(_settings())

    async def hints(_org):
        return {}

    monkeypatch.setattr(svc, "_load_org_domain_hints", hints)
    monkeypatch.setattr(svc, "_classify_by_rules", lambda *a, **k: dict(LOW_CONF_RULES))

    await svc.classify("org-1", LONG_STATEMENT)

    assert router.completions == 1, "low-confidence rules must consult the model"
