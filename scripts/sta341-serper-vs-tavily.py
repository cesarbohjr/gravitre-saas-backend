#!/usr/bin/env python3
"""STA-341: Tavily half of side-by-side (run under railway run for prod keys)."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.services.internet_research_query import prepare_internet_research_query
from app.services.web_research import _search_tavily

# Confirmed historical research-path queries (usage_records store hashes only;
# plaintext recovered from live smokes + conversation_messages + cascade script).
HISTORICAL = [
    {
        "raw": "What is the current US federal funds rate?",
        "evidence": "internet-research-live + verify-web-research-provider-tavily-live 2026-08-11",
    },
    {
        "raw": (
            "Summarize what you can find about our refund policy. "
            "Include research confidence and sources used."
        ),
        "evidence": "smoke-research-cascade-prod + conversation_messages (repeated)",
    },
]


async def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    provider = (settings.web_research_provider or "").strip().lower()
    rows = []
    for item in HISTORICAL:
        prepared = prepare_internet_research_query(item["raw"])
        t0 = time.perf_counter()
        tv = await _search_tavily(prepared.query, settings=settings, max_results=5)
        ms = (time.perf_counter() - t0) * 1000
        results = tv.get("results") or []
        rows.append(
            {
                "raw": item["raw"],
                "query_sent": prepared.query,
                "evidence": item["evidence"],
                "tavily": {
                    "provider": tv.get("provider"),
                    "totalResults": tv.get("totalResults"),
                    "error": tv.get("error"),
                    "latency_ms": round(ms, 1),
                    "titles": [r.get("title") for r in results[:5]],
                    "urls": [r.get("url") for r in results[:5]],
                    "snippets": [(r.get("snippet") or "")[:200] for r in results[:5]],
                },
            }
        )

    out = {
        "web_research_provider": provider,
        "tavily_configured": bool((settings.tavily_api_key or "").strip()),
        "rows": rows,
    }
    path = ROOT / "docs" / "delivery" / "_sta341-tavily-half.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if provider == "tavily" and all(r["tavily"].get("totalResults", 0) > 0 for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
