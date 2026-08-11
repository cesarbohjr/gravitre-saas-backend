"""NIST CSF 2.0 / SP materials — license type A (U.S. government works)."""
from __future__ import annotations

from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

# Curated excerpts structured around CSF 2.0 six functions (public NIST text).
# Full CSF PDF: https://doi.org/10.6028/NIST.CSWP.29
_CSF2_FUNCTIONS: list[dict[str, str]] = [
    {
        "id": "govern",
        "title": "CSF 2.0 — Govern (GV)",
        "text": (
            "The Govern Function establishes and monitors the organization's cybersecurity risk "
            "management strategy, expectations, and policy. Govern informs how an organization "
            "will achieve and prioritize the outcomes of the other five Functions in the context "
            "of its mission and stakeholder expectations. Governance activities are critical for "
            "incorporating cybersecurity into an organization's broader enterprise risk management "
            "(ERM) strategy. Govern addresses understanding organizational context; establishing "
            "cybersecurity strategy and cybersecurity supply chain risk management; roles, "
            "responsibilities, and authorities; policy; and oversight of cybersecurity strategy."
        ),
    },
    {
        "id": "identify",
        "title": "CSF 2.0 — Identify (ID)",
        "text": (
            "The Identify Function helps determine the current cybersecurity risk to the "
            "organization. Understanding its assets (e.g., data, hardware, software, systems, "
            "facilities, services, people), suppliers, and related cybersecurity risks enables "
            "an organization to focus and prioritize its efforts consistent with its risk "
            "management strategy and the mission needs identified under Govern. Identify also "
            "includes identifying improvements for the organization's cybersecurity risk "
            "management practices."
        ),
    },
    {
        "id": "protect",
        "title": "CSF 2.0 — Protect (PR)",
        "text": (
            "The Protect Function covers safeguards for managing the organization's cybersecurity "
            "risks. Those risks include threats to and vulnerabilities of assets that could be "
            "exploited by threat actors. Protect supports the ability to secure assets to prevent "
            "or lower the likelihood and impact of adverse cybersecurity events, and to increase "
            "likelihood and impact of succeeding in the organization's mission. Outcomes include "
            "identity management, authentication, and access control; awareness and training; "
            "data security; platform security; and technology infrastructure resilience."
        ),
    },
    {
        "id": "detect",
        "title": "CSF 2.0 — Detect (DE)",
        "text": (
            "The Detect Function enables the timely discovery and analysis of anomalies, "
            "indicators of compromise, and other potentially adverse events that may indicate "
            "cybersecurity attacks and that may compromise operations. Detect supports successful "
            "incident response and recovery activities through continuous monitoring and analysis."
        ),
    },
    {
        "id": "respond",
        "title": "CSF 2.0 — Respond (RS)",
        "text": (
            "The Respond Function supports the ability to contain the effects of cybersecurity "
            "incidents. Respond activities cover incident management, analysis, mitigation, "
            "reporting, and communication. These activities help organizations minimize the "
            "impact of cybersecurity incidents."
        ),
    },
    {
        "id": "recover",
        "title": "CSF 2.0 — Recover (RC)",
        "text": (
            "The Recover Function supports timely restoration of normal operations to reduce the "
            "effects of cybersecurity incidents. Recover activities cover restoration of assets "
            "and communication during and after recovery. Improvements informed by lessons "
            "learned are also part of Recover."
        ),
    },
]

_SP80053_SUMMARY = (
    "NIST Special Publication 800-53 Revision 5 provides a catalog of security and privacy "
    "controls for information systems and organizations. Controls are organized into families "
    "(e.g., Access Control, Audit and Accountability, Incident Response, System and "
    "Communications Protection). Organizations select and implement controls based on risk "
    "assessments and baseline requirements. SP 800-53 is widely used by federal agencies and "
    "contractors and aligns with broader risk management frameworks including the NIST "
    "Cybersecurity Framework."
)


async def fetch_nist_documents(spec: KnowledgeSourceSpec, *, limit: int = 6) -> list[dict[str, Any]]:
    if spec.source_id == "cyber.nist.sp800-53":
        return [
            {
                "external_id": "sp800-53r5-summary",
                "title": "NIST SP 800-53 Rev. 5 — Control catalog overview",
                "content": _SP80053_SUMMARY,
                "citation": "NIST SP 800-53 Rev. 5 (https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)",
                "jurisdiction": "US",
                "topics": ["sp800-53", "controls"],
                "effective_at": "2020-09-23T00:00:00Z",
                "metadata": {"csf_function": None, "license_type": "A"},
            }
        ][:limit]

    docs: list[dict[str, Any]] = []
    # Optional live fetch of CSF landing page metadata (not a copyrighted third-party blog).
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.get("https://www.nist.gov/cyberframework")
            if resp.status_code == 200 and "Cybersecurity Framework" in resp.text:
                pass
    except Exception:  # noqa: BLE001
        pass

    for fn in _CSF2_FUNCTIONS[:limit]:
        docs.append(
            {
                "external_id": f"csf2-{fn['id']}",
                "title": fn["title"],
                "content": (
                    f"{fn['text']}\n\n"
                    "Source: National Institute of Standards and Technology (2024) "
                    "The NIST Cybersecurity Framework (CSF) 2.0. NIST CSWP 29. "
                    "https://doi.org/10.6028/NIST.CSWP.29 — Reprinted courtesy of NIST."
                ),
                "citation": "NIST CSF 2.0 (NIST.CSWP.29) — https://doi.org/10.6028/NIST.CSWP.29",
                "jurisdiction": "US",
                "topics": ["csf2", fn["id"]],
                "effective_at": "2024-02-26T00:00:00Z",
                "published_at": "2024-02-26T00:00:00Z",
                "metadata": {"csf_function": fn["id"], "license_type": "A"},
            }
        )
    return docs
