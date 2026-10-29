"""Isolated Playwright candidate for production-style broker comparison.

No autonomous model control or alternate authorization service. Browser writes
are possible only after the existing gateway /action approval and a fresh,
identical viewport/DOM fingerprint. This candidate is deliberately not the
default native worker executable.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from urllib.parse import urlsplit

from engine import fresh_browser_evidence, stable_browser_evidence, gateway
from browser_adapter_benchmark import PlaywrightSession, action_for


def validate_url(url: str, allowed_hosts: list[str]) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise PermissionError("Browser destination outside reviewed HTTPS host allowlist")
    return url


async def request_exact_approval(config, action, evidence, sequence):
    details = {"actions": action, "url": evidence["url"], **evidence["snapshot"]}
    deadline = asyncio.get_running_loop().time() + min(config["max_seconds"], 300)
    while True:
        response = await asyncio.to_thread(gateway, config, "/action", {"sequence": sequence, "action": details})
        if response.get("state") == "approved":
            return
        if response.get("state") == "denied" or asyncio.get_running_loop().time() >= deadline:
            raise PermissionError("Browser action was not approved")
        await asyncio.sleep(0.5)


async def approved_click(config, session, page, sequence=0):
    state = await session.get_browser_state_summary(include_screenshot=False)
    action = action_for(state)
    before, fingerprint = await stable_browser_evidence(session, action)
    validate_url(before.url, config["allowed_hosts"])
    await request_exact_approval(config, action, {"url": before.url, "snapshot": fingerprint}, sequence)
    after, updated = await fresh_browser_evidence(session, action, "after_approval")
    if updated != fingerprint or after.url != before.url:
        raise PermissionError("Approved browser fingerprint became stale")
    # Selector identity must be derived from the currently verified DOM.
    index = action["click"]["index"]
    node = after.dom_state.selector_map[index]
    identifier = (node.attributes or {}).get("id")
    if not isinstance(identifier, str) or not identifier.isascii() or not identifier.replace("-", "").replace("_", "").isalnum():
        raise PermissionError("Candidate requires one bounded exact-id target")
    await page.locator("#" + identifier).click(timeout=10000)
    return {"approved_action": True, "verified_execution": False}


async def run(config, *, browser=None):
    if not config.get("allowed_hosts") or config.get("engine") != "browser_use":
        raise PermissionError("Candidate requires an existing approved browser job")
    if browser is not None:
        raise PermissionError("External browser sessions are forbidden")
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        instance = await playwright.chromium.launch(executable_path="/usr/bin/chromium",
            headless=True, chromium_sandbox=True,
            proxy={"server": "http://gateway:8080", "bypass": "gateway,localhost,127.0.0.1"})
        try:
            context = await instance.new_context(viewport={"width":1280,"height":720}, accept_downloads=False,
                permissions=[], service_workers="block")
            page = await context.new_page()
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
            # Destination is a trusted benchmark input, not an LLM-supplied URL.
            url = validate_url(config["comparison_url"], config["allowed_hosts"])
            await page.goto(url, timeout=20000)
            session = PlaywrightSession(page)
            result = await approved_click(config, session, page)
            return {"observations": [{"summary": "Comparison candidate completed one reviewed fixture click."}], **result}
        finally:
            await instance.close()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    config = json.loads(sys.stdin.buffer.read(262145))
    result = asyncio.run(run(config))
    Path("/out/result.json").write_text(json.dumps(result))
