"""Shared web research — Serper primary (when selected), Tavily fallback, Google optional."""
from __future__ import annotations

import hashlib
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
SERPER_SEARCH_URL = "https://google.serper.dev/search"


class WebResearchNotConfiguredError(RuntimeError):
    """Raised when no internet research provider is configured."""


class TavilyNotConfiguredError(WebResearchNotConfiguredError):
    """Raised when Tavily is required but TAVILY_API_KEY is missing."""


class SerperNotConfiguredError(WebResearchNotConfiguredError):
    """Raised when Serper is required but SERPER_API_KEY is missing."""


def is_web_research_provider_configured(settings: Settings) -> bool:
    """True when the selected provider (or fallback) can run."""
    provider = (getattr(settings, "web_research_provider", None) or "google").strip().lower()
    if provider == "tavily":
        return bool((getattr(settings, "tavily_api_key", None) or "").strip())
    if provider == "serper":
        if (getattr(settings, "serper_api_key", None) or "").strip():
            return True
        if getattr(settings, "web_research_fallback_tavily", True):
            return bool((getattr(settings, "tavily_api_key", None) or "").strip())
        return False
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


async def _search_serper(
    query: str,
    *,
    settings: Settings,
    max_results: int = 5,
) -> dict[str, Any]:
    api_key = (getattr(settings, "serper_api_key", None) or "").strip()
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return {"results": [], "sources": [], "totalResults": 0, "error": "Missing query", "provider": "serper"}
    if not api_key:
        raise SerperNotConfiguredError("SERPER_API_KEY is not configured")

    capped = max(1, min(int(max_results), 10))
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                SERPER_SEARCH_URL,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": cleaned_query, "num": capped},
            )
        if resp.status_code >= 400:
            logger.warning(
                "serper_search_http_error status=%s query=%s",
                resp.status_code,
                cleaned_query[:120],
            )
            return {
                "results": [],
                "sources": [],
                "totalResults": 0,
                "error": f"serper http {resp.status_code}",
                "provider": "serper",
            }
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("serper_search_failed query=%s error=%s", cleaned_query[:120], str(exc))
        return {
            "results": [],
            "sources": [],
            "totalResults": 0,
            "error": "serper unavailable",
            "provider": "serper",
        }

    results = [
        {
            "title": str(item.get("title") or "Result"),
            "url": str(item.get("link") or ""),
            "snippet": str(item.get("snippet") or "")[:320],
        }
        for item in (payload.get("organic") or [])
    ][:capped]
    sources = [
        {"title": row["title"], "url": row["url"], "excerpt": row["snippet"]}
        for row in results
        if row.get("url")
    ]
    return {
        "results": results,
        "sources": sources,
        "totalResults": len(results),
        "provider": "serper",
        "query_sent": cleaned_query[:2000],
    }


def _should_fallback_from_primary(payload: dict[str, Any] | None) -> tuple[bool, str]:
    """Decide whether primary failed hard enough to warrant Tavily fallback.

    Empty-but-successful SERPs do not fallback (same discipline as Google path:
    only error / not-configured). This avoids silent always-fallback.
    """
    if payload is None:
        return True, "primary_payload_missing"
    if payload.get("error"):
        return True, f"primary_error:{payload.get('error')}"
    return False, ""


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

    Providers (WEB_RESEARCH_PROVIDER):
      - serper: Serper primary; Tavily fallback on hard failure (when enabled)
      - tavily: direct Tavily
      - google: Google Grounding primary; Tavily fallback on hard failure

    When org_id + Supabase client provided, records Research Lookup metering
    after a successful query with results. metadata.provider reflects the
    provider that actually served results (serper | tavily | google_grounding).
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
    fallback_enabled = bool(getattr(active_settings, "web_research_fallback_tavily", True))

    payload: dict[str, Any] | None = None
    errors: list[str] = []
    fallback_from: str | None = None
    fallback_reason: str | None = None

    if provider == "serper":
        try:
            payload = await _search_serper(governed_query, settings=active_settings, max_results=capped)
            need_fb, reason = _should_fallback_from_primary(payload)
            if need_fb and fallback_enabled:
                fallback_from = "serper"
                fallback_reason = reason
                errors.append(reason)
                # VISIBLE fallback log — must not be silent (STA-341 / Google silent-fail lesson)
                logger.warning(
                    "web_research_fallback_to_tavily primary=serper reason=%s query=%s",
                    reason,
                    governed_query[:120],
                )
                payload = None
            elif need_fb and not fallback_enabled:
                errors.append(reason)
        except SerperNotConfiguredError as exc:
            errors.append(str(exc))
            if fallback_enabled:
                fallback_from = "serper"
                fallback_reason = "serper_not_configured"
                logger.warning(
                    "web_research_fallback_to_tavily primary=serper reason=serper_not_configured query=%s",
                    governed_query[:120],
                )
            payload = None

    elif provider == "google":
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
            elif payload.get("error") and fallback_enabled:
                fallback_from = "google_grounding"
                fallback_reason = str(payload.get("error"))
                errors.append(fallback_reason)
                logger.warning(
                    "web_research_fallback_to_tavily primary=google_grounding reason=%s query=%s",
                    fallback_reason,
                    governed_query[:120],
                )
                payload = None
        except GoogleGroundingNotConfiguredError as exc:
            errors.append(str(exc))
            if fallback_enabled:
                fallback_from = "google_grounding"
                fallback_reason = "google_not_configured"
                logger.warning(
                    "web_research_fallback_to_tavily primary=google_grounding reason=google_not_configured query=%s",
                    governed_query[:120],
                )
            payload = None

    if payload is None:
        # Direct tavily, or fallback after serper/google failure
        if provider == "tavily" or fallback_enabled:
            try:
                payload = await _search_tavily(governed_query, settings=active_settings, max_results=capped)
                if fallback_from and payload is not None:
                    payload["fallback_from"] = fallback_from
                    payload["fallback_reason"] = fallback_reason
                    # provider stays "tavily" — accurate for metering (who served results)
                    logger.warning(
                        "web_research_fallback_served provider=tavily fallback_from=%s reason=%s "
                        "totalResults=%s query=%s",
                        fallback_from,
                        fallback_reason,
                        payload.get("totalResults"),
                        governed_query[:120],
                    )
            except TavilyNotConfiguredError:
                if not errors:
                    raise WebResearchNotConfiguredError(
                        "Internet research is not configured (Serper/Google grounding or Tavily fallback required)"
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
    extra_meta: dict[str, Any] = {}
    if payload.get("fallback_from"):
        extra_meta["fallback_from"] = payload.get("fallback_from")
        extra_meta["fallback_reason"] = payload.get("fallback_reason")

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
            extra_metadata=extra_meta or None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("research_lookup_metering_failed org_id=%s error=%s", org_id, str(exc))
