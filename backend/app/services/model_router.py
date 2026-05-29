from __future__ import annotations

import hashlib
import json
import time
from enum import StrEnum
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import MODEL_TIERS, TASK_COMPLEXITY, Settings, get_settings
from app.core.logging import get_logger
from app.services.ai_guardrails import (
    AIServiceDisabledError,
    enforce_budget,
    enforce_rate_limit,
    fence_untrusted,
    harden_system_prompt,
    moderate_input,
)
from app.services.providers.anthropic_adapter import AnthropicAdapter
from app.services.providers.base import (
    AllProvidersFailedError,
    CircuitBreaker,
    CompletionOptions,
    Message,
    ProviderAdapter,
    ProviderInvalidResponseError,
)
from app.services.providers.failover import build_priority, run_failover
from app.services.providers.gemini_adapter import GeminiAdapter
from app.services.providers.openai_adapter import OpenAIAdapter
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

OPENAI_REQUEST_TIMEOUT_S = 30.0


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


# Approximate per-1k token pricing (input, output) for cost estimation.
_MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4.1": (0.002, 0.008),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.005, 0.015),
    "claude-haiku-4-5-20251001": (0.0008, 0.004),
    "claude-sonnet-4-6": (0.003, 0.015),
    "gemini-2.5-flash": (0.0001, 0.0004),
    "gemini-2.5-pro": (0.00125, 0.005),
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
                max_retries=0,  # retries handled inside the adapter
            )
            if self.settings.openai_api_key
            else None
        )
        # Provider adapters. The OpenAI adapter reads the live client via a getter
        # so tests that swap `router._openai` continue to work.
        self._adapters: dict[str, ProviderAdapter] = {
            "openai": OpenAIAdapter(
                client_getter=lambda: self._openai,
                api_key_getter=lambda: (self.settings.openai_api_key or ""),
                timeout_s=OPENAI_REQUEST_TIMEOUT_S,
            ),
            "anthropic": AnthropicAdapter(
                api_key_getter=lambda: (self.settings.anthropic_api_key or "").strip(),
                voyage_key_getter=lambda: (getattr(self.settings, "voyage_api_key", "") or "").strip(),
                timeout_s=OPENAI_REQUEST_TIMEOUT_S,
            ),
            "gemini": GeminiAdapter(
                api_key_getter=lambda: (
                    getattr(self.settings, "gemini_key", "")
                    or getattr(self.settings, "gemini_api_key", "")
                    or getattr(self.settings, "google_api_key", "")
                    or ""
                ).strip(),
            ),
        }
        self._breaker = CircuitBreaker(failure_threshold=3, cooldown_s=60.0)
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
        complexity = TASK_COMPLEXITY.get(task_type.value, "medium")
        model = self._resolve_model(task_type)  # primary (openai) model, for cache key

        # --- Governance guardrails (chokepoint) ---------------------------------
        if getattr(self.settings, "disable_ai", False):
            logger.warning("AI_DISABLED task_type=%s org_id=%s", task_type.value, org_id)
            raise AIServiceDisabledError()
        enforce_rate_limit(org_id, self.settings)
        enforce_budget(org_id, self.settings)
        await moderate_input(f"{system_prompt or ''}\n{prompt}", self.settings, self._openai)

        cache_key = self._cache_key(task_type, prompt, system_prompt, temperature, max_tokens, model, context)
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key].model_copy(update={"cache_hit": True})
            await self._log_model_call(org_id=org_id, task_type=task_type, response=cached)
            return cached

        # Canonical messages with safety hardening + untrusted-input fencing.
        messages: list[Message] = []
        hardened_system = harden_system_prompt(system_prompt)
        if hardened_system:
            messages.append({"role": "system", "content": hardened_system})
        for c in context or []:
            role = c.get("role")
            content = c.get("content")
            if role in ("system", "user", "assistant") and content is not None:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": fence_untrusted(prompt)})

        # Build the failover priority chain.
        if getattr(self.settings, "ai_failover_enabled", True):
            priority = build_priority(getattr(self.settings, "preferred_ai_provider", "openai"), complexity)
        else:
            priority = [("openai", MODEL_TIERS[complexity]["openai"])]

        options = CompletionOptions(
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=OPENAI_REQUEST_TIMEOUT_S,
        )

        start = time.perf_counter()
        logger.info(
            "MODEL_CALL_START task_type=%s complexity=%s priority=%s",
            task_type.value,
            complexity,
            [name for name, _ in priority],
        )
        try:
            result = await run_failover(self._adapters, priority, messages, options, self._breaker)
        except ProviderInvalidResponseError as exc:
            self._log_call_failure(task_type, model, "varied", start, exc)
            await self._log_guardrail_event(org_id, task_type, "ai_failover_invalid", [], str(exc))
            raise
        except AllProvidersFailedError as exc:
            self._log_call_failure(task_type, model, "varied", start, exc)
            await self._log_guardrail_event(org_id, task_type, "ai_failover_exhausted", [], str(exc))
            raise

        resp = result.response
        latency_ms = int((time.perf_counter() - start) * 1000)

        if resp.prompt_tokens or resp.completion_tokens:
            input_tokens = resp.prompt_tokens
            output_tokens = resp.completion_tokens
        else:
            input_tokens = self._estimate_tokens(prompt + (system_prompt or ""))
            output_tokens = self._estimate_tokens(resp.content)

        cost = self._estimate_cost(resp.model_used, input_tokens, output_tokens)

        response_text = resp.content
        parsed_payload: dict[str, Any] | None = None
        if response_format:
            parsed_payload = self._parse_structured(response_text, response_format)
            response_text = json.dumps(parsed_payload, separators=(",", ":"))

        final = ModelResponse(
            provider=resp.provider_used,
            model=resp.model_used,
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
            "MODEL_CALL_SUCCESS task_type=%s provider=%s model=%s duration_ms=%s attempts=%s",
            task_type.value,
            resp.provider_used,
            resp.model_used,
            latency_ms,
            result.attempts,
        )
        await self._log_model_call(org_id=org_id, task_type=task_type, response=final)
        await self._log_guardrail_event(
            org_id,
            task_type,
            "ai_failover",
            result.attempts,
            f"final={resp.provider_used}/{resp.model_used}",
            latency_ms=latency_ms,
        )
        return final

    def _log_call_failure(
        self,
        task_type: TaskType,
        model: str,
        provider: str,
        start: float,
        exc: Exception,
    ) -> None:
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

    def _resolve_model(self, task_type: TaskType) -> str:
        """Primary (OpenAI) model for the task's complexity tier."""
        complexity = TASK_COMPLEXITY.get(task_type.value, "medium")
        return MODEL_TIERS[complexity]["openai"]

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

    def _parse_structured(self, text: str, schema: type[BaseModel]) -> dict[str, Any]:
        normalized = text.strip()
        if normalized.startswith("```"):
            normalized = normalized.replace("```json", "").replace("```", "").strip()
        if not normalized:
            raise ValueError("Model returned empty response for structured output")
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

    async def _log_guardrail_event(
        self,
        org_id: str | None,
        task_type: TaskType,
        event_type: str,
        attempts: list[tuple[str, str]],
        summary: str,
        latency_ms: int | None = None,
    ) -> None:
        """Log a failover attempt to guardrail_events (best-effort) + structured log."""
        final_provider = next((name for name, outcome in attempts if outcome == "success"), None)
        logger.warning(
            "AI_FAILOVER event=%s task_type=%s attempts=%s final=%s latency_ms=%s summary=%s",
            event_type,
            task_type.value,
            attempts,
            final_provider,
            latency_ms,
            summary,
        )
        if not org_id:
            return
        try:
            client = get_supabase_client(self.settings)
            client.table("guardrail_events").insert(
                {
                    "org_id": org_id,
                    "event_type": event_type,
                    "detail": {
                        "task_type": task_type.value,
                        "attempts": [{"provider": n, "outcome": o} for n, o in attempts],
                        "final_provider": final_provider,
                        "latency_ms": latency_ms,
                        "summary": summary,
                    },
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("guardrail_events insert failed: %s", str(exc))


_model_router_singleton: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _model_router_singleton
    if _model_router_singleton is None:
        _model_router_singleton = ModelRouter()
    return _model_router_singleton
