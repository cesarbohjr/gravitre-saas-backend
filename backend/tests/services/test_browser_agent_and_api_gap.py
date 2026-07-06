"""Browser agent + API gap fallback tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.api_gap_service import gap_recovery_prompt_section, resolve_api_gap_fallback
from app.services.browser_agent_service import BrowserAgentError, browser_agent_interact, browser_agent_read


def test_resolve_api_gap_fallback_missing_action():
    result = resolve_api_gap_fallback("dropbox", "files.upload")
    assert result["missing"] is True
    assert "browser_agent_read" in result["recommended_tools"]


def test_resolve_api_gap_fallback_native_hubspot_contact():
    result = resolve_api_gap_fallback("hubspot", "hubspot.contacts.search")
    assert result["missing"] is False


def test_gap_recovery_prompt_includes_mcp_when_registered():
    section = gap_recovery_prompt_section(connected_integrations=["hubspot"], has_mcp_tools=True)
    assert "mcp_" in section
    assert "browser_agent_read" in section


@pytest.mark.asyncio
async def test_browser_agent_read_blocks_private_url():
    with pytest.raises(BrowserAgentError, match="Blocked"):
        await browser_agent_read("http://127.0.0.1/admin")


@pytest.mark.asyncio
async def test_browser_agent_read_extracts_text():
    html = "<html><head><title>Acme</title></head><body><p>Hello world</p></body></html>"
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = html.encode()
    mock_response.encoding = "utf-8"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.browser_agent_service.httpx.AsyncClient", return_value=mock_client):
        payload = await browser_agent_read("https://example.com/deals")
    assert payload["title"] == "Acme"
    assert "Hello world" in payload["text"]


@pytest.mark.asyncio
async def test_browser_agent_interact_requires_approval():
    result = await browser_agent_interact(
        "https://example.com/app",
        actions=[{"type": "click", "selector": "#save"}],
        settings=MagicMock(browser_agent_enabled=True, browser_agent_interact_enabled=True),
    )
    assert result["pending_approval"] is True
