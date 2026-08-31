"""Phase 3 — find real conflicts between sources, resolve them or say so.

Before this, when org RAG said one thing and a Knowledge Fabric pack said
another, both went into the prompt as undifferentiated excerpts and the model
picked — silently, with no record that a conflict existed. That is the failure
mode this program keeps finding in other forms: an answer presented at full
confidence over evidence that did not agree with itself.

Resolution uses only signals that already exist and are already populated:

  ``authority_score``  registry-backed source authority (knowledge_fabric)
  ``effective_at`` / ``valid_from`` / ``last_updated``  effective dating
  ``superseded_at`` / ``superseded_by``  explicit supersession
  ``kind``  org-private evidence outranks general knowledge for org-specific
            questions, since a customer's own record is the authority on itself

When those signals cannot separate the claims, the conflict is surfaced to the
user rather than resolved. Guessing and calling it an answer is the thing being
prevented, so an unresolved conflict is a valid, reportable outcome.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

# Org-private evidence wins on org-specific questions; platform packs win on
# general regulatory questions. Used only to break ties the dated/authority
# signals could not.
_ORG_PRIVATE_KINDS = frozenset({"knowledge", "memory", "hybrid_memory", "graph"})
_GENERAL_KINDS = frozenset({"knowledge_pack", "internet", "intelligence_pack"})

_DATE_KEYS = ("effective_at", "valid_from", "last_updated", "published_at")


@dataclass
class Contradiction:
    subject: str
    claims: list[dict[str, Any]] = field(default_factory=list)
    resolution: str = "unresolved"
    winner_index: int | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject[:200],
            "resolution": self.resolution,
            "winner_index": self.winner_index,
            "rationale": self.rationale[:400],
            "claims": [
                {
                    "index": c.get("index"),
                    "kind": c.get("kind"),
                    "source": str(c.get("source") or c.get("citation") or "")[:120],
                    "claim": str(c.get("claim") or "")[:240],
                    "authority_score": c.get("authority_score"),
                    "as_of": c.get("as_of"),
                    "superseded": bool(c.get("superseded")),
                }
                for c in self.claims[:4]
            ],
        }


def _as_of(row: dict[str, Any]) -> str | None:
    for key in _DATE_KEYS:
        value = row.get(key)
        if value:
            return str(value)
    return None


# Authority is decisive only when the gap is real rather than ranking noise.
# Expressed in normalized 0..1 space — see _authority for why that matters.
AUTHORITY_DECISIVE_GAP = 0.10


def _authority(row: dict[str, Any]) -> float | None:
    """Authority normalized to 0..1.

    Two scales are live in this codebase: knowledge_fabric stores chunk and
    source ``authority_score`` in 0..1 (real corpus rows read 0.97), while
    ``research_manager._KIND_AUTHORITY`` ranks source *kinds* on 0..100. A
    threshold written for one silently never fires on the other, which is
    exactly what happened here: a 10-point gap is unreachable when every real
    value sits below 1.0, so the authority rung was dead on real data and only
    looked alive under synthetic scores.
    """
    value = row.get("authority_score")
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score / 100.0 if score > 1.0 else score


def _is_org_specific(query: str) -> bool:
    return bool(
        re.search(
            r"\b(our|we|us|my|company'?s|internal|policy|handbook|team)\b", query or "", re.I
        )
    )


def resolve_contradiction(
    contradiction: Contradiction,
    *,
    query: str = "",
) -> Contradiction:
    """Apply existing authority / freshness / supersession signals, in that order."""
    claims = contradiction.claims
    if len(claims) < 2:
        contradiction.resolution = "not_a_conflict"
        contradiction.rationale = "fewer than two claims"
        return contradiction

    # 1. Explicit supersession is the strongest signal available: the corpus
    #    itself says one document replaced the other.
    live = [c for c in claims if not c.get("superseded")]
    superseded = [c for c in claims if c.get("superseded")]
    if live and superseded:
        winner = live[0]
        contradiction.resolution = "resolved_supersession"
        contradiction.winner_index = winner.get("index")
        contradiction.rationale = (
            f"{len(superseded)} conflicting claim(s) come from documents marked "
            f"superseded; kept the live source "
            f"{str(winner.get('source') or winner.get('kind'))!r}"
        )
        return contradiction

    # 2. Effective dating — a current statement beats a stale one on the same
    #    subject. Only usable when every claim carries a date.
    dated = [c for c in claims if c.get("as_of")]
    if len(dated) == len(claims) and len({str(c["as_of"]) for c in dated}) > 1:
        winner = max(dated, key=lambda c: str(c["as_of"]))
        loser_dates = sorted(str(c["as_of"]) for c in dated if c is not winner)
        contradiction.resolution = "resolved_freshness"
        contradiction.winner_index = winner.get("index")
        contradiction.rationale = (
            f"most recent effective date {str(winner['as_of'])} beats {', '.join(loser_dates)}"
        )
        return contradiction

    # 3. Source authority, when the gap is real rather than noise.
    scored = [(c, _authority(c)) for c in claims]
    with_scores = [(c, s) for c, s in scored if s is not None]
    if len(with_scores) == len(claims) and len(with_scores) > 1:
        with_scores.sort(key=lambda pair: pair[1], reverse=True)
        top, top_score = with_scores[0]
        _, second_score = with_scores[1]
        if top_score - second_score >= AUTHORITY_DECISIVE_GAP:
            contradiction.resolution = "resolved_authority"
            contradiction.winner_index = top.get("index")
            contradiction.rationale = (
                f"authority {top_score:.2f} vs {second_score:.2f} (normalized) — "
                f"kept the higher-authority source"
            )
            return contradiction

    # 4. Org-specific question: the customer's own record is authoritative about
    #    the customer. Only applied when the question is clearly about them.
    if _is_org_specific(query):
        org_claims = [c for c in claims if str(c.get("kind") or "") in _ORG_PRIVATE_KINDS]
        general = [c for c in claims if str(c.get("kind") or "") in _GENERAL_KINDS]
        if len(org_claims) == 1 and general:
            winner = org_claims[0]
            contradiction.resolution = "resolved_org_precedence"
            contradiction.winner_index = winner.get("index")
            contradiction.rationale = (
                "question is about this organization, so its own record takes "
                "precedence over general knowledge"
            )
            return contradiction

    contradiction.resolution = "unresolved"
    contradiction.rationale = (
        "no supersession marker, no complete effective dating, no decisive "
        "authority gap, and not an org-specific question — conflict surfaced "
        "rather than guessed"
    )
    return contradiction


async def detect_contradictions(
    *,
    query: str,
    rows: list[dict[str, Any]],
    settings: Settings | None = None,
    org_id: str | None = None,
    routing_tier: str = "multi_step",
) -> list[Contradiction]:
    """Ask for genuine factual conflicts only — not tone or phrasing differences."""
    usable = [
        r
        for r in (rows or [])
        if isinstance(r, dict) and str(r.get("content") or "").strip()
    ]
    if len(usable) < 2:
        return []

    lines: list[str] = []
    for index, row in enumerate(usable[:8]):
        label = str(row.get("citation") or row.get("source") or row.get("kind") or "source")
        body = str(row.get("content") or "").strip().replace("\n", " ")[:420]
        lines.append(f"[{index}] ({row.get('kind') or 'source'} — {label[:70]})\n{body}")

    prompt = (
        "Compare these retrieved sources for GENUINE factual contradictions on the "
        "same specific point — a different number, date, rule, status, or "
        "requirement for the same subject.\n"
        "Do NOT report: different wording for the same fact, different level of "
        "detail, different topics, or one source simply being silent.\n\n"
        f"Question being answered:\n{(query or '')[:800]}\n\n"
        f"Sources:\n" + "\n\n".join(lines) + "\n\n"
        'Return JSON only: {"contradictions": [{"subject": str, '
        '"claims": [{"index": int, "claim": str}]}]}. '
        "Empty list if the sources genuinely agree. Each contradiction must cite "
        "at least two source indexes."
    )

    try:
        from app.services.assistant_routing_tier import model_for_routing_phase
        from app.services.model_router import TaskType, get_model_router

        router = get_model_router()
        response = await router.complete(
            TaskType.SUMMARIZATION,
            prompt,
            org_id=org_id,
            model_override=model_for_routing_phase("verification", routing_tier),
            max_tokens=420,
        )
        raw = str(response.content or "").strip()
        match = _JSON_BLOCK.search(raw)
        if not match:
            return []
        parsed = json.loads(match.group(0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("contradiction_detect_failed org_id=%s error=%s", org_id, exc)
        return []

    found: list[Contradiction] = []
    for item in (parsed.get("contradictions") or [])[:4]:
        if not isinstance(item, dict):
            continue
        raw_claims = [c for c in (item.get("claims") or []) if isinstance(c, dict)]
        claims: list[dict[str, Any]] = []
        for claim in raw_claims:
            try:
                index = int(claim.get("index"))
            except (TypeError, ValueError):
                continue
            if not 0 <= index < len(usable):
                continue
            row = usable[index]
            claims.append(
                {
                    "index": index,
                    "claim": str(claim.get("claim") or "")[:300],
                    "kind": row.get("kind"),
                    "source": row.get("source") or row.get("citation"),
                    "citation": row.get("citation"),
                    "authority_score": _authority(row),
                    "as_of": _as_of(row),
                    "superseded": bool(row.get("superseded_at") or row.get("superseded_by")),
                }
            )
        # Two claims from the same source is a paraphrase, not a conflict.
        if len({c["index"] for c in claims}) < 2:
            continue
        found.append(
            resolve_contradiction(
                Contradiction(subject=str(item.get("subject") or "")[:200], claims=claims),
                query=query,
            )
        )
    return found


def format_contradiction_section(contradictions: list[Contradiction]) -> str:
    """Prompt block telling the model what conflicts, and what won, and why."""
    if not contradictions:
        return ""
    lines: list[str] = []
    for con in contradictions:
        if con.resolution.startswith("resolved"):
            winner = next(
                (c for c in con.claims if c.get("index") == con.winner_index), None
            )
            winner_label = str(
                (winner or {}).get("source") or (winner or {}).get("kind") or "the kept source"
            )
            lines.append(
                f"- CONFLICT on {con.subject or 'a retrieved fact'} — RESOLVED: use "
                f"{winner_label!r}. Reason: {con.rationale}. Do not repeat the "
                f"superseded or lower-authority version."
            )
        else:
            claim_bits = "; ".join(
                f"{str(c.get('source') or c.get('kind'))!r} says {str(c.get('claim') or '')[:140]}"
                for c in con.claims[:3]
            )
            lines.append(
                f"- CONFLICT on {con.subject or 'a retrieved fact'} — UNRESOLVED: "
                f"{claim_bits}. Tell the user these sources disagree and what each "
                f"says. Do not silently pick one."
            )
    return (
        "EVIDENCE CONFLICTS DETECTED ACROSS SOURCES (handle explicitly):\n"
        + "\n".join(lines)
    )
