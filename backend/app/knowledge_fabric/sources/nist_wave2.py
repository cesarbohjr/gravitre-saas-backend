"""NIST AI RMF / GenAI Profile / Zero Trust — U.S. government works."""
from __future__ import annotations

from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (nist-wave2; support@gravitre.ai)"}

# Curated public NIST summaries (full PDFs available at cited URLs).
_DOCS: dict[str, list[dict[str, Any]]] = {
    "cyber.nist.ai_rmf": [
        {
            "external_id": "nist-ai-rmf-1-0-overview",
            "title": "NIST AI Risk Management Framework 1.0 — overview",
            "content": (
                "The NIST AI Risk Management Framework (AI RMF 1.0) provides a flexible, "
                "rights-preserving, and risk-based approach for organizations that design, "
                "develop, deploy, or use AI systems. Core functions are Govern, Map, Measure, "
                "and Manage. Govern is cross-cutting and establishes culture, policies, and "
                "accountability. Map establishes context and categorizes AI risks. Measure "
                "employs quantitative and qualitative methods. Manage allocates resources and "
                "implements response plans. The framework is voluntary and intended to be used "
                "alongside sector-specific guidance. "
                "Source: NIST AI RMF 1.0 — https://doi.org/10.6028/NIST.AI.100-1"
            ),
            "citation": "NIST AI RMF 1.0 — https://doi.org/10.6028/NIST.AI.100-1",
            "topics": ["ai_rmf", "govern", "map", "measure", "manage", "ai_risk"],
        }
    ],
    "cyber.nist.genai_profile": [
        {
            "external_id": "nist-genai-profile-overview",
            "title": "NIST Generative AI Profile — overview",
            "content": (
                "The NIST Generative AI Profile (NIST AI 600-1) profiles the AI RMF for "
                "generative AI risks including content authenticity, data privacy, intellectual "
                "property, information integrity, and harmful content. Organizations should map "
                "GAI-specific risks under Map, measure them with appropriate metrics, and manage "
                "with human oversight, transparency, and incident response. "
                "Source: https://doi.org/10.6028/NIST.AI.600-1"
            ),
            "citation": "NIST AI 600-1 Generative AI Profile — https://doi.org/10.6028/NIST.AI.600-1",
            "topics": ["genai", "ai_rmf", "content_integrity", "ai_risk"],
        }
    ],
    "cyber.nist.zero_trust": [
        {
            "external_id": "nist-sp800-207-overview",
            "title": "NIST SP 800-207 Zero Trust Architecture — overview",
            "content": (
                "NIST SP 800-207 defines Zero Trust Architecture (ZTA): never trust, always "
                "verify. Core tenets include continuous authentication/authorization, least "
                "privilege, microsegmentation, and assuming breach. Policy decision points and "
                "policy enforcement points mediate access to enterprise resources based on "
                "identity, device, and context signals. ZTA is a journey, not a single product. "
                "Source: https://doi.org/10.6028/NIST.SP.800-207"
            ),
            "citation": "NIST SP 800-207 — https://doi.org/10.6028/NIST.SP.800-207",
            "topics": ["zero_trust", "zta", "sp800-207", "access_control"],
        }
    ],
}


async def fetch_nist_wave2_documents(
    spec: KnowledgeSourceSpec,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    docs = list(_DOCS.get(spec.source_id) or [])
    # Optional live HEAD to confirm DOI/page still reachable
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=_HEADERS) as client:
        for doc in docs:
            url = (doc.get("citation") or "").split(" — ")[-1].strip()
            if url.startswith("http"):
                try:
                    await client.head(url)
                except Exception:  # noqa: BLE001
                    pass
    out = []
    for doc in docs[:limit]:
        out.append(
            {
                **doc,
                "jurisdiction": "US",
                "metadata": {
                    "license_type": "A",
                    "license": "US-Gov-Work",
                    "license_url": "https://www.nist.gov/open",
                },
            }
        )
    return out
