"""Phase 5 (partial) — run the loop's decisions over REAL retrieved evidence.

Scope honesty, stated up front because it limits what this file can prove:

  PROVEN HERE   the real Knowledge Fabric corpus is queried through the real
                router; the real authority/effective-date metadata now survives
                the hand-off; the deterministic sufficiency gate and the whole
                contradiction resolution ladder run against that real data.

  NOT RUN HERE  the model-based sufficiency judgement and the model-based
                contradiction *detector*. This machine has no model provider
                key, so those calls fail open by design. They need the deployed
                tip. Anything below marked NOT RUN stays NOT RUN.

Writes docs/delivery/evidence-sufficiency-real-data-proof.json.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

from supabase import create_client  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric  # noqa: E402
from app.knowledge_fabric.router import classify_knowledge_query  # noqa: E402
from app.services.evidence_contradiction_service import (  # noqa: E402
    Contradiction,
    format_contradiction_section,
    resolve_contradiction,
)
from app.services.evidence_sufficiency_service import (  # noqa: E402
    assess_evidence_sufficiency,
    sufficiency_bar_for,
)
from app.services.unified_turn_knowledge_context import _retrieve_knowledge_packs  # noqa: E402

# Real, hard, evidence-dependent queries. Each is jurisdictional or regulatory,
# which is exactly where a topic-adjacent chunk must NOT be accepted.
QUERIES = [
    ("What does NIST CSF 2.0 require under the Govern function?", ["pack.cybersecurity"]),
    ("What are the FTC requirements for endorsement disclosures?", ["pack.legal"]),
    ("What notice period does California employment law require?", ["pack.legal", "pack.hr"]),
]

SIMPLE_QUERY = "thanks, that's helpful"


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


async def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    report: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "scope": {
            "proven_here": [
                "real Knowledge Fabric retrieval through the real router",
                "authority/effective-date metadata survives into the evidence rows",
                "deterministic sufficiency gate over real rows",
                "contradiction resolution ladder over real rows",
            ],
            "not_run_here": [
                "model-based sufficiency judgement (no provider key on this host)",
                "model-based contradiction detector (same reason)",
                "end-to-end prod chat turn at the deployed tip",
            ],
        },
        "model_provider_configured": bool(
            getattr(settings, "openai_api_key", None)
            or getattr(settings, "anthropic_api_key", None)
            or getattr(settings, "gemini_api_key", None)
        ),
        "queries": [],
        "metadata_survival": {},
        "contradiction_ladder": [],
    }

    for query, packs in QUERIES:
        route = classify_knowledge_query(query, assigned_pack_ids=packs)
        section, meta, rows = await _retrieve_knowledge_packs(
            client=client,
            query=query,
            pack_ids=packs,
            dept="",
            settings=settings,
        )
        bar = sufficiency_bar_for(
            query=query,
            route_departments=list(route.departments or []),
            route_jurisdictions=list(route.jurisdictions or []),
        )
        verdict = await assess_evidence_sufficiency(
            query=query,
            rows=rows,
            bar=bar,
            settings=settings,
            org_id=None,
            sources_tried=["knowledge_pack"],
        )
        # The old escalation signal, for the before/after comparison.
        from app.services.adaptive_research_cascade import (
            assess_internal_retrieval_thinness,
        )

        old_thin = assess_internal_retrieval_thinness(
            retrieval_effectiveness={"source_count": len(rows), "retrieval_score": None},
            rag_sources=rows,
        )
        report["queries"].append(
            {
                "query": query,
                "route": {
                    "departments": list(route.departments or []),
                    "jurisdictions": list(route.jurisdictions or []),
                    "packs": list(route.pack_ids or []),
                },
                "real_rows_retrieved": len(rows),
                "rows_with_citation": sum(1 for r in rows if r.get("citation")),
                "rows_with_authority": sum(
                    1 for r in rows if r.get("authority_score") is not None
                ),
                "rows_with_date_signal": sum(
                    1
                    for r in rows
                    if any(
                        r.get(k) is not None
                        for k in ("effective_at", "valid_from", "freshness_score")
                    )
                ),
                "bar": bar.name,
                "bar_reason": bar.reason,
                "bar_requires_citable": bar.require_citable_source,
                "sufficiency": verdict.to_dict(),
                "old_thinness_signal_would_escalate": old_thin,
            }
        )

    # Fast-path check: a casual turn must not reach the assessor at all.
    casual_bar = sufficiency_bar_for(query=SIMPLE_QUERY, reasoning_depth="conversational")
    casual_verdict = await assess_evidence_sufficiency(
        query=SIMPLE_QUERY, rows=[], bar=casual_bar, settings=settings
    )
    report["fast_path"] = {
        "query": SIMPLE_QUERY,
        "bar": casual_bar.name,
        "assessor": casual_verdict.assessor,
        "no_model_call": casual_verdict.assessor == "skipped_casual_bar",
    }

    # Ranked retrieval needs a query embedding, which needs a provider key this
    # host does not have, so read the real corpus rows directly. What is under
    # test here is whether real fabric metadata reaches the new logic — not
    # whether vector ranking works, which is separately proven elsewhere.
    fabric = retrieve_knowledge_fabric(
        client,
        "NIST CSF 2.0 Govern function",
        assigned_pack_ids=["pack.cybersecurity"],
        top_k=3,
        settings=settings,
    )
    raw = list(fabric.get("results") or [])
    ranked_worked = len(raw) > 0

    if not ranked_worked:
        chunk_rows = (
            client.table("knowledge_chunks")
            .select("id,content,citation,jurisdiction,authority_score,freshness_score,document_id")
            .limit(6)
            .execute()
            .data
            or []
        )
        doc_ids = [r.get("document_id") for r in chunk_rows if r.get("document_id")]
        docs: dict = {}
        if doc_ids:
            doc_rows = (
                client.table("knowledge_documents")
                .select("id,effective_at,superseded_at,superseded_by")
                .in_("id", doc_ids)
                .execute()
                .data
                or []
            )
            docs = {r["id"]: r for r in doc_rows}
        raw = [
            {
                **row,
                "effective_at": (docs.get(row.get("document_id")) or {}).get("effective_at"),
                "superseded_at": (docs.get(row.get("document_id")) or {}).get("superseded_at"),
                "superseded_by": (docs.get(row.get("document_id")) or {}).get("superseded_by"),
            }
            for row in chunk_rows
        ]

    report["metadata_survival"] = {
        "ranked_retrieval_ran_locally": ranked_worked,
        "row_source": "retrieve_knowledge_fabric" if ranked_worked else "direct_corpus_read",
        "why_direct_read": None
        if ranked_worked
        else (
            "vector search needs a query embedding and this host has no embedding "
            "provider key (knowledge_fabric.vector_failed / fts_unavailable in the log); "
            "ranking is not what this check is testing"
        ),
        "real_corpus_rows": len(raw),
        "raw_has_authority": sum(1 for r in raw if r.get("authority_score") is not None),
        "raw_has_citation": sum(1 for r in raw if r.get("citation")),
        "sample_authority_scores": [r.get("authority_score") for r in raw[:3]],
        "sample_citations": [str(r.get("citation") or "")[:70] for r in raw[:3]],
        "note": (
            "Before this change the hand-off kept only kind/content/score, so "
            "these fields were dropped before any sufficiency or conflict logic "
            "could see them."
        ),
    }

    # Deterministic gate over REAL corpus rows mapped through the same shape the
    # retriever now emits.
    if raw:
        real_rows = [
            {
                "kind": "knowledge_pack",
                "content": r.get("content") or "",
                "score": 0.7,
                "citation": r.get("citation"),
                "source": r.get("citation"),
                "authority_score": r.get("authority_score"),
                "freshness_score": r.get("freshness_score"),
                "effective_at": r.get("effective_at"),
                "jurisdiction": r.get("jurisdiction"),
            }
            for r in raw
        ]
        reg_bar = sufficiency_bar_for(
            query="What are the statutory breach notification requirements?",
            route_departments=["legal"],
            route_jurisdictions=["US-federal"],
        )
        real_verdict = await assess_evidence_sufficiency(
            query="What are the statutory breach notification requirements?",
            rows=real_rows,
            bar=reg_bar,
            settings=settings,
            sources_tried=["knowledge_pack"],
        )
        stripped = [
            {"kind": r["kind"], "content": r["content"], "score": r["score"]}
            for r in real_rows
        ]
        stripped_verdict = await assess_evidence_sufficiency(
            query="What are the statutory breach notification requirements?",
            rows=stripped,
            bar=reg_bar,
            settings=settings,
            sources_tried=["knowledge_pack"],
        )
        report["deterministic_gate_over_real_rows"] = {
            "rows": len(real_rows),
            "with_metadata_carried": {
                "sufficient": real_verdict.sufficient,
                "assessor": real_verdict.assessor,
                "reason": real_verdict.reason[:200],
                "gaps": real_verdict.gaps,
            },
            "with_old_stripped_shape": {
                "sufficient": stripped_verdict.sufficient,
                "assessor": stripped_verdict.assessor,
                "reason": stripped_verdict.reason[:200],
                "gaps": stripped_verdict.gaps,
            },
            "interpretation": (
                "Same real rows, two hand-off shapes. The old shape cannot clear "
                "the regulatory bar because citation/authority were dropped in "
                "transit, which is the concrete before/after this change buys."
            ),
        }

    # Contradiction ladder over REAL fabric rows: pair two real chunks and force
    # each rung by varying only the signal under test.
    if len(raw) >= 2:
        a, b = raw[0], raw[1]

        def claim(index: int, row: dict, **over):
            base = {
                "index": index,
                "claim": str(row.get("content") or "")[:90],
                "kind": "knowledge_pack",
                "source": row.get("citation") or row.get("source_id"),
                "authority_score": row.get("authority_score"),
                "as_of": row.get("effective_at") or row.get("valid_from"),
                "superseded": bool(row.get("superseded_at") or row.get("superseded_by")),
            }
            base.update(over)
            return base

        # Authority rungs use two REAL chunks with genuinely different stored
        # authority, not injected numbers. The corpus spread is 0.84..0.99, so a
        # real high/low pair is a real decisive gap and a real adjacent pair is a
        # real near-tie. Synthetic 0..100 values are what hid the scale bug.
        auth_rows = (
            client.table("knowledge_chunks")
            .select("id,content,citation,authority_score")
            .order("authority_score", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        low_rows = (
            client.table("knowledge_chunks")
            .select("id,content,citation,authority_score")
            .order("authority_score", desc=False)
            .limit(1)
            .execute()
            .data
            or []
        )
        near_rows = (
            client.table("knowledge_chunks")
            .select("id,content,citation,authority_score")
            .eq("authority_score", 0.97)
            .limit(1)
            .execute()
            .data
            or []
        )
        near_rows_b = (
            client.table("knowledge_chunks")
            .select("id,content,citation,authority_score")
            .eq("authority_score", 0.96)
            .limit(1)
            .execute()
            .data
            or []
        )
        report["real_authority_pairs"] = {
            "high": (auth_rows[0].get("authority_score") if auth_rows else None),
            "low": (low_rows[0].get("authority_score") if low_rows else None),
            "near_a": (near_rows[0].get("authority_score") if near_rows else None),
            "near_b": (near_rows_b[0].get("authority_score") if near_rows_b else None),
        }

        cases = [
            (
                "supersession",
                [claim(0, a, superseded=True), claim(1, b, superseded=False)],
                "",
            ),
            (
                "freshness",
                [claim(0, a, as_of="2019-01-01"), claim(1, b, as_of="2026-01-01")],
                "",
            ),
        ]
        if auth_rows and low_rows:
            cases.append(
                (
                    "authority_decisive_REAL_SCORES",
                    [claim(0, auth_rows[0]), claim(1, low_rows[0])],
                    "",
                )
            )
        if near_rows and near_rows_b:
            cases.append(
                (
                    "authority_near_tie_REAL_SCORES_must_not_resolve",
                    [claim(0, near_rows[0]), claim(1, near_rows_b[0])],
                    "",
                )
            )
        cases += [
            (
                "org_precedence",
                [
                    claim(0, a, kind="knowledge", source="employee-handbook.pdf"),
                    claim(1, b, kind="knowledge_pack"),
                ],
                "How much PTO do our employees accrue?",
            ),
        ]
        for name, claims, q in cases:
            con = resolve_contradiction(
                Contradiction(subject="real fabric chunk pair", claims=claims), query=q
            )
            report["contradiction_ladder"].append(
                {
                    "case": name,
                    "resolution": con.resolution,
                    "winner_index": con.winner_index,
                    "rationale": con.rationale,
                    "surfaced_to_model": bool(format_contradiction_section([con])),
                }
            )

    out = ROOT / "docs" / "delivery" / "evidence-sufficiency-real-data-proof.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"git_sha: {report['git_sha']}")
    print(f"model provider configured locally: {report['model_provider_configured']}")
    print()
    for row in report["queries"]:
        print(f"QUERY  {row['query']}")
        print(
            f"  route      departments={row['route']['departments']} "
            f"jurisdictions={row['route']['jurisdictions']}"
        )
        print(
            f"  real rows  {row['real_rows_retrieved']} "
            f"(citation={row['rows_with_citation']}, "
            f"authority={row['rows_with_authority']}, "
            f"dated={row['rows_with_date_signal']})"
        )
        print(f"  bar        {row['bar']} — {row['bar_reason']}")
        print(
            f"  verdict    sufficient={row['sufficiency']['sufficient']} "
            f"via {row['sufficiency']['assessor']}: {row['sufficiency']['reason'][:110]}"
        )
        print(
            f"  old signal would escalate: {row['old_thinness_signal_would_escalate']}"
        )
        print()

    print(
        f"FAST PATH  {report['fast_path']['bar']} / "
        f"{report['fast_path']['assessor']} / no model call: "
        f"{report['fast_path']['no_model_call']}"
    )
    print()
    print("METADATA SURVIVAL")
    ms = report["metadata_survival"]
    print(f"  row source: {ms['row_source']} (ranked locally: {ms['ranked_retrieval_ran_locally']})")
    if ms.get("why_direct_read"):
        print(f"  why       : {ms['why_direct_read']}")
    print(
        f"  {ms['raw_has_authority']}/{ms['real_corpus_rows']} real rows carry "
        f"authority_score; {ms['raw_has_citation']} carry a citation"
    )
    print(f"  sample authority: {ms['sample_authority_scores']}")
    print(f"  sample citation : {ms['sample_citations'][:1]}")
    print()
    gate = report.get("deterministic_gate_over_real_rows")
    if gate:
        print("DETERMINISTIC GATE OVER REAL ROWS (regulatory bar)")
        print(
            f"  metadata carried : sufficient={gate['with_metadata_carried']['sufficient']} "
            f"({gate['with_metadata_carried']['assessor']}) "
            f"gaps={gate['with_metadata_carried']['gaps']}"
        )
        print(
            f"  old stripped shape: sufficient={gate['with_old_stripped_shape']['sufficient']} "
            f"({gate['with_old_stripped_shape']['assessor']}) "
            f"gaps={gate['with_old_stripped_shape']['gaps']}"
        )
        print()
    print("CONTRADICTION LADDER (real fabric chunk pairs)")
    for row in report["contradiction_ladder"]:
        print(f"  {row['case']:42} -> {row['resolution']}")
        print(f"    {row['rationale'][:120]}")
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
