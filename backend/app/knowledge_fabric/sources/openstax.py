"""OpenStax Principles of Marketing — BLOCKED for shared corpus (CC BY-NC-SA 4.0).

Live-verified 2026-08-11 from OpenStax preface and chapter pages:
https://openstax.org/books/principles-marketing/pages/preface
License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA).

Prompt expected CC BY 4.0 — DISCREPANCY. commercial_use_allowed=false.
Used as the deliberate NC rejection fixture for the hard gate live test.
"""
from __future__ import annotations

from typing import Any

from app.knowledge_fabric.license_types import assert_ingest_allowed
from app.knowledge_fabric.registry import KnowledgeSourceSpec

OPENSTAX_MARKETING_LICENSE = "CC-BY-NC-SA-4.0"
OPENSTAX_LICENSE_URL = "https://openstax.org/books/principles-marketing/pages/preface"


async def fetch_openstax_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Intentionally raises — NC content must never enter platform_shared corpus."""
    _ = limit
    commercial = getattr(spec, "commercial_use_allowed", False) if spec else False
    license_type = getattr(spec, "license_type", "C") if spec else "C"
    assert_ingest_allowed(
        license_type,
        ingestion_method=getattr(spec, "ingestion_method", "bulk") if spec else "bulk",
        crawl_allowed=getattr(spec, "crawl_allowed", False) if spec else False,
        commercial_use_allowed=commercial,
    )
    raise RuntimeError("OpenStax Principles of Marketing is CC BY-NC-SA — ingest refused")


def deliberate_nc_ingest_attempt(source_row: dict[str, Any]) -> dict[str, Any]:
    """Disposable test path: attempt gate with a forged NC source row."""
    try:
        assert_ingest_allowed(
            str(source_row.get("license_type") or "A"),
            ingestion_method=str(source_row.get("ingestion_method") or "bulk"),
            crawl_allowed=bool(source_row.get("crawl_allowed")),
            commercial_use_allowed=source_row.get("commercial_use_allowed"),
        )
        return {"rejected": False, "error": None}
    except ValueError as exc:
        return {"rejected": True, "error": str(exc)}
