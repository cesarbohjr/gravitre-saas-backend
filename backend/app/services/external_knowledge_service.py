"""External knowledge connectors — Wikipedia and structured public sources."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"


async def fetch_wikipedia_summary(topic: str, *, max_chars: int = 400) -> dict[str, Any] | None:
    slug = topic.strip().replace(" ", "_")[:120]
    if not slug:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{WIKIPEDIA_API}{slug}")
            if resp.status_code != 200:
                return None
            data = resp.json()
            extract = str(data.get("extract") or "")[:max_chars]
            if not extract:
                return None
            return {
                "type": "external_wikipedia",
                "title": data.get("title") or topic,
                "summary": extract,
                "source": data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://en.wikipedia.org/wiki/{slug}",
                "freshness_score": 0.7,
                "trust_score": 0.75,
            }
    except Exception as exc:  # noqa: BLE001
        logger.debug("wikipedia_fetch_failed topic=%s error=%s", topic, exc)
        return None


async def gather_external_knowledge(
    topic: str,
    *,
    settings: Settings | None = None,
    include_wikipedia: bool = True,
) -> list[dict[str, Any]]:
    """Best-effort public knowledge without duplicating Tavily web search."""
    _ = settings
    findings: list[dict[str, Any]] = []
    if include_wikipedia:
        wiki = await fetch_wikipedia_summary(topic)
        if wiki:
            findings.append(wiki)
    return findings


def detect_source_contradictions(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lightweight contradiction flags across external findings."""
    from app.services.context_conflict_detection import _has_opposing_sentiment

    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(findings):
        left_text = str(left.get("summary") or "")
        for right in findings[index + 1 :]:
            right_text = str(right.get("summary") or "")
            if _has_opposing_sentiment(left_text, right_text):
                conflicts.append(
                    {
                        "source_a": left.get("source"),
                        "source_b": right.get("source"),
                        "requires_human_review": True,
                    }
                )
    return conflicts
