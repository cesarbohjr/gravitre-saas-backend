"""Competition Bureau Canada — deceptive / influencer marketing guidance (OGL)."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (competition-bureau-ca; support@gravitre.ai)"}

CB_URLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "cb-deceptive-marketing",
        "https://competition-bureau.canada.ca/en/deceptive-marketing-practices",
        ("deceptive_marketing", "competition_bureau", "advertising", "canada"),
    ),
    (
        "cb-influencer",
        "https://competition-bureau.canada.ca/en/how-we-foster-competition/education-and-outreach/publications/influencer-marketing-and-competition-act",
        ("influencer_marketing", "endorsements", "competition_bureau", "canada"),
    ),
    (
        "cb-false-ordinary",
        "https://competition-bureau.canada.ca/en/how-we-foster-competition/education-and-outreach/publications/false-or-misleading-representations",
        ("deceptive_advertising", "pricing", "competition_bureau", "canada"),
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


async def fetch_competition_bureau_ca_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    _ = spec
    docs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for external_id, url, topics in CB_URLS[:limit]:
            resp = await client.get(url)
            if resp.status_code >= 400:
                continue
            text = _html_to_text(resp.text)[:11000]
            title_m = re.search(r"<title>([^<]+)</title>", resp.text, re.I)
            title = (title_m.group(1) if title_m else external_id).split("|")[0].strip()
            docs.append(
                {
                    "external_id": external_id,
                    "title": f"Competition Bureau Canada — {title}",
                    "content": text,
                    "citation": f"Competition Bureau Canada — {url}",
                    "jurisdiction": "CA-federal",
                    "topics": list(topics),
                    "metadata": {
                        "license_type": "A",
                        "license": "Canada-OGL",
                        "license_url": "https://open.canada.ca/en/open-government-licence-canada",
                        "refreshable": True,
                        "cross_pack": ["pack.legal", "pack.marketing"],
                    },
                }
            )
    return docs
