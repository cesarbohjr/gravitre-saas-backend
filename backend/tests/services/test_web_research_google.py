"""Tests for Google grounding web research provider."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.web_research_google import (
    GoogleGroundingNotConfiguredError,
    is_google_grounding_configured,
    search_google_grounding,
)


def _settings(**kwargs):
    base = {
        "gemini_api_key": "test-key",
        "google_cloud_project": "",
        "google_genai_use_vertexai": False,
        "google_cloud_location": "us-central1",
        "web_research_google_model": "gemini-2.5-flash",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_is_google_grounding_configured_with_api_key():
    assert is_google_grounding_configured(_settings())


def test_is_google_grounding_configured_with_vertex():
    assert is_google_grounding_configured(
        _settings(gemini_api_key="", google_genai_use_vertexai=True, google_cloud_project="gravitre-oauth")
    )


@pytest.mark.asyncio
async def test_search_google_grounding_parses_chunks():
    chunk = MagicMock()
    chunk.web.uri = "https://example.com/news"
    chunk.web.title = "Example News"

    candidate = MagicMock()
    candidate.grounding_metadata.grounding_chunks = [chunk]
    response = MagicMock()
    response.candidates = [candidate]
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 50

    fake_types = MagicMock()
    fake_types.GenerateContentConfig = MagicMock(return_value=MagicMock())
    fake_types.Tool = MagicMock(return_value=MagicMock())
    fake_types.GoogleSearch = MagicMock(return_value=MagicMock())

    with patch("app.services.web_research_google._build_genai_client") as mock_client, patch.dict(
        "sys.modules",
        {
            "google": MagicMock(),
            "google.genai": MagicMock(types=fake_types),
            "google.genai.types": fake_types,
        },
    ):
        mock_client.return_value.models.generate_content.return_value = response
        payload = await search_google_grounding("latest AI news", settings=_settings())

    assert payload["totalResults"] == 1
    assert payload["results"][0]["url"] == "https://example.com/news"
    assert payload["provider"] == "google_grounding"
    assert payload["usage"]["input_tokens"] == 100


@pytest.mark.asyncio
async def test_search_google_grounding_not_configured():
    with patch(
        "app.services.web_research_google._build_genai_client",
        side_effect=GoogleGroundingNotConfiguredError("missing credentials"),
    ):
        with pytest.raises(GoogleGroundingNotConfiguredError):
            await search_google_grounding("query", settings=_settings(gemini_api_key=""))
