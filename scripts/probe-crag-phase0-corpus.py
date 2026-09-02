#!/usr/bin/env python3
"""Is org RAG returning zero because the corpus is empty, or because it is broken?

Phase 0b found `org_rag_chunk_count == 0` on 256 of 256 turns where the
sufficiency loop ran. A constant, not a distribution. Two very different causes:

  (a) these orgs have no documents. Then the gate is correct, retrieval is
      correct, and the saturated verdict is an artifact of WHICH orgs generated
      the traffic -- 1034 of 1063 events were probe traffic, and probe orgs are
      created empty. Nothing to fix in retrieval.
  (b) orgs DO have indexed chunks and retrieval still returns none. Then org RAG
      is silently returning nothing on the unified-turn path, which would be a
      real, live defect sitting underneath everything Phase 1/2 would build.

The dormant-call audit already burned this exact way once: 140 of 142
`outcome_error` events turned out to be probe traffic, and treating the
aggregate as customer impact would have been wrong. So this segments by org and
then, for any org that actually has a corpus, checks whether retrieval reaches
it.

Read-only: counts rows, runs retrieval for real against orgs that have content.
No writes.
"""
from __future__ import annotations

import asyncio
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

OUT = REPO / "docs" / "delivery" / "crag-phase0-corpus.json"
LOOKBACK_DAYS = 30
PAGE = 500


def _load_env() -> None:
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded is None:
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


def _count(client: Any, table: str, org_id: str | None = None) -> Any:
    try:
        q = client.table(table).select("id", count="exact")
        if org_id:
            q = q.eq("org_id", org_id)
        res = q.limit(1).execute()
        return getattr(res, "count", None)
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}: {str(exc)[:90]}"


async def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()

    # 1. which orgs generated the loop traffic, and their per-org rag counts
    per_org: dict[str, Counter] = {}
    for action in ("unified_turn.live.completed", "unified_turn.live.fallthrough"):
        offset = 0
        while True:
            batch = (
                client.table("audit_events")
                .select("org_id,metadata,created_at")
                .eq("action", action)
                .gte("created_at", since)
                .order("created_at", desc=True)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            data = batch.data or []
            for row in data:
                meta = _meta(row.get("metadata"))
                suff = _find(meta, "evidenceSufficiency")
                if not isinstance(suff, dict) or suff.get("skipped"):
                    continue
                know = _find(meta, "unifiedTurnKnowledge") or {}
                org = str(row.get("org_id"))
                per_org.setdefault(org, Counter())
                per_org[org]["loop_turns"] += 1
                per_org[org][f"rag={know.get('org_rag_chunk_count')}"] += 1
            if len(data) < PAGE:
                break
            offset += PAGE

    # 2. discover the real table names for the rag corpus
    candidate_tables = [
        "rag_documents",
        "rag_chunks",
        "document_chunks",
        "documents",
        "knowledge_documents",
        "knowledge_chunks",
        "org_documents",
    ]
    table_totals = {t: _count(client, t) for t in candidate_tables}
    live_tables = [
        t for t, c in table_totals.items() if isinstance(c, int)
    ]

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "rag_table_totals_all_orgs": table_totals,
        "orgs": {},
    }

    # 3. per org: name, is-probe, corpus counts, and a real retrieval attempt
    for org, counts in sorted(per_org.items(), key=lambda kv: -kv[1]["loop_turns"]):
        entry: dict[str, Any] = {
            "loop_turns": counts["loop_turns"],
            "rag_count_distribution": {
                k: v for k, v in counts.items() if k.startswith("rag=")
            },
        }
        try:
            row = (
                client.table("organizations")
                .select("name,created_at")
                .eq("id", org)
                .limit(1)
                .execute()
                .data
            )
            entry["org_name"] = (row or [{}])[0].get("name")
            entry["org_created_at"] = (row or [{}])[0].get("created_at")
        except Exception as exc:  # noqa: BLE001
            entry["org_name"] = f"ERR {type(exc).__name__}"

        entry["corpus"] = {t: _count(client, t, org) for t in live_tables}
        report["orgs"][org] = entry

    # 4. for any org with a real corpus, does retrieval actually return rows?
    #    This is the part that separates "empty" from "broken".
    report["retrieval_probe"] = {}
    for org, entry in report["orgs"].items():
        corpus = entry.get("corpus") or {}
        has_content = any(isinstance(v, int) and v > 0 for v in corpus.values())
        if not has_content:
            report["retrieval_probe"][org] = {"skipped": "org_has_no_corpus"}
            continue
        try:
            from app.services.rag_service import get_rag_service

            svc = get_rag_service(settings)
            got = await svc.retrieve_hybrid_rows(
                org_id=org,
                query="what are our policies",
                top_k=8,
            )
            report["retrieval_probe"][org] = {
                "rows_returned": len(got or []),
                "sample_kinds": [
                    (r.get("kind") if isinstance(r, dict) else type(r).__name__)
                    for r in (got or [])[:3]
                ],
            }
        except Exception as exc:  # noqa: BLE001
            report["retrieval_probe"][org] = {
                "error": f"{type(exc).__name__}: {str(exc)[:200]}"
            }

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("=" * 70)
    print("PHASE 0c - is the org corpus empty, or is retrieval broken?")
    print("=" * 70)
    print("rag table totals (ALL orgs):")
    for t, c in table_totals.items():
        print(f"  {t:24s} {c}")
    print()
    for org, entry in report["orgs"].items():
        print("-" * 70)
        print(f"org {org}")
        print(f"  name            : {entry.get('org_name')}")
        print(f"  loop turns      : {entry['loop_turns']}")
        print(f"  rag counts seen : {entry['rag_count_distribution']}")
        print(f"  corpus rows     : {entry.get('corpus')}")
        print(f"  retrieval probe : {report['retrieval_probe'].get(org)}")
    print("-" * 70)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
