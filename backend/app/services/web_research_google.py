"""Google Grounded Generation — grounding on Google Search (Tavily-equivalent).

Uses a single Gravitre GCP/API account (GEMINI_API_KEY or Vertex via GOOGLE_CLOUD_PROJECT).
Only the user search query is sent — not full conversation context.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_GROUNDING_MODEL = "gemini-2.5-flash"


class GoogleGroundingNotConfiguredError(RuntimeError):
    """Raised when Google grounding credentials are missing."""


def is_google_grounding_configured(settings: Settings) -> bool:
    api_key = (getattr(settings, "gemini_api_key", None) or "").strip()
    project = (getattr(settings, "google_cloud_project", None) or "").strip()
    use_vertex = bool(getattr(settings, "google_genai_use_vertexai", False))
    return bool(api_key) or (use_vertex and bool(project))


def _build_genai_client(settings: Settings) -> Any:
    from google import genai

    use_vertex = bool(getattr(settings, "google_genai_use_vertexai", False))
    project = (getattr(settings, "google_cloud_project", None) or "").strip()
    location = (getattr(settings, "google_cloud_location", None) or "us-central1").strip()
    api_key = (getattr(settings, "gemini_api_key", None) or "").strip()

    if use_vertex and project:
        return genai.Client(vertexai=True, project=project, location=location)
    if api_key:
        return genai.Client(api_key=api_key)
    raise GoogleGroundingNotConfiguredError(
        "Configure GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT + GOOGLE_GENAI_USE_VERTEXAI=true"
    )


def _extract_results_from_response(response: Any, *, max_results: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Parse grounding chunks into normalized search rows + token usage."""
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    usage = {"input_tokens": 0, "output_tokens": 0, "grounding_count": 1}

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return results, usage

    candidate = candidates[0]
    meta = getattr(candidate, "grounding_metadata", None)
    if meta is None and hasattr(candidate, "groundingMetadata"):
        meta = candidate.groundingMetadata

    chunks = []
    if meta is not None:
        chunks = getattr(meta, "grounding_chunks", None) or getattr(meta, "groundingChunks", None) or []

    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web is None:
            continue
        url = str(getattr(web, "uri", None) or getattr(web, "url", None) or "").strip()
        title = str(getattr(web, "title", None) or "Web result").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": "",
            }
        )
        if len(results) >= max_results:
            break

    usage_meta = getattr(response, "usage_metadata", None) or getattr(response, "usageMetadata", None)
    if usage_meta is not None:
        usage["input_tokens"] = int(getattr(usage_meta, "prompt_token_count", 0) or 0)
        usage["output_tokens"] = int(getattr(usage_meta, "candidates_token_count", 0) or 0)

    return results, usage


def _search_sync(query: str, settings: Settings, max_results: int) -> dict[str, Any]:
    # Query is already governance-sanitized by search_web(); defense-in-depth only here.
    cleaned = (query or "").strip()[:2000]
    if not cleaned:
        return {"results": [], "sources": [], "totalResults": 0, "error": "Missing query"}

    # Credentials check before importing the optional google.genai SDK so
    # NotConfigured surfaces correctly when the package is absent.
    client = _build_genai_client(settings)
    try:
        from google.genai import types
    except ImportError as exc:
        raise GoogleGroundingNotConfiguredError(
            "google-genai package is not installed"
        ) from exc
    model = (getattr(settings, "web_research_google_model", None) or DEFAULT_GROUNDING_MODEL).strip()

    prompt = (
        "Retrieve current public web information for this search query only. "
        "Do not include private or conversational context.\n\n"
        f"Query: {cleaned}"
    )

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
        max_output_tokens=512,
    )

    response = client.models.generate_content(model=model, contents=prompt, config=config)
    rows, usage = _extract_results_from_response(response, max_results=max_results)

    sources = [
        {"title": row["title"], "url": row["url"], "excerpt": row.get("snippet") or ""}
        for row in rows
        if row.get("url")
    ]

    return {
        "results": rows,
        "sources": sources,
        "totalResults": len(rows),
        "provider": "google_grounding",
        "usage": usage,
        "query_sent": cleaned[:2000],
    }


async def search_google_grounding(
    query: str,
    *,
    settings: Settings,
    max_results: int = 5,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(_search_sync, query, settings, max(1, min(int(max_results), 10)))
    except GoogleGroundingNotConfiguredError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("google_grounding_search_failed query=%s error=%s", (query or "")[:120], str(exc))
        return {
            "results": [],
            "sources": [],
            "totalResults": 0,
            "error": "google grounding search unavailable",
            "provider": "google_grounding",
        }
