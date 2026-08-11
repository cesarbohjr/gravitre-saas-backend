"""Google Trends — live signal source (not static chunked corpus).

Access status (verified 2026-08-11):
- Official Google Trends API developer docs URL returned non-usable / unavailable
  for a production key in this environment (developers.google.com/search/apis/trends
  did not expose a ready public API key path).
- Wire as live_only intelligence: prefer an official API when credentials exist
  (GOOGLE_TRENDS_API_KEY / alpha access); otherwise fall back to the existing
  live-research connector path (web research) without permanent corpus ingest.
"""
from __future__ import annotations

import os
from typing import Any

from app.knowledge_fabric.license_types import assert_ingest_allowed


def trends_access_status() -> dict[str, Any]:
    api_key = (os.environ.get("GOOGLE_TRENDS_API_KEY") or "").strip()
    return {
        "official_api_key_configured": bool(api_key),
        "access_path": "official_api" if api_key else "live_research_connector_fallback",
        "explore_url": "https://trends.google.com/trends/",
        "signals": [
            "topic_interest",
            "keyword_interest",
            "geo_interest",
            "historical_interest",
            "trend_comparison",
        ],
        "corpus_policy": "live_only_no_permanent_ingest",
        "license_type": "D",
        "note": (
            "No production Google Trends official API credential is configured. "
            "Do not scrape Trends HTML into knowledge_*. Use live research fallback."
        ),
    }


def assert_trends_not_permanent(source_row: dict[str, Any]) -> None:
    assert_ingest_allowed(
        str(source_row.get("license_type") or "D"),
        ingestion_method=str(source_row.get("ingestion_method") or "live_only"),
        crawl_allowed=bool(source_row.get("crawl_allowed")),
        commercial_use_allowed=source_row.get("commercial_use_allowed"),
    )


async def live_trends_query(query: str) -> dict[str, Any]:
    status = trends_access_status()
    return {
        "mode": "live_signal",
        "query": query,
        "access": status,
        "results": [],
    }
