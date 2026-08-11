"""Query classification router — department / jurisdiction / knowledge tier."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# US state / province hints for jurisdiction scoping
_STATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bCalifornia\b|\bCA\b", re.I), "US-CA"),
    (re.compile(r"\bNew York\b|\bNY\b", re.I), "US-NY"),
    (re.compile(r"\bTexas\b|\bTX\b", re.I), "US-TX"),
    (re.compile(r"\bOntario\b", re.I), "CA-ON"),
    (re.compile(r"\bBritish Columbia\b|\bB\.?C\.?\b", re.I), "CA-BC"),
    (re.compile(r"\bfederal\b|\bU\.?S\.?\b|\bUnited States\b", re.I), "US-federal"),
]

_DEPT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "legal": ("law", "statute", "regulation", "court", "opinion", "jurisdiction", "employment law", "flsa", "fmla"),
    "finance": ("sec", "edgar", "filing", "10-k", "xbrl", "revenue", "gaap", "earnings"),
    "cybersecurity": ("nist", "csf", "cyber", "incident", "sp 800", "controls", "msp"),
    "hr": ("employee", "payroll", "hiring", "occupation", "o*net", "leave", "wage", "labor"),
    "sales": ("pipeline", "quota", "prospect", "crm deal"),
    "marketing": ("campaign", "brand", "seo", "content calendar"),
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
    for pat, code in _STATE_PATTERNS:
        if pat.search(text):
            jurisdictions.append(code)
    if not jurisdictions and any(d == "legal" for d in departments):
        jurisdictions.append("US-federal")

    pack_ids = []
    for d in departments:
        pid = _PACK_BY_DEPT.get(d)
        if pid:
            pack_ids.append(pid)
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
