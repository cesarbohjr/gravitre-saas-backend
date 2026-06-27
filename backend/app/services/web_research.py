"""Shared Tavily web research for agent ToolRegistry and assistant tools."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyNotConfiguredError(RuntimeError):
    """Raised when TAVILY_API_KEY / settings.tavily_api_key is missing."""


async def search_web(
    query: str,
    *,
    settings: Settings | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """
    Search the web via Tavily.

    Returns a normalized dict with keys: results, sources, totalResults.
    On missing API key, raises TavilyNotConfiguredError.
    On empty query, returns an error payload without raising.
    """
    active_settings = settings or get_settings()
    api_key = (getattr(active_settings, "tavily_api_key", None) or "").strip()
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return {
            "results": [],
            "sources": [],
            "totalResults": 0,
            "error": "Missing query",
        }
    if not api_key:
        raise TavilyNotConfiguredError("TAVILY_API_KEY is not configured")

    capped = max(1, min(int(max_results), 10))
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": api_key,
                    "query": cleaned_query,
                    "max_results": capped,
                    "include_answer": False,
                },
            )
        if resp.status_code >= 400:
            logger.warning(
                "tavily_search_http_error status=%s query=%s",
                resp.status_code,
                cleaned_query[:120],
            )
            return {
                "results": [],
                "sources": [],
                "totalResults": 0,
                "error": "web search request failed",
            }
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("tavily_search_failed query=%s error=%s", cleaned_query[:120], str(exc))
        return {
            "results": [],
            "sources": [],
            "totalResults": 0,
            "error": "web search unavailable",
        }

    results = [
        {
            "title": str(item.get("title") or "Result"),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("content") or "")[:320],
        }
        for item in (payload.get("results") or [])
    ]
    sources = [
        {"title": row["title"], "url": row["url"], "excerpt": row["snippet"]}
        for row in results
        if row.get("url")
    ]
    return {
        "results": results,
        "sources": sources,
        "totalResults": len(results),
    }
