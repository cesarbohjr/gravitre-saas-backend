"""Tests for shared Tavily web research service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.web_research import TavilyNotConfiguredError, WebResearchNotConfiguredError, search_web


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.mark.asyncio
async def test_search_web_requires_api_key_when_no_provider():
    with pytest.raises(WebResearchNotConfiguredError):
        await search_web("latest AI news", settings=_settings(), org_id=None, client=None)


@pytest.mark.asyncio
async def test_search_web_parses_tavily_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"title": "Example", "url": "https://example.com", "content": "Snippet text"},
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.web_research.httpx.AsyncClient", return_value=mock_client):
        output = await search_web(
            "latest AI news",
            settings=_settings(tavily_api_key="tvly-test", web_research_provider="tavily"),
        )

    assert output["totalResults"] == 1
    assert output["provider"] == "tavily"
@pytest.mark.asyncio
async def test_search_web_blocks_when_org_hourly_circuit_open():
    from app.services.web_research import search_web

    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    select = MagicMock()
    table.select.return_value = select
    select.eq.return_value = select
    select.limit.return_value = select
    select.execute.return_value = MagicMock(data=[{"grounding_count": 500}])

    output = await search_web(
        "latest AI news",
        settings=_settings(
            gemini_api_key="gem-test",
            internet_research_enabled=True,
            grounding_org_hourly_circuit_limit=500,
        ),
        org_id="org-123",
        client=client,
    )
    assert output["totalResults"] == 0
    assert output.get("circuit_breaker", {}).get("blocked") is True
    assert "hourly circuit breaker" in (output.get("error") or "")

