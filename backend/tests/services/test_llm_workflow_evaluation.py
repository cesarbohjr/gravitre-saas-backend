from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.llm_workflow_evaluation import (
    EvaluationCase, evaluate_models, score_structured_response, summarize_evaluations,
)

MODEL = "gpt-5.4-mini"
CASE = EvaluationCase("approval", "classification", "Return a JSON decision.",
                      {"approved": False}, critical=True)


def _response(**changes):
    return SimpleNamespace(**{
        "model": MODEL, "provider": "openai", "content": '{"approved":false}',
        "model_call_id": "call-1", "input_tokens": 10, "output_tokens": 5,
        "cost_usd": .01, "latency_ms": 100, **changes,
    })


def test_structured_scoring_preserves_types_and_rejects_non_json():
    assert score_structured_response('{"approved":false}', CASE.expected)
    assert not score_structured_response('{"approved":0}', CASE.expected)
    assert not score_structured_response('```json\n{"approved":false}\n```', CASE.expected)
    assert not score_structured_response('{"approved":false,"extra":true}', CASE.expected)
    assert not score_structured_response('{"approved":true,"approved":false}', CASE.expected)


@pytest.mark.asyncio
async def test_evaluation_uses_existing_router_evidence_without_changing_routing():
    router = SimpleNamespace(complete=AsyncMock(return_value=_response()))
    report = await evaluate_models(router, org_id="test-org", models=[MODEL], cases=(CASE,))
    assert report["results"][0]["passed"] is True
    assert report["models"][MODEL]["routing_approved"] is False
    assert report["models"][MODEL]["latency_ms"]["p95"] is None
    assert router.complete.call_args.kwargs["use_cache"] is False
    assert router.complete.call_args.kwargs["org_id"] == "test-org"
    assert "content" not in report["results"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("change,reason", [
    ({"model": "gpt-5.5"}, "provider_substitution"),
    ({"model_call_id": None}, "missing_model_evidence"),
    ({"content": '{"approved":true}'}, "structured_answer_mismatch"),
])
async def test_substituted_unmeasured_and_unsafe_answers_fail(change, reason):
    router = SimpleNamespace(complete=AsyncMock(return_value=_response(**change)))
    report = await evaluate_models(router, org_id="test-org", models=[MODEL], cases=(CASE,))
    assert report["results"][0]["failure"] == reason
    assert report["models"][MODEL]["critical_failures"] == 1


def test_partial_cost_never_appears_as_cheap_success():
    result = summarize_evaluations([
        {"requested_model": MODEL, "passed": True, "critical": False, "cost_usd": .01},
        {"requested_model": MODEL, "passed": False, "critical": True, "cost_usd": None},
    ])[MODEL]
    assert result["total_cost_usd"] is None
    assert result["cost_per_success_usd"] is None


@pytest.mark.asyncio
async def test_provider_errors_do_not_leak_secrets_and_bounded_validation_runs_first(caplog):
    router = SimpleNamespace(complete=AsyncMock(side_effect=RuntimeError("secret-provider-payload")))
    report = await evaluate_models(router, org_id="test-org", models=[MODEL], cases=(CASE,))
    assert report["results"][0]["failure"] == "RuntimeError"
    assert "secret-provider-payload" not in str(report)
    assert "workflow_model_evaluation_failed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "secret-provider-payload" not in caplog.text
    router.complete.reset_mock()
    with pytest.raises(ValueError):
        await evaluate_models(router, org_id="test-org", models=[MODEL], repetitions=999)
    router.complete.assert_not_called()
