"""The LLM catalog is the single source of truth for routable chat models."""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.config import MODEL_TIERS, Settings, get_settings
from app.services.assistant_mode import AVAILABLE_MODELS, MODE_DEFAULT_MODELS, resolve_assistant_model
from app.services.llm_catalog import (
    LLM_CATALOG,
    PROVIDERS,
    get_llm_model,
    model_accepts_temperature,
    visible_llm_models,
)
from app.services.model_router import _MODEL_PRICING_PER_1K, ModelRouter, TaskType
from app.services.providers.provider_tool_router import resolve_provider_for_model

WEB_ROOT = Path(__file__).resolve().parents[3] / "apps" / "web"
_ID_RE = re.compile(r'\bid:\s*"([^"]+)"')


def _ts_block(path: Path, start_marker: str) -> str:
    """Text from ``start_marker`` to the closing bracket of that array literal."""
    text = path.read_text(encoding="utf-8")
    start = text.index(start_marker)
    # The array literal opens after "=", skipping type annotations like "Foo[]".
    open_idx = text.index("[", text.index("=", start))
    depth = 0
    for idx in range(open_idx, len(text)):
        if text[idx] == "[":
            depth += 1
        elif text[idx] == "]":
            depth -= 1
            if depth == 0:
                return text[open_idx: idx + 1]
    raise AssertionError(f"unterminated array after {start_marker!r} in {path}")


def _web_ids(rel_path: str, start_marker: str) -> list[str]:
    path = WEB_ROOT / rel_path
    if not path.exists():
        pytest.skip(f"web app not checked out next to backend: {path}")
    return _ID_RE.findall(_ts_block(path, start_marker))


def test_catalog_ids_unique_and_providers_have_adapters():
    ids = [m.id for m in LLM_CATALOG]
    assert len(ids) == len(set(ids))
    assert {m.provider for m in LLM_CATALOG} <= set(PROVIDERS)


def test_model_tiers_and_mode_defaults_use_current_catalog_models():
    for tier, by_provider in MODEL_TIERS.items():
        for provider, model_id in by_provider.items():
            entry = get_llm_model(model_id)
            assert entry is not None, f"MODEL_TIERS[{tier}][{provider}]={model_id} not in catalog"
            assert entry.provider == provider
            assert not entry.deprecated, f"MODEL_TIERS[{tier}][{provider}] uses deprecated {model_id}"
    for mode, model_id in MODE_DEFAULT_MODELS.items():
        assert model_id in AVAILABLE_MODELS, f"mode {mode} default {model_id} is not a visible model"


def test_available_models_hide_deprecated_but_resolver_still_accepts_them():
    assert "gpt-6-astra" in AVAILABLE_MODELS
    assert "claude-opus-5-5" in AVAILABLE_MODELS
    assert "gemini-3.8-flash" in AVAILABLE_MODELS
    for legacy in ("gpt-5.5", "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "gemini-2.5-pro"):
        assert legacy not in AVAILABLE_MODELS
        model, _task = resolve_assistant_model("standard", legacy)
        assert model == legacy, f"saved agent model {legacy} must keep routing"
    # Unknown / unsupported (no adapter) ids fall back to the mode default.
    model, _task = resolve_assistant_model("fast", "grok-3")
    assert model == MODE_DEFAULT_MODELS["fast"]


def test_pricing_is_derived_from_catalog():
    assert _MODEL_PRICING_PER_1K["gpt-6-astra"] == pytest.approx((0.010, 0.010, 0.050))
    assert _MODEL_PRICING_PER_1K["claude-opus-5-5"] == pytest.approx((0.004, 0.0002, 0.020))
    assert _MODEL_PRICING_PER_1K["gpt-5.5"] == pytest.approx((0.005, 0.0005, 0.030))
    assert "text-embedding-3-small" in _MODEL_PRICING_PER_1K
    for model in visible_llm_models():
        assert model.id in _MODEL_PRICING_PER_1K, f"current model {model.id} has no price"


def test_resolve_provider_for_model_uses_catalog():
    assert resolve_provider_for_model("gpt-6.1-sol") == "openai"
    assert resolve_provider_for_model("claude-fable-5-1") == "anthropic"
    assert resolve_provider_for_model("gemini-3.1-pro-preview") == "gemini"
    assert resolve_provider_for_model("claude-haiku-4-5-20251001") == "anthropic"
    assert resolve_provider_for_model("ft:gpt-4.1-mini:org:x") == "openai"


def test_temperature_omitted_for_claude_models_that_reject_it():
    assert model_accepts_temperature("claude-haiku-4-5") is True
    assert model_accepts_temperature("claude-sonnet-4-6") is True
    assert model_accepts_temperature("gpt-6.1-sol") is True
    for model_id in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-opus-4-8"):
        assert model_accepts_temperature(model_id) is False


def test_only_openai_fine_tunable_bases_are_marked_fine_tunable():
    tunable = {m.id for m in LLM_CATALOG if m.fine_tunable}
    assert tunable == {"gpt-4.1", "gpt-4.1-mini"}


def test_web_llm_lists_only_reference_catalog_models():
    catalog_ids = {m.id for m in LLM_CATALOG}
    visible_ids = {m.id for m in visible_llm_models()}

    registry_ids = _web_ids("lib/ml-registry-catalog.ts", "const LLM_BASE_MODELS")
    assert registry_ids, "could not parse LLM_BASE_MODELS"
    assert set(registry_ids) <= visible_ids, set(registry_ids) - visible_ids

    picker_ids = [
        i for i in _web_ids("components/gravitre/assistant/assistant-model-selector.tsx", "MODEL_OPTIONS =")
        if i != "auto"
    ]
    assert picker_ids, "could not parse MODEL_OPTIONS"
    assert set(picker_ids) <= visible_ids, set(picker_ids) - visible_ids

    trainable_ids = _web_ids("lib/training-ui-copy.ts", "TRAINABLE_BASE_MODELS =")
    assert trainable_ids
    assert set(trainable_ids) <= catalog_ids
    assert all(get_llm_model(i).fine_tunable for i in trainable_ids)  # type: ignore[union-attr]

    web_fine_tunable = re.findall(
        r'id:\s*"([^"]+)"[^}]*?fineTunable:\s*true',
        _ts_block(WEB_ROOT / "lib/ml-registry-catalog.ts", "const LLM_BASE_MODELS"),
        flags=re.S,
    )
    assert set(web_fine_tunable) == {m.id for m in LLM_CATALOG if m.fine_tunable}


@pytest.mark.asyncio
async def test_model_override_is_pinned_to_its_own_provider(mock_settings):
    router = ModelRouter(settings=mock_settings)
    with patch("app.services.model_router.moderate_input", AsyncMock()):
        prepared = await router.prepare_stream(
            task_type=TaskType.RAG_ANSWERING, prompt="hi", model_override="claude-sonnet-5-5"
        )
        gemini = await router.prepare_stream(
            task_type=TaskType.RAG_ANSWERING, prompt="hi", model_override="gemini-3.8-flash"
        )
    assert prepared.priority == [("anthropic", "claude-sonnet-5-5")]
    assert gemini.priority == [("gemini", "gemini-3.8-flash")]


@pytest.mark.asyncio
async def test_model_policy_checks_the_override_provider(mock_settings):
    """An anthropic-only allowlist must admit a Claude override (was checked as openai)."""
    router = ModelRouter(settings=mock_settings)
    policy = {"mode": "allowlist", "providers": ["anthropic"], "models": []}
    with (
        patch("app.services.model_router.get_supabase_client", return_value=MagicMock()),
        patch("app.services.model_router.load_org_model_policy", return_value=policy),
        patch("app.services.model_router.enforce_rate_limit"),
        patch("app.services.model_router.enforce_budget"),
        patch("app.services.model_router.moderate_input", AsyncMock()),
    ):
        prepared = await router.prepare_stream(
            task_type=TaskType.RAG_ANSWERING,
            prompt="hi",
            org_id="org-1",
            model_override="claude-opus-5-5",
        )
    assert prepared.priority == [("anthropic", "claude-opus-5-5")]


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        anthropic_api_key="",
        google_api_key="",
    )
    base.update(overrides)
    return Settings(**base)


def test_llm_catalog_endpoint_lists_visible_models_for_configured_providers():
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
    app.dependency_overrides[get_settings] = lambda: _settings()
    try:
        resp = TestClient(app).get("/api/models/llm-catalog")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["providers"] == ["openai"]
    ids = {m["id"] for m in body["models"]}
    assert "gpt-6-astra" in ids
    assert "gpt-5.5" not in ids  # deprecated: routable, not listed
    assert all(m["provider"] == "openai" for m in body["models"])


def test_llm_catalog_endpoint_requires_auth():
    from app.main import app

    app.dependency_overrides.clear()
    resp = TestClient(app).get("/api/models/llm-catalog")
    assert resp.status_code in (401, 403)
