"""Multi-provider tool-calling router (OpenAI, Anthropic, Gemini).

ReAct and unified-turn attach narrowed tools in OpenAI function schema; this module
translates to each provider's native tool format and normalizes responses back to
the OpenAI-compatible layout the rest of the stack expects.
"""
from __future__ import annotations

import importlib
import json
import time
import uuid
from typing import Any, Literal

from app.core.logging import get_logger
from app.services.providers.base import ProviderUnavailableError
from app.services.providers.tool_completion import (
    ToolCallSpec,
    ToolCompletionResult,
    make_openai_compatible_response,
    parse_json_args,
    tool_name_for_call_id,
)

logger = get_logger(__name__)

ProviderName = Literal["openai", "anthropic", "gemini"]


def _try_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return None


# Voice-latency follow-up (2026-09-05): _complete_anthropic_with_tools() built a
# fresh AsyncAnthropic() (and its underlying httpx.AsyncClient) on every single
# tool-calling completion — no TCP/TLS connection reuse across calls in this
# module, the same class of gap fixed in anthropic_adapter.py's AnthropicAdapter.
# ANTHROPIC_API_KEY is a single, process-wide setting, so a module-level
# key-keyed cache (not per-org) is safe here too.
_anthropic_tool_client_cache: dict[tuple[str, float], Any] = {}


def _get_anthropic_tool_client(anthropic: Any, api_key: str, timeout_s: float) -> Any:
    key = (api_key, timeout_s)
    client = _anthropic_tool_client_cache.get(key)
    if client is None:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s, max_retries=0)
        _anthropic_tool_client_cache[key] = client
    return client


def resolve_provider_for_model(model_id: str) -> ProviderName:
    from app.services.assistant_mode import AVAILABLE_MODELS

    model = str(model_id or "").strip()
    if model in AVAILABLE_MODELS:
        provider = str(AVAILABLE_MODELS[model]["provider"] or "").strip().lower()
        if provider in {"openai", "anthropic", "gemini"}:
            return provider  # type: ignore[return-value]
    lowered = model.lower()
    if lowered.startswith("claude") or "anthropic" in lowered:
        return "anthropic"
    if lowered.startswith("gemini"):
        return "gemini"
    return "openai"


def provider_tools_configured(provider: ProviderName, settings: Any) -> bool:
    if provider == "openai":
        return bool(getattr(settings, "openai_api_key", None))
    if provider == "anthropic":
        return bool(getattr(settings, "anthropic_api_key", None))
    if provider == "gemini":
        key = getattr(settings, "gemini_api_key", None) or getattr(settings, "google_api_key", None)
        return bool(key)
    return False


def openai_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in tools:
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = str(fn.get("name") or tool.get("name") or "").strip()
        if not name:
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        if not params:
            params = {"type": "object", "properties": {}}
        out.append(
            {
                "name": name,
                "description": str(fn.get("description") or tool.get("description") or ""),
                "input_schema": params,
            }
        )
    return out


def openai_messages_to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    anthropic: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def _flush_tool_results() -> None:
        nonlocal pending_tool_results
        if pending_tool_results:
            anthropic.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results = []

    for msg in messages:
        role = str(msg.get("role") or "")
        if role == "system":
            text = str(msg.get("content") or "").strip()
            if text:
                system_parts.append(text)
            continue
        if role == "user":
            _flush_tool_results()
            anthropic.append({"role": "user", "content": str(msg.get("content") or "")})
            continue
        if role == "assistant":
            _flush_tool_results()
            blocks: list[dict[str, Any]] = []
            content = msg.get("content")
            if content:
                blocks.append({"type": "text", "text": str(content)})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": str(tc.get("id") or uuid.uuid4()),
                        "name": str(fn.get("name") or ""),
                        "input": parse_json_args(fn.get("arguments")),
                    }
                )
            anthropic.append({"role": "assistant", "content": blocks or ""})
            continue
        if role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": str(msg.get("tool_call_id") or ""),
                    "content": str(msg.get("content") or ""),
                }
            )
    _flush_tool_results()
    system = "\n\n".join(system_parts) if system_parts else None
    return system, anthropic


def _parse_anthropic_response(resp: Any) -> ToolCompletionResult:
    content_parts: list[str] = []
    tool_calls: list[ToolCallSpec] = []
    for block in getattr(resp, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            text = getattr(block, "text", "") or ""
            if text:
                content_parts.append(str(text))
        elif btype == "tool_use":
            inp = getattr(block, "input", None) or {}
            tool_calls.append(
                ToolCallSpec(
                    id=str(getattr(block, "id", None) or uuid.uuid4()),
                    name=str(getattr(block, "name", None) or ""),
                    arguments=json.dumps(inp if isinstance(inp, dict) else {}),
                )
            )
    usage = getattr(resp, "usage", None)
    pt = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    ct = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    text = "\n".join(content_parts).strip() or None
    return ToolCompletionResult(
        content=text,
        tool_calls=tool_calls,
        prompt_tokens=pt,
        completion_tokens=ct,
        raw_response=resp,
    )


async def _complete_anthropic_with_tools(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: str,
    temperature: float | None,
) -> ToolCompletionResult:
    anthropic = _try_import("anthropic")
    if anthropic is None:
        raise ProviderUnavailableError("anthropic", "anthropic SDK is not installed")
    system_text, convo = openai_messages_to_anthropic(messages)
    native_tools = openai_tools_to_anthropic(tools)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": convo or [{"role": "user", "content": ""}],
        "max_tokens": 4096,
    }
    if system_text:
        kwargs["system"] = system_text
    if native_tools:
        kwargs["tools"] = native_tools
        if tool_choice and tool_choice != "none":
            kwargs["tool_choice"] = {"type": "auto"}
    if temperature is not None:
        kwargs["temperature"] = temperature
    client = _get_anthropic_tool_client(anthropic, api_key, 60.0)
    resp = await client.messages.create(**kwargs)
    return _parse_anthropic_response(resp)


def _sanitize_json_schema_for_gemini(schema: Any) -> Any:
    """Gemini function declarations reject array `items` without an explicit type."""
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in {"properties", "patternProperties"} and isinstance(value, dict):
            out[key] = {
                prop_key: _sanitize_json_schema_for_gemini(prop_val)
                for prop_key, prop_val in value.items()
            }
        elif key == "items":
            if isinstance(value, dict):
                sanitized = _sanitize_json_schema_for_gemini(value)
                if not sanitized.get("type"):
                    sanitized = {**sanitized, "type": "string"}
                out[key] = sanitized
            else:
                out[key] = {"type": "string"}
        elif key in {"anyOf", "oneOf", "allOf"} and isinstance(value, list):
            out[key] = [_sanitize_json_schema_for_gemini(item) for item in value]
        else:
            out[key] = value
    if out.get("type") == "array" and "items" not in out:
        out["items"] = {"type": "string"}
    return out


def openai_tools_to_gemini_declarations(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decls: list[dict[str, Any]] = []
    for tool in tools:
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = str(fn.get("name") or tool.get("name") or "").strip()
        if not name:
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        if not params:
            params = {"type": "object", "properties": {}}
        params = _sanitize_json_schema_for_gemini(params)
        decls.append(
            {
                "name": name,
                "description": str(fn.get("description") or tool.get("description") or ""),
                "parameters": params,
            }
        )
    return decls


def openai_messages_to_gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    injected_system = False

    for msg in messages:
        role = str(msg.get("role") or "")
        if role == "system":
            text = str(msg.get("content") or "").strip()
            if text:
                system_parts.append(text)
            continue
        if role == "user":
            text = str(msg.get("content") or "")
            if system_parts and not injected_system:
                text = f"{chr(10).join(system_parts)}{chr(10)}{chr(10)}{text}".strip()
                injected_system = True
            contents.append({"role": "user", "parts": [text]})
            continue
        if role == "assistant":
            parts: list[Any] = []
            content = msg.get("content")
            if content:
                parts.append(str(content))
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                parts.append(
                    {
                        "function_call": {
                            "name": str(fn.get("name") or ""),
                            "args": parse_json_args(fn.get("arguments")),
                        }
                    }
                )
            contents.append({"role": "model", "parts": parts or [""]})
            continue
        if role == "tool":
            fn_name = tool_name_for_call_id(messages, str(msg.get("tool_call_id") or ""))
            if not fn_name:
                fn_name = "unknown_tool"
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "name": fn_name,
                                "response": {"content": str(msg.get("content") or "")},
                            }
                        }
                    ],
                }
            )
    if system_parts and not injected_system and not contents:
        contents.append({"role": "user", "parts": [chr(10).join(system_parts)]})
    return contents


def _parse_gemini_response(resp: Any) -> ToolCompletionResult:
    content_parts: list[str] = []
    tool_calls: list[ToolCallSpec] = []
    candidates = getattr(resp, "candidates", None) or []
    if not candidates:
        return ToolCompletionResult(content=None, tool_calls=[], raw_response=resp)
    parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            content_parts.append(str(text))
        fn_call = getattr(part, "function_call", None)
        if fn_call is not None:
            name = str(getattr(fn_call, "name", None) or "")
            args = getattr(fn_call, "args", None) or {}
            if hasattr(args, "items"):
                args_dict = dict(args)
            else:
                args_dict = parse_json_args(str(args))
            tool_calls.append(
                ToolCallSpec(
                    id=str(uuid.uuid4()),
                    name=name,
                    arguments=json.dumps(args_dict),
                )
            )
    meta = getattr(resp, "usage_metadata", None)
    pt = int(getattr(meta, "prompt_token_count", 0) or 0) if meta else 0
    ct = int(getattr(meta, "candidates_token_count", 0) or 0) if meta else 0
    text = "\n".join(content_parts).strip() or None
    return ToolCompletionResult(
        content=text,
        tool_calls=tool_calls,
        prompt_tokens=pt,
        completion_tokens=ct,
        raw_response=resp,
    )


async def _complete_gemini_with_tools(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    temperature: float | None,
) -> ToolCompletionResult:
    genai = _try_import("google.generativeai")
    if genai is None:
        raise ProviderUnavailableError("gemini", "google-generativeai SDK is not installed")
    genai.configure(api_key=api_key)
    declarations = openai_tools_to_gemini_declarations(tools)
    tool_config = None
    if declarations:
        tool_config = [{"function_declarations": declarations}]
    gen_config: dict[str, Any] = {}
    if temperature is not None:
        gen_config["temperature"] = temperature
    gen_model = genai.GenerativeModel(model, tools=tool_config)
    contents = openai_messages_to_gemini_contents(messages)
    resp = await gen_model.generate_content_async(contents, generation_config=gen_config or None)
    return _parse_gemini_response(resp)


async def _complete_openai_with_tools(
    *,
    openai_client: Any,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: str,
    temperature: float | None,
) -> ToolCompletionResult:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    # OpenAI rejects tool_choice without tools ("'tool_choice' is only allowed
    # when 'tools' are specified"), and both callers can legitimately arrive with
    # an empty list: unified_turn_reasoning_service sets tool_choice="none" for
    # conversational turns while only attaching tools when it has some, and
    # react_engine passes `tools if tools else []`. Sending either key with no
    # tools turned those turns into a 400 that surfaced as an outcome_error
    # fallthrough. With no tools there is nothing for tool_choice to constrain,
    # so both keys are omitted rather than sent empty.
    if tools:
        kwargs["tools"] = list(tools)
        kwargs["tool_choice"] = tool_choice or "auto"
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = await openai_client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    message = choice.message
    tool_calls: list[ToolCallSpec] = []
    for tc in getattr(message, "tool_calls", None) or []:
        fn = getattr(tc, "function", None)
        tool_calls.append(
            ToolCallSpec(
                id=str(getattr(tc, "id", None) or uuid.uuid4()),
                name=str(getattr(fn, "name", None) or ""),
                arguments=str(getattr(fn, "arguments", None) or "{}"),
            )
        )
    usage = getattr(resp, "usage", None)
    pt = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    ct = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
    content = (getattr(message, "content", None) or "").strip() or None
    return ToolCompletionResult(
        content=content,
        tool_calls=tool_calls,
        prompt_tokens=pt,
        completion_tokens=ct,
        raw_response=resp,
    )


async def complete_with_tools(
    router: Any,
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: str = "auto",
    temperature: float | None = 0.2,
) -> Any:
    """Provider-aware tool completion; returns OpenAI-compatible response object."""
    from app.services.narrowed_tools import assert_tools_narrowed

    assert_tools_narrowed(tools, where="provider_tool_router.complete_with_tools")
    provider = resolve_provider_for_model(model)
    settings = getattr(router, "settings", None)
    start = time.perf_counter()

    if provider == "anthropic":
        api_key = str(getattr(settings, "anthropic_api_key", None) or "")
        if not api_key:
            raise ProviderUnavailableError("anthropic", "ANTHROPIC_API_KEY is not configured")
        result = await _complete_anthropic_with_tools(
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )
    elif provider == "gemini":
        api_key = str(getattr(settings, "gemini_key", None) or getattr(settings, "gemini_api_key", None) or "")
        if not api_key:
            raise ProviderUnavailableError("gemini", "GEMINI_API_KEY is not configured")
        result = await _complete_gemini_with_tools(
            api_key=api_key,
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
        )
    else:
        client = getattr(router, "_openai", None)
        if client is None:
            raise ProviderUnavailableError("openai", "OPENAI_API_KEY is not configured")
        result = await _complete_openai_with_tools(
            openai_client=client,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.debug(
        "provider_tool_complete provider=%s model=%s tools=%s tool_calls=%s ms=%s",
        provider,
        model,
        len(tools),
        len(result.tool_calls),
        elapsed_ms,
    )
    return make_openai_compatible_response(result)
