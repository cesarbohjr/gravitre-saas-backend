"""CISA advisories / MSP / StopRansomware — U.S. government works (license type A).

Live cisa.gov HTML is currently edge-blocked (HTTP 403) for automated fetch.
We ingest curated public summaries with canonical citations — same pattern as
NIST Wave 2 overviews — and record fetch_status in metadata.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GravitreKnowledgeFabric/1.0; +https://gravitre.ai)"
}

# Curated authoritative summaries when live HTML is blocked (403).
_CURATED: list[dict[str, Any]] = [
    {
        "external_id": "cisa-advisories-overview",
        "title": "CISA Cybersecurity Advisories — overview",
        "url": "https://www.cisa.gov/news-events/cybersecurity-advisories",
        "content": (
            "CISA publishes cybersecurity advisories covering known exploited vulnerabilities, "
            "threat actor activity, and defensive mitigations for U.S. critical infrastructure "
            "and enterprise networks. Organizations should subscribe to CISA advisories, "
            "prioritize Known Exploited Vulnerabilities (KEV) catalog items, and apply "
            "vendor patches on the timelines CISA recommends. Advisories often include "
            "detection signatures, IOCs, and recommended hunting queries for MSSP/MSP "
            "customers. Source: https://www.cisa.gov/news-events/cybersecurity-advisories"
        ),
        "topics": ["cisa", "advisories", "cyber_threats", "kev"],
    },
    {
        "external_id": "cisa-msp-guidance-overview",
        "title": "CISA guidance for managed service providers — overview",
        "url": "https://www.cisa.gov/topics/cybersecurity-best-practices",
        "content": (
            "CISA guidance for MSPs and their customers emphasizes secure remote access, "
            "least-privilege administration, multi-factor authentication, segmented "
            "management planes, logging/monitoring, and rapid incident reporting. MSPs "
            "should treat customer environments as high-value targets, harden jump hosts, "
            "rotate credentials, and maintain out-of-band recovery paths. Customers should "
            "verify MSP security baselines contractually. "
            "Source: https://www.cisa.gov/topics/cybersecurity-best-practices"
        ),
        "topics": ["cisa", "msp", "best_practices"],
    },
    {
        "external_id": "cisa-stopransomware-overview",
        "title": "CISA StopRansomware — overview",
        "url": "https://www.cisa.gov/stopransomware",
        "content": (
            "StopRansomware is a joint U.S. government effort (CISA, FBI, MS-ISAC and "
            "partners) providing one-stop ransomware prevention and response guidance. "
            "Core practices: maintain offline immutable backups, patch internet-facing "
            "systems promptly, disable unused RDP/ports, enforce MFA, prepare IR plans, "
            "and report incidents to CISA/FBI. Do not pay ransom as a substitute for "
            "recovery capability. Source: https://www.cisa.gov/stopransomware"
        ),
        "topics": ["ransomware", "stopransomware", "incident_response", "cisa"],
    },
]


async def fetch_cisa_documents(
    spec: KnowledgeSourceSpec | None = None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    _ = spec
    live_status: dict[str, Any] = {"attempted": True, "statuses": []}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=_HEADERS) as client:
        for doc in _CURATED:
            try:
                resp = await client.head(doc["url"])
                live_status["statuses"].append({"url": doc["url"], "status": resp.status_code})
            except Exception as exc:  # noqa: BLE001
                live_status["statuses"].append(
                    {"url": doc["url"], "status": "error", "error": str(exc)[:120]}
                )
    blocked = all(
        (s.get("status") == 403) or (s.get("status") == "error")
        for s in live_status["statuses"]
    )
    live_status["html_blocked"] = blocked
    out: list[dict[str, Any]] = []
    for doc in _CURATED[:limit]:
        out.append(
            {
                "external_id": doc["external_id"],
                "title": f"CISA — {doc['title']}",
                "content": doc["content"],
                "citation": f"CISA — {doc['url']}",
                "jurisdiction": "US-federal",
                "topics": list(doc["topics"]),
                "metadata": {
                    "license_type": "A",
                    "license": "US-Gov-Work",
                    "license_url": "https://www.usa.gov/government-copyright",
                    "fetch_status": live_status,
                    "content_mode": "curated_summary_live_html_blocked"
                    if blocked
                    else "curated_summary",
                },
            }
        )
    return out
