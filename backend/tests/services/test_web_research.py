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
        output = await search_web("latest AI news", settings=_settings(tavily_api_key="tvly-test"))

    assert output["totalResults"] == 1
    assert output["results"][0]["title"] == "Example"
    assert output["sources"][0]["url"] == "https://example.com"
