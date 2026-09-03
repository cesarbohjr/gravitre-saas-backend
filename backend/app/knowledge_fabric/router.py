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
        # "statute" does not cover "statutory": the suffix rule below appends to
        # a whole keyword, and "statute" + "ory" is not a word. Measured on real
        # traffic, "statutory" was the second most common piece of legal
        # vocabulary in messages that routed nowhere.
        "statutory",
        "regulation",
        # Covers "regulator", "regulators" and "regulatory" under the suffix rule.
        "regulator",
        "court",
        "opinion",
        "jurisdiction",
        "constitution",
        "equal protection",
        "employment law",
        "contract",
        "liability",
        "indemnity",
        # Privacy vocabulary was absent from this list entirely, so the most
        # ordinary privacy question in the product routed to no department and
        # retrieved no legal evidence. This is the gap Phase 5 surfaced.
        "privacy",
        "personal information",
        "personal data",
        "breach notification",
        "data subject",
        "hipaa",
        "gdpr",
        "ccpa",
        "cpra",
        "phipa",
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


# Keywords that must match as a whole word, with no suffix allowed.
#
# The default rule below deliberately allows a suffix, because measured on 1982
# real user messages the suffix matches are overwhelmingly the ones we want:
# "prospect" firing inside "prospects" (21) and "prospecting" (9), "msp" inside
# "msps" (10), "cyber" inside "cybersecurity" (7). A naive word-boundary fix
# would have destroyed all of those to remove a smaller number of accidents --
# the obvious fix, measurably worse than the defect.
#
# What the same measurement showed genuinely wrong was "sec", the finance
# keyword for SEC filings, firing inside "secondary" (13), "security" (2) and
# "cybersecurity" (2). Every one of its partial matches was an accident, and it
# was routing security questions to finance.
#
# The rest are acronyms already in the vocabulary that prefix common English
# words -- "seo" in "Seoul", "csf" and "cisa" in assorted identifiers. They carry
# no measured accidents, unlike "sec"; they are listed because the same accident
# is available to them, and that reason is stated rather than left to look like
# data.
#
# Every entry must be a keyword that actually exists. An entry for a keyword the
# router does not have protects nothing while reading as though it does, so
# `test_every_exact_only_keyword_is_actually_in_the_vocabulary` fails on one.
# That test is why "phi" and "dpa" are not here: they were added on the
# assumption they were vocabulary, and they are not.
_EXACT_ONLY_KEYWORDS = frozenset(
    {"sec", "seo", "ftc", "csf", "gaap", "xbrl", "eeoc", "cisa"}
)


def _compile_keyword(keyword: str) -> re.Pattern[str]:
    """One keyword, as the pattern that decides whether it fired.

    Left edge is always a boundary. That alone removes the whole class of
    mid-word accidents the old naked `in` test produced: "law" inside "flawed",
    "law" inside "outlaw", "incident" inside "coincident". Those were routing
    ordinary sentences to legal and cybersecurity.

    Right edge depends on the keyword. Ordinary words allow an alphabetic suffix
    so inflections match; acronyms do not.
    """
    escaped = re.escape(keyword)
    left = r"(?<![a-z0-9])"
    if keyword in _EXACT_ONLY_KEYWORDS:
        return re.compile(left + escaped + r"(?![a-z0-9])")
    return re.compile(left + escaped + r"[a-z]*")


# Compiled once at import. `_DEPT_KEYWORDS` stays the single source of the
# vocabulary so the reachability probe and the tests read the same list the
# router does, rather than a copy free to drift from it.
_DEPT_MATCHERS: dict[str, tuple[re.Pattern[str], ...]] = {
    dept: tuple(_compile_keyword(k) for k in keys)
    for dept, keys in _DEPT_KEYWORDS.items()
}

# Marketing compliance (FTC / CAN-SPAM / endorsements / Competition Bureau)
# retrieves Legal and Marketing together. Compiled through the same rule as the
# department keywords: it had the identical naked-substring defect, and fixing
# one and not the other would leave half the router matching by accident.
_COMPLIANCE_MARKERS = (
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
_COMPLIANCE_MATCHERS = tuple(_compile_keyword(m) for m in _COMPLIANCE_MARKERS)


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

# Agent UI department labels → router department keys (existing correlation).
_AGENT_DEPT_ALIASES: dict[str, str] = {
    "legal": "legal",
    "finance": "finance",
    "cybersecurity": "cybersecurity",
    "cyber": "cybersecurity",
    "msp": "cybersecurity",
    "it": "cybersecurity",
    "hr": "hr",
    "sales": "sales",
    "marketing": "marketing",
    "operations": "cybersecurity",
    "support": "legal",
}


def normalize_agent_department(agent_department: str | None) -> str | None:
    if not agent_department:
        return None
    key = agent_department.strip().lower()
    return _AGENT_DEPT_ALIASES.get(key) or (key if key in _PACK_BY_DEPT else None)


def recommended_pack_ids_for_department(agent_department: str | None) -> list[str]:
    """Surface existing _PACK_BY_DEPT + registry secondary_packs correlation for UI.

    Recommendation only — never a restriction on which packs can be assigned.
    """
    from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES

    dept = normalize_agent_department(agent_department)
    if not dept:
        return []
    primary = _PACK_BY_DEPT.get(dept)
    out: list[str] = []
    if primary:
        out.append(primary)
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        if primary and spec.pack_id == primary:
            for sp in spec.secondary_packs:
                if sp not in out:
                    out.append(sp)
        if spec.department == dept and spec.pack_id not in out:
            out.append(spec.pack_id)
    return out


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
    for dept, matchers in _DEPT_MATCHERS.items():
        if any(m.search(lower) for m in matchers):
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
    if any(m.search(lower) for m in _COMPLIANCE_MATCHERS):
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
