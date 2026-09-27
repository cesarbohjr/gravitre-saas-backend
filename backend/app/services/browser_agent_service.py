"""Browser agent for connector API gaps — read pages and optional UI automation."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

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


async def _playwright_page_snapshot(page: Any, *, take_screenshot: bool = True) -> dict[str, Any]:
    stages: dict[str, int] = {}
    t0 = time.perf_counter()
    url = str(page.url or "")
    title = str(await page.title() or "")
    stages["title_ms"] = int((time.perf_counter() - t0) * 1000)
    t1 = time.perf_counter()
    try:
        text = str(await page.inner_text("body") or "")
    except Exception:  # noqa: BLE001
        html = await page.content()
        text = _extract_text(html)
    stages["dom_text_ms"] = int((time.perf_counter() - t1) * 1000)
    shot_digest = None
    if take_screenshot:
        t2 = time.perf_counter()
        shot = await page.screenshot(type="png")
        shot_digest = hashlib.sha256(shot).hexdigest()
        stages["screenshot_ms"] = int((time.perf_counter() - t2) * 1000)
    return {
        "url": url,
        "title": title,
        "dom_excerpt": text[:800],
        "screenshot_digest": shot_digest,
        "text": text[:_MAX_TEXT_CHARS],
        "stage_ms": stages,
    }


_playwright_driver: Any = None
_public_chromium: Any = None
_public_chromium_lock = asyncio.Lock()


async def _navigation_timing_ms(page: Any) -> dict[str, int]:
    try:
        raw = await page.evaluate(
            """() => {
              const n = performance.getEntriesByType('navigation')[0];
              if (!n) return {};
              const tls = n.secureConnectionStart > 0
                ? Math.round(n.connectEnd - n.secureConnectionStart)
                : 0;
              return {
                dns_ms: Math.round(n.domainLookupEnd - n.domainLookupStart),
                tcp_connect_ms: Math.round(n.connectEnd - n.connectStart),
                tls_ms: tls,
                ttfb_ms: Math.round(n.responseStart - n.requestStart),
                download_ms: Math.round(n.responseEnd - n.responseStart),
                dcl_from_nav_start_ms: Math.round(n.domContentLoadedEventEnd - n.startTime)
              };
            }"""
        )
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = int(value or 0)
        except (TypeError, ValueError):
            continue
    return out


async def _click_public_follow_link(
    page: Any,
    *,
    follow_link_text: str | None,
) -> tuple[bool, str, str]:
    """Follow the public example.com outbound link without waiting on stale labels.

    Destination href is preferred. Visible names are tried only when present
    (count() == 0 skips immediately — no 8s timeout on 'More information').
    """
    last_error = ""
    try:
        href = page.locator('a[href*="iana.org"]')
        if await href.count() > 0:
            await href.first.click(timeout=8_000)
            return True, "a[href*=iana.org]", ""
    except Exception as extra:  # noqa: BLE001
        last_error = str(extra)[:240]
    candidates: list[str] = []
    for name in (follow_link_text, "Learn more", "More information"):
        if name and name not in candidates:
            candidates.append(name)
    for name in candidates:
        try:
            link = page.get_by_role("link", name=name)
            if await link.count() == 0:
                continue
            await link.first.click(timeout=8_000)
            return True, name, last_error
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:240]
    return False, str(follow_link_text or ""), last_error


async def _public_read_chromium() -> tuple[Any, dict[str, int]]:
    """Process-local Chromium for public READ. Isolated context per task — no auth reuse."""
    global _playwright_driver, _public_chromium
    async with _public_chromium_lock:
        if _public_chromium is not None:
            try:
                if _public_chromium.is_connected():
                    return _public_chromium, {
                        "chromium_reused": 1,
                        "playwright_start_ms": 0,
                        "chromium_launch_ms": 0,
                    }
            except Exception:  # noqa: BLE001
                _public_chromium = None
        from playwright.async_api import async_playwright

        t0 = time.perf_counter()
        if _playwright_driver is None:
            _playwright_driver = await async_playwright().start()
        playwright_start_ms = int((time.perf_counter() - t0) * 1000)
        t1 = time.perf_counter()
        _public_chromium = await _playwright_driver.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        return _public_chromium, {
            "chromium_reused": 0,
            "playwright_start_ms": playwright_start_ms,
            "chromium_launch_ms": int((time.perf_counter() - t1) * 1000),
        }


async def browser_agent_playwright_session(
    url: str,
    *,
    follow_link_text: str | None = "More information",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """READ-only Chromium session: open a public page, optionally follow a public link.

    This is not httpx. Form fill / submit stay on browser_agent_interact + approval.
    """
    active = settings or get_settings()
    if not getattr(active, "browser_agent_enabled", True):
        raise BrowserAgentError("Browser agent is disabled for this environment", code="disabled")
    safe_url = _validate_public_url(url)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise BrowserAgentError(
            "Playwright is not installed, so I cannot open a real browser session.",
            code="playwright_missing",
        ) from exc
    session_id = str(uuid4())
    visits: list[dict[str, Any]] = []
    stages: dict[str, int] = {}
    t_session = time.perf_counter()
    context = None
    try:
        t0 = time.perf_counter()
        browser, acquire = await _public_read_chromium()
        stages.update(acquire)
        stages["chromium_acquire_ms"] = int((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        context = await browser.new_context(accept_downloads=False)
        stages["context_create_ms"] = int((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        page = await context.new_page()
        stages["page_create_ms"] = int((time.perf_counter() - t0) * 1000)
        stages["first_goto_start_ms"] = 0
        t0 = time.perf_counter()
        await page.goto(safe_url, wait_until="domcontentloaded", timeout=45_000)
        stages["first_goto_dcl_ms"] = int((time.perf_counter() - t0) * 1000)
        first_nav = await _navigation_timing_ms(page)
        stages["first_dns_ms"] = first_nav.get("dns_ms", 0)
        stages["first_tcp_connect_ms"] = first_nav.get("tcp_connect_ms", 0)
        stages["first_tls_ms"] = first_nav.get("tls_ms", 0)
        stages["first_ttfb_ms"] = first_nav.get("ttfb_ms", 0)
        stages["first_download_ms"] = first_nav.get("download_ms", 0)
        stages["first_dcl_from_nav_start_ms"] = first_nav.get("dcl_from_nav_start_ms", 0)
        first = await _playwright_page_snapshot(page)
        first_ms = first.get("stage_ms") if isinstance(first.get("stage_ms"), dict) else {}
        stages["first_title_ms"] = int(first_ms.get("title_ms") or 0)
        stages["first_dom_text_ms"] = int(first_ms.get("dom_text_ms") or 0)
        stages["first_screenshot_ms"] = int(first_ms.get("screenshot_ms") or 0)
        first["action"] = "goto"
        visits.append(first)
        if follow_link_text:
            t0 = time.perf_counter()
            clicked, follow_used, last_error = await _click_public_follow_link(
                page,
                follow_link_text=follow_link_text,
            )
            stages["click_ms"] = int((time.perf_counter() - t0) * 1000)
            if clicked:
                t0 = time.perf_counter()
                await page.wait_for_load_state("domcontentloaded", timeout=45_000)
                stages["second_dcl_ms"] = int((time.perf_counter() - t0) * 1000)
                second_nav = await _navigation_timing_ms(page)
                stages["second_dns_ms"] = second_nav.get("dns_ms", 0)
                stages["second_tcp_connect_ms"] = second_nav.get("tcp_connect_ms", 0)
                stages["second_tls_ms"] = second_nav.get("tls_ms", 0)
                stages["second_ttfb_ms"] = second_nav.get("ttfb_ms", 0)
                stages["second_download_ms"] = second_nav.get("download_ms", 0)
                stages["second_dcl_from_nav_start_ms"] = second_nav.get("dcl_from_nav_start_ms", 0)
                second = await _playwright_page_snapshot(page)
                second_ms = second.get("stage_ms") if isinstance(second.get("stage_ms"), dict) else {}
                stages["second_title_ms"] = int(second_ms.get("title_ms") or 0)
                stages["second_dom_text_ms"] = int(second_ms.get("dom_text_ms") or 0)
                stages["second_screenshot_ms"] = int(second_ms.get("screenshot_ms") or 0)
                second["action"] = "click_link"
                second["link_text"] = follow_used
                visits.append(second)
            else:
                visits.append(
                    {
                        "url": str(page.url or ""),
                        "title": "",
                        "dom_excerpt": "",
                        "screenshot_digest": None,
                        "action": "click_link",
                        "link_text": follow_link_text,
                        "success": False,
                        "error": last_error,
                    }
                )
        t0 = time.perf_counter()
        await context.close()
        context = None
        stages["context_close_ms"] = int((time.perf_counter() - t0) * 1000)
    except BrowserAgentError:
        if context is not None:
            try:
                await context.close()
            except Exception:  # noqa: BLE001
                pass
        raise
    except Exception as extra:  # noqa: BLE001
        if context is not None:
            try:
                await context.close()
            except Exception:  # noqa: BLE001
                pass
        logger.exception("playwright_session_failed url=%s", safe_url[:120])
        raise BrowserAgentError(
            f"The browser session could not complete: {extra}",
            code="playwright_failed",
        ) from extra
    session_ms = int((time.perf_counter() - t_session) * 1000)
    stages["playwright_session_ms"] = session_ms
    last = visits[-1] if visits else {}
    click_failed = any(row.get("success") is False for row in visits)
    return {
        "success": bool(visits) and not click_failed,
        "url": last.get("url") or safe_url,
        "title": last.get("title") or visits[0].get("title") if visits else "",
        "text": last.get("text") or last.get("dom_excerpt") or "",
        "screenshot_digest": last.get("screenshot_digest"),
        "cdp_trace_id": session_id,
        "mode": "playwright_session_read",
        "strategy": "browser_cdp",
        "chromium_launch_ms": stages.get("chromium_acquire_ms"),
        "first_goto_ms": stages.get("first_goto_dcl_ms"),
        "follow_link_ms": (stages.get("click_ms") or 0)
        + (stages.get("second_dcl_ms") or 0)
        + (stages.get("second_dom_text_ms") or 0)
        + (stages.get("second_screenshot_ms") or 0),
        "playwright_session_ms": session_ms,
        "stage_timings": stages,
        "visits": [
            {
                "url": row.get("url"),
                "title": row.get("title"),
                "action": row.get("action"),
                "screenshot_digest": row.get("screenshot_digest"),
                "dom_excerpt": row.get("dom_excerpt"),
                "link_text": row.get("link_text"),
                "error": row.get("error"),
            }
            for row in visits
        ],
    }


async def browser_agent_interact(
    url: str,
    *,
    actions: list[dict[str, Any]] | None = None,
    settings: Settings | None = None,
    approval_id: str | None = None,
    hmac_verified: bool = False,
) -> dict[str, Any]:
    """Optional Playwright UI automation when native APIs are unavailable (approval-gated)."""
    active = settings or get_settings()
    if not getattr(active, "browser_agent_enabled", True):
        raise BrowserAgentError("Browser agent is disabled for this environment", code="disabled")
    if hmac_verified and approval_id:
        pass
    elif not getattr(active, "browser_agent_interact_enabled", False):
        raise BrowserAgentError(
            "Browser interact is disabled. Set BROWSER_AGENT_INTERACT_ENABLED=true and provide approval_id.",
            code="disabled",
        )
    elif not approval_id:
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
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(safe_url, wait_until="domcontentloaded", timeout=45_000)
            for index, step in enumerate(steps):
                action_type = str(step.get("type") or step.get("action") or "").lower()
                selector = str(step.get("selector") or "")
                value = step.get("value")
                try:
                    if action_type == "click" and selector:
                        await page.locator(selector).first.click(timeout=15_000)
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=15_000)
                        except Exception:  # noqa: BLE001
                            pass
                        results.append(
                            {
                                "step": index,
                                "action": "click",
                                "selector": selector,
                                "ok": True,
                                "url": str(page.url or safe_url),
                            }
                        )
                    elif action_type in {"fill", "type"} and selector:
                        await page.locator(selector).first.fill(str(value or ""), timeout=15_000)
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
                except Exception as step_exc:  # noqa: BLE001
                    results.append(
                        {
                            "step": index,
                            "action": action_type or "unknown",
                            "selector": selector,
                            "ok": False,
                            "error": str(step_exc)[:240],
                        }
                    )
            snapshot_text = _extract_text(await page.content())
            final_url = str(page.url or safe_url)
            await browser.close()
    except BrowserAgentError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("playwright_interact_failed url=%s", safe_url[:120])
        raise BrowserAgentError(
            f"The browser form fill could not complete: {exc}",
            code="playwright_failed",
        ) from exc
    return {
        "url": final_url,
        "approval_id": approval_id,
        "steps": results,
        "text": snapshot_text[:_MAX_TEXT_CHARS],
        "mode": "playwright_interact",
        "success": bool(results) and all(row.get("ok") is not False for row in results),
    }
