"""Google Gemini provider adapter.

Gemini has no native system role: the system message is prepended to the first
user message. Roles map "assistant" -> "model", "user" -> "user".
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
    retry_provider_call,
)

logger = get_logger(__name__)


def _try_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return None


class GeminiAdapter(ProviderAdapter):
    provider_name = "gemini"
    supported_models = ["gemini-2.5-flash", "gemini-2.5-pro"]

    def __init__(self, api_key_getter: Callable[[], str]) -> None:
        self._api_key_getter = api_key_getter

    def is_available(self) -> bool:
        return bool(self._api_key_getter()) and _try_import("google.generativeai") is not None

    def _to_contents(self, messages: list[Message]) -> list[dict[str, Any]]:
        system_text, convo = extract_system(messages)
        contents: list[dict[str, Any]] = []
        injected_system = False
        for m in convo:
            role = "model" if m["role"] == "assistant" else "user"
            text = m["content"]
            if role == "user" and system_text and not injected_system:
                text = f"{system_text}\n\n{text}"
                injected_system = True
            contents.append({"role": role, "parts": [text]})
        if system_text and not injected_system:
            contents.insert(0, {"role": "user", "parts": [system_text]})
        return contents

    async def complete(
        self,
        messages: list[Message],
        model: str,
        options: CompletionOptions,
    ) -> ProviderResponse:
        api_key = self._api_key_getter()
        if not api_key:
            raise ProviderUnavailableError("gemini", "GEMINI_API_KEY is not configured")
        genai = _try_import("google.generativeai")
        if genai is None:
            raise ProviderUnavailableError("gemini", "google-generativeai SDK is not installed")

        contents = self._to_contents(messages)
        gen_config: dict[str, Any] = {}
        if options.temperature is not None:
            gen_config["temperature"] = options.temperature
        if options.max_tokens is not None:
            gen_config["max_output_tokens"] = options.max_tokens

        async def _attempt() -> ProviderResponse:
            start = time.perf_counter()
            try:
                genai.configure(api_key=api_key)
                gen_model = genai.GenerativeModel(model)
                resp = await gen_model.generate_content_async(
                    contents,
                    generation_config=gen_config or None,
                )
            except Exception as exc:  # noqa: BLE001
                raise self._map_error(exc) from exc
            content = getattr(resp, "text", "") or ""
            if not content.strip():
                raise ProviderUnavailableError("gemini", "Model returned empty response")
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

        return await retry_provider_call(_attempt)

    def embed(self, text: str, model: str = "models/text-embedding-004") -> list[float]:
        api_key = self._api_key_getter()
        if not api_key:
            raise ProviderUnavailableError("gemini", "GEMINI_API_KEY is not configured")
        genai = _try_import("google.generativeai")
        if genai is None:
            raise ProviderUnavailableError("gemini", "google-generativeai SDK is not installed")
        try:
            genai.configure(api_key=api_key)
            result = genai.embed_content(model=model, content=text)
            embedding = result["embedding"] if isinstance(result, dict) else getattr(result, "embedding", None)
            if embedding is None:
                raise ProviderUnavailableError("gemini", "no embedding returned")
            return list(embedding)
        except ProviderUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError("gemini", f"gemini embed failed: {exc}") from exc

    @staticmethod
    def _usage(resp: Any) -> tuple[int, int]:
        meta = getattr(resp, "usage_metadata", None)
        if meta is None:
            return 0, 0
        return (
            int(getattr(meta, "prompt_token_count", 0) or 0),
            int(getattr(meta, "candidates_token_count", 0) or 0),
        )

    @staticmethod
    def _map_error(exc: Exception):
        exceptions = _try_import("google.api_core.exceptions")
        if exceptions is not None:
            resource_exhausted = getattr(exceptions, "ResourceExhausted", ())
            invalid_argument = getattr(exceptions, "InvalidArgument", ())
            permission_denied = getattr(exceptions, "PermissionDenied", ())
            if resource_exhausted and isinstance(exc, resource_exhausted):
                return ProviderRateLimitedError("gemini", str(exc))
            if (invalid_argument and isinstance(exc, invalid_argument)) or (
                permission_denied and isinstance(exc, permission_denied)
            ):
                return ProviderInvalidResponseError("gemini", str(exc))
        return ProviderUnavailableError("gemini", str(exc))
