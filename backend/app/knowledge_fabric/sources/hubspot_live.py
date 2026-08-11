"""HubSpot (and similar) commercial research — LIVE_RETRIEVAL only (license type D).

Never permanently ingest into knowledge_* / platform_shared corpus.
Maps proposed LIVE_RETRIEVAL_ONLY policy onto existing type D gate.
"""
from __future__ import annotations

from typing import Any

from app.knowledge_fabric.license_types import assert_ingest_allowed

HUBSPOT_RESEARCH_NOTE = (
    "HubSpot published research may be queried live when relevant; it must not be "
    "copied into the permanent shared knowledge corpus (type D / live_only)."
)


def assert_hubspot_not_permanent(source_row: dict[str, Any]) -> None:
    assert_ingest_allowed(
        str(source_row.get("license_type") or "D"),
        ingestion_method=str(source_row.get("ingestion_method") or "live_only"),
        crawl_allowed=bool(source_row.get("crawl_allowed")),
        commercial_use_allowed=source_row.get("commercial_use_allowed"),
    )


async def live_retrieve_hubspot_stub(query: str) -> dict[str, Any]:
    """Placeholder live path — points at public research hub; no corpus write."""
    return {
        "mode": "live_retrieval_only",
        "license_type": "D",
        "query": query,
        "results": [],
        "note": HUBSPOT_RESEARCH_NOTE,
        "entry_url": "https://www.hubspot.com/state-of-marketing",
    }
