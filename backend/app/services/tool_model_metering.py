"""Meter tool-calling rounds through Gravitre's existing model-call contract.

Uses the same writer and catalog estimator as ModelRouter. Attribution context
is inherited; no second cost store and no prompt/response content is persisted.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def record_tool_model_call(
    router: Any, *, org_id: str | None, model: str, elapsed_ms: int,
    input_tokens: int, output_tokens: int, cached_tokens: int = 0,
    agent_id: str | None = None, cache_write_tokens: int = 0,
) -> str | None:
    if not org_id:
        return None
    from app.services.llm_catalog import provider_for_model
    from app.services.model_router import ModelResponse, TaskType

    try:
        response = ModelResponse(
            provider=provider_for_model(model) or "openai", model=model, content="",
            input_tokens=max(0, input_tokens), output_tokens=max(0, output_tokens),
            latency_ms=max(0, elapsed_ms),
            cost_usd=router._estimate_cost(model, input_tokens, output_tokens, cached_tokens, cache_write_tokens=cache_write_tokens),
            cache_hit=cached_tokens > 0,
        )
        return await router._log_model_call(org_id, TaskType.DECISION_REASONING, response, agent_id=agent_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool_model_metering_failed org_id=%s model=%s error=%s", org_id, model, exc)
        return None


async def record_tool_response(router: Any, *, org_id: str | None, model: str, elapsed_ms: int,
                               response: Any, agent_id: str | None = None) -> str | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        logger.warning("tool_model_usage_missing model=%s", model)
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    return await record_tool_model_call(
        router, org_id=org_id, model=model, elapsed_ms=elapsed_ms,
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        cached_tokens=int(getattr(details, "cached_tokens", 0) or 0), agent_id=agent_id,
        cache_write_tokens=int(getattr(details, "cache_write_tokens", 0) or 0),
    )


async def authorize_tool_model_call(router: Any, *, model: str) -> None:
    """Apply the existing org model policy and budget before provider dispatch."""
    import asyncio
    from app.services.ai_guardrails import AIServiceDisabledError
    from app.services.cost_attribution import current_model_org_id

    # Settings is a typed bool in production. Mock routers often expose an
    # unspecified MagicMock here; its truthiness must not invent a kill switch.
    if getattr(getattr(router, "settings", None), "disable_ai", False) is True:
        raise AIServiceDisabledError()
    org_id = current_model_org_id()
    if org_id is None:
        return
    await asyncio.to_thread(router._assert_model_policy, org_id, model)
    await asyncio.to_thread(router._enforce_rate_and_budget, org_id)
