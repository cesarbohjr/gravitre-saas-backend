"""CourtListener / Free Law Project API — license type B."""
from __future__ import annotations

import os
from typing import Any

import httpx

API = "https://www.courtlistener.com/api/rest/v4/opinions/"


async def fetch_courtlistener_opinions(*, limit: int = 3) -> list[dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "GravitreKnowledgeFabric/1.0 (platform knowledge pack; contact support@gravitre.ai)",
    }
    token = os.environ.get("COURTLISTENER_API_TOKEN") or os.environ.get("COURTLISTENER_TOKEN")
    if token:
        headers["Authorization"] = f"Token {token}"

    params = {"page_size": max(1, min(limit, 10)), "order_by": "-date_created"}
    try:
        async with httpx.AsyncClient(timeout=45.0, headers=headers) as http:
            resp = await http.get(API, params=params)
            if resp.status_code in {401, 403}:
                # Token required for REST v4 in current CourtListener policy.
                return []
            resp.raise_for_status()
            payload = resp.json()
    except Exception:  # noqa: BLE001
        return []

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        results = []

    docs: list[dict[str, Any]] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        opinion_id = str(item.get("id") or item.get("resource_uri") or "")
        plain = (
            item.get("plain_text")
            or item.get("html_with_citations")
            or item.get("html")
            or item.get("snippet")
            or ""
        )
        if isinstance(plain, str) and "<" in plain[:200]:
            # Strip crude HTML tags for chunking
            import re

            plain = re.sub(r"<[^>]+>", " ", plain)
        plain = (plain or "").strip()
        if len(plain) < 80:
            continue
        # Cap stored text — API licensed reuse of excerpts for retrieval corpus
        plain = plain[:12000]
        cluster = item.get("cluster") if isinstance(item.get("cluster"), dict) else {}
        case_name = (
            cluster.get("case_name")
            or item.get("case_name")
            or f"Opinion {opinion_id}"
        )
        abs_url = item.get("absolute_url") or cluster.get("absolute_url") or ""
        if abs_url and abs_url.startswith("/"):
            abs_url = f"https://www.courtlistener.com{abs_url}"
        docs.append(
            {
                "external_id": f"cl-opinion-{opinion_id}",
                "title": str(case_name)[:240],
                "content": plain,
                "citation": f"CourtListener opinion {opinion_id}"
                + (f" — {abs_url}" if abs_url else ""),
                "jurisdiction": "US-federal",
                "topics": ["case_law", "opinions"],
                "published_at": item.get("date_created"),
                "metadata": {
                    "courtlistener_id": opinion_id,
                    "license_type": "B",
                    "api": "courtlistener.rest.v4",
                },
            }
        )
    return docs
