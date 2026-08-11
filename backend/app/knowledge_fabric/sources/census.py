"""U.S. Census Bureau Data API — structured intelligence (license type B), not a text corpus.

Live-verified 2026-08-11 (census.gov developers Terms of Service):
- API use permitted to search/display/analyze/retrieve Census data
- Attribution notice required: "This product uses the Census Bureau Data API but is not endorsed..."
- Requires API key for most datasets

This module fetches structured dimension snapshots and stores compact JSON summaries
(not scraped narrative pages). Full interactive queries remain API-backed.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (census-api; support@gravitre.ai)"}
CENSUS_BASE = "https://api.census.gov/data"


async def fetch_census_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    _ = spec
    api_key = (os.environ.get("CENSUS_API_KEY") or "").strip()
    docs: list[dict[str, Any]] = []

    # Always include a dimensions/catalog document describing the structured interface.
    catalog = {
        "dimensions": [
            "geography",
            "industry",
            "establishments",
            "employment",
            "population",
            "income",
            "business_formation",
            "trade",
        ],
        "endpoints": {
            "acs5_population": f"{CENSUS_BASE}/2023/acs/acs5",
            "cbp_establishments": f"{CENSUS_BASE}/2022/cbp",
            "bfs": f"{CENSUS_BASE}/timeseries/bfs/total",
        },
        "attribution": (
            "This product uses the Census Bureau Data API but is not endorsed or certified "
            "by the Census Bureau."
        ),
        "terms_url": "https://www.census.gov/data/developers/about/terms-of-service.html",
        "api_key_configured": bool(api_key),
    }
    docs.append(
        {
            "external_id": "census-api-dimensions",
            "title": "U.S. Census Bureau — structured intelligence dimensions",
            "content": (
                "U.S. Census Bureau Data API structured intelligence coverage for Gravitre Sales/"
                "Marketing packs. Dimensions: geography, industry, establishments, employment, "
                "population, income, business formation, and trade. "
                f"Catalog: {json.dumps(catalog)}. "
                "Query live via Census API; do not treat this as a static scraped corpus."
            ),
            "citation": "U.S. Census Bureau Data API — https://www.census.gov/data/developers/",
            "jurisdiction": "US-federal",
            "topics": [
                "geography",
                "industry",
                "establishments",
                "employment",
                "population",
                "income",
                "business_formation",
                "trade",
            ],
            "metadata": {
                "license_type": "B",
                "structured_api": True,
                "ingestion_policy_map": "API",
                "catalog": catalog,
            },
        }
    )

    # Optional live sample pulls when key present (still structured JSON, not prose scrape).
    if api_key and limit > 1:
        async with httpx.AsyncClient(timeout=45, headers=_HEADERS) as client:
            try:
                params = {
                    "get": "NAME,B01001_001E",
                    "for": "us:*",
                    "key": api_key,
                }
                resp = await client.get(f"{CENSUS_BASE}/2023/acs/acs5", params=params)
                if resp.status_code == 200:
                    payload = resp.json()
                    docs.append(
                        {
                            "external_id": "census-acs5-us-population-sample",
                            "title": "Census ACS 5-year — US total population (sample)",
                            "content": (
                                "Structured Census ACS5 sample (US): "
                                f"{json.dumps(payload)[:2000]}. "
                                "Attribution: This product uses the Census Bureau Data API but "
                                "is not endorsed or certified by the Census Bureau."
                            ),
                            "citation": "U.S. Census Bureau ACS 5-Year API",
                            "jurisdiction": "US-federal",
                            "topics": ["population", "geography"],
                            "metadata": {"license_type": "B", "structured_api": True},
                        }
                    )
            except Exception:  # noqa: BLE001
                pass

    return docs[:limit]


async def query_census_live(
    *,
    dataset_path: str,
    params: dict[str, str],
) -> dict[str, Any]:
    """Live structured query helper (not permanent corpus write)."""
    api_key = (os.environ.get("CENSUS_API_KEY") or "").strip()
    if api_key:
        params = {**params, "key": api_key}
    async with httpx.AsyncClient(timeout=45, headers=_HEADERS) as client:
        resp = await client.get(f"{CENSUS_BASE}/{dataset_path.lstrip('/')}", params=params)
        return {
            "http": resp.status_code,
            "url": str(resp.url).replace(api_key, "***") if api_key else str(resp.url),
            "data": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:2000],
            "attribution": (
                "This product uses the Census Bureau Data API but is not endorsed or certified "
                "by the Census Bureau."
            ),
        }
