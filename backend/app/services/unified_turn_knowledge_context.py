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

_HOLD_PACKS = frozenset({"pack.sales", "pack.marketing"})

_QUESTION_HINT = re.compile(
    r"\?|^(?:what|how|why|when|where|who|tell me|explain|describe|compare|best|top|recommend)\b",
    re.I | re.M,
)

_GREETING_HINT = re.compile(
    r"^(?:hi|hello|hey|thanks|thank you|good morning|good afternoon|good evening)\b",
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
    rag = get_rag_service(settings)
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
    research_scope: str | None = None,
    reasoning_depth: str = "full",
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

    sections: list[str] = []
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
            rag_source_rows.extend(rows)
            if section:
                sections.append(section)
        except Exception as exc:  # noqa: BLE001
            meta["fabric_error"] = str(exc)[:200]

    tried.append(SOURCE_ORG_RAG)
    try:
        section, rag_meta, rows = await _retrieve_org_rag(
            org_id=org_id, query=query, agent=agent, settings=settings
        )
        meta.update(rag_meta)
        rag_source_rows.extend(rows)
        if section:
            sections.append(section)
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
            rag_source_rows.extend(rows)
            if internet_section:
                sections.append(internet_section)
                meta["auto_internet_when_thin"] = internal_thin
        except Exception as exc:  # noqa: BLE001
            meta["internet_error"] = str(exc)[:200]

    # ---- rounds 2+: sufficiency-gated escalation --------------------------
    loop_enabled = bool(getattr(settings, "evidence_sufficiency_loop_enabled", True))
    max_rounds = _resolve_max_rounds(settings)
    from app.services.evidence_sufficiency_service import (
        BAR_CASUAL,
        assess_evidence_sufficiency,
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

        while not verdict.sufficient and loop_meta["additional_rounds_used"] < max_rounds:
            # A broken assessor withholds sufficiency rather than granting it, but
            # more evidence cannot fix an assessor that is not running. Escalating
            # here would spend the whole round budget, and the added latency, on
            # every turn for no possible gain.
            if verdict.assessor == "assessor_error":
                loop_meta["stopped_because"] = "assessor_unavailable"
                break

            next_source = next((s for s in ESCALATION_ORDER if s not in tried), None)
            if next_source is None:
                loop_meta["stopped_because"] = "no_untried_source"
                break

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
                rag_source_rows.extend(rows)
                if section:
                    sections.append(section)
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

        if not verdict.sufficient and loop_meta["additional_rounds_used"] >= max_rounds:
            loop_meta["stopped_because"] = "max_rounds_reached"

        loop_meta["sources_tried"] = list(tried)
        loop_meta["final_sufficient"] = verdict.sufficient
        loop_meta["final_reason"] = verdict.reason[:300]
        loop_meta["final_gaps"] = list(verdict.gaps)[:6]
        loop_meta["ms"] = round((time.perf_counter() - loop_started) * 1000)

        if verdict.assessor == "assessor_error":
            # Distinct from a reasoned shortfall: the evidence was never judged at
            # all. Claiming it "does not meet the bar" would invent a finding, so
            # the model is told the check is unavailable and asked to stay within
            # what the excerpts support.
            sections.append(
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
            sections.append(
                "EVIDENCE SUFFICIENCY WARNING — retrieval was attempted "
                f"{1 + loop_meta['additional_rounds_used']} time(s) across "
                f"{len(tried)} source(s) and the evidence still does not meet the "
                f"{bar.name} standard for this question ({gap_text}). "
                "Answer only what the excerpts support, state plainly which part "
                "of the question you cannot substantiate, and do not present the "
                "answer as fully verified."
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
            sections.append(conflict_section)
        meta["evidenceConflicts"] = {
            "count": len(conflicts),
            "resolved": sum(1 for c in conflicts if c.resolution.startswith("resolved")),
            "unresolved": sum(1 for c in conflicts if c.resolution == "unresolved"),
            "details": [c.to_dict() for c in conflicts],
            "ms": round((time.perf_counter() - conflict_started) * 1000),
        }

    meta["evidenceSufficiency"] = loop_meta

    if not sections:
        meta["skipped"] = "no_hits"
        return "", meta

    block = (
        "RETRIEVED KNOWLEDGE FOR THIS TURN (use when relevant; do not invent facts "
        "outside these excerpts and connected tools):\n\n"
        + "\n\n".join(sections)
    )
    return block, meta
