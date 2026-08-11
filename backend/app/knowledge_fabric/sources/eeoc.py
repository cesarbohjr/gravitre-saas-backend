"""EEOC employer guidance — U.S. government works (license type A)."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (eeoc-ingest; support@gravitre.ai)"}

EEOC_URLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "eeoc-employers",
        "https://www.eeoc.gov/employers",
        ("eeoc", "employment_discrimination", "employer_guidance"),
    ),
    (
        "eeoc-prohibited-practices",
        "https://www.eeoc.gov/prohibited-employment-policiespractices",
        ("eeoc", "prohibited_practices", "title_vii"),
    ),
    (
        "eeoc-guidance",
        "https://www.eeoc.gov/guidance",
        ("eeoc", "guidance_library", "employment_law"),
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


async def fetch_eeoc_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    _ = spec
    docs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for external_id, url, topics in EEOC_URLS[:limit]:
            resp = await client.get(url)
            if resp.status_code >= 400:
                continue
            text = _html_to_text(resp.text)[:11000]
            title_m = re.search(r"<title>([^<]+)</title>", resp.text, re.I)
            title = (title_m.group(1) if title_m else external_id).split("|")[0].strip()
            docs.append(
                {
                    "external_id": external_id,
                    "title": f"EEOC — {title}",
                    "content": text,
                    "citation": f"U.S. Equal Employment Opportunity Commission — {url}",
                    "jurisdiction": "US-federal",
                    "topics": list(topics),
                    "metadata": {
                        "license_type": "A",
                        "license": "US-Gov-Work",
                        "license_url": "https://www.eeoc.gov/eeoc-privacy-policy",
                        "refreshable": True,
                    },
                }
            )
    return docs
