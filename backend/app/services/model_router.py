from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import MODEL_TIERS, TASK_COMPLEXITY, Settings, get_settings
from app.core.logging import get_logger
from app.services.ai_guardrails import (
    AIContentFlaggedError,
    AIGuardrailError,
    AIModelPolicyError,
    AIServiceDisabledError,
    enforce_budget,
    enforce_rate_limit,
    fence_untrusted,
    harden_system_prompt,
    moderate_input,
    moderate_output,
    redact_pii,
)
from app.services.model_policy_service import assert_model_allowed, load_org_model_policy
from app.services.providers.anthropic_adapter import AnthropicAdapter
from app.services.providers.base import (
    AllProvidersFailedError,
    CompletionOptions,
    Message,
    ProviderAdapter,
    ProviderInvalidResponseError,
)
from app.services.providers.failover import (
    build_priority,
    create_circuit_breaker,
    run_failover,
    run_failover_stream,
)
from app.services.providers.gemini_adapter import GeminiAdapter
from app.services.providers.openai_adapter import OpenAIAdapter
from app.core.db import get_supabase_client

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


# Per-1K token pricing (input, cached_input, output). Comment shows per-1M.
# cached_input applies to prompt tokens served from the provider's prompt cache
# (defaults to the normal input rate when the provider has no separate cache rate).
# Verified May 2026.
_MODEL_PRICING_PER_1K: dict[str, tuple[float, float, float]] = {
    "gpt-4.1": (0.002, 0.002, 0.008),                      # $2.00 in / $8.00 out per 1M
    "gpt-5.5": (0.005, 0.0005, 0.030),                     # $5.00 in / $0.50 cached / $30.00 out per 1M
    "gpt-5.4-mini": (0.00075, 0.00075, 0.0045),            # $0.75 in / $4.50 out per 1M
    "text-embedding-3-small": (0.00002, 0.00002, 0.0),     # $0.02 / 1M input (embeddings)
    "claude-sonnet-4-6": (0.003, 0.003, 0.015),            # $3.00 in / $15.00 out per 1M
    "claude-haiku-4-5-20251001": (0.0008, 0.0008, 0.004),  # $0.80 in / $4.00 out per 1M
    "gemini-2.5-pro": (0.00125, 0.00125, 0.010),           # $1.25 in / $10.00 out per 1M
    "gemini-2.5-flash": (0.0000875, 0.0000875, 0.00035),   # $0.0875 in / $0.35 out per 1M (non-thinking)
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
    # id of the model_calls row written for this call (used as the billing
    # idempotency anchor); None if logging was skipped or failed.
    model_call_id: str | None = None


@dataclass
class ModelStreamEvent:
    """Token delta during streaming, or final `response` when the provider stream completes."""

    delta: str = ""
    response: ModelResponse | None = None


@dataclass
class PreparedStream:
    """Pre-flight context for provider-native streaming (guardrails already passed)."""

    task_type: TaskType
    org_id: str | None
    prompt: str
    system_prompt: str | None
    messages: list[Message]
    priority: list[tuple[str, str]]
    options: CompletionOptions
    model: str
    agent_id: str | None = None
    operator_id: str | None = None
    autonomous_run: bool = False
    trained_model_id: str | None = None
    trained_model_version: int | None = None
    used_fallback: bool = False


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
        # Redis-backed breaker state (shared across instances) when REDIS_URL is
        # configured; falls back to per-process state otherwise.
        self._breaker = create_circuit_breaker(self.settings)
        self._cache: dict[str, ModelResponse] = {}

    # Token streaming (STA-5 / STA-151):
    #   prepare_stream() — guardrails + message build before HTTP stream opens
    #   stream() — run_failover_stream() forwards provider chunks to assistant SSE
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
        model_override: str | None = None,
        agent_id: str | None = None,
        operator_id: str | None = None,
        autonomous_run: bool = False,
        trained_model_id: str | None = None,
        trained_model_version: int | None = None,
        used_fallback: bool = False,
    ) -> ModelResponse:
        complexity = TASK_COMPLEXITY.get(task_type.value, "medium")
        model = model_override or self._resolve_model(task_type)  # primary model, for cache key

        if org_id:
            try:
                client = get_supabase_client(self.settings)
                policy = load_org_model_policy(client, org_id)
                assert_model_allowed(policy, provider="openai", model=model)
            except AIModelPolicyError:
                raise
            except Exception:  # noqa: BLE001
                logger.debug("model_policy_check_skipped org_id=%s", org_id, exc_info=True)

        if autonomous_run and operator_id and org_id:
            try:
                from app.services.autonomous_budget_service import (
                    AutonomousBudgetExceededError,
                    check_autonomous_llm_budget,
                    is_autonomous_operator,
                )

                client = get_supabase_client(self.settings)
                op_resp = (
                    client.table("operators")
                    .select("*")
                    .eq("org_id", org_id)
                    .eq("id", operator_id)
                    .limit(1)
                    .execute()
                )
                operator_row = op_resp.data[0] if op_resp.data else None
                if operator_row and is_autonomous_operator(operator_row):
                    est_in = self._estimate_tokens(prompt + (system_prompt or ""))
                    est_out = max(int(max_tokens or 0), est_in)
                    est_model = model_override or self._resolve_model(task_type)
                    est_spend = self._estimate_cost(est_model, est_in, est_out)
                    check_autonomous_llm_budget(
                        client,
                        org_id,
                        operator_row,
                        projected_tokens=est_in + est_out,
                        projected_spend_usd=est_spend,
                    )
            except AutonomousBudgetExceededError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("autonomous budget pre-check skipped org_id=%s error=%s", org_id, str(exc))

        # --- Governance guardrails (chokepoint) ---------------------------------
        # Any guardrail refusal is persisted to guardrail_events (auditable),
        # then re-raised so the caller can surface it.
        try:
            if getattr(self.settings, "disable_ai", False):
                raise AIServiceDisabledError()
            enforce_rate_limit(org_id, self.settings)
            enforce_budget(org_id, self.settings)
            await moderate_input(f"{system_prompt or ''}\n{prompt}", self.settings, self._openai)
        except AIGuardrailError as exc:
            code = getattr(exc, "code", "AI_GUARDRAIL")
            logger.warning(
                "AI_GUARDRAIL_BLOCK task_type=%s org_id=%s code=%s", task_type.value, org_id, code
            )
            await self._log_guardrail_event(org_id, task_type, code, [], str(exc))
            raise

        cache_key = self._cache_key(task_type, prompt, system_prompt, temperature, max_tokens, model, context)
        if use_cache and not model_override and cache_key in self._cache:
            cached = self._cache[cache_key].model_copy(update={"cache_hit": True})
            cached.model_call_id = await self._log_model_call(
                org_id=org_id,
                task_type=task_type,
                response=cached,
                agent_id=agent_id,
                trained_model_id=trained_model_id,
                trained_model_version=trained_model_version,
                used_fallback=used_fallback,
            )
            if autonomous_run and operator_id and org_id:
                await self._record_autonomous_llm(org_id, operator_id, cached)
            return cached

        # Canonical messages with safety hardening + untrusted-input fencing.
        # PII is redacted from user/retrieved content before it leaves the
        # platform (system prompt is developer-authored, left intact).
        redact = getattr(self.settings, "ai_pii_redaction_enabled", True)
        messages: list[Message] = []
        hardened_system = harden_system_prompt(system_prompt)
        if hardened_system:
            messages.append({"role": "system", "content": hardened_system})
        for c in context or []:
            role = c.get("role")
            content = c.get("content")
            if role in ("system", "user", "assistant") and content is not None:
                text = str(content)
                if redact and role != "system":
                    text = redact_pii(text)
                messages.append({"role": role, "content": text})
        user_prompt = redact_pii(prompt) if redact else prompt
        messages.append({"role": "user", "content": fence_untrusted(user_prompt)})

        # Build the failover priority chain.
        if model_override:
            priority = [("openai", model_override)]
        elif getattr(self.settings, "ai_failover_enabled", True):
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
            from app.services.ai_tracing import trace_span

            with trace_span("model_router.complete", task_type=task_type.value, org_id=org_id):
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

        cached_tokens = 0
        if resp.prompt_tokens or resp.completion_tokens:
            input_tokens = resp.prompt_tokens
            output_tokens = resp.completion_tokens
            cached_tokens = resp.cached_tokens
        else:
            input_tokens = self._estimate_tokens(prompt + (system_prompt or ""))
            output_tokens = self._estimate_tokens(resp.content)

        cost = self._estimate_cost(resp.model_used, input_tokens, output_tokens, cached_tokens)

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
        final.model_call_id = await self._log_model_call(
            org_id=org_id,
            task_type=task_type,
            response=final,
            agent_id=agent_id,
            trained_model_id=trained_model_id,
            trained_model_version=trained_model_version,
            used_fallback=used_fallback,
        )
        if autonomous_run and operator_id and org_id:
            await self._record_autonomous_llm(org_id, operator_id, final)
        # Output moderation (after cost is logged so spend is still accounted).
        try:
            await moderate_output(resp.content, self.settings, self._openai)
        except AIContentFlaggedError as exc:
            logger.warning("AI_OUTPUT_FLAGGED task_type=%s org_id=%s", task_type.value, org_id)
            await self._log_guardrail_event(org_id, task_type, "ai_output_flagged", [], str(exc))
            raise
        await self._log_guardrail_event(
            org_id,
            task_type,
            "ai_failover",
            result.attempts,
            f"final={resp.provider_used}/{resp.model_used}",
            latency_ms=latency_ms,
        )
        return final

    async def prepare_stream(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        context: list[dict] | None = None,
        org_id: str | None = None,
        model_override: str | None = None,
        agent_id: str | None = None,
        operator_id: str | None = None,
        autonomous_run: bool = False,
        trained_model_id: str | None = None,
        trained_model_version: int | None = None,
        used_fallback: bool = False,
    ) -> PreparedStream:
        """Run guardrails and build messages before opening an HTTP stream."""
        complexity = TASK_COMPLEXITY.get(task_type.value, "medium")
        model = model_override or self._resolve_model(task_type)

        if org_id:
            try:
                client = get_supabase_client(self.settings)
                policy = load_org_model_policy(client, org_id)
                assert_model_allowed(policy, provider="openai", model=model)
            except AIModelPolicyError:
                raise
            except Exception:  # noqa: BLE001
                logger.debug("model_policy_check_skipped org_id=%s", org_id, exc_info=True)

        if autonomous_run and operator_id and org_id:
            try:
                from app.services.autonomous_budget_service import (
                    AutonomousBudgetExceededError,
                    check_autonomous_llm_budget,
                    is_autonomous_operator,
                )

                client = get_supabase_client(self.settings)
                op_resp = (
                    client.table("operators")
                    .select("*")
                    .eq("org_id", org_id)
                    .eq("id", operator_id)
                    .limit(1)
                    .execute()
                )
                operator_row = op_resp.data[0] if op_resp.data else None
                if operator_row and is_autonomous_operator(operator_row):
                    est_in = self._estimate_tokens(prompt + (system_prompt or ""))
                    est_out = max(int(max_tokens or 0), est_in)
                    est_model = model_override or self._resolve_model(task_type)
                    est_spend = self._estimate_cost(est_model, est_in, est_out)
                    check_autonomous_llm_budget(
                        client,
                        org_id,
                        operator_row,
                        projected_tokens=est_in + est_out,
                        projected_spend_usd=est_spend,
                    )
            except AutonomousBudgetExceededError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("autonomous budget pre-check skipped org_id=%s error=%s", org_id, str(exc))

        try:
            if getattr(self.settings, "disable_ai", False):
                raise AIServiceDisabledError()
            enforce_rate_limit(org_id, self.settings)
            enforce_budget(org_id, self.settings)
            await moderate_input(f"{system_prompt or ''}\n{prompt}", self.settings, self._openai)
        except AIGuardrailError as exc:
            code = getattr(exc, "code", "AI_GUARDRAIL")
            logger.warning(
                "AI_GUARDRAIL_BLOCK task_type=%s org_id=%s code=%s", task_type.value, org_id, code
            )
            await self._log_guardrail_event(org_id, task_type, code, [], str(exc))
            raise

        redact = getattr(self.settings, "ai_pii_redaction_enabled", True)
        messages: list[Message] = []
        hardened_system = harden_system_prompt(system_prompt)
        if hardened_system:
            messages.append({"role": "system", "content": hardened_system})
        for c in context or []:
            role = c.get("role")
            content = c.get("content")
            if role in ("system", "user", "assistant") and content is not None:
                text = str(content)
                if redact and role != "system":
                    text = redact_pii(text)
                messages.append({"role": role, "content": text})
        user_prompt = redact_pii(prompt) if redact else prompt
        messages.append({"role": "user", "content": fence_untrusted(user_prompt)})

        if model_override:
            priority = [("openai", model_override)]
        elif getattr(self.settings, "ai_failover_enabled", True):
            priority = build_priority(getattr(self.settings, "preferred_ai_provider", "openai"), complexity)
        else:
            priority = [("openai", MODEL_TIERS[complexity]["openai"])]

        options = CompletionOptions(
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=OPENAI_REQUEST_TIMEOUT_S,
        )

        return PreparedStream(
            task_type=task_type,
            org_id=org_id,
            prompt=prompt,
            system_prompt=system_prompt,
            messages=messages,
            priority=priority,
            options=options,
            model=model,
            agent_id=agent_id,
            operator_id=operator_id,
            autonomous_run=autonomous_run,
            trained_model_id=trained_model_id,
            trained_model_version=trained_model_version,
            used_fallback=used_fallback,
        )

    async def stream(self, prepared: PreparedStream) -> AsyncIterator[ModelStreamEvent]:
        """Stream provider tokens after `prepare_stream()` pre-flight succeeds."""
        start = time.perf_counter()
        logger.info(
            "MODEL_STREAM_START task_type=%s priority=%s",
            prepared.task_type.value,
            [name for name, _ in prepared.priority],
        )
        attempts: list[tuple[str, str]] = []
        try:
            async for chunk in run_failover_stream(
                self._adapters,
                prepared.priority,
                prepared.messages,
                prepared.options,
                self._breaker,
            ):
                if chunk.delta:
                    yield ModelStreamEvent(delta=chunk.delta)
                if chunk.done and chunk.response is not None:
                    resp = chunk.response
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    cached_tokens = resp.cached_tokens
                    input_tokens = resp.prompt_tokens or self._estimate_tokens(
                        prepared.prompt + (prepared.system_prompt or "")
                    )
                    output_tokens = resp.completion_tokens or self._estimate_tokens(resp.content)
                    cost = self._estimate_cost(resp.model_used, input_tokens, output_tokens, cached_tokens)
                    final = ModelResponse(
                        provider=resp.provider_used,
                        model=resp.model_used,
                        content=resp.content,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost_usd=cost,
                        cache_hit=False,
                    )
                    try:
                        await moderate_output(resp.content, self.settings, self._openai)
                    except AIContentFlaggedError as exc:
                        logger.warning(
                            "AI_OUTPUT_FLAGGED task_type=%s org_id=%s",
                            prepared.task_type.value,
                            prepared.org_id,
                        )
                        await self._log_guardrail_event(
                            prepared.org_id,
                            prepared.task_type,
                            "ai_output_flagged",
                            [],
                            str(exc),
                        )
                        raise
                    logger.info(
                        "MODEL_STREAM_SUCCESS task_type=%s provider=%s model=%s duration_ms=%s",
                        prepared.task_type.value,
                        resp.provider_used,
                        resp.model_used,
                        latency_ms,
                    )
                    final.model_call_id = await self._log_model_call(
                        org_id=prepared.org_id,
                        task_type=prepared.task_type,
                        response=final,
                        agent_id=prepared.agent_id,
                        trained_model_id=prepared.trained_model_id,
                        trained_model_version=prepared.trained_model_version,
                        used_fallback=prepared.used_fallback,
                    )
                    if prepared.autonomous_run and prepared.operator_id and prepared.org_id:
                        await self._record_autonomous_llm(prepared.org_id, prepared.operator_id, final)
                    await self._log_guardrail_event(
                        prepared.org_id,
                        prepared.task_type,
                        "ai_failover",
                        attempts,
                        f"final={resp.provider_used}/{resp.model_used}",
                        latency_ms=latency_ms,
                    )
                    yield ModelStreamEvent(response=final)
                    return
        except ProviderInvalidResponseError as exc:
            self._log_call_failure(prepared.task_type, prepared.model, "varied", start, exc)
            await self._log_guardrail_event(
                prepared.org_id, prepared.task_type, "ai_failover_invalid", [], str(exc)
            )
            raise
        except AllProvidersFailedError as exc:
            self._log_call_failure(prepared.task_type, prepared.model, "varied", start, exc)
            await self._log_guardrail_event(
                prepared.org_id, prepared.task_type, "ai_failover_exhausted", [], str(exc)
            )
            raise

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

    async def _record_autonomous_llm(self, org_id: str, operator_id: str, response: ModelResponse) -> None:
        try:
            from app.services.autonomous_budget_service import (
                is_autonomous_operator,
                record_autonomous_llm_usage,
            )

            client = get_supabase_client(self.settings)
            op_resp = (
                client.table("operators")
                .select("*")
                .eq("org_id", org_id)
                .eq("id", operator_id)
                .limit(1)
                .execute()
            )
            operator_row = op_resp.data[0] if op_resp.data else None
            if not operator_row or not is_autonomous_operator(operator_row):
                return
            record_autonomous_llm_usage(
                client,
                org_id,
                operator_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                spend_usd=response.cost_usd,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "autonomous llm usage record skipped org_id=%s operator_id=%s error=%s",
                org_id,
                operator_id,
                str(exc),
            )

    def _estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        in_cost, cached_cost, out_cost = _MODEL_PRICING_PER_1K.get(model, (0.002, 0.002, 0.008))
        # cached_tokens is a subset of input_tokens; bill it at the cache rate.
        cached = max(0, min(cached_tokens, input_tokens))
        uncached_input = input_tokens - cached
        return round(
            (uncached_input / 1000 * in_cost)
            + (cached / 1000 * cached_cost)
            + (output_tokens / 1000 * out_cost),
            6,
        )

    async def _log_model_call(
        self,
        org_id: str | None,
        task_type: TaskType,
        response: ModelResponse,
        *,
        agent_id: str | None = None,
        trained_model_id: str | None = None,
        trained_model_version: int | None = None,
        used_fallback: bool = False,
    ) -> str | None:
        """Write the model_calls row and return its id (billing idempotency anchor)."""
        if not org_id:
            return None
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
                "agent_id": agent_id,
                "trained_model_id": trained_model_id,
                "trained_model_version": trained_model_version,
                "used_fallback": used_fallback,
            }
            resp = client.table("model_calls").insert(row).execute()
            if resp.data:
                return str(resp.data[0].get("id"))
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("model_calls insert failed: %s", str(exc))
            return None

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

    DEPARTMENT_MODEL_OVERRIDES: dict[str, str | None] = {
        "finance": None,
        "legal": None,
        "hr": None,
        "engineering": None,
        "marketing": None,
        "sales": None,
    }

    SENSITIVITY_ROUTING: dict[str, dict[str, Any] | str] = {
        "high": {
            "preferred_provider": "anthropic",
            "avoid": ["gemini"],
            "reason": "data residency + compliance",
        },
        "medium": "standard_tier",
        "low": "fast_tier",
    }

    VISION_MODELS: dict[str, str] = {
        "openai": "gpt-4o",
        "anthropic": "claude-3-5-sonnet-20241022",
    }

    def route_for_sensitivity(self, sensitivity: str, task_complexity: str = "medium") -> str:
        """Pick model tier with sensitivity-aware provider preference."""
        level = (sensitivity or "medium").strip().lower()
        rule = self.SENSITIVITY_ROUTING.get(level, "standard_tier")
        if isinstance(rule, dict):
            return MODEL_TIERS.get("high", MODEL_TIERS["medium"])["anthropic"]
        if rule == "fast_tier":
            return self._get_model_for_complexity("low")
        return self._get_model_for_complexity(task_complexity)

    async def route_with_cost_awareness(
        self,
        task_complexity: str,
        budget_remaining_usd: float | None = None,
    ) -> str:
        """Fall back to cheaper tier when budget is low."""
        if budget_remaining_usd is not None and budget_remaining_usd < 1.0:
            logger.info(
                "model_router_cost_downgrade budget_remaining_usd=%s complexity=%s->low",
                budget_remaining_usd,
                task_complexity,
            )
            return self._get_model_for_complexity("low")
        return self._get_model_for_complexity(task_complexity)

    async def route_for_modality(
        self,
        has_image: bool = False,
        has_audio: bool = False,
    ) -> str:
        if has_image:
            return self.VISION_MODELS.get("openai") or MODEL_TIERS["vision"]["openai"]
        if has_audio:
            audio_model = getattr(self.settings, "audio_transcription_model", None) or "gpt-4o-mini-transcribe"
            return str(audio_model)
        return self._get_model_for_complexity("medium")

    def _get_model_for_complexity(self, task_complexity: str) -> str:
        tier = MODEL_TIERS.get(task_complexity, MODEL_TIERS["medium"])
        return tier["openai"]

    async def get_model_for_department(
        self,
        department: str,
        task_complexity: str = "medium",
    ) -> str:
        override = self.DEPARTMENT_MODEL_OVERRIDES.get(department.strip().lower())
        if override:
            return override
        return self._get_model_for_complexity(task_complexity)

    async def route_with_vision(
        self,
        messages: list[dict],
        has_image: bool = False,
    ) -> str:
        _ = messages
        if has_image:
            return MODEL_TIERS["vision"]["openai"]
        return self._get_model_for_complexity("medium")


_model_router_singleton: ModelRouter | None = None


class ConfidenceRoutingMixin:
    """Confidence-aware routing helpers mixed into ModelRouter."""

    MIN_EVALUATIONS = 5
    MIN_OUTCOMES = 5


def _apply_confidence_routing_mixin() -> None:
    async def route_with_confidence(
        self: ModelRouter,
        task_type: str,
        initial_confidence: float,
        context_available: bool = True,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        _ = org_id
        confidence = max(0.0, min(1.0, float(initial_confidence)))
        if confidence >= 0.85:
            tier = "low"
            escalate = False
        elif confidence >= 0.65:
            tier = "medium"
            escalate = False
        elif confidence >= 0.40:
            tier = "medium" if context_available else "high"
            escalate = False
        else:
            tier = "high"
            escalate = True
        model = self._get_model_for_complexity(tier)
        return {
            "model": model,
            "tier": tier,
            "confidence": confidence,
            "escalate_to_human": escalate,
            "retrieve_more_context": confidence < 0.65 and not context_available,
        }

    async def route_with_historical_performance(
        self: ModelRouter,
        task_type: str,
        department: str | None,
        org_id: str,
        evaluation_service: Any,
    ) -> dict[str, Any]:
        best = await evaluation_service.recommend_best_model_for_task(org_id, task_type, department)
        if best.get("status") == "insufficient_data":
            model = self._get_model_for_complexity("medium")
            return {"model": model, "source": "default_routing", "task_type": task_type}
        return {
            "model": best.get("recommended_model"),
            "source": "historical_performance",
            "score": best.get("score"),
            "task_type": task_type,
        }

    async def route_with_outcome_score(
        self: ModelRouter,
        task_type: str,
        department: str | None,
        org_id: str,
        outcome_service: Any,
    ) -> dict[str, Any]:
        from app.services.model_selector import get_model_selector

        selector = get_model_selector(self.settings)
        base = await selector.select(org_id, {"intent": task_type, "department": department})
        model_name = str(base.get("ml_model_name") or base.get("model") or self._get_model_for_complexity("medium"))
        score_result = await outcome_service.get_model_outcome_score(org_id, model_name)
        if score_result.get("status") == "insufficient_data":
            return {**base, "routing_source": "default", "outcome_score": None}
        outcome_score = float(score_result.get("score") or 0)
        deprioritize = outcome_score < 0.35
        return {
            **base,
            "routing_source": "outcome_adjusted",
            "outcome_score": outcome_score,
            "deprioritized": deprioritize,
        }

    async def route_with_multistep_fallback(
        self: ModelRouter,
        task_type: str,
        confidence: float,
        attempts: int = 0,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        if attempts >= max_attempts:
            return {
                "model": self._get_model_for_complexity("high"),
                "escalate_to_human": True,
                "attempts": attempts,
                "max_attempts": max_attempts,
            }
        routed = await route_with_confidence(self, task_type, confidence, context_available=attempts > 0)
        if routed.get("escalate_to_human") and attempts + 1 < max_attempts:
            return await route_with_multistep_fallback(
                self, task_type, confidence + 0.1, attempts=attempts + 1, max_attempts=max_attempts
            )
        routed["attempts"] = attempts
        routed["max_attempts"] = max_attempts
        return routed

    def should_retrieve_more_context(self: ModelRouter, confidence: float, context_size: int) -> bool:
        return confidence < 0.65 and context_size < 8

    def should_escalate_to_human(self: ModelRouter, confidence: float, risk_level: str) -> bool:
        return confidence < 0.40 or str(risk_level or "").lower() == "high"

    def should_trigger_agent_debate(self: ModelRouter, confidence: float, task_complexity: str) -> bool:
        return confidence < 0.55 and task_complexity in ("high", "critical")

    def explain_routing_decision(
        self: ModelRouter,
        selected_model: str,
        task_type: str,
        confidence: float,
        routing_inputs: dict[str, Any],
    ) -> str:
        from app.services.ai_trust_layer import get_ai_trust_layer

        historical = routing_inputs.get("historical_score")
        parts = [
            f"Selected {selected_model} for {task_type} task.",
            f"Confidence: {confidence:.2f} ({get_ai_trust_layer().confidence_band(confidence)} band).",
        ]
        if historical is not None:
            parts.append(f"Historical performance score: {historical:.2f}.")
        if routing_inputs.get("escalate_to_human"):
            parts.append("Escalated to human review due to low confidence or high risk.")
        return " ".join(parts)

    ModelRouter.route_with_confidence = route_with_confidence  # type: ignore[attr-defined]
    ModelRouter.route_with_historical_performance = route_with_historical_performance  # type: ignore[attr-defined]
    ModelRouter.route_with_outcome_score = route_with_outcome_score  # type: ignore[attr-defined]
    ModelRouter.route_with_multistep_fallback = route_with_multistep_fallback  # type: ignore[attr-defined]
    ModelRouter.should_retrieve_more_context = should_retrieve_more_context  # type: ignore[attr-defined]
    ModelRouter.should_escalate_to_human = should_escalate_to_human  # type: ignore[attr-defined]
    ModelRouter.should_trigger_agent_debate = should_trigger_agent_debate  # type: ignore[attr-defined]
    ModelRouter.explain_routing_decision = explain_routing_decision  # type: ignore[attr-defined]


_apply_confidence_routing_mixin()


def get_model_router() -> ModelRouter:
    global _model_router_singleton
    if _model_router_singleton is None:
        _model_router_singleton = ModelRouter()
    return _model_router_singleton
