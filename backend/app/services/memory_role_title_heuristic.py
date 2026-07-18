"""STA-320 Option B — Non-PII role/title heuristic (no embeddings).

Matches assignee mentions that look like org roles/titles (e.g. "the AE")
against durable `org_entity_resolution_records` rows with entity_type="role".

Does not embed names/emails, does not soft-match person names, and does not
require memoryEntityEmbeddings opt-in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.services.entity_resolution_store import lookup_resolutions, normalize_alias, upsert_resolution
from app.services.query_normalization import normalize_query

logger = get_logger(__name__)

ROLE_ENTITY_TYPE = "role"
LEARN_SOURCE = "role_title_heuristic"


@dataclass(frozen=True)
class RoleMatchResult:
    status: str  # bound | ambiguous | miss
    entity_id: str | None = None
    candidates: tuple[tuple[str, str], ...] = ()  # (entity_id, role_label)
    reason: str = ""

# Canonical role tokens → aliases we store/lookup (all normalized later).
_ROLE_LEXICON: dict[str, tuple[str, ...]] = {
    "ae": ("ae", "account executive"),
    "account executive": ("ae", "account executive"),
    "sdr": ("sdr", "sales development representative"),
    "sales development representative": ("sdr", "sales development representative"),
    "bdr": ("bdr", "business development representative"),
    "business development representative": ("bdr", "business development representative"),
    "csm": ("csm", "customer success manager"),
    "customer success manager": ("csm", "customer success manager"),
    "account manager": ("account manager", "am"),
    "am": ("am", "account manager"),
    "vp sales": ("vp sales", "vp of sales"),
    "vp of sales": ("vp sales", "vp of sales"),
    "head of sales": ("head of sales",),
    "head of marketing": ("head of marketing",),
    "head of support": ("head of support",),
    "head of engineering": ("head of engineering",),
    "sales lead": ("sales lead",),
    "marketing lead": ("marketing lead",),
    "support lead": ("support lead",),
    "engineering lead": ("engineering lead",),
}

_DEPTS = ("sales", "marketing", "support", "engineering", "customer success", "ops", "operations")

# Bare first-name-ish tokens we refuse to treat as role cues.
_NAME_LIKE = re.compile(r"^[a-z]{2,20}$")
_THE_ROLE = re.compile(
    r"\b(?:the\s+)?("
    + "|".join(
        re.escape(k)
        for k in sorted(_ROLE_LEXICON.keys(), key=len, reverse=True)
    )
    + r")\b",
    re.IGNORECASE,
)
_DEPT_LEAD = re.compile(
    r"\b(" + "|".join(re.escape(d) for d in _DEPTS) + r")\s+lead\b",
    re.IGNORECASE,
)
_VP_OF_DEPT = re.compile(
    r"\bvp\s+(?:of\s+)?(" + "|".join(re.escape(d) for d in _DEPTS) + r")\b",
    re.IGNORECASE,
)


def extract_role_title_cues(mention: str) -> list[str]:
    """Return normalized role/title cue aliases for lookup. Empty if none."""
    raw = (mention or "").strip()
    if not raw:
        return []
    norm = normalize_query(raw)
    if not norm:
        return []

    cues: list[str] = []
    seen: set[str] = set()

    def _add(alias: str) -> None:
        a = normalize_alias(alias)
        if a and a not in seen:
            seen.add(a)
            cues.append(a)

    for match in _THE_ROLE.finditer(norm):
        key = match.group(1).lower()
        for alias in _ROLE_LEXICON.get(key, (key,)):
            _add(alias)

    for match in _DEPT_LEAD.finditer(norm):
        _add(f"{match.group(1).lower()} lead")

    for match in _VP_OF_DEPT.finditer(norm):
        dept = match.group(1).lower()
        _add(f"vp {dept}")
        _add(f"vp of {dept}")

    # Exact full-string role phrase (no surrounding name noise).
    if norm in _ROLE_LEXICON:
        for alias in _ROLE_LEXICON[norm]:
            _add(alias)

    # Reject bare person-name-looking single tokens with no lexicon hit.
    if not cues and _NAME_LIKE.fullmatch(norm):
        return []

    return cues


def match_by_role_cues(
    client: Any,
    *,
    org_id: str,
    integration: str,
    cues: list[str],
) -> RoleMatchResult:
    """Lookup role aliases; unique entity → bound; multi → ambiguous (role labels)."""
    if not cues:
        return RoleMatchResult(status="miss", reason="role_title_no_cues")

    hits = lookup_resolutions(
        client,
        org_id,
        cues,
        integration=integration,
        limit=20,
    )
    role_hits = [h for h in hits if h.entity_type == ROLE_ENTITY_TYPE]
    if not role_hits:
        return RoleMatchResult(status="miss", reason="role_title_no_match")

    by_entity: dict[str, str] = {}
    for hit in role_hits:
        eid = (hit.entity_id or "").strip()
        if not eid:
            continue
        # Prefer the cue alias as the clarify label (non-PII).
        by_entity.setdefault(eid, hit.alias_normalized or "role")

    if len(by_entity) == 1:
        eid, label = next(iter(by_entity.items()))
        return RoleMatchResult(
            status="bound",
            entity_id=eid,
            candidates=((eid, label),),
            reason="role_title_exact",
        )
    if len(by_entity) > 1:
        candidates = tuple((eid, label) for eid, label in list(by_entity.items())[:5])
        return RoleMatchResult(
            status="ambiguous",
            candidates=candidates,
            reason="role_title_ambiguous",
        )
    return RoleMatchResult(status="miss", reason="role_title_empty_ids")


def learn_role_aliases(
    client: Any,
    *,
    org_id: str,
    integration: str,
    entity_id: str,
    mention: str,
    confidence: float = 0.85,
) -> int:
    """Persist role cues from a uniquely bound mention as entity_type=role aliases."""
    eid = str(entity_id or "").strip()
    if not org_id or not eid:
        return 0
    cues = extract_role_title_cues(mention)
    if not cues:
        return 0
    written = 0
    for cue in cues:
        try:
            if upsert_resolution(
                client,
                org_id=org_id,
                alias=cue,
                entity_type=ROLE_ENTITY_TYPE,
                entity_id=eid,
                integration=integration,
                source=LEARN_SOURCE,
                confidence=confidence,
            ):
                written += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "role_title_learn_skipped org_id=%s cue=%s error=%s",
                org_id,
                cue,
                exc,
            )
    return written
