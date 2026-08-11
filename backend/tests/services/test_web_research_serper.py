"""STA-341 — Serper primary + Tavily fallback tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.web_research import search_web


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        web_research_provider="serper",
        web_research_fallback_tavily=True,
        serper_api_key="serper-test-key",
        tavily_api_key="tvly-test",
    )
    base.update(overrides)
    return Settings(**base)


def _http_client(response: MagicMock) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.mark.asyncio
async def test_serper_primary_success_sets_provider_serper():
    serper_resp = MagicMock()
    serper_resp.status_code = 200
    serper_resp.json.return_value = {
        "organic": [
            {"title": "Fed", "link": "https://www.newyorkfed.org/effr", "snippet": "3.50-3.75%"},
        ]
    }
    with patch("app.services.web_research.httpx.AsyncClient", return_value=_http_client(serper_resp)):
        out = await search_web("federal funds rate", settings=_settings())
    assert out["provider"] == "serper"
    assert out["totalResults"] == 1
    assert out.get("fallback_from") is None


@pytest.mark.asyncio
async def test_serper_http_error_falls_back_to_tavily_visibly():
    serper_resp = MagicMock()
    serper_resp.status_code = 401
    serper_resp.json.return_value = {"message": "Unauthorized"}

    tavily_resp = MagicMock()
    tavily_resp.status_code = 200
    tavily_resp.json.return_value = {
        "results": [
            {"title": "Tavily hit", "url": "https://example.com/tavily", "content": "fallback snippet"},
        ]
    }

    clients = [_http_client(serper_resp), _http_client(tavily_resp)]

    def _factory(*_a, **_k):
        return clients.pop(0)

    with (
        patch("app.services.web_research.httpx.AsyncClient", side_effect=_factory),
        patch("app.services.web_research.logger") as mock_logger,
    ):
        out = await search_web("federal funds rate", settings=_settings())

    assert out["provider"] == "tavily"
    assert out["fallback_from"] == "serper"
    assert out["totalResults"] == 1
    # Visible warning logs for fallback (not silent)
    warn_msgs = " ".join(str(c) for c in mock_logger.warning.call_args_list)
    assert "web_research_fallback_to_tavily" in warn_msgs
    assert "web_research_fallback_served" in warn_msgs


@pytest.mark.asyncio
async def test_serper_missing_key_falls_back_when_enabled():
    tavily_resp = MagicMock()
    tavily_resp.status_code = 200
    tavily_resp.json.return_value = {
        "results": [{"title": "Ok", "url": "https://example.com", "content": "x"}],
    }
    with patch("app.services.web_research.httpx.AsyncClient", return_value=_http_client(tavily_resp)):
        out = await search_web(
            "test query",
            settings=_settings(serper_api_key=""),
        )
    assert out["provider"] == "tavily"
    assert out.get("fallback_from") == "serper"
