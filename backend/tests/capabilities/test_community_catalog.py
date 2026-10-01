from unittest.mock import AsyncMock

import pytest

from app.capabilities import community_catalog


@pytest.mark.asyncio
async def test_official_catalog_filters_by_query_and_source(monkeypatch):
    async def fake_fetch(source):
        return [
            {
                "id": f"{source.key}:skills/example",
                "name": "Example Skill",
                "kind": "skill",
                "publisher": source.publisher,
                "sourceKey": source.key,
                "sourceName": source.name,
                "repositoryUrl": source.repository_url,
                "branch": source.branch,
                "packagePath": "skills/example",
                "sourceUrl": f"{source.repository_url}/tree/main/skills/example",
                "trust": "official",
                "status": "available_for_review",
                "runtimeEnabled": False,
                "commitSha": "abc123",
            }
        ]

    monkeypatch.setattr(community_catalog, "_fetch_source_index", fake_fetch)

    result = await community_catalog.list_official_community_catalog(
        query="example",
        source_key="openai-skills",
    )

    assert result["adminOnly"] is True
    assert result["activationPolicy"] == "review_required"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["key"] == "openai-skills"
    assert len(result["items"]) == 1
    assert result["items"][0]["runtimeEnabled"] is False


@pytest.mark.asyncio
async def test_official_catalog_does_not_substitute_failed_sources(monkeypatch):
    monkeypatch.setattr(
        community_catalog,
        "_fetch_source_index",
        AsyncMock(side_effect=RuntimeError("upstream unavailable")),
    )

    result = await community_catalog.list_official_community_catalog()

    assert result["items"] == []
    assert len(result["errors"]) == len(community_catalog.OFFICIAL_COMMUNITY_SOURCES)
    assert all("upstream unavailable" in row["message"] for row in result["errors"])


def test_community_source_only_allows_curated_official_sources():
    assert community_catalog.community_source("openai-skills") is not None
    assert community_catalog.community_source("anthropic-skills") is not None
    assert community_catalog.community_source("openai-plugins") is not None
    assert community_catalog.community_source("anthropic-plugins") is not None
    assert community_catalog.community_source("anthropic-partner-plugins") is not None
    assert community_catalog.community_source("arbitrary-github") is None


def test_official_catalog_includes_skill_and_plugin_sources():
    kinds = {source.kind for source in community_catalog.OFFICIAL_COMMUNITY_SOURCES}
    assert kinds == {"skill", "plugin"}
    plugin_sources = {
        source.key for source in community_catalog.OFFICIAL_COMMUNITY_SOURCES
        if source.kind == "plugin"
    }
    assert {"openai-plugins", "anthropic-plugins", "anthropic-partner-plugins"} <= plugin_sources
