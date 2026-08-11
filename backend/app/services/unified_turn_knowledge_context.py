"""Inject org RAG + platform knowledge fabric + auto internet into unified-turn LIVE."""
from __future__ import annotations

import asyncio
import re
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


def should_augment_unified_turn_with_knowledge(
    message: str,
    *,
    classification: dict[str, Any] | None = None,
) -> bool:
    """True when LIVE should prefetch RAG / knowledge packs before answering."""
    text = (message or "").strip()
    if len(text) < 8:
        return False
    if _GREETING_HINT.match(text):
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
) -> tuple[str, dict[str, Any]]:
    from app.services.adaptive_research_cascade import format_internet_research_section
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
    internet_section = format_internet_research_section(internet_payload)
    if not internet_section:
        meta["internet_hit_count"] = 0
        return "", meta
    meta["internet_hit_count"] = len(internet_payload.get("results") or [])
    meta["internet_provider"] = internet_payload.get("provider")
    return (
        "INTERNET RESEARCH (metered; cite URLs when used):\n" + internet_section.strip(),
        meta,
    )


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
    from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric

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

    if pack_ids:
        try:
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
                rag_source_rows.append(
                    {
                        "kind": "knowledge_pack",
                        "content": hit.get("content") or "",
                        "score": hit.get("semantic_score") or 0.7,
                    }
                )
            if hits:
                lines = []
                for hit in hits[:6]:
                    cite = hit.get("citation") or hit.get("source_id") or "knowledge pack"
                    lines.append(f"- [{cite}]\n{hit.get('content') or ''}")
                sections.append(
                    "PLATFORM KNOWLEDGE PACK EXCERPTS (authoritative; cite when used):\n"
                    + "\n\n".join(lines)
                )
        except Exception as exc:  # noqa: BLE001
            meta["fabric_error"] = str(exc)[:200]

    try:
        from app.services.rag_service import get_rag_service

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
            rag_source_rows.append(
                {
                    "kind": "knowledge",
                    "content": chunk.content or "",
                    "score": chunk.score or 0.0,
                }
            )
        if chunks:
            lines = []
            for chunk in chunks[:4]:
                source = chunk.source or "org document"
                lines.append(f"- [{source}]\n{(chunk.content or '').strip()}")
            sections.append(
                "ORG PRIVATE KNOWLEDGE (customer RAG; org-scoped only):\n" + "\n\n".join(lines)
            )
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
        try:
            internet_section, internet_meta = await _run_internet_prefetch(
                org_id=org_id,
                query=query,
                client=client,
                settings=settings,
            )
            meta.update(internet_meta)
            if internet_section:
                sections.append(internet_section)
                meta["auto_internet_when_thin"] = internal_thin
        except Exception as exc:  # noqa: BLE001
            meta["internet_error"] = str(exc)[:200]

    if not sections:
        meta["skipped"] = "no_hits"
        return "", meta

    block = (
        "RETRIEVED KNOWLEDGE FOR THIS TURN (use when relevant; do not invent facts "
        "outside these excerpts and connected tools):\n\n"
        + "\n\n".join(sections)
    )
    return block, meta
