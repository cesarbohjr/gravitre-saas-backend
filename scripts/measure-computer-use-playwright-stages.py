#!/usr/bin/env python3
"""Local Playwright stage breakdown for the Computer Use public READ path.

Same URLs as production. Not LIVE_API. Not httpx. Isolated process only.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from types import SimpleNamespace

from app.services.browser_agent_service import browser_agent_playwright_session  # noqa: E402

SETTINGS = SimpleNamespace(browser_agent_enabled=True)


async def one_run(label: str) -> dict:
    t0 = time.perf_counter()
    raw = await browser_agent_playwright_session(
        "https://example.com/",
        follow_link_text="More information",
        settings=SETTINGS,
    )
    wall_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "label": label,
        "wall_ms": wall_ms,
        "success": raw.get("success"),
        "url": raw.get("url"),
        "chromium_launch_ms": raw.get("chromium_launch_ms"),
        "first_goto_ms": raw.get("first_goto_ms"),
        "follow_link_ms": raw.get("follow_link_ms"),
        "playwright_session_ms": raw.get("playwright_session_ms"),
        "stage_timings": raw.get("stage_timings"),
        "visit_count": len(raw.get("visits") or []),
        "titles": [row.get("title") for row in (raw.get("visits") or [])],
    }


async def main() -> int:
    cold = await one_run("cold")
    warm = await one_run("warm_second_process_launch")
    payload = {"cold": cold, "second_launch": warm}
    out = ROOT / "docs" / "delivery" / "gravitre-computer-use-playwright-stages-local.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
