"""Single source of truth for the chat LLMs Gravitre can route to.

Everything that needs a model list derives from ``LLM_CATALOG``: the assistant
model picker (``assistant_mode.AVAILABLE_MODELS``), cost estimation
(``model_router._MODEL_PRICING_PER_1K``), provider resolution
(``provider_tool_router.resolve_provider_for_model``) and the
``GET /api/models/llm-catalog`` endpoint.

``deprecated`` models are hidden from pickers but stay routable and priced, so
agents and workflows saved with an older id keep working. Only providers with an
adapter in ``app/services/providers/`` (openai, anthropic, gemini) belong here.

Sources (checked 2026-10-06):
- OpenAI: developers.openai.com/api/docs/models
- Anthropic: Claude API model table (claude-api skill, cached 2026-09-25)
- Google: ai.google.dev/gemini-api/docs/models and /pricing. Gemini 3.6–3.8
  Flash are discounted to $0.75 / $3.75 through 2026-12-31; the list price
  below is the standard rate that applies from 2027-01-01, so budgets stay
  conservative. Gemini 2.5 is restricted to prior users (deprecated here).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

LlmProvider = Literal["openai", "anthropic", "gemini"]
LlmTier = Literal["flagship", "balanced", "fast"]

PROVIDERS: tuple[LlmProvider, ...] = ("openai", "anthropic", "gemini")


@dataclass(frozen=True)
class LlmModel:
    id: str
    provider: LlmProvider
    label: str
    description: str
    tier: LlmTier
    # USD per 1M tokens; None = not priced (cost falls back to the router default).
    input_per_1m: float | None = None
    output_per_1m: float | None = None
    # Prompt-cache read rate; None = billed at the input rate.
    cached_input_per_1m: float | None = None
    context_window: int | None = None
    # OpenAI fine-tuning API supports this base (SFT/DPO via the training worker).
    fine_tunable: bool = False
    # Hidden from pickers; still accepted for saved agents / explicit overrides.
    deprecated: bool = False
    preview: bool = False
    # Claude 4.7+/5.x reject non-default sampling params with a 400.
    accepts_temperature: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "label": self.label,
            "description": self.description,
            "tier": self.tier,
            "input_per_1m": self.input_per_1m,
            "output_per_1m": self.output_per_1m,
            "cached_input_per_1m": self.cached_input_per_1m,
            "context_window": self.context_window,
            "fine_tunable": self.fine_tunable,
            "deprecated": self.deprecated,
            "preview": self.preview,
        }


LLM_CATALOG: tuple[LlmModel, ...] = (
    # --- OpenAI -------------------------------------------------------------
    LlmModel("gpt-6-astra", "openai", "GPT-6 Astra", "OpenAI flagship for complex reasoning and agents",
             "flagship", 10.0, 50.0, context_window=1_050_000),
    LlmModel("gpt-6.1-sol", "openai", "GPT-6.1 Sol", "Near-flagship quality at a fraction of the cost",
             "balanced", 2.0, 10.0, context_window=1_050_000),
    LlmModel("gpt-6-luna", "openai", "GPT-6 Luna", "Fast, low-cost OpenAI model for high volume",
             "fast", 0.10, 0.50, context_window=1_050_000),
    LlmModel("gpt-4.1", "openai", "GPT-4.1", "Fine-tunable OpenAI base (SFT/DPO)",
             "balanced", 2.0, 8.0, fine_tunable=True),
    LlmModel("gpt-4.1-mini", "openai", "GPT-4.1 Mini", "Cost-efficient fine-tunable OpenAI base",
             "fast", 0.40, 1.60, fine_tunable=True),
    # Previous OpenAI lineup — kept routable for saved agents.
    LlmModel("gpt-5.5", "openai", "GPT-5.5", "Previous OpenAI flagship",
             "flagship", 5.0, 30.0, cached_input_per_1m=0.50, deprecated=True),
    LlmModel("gpt-5.4-mini", "openai", "GPT-5.4 Mini", "Previous fast OpenAI model",
             "fast", 0.75, 4.50, deprecated=True),
    LlmModel("gpt-5.4-nano", "openai", "GPT-5.4 Nano", "Previous cheapest OpenAI model",
             "fast", 0.20, 1.25, deprecated=True),
    LlmModel("gpt-4o", "openai", "GPT-4o", "Legacy multimodal model", "balanced", deprecated=True),
    LlmModel("gpt-4o-mini", "openai", "GPT-4o Mini", "Legacy small multimodal model", "fast", deprecated=True),
    LlmModel("o3-mini", "openai", "o3-mini", "Legacy reasoning model", "balanced", deprecated=True),
    LlmModel("o4-mini", "openai", "o4-mini", "Legacy compact reasoning model", "balanced", deprecated=True),
    # --- Anthropic ----------------------------------------------------------
    LlmModel("claude-fable-5-1", "anthropic", "Claude Fable 5.1",
             "Anthropic's most capable model for the hardest long-horizon work",
             "flagship", 10.0, 50.0, cached_input_per_1m=0.25, context_window=1_000_000,
             accepts_temperature=False),
    LlmModel("claude-opus-5-5", "anthropic", "Claude Opus 5.5",
             "Frontier Claude for deep reasoning, coding, and agents",
             "flagship", 4.0, 20.0, cached_input_per_1m=0.20, context_window=1_000_000,
             accepts_temperature=False),
    LlmModel("claude-sonnet-5-5", "anthropic", "Claude Sonnet 5.5",
             "Balanced Claude for writing, coding, and everyday agent work",
             "balanced", 2.0, 10.0, cached_input_per_1m=0.20, context_window=1_000_000,
             accepts_temperature=False),
    LlmModel("claude-haiku-4-5", "anthropic", "Claude Haiku 4.5",
             "Fastest Claude for routing, triage, and high-QPS agents",
             "fast", 1.0, 5.0, cached_input_per_1m=0.10, context_window=200_000),
    # Previous Claude ids — kept routable for saved agents.
    LlmModel("claude-sonnet-4-6", "anthropic", "Claude Sonnet 4.6", "Previous Claude Sonnet",
             "balanced", 3.0, 15.0, deprecated=True),
    LlmModel("claude-opus-4-6", "anthropic", "Claude Opus 4.6", "Previous Claude Opus",
             "flagship", 5.0, 25.0, deprecated=True),
    LlmModel("claude-haiku-4-5-20251001", "anthropic", "Claude Haiku 4.5 (2025-10-01)",
             "Dated Claude Haiku 4.5 snapshot", "fast", 1.0, 5.0, cached_input_per_1m=0.10, deprecated=True),
    LlmModel("claude-3-5-sonnet-20241022", "anthropic", "Claude 3.5 Sonnet", "Retired Claude model",
             "balanced", deprecated=True),
    # --- Google Gemini ------------------------------------------------------
    LlmModel("gemini-3.1-pro-preview", "gemini", "Gemini 3.1 Pro (preview)",
             "Google's most capable Gemini for long context and rich media",
             "flagship", 2.0, 12.0, cached_input_per_1m=0.20, preview=True),
    LlmModel("gemini-3.8-flash", "gemini", "Gemini 3.8 Flash", "Most intelligent Gemini Flash",
             "balanced", 1.50, 7.50, cached_input_per_1m=0.15),
    LlmModel("gemini-3.7-flash", "gemini", "Gemini 3.7 Flash", "Stable Gemini Flash",
             "balanced", 1.50, 7.50, cached_input_per_1m=0.15),
    LlmModel("gemini-3.6-flash", "gemini", "Gemini 3.6 Flash", "Stable Gemini Flash",
             "balanced", 1.50, 7.50, cached_input_per_1m=0.15),
    LlmModel("gemini-3.5-flash", "gemini", "Gemini 3.5 Flash", "Stable Gemini Flash",
             "balanced", 1.50, 9.00, cached_input_per_1m=0.15),
    LlmModel("gemini-3.5-flash-lite", "gemini", "Gemini 3.5 Flash-Lite", "Fast, low-cost Gemini",
             "fast", 0.30, 2.50),
    LlmModel("gemini-3.1-flash-lite", "gemini", "Gemini 3.1 Flash-Lite", "Cheapest Gemini for bulk work",
             "fast", 0.25, 1.50, cached_input_per_1m=0.025),
    # Gemini 2.x is restricted to prior users — kept routable for them.
    LlmModel("gemini-2.5-pro", "gemini", "Gemini 2.5 Pro", "Previous Gemini Pro",
             "flagship", 1.25, 10.0, deprecated=True),
    LlmModel("gemini-2.5-flash", "gemini", "Gemini 2.5 Flash", "Previous Gemini Flash",
             "fast", 0.0875, 0.35, deprecated=True),
    LlmModel("gemini-2.0-flash", "gemini", "Gemini 2.0 Flash", "Legacy Gemini Flash", "fast", deprecated=True),
)

_BY_ID: dict[str, LlmModel] = {m.id: m for m in LLM_CATALOG}


def get_llm_model(model_id: str | None) -> LlmModel | None:
    return _BY_ID.get(str(model_id or "").strip())


def is_known_llm(model_id: str | None) -> bool:
    return get_llm_model(model_id) is not None


def provider_for_model(model_id: str | None) -> LlmProvider | None:
    model = get_llm_model(model_id)
    return model.provider if model else None


def visible_llm_models(providers: set[str] | None = None) -> list[LlmModel]:
    """Non-deprecated models, optionally limited to the given providers."""
    return [
        m for m in LLM_CATALOG
        if not m.deprecated and (providers is None or m.provider in providers)
    ]


def model_accepts_temperature(model_id: str | None) -> bool:
    """False for models that 400 on a non-default ``temperature``.

    Unknown Claude ids are matched by family so dated or newer snapshots of the
    same line behave like the catalog entry.
    """
    model = get_llm_model(model_id)
    if model is not None:
        return model.accepts_temperature
    lowered = str(model_id or "").strip().lower()
    return not lowered.startswith(
        ("claude-fable", "claude-mythos", "claude-opus-5", "claude-sonnet-5",
         "claude-opus-4-7", "claude-opus-4-8")
    )


def pricing_per_1k() -> dict[str, tuple[float, float, float]]:
    """(input, cached_input, output) USD per 1K tokens for every priced model."""
    out: dict[str, tuple[float, float, float]] = {}
    for m in LLM_CATALOG:
        if m.input_per_1m is None or m.output_per_1m is None:
            continue
        cached = m.cached_input_per_1m if m.cached_input_per_1m is not None else m.input_per_1m
        out[m.id] = (m.input_per_1m / 1000, cached / 1000, m.output_per_1m / 1000)
    return out


def configured_llm_providers(settings: Any) -> set[str]:
    """Providers whose API key is configured (mirrors ModelRouter adapter keys)."""
    configured: set[str] = set()
    if str(getattr(settings, "openai_api_key", "") or "").strip():
        configured.add("openai")
    if str(getattr(settings, "anthropic_api_key", "") or "").strip():
        configured.add("anthropic")
    gemini_key = (
        getattr(settings, "gemini_key", "")
        or getattr(settings, "gemini_api_key", "")
        or getattr(settings, "google_api_key", "")
        or ""
    )
    if str(gemini_key).strip():
        configured.add("gemini")
    return configured
