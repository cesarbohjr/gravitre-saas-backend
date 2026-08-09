"""Async source client smoke tests (graceful degrade, no live keys required)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.intelligence_packs.executive.sources import fetch_fred_series, fetch_opencorporates_search, fetch_sec_company_filings


@pytest.mark.asyncio
async def test_fred_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    result = await fetch_fred_series("GDP", settings=SimpleNamespace(fred_api_key=""))
    assert result["ok"] is False
    assert result["error_code"] == "GRAVITRE_SOURCE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_sec_requires_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    result = await fetch_sec_company_filings("Acme", settings=SimpleNamespace(sec_user_agent=""))
    assert result["ok"] is False
    assert result["error_code"] == "SEC_USER_AGENT_REQUIRED"


@pytest.mark.asyncio
async def test_opencorporates_blocked_without_license(monkeypatch):
    monkeypatch.setenv("OPENCORPORATES_API_TOKEN", "tok")
    result = await fetch_opencorporates_search(
        "OpenCorporates",
        settings=SimpleNamespace(opencorporates_license_confirmed=False, opencorporates_api_token="tok"),
    )
    assert result["ok"] is False
    assert result["error_code"] == "SOURCE_ACTIVATION_BLOCKED"
