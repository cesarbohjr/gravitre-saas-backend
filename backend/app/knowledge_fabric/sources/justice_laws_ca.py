"""Justice Laws Canada — Canada Open Government Licence (confirm live before ingest)."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (justice-laws-ca; support@gravitre.ai)"}

# Acts page + consolidated sample acts (HTML). XML corpus available at laws-lois.justice.gc.ca.
JUSTICE_URLS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "ca-justice-laws-home",
        "https://laws-lois.justice.gc.ca/eng/",
        "Justice Laws Website — home",
        ("statutes", "regulations", "canada_federal"),
    ),
    (
        "ca-pipeda",
        "https://laws-lois.justice.gc.ca/eng/acts/P-8.6/",
        "Personal Information Protection and Electronic Documents Act (PIPEDA)",
        ("pipeda", "privacy", "canada_federal"),
    ),
    (
        "ca-competition-act",
        "https://laws-lois.justice.gc.ca/eng/acts/C-34/",
        "Competition Act",
        ("competition", "consumer_protection", "canada_federal"),
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


async def fetch_justice_laws_ca_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    _ = spec
    docs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for external_id, url, title, topics in JUSTICE_URLS[:limit]:
            resp = await client.get(url)
            if resp.status_code >= 400:
                continue
            text = _html_to_text(resp.text)[:12000]
            # Pull current-to / effective hints when present
            current_to = None
            m = re.search(r"Current to\s+([A-Za-z0-9 ,]+)", text, re.I)
            if m:
                current_to = m.group(1).strip()[:80]
            docs.append(
                {
                    "external_id": external_id,
                    "title": f"Justice Laws Canada — {title}",
                    "content": text,
                    "citation": f"Justice Laws Website (Canada) — {url}",
                    "jurisdiction": "CA-federal",
                    "topics": list(topics),
                    "effective_at": None,
                    "metadata": {
                        "license_type": "A",
                        "license": "Canada-OGL",
                        "license_url": "https://open.canada.ca/en/open-government-licence-canada",
                        "jurisdiction": "CA-federal",
                        "act": title,
                        "section": None,
                        "current_to_date": current_to,
                        "superseded_version": None,
                        "effective_date_sensitive": True,
                        "refreshable": True,
                    },
                }
            )
    return docs
