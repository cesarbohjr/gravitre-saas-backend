"""Inject org RAG + platform knowledge fabric + auto internet into unified-turn LIVE.

Retrieval used to be strictly one pass: classify, pull packs, pull org RAG, and
if the result looked thin by row count, also pull the web. Whether any of it
answered the question was never asked, and the post-answer critic that could
have noticed only ever rewrote wording.

This module now runs that same Router as a bounded loop:

    round 1   knowledge packs + org RAG        (unchanged)
              existing thinness escalation      (unchanged)
    round 2+  a source not yet tried, only when evidence-sufficiency says the
              question is still not answerable, capped hard

The sources, the classifier, and the escalation heuristic are the existing ones.
The loop adds the decision to go back, which is what did not exist.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_HOLD_PACKS = frozenset({"pack.sales", "pack.marketing"})

_QUESTION_HINT = re.compile(
    r"\?|^(?:what|how|why|when|where|who|tell me|explain|describe|compare|best|top|recommend)\b",
    re.I | re.M,
)

_GREETING_HINT = re.compile(
    r"^(?:hi|hello|hey|thanks|thank you|good morning|good afternoon|good evening)\b",
    re.I,
)
_PRIORITIZATION_HINT = re.compile(
    r"\b(priorit(?:ize|isation|ization|y)|who should i (?:focus|prioritize)|focus this week|top prospects?)\b",
    re.I,
)

# Escalation order. Follows the Router's own hierarchy: the org's own corpus and
# curated packs first, then the open web, then the org business graph. Nothing
# here is a new retrieval system — each entry calls the function that already
# owned that source.
SOURCE_KNOWLEDGE_PACK = "knowledge_pack"
SOURCE_ORG_RAG = "org_rag"
SOURCE_INTERNET = "internet"
SOURCE_BUSINESS_GRAPH = "business_graph"

ESCALATION_ORDER = (SOURCE_INTERNET, SOURCE_BUSINESS_GRAPH)

MAX_ADDITIONAL_ROUNDS_CEILING = 3
CONTEXT_BLOCK_OVERHEAD_TOKENS = 32


def _rows_for_round(
    rows: list[dict[str, Any]],
    *,
    round_number: int,
    retrieval_source: str,
) -> list[dict[str, Any]]:
    """Preserve which bounded retrieval round produced each evidence row."""
    tagged: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tagged.append(
            {
                **row,
                "retrieval_round": round_number,
                "retrieval_source": retrieval_source,
            }
        )
    return tagged


def should_augment_unified_turn_with_knowledge(
    message: str,
    *,
    classification: dict[str, Any] | None = None,
) -> bool:
    """True when LIVE should prefetch RAG / knowledge packs before answering."""
    from app.services.conversational_reply_service import re_search_meta

    text = (message or "").strip()
    if len(text) < 8:
        return False
    if _GREETING_HINT.match(text):
        return False
    # Meta/capability: answer from agent config — zero KF / web retrieval / COGS.
    if re_search_meta(text):
        return False
    if isinstance(classification, dict) and classification.get("requires_action"):
        return False
    if _QUESTION_HINT.search(text):
        return True
    if len(text.split()) >= 6:
        return True
    dept = str((classification or {}).get("department") or "").strip().lower()
    return dept not in {"", "all", "general"}


def should_include_signal_priorities(
    message: str,
    *,
    classification: dict[str, Any] | None = None,
) -> bool:
    text = str(message or "").strip()
    if not text:
        return False
    if _PRIORITIZATION_HINT.search(text):
        return True
    return str((classification or {}).get("intent") or "").lower() in {"crm_lookup", "data_analysis"}


async def _run_internet_prefetch(
    *,
    org_id: str,
    query: str,
    client: Any,
    settings: Settings,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    from app.services.adaptive_research_cascade import (
        format_internet_research_section,
        normalize_internet_results,
    )
    from app.services.internet_research_query import prepare_internet_research_query
    from app.services.web_research import search_web

    meta: dict[str, Any] = {}
    governed_query = prepare_internet_research_query(query).query
    internet_payload = await search_web(
        governed_query,
        settings=settings,
        max_results=5,
        org_id=org_id,
        client=client,
    )
    raw_count = len(internet_payload.get("results") or [])
    relevant = normalize_internet_results(internet_payload, query=governed_query)
    internet_section = format_internet_research_section(
        internet_payload, query=governed_query
    )
    meta["internet_raw_hit_count"] = raw_count
    meta["internet_hit_count"] = len(relevant)
    meta["internet_provider"] = internet_payload.get("provider")
    rows = [
        {
            "kind": SOURCE_INTERNET,
            "content": str(row.get("content") or ""),
            "score": row.get("score") or 0.5,
            "source": row.get("source") or row.get("title"),
            "url": row.get("url"),
            # Web results carry no effective date from the provider; saying so
            # is what lets the regulatory bar refuse them as sole evidence.
            "last_updated": None,
        }
        for row in relevant[:5]
    ]
    if not internet_section:
        meta["internet_empty_relevant"] = raw_count > 0
        return "", meta, rows
    return (
        "INTERNET RESEARCH (metered; cite URLs when used):\n" + internet_section.strip(),
        meta,
        rows,
    )


async def _retrieve_knowledge_packs(
    *,
    client: Any,
    query: str,
    pack_ids: list[str],
    dept: str,
    settings: Settings,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric

    meta: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    fabric = await asyncio.to_thread(
        retrieve_knowledge_fabric,
        client,
        query,
        assigned_pack_ids=pack_ids,
        agent_department=dept or None,
        top_k=6,
        settings=settings,
    )
    hits = list(fabric.get("results") or [])
    meta["fabric_hit_count"] = len(hits)
    for hit in hits[:6]:
        # Authority, citation and effective dating are carried through instead of
        # being dropped: the sufficiency bar and the contradiction resolver are
        # only able to work because these fields survive the hand-off.
        rows.append(
            {
                "kind": SOURCE_KNOWLEDGE_PACK,
                "content": hit.get("content") or "",
                "score": hit.get("semantic_score") or 0.7,
                "citation": hit.get("citation"),
                "source": hit.get("citation") or hit.get("source_id"),
                "authority_score": hit.get("authority_score"),
                "freshness_score": hit.get("freshness_score"),
                "effective_at": hit.get("effective_at"),
                "valid_from": hit.get("valid_from"),
                "valid_until": hit.get("valid_until"),
                "superseded_at": hit.get("superseded_at"),
                "superseded_by": hit.get("superseded_by"),
                "jurisdiction": hit.get("jurisdiction"),
            }
        )
    if not hits:
        return "", meta, rows
    lines = []
    for hit in hits[:6]:
        cite = hit.get("citation") or hit.get("source_id") or "knowledge pack"
        lines.append(f"- [{cite}]\n{hit.get('content') or ''}")
    section = (
        "PLATFORM KNOWLEDGE PACK EXCERPTS (authoritative; cite when used):\n"
        + "\n\n".join(lines)
    )
    return section, meta, rows


async def _retrieve_org_rag(
    *,
    org_id: str,
    query: str,
    agent: dict[str, Any] | None,
    settings: Settings,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    from app.services.rag_service import get_rag_service

    meta: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    rag = get_rag_service()
    chunks, rag_metrics = await rag.retrieve_chunks(
        org_id,
        query,
        top_k=4,
        agent_id=str((agent or {}).get("id") or "") or None,
    )
    meta["org_rag_chunk_count"] = len(chunks)
    meta["org_rag_metrics"] = rag_metrics
    for chunk in chunks[:4]:
        metadata = getattr(chunk, "metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}
        rows.append(
            {
                "kind": "knowledge",
                "content": chunk.content or "",
                "score": chunk.score or 0.0,
                "source": chunk.source or "org document",
                "last_updated": metadata.get("last_updated")
                or metadata.get("source_updated_at"),
                "effective_at": metadata.get("effective_at"),
            }
        )
    if not chunks:
        return "", meta, rows
    lines = []
    for chunk in chunks[:4]:
        source = chunk.source or "org document"
        lines.append(f"- [{source}]\n{(chunk.content or '').strip()}")
    section = (
        "ORG PRIVATE KNOWLEDGE (customer RAG; org-scoped only):\n" + "\n\n".join(lines)
    )
    return section, meta, rows


async def _retrieve_business_graph(
    *,
    org_id: str,
    query: str,
    client: Any,
    settings: Settings,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """The org entity graph built from connected systems. One hop, advisory."""
    from app.services.knowledge_graph_service import get_knowledge_graph_service

    meta: dict[str, Any] = {}
    context = await get_knowledge_graph_service().answer_business_question(
        org_id, query, settings=settings, client=client
    )
    if not isinstance(context, dict) or context.get("status") != "ok":
        meta["business_graph_status"] = (
            str((context or {}).get("status") or "unavailable")
            if isinstance(context, dict)
            else "unavailable"
        )
        return "", meta, []
    explanation = context.get("explanation")
    body = ""
    if isinstance(explanation, dict):
        body = str(
            explanation.get("summary") or explanation.get("narrative") or ""
        ).strip()
        if not body:
            body = str(explanation)[:900]
    elif explanation:
        body = str(explanation)[:900]
    if not body:
        meta["business_graph_status"] = "ok_but_empty"
        return "", meta, []
    entity = context.get("identifiedEntity") or {}
    label = (
        f"{entity.get('entityType') or 'entity'}:{entity.get('entityId') or 'unknown'}"
    )
    meta["business_graph_status"] = "ok"
    meta["business_graph_entity"] = label
    rows = [
        {
            "kind": "graph",
            "content": body,
            "score": 0.6,
            "source": f"org business graph ({label})",
        }
    ]
    section = (
        "CONNECTED BUSINESS SYSTEMS — ORG ENTITY GRAPH (one hop; advisory):\n"
        f"- [{label}]\n{body}"
    )
    return section, meta, rows


AUDIT_ACTION_SUFFICIENCY = "evidence.sufficiency.assessed"


def _emit_sufficiency_audit(
    *,
    client: Any,
    org_id: str,
    actor_id: str | None,
    conversation_id: str | None,
    loop_meta: dict[str, Any],
    evidence_meta: dict[str, Any],
) -> None:
    """Give the sufficiency gate a queryable audit action of its own.

    Until now the verdict existed only as nested metadata inside
    ``latency_breakdown.unifiedTurnKnowledge`` on ``unified_turn.*`` events. It
    could be reconstructed, but not asked about: "how often did evidence fall
    short of the regulatory bar last week" required walking every turn payload.
    Every other governed mechanism in this program earned a first-class action.

    Two hard-won rules are enforced here rather than trusted:

    * **A real actor, or a loud skip.** ``write_audit_event`` silently drops the
      insert when actor_id or resource_id is not a UUID -- it logs and returns,
      because both columns are uuid NOT NULL. Three instruments were written
      with ``actor_id=None`` during the dormant-call audit and read zero events
      in production, and two of those zeroes were nearly taken as proof that
      live code was unreachable. So a missing actor is recorded in the metadata
      AND logged by name, never passed through as None.
    * **Fail-closed is announced.** When the assessor could not run, the event
      says so explicitly (``assessorUnavailable``) instead of letting an
      unjudged turn look identical to one that genuinely fell short.

    Never raises: an audit gap must not break a turn.
    """
    if client is None:
        return
    try:
        from app.core.uuid_utils import is_uuid  # type: ignore
    except Exception:  # noqa: BLE001
        def is_uuid(value: Any) -> bool:  # type: ignore[misc]
            import uuid as _uuid

            try:
                _uuid.UUID(str(value))
                return True
            except (ValueError, AttributeError, TypeError):
                return False

    assessments = [a for a in (loop_meta.get("assessments") or []) if isinstance(a, dict)]
    assessors = [str(a.get("assessor")) for a in assessments]

    from app.services.evidence_sufficiency_service import (
        MODEL_ASSESSORS,
        UNAVAILABLE_ASSESSORS,
    )

    payload: dict[str, Any] = {
        "bar": loop_meta.get("bar"),
        "skipped": loop_meta.get("skipped"),
        "additionalRoundsUsed": loop_meta.get("additional_rounds_used"),
        "maxAdditionalRounds": loop_meta.get("max_additional_rounds"),
        "finalSufficient": loop_meta.get("final_sufficient"),
        # The three-way classification, and every stance the loop passed through.
        # `finalSufficient` alone cannot distinguish "wrong evidence, discarded"
        # from "on-topic evidence, still thin", which are the two cases the loop
        # now responds to differently.
        "finalStance": loop_meta.get("final_stance"),
        # True when the stance was reconstructed from a legacy bool rather than
        # genuinely classified. Without it, a defaulted stance reads exactly like
        # a reasoned one and the whole three-way signal becomes unfalsifiable.
        "finalStanceInferred": loop_meta.get("final_stance_inferred"),
        "stances": loop_meta.get("stances"),
        # What the loop actually DID, as opposed to what it concluded.
        "discards": loop_meta.get("discards"),
        "discardedRows": loop_meta.get("discarded_rows"),
        "refined": loop_meta.get("refined"),
        "refinedFrom": loop_meta.get("refined_from"),
        "refinedTo": loop_meta.get("refined_to"),
        "stoppedBecause": loop_meta.get("stopped_because"),
        "finalGaps": loop_meta.get("final_gaps"),
        "sourcesTried": loop_meta.get("sources_tried"),
        "ms": loop_meta.get("ms"),
        # Whether a model genuinely judged the evidence. Compared against the
        # module constants, never a literal.
        "assessorRan": any(a in MODEL_ASSESSORS for a in assessors),
        "assessorUnavailable": any(a in UNAVAILABLE_ASSESSORS for a in assessors),
        # The raw list is kept so `assessorRan` can be cross-checked against an
        # independent signal instead of being believed on its own.
        "assessors": assessors,
        "roundCount": len(assessments),
        "evidenceCounts": {
            "orgRag": evidence_meta.get("org_rag_chunk_count"),
            "fabric": evidence_meta.get("fabric_hit_count"),
            "internet": evidence_meta.get("internet_hit_count"),
            "businessGraph": evidence_meta.get("business_graph_status"),
        },
    }

    if not (actor_id and is_uuid(actor_id)) or not (
        conversation_id and is_uuid(conversation_id)
    ):
        # Loudly, not silently. This is the exact shape that produced three
        # dead instruments and two false "never reached" conclusions.
        logger.warning(
            "sufficiency_audit_skipped org_id=%s reason=non_uuid_actor_or_resource "
            "actor=%r conversation=%r bar=%s",
            org_id,
            actor_id,
            conversation_id,
            loop_meta.get("bar"),
        )
        loop_meta["audit_skipped"] = "non_uuid_actor_or_resource"
        return

    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_ACTION_SUFFICIENCY,
            "conversation",
            conversation_id,
            payload,
        )
        loop_meta["audit_emitted"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("sufficiency_audit_failed org_id=%s error=%s", org_id, exc)
        loop_meta["audit_skipped"] = f"write_failed:{type(exc).__name__}"


def _render_refined_evidence(rows: list[dict[str, Any]]) -> str:
    """Re-render only the excerpts the assessor judged load-bearing.

    The per-source formatters produce one block per source, so refinement cannot
    be done by dropping section strings -- the granularity is wrong. This renders
    from the rows themselves, preserving citation, source and kind so nothing
    that made an excerpt attributable is lost on the way through.
    """
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        label = str(
            row.get("citation") or row.get("source") or row.get("kind") or "source"
        )[:120]
        bits = []
        if row.get("url") or row.get("web_link"):
            bits.append(str(row.get("url") or row.get("web_link"))[:200])
        for date_key in ("effective_at", "valid_from", "last_updated"):
            if row.get(date_key):
                bits.append(f"{date_key}={row.get(date_key)}")
                break
        suffix = f" ({'; '.join(bits)})" if bits else ""
        lines.append(f"[{index}] {label}{suffix}\n{content}")
    if not lines:
        return ""
    return (
        "REFINED EVIDENCE — the excerpts below were judged to carry the answer; "
        "unrelated retrieved material has been removed:\n\n" + "\n\n".join(lines)
    )


def _resolve_max_rounds(settings: Settings) -> int:
    raw = getattr(settings, "evidence_sufficiency_max_rounds", 2)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 2
    return max(0, min(MAX_ADDITIONAL_ROUNDS_CEILING, value))


async def build_unified_turn_knowledge_context(
    *,
    org_id: str,
    query: str,
    client: Any,
    settings: Settings,
    classification: dict[str, Any] | None = None,
    agent: dict[str, Any] | None = None,
    knowledge_assignments: list[dict[str, Any]] | None = None,
    connected_integrations: list[str] | None = None,
    supplemental_context: dict[str, str] | None = None,
    research_scope: str | None = None,
    reasoning_depth: str = "full",
    actor_id: str | None = None,
    conversation_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (prompt_block, meta) for unified-turn user context."""
    meta: dict[str, Any] = {
        "org_rag_chunk_count": 0,
        "fabric_hit_count": 0,
        "internet_hit_count": 0,
        "pack_ids": [],
        "route_reason": "",
        "research_scope": research_scope or "internal_only",
    }
    if not should_augment_unified_turn_with_knowledge(query, classification=classification):
        meta["skipped"] = "not_informational"
        return "", meta

    evidence_sections: list[str] = []
    advisory_sections: list[str] = []
    dept = str(
        (classification or {}).get("department")
        or (agent or {}).get("department")
        or ""
    ).strip()
    if dept.lower() in {"all", "general"}:
        dept = ""

    assigned_pack_ids = [
        str(row.get("source_id") or "")
        for row in (knowledge_assignments or [])
        if isinstance(row, dict)
        and str(row.get("source_type") or "").lower() == "knowledge_pack"
        and str(row.get("source_id") or "").startswith("pack.")
        and row.get("enabled", True)
    ]

    from app.knowledge_fabric.router import classify_knowledge_query

    route = classify_knowledge_query(
        query,
        assigned_pack_ids=assigned_pack_ids or None,
        agent_department=dept or None,
    )
    pack_ids = [p for p in route.pack_ids if p not in _HOLD_PACKS]
    if assigned_pack_ids and not pack_ids:
        pack_ids = [p for p in assigned_pack_ids if p not in _HOLD_PACKS]
    try:
        from app.knowledge_fabric.tool_knowledge import tool_packs_for_connected_vendors

        for pack_id in tool_packs_for_connected_vendors(list(connected_integrations or [])):
            if pack_id not in pack_ids and pack_id not in _HOLD_PACKS:
                pack_ids.append(pack_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("unified_turn tool_knowledge packs skipped error=%s", exc)
    meta["pack_ids"] = pack_ids
    meta["route_reason"] = route.reason

    rag_source_rows: list[dict[str, Any]] = []
    tried: list[str] = []

    # ---- round 1: unchanged single-pass behaviour -------------------------
    if pack_ids:
        tried.append(SOURCE_KNOWLEDGE_PACK)
        try:
            section, pack_meta, rows = await _retrieve_knowledge_packs(
                client=client,
                query=query,
                pack_ids=pack_ids,
                dept=dept,
                settings=settings,
            )
            meta.update(pack_meta)
            rag_source_rows.extend(
                _rows_for_round(
                    rows,
                    round_number=1,
                    retrieval_source=SOURCE_KNOWLEDGE_PACK,
                )
            )
            if section:
                evidence_sections.append(section)
        except Exception as exc:  # noqa: BLE001
            meta["fabric_error"] = str(exc)[:200]

    tried.append(SOURCE_ORG_RAG)
    try:
        section, rag_meta, rows = await _retrieve_org_rag(
            org_id=org_id, query=query, agent=agent, settings=settings
        )
        meta.update(rag_meta)
        rag_source_rows.extend(
            _rows_for_round(
                rows,
                round_number=1,
                retrieval_source=SOURCE_ORG_RAG,
            )
        )
        if section:
            evidence_sections.append(section)
    except Exception as exc:  # noqa: BLE001
        meta["org_rag_error"] = str(exc)[:200]

    from app.services.adaptive_research_cascade import (
        assess_internal_retrieval_thinness,
        should_run_internet_research,
    )

    internal_thin = assess_internal_retrieval_thinness(
        retrieval_effectiveness={
            "source_count": len(rag_source_rows),
            "retrieval_score": None,
        },
        rag_sources=rag_source_rows,
    )
    meta["internal_thin"] = internal_thin

    if client is not None and should_run_internet_research(
        research_scope,
        settings=settings,
        internal_thin=internal_thin,
    ):
        tried.append(SOURCE_INTERNET)
        try:
            internet_section, internet_meta, rows = await _run_internet_prefetch(
                org_id=org_id,
                query=query,
                client=client,
                settings=settings,
            )
            meta.update(internet_meta)
            rag_source_rows.extend(
                _rows_for_round(
                    rows,
                    round_number=1,
                    retrieval_source=SOURCE_INTERNET,
                )
            )
            if internet_section:
                evidence_sections.append(internet_section)
                meta["auto_internet_when_thin"] = internal_thin
        except Exception as exc:  # noqa: BLE001
            meta["internet_error"] = str(exc)[:200]

    # ---- rounds 2+: sufficiency-gated escalation --------------------------
    loop_enabled = bool(getattr(settings, "evidence_sufficiency_loop_enabled", True))
    max_rounds = _resolve_max_rounds(settings)
    from app.services.evidence_sufficiency_service import (
        ASSESSOR_ERROR,
        BAR_CASUAL,
        STANCE_CORRECT,
        assess_evidence_sufficiency,
        substantive_rows,
        sufficiency_bar_for,
    )

    bar = sufficiency_bar_for(
        query=query,
        route_departments=list(route.departments or []),
        route_jurisdictions=list(route.jurisdictions or []),
        reasoning_depth=reasoning_depth,
    )
    loop_meta: dict[str, Any] = {
        "enabled": loop_enabled,
        "bar": bar.name,
        "max_additional_rounds": max_rounds,
        "additional_rounds_used": 0,
        "sources_tried": list(tried),
        "assessments": [],
        # Phase 2 actions, counted so "the loop ran" and "the loop did something"
        # are separable in production data.
        "stances": [],
        "discards": 0,
        "discarded_rows": 0,
        "refined": False,
    }

    if not loop_enabled or bar.name == BAR_CASUAL or max_rounds == 0:
        loop_meta["skipped"] = (
            "flag_disabled"
            if not loop_enabled
            else ("casual_bar" if bar.name == BAR_CASUAL else "max_rounds_zero")
        )
    else:
        routing_tier = str((classification or {}).get("routing_tier") or "multi_step")
        loop_started = time.perf_counter()
        verdict = await assess_evidence_sufficiency(
            query=query,
            rows=rag_source_rows,
            bar=bar,
            settings=settings,
            org_id=org_id,
            routing_tier=routing_tier,
            sources_tried=tried,
        )
        loop_meta["assessments"].append(verdict.to_dict())
        loop_meta["stances"].append(verdict.stance)

        while not verdict.sufficient and loop_meta["additional_rounds_used"] < max_rounds:
            # A broken assessor withholds sufficiency rather than granting it, but
            # more evidence cannot fix an assessor that is not running. Escalating
            # here would spend the whole round budget, and the added latency, on
            # every turn for no possible gain.
            if verdict.assessor == ASSESSOR_ERROR:
                loop_meta["stopped_because"] = "assessor_unavailable"
                break

            next_source = next((s for s in ESCALATION_ORDER if s not in tried), None)
            if next_source is None:
                loop_meta["stopped_because"] = "no_untried_source"
                break

            # INCORRECT means the evidence answers a different question. Carrying
            # it into the next round would let the model generate from material
            # already judged wrong, which is the specific outcome this loop exists
            # to prevent -- and it would also bias the next assessment, since the
            # assessor sees the accumulated set.
            #
            # Both the rows and the rendered sections have to go. Dropping only
            # the rows would leave the discarded text sitting in the prompt while
            # every downstream count claimed it was gone: a fix one layer below
            # the thing that decides what the model actually reads.
            if verdict.should_discard_evidence:
                loop_meta["discards"] += 1
                loop_meta["discarded_rows"] += len(rag_source_rows)
                rag_source_rows = []
                evidence_sections.clear()

            tried.append(next_source)
            loop_meta["additional_rounds_used"] += 1
            try:
                if next_source == SOURCE_INTERNET:
                    if client is None:
                        raise RuntimeError("no client for internet retrieval")
                    section, extra_meta, rows = await _run_internet_prefetch(
                        org_id=org_id, query=query, client=client, settings=settings
                    )
                else:
                    section, extra_meta, rows = await _retrieve_business_graph(
                        org_id=org_id, query=query, client=client, settings=settings
                    )
                meta.update(extra_meta)
                rag_source_rows.extend(
                    _rows_for_round(
                        rows,
                        round_number=1 + loop_meta["additional_rounds_used"],
                        retrieval_source=next_source,
                    )
                )
                if section:
                    evidence_sections.append(section)
            except Exception as exc:  # noqa: BLE001
                meta[f"{next_source}_error"] = str(exc)[:200]

            verdict = await assess_evidence_sufficiency(
                query=query,
                rows=rag_source_rows,
                bar=bar,
                settings=settings,
                org_id=org_id,
                routing_tier=routing_tier,
                sources_tried=tried,
            )
            loop_meta["assessments"].append(verdict.to_dict())
            loop_meta["stances"].append(verdict.stance)

        if not verdict.sufficient and loop_meta["additional_rounds_used"] >= max_rounds:
            loop_meta["stopped_because"] = "max_rounds_reached"

        # CORRECT with a named subset: keep the load-bearing excerpts and drop the
        # rest, so generation is not diluted by material the assessor explicitly
        # did not endorse.
        #
        # Guarded three ways, because an over-eager refinement silently deletes
        # good evidence: only on CORRECT, only when the assessor named a strict
        # and non-empty subset, and never down to nothing.
        if verdict.stance == STANCE_CORRECT and verdict.keep_indices:
            candidates = substantive_rows(rag_source_rows)
            kept = [candidates[i] for i in verdict.keep_indices if 0 <= i < len(candidates)]
            if kept and len(kept) < len(candidates):
                refined_section = _render_refined_evidence(kept)
                if refined_section:
                    rag_source_rows = kept
                    evidence_sections.clear()
                    evidence_sections.append(refined_section)
                    loop_meta["refined"] = True
                    loop_meta["refined_from"] = len(candidates)
                    loop_meta["refined_to"] = len(kept)

        loop_meta["sources_tried"] = list(tried)
        loop_meta["final_stance"] = verdict.stance
        loop_meta["final_stance_inferred"] = verdict.stance_inferred
        loop_meta["final_sufficient"] = verdict.sufficient
        loop_meta["final_reason"] = verdict.reason[:300]
        loop_meta["final_gaps"] = list(verdict.gaps)[:6]
        loop_meta["ms"] = round((time.perf_counter() - loop_started) * 1000)

        if verdict.assessor == ASSESSOR_ERROR:
            # Distinct from a reasoned shortfall: the evidence was never judged at
            # all. Claiming it "does not meet the bar" would invent a finding, so
            # the model is told the check is unavailable and asked to stay within
            # what the excerpts support.
            advisory_sections.append(
                "EVIDENCE SUFFICIENCY UNVERIFIED — the sufficiency check could "
                "not run for this turn, so the evidence has not been judged "
                f"against the {bar.name} standard. Answer only what the excerpts "
                "directly support, attribute each claim to its source, and do not "
                "present the answer as verified."
            )
        elif not verdict.sufficient:
            # The honest outcome when iteration ran out: answer, but say the
            # evidence never reached the bar. Never present this at full
            # confidence just because the loop terminated.
            gap_text = ", ".join(verdict.gaps[:4]) or "evidence did not reach the bar"
            # INCORRECT and AMBIGUOUS need different instructions. On INCORRECT
            # the evidence was discarded, so telling the model to "answer only
            # what the excerpts support" would point it at excerpts that are no
            # longer there -- and inviting it to answer anyway is how a turn ends
            # up generating from nothing while sounding sourced.
            if verdict.should_discard_evidence and not rag_source_rows:
                advisory_sections.append(
                    "NO USABLE EVIDENCE — retrieval was attempted "
                    f"{1 + loop_meta['additional_rounds_used']} time(s) across "
                    f"{len(tried)} source(s). What came back was judged to address "
                    f"a different question and was discarded ({gap_text}). Say "
                    "plainly that you do not have the information to answer this, "
                    "and do not substitute general knowledge for the missing "
                    "evidence."
                )
            else:
                advisory_sections.append(
                    "EVIDENCE SUFFICIENCY WARNING — retrieval was attempted "
                    f"{1 + loop_meta['additional_rounds_used']} time(s) across "
                    f"{len(tried)} source(s) and the evidence still does not meet the "
                    f"{bar.name} standard for this question ({gap_text}). "
                    "Answer only what the excerpts support, state plainly which part "
                    "of the question you cannot substantiate, and do not present the "
                    "answer as fully verified."
                )

        # Emitted only when the loop actually ran. A row per skipped turn would
        # add a write to the conversational fast path -- the one path that must
        # not pay for this machinery -- and would carry no verdict anyway.
        # Threaded because write_audit_event uses the blocking Supabase client.
        await asyncio.to_thread(
            _emit_sufficiency_audit,
            client=client,
            org_id=org_id,
            actor_id=actor_id,
            conversation_id=conversation_id,
            loop_meta=loop_meta,
            evidence_meta=meta,
        )

    # ---- cross-source contradiction check --------------------------------
    contradiction_enabled = bool(
        getattr(settings, "evidence_contradiction_check_enabled", True)
    )
    distinct_kinds = {str(r.get("kind") or "") for r in rag_source_rows}
    if (
        contradiction_enabled
        and bar.name != BAR_CASUAL
        and len(rag_source_rows) >= 2
        and len(distinct_kinds) >= 2
    ):
        from app.services.evidence_contradiction_service import (
            detect_contradictions,
            format_contradiction_section,
        )

        conflict_started = time.perf_counter()
        conflicts = await detect_contradictions(
            query=query,
            rows=rag_source_rows,
            settings=settings,
            org_id=org_id,
            routing_tier=str((classification or {}).get("routing_tier") or "multi_step"),
        )
        conflict_section = format_contradiction_section(conflicts)
        if conflict_section:
            advisory_sections.append(conflict_section)
        meta["evidenceConflicts"] = {
            "count": len(conflicts),
            "resolved": sum(1 for c in conflicts if c.resolution.startswith("resolved")),
            "unresolved": sum(1 for c in conflicts if c.resolution == "unresolved"),
            "details": [c.to_dict() for c in conflicts],
            "ms": round((time.perf_counter() - conflict_started) * 1000),
        }

    meta["evidenceSufficiency"] = loop_meta

    sections = evidence_sections + advisory_sections
    supplemental = supplemental_context or {}
    memory_section = str(supplemental.get("memory_section") or "").strip()
    raw_kernel_knowledge = str(supplemental.get("knowledge_section") or "")
    kernel_fabric_removed = bool(
        re.search(r"<knowledge_fabric>.*?</knowledge_fabric>", raw_kernel_knowledge, re.S | re.I)
    )
    kernel_knowledge_section = re.sub(
        r"<knowledge_fabric>.*?</knowledge_fabric>\s*",
        "",
        raw_kernel_knowledge,
        flags=re.S | re.I,
    ).strip()
    outcome_bias_section = str(
        supplemental.get("outcome_bias_section") or ""
    ).strip()
    if should_include_signal_priorities(query, classification=classification) and client is not None:
        try:
            from app.services.department_signal_scoring_service import (
                get_department_signal_scoring_service,
            )

            scorer = get_department_signal_scoring_service(settings)
            if dept and dept in {"sales", "marketing", "finance", "hr", "msp"}:
                score_payload = await asyncio.to_thread(
                    scorer.score_department,
                    org_id,
                    client=client,
                    department=dept,
                    limit=3,
                )
                rendered = scorer.render_priority_context(score_payload)
                if rendered:
                    advisory_sections.append(rendered)
                meta["signalScoring"] = score_payload
            else:
                scored_all = await asyncio.to_thread(
                    scorer.score_all_departments,
                    org_id,
                    client=client,
                    limit_per_department=2,
                )
                lines: list[str] = ["SIGNAL PRIORITIZATION SNAPSHOT (multi-department):"]
                for row in list(scored_all.get("departments") or [])[:5]:
                    one = scorer.render_priority_context(row)
                    if one:
                        lines.append(one)
                if len(lines) > 1:
                    advisory_sections.append("\n".join(lines))
                meta["signalScoring"] = scored_all
        except Exception as exc:  # noqa: BLE001
            meta["signalScoringError"] = str(exc)[:160]

    sections = evidence_sections + advisory_sections
    if not sections and not any(
        (memory_section, kernel_knowledge_section, outcome_bias_section)
    ):
        meta["skipped"] = "no_hits"
        return "", meta

    active_ranking = bool(getattr(settings, "cross_source_context_engine_enabled", False))
    shadow_ranking = bool(
        getattr(settings, "cross_source_context_engine_shadow_enabled", True)
    )
    if active_ranking or shadow_ranking:
        from app.services.context_prioritization_engine import (
            ContextSource,
            evidence_rows_to_context_sources,
            get_context_prioritization_engine,
            render_context_sources,
        )

        raw_budget = getattr(settings, "cross_source_context_token_budget", 12_000)
        try:
            token_budget = max(512, min(32_000, int(raw_budget)))
        except (TypeError, ValueError):
            token_budget = 12_000
        normalized = evidence_rows_to_context_sources(rag_source_rows, query=query)
        if memory_section:
            normalized.append(
                ContextSource(
                    source_id="kernel:conversation_memory",
                    source_type="conversation_memory",
                    label="Conversation and agent memory",
                    score=0.0,
                    content=memory_section,
                    metadata={"source_identity": "kernel:conversation_memory"},
                )
            )
        if kernel_knowledge_section:
            normalized.append(
                ContextSource(
                    source_id="kernel:org_knowledge",
                    source_type="entity_graph",
                    label="Org knowledge graph and definitions",
                    score=0.0,
                    content=kernel_knowledge_section,
                    metadata={"source_identity": "kernel:org_knowledge"},
                )
            )
        mandatory_sections = list(advisory_sections)
        if active_ranking and outcome_bias_section:
            mandatory_sections.append(outcome_bias_section)
        advisory_tokens = sum(max(1, len(section) // 4) for section in mandatory_sections)
        reserved_tokens = advisory_tokens + CONTEXT_BLOCK_OVERHEAD_TOKENS
        evidence_token_budget = max(0, token_budget - reserved_tokens)
        profile = get_context_prioritization_engine().build_context_profile(
            raw_sources=normalized,
            classification=classification or {},
            token_budget=evidence_token_budget,
            department=dept or None,
        )
        explanation = profile.to_explanation_dict()
        selected_by_kind: dict[str, int] = {}
        tokens_by_kind: dict[str, int] = {}
        for source in profile.ranked_sources:
            selected_by_kind[source.source_type] = (
                selected_by_kind.get(source.source_type, 0) + 1
            )
            tokens_by_kind[source.source_type] = (
                tokens_by_kind.get(source.source_type, 0) + source.token_estimate
            )
        ranked_context = render_context_sources(profile.ranked_sources)
        ranked_sections = ([ranked_context] if ranked_context else []) + mandatory_sections
        meta["contextRanking"] = {
            "mode": "active" if active_ranking else "shadow",
            "candidateCount": explanation["candidateCount"],
            "selectedCount": explanation["selectedCount"],
            "duplicateCount": explanation["duplicateCount"],
            "tokenBudget": token_budget,
            "evidenceTokenBudget": evidence_token_budget,
            "tokensUsed": explanation["tokensUsed"] + reserved_tokens,
            "advisoryTokens": advisory_tokens,
            "blockOverheadTokens": CONTEXT_BLOCK_OVERHEAD_TOKENS,
            "selectedByKind": selected_by_kind,
            "tokensByKind": tokens_by_kind,
            "excludedSources": explanation["excludedSources"][:20],
            "selectedSourceIds": [
                source.source_id for source in profile.ranked_sources[:20]
            ],
            "selectedSources": explanation["sourcesUsed"][:20],
            "managedSupplementalSections": bool(
                active_ranking
                and any((memory_section, kernel_knowledge_section, outcome_bias_section))
            ),
            "kernelFabricExcludedFromRanking": kernel_fabric_removed,
            "legacyPromptChars": len("\n\n".join(sections)),
            "rankedPromptChars": len("\n\n".join(ranked_sections)),
        }
        if active_ranking:
            sections = ranked_sections

    if not sections:
        meta["skipped"] = "no_retrieval_hits"
        return "", meta

    heading = (
        "RANKED CONTEXT FOR THIS TURN (use when relevant; do not invent facts "
        "outside these excerpts and connected tools):\n\n"
        if active_ranking
        else "RETRIEVED KNOWLEDGE FOR THIS TURN (use when relevant; do not invent facts "
        "outside these excerpts and connected tools):\n\n"
    )
    block = (
        heading + "\n\n".join(sections)
    )
    return block, meta
