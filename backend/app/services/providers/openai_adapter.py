"""OpenAI provider adapter."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.logging import get_logger
from app.services.providers.base import (
    CompletionOptions,
    Message,
    ProviderAdapter,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderResponse,
    ProviderUnavailableError,
)

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3


def _supports_custom_temperature(model: str) -> bool:
    """GPT-5 / o-series models reject non-default temperature."""
    lowered = model.lower()
    if lowered.startswith(("gpt-5", "o1", "o3", "o4")):
        return False
    return True


class OpenAIAdapter(ProviderAdapter):
    provider_name = "openai"
    supported_models = ["gpt-5.5", "gpt-5.4-mini", "gpt-4.1", "text-embedding-3-small"]

    def __init__(
        self,
        client_getter: Callable[[], AsyncOpenAI | None],
        api_key_getter: Callable[[], str],
        timeout_s: float = 30.0,
    ) -> None:
        # client_getter reads the live AsyncOpenAI client (so tests that swap the
        # router's client are honored). api_key_getter is for the sync embed client.
        self._client_getter = client_getter
        self._api_key_getter = api_key_getter
        self._timeout_s = timeout_s

    def is_available(self) -> bool:
        return self._client_getter() is not None

    async def complete(
        self,
        messages: list[Message],
        model: str,
        options: CompletionOptions,
    ) -> ProviderResponse:
        client = self._client_getter()
        if client is None:
            raise ProviderUnavailableError("openai", "OPENAI_API_KEY is not configured")

        payload = [{"role": m["role"], "content": m["content"]} for m in messages]
        start = time.perf_counter()
        delay = 0.4
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": payload,
                }
                if _supports_custom_temperature(model):
                    kwargs["temperature"] = (
                        options.temperature if options.temperature is not None else 0.2
                    )
                if options.max_tokens is not None:
                    kwargs["max_tokens"] = options.max_tokens
                resp = await client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content or ""
                if not content.strip():
                    raise RuntimeError("Model returned empty response")
                latency_ms = (time.perf_counter() - start) * 1000
                pt, ct, cached = self._usage(resp)
                return ProviderResponse(
                    content=content,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=pt + ct,
                    cached_tokens=cached,
                    model_used=model,
                    provider_used=self.provider_name,
                    latency_ms=latency_ms,
                    raw_response=resp,
                )
            except (BadRequestError, PermissionDeniedError) as exc:
                # Input / policy problem — not a provider availability issue.
                raise ProviderInvalidResponseError("openai", str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    break
                sleep_for = delay
                if isinstance(exc, RateLimitError):
                    sleep_for = max(delay, self._retry_after(exc, 2.0))
                logger.warning(
                    "openai retry model=%s attempt=%s error=%s", model, attempt + 1, str(exc)
                )
                await asyncio.sleep(sleep_for)
                delay *= 2

        # Exhausted retries -> map to a typed, failover-friendly error.
        if isinstance(last_exc, RateLimitError):
            raise ProviderRateLimitedError("openai", str(last_exc)) from last_exc
        if isinstance(last_exc, AuthenticationError):
            raise ProviderUnavailableError("openai", f"auth error: {last_exc}") from last_exc
        raise ProviderUnavailableError("openai", str(last_exc)) from last_exc

    def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        api_key = self._api_key_getter()
        if not api_key:
            raise ProviderUnavailableError("openai", "OPENAI_API_KEY is not configured")
        try:
            client = OpenAI(api_key=api_key, timeout=self._timeout_s, max_retries=2)
            resp = client.embeddings.create(model=model, input=text)
            return list(resp.data[0].embedding)
        except (BadRequestError, PermissionDeniedError) as exc:
            raise ProviderInvalidResponseError("openai", str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitedError("openai", str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError("openai", str(exc)) from exc

    @staticmethod
    def _usage(resp: Any) -> tuple[int, int, int]:
        raw = getattr(resp, "usage", None)
        if raw is None:
            return 0, 0, 0
        prompt = int(getattr(raw, "prompt_tokens", 0) or 0)
        completion = int(getattr(raw, "completion_tokens", 0) or 0)
        details = getattr(raw, "prompt_tokens_details", None)
        cached = int(getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
        return prompt, completion, cached

    @staticmethod
    def _retry_after(exc: Exception, default: float) -> float:
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
