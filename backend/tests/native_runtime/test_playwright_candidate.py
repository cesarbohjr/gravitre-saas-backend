"""Safety properties of the opt-in candidate; no production activation."""
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

candidate = runpy.run_path(str(Path(__file__).resolve().parents[2] / "native-workers/playwright_candidate.py"))


@pytest.mark.parametrize("url", [
    "http://www.selenium.dev/path", "https://localhost/path",
    "https://www.selenium.dev:444/path", "https://admin@www.selenium.dev/path",
    "https://www.selenium.dev.evil.example/path",
])
def test_rejects_nonapproved_destination(url):
    with pytest.raises(PermissionError):
        candidate["validate_url"](url, ["www.selenium.dev"])


def test_accepts_exact_https_host():
    assert candidate["validate_url"]("https://www.selenium.dev/path", ["www.selenium.dev"])


@pytest.mark.asyncio
async def test_action_gateway_denial_never_clicks(monkeypatch):
    page = SimpleNamespace(locator=AsyncMock())
    session = SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=SimpleNamespace(
        dom_state=SimpleNamespace(selector_map={1:SimpleNamespace(attributes={"id":"commit"})}))))
    monkeypatch.setitem(candidate["approved_click"].__globals__, "action_for", lambda state: {"click":{"index":1}})
    monkeypatch.setitem(candidate["approved_click"].__globals__, "stable_browser_evidence", AsyncMock(return_value=(
        SimpleNamespace(url="https://www.selenium.dev/page"), {"page_fingerprint":"a"*64})))
    async def deny(*args, **kwargs):
        raise PermissionError("no approval")
    monkeypatch.setitem(candidate["approved_click"].__globals__, "request_exact_approval", deny)
    with pytest.raises(PermissionError):
        await candidate["approved_click"]({"allowed_hosts":["www.selenium.dev"]},session,page)
    assert page.locator.call_count == 0
