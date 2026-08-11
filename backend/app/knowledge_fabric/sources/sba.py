"""SBA business guidance — U.S. government public-domain material (license type A)."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (sba-ingest; support@gravitre.ai)"}

# Live-verified 2026-08-11: sba.gov privacy/use notice — government information on SBA.gov
# is in the public domain; third-party materials may be copyrighted (exclude those).
SBA_GUIDANCE_URLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "sba-market-research",
        "https://www.sba.gov/business-guide/plan-your-business/market-research-competitive-analysis",
        ("market_research", "competitive_analysis", "marketing_strategy"),
    ),
    (
        "sba-write-business-plan",
        "https://www.sba.gov/business-guide/plan-your-business/write-your-business-plan",
        ("marketing_strategy", "sales_planning", "business_planning"),
    ),
    (
        "sba-customers",
        "https://www.sba.gov/business-guide/manage-your-business/get-more-customers",
        ("customer_acquisition", "customer_retention", "promotion"),
    ),
)


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def fetch_sba_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    _ = spec
    docs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for external_id, url, topics in SBA_GUIDANCE_URLS[:limit]:
            resp = await client.get(url)
            if resp.status_code >= 400:
                continue
            text = _html_to_text(resp.text)
            if len(text) > 10000:
                text = text[:10000]
            title_m = re.search(r"<title>([^<]+)</title>", resp.text, re.I)
            title = (title_m.group(1) if title_m else external_id).split("|")[0].strip()
            docs.append(
                {
                    "external_id": external_id,
                    "title": f"SBA — {title}",
                    "content": text,
                    "citation": f"U.S. Small Business Administration — {url}",
                    "jurisdiction": "US-federal",
                    "topics": list(topics),
                    "metadata": {
                        "license_type": "A",
                        "license": "US-Gov-Work",
                        "license_url": "https://www.sba.gov/about-sba/open-government/about-sbagov-website/privacy-policy",
                    },
                }
            )
    return docs
