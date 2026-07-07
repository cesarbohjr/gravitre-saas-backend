"""Browser agent for connector API gaps — read pages and optional UI automation."""
from __future__ import annotations

import ipaddress
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})
_MAX_READ_BYTES = 512_000
_MAX_TEXT_CHARS = 12_000


class BrowserAgentError(Exception):
    def __init__(self, message: str, *, code: str = "browser_agent_error") -> None:
        super().__init__(message)
        self.code = code


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self._chunks.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        return re.sub(r"\s+", " ", raw).strip()


def _validate_public_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if not cleaned:
        raise BrowserAgentError("url is required", code="validation_error")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise BrowserAgentError("Only http(s) URLs are allowed", code="validation_error")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        raise BrowserAgentError("Blocked host for browser agent", code="ssrf_blocked")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise BrowserAgentError("Blocked private/reserved address", code="ssrf_blocked")
    except ValueError:
        pass
    return cleaned


def _extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.text()
    if len(text) > _MAX_TEXT_CHARS:
        return text[: _MAX_TEXT_CHARS - 3] + "..."
    return text


async def browser_agent_read(
    url: str,
    *,
    settings: Settings | None = None,
    selector: str | None = None,
) -> dict[str, Any]:
    """Fetch a page and return title + extracted text (read-only, no JS execution)."""
    active = settings or get_settings()
    if not getattr(active, "browser_agent_enabled", True):
        raise BrowserAgentError("Browser agent is disabled for this environment", code="disabled")
    safe_url = _validate_public_url(url)
    headers = {"User-Agent": "Gravitre-BrowserAgent/1.0 (+https://gravitre.app)"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(safe_url, headers=headers)
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "")
        body = response.content[:_MAX_READ_BYTES]
        html = body.decode(response.encoding or "utf-8", errors="replace")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    text = _extract_text(html)
    if selector:
        # Lightweight selector hint — full DOM query requires Playwright interact path.
        text = f"[selector={selector} not applied in read-only mode]\n{text}"
    return {
        "url": safe_url,
        "title": title,
        "content_type": content_type,
        "text": text,
        "mode": "httpx_read",
    }


async def browser_agent_interact(
    url: str,
    *,
    actions: list[dict[str, Any]] | None = None,
    settings: Settings | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Optional Playwright UI automation when native APIs are unavailable (approval-gated)."""
    active = settings or get_settings()
    if not getattr(active, "browser_agent_enabled", True):
        raise BrowserAgentError("Browser agent is disabled for this environment", code="disabled")
    if not getattr(active, "browser_agent_interact_enabled", False):
        raise BrowserAgentError(
            "Browser interact is disabled. Set BROWSER_AGENT_INTERACT_ENABLED=true and provide approval_id.",
            code="disabled",
        )
    if not approval_id:
        return {
            "pending_approval": True,
            "message": "browser_agent_interact requires human approval before UI automation.",
            "url": url,
            "actions": actions or [],
        }
    safe_url = _validate_public_url(url)
    steps = list(actions or [])
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise BrowserAgentError(
            "Playwright is not installed. Add playwright to requirements-extras-data and run playwright install.",
            code="playwright_missing",
        ) from exc

    results: list[dict[str, Any]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(safe_url, wait_until="domcontentloaded", timeout=45_000)
        for index, step in enumerate(steps):
            action_type = str(step.get("type") or step.get("action") or "").lower()
            selector = str(step.get("selector") or "")
            value = step.get("value")
            if action_type == "click" and selector:
                await page.click(selector, timeout=15_000)
                results.append({"step": index, "action": "click", "selector": selector, "ok": True})
            elif action_type in {"fill", "type"} and selector:
                await page.fill(selector, str(value or ""))
                results.append({"step": index, "action": "fill", "selector": selector, "ok": True})
            elif action_type == "wait":
                ms = int(step.get("ms") or step.get("milliseconds") or 1000)
                await page.wait_for_timeout(ms)
                results.append({"step": index, "action": "wait", "ms": ms, "ok": True})
            else:
                results.append(
                    {
                        "step": index,
                        "action": action_type or "unknown",
                        "ok": False,
                        "error": "Unsupported action — use click, fill, or wait",
                    }
                )
        snapshot_text = _extract_text(await page.content())
        await browser.close()
    return {
        "url": safe_url,
        "approval_id": approval_id,
        "steps": results,
        "text": snapshot_text[:_MAX_TEXT_CHARS],
        "mode": "playwright_interact",
    }
