"""Anthropic (Claude) provider adapter.

System messages are extracted and passed as the top-level `system` parameter.
Anthropic has no native embeddings, so embed() uses Voyage AI (voyage-3), the
Anthropic-ecosystem embedding option, when VOYAGE_API_KEY is configured.
"""
from __future__ import annotations

import importlib
import time
from typing import Any, Callable

from app.core.logging import get_logger
from app.services.providers.base import (
    CompletionOptions,
    Message,
    ProviderAdapter,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderResponse,
    ProviderUnavailableError,
    extract_system,
)

logger = get_logger(__name__)

_DEFAULT_MAX_TOKENS = 1024


def _try_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return None


class AnthropicAdapter(ProviderAdapter):
    provider_name = "anthropic"
    supported_models = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"]

    def __init__(
        self,
        api_key_getter: Callable[[], str],
        voyage_key_getter: Callable[[], str],
        timeout_s: float = 30.0,
    ) -> None:
        self._api_key_getter = api_key_getter
        self._voyage_key_getter = voyage_key_getter
        self._timeout_s = timeout_s

    def is_available(self) -> bool:
        return bool(self._api_key_getter()) and _try_import("anthropic") is not None

    async def complete(
        self,
        messages: list[Message],
        model: str,
        options: CompletionOptions,
    ) -> ProviderResponse:
        api_key = self._api_key_getter()
        if not api_key:
            raise ProviderUnavailableError("anthropic", "ANTHROPIC_API_KEY is not configured")
        anthropic = _try_import("anthropic")
        if anthropic is None:
            raise ProviderUnavailableError("anthropic", "anthropic SDK is not installed")

        system_text, convo = extract_system(messages)
        native = [{"role": m["role"], "content": m["content"]} for m in convo]
        if not native:
            native = [{"role": "user", "content": system_text or ""}]
            system_text = None

        start = time.perf_counter()
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key, timeout=self._timeout_s, max_retries=0)
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": native,
                "max_tokens": options.max_tokens or _DEFAULT_MAX_TOKENS,
            }
            if system_text:
                kwargs["system"] = system_text
            if options.temperature is not None:
                kwargs["temperature"] = options.temperature
            resp = await client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._map_error(anthropic, exc) from exc

        content = self._extract_text(resp)
        if not content.strip():
            raise ProviderUnavailableError("anthropic", "Model returned empty response")
        latency_ms = (time.perf_counter() - start) * 1000
        pt, ct = self._usage(resp)
        return ProviderResponse(
            content=content,
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=pt + ct,
            model_used=model,
            provider_used=self.provider_name,
            latency_ms=latency_ms,
            raw_response=resp,
        )

    def embed(self, text: str, model: str = "voyage-3") -> list[float]:
        voyage_key = self._voyage_key_getter()
        if not voyage_key:
            raise ProviderUnavailableError("anthropic", "VOYAGE_API_KEY is not configured (no Anthropic-native embeddings)")
        voyageai = _try_import("voyageai")
        if voyageai is None:
            raise ProviderUnavailableError("anthropic", "voyageai SDK is not installed")
        try:
            client = voyageai.Client(api_key=voyage_key)
            result = client.embed([text], model=model)
            return list(result.embeddings[0])
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError("anthropic", f"voyage embed failed: {exc}") from exc

    @staticmethod
    def _extract_text(resp: Any) -> str:
        blocks = getattr(resp, "content", None) or []
        parts: list[str] = []
        for block in blocks:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)

    @staticmethod
    def _usage(resp: Any) -> tuple[int, int]:
        raw = getattr(resp, "usage", None)
        if raw is None:
            return 0, 0
        return int(getattr(raw, "input_tokens", 0) or 0), int(getattr(raw, "output_tokens", 0) or 0)

    @staticmethod
    def _map_error(anthropic: Any, exc: Exception):
        rate_limit = getattr(anthropic, "RateLimitError", ())
        bad_request = getattr(anthropic, "BadRequestError", ())
        permission = getattr(anthropic, "PermissionDeniedError", ())
        if rate_limit and isinstance(exc, rate_limit):
            return ProviderRateLimitedError("anthropic", str(exc))
        if (bad_request and isinstance(exc, bad_request)) or (permission and isinstance(exc, permission)):
            return ProviderInvalidResponseError("anthropic", str(exc))
        return ProviderUnavailableError("anthropic", str(exc))
