from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.cost_attribution import attribution, attribution_fields
from app.services.tool_model_metering import authorize_tool_model_call, record_tool_response


@pytest.mark.asyncio
async def test_three_tool_rounds_use_canonical_writer_and_share_turn_without_losing_cache_usage():
    seen = []
    async def write(org_id, task_type, response, **kwargs):
        seen.append((org_id, response, dict(attribution_fields())))
        return str(len(seen))
    router = SimpleNamespace(_estimate_cost=MagicMock(return_value=.03), _log_model_call=write)
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20,
        prompt_tokens_details=SimpleNamespace(cached_tokens=50)))
    with attribution(turn_id="turn-1", run_id="run-1"):
        ids = [await record_tool_response(router, org_id="org", model="gpt-5.4", elapsed_ms=12, response=response) for _ in range(3)]
    assert ids == ["1", "2", "3"]
    assert all(row[2] == {"run_id": "run-1", "turn_id": "turn-1"} for row in seen)
    assert all(row[1].input_tokens == 100 and row[1].output_tokens == 20 and row[1].cache_hit for row in seen)
    assert attribution_fields() == {}
    router._estimate_cost.assert_called_with("gpt-5.4", 100, 20, 50, cache_write_tokens=0)


@pytest.mark.asyncio
async def test_missing_provider_usage_is_not_invented():
    router = SimpleNamespace(_log_model_call=AsyncMock())
    assert await record_tool_response(router, org_id="org", model="gpt-5.4", elapsed_ms=12, response=SimpleNamespace()) is None
    router._log_model_call.assert_not_called()


def test_anthropic_cache_usage_is_not_lost_in_normalization():
    from app.services.providers.provider_tool_router import _parse_anthropic_response
    from app.services.providers.tool_completion import make_openai_compatible_response
    response = SimpleNamespace(content=[], usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=50, cache_creation_input_tokens=10))
    normalized = make_openai_compatible_response(_parse_anthropic_response(response))
    assert normalized.usage.prompt_tokens == 160
    assert normalized.usage.prompt_tokens_details.cached_tokens == 50
    assert normalized.usage.prompt_tokens_details.cache_write_tokens == 10


@pytest.mark.asyncio
async def test_direct_provider_gate_checks_existing_org_policy_and_budget():
    router = SimpleNamespace(settings=SimpleNamespace(disable_ai=False),
        _assert_model_policy=MagicMock(), _enforce_rate_and_budget=MagicMock())
    with attribution(org_id="client-org", turn_id="turn-1"):
        await authorize_tool_model_call(router, model="claude-haiku-5-5")
    router._assert_model_policy.assert_called_once_with("client-org", "claude-haiku-5-5")
    router._enforce_rate_and_budget.assert_called_once_with("client-org")


@pytest.mark.asyncio
async def test_direct_provider_gate_stops_when_budget_refuses():
    router = SimpleNamespace(settings=SimpleNamespace(disable_ai=False),
        _assert_model_policy=MagicMock(), _enforce_rate_and_budget=MagicMock(side_effect=RuntimeError("budget exceeded")))
    with attribution(org_id="client-org"):
        with pytest.raises(RuntimeError, match="budget exceeded"):
            await authorize_tool_model_call(router, model="claude-haiku-5-5")
