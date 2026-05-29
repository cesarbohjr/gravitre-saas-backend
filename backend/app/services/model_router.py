from __future__ import annotations

import asyncio
import hashlib
import json
import time
from enum import StrEnum
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.ai_guardrails import (
    AIServiceDisabledError,
    enforce_budget,
    enforce_rate_limit,
    fence_untrusted,
    harden_system_prompt,
    moderate_input,
)
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

# Per-request timeout (seconds) for OpenAI calls; we manage retries ourselves.
OPENAI_REQUEST_TIMEOUT_S = 30.0
MAX_ATTEMPTS = 3


class TaskType(StrEnum):
    CLASSIFICATION = "classification"
    INTENT_DETECTION = "intent_detection"
    WORKFLOW_PLANNING = "workflow_planning"
    DECISION_REASONING = "decision_reasoning"
    AGENT_DEBATE = "agent_debate"
    SUMMARIZATION = "summarization"
    CONTENT_GENERATION = "content_generation"
    RAG_ANSWERING = "rag_answering"
    OPTIMIZATION_ANALYSIS = "optimization"


DEFAULT_ROUTES: dict[TaskType, str] = {
    TaskType.CLASSIFICATION: "gpt-4.1",
    TaskType.INTENT_DETECTION: "gpt-4.1",
    TaskType.WORKFLOW_PLANNING: "gpt-4.1",
    TaskType.DECISION_REASONING: "gpt-4.1",
    TaskType.AGENT_DEBATE: "gpt-4.1",
    TaskType.SUMMARIZATION: "gpt-4.1",
    TaskType.CONTENT_GENERATION: "gpt-4.1",
    TaskType.RAG_ANSWERING: "gpt-4.1",
    TaskType.OPTIMIZATION_ANALYSIS: "gpt-4.1",
}

_MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4.1": (0.002, 0.008),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.005, 0.015),
}


class ModelResponse(BaseModel):
    provider: str
    model: str
    content: str
    parsed: dict[str, Any] | None = None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    cache_hit: bool = False


class ModelRouter:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._openai = (
            AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                timeout=OPENAI_REQUEST_TIMEOUT_S,
                max_retries=0,  # retries handled by _retry_complete with backoff
            )
            if self.settings.openai_api_key
            else None
        )
        self._cache: dict[str, ModelResponse] = {}

    async def complete(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: type[BaseModel] | None = None,
        use_cache: bool = False,
        context: list[dict] | None = None,
        org_id: str | None = None,
    ) -> ModelResponse:
        model = self._resolve_model(task_type)
        provider = "openai"

        # --- Governance guardrails (chokepoint) ---------------------------------
        # 1) Global killswitch
        if getattr(self.settings, "disable_ai", False):
            logger.warning("AI_DISABLED task_type=%s org_id=%s", task_type.value, org_id)
            raise AIServiceDisabledError()
        # 2) Per-org rate limit (runaway-spend circuit breaker)
        enforce_rate_limit(org_id, self.settings)
        # 3) Hard spend gate (period ai_credits budget)
        enforce_budget(org_id, self.settings)
        # 4) Input moderation (system + user content)
        await moderate_input(f"{system_prompt or ''}\n{prompt}", self.settings, self._openai)

        cache_key = self._cache_key(task_type, prompt, system_prompt, temperature, max_tokens, model, context)

        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key].model_copy(update={"cache_hit": True})
            await self._log_model_call(org_id=org_id, task_type=task_type, response=cached)
            return cached

        start = time.perf_counter()
        logger.info(
            "MODEL_CALL_START task_type=%s model=%s provider=%s",
            task_type.value,
            model,
            provider,
            extra={"task_type": task_type.value, "model": model, "provider": provider},
        )
        try:
            response_text, usage = await self._retry_complete(
                model=model,
                prompt=fence_untrusted(prompt),
                system_prompt=harden_system_prompt(system_prompt),
                temperature=temperature,
                max_tokens=max_tokens,
                context=context,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "MODEL_CALL_FAILURE task_type=%s model=%s provider=%s duration_ms=%s error=%s",
                task_type.value,
                model,
                provider,
                latency_ms,
                str(exc),
                extra={
                    "task_type": task_type.value,
                    "model": model,
                    "provider": provider,
                    "duration_ms": latency_ms,
                    "status": "failure",
                },
            )
            raise
        latency_ms = int((time.perf_counter() - start) * 1000)
        # Prefer actual token usage reported by the API; fall back to estimation.
        if usage:
            input_tokens = int(usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("completion_tokens") or 0)
        else:
            input_tokens = self._estimate_tokens(prompt + (system_prompt or ""))
            output_tokens = self._estimate_tokens(response_text)
        cost = self._estimate_cost(model, input_tokens, output_tokens)

        parsed_payload: dict[str, Any] | None = None
        if response_format:
            parsed_payload = self._parse_structured(response_text, response_format)
            response_text = json.dumps(parsed_payload, separators=(",", ":"))

        final = ModelResponse(
            provider=provider,
            model=model,
            content=response_text,
            parsed=parsed_payload,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
            cache_hit=False,
        )
        if use_cache:
            self._cache[cache_key] = final
        logger.info(
            "MODEL_CALL_SUCCESS task_type=%s model=%s provider=%s duration_ms=%s",
            task_type.value,
            model,
            provider,
            latency_ms,
            extra={
                "task_type": task_type.value,
                "model": model,
                "provider": provider,
                "duration_ms": latency_ms,
                "status": "success",
            },
        )
        await self._log_model_call(org_id=org_id, task_type=task_type, response=final)
        return final

    def _resolve_model(self, task_type: TaskType) -> str:
        # Stabilized routing: use one reliable production model until broader routing is reintroduced.
        return DEFAULT_ROUTES.get(task_type, "gpt-4.1")

    def _cache_key(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        model: str,
        context: list[dict] | None,
    ) -> str:
        payload = json.dumps(
            {
                "task_type": task_type.value,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "model": model,
                "context": context or [],
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _retry_complete(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        context: list[dict] | None,
    ) -> tuple[str, dict[str, int] | None]:
        delay = 0.4
        for attempt in range(MAX_ATTEMPTS):
            try:
                return await self._openai_complete(model, prompt, system_prompt, temperature, max_tokens, context)
            except Exception as exc:  # noqa: BLE001
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                # Rate limits / timeouts / transient connection errors get a
                # longer, retry-after-aware backoff; other errors back off normally.
                sleep_for = delay
                if isinstance(exc, RateLimitError):
                    sleep_for = max(delay, self._retry_after_seconds(exc, default=2.0))
                elif isinstance(exc, (APITimeoutError, APIConnectionError)):
                    sleep_for = delay
                logger.warning(
                    "Model completion retrying model=%s attempt=%s error_type=%s error=%s sleep_s=%.2f",
                    model,
                    attempt + 1,
                    type(exc).__name__,
                    str(exc),
                    sleep_for,
                )
                await asyncio.sleep(sleep_for)
                delay *= 2
        raise RuntimeError("unreachable")

    @staticmethod
    def _retry_after_seconds(exc: Exception, default: float) -> float:
        """Best-effort parse of a Retry-After header from an OpenAI error."""
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            return default
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if not raw:
            return default
        try:
            return max(default, float(raw))
        except (TypeError, ValueError):
            return default

    async def _openai_complete(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        context: list[dict] | None,
    ) -> tuple[str, dict[str, int] | None]:
        if not self._openai:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        messages.extend(context or [])
        messages.append({"role": "user", "content": prompt})
        resp = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature if temperature is not None else 0.2,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        if not content.strip():
            raise RuntimeError("Model returned empty response")
        usage = self._extract_usage(resp)
        return content, usage

    @staticmethod
    def _extract_usage(resp: Any) -> dict[str, int] | None:
        """Pull actual token usage from an OpenAI chat completion response."""
        raw = getattr(resp, "usage", None)
        if raw is None:
            return None
        prompt_tokens = getattr(raw, "prompt_tokens", None)
        completion_tokens = getattr(raw, "completion_tokens", None)
        if prompt_tokens is None and completion_tokens is None:
            return None
        return {
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
        }

    def _parse_structured(self, text: str, schema: type[BaseModel]) -> dict[str, Any]:
        normalized = text.strip()
        if normalized.startswith("```"):
            normalized = normalized.replace("```json", "").replace("```", "").strip()
        if not normalized:
            raise ValueError("Model returned empty response for structured output")
        # Models can wrap JSON in prose; extract the first JSON object if needed.
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            start = normalized.find("{")
            end = normalized.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("Model did not return valid JSON for structured output")
            try:
                payload = json.loads(normalized[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ValueError("Model did not return valid JSON for structured output") from exc
        return schema.model_validate(payload).model_dump()

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        in_cost, out_cost = _MODEL_PRICING_PER_1K.get(model, (0.002, 0.008))
        return round((input_tokens / 1000 * in_cost) + (output_tokens / 1000 * out_cost), 6)

    async def _log_model_call(self, org_id: str | None, task_type: TaskType, response: ModelResponse) -> None:
        if not org_id:
            return
        try:
            client = get_supabase_client(self.settings)
            row = {
                "org_id": org_id,
                "task_type": task_type.value,
                "provider": response.provider,
                "model_name": response.model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "cost_usd": response.cost_usd,
                "cache_hit": response.cache_hit,
            }
            client.table("model_calls").insert(row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("model_calls insert failed: %s", str(exc))


_model_router_singleton: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _model_router_singleton
    if _model_router_singleton is None:
        _model_router_singleton = ModelRouter()
    return _model_router_singleton
