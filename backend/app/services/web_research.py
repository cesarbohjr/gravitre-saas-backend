"""Shared web research — Google Grounding primary, Tavily optional fallback."""
from __future__ import annotations

import hashlib
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class WebResearchNotConfiguredError(RuntimeError):
    """Raised when no internet research provider is configured."""


class TavilyNotConfiguredError(WebResearchNotConfiguredError):
    """Raised when Tavily is required but TAVILY_API_KEY is missing."""


def is_web_research_provider_configured(settings: Settings) -> bool:
    """True when the selected provider (or fallback) can run."""
    provider = (getattr(settings, "web_research_provider", None) or "google").strip().lower()
    if provider == "tavily":
        return bool((getattr(settings, "tavily_api_key", None) or "").strip())
    from app.services.web_research_google import is_google_grounding_configured

    if is_google_grounding_configured(settings):
        return True
    if getattr(settings, "web_research_fallback_tavily", True):
        return bool((getattr(settings, "tavily_api_key", None) or "").strip())
    return False


async def _search_tavily(
    query: str,
    *,
    settings: Settings,
    max_results: int = 5,
) -> dict[str, Any]:
    api_key = (getattr(settings, "tavily_api_key", None) or "").strip()
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return {"results": [], "sources": [], "totalResults": 0, "error": "Missing query", "provider": "tavily"}
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
            logger.warning("tavily_search_http_error status=%s query=%s", resp.status_code, cleaned_query[:120])
            return {
                "results": [],
                "sources": [],
                "totalResults": 0,
                "error": "web search request failed",
                "provider": "tavily",
            }
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("tavily_search_failed query=%s error=%s", cleaned_query[:120], str(exc))
        return {
            "results": [],
            "sources": [],
            "totalResults": 0,
            "error": "web search unavailable",
            "provider": "tavily",
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
        "provider": "tavily",
        "query_sent": cleaned_query[:2000],
    }


async def search_web(
    query: str,
    *,
    settings: Settings | None = None,
    max_results: int = 5,
    org_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """
    Search the public web for retrieval cascade / assistant tools.

    Primary: Google Grounded Generation (grounding on Google Search).
    Fallback: Tavily when configured and primary fails or provider=tavily.

    When org_id + Supabase client provided, records Research Lookup metering
    and platform grounding volume after a successful query with results.
    """
    from app.services.grounding_volume_monitor import check_org_grounding_circuit
    from app.services.internet_research_query import prepare_internet_research_query

    active_settings = settings or get_settings()
    prepared = prepare_internet_research_query(query)
    governed_query = prepared.query
    query_meta = prepared.to_metadata()

    if not governed_query:
        return {
            "results": [],
            "sources": [],
            "totalResults": 0,
            "error": "Missing query",
            **query_meta,
        }

    if org_id and client is not None:
        circuit = check_org_grounding_circuit(client, org_id, active_settings)
        if circuit.get("blocked"):
            return {
                "results": [],
                "sources": [],
                "totalResults": 0,
                "error": "internet research temporarily paused for this organization (hourly circuit breaker)",
                "circuit_breaker": circuit,
                **query_meta,
            }

    provider = (getattr(active_settings, "web_research_provider", None) or "google").strip().lower()
    capped = max(1, min(int(max_results), 10))

    payload: dict[str, Any] | None = None
    errors: list[str] = []

    if provider == "google":
        from app.services.web_research_google import (
            GoogleGroundingNotConfiguredError,
            search_google_grounding,
        )

        try:
            payload = await search_google_grounding(
                governed_query, settings=active_settings, max_results=capped
            )
            if payload.get("totalResults", 0) > 0:
                pass
            elif payload.get("error") and getattr(active_settings, "web_research_fallback_tavily", True):
                errors.append(str(payload.get("error")))
                payload = None
        except GoogleGroundingNotConfiguredError as exc:
            errors.append(str(exc))
            payload = None

    if payload is None:
        if provider == "tavily" or getattr(active_settings, "web_research_fallback_tavily", True):
            try:
                payload = await _search_tavily(governed_query, settings=active_settings, max_results=capped)
            except TavilyNotConfiguredError:
                if not errors:
                    raise WebResearchNotConfiguredError(
                        "Internet research is not configured (Google grounding or Tavily fallback required)"
                    )
                raise WebResearchNotConfiguredError("; ".join(errors))
        else:
            raise WebResearchNotConfiguredError(errors[0] if errors else "Internet research provider unavailable")

    if payload is not None:
        payload.update(query_meta)

    if (
        payload
        and int(payload.get("totalResults") or 0) > 0
        and org_id
        and client is not None
    ):
        await _record_usage_after_search(
            client,
            org_id=org_id,
            query=governed_query,
            payload=payload,
            settings=active_settings,
        )

    return payload or {"results": [], "sources": [], "totalResults": 0, "error": "no results", **query_meta}


async def _record_usage_after_search(
    client: Any,
    *,
    org_id: str,
    query: str,
    payload: dict[str, Any],
    settings: Settings | None = None,
) -> None:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    provider = str(payload.get("provider") or "unknown")
    query_hash = hashlib.sha256((query or "").strip().encode()).hexdigest()[:16]

    try:
        from app.services.grounding_volume_monitor import record_grounding_count
        from app.services.research_lookup_metering import record_research_lookup

        if provider == "google_grounding":
            record_grounding_count(
                client,
                org_id=org_id,
                count=int(usage.get("grounding_count") or 1),
                settings=settings,
            )
        record_research_lookup(
            client,
            org_id=org_id,
            provider=provider,
            query_hash=query_hash,
            grounding_count=int(usage.get("grounding_count") or 1),
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            source_id=query_hash,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("research_lookup_metering_failed org_id=%s error=%s", org_id, str(exc))
