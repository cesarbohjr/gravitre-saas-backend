"""Phase 1 — decide whether retrieved evidence is actually enough to answer.

The Knowledge Fabric Router already retrieves from several sources in one pass.
What it never did was ask whether the result *answers the question*. The only
existing escalation signal, ``assess_internal_retrieval_thinness``, counts rows
and compares a score:

    source_count <= THIN_SOURCE_COUNT  or  retrieval_score < THIN_RETRIEVAL_SCORE

Four irrelevant chunks clear that bar. This module asks the different question:
does the retrieved evidence directly address what was asked, is it current
enough, and does it come from a source with enough authority *for this kind of
query*.

Two deliberate choices:

  * The bar is not uniform. A jurisdictional or regulatory question needs a
    citable, in-date, authoritative source; a general business question does
    not. The bar is derived from the EXISTING router classification
    (``KnowledgeRoute.departments`` / ``.jurisdictions``) — this does not add a
    second classifier.
  * The verdict carries Module C labelling, because "evidence is sufficient" is
    itself an estimate produced by a model, and this program does not present
    estimates as measurements.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    label_confidence,
)

logger = get_logger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

# Departments whose answers carry regulatory or contractual consequence, so an
# uncited or stale source is not an acceptable basis for an answer.
_HIGH_BAR_DEPARTMENTS = frozenset({"legal", "cybersecurity", "finance"})

_COMPLIANCE_MARKERS = re.compile(
    r"\b(complian|regulat|statut|legal|liabilit|gdpr|hipaa|pipeda|sox|pci|ccpa|"
    r"contract|audit|penalt|jurisdiction|law|attorney|tax)\w*",
    re.I,
)

BAR_REGULATORY = "regulatory"
BAR_BUSINESS = "business"
BAR_CASUAL = "casual"

# Who produced the verdict. These are named constants rather than inline strings
# for a specific, already-paid-for reason: the grounding validator recorded
# `assessorRan` by comparing its confidence source against a literal "model"
# while the real value was "loaded_model_artifact". The field read False on
# every event for weeks, and was interpreted as "the validator always fails
# open" -- a confident conclusion drawn from a typo. Any consumer deciding
# whether this assessor really ran must compare against these, never a literal.
ASSESSOR_LLM = "llm"
ASSESSOR_DETERMINISTIC = "deterministic"
ASSESSOR_ERROR = "assessor_error"
ASSESSOR_SKIPPED_CASUAL = "skipped_casual_bar"

# A model genuinely reasoned about the evidence.
MODEL_ASSESSORS = frozenset({ASSESSOR_LLM})
# The check did not run at all. Distinct from a reasoned shortfall: sufficiency
# is UNKNOWN, not denied.
UNAVAILABLE_ASSESSORS = frozenset({ASSESSOR_ERROR})


@dataclass
class SufficiencyBar:
    """How much evidence this query type needs before an answer is dependable."""

    name: str
    min_sources: int
    require_citable_source: bool
    require_freshness_signal: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar": self.name,
            "min_sources": self.min_sources,
            "require_citable_source": self.require_citable_source,
            "require_freshness_signal": self.require_freshness_signal,
            "bar_reason": self.reason,
        }


@dataclass
class SufficiencyVerdict:
    sufficient: bool
    bar: SufficiencyBar
    assessor: str
    reason: str
    gaps: list[str] = field(default_factory=list)
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sufficient": self.sufficient,
            "assessor": self.assessor,
            "reason": self.reason[:400],
            "gaps": list(self.gaps)[:6],
        }
        payload.update(self.bar.to_dict())
        # The sufficiency judgement is a model/heuristic output, never a
        # measurement — Module C labelling is mandatory, not decorative.
        payload.update(
            label_confidence(
                self.confidence,
                source=CONFIDENCE_SOURCE_HEURISTIC,
                is_estimate=True,
                key="assessment_confidence",
            )
        )
        return payload


def sufficiency_bar_for(
    *,
    query: str,
    route_departments: list[str] | None = None,
    route_jurisdictions: list[str] | None = None,
    reasoning_depth: str = "full",
) -> SufficiencyBar:
    """Pick the bar from the router's own classification. No new classifier."""
    if (reasoning_depth or "full").strip().lower() == "conversational":
        return SufficiencyBar(
            name=BAR_CASUAL,
            min_sources=0,
            require_citable_source=False,
            require_freshness_signal=False,
            reason="conversational reasoning depth — spoken/simple turn stays on the fast path",
        )

    departments = {str(d).strip().lower() for d in (route_departments or []) if d}
    jurisdictions = [str(j).strip() for j in (route_jurisdictions or []) if j]
    high_departments = sorted(departments & _HIGH_BAR_DEPARTMENTS)
    compliance_hit = bool(_COMPLIANCE_MARKERS.search(query or ""))

    if high_departments or jurisdictions or compliance_hit:
        bits = []
        if high_departments:
            bits.append(f"department={','.join(high_departments)}")
        if jurisdictions:
            bits.append(f"jurisdiction={','.join(jurisdictions)}")
        if compliance_hit:
            bits.append("compliance/regulatory language in query")
        return SufficiencyBar(
            name=BAR_REGULATORY,
            min_sources=2,
            require_citable_source=True,
            require_freshness_signal=True,
            reason="; ".join(bits),
        )

    return SufficiencyBar(
        name=BAR_BUSINESS,
        min_sources=1,
        require_citable_source=False,
        require_freshness_signal=False,
        reason=(
            f"department={','.join(sorted(departments))}"
            if departments
            else "general business question"
        ),
    )


def summarize_evidence_process(
    knowledge_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Compact, user-facing account of the retrieval process — or None.

    Returns None for the common case: one pass, evidence met the bar, sources
    agreed. Phase 4's requirement is that this transparency shows up when it
    changes what the reader should think about the answer, not on every turn.
    """
    if not isinstance(knowledge_meta, dict):
        return None
    loop = knowledge_meta.get("evidenceSufficiency")
    conflicts = knowledge_meta.get("evidenceConflicts")
    loop = loop if isinstance(loop, dict) else {}
    conflicts = conflicts if isinstance(conflicts, dict) else {}

    rounds = int(loop.get("additional_rounds_used") or 0)
    fell_short = loop.get("final_sufficient") is False
    conflict_count = int(conflicts.get("count") or 0)
    if rounds == 0 and not fell_short and conflict_count == 0:
        return None

    summary: dict[str, Any] = {
        "sources_checked": list(loop.get("sources_tried") or []),
        "retrieval_rounds": 1 + rounds,
        "additional_rounds_triggered": rounds,
        "evidence_standard": loop.get("bar"),
        "evidence_met_standard": loop.get("final_sufficient"),
    }
    if fell_short:
        summary["shortfall"] = list(loop.get("final_gaps") or [])[:4]
        summary["shortfall_reason"] = str(loop.get("final_reason") or "")[:300]
        summary["stopped_because"] = loop.get("stopped_because")
    if conflict_count:
        summary["source_conflicts"] = {
            "detected": conflict_count,
            "resolved": int(conflicts.get("resolved") or 0),
            "unresolved": int(conflicts.get("unresolved") or 0),
            "details": [
                {
                    "subject": row.get("subject"),
                    "resolution": row.get("resolution"),
                    "rationale": row.get("rationale"),
                }
                for row in (conflicts.get("details") or [])[:3]
                if isinstance(row, dict)
            ],
        }
    # An answer whose evidence never met the bar, or that rests on an unresolved
    # source conflict, must not read as fully verified.
    if fell_short or int(conflicts.get("unresolved") or 0) > 0:
        summary["confidence_note"] = (
            "Evidence did not fully meet the standard for this question; "
            "treat the answer as provisional."
            if fell_short
            else "Sources disagree and the conflict could not be resolved from "
            "authority or effective dates."
        )
    return summary


def _has_citable_source(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("citation") or row.get("url") or row.get("web_link"):
            return True
        if row.get("authority_score") is not None:
            return True
    return False


def _has_freshness_signal(rows: list[dict[str, Any]]) -> bool:
    keys = (
        "freshness_score",
        "effective_at",
        "valid_from",
        "last_updated",
        "published_at",
    )
    for row in rows:
        if isinstance(row, dict) and any(row.get(k) is not None for k in keys):
            return True
    return False


def _evidence_digest(rows: list[dict[str, Any]], limit: int = 8) -> str:
    lines: list[str] = []
    for index, row in enumerate(rows[:limit], start=1):
        if not isinstance(row, dict):
            continue
        label = str(
            row.get("citation") or row.get("source") or row.get("kind") or "source"
        )[:80]
        body = str(row.get("content") or "").strip().replace("\n", " ")[:340]
        if not body:
            continue
        meta_bits = []
        if row.get("authority_score") is not None:
            meta_bits.append(f"authority={row.get('authority_score')}")
        for date_key in ("effective_at", "valid_from", "last_updated"):
            if row.get(date_key):
                meta_bits.append(f"{date_key}={row.get(date_key)}")
                break
        suffix = f" ({'; '.join(meta_bits)})" if meta_bits else ""
        lines.append(f"[{index}] {label}{suffix}\n{body}")
    return "\n\n".join(lines)


async def assess_evidence_sufficiency(
    *,
    query: str,
    rows: list[dict[str, Any]],
    bar: SufficiencyBar,
    settings: Settings | None = None,
    org_id: str | None = None,
    routing_tier: str = "multi_step",
    sources_tried: list[str] | None = None,
) -> SufficiencyVerdict:
    """Reasoned sufficiency judgement, with deterministic short-circuits first.

    Deterministic checks come first only where they are decisive and cheap: no
    evidence at all, or a hard structural requirement of the bar that the rows
    plainly do not meet. Everything else goes to the model, because "does this
    evidence actually address the question" is not a countable property.
    """
    rows = [r for r in (rows or []) if isinstance(r, dict)]

    if bar.name == BAR_CASUAL:
        return SufficiencyVerdict(
            sufficient=True,
            bar=bar,
            assessor=ASSESSOR_SKIPPED_CASUAL,
            reason="conversational turn — sufficiency loop does not engage",
            confidence=None,
        )

    substantive = [r for r in rows if str(r.get("content") or "").strip()]
    if len(substantive) < max(1, bar.min_sources):
        return SufficiencyVerdict(
            sufficient=False,
            bar=bar,
            assessor=ASSESSOR_DETERMINISTIC,
            reason=(
                f"{len(substantive)} substantive source(s) retrieved; "
                f"{bar.name} bar needs at least {bar.min_sources}"
            ),
            gaps=["insufficient_source_count"],
            confidence=None,
        )

    # Only one structural veto: a regulatory answer with nothing attributable
    # behind it is unusable regardless of what it says.
    #
    # Missing freshness deliberately is NOT a veto. Live traffic showed why: web
    # results carry no date from the provider, so a dated-source requirement made
    # every web-answered regulatory question fail the gate before any reasoning
    # happened, which both skipped the real assessment and guaranteed the loop
    # burned its whole round budget for nothing. Currency matters, so it is
    # passed to the assessor as a weighted input instead of a dead end.
    if bar.require_citable_source and not _has_citable_source(substantive):
        return SufficiencyVerdict(
            sufficient=False,
            bar=bar,
            assessor=ASSESSOR_DETERMINISTIC,
            reason=(
                f"{bar.name} bar requires an attributable source, and none of the "
                f"{len(substantive)} retrieved excerpts carry a citation, URL, or "
                "authority score"
            ),
            gaps=["no_citable_source"],
            confidence=None,
        )

    freshness_missing = bar.require_freshness_signal and not _has_freshness_signal(
        substantive
    )
    digest = _evidence_digest(substantive)
    tried = ", ".join(sources_tried or []) or "unknown"
    prompt = (
        "You judge whether retrieved evidence is sufficient to answer a question "
        "dependably. You are NOT answering the question.\n\n"
        f"Question:\n{(query or '')[:1200]}\n\n"
        f"Sources already searched: {tried}\n"
        f"Evidence standard for this question: {bar.name} "
        f"({bar.reason or 'general'}).\n"
        + (
            "A regulatory/legal standard means: the evidence must directly state the "
            "answer, be attributable to a citable authority, and be current.\n"
            if bar.name == BAR_REGULATORY
            else "A business standard means: the evidence must directly address the "
            "question well enough to answer without guessing.\n"
        )
        + (
            "NOTE: none of the retrieved evidence carries an effective date or "
            "last-updated signal. Decide whether currency actually matters for "
            "THIS question — a question asking for a current effective date, rate, "
            "or deadline is not answerable dependably without it, while a stable "
            "definitional or structural question may be.\n"
            if freshness_missing
            else ""
        )
        + f"\nRetrieved evidence:\n{digest or '(none)'}\n\n"
        "Judge three things: (1) does the evidence directly address what was asked, "
        "or only the general topic; (2) is it current enough for the question; "
        "(3) is the source authority adequate for this standard.\n"
        'Return JSON only: {"sufficient": bool, "reason": str, '
        '"gaps": [str], "confidence": number between 0 and 1}. '
        "gaps names what is missing, e.g. does_not_address_question, stale_evidence, "
        "weak_authority, partial_coverage. Be strict: topic-adjacent evidence that "
        "does not contain the answer is NOT sufficient."
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
            max_tokens=320,
        )
        raw = str(response.content or "").strip()
        match = _JSON_BLOCK.search(raw)
        if not match:
            raise ValueError("no JSON in sufficiency response")
        parsed = json.loads(match.group(0))
        raw_conf = parsed.get("confidence")
        confidence = None
        if isinstance(raw_conf, (int, float)):
            confidence = max(0.0, min(1.0, float(raw_conf)))
        sufficient = bool(parsed.get("sufficient", True))
        gaps = [str(g) for g in (parsed.get("gaps") or []) if g]
        # Keep the undated-evidence fact visible in the shortfall record when the
        # assessor concluded the evidence falls short, so the reported reason
        # includes it even if the model phrased the gap differently.
        if not sufficient and freshness_missing and "no_freshness_signal" not in gaps:
            gaps.append("no_freshness_signal")
        return SufficiencyVerdict(
            sufficient=sufficient,
            bar=bar,
            assessor=ASSESSOR_LLM,
            reason=str(parsed.get("reason") or "").strip() or "model returned no reason",
            gaps=gaps,
            confidence=confidence,
        )
    except Exception as exc:  # noqa: BLE001
        # An assessor failure means sufficiency is UNKNOWN, which is not the same
        # thing as sufficient. Reporting sufficient=True here told the rest of the
        # turn that a regulatory answer had cleared its evidence bar when nothing
        # had actually evaluated it — the precise "full confidence on unverified
        # evidence" outcome the loop exists to prevent. A live prod run at tip
        # f8dc5f64 hit exactly this and reported final_sufficient=True off a
        # TypeError.
        #
        # Sufficiency is therefore withheld, but no further rounds are spent: more
        # retrieval cannot fix a broken assessor, and burning the round budget on
        # every turn whenever the fast model hiccups would be its own regression.
        # The caller distinguishes this from a reasoned shortfall via the assessor
        # field, so the answer is labeled unverified rather than under-evidenced.
        logger.warning("sufficiency_assessor_failed org_id=%s error=%s", org_id, exc)
        return SufficiencyVerdict(
            sufficient=False,
            bar=bar,
            assessor=ASSESSOR_ERROR,
            reason=f"sufficiency assessor unavailable: {str(exc)[:160]}",
            gaps=["assessor_unavailable"],
            confidence=None,
        )
