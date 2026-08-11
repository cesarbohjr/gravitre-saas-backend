"""DOL Employment Law Guide — expands HR pack beyond FLSA/FMLA snippets."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (dol-elg; support@gravitre.ai)"}

ELG_URLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "dol-elg-overview",
        "https://www.dol.gov/agencies/whd/employment-law-guide",
        ("employment_law", "wage_hour", "dol_guide"),
    ),
    (
        "dol-elg-wages",
        "https://www.dol.gov/agencies/whd/flsa",
        ("flsa", "minimum_wage", "overtime"),
    ),
    (
        "dol-elg-fmla",
        "https://www.dol.gov/agencies/whd/fmla",
        ("fmla", "leave", "job_protected_leave"),
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


async def fetch_dol_elg_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    _ = spec
    docs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for external_id, url, topics in ELG_URLS[:limit]:
            resp = await client.get(url)
            if resp.status_code >= 400:
                continue
            text = _html_to_text(resp.text)[:11000]
            title_m = re.search(r"<title>([^<]+)</title>", resp.text, re.I)
            title = (title_m.group(1) if title_m else external_id).split("|")[0].strip()
            docs.append(
                {
                    "external_id": external_id,
                    "title": f"DOL ELG — {title}",
                    "content": text,
                    "citation": f"U.S. Department of Labor — {url}",
                    "jurisdiction": "US-federal",
                    "topics": list(topics),
                    "metadata": {
                        "license_type": "A",
                        "license": "US-Gov-Work",
                        "license_url": "https://www.dol.gov/general/aboutdol/disclaimer",
                        "refreshable": True,
                    },
                }
            )
    return docs
