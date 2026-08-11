"""FTC business guidance — U.S. government works (license type A), refreshable."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (ftc-ingest; support@gravitre.ai)"}

# Live-verified 2026-08-11: ftc.gov website policy — U.S. government work / public domain (17 U.S.C. § 105).
FTC_GUIDANCE_URLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "ftc-can-spam",
        "https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business",
        ("can_spam", "email_marketing", "advertising", "compliance"),
    ),
    (
        "ftc-endorsements",
        "https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking",
        ("endorsements", "influencers", "advertising", "compliance"),
    ),
    (
        "ftc-native-advertising",
        "https://www.ftc.gov/business-guidance/resources/native-advertising-guide-businesses",
        ("native_advertising", "advertising", "disclosure", "compliance"),
    ),
    (
        "ftc-deceptive-advertising",
        "https://www.ftc.gov/business-guidance/advertising-marketing/advertising-marketing-basics",
        ("deceptive_advertising", "advertising", "marketing_metrics", "ethics"),
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


async def fetch_ftc_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    _ = spec
    docs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for external_id, url, topics in FTC_GUIDANCE_URLS[:limit]:
            resp = await client.get(url)
            resp.raise_for_status()
            text = _html_to_text(resp.text)
            # Trim chrome; keep substantive guidance body
            if len(text) > 12000:
                text = text[:12000]
            title_m = re.search(r"<title>([^<]+)</title>", resp.text, re.I)
            title = (title_m.group(1) if title_m else external_id).split("|")[0].strip()
            docs.append(
                {
                    "external_id": external_id,
                    "title": f"FTC — {title}",
                    "content": text,
                    "citation": f"U.S. Federal Trade Commission — {url}",
                    "jurisdiction": "US-federal",
                    "topics": list(topics),
                    "metadata": {
                        "license_type": "A",
                        "license": "US-Gov-Work",
                        "license_url": "https://www.ftc.gov/policy-notices/website-policy",
                        "refreshable": True,
                        "cross_pack": ["pack.legal", "pack.marketing"],
                    },
                }
            )
    return docs
