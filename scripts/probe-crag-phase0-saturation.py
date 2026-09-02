#!/usr/bin/env python3
"""Why does the sufficiency loop return final_sufficient=False on 99.4% of turns?

Phase 0 measured the loop as genuinely reachable and genuinely running (157
sufficiency blocks on `unified_turn.live.completed` over 30 days, assessor=llm
284 times, rounds-vs-sources cross-check 156/156 consistent). But its verdict is
effectively constant: insufficient on 156 of 157.

A gate whose answer never varies carries no information, however correct each
individual call is. Before layering a three-way CRAG classification on top, the
cause has to be established, because the two candidate causes point at opposite
work:

  (a) the BAR is miscalibrated -- evidence is fine, the gate is too strict.
      Then Phase 1 (better classification) is the fix.
  (b) RETRIEVAL IS STARVING -- the gate is right and the evidence really is
      thin. Then Phase 3 (contextual chunks / hybrid / rerank) is the fix, and
      building a loop that iterates harder on empty evidence would just spend
      more latency reaching the same answer.

This separates them by reading, per turn, the actual retrieval counts that sit
next to the verdict (`org_rag_chunk_count`, `fabric_hit_count`,
`internet_hit_count`, `business_graph_status`) alongside `final_gaps` and the
assessor's own stated reasons.

Read-only. No model calls, no writes.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "crag-phase0-saturation.json"
LOOKBACK_DAYS = 30
PAGE = 500


def _load_env() -> None:
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        for key, value in loaded.items():
            if value and key not in os.environ:
                os.environ[key] = value


def _find(node: Any, target: str, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if isinstance(node, dict):
        if target in node:
            return node[target]
        for v in node.values():
            got = _find(v, target, depth + 1)
            if got is not None:
                return got
    elif isinstance(node, list):
        for item in node[:20]:
            got = _find(item, target, depth + 1)
            if got is not None:
                return got
    return None


def _meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()

    rows: list[dict[str, Any]] = []
    for action in ("unified_turn.live.completed", "unified_turn.live.fallthrough"):
        offset = 0
        while True:
            batch = (
                client.table("audit_events")
                .select("id,org_id,action,created_at,metadata")
                .eq("action", action)
                .gte("created_at", since)
                .order("created_at", desc=True)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            data = batch.data or []
            rows.extend(data)
            if len(data) < PAGE:
                break
            offset += PAGE

    gaps = Counter()
    reasons = Counter()
    bar_by_verdict = Counter()
    zero_evidence = 0
    some_evidence = 0
    retrieval = {
        "org_rag_chunk_count": Counter(),
        "fabric_hit_count": Counter(),
        "internet_hit_count": Counter(),
        "business_graph_status": Counter(),
    }
    # the decisive number: of the insufficient turns, how many had literally
    # nothing retrieved from the org's own corpus
    insufficient_with_zero_rag = 0
    insufficient_total = 0
    examples: list[dict[str, Any]] = []
    total_rag = 0
    n_rag = 0

    for row in rows:
        meta = _meta(row.get("metadata"))
        suff = _find(meta, "evidenceSufficiency")
        if not isinstance(suff, dict) or suff.get("skipped"):
            continue
        know = _find(meta, "unifiedTurnKnowledge")
        know = know if isinstance(know, dict) else {}

        rag_n = know.get("org_rag_chunk_count")
        fab_n = know.get("fabric_hit_count")
        web_n = know.get("internet_hit_count")
        graph_s = know.get("business_graph_status")
        retrieval["org_rag_chunk_count"][str(rag_n)] += 1
        retrieval["fabric_hit_count"][str(fab_n)] += 1
        retrieval["internet_hit_count"][str(web_n)] += 1
        retrieval["business_graph_status"][str(graph_s)] += 1

        try:
            rag_i = int(rag_n or 0)
            total_rag += rag_i
            n_rag += 1
        except (TypeError, ValueError):
            rag_i = 0

        try:
            tot = int(rag_n or 0) + int(fab_n or 0) + int(web_n or 0)
        except (TypeError, ValueError):
            tot = 0
        if tot == 0:
            zero_evidence += 1
        else:
            some_evidence += 1

        final = suff.get("final_sufficient")
        bar_by_verdict[f"{suff.get('bar')}/{final}"] += 1
        if final is False:
            insufficient_total += 1
            if rag_i == 0:
                insufficient_with_zero_rag += 1
            for g in suff.get("final_gaps") or []:
                gaps[str(g)] += 1
            r = str(suff.get("final_reason") or "")[:200]
            if r:
                reasons[r] += 1
            if len(examples) < 6:
                examples.append(
                    {
                        "created_at": row.get("created_at"),
                        "bar": suff.get("bar"),
                        "final_gaps": suff.get("final_gaps"),
                        "final_reason": suff.get("final_reason"),
                        "sources_tried": suff.get("sources_tried"),
                        "stopped_because": suff.get("stopped_because"),
                        "org_rag_chunk_count": rag_n,
                        "fabric_hit_count": fab_n,
                        "internet_hit_count": web_n,
                        "business_graph_status": graph_s,
                    }
                )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "turns_with_loop_run": insufficient_total + bar_by_verdict.total() - insufficient_total,
        "insufficient_total": insufficient_total,
        "insufficient_with_zero_org_rag": insufficient_with_zero_rag,
        "mean_org_rag_chunks": round(total_rag / n_rag, 2) if n_rag else None,
        "turns_with_zero_total_evidence": zero_evidence,
        "turns_with_some_evidence": some_evidence,
        "final_gaps": dict(gaps.most_common()),
        "final_reasons_top": dict(reasons.most_common(10)),
        "bar_by_verdict": dict(bar_by_verdict.most_common()),
        "retrieval_distributions": {k: dict(v.most_common(12)) for k, v in retrieval.items()},
        "examples": examples,
    }
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("=" * 66)
    print("PHASE 0b - why is the sufficiency verdict saturated?")
    print("=" * 66)
    print(f"turns where the loop ran        : {bar_by_verdict.total()}")
    print(f"  verdict insufficient          : {insufficient_total}")
    print(f"  ... of which 0 org RAG chunks : {insufficient_with_zero_rag}")
    print(f"mean org_rag_chunk_count        : {report['mean_org_rag_chunks']}")
    print(f"turns with ZERO total evidence  : {zero_evidence}")
    print(f"turns with some evidence        : {some_evidence}")
    print()
    print("final_gaps:")
    for k, v in report["final_gaps"].items():
        print(f"  {k:34s} {v}")
    print()
    print("bar / verdict:")
    for k, v in report["bar_by_verdict"].items():
        print(f"  {k:34s} {v}")
    print()
    print("retrieval distributions:")
    for k, v in report["retrieval_distributions"].items():
        print(f"  {k:26s} {v}")
    print()
    print("assessor's own stated reasons (top):")
    for k, v in list(report["final_reasons_top"].items())[:6]:
        print(f"  [{v}x] {k[:150]}")
    print()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
