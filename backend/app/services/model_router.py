from __future__ import annotations

import asyncio
import hashlib
import json
import time
from enum import StrEnum
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


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
    TaskType.CLASSIFICATION: "gpt-4o-mini",
    TaskType.INTENT_DETECTION: "gpt-4o-mini",
    TaskType.WORKFLOW_PLANNING: "claude-3-5-sonnet",
    TaskType.DECISION_REASONING: "claude-3-5-sonnet",
    TaskType.AGENT_DEBATE: "claude-3-opus",
    TaskType.SUMMARIZATION: "gpt-4o-mini",
    TaskType.CONTENT_GENERATION: "gpt-4o",
    TaskType.RAG_ANSWERING: "gpt-4o",
    TaskType.OPTIMIZATION_ANALYSIS: "gpt-4o",
}

_MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.005, 0.015),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-opus": (0.015, 0.075),
    "gemini-1.5-pro": (0.0035, 0.0105),
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
        self._openai = AsyncOpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None
        self._anthropic = (
            AsyncAnthropic(api_key=self.settings.anthropic_api_key) if self.settings.anthropic_api_key else None
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
        provider = self._provider_for_model(model)
        cache_key = self._cache_key(task_type, prompt, system_prompt, temperature, max_tokens, model, context)

        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key].model_copy(update={"cache_hit": True})
            await self._log_model_call(org_id=org_id, task_type=task_type, response=cached)
            return cached

        start = time.perf_counter()
        response_text = await self._retry_complete(
            provider=provider,
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            context=context,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
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
        await self._log_model_call(org_id=org_id, task_type=task_type, response=final)
        return final

    def _resolve_model(self, task_type: TaskType) -> str:
        if task_type in {TaskType.CLASSIFICATION, TaskType.INTENT_DETECTION, TaskType.SUMMARIZATION}:
            return self.settings.default_fast_model or DEFAULT_ROUTES[task_type]
        if task_type in {TaskType.WORKFLOW_PLANNING, TaskType.DECISION_REASONING, TaskType.AGENT_DEBATE}:
            return self.settings.default_reasoning_model or DEFAULT_ROUTES[task_type]
        return DEFAULT_ROUTES[task_type]

    def _provider_for_model(self, model: str) -> str:
        normalized = model.lower()
        if normalized.startswith("claude"):
            return "anthropic"
        if normalized.startswith("gemini"):
            return "google"
        return "openai"

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
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        context: list[dict] | None,
    ) -> str:
        delay = 0.4
        for attempt in range(3):
            try:
                if provider == "openai":
                    return await self._openai_complete(model, prompt, system_prompt, temperature, max_tokens, context)
                if provider == "anthropic":
                    return await self._anthropic_complete(model, prompt, system_prompt, temperature, max_tokens, context)
                return await self._google_complete(model, prompt, system_prompt, temperature, max_tokens, context)
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    raise
                logger.warning("Model completion retrying: %s", str(exc))
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    async def _openai_complete(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        context: list[dict] | None,
    ) -> str:
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
        return resp.choices[0].message.content or ""

    async def _anthropic_complete(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        context: list[dict] | None,
    ) -> str:
        if not self._anthropic:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        messages = list(context or [])
        messages.append({"role": "user", "content": prompt})
        resp = await self._anthropic.messages.create(
            model=model,
            system=system_prompt or "",
            max_tokens=max_tokens or 1000,
            temperature=temperature if temperature is not None else 0.2,
            messages=messages,
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")

    async def _google_complete(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        _context: list[dict] | None,
    ) -> str:
        if not self.settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2 if temperature is None else temperature,
                "maxOutputTokens": max_tokens or 1000,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params={"key": self.settings.google_api_key}, json=body)
            resp.raise_for_status()
            data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return " ".join(str(part.get("text") or "") for part in parts).strip()

    def _parse_structured(self, text: str, schema: type[BaseModel]) -> dict[str, Any]:
        normalized = text.strip()
        if normalized.startswith("```"):
            normalized = normalized.replace("```json", "").replace("```", "").strip()
        if not normalized:
            raise ValueError("Model returned empty response for structured output")
        payload = json.loads(normalized)
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
