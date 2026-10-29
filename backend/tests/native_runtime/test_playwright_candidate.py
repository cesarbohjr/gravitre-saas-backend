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


def test_broker_comparison_opt_in_requires_pinned_image_and_https():
    from app.services.native_runtime.docker_runner import DockerRunner, SandboxImages
    digest = "a" * 64
    images = SandboxImages("registry/openhands@sha256:"+digest,
        "registry/browser@sha256:"+digest,"registry/gateway@sha256:"+digest)
    with pytest.raises(ValueError):
        DockerRunner(images, comparison_url="https://www.selenium.dev/page")
    with pytest.raises(ValueError):
        DockerRunner(SandboxImages(images.openhands,images.browser_use,images.gateway,
            playwright_comparison="registry/playwright@sha256:"+digest),
            comparison_url="http://www.selenium.dev/page")
    candidate_image = SandboxImages(images.openhands,images.browser_use,images.gateway,
        playwright_comparison="registry/playwright@sha256:"+digest)
    assert DockerRunner(candidate_image,comparison_url="https://www.selenium.dev/page").comparison_url == "https://www.selenium.dev/page"
    assert DockerRunner(candidate_image).comparison_url is None


@pytest.mark.asyncio
async def test_navigation_denial_never_dispatches(monkeypatch):
    page = SimpleNamespace(goto=AsyncMock())
    session = SimpleNamespace()
    monkeypatch.setitem(candidate["approved_navigation"].__globals__, "stable_browser_evidence",
        AsyncMock(return_value=(SimpleNamespace(url="about:blank"), {"page_fingerprint":"a"*64})))
    async def deny(*args, **kwargs):
        raise PermissionError("review denied")
    monkeypatch.setitem(candidate["approved_navigation"].__globals__, "request_exact_approval", deny)
    with pytest.raises(PermissionError):
        await candidate["approved_navigation"]({"allowed_hosts":["www.selenium.dev"]},
            session, page, "https://www.selenium.dev/selenium/web/web-form.html")
    page.goto.assert_not_awaited()
