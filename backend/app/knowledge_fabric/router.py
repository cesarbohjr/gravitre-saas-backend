"""Query classification router — department / jurisdiction / knowledge tier."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Jurisdiction hints — Canada federal must win over bare "CA" (California postal)
_CANADA_FEDERAL_PAT = re.compile(
    r"\bCanada\b|\bCanadian\b|\bPIPEDA\b|\bJustice Laws\b|"
    r"\bCompetition Bureau\b|\blaws-lois\.justice\.gc\.ca\b|"
    r"\bCanada Open Government\b",
    re.I,
)
_STATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bCalifornia\b", re.I), "US-CA"),
    # Bare CA only when not clearly Canada (handled separately above)
    (re.compile(r"(?<![A-Za-z])\bCA\b(?![A-Za-z])", re.I), "US-CA"),
    (re.compile(r"\bNew York\b|\bNY\b", re.I), "US-NY"),
    (re.compile(r"\bTexas\b|\bTX\b", re.I), "US-TX"),
    (re.compile(r"\bOntario\b", re.I), "CA-ON"),
    (re.compile(r"\bBritish Columbia\b|\bB\.?C\.?\b", re.I), "CA-BC"),
    (re.compile(r"\bU\.?S\.?\b|\bUnited States\b", re.I), "US-federal"),
    (re.compile(r"\bfederal\b", re.I), "US-federal"),
]

_DEPT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "legal": (
        "law",
        "statute",
        "regulation",
        "court",
        "opinion",
        "jurisdiction",
        "constitution",
        "equal protection",
        "employment law",
        "flsa",
        "fmla",
        "ftc",
        "can-spam",
        "can spam",
        "endorsement guide",
        "deceptive advertising",
        "native advertising",
        "pipeda",
        "justice laws",
        "competition act",
        "competition bureau",
    ),
    "finance": ("sec", "edgar", "filing", "10-k", "xbrl", "revenue", "gaap", "earnings"),
    "cybersecurity": (
        "nist",
        "csf",
        "cyber",
        "incident",
        "sp 800",
        "controls",
        "msp",
        "cisa",
        "ransomware",
        "zero trust",
        "ai rmf",
    ),
    "hr": (
        "employee",
        "payroll",
        "hiring",
        "occupation",
        "o*net",
        "leave",
        "wage",
        "labor",
        "eeoc",
        "employment law guide",
    ),
    "sales": (
        "pipeline",
        "quota",
        "prospect",
        "crm deal",
        "sales management",
        "personal selling",
        "quota attainment",
        "census",
        "establishments",
        "business formation",
    ),
    "marketing": (
        "campaign",
        "brand",
        "seo",
        "content calendar",
        "marketing",
        "segmentation",
        "positioning",
        "consumer behavior",
        "market research",
        "advertising",
        "influencer",
        "can-spam",
        "can spam",
        "native advertising",
        "google trends",
        "customer acquisition",
    ),
}


@dataclass
class KnowledgeRoute:
    departments: list[str] = field(default_factory=list)
    jurisdictions: list[str] = field(default_factory=list)
    tiers: list[str] = field(default_factory=lambda: ["customer_rag", "expert_pack"])
    pack_ids: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "departments": self.departments,
            "jurisdictions": self.jurisdictions,
            "tiers": self.tiers,
            "pack_ids": self.pack_ids,
            "reason": self.reason,
        }


_PACK_BY_DEPT = {
    "legal": "pack.legal",
    "finance": "pack.finance",
    "cybersecurity": "pack.cybersecurity",
    "hr": "pack.hr",
    "sales": "pack.sales",
    "marketing": "pack.marketing",
}


def classify_knowledge_query(
    query: str,
    *,
    assigned_pack_ids: list[str] | None = None,
    agent_department: str | None = None,
    allow_live_internet: bool = False,
) -> KnowledgeRoute:
    text = (query or "").strip()
    lower = text.lower()
    departments: list[str] = []
    for dept, keys in _DEPT_KEYWORDS.items():
        if any(k in lower for k in keys):
            departments.append(dept)
    if not departments and agent_department:
        dept = agent_department.strip().lower()
        if dept in _PACK_BY_DEPT:
            departments = [dept]
        elif dept == "msp":
            departments = ["cybersecurity"]

    jurisdictions: list[str] = []
    canada_federal = bool(_CANADA_FEDERAL_PAT.search(text))
    if canada_federal:
        jurisdictions.append("CA-federal")
    for pat, code in _STATE_PATTERNS:
        if pat.search(text):
            # Skip bare-CA → US-CA when the query is clearly Canadian
            if code == "US-CA" and canada_federal and not re.search(r"\bCalifornia\b", text, re.I):
                continue
            # Bare "federal" alone under a Canada query → CA-federal (already set)
            if code == "US-federal" and canada_federal and not re.search(
                r"\bU\.?S\.?\b|\bUnited States\b", text, re.I
            ):
                continue
            if code not in jurisdictions:
                jurisdictions.append(code)
    if not jurisdictions and any(d == "legal" for d in departments):
        jurisdictions.append("US-federal")

    pack_ids = []
    for d in departments:
        pid = _PACK_BY_DEPT.get(d)
        if pid and pid not in pack_ids:
            pack_ids.append(pid)
    # Marketing compliance (FTC / CAN-SPAM / endorsements / Competition Bureau)
    # should retrieve Legal + Marketing together
    compliance_markers = (
        "can-spam",
        "can spam",
        "ftc",
        "endorsement",
        "influencer",
        "native advertising",
        "deceptive advertising",
        "competition bureau",
        "deceptive marketing",
    )
    if any(m in lower for m in compliance_markers):
        for pid in ("pack.marketing", "pack.legal"):
            if pid not in pack_ids:
                pack_ids.append(pid)
        if "marketing" not in departments:
            departments.append("marketing")
        if "legal" not in departments:
            departments.append("legal")
    assigned = [p for p in (assigned_pack_ids or []) if p]
    if assigned:
        # Only retrieve from packs the agent is entitled to
        pack_ids = [p for p in pack_ids if p in assigned] or list(assigned)

    tiers = ["customer_rag", "expert_pack"]
    if allow_live_internet or "latest news" in lower or "search the web" in lower:
        tiers.append("live_internet")

    reason = (
        f"departments={departments or ['unspecified']}; "
        f"jurisdictions={jurisdictions or ['none']}; "
        f"packs={pack_ids}"
    )
    return KnowledgeRoute(
        departments=departments,
        jurisdictions=jurisdictions,
        tiers=tiers,
        pack_ids=pack_ids,
        reason=reason,
    )
