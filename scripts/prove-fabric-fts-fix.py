#!/usr/bin/env python3
"""Before/after proof that the Knowledge Fabric keyword half is live again.

BEFORE is not a reconstruction: it re-issues the exact call the shipped code made
(`config=` kwarg, `.limit()` after `.text_search()`) and shows it raising, which
is what the swallowed `except` turned into silence. AFTER issues the corrected
call through the real `retrieve()` entry point and reads `retrieval_health`.

Read-only. No writes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "fabric-fts-fix.json"

QUERIES = [
    "What are the statutory breach notification deadlines under Ontario privacy law?",
    "data retention requirements",
    "employee privacy obligations",
]


def _load_env() -> None:
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        for k, v in (loaded or {}).items():
            if v and k not in os.environ:
                os.environ[k] = v


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.knowledge_fabric.retrieval import (
        FTS_OPTIONS,
        build_fts_query,
        retrieve_knowledge_fabric,
    )
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    report: dict[str, Any] = {"queries": []}

    for q in QUERIES:
        entry: dict[str, Any] = {"query": q}

        # BEFORE: the literal shipped call.
        try:
            (
                client.table("knowledge_chunks")
                .select("id,content")
                .text_search("content_tsv", q, config="english")
                .limit(10)
                .execute()
            )
            entry["before"] = "UNEXPECTED_OK"
        except Exception as exc:  # noqa: BLE001
            entry["before"] = f"{type(exc).__name__}: {str(exc)[:120]}"

        # AFTER: the corrected call, same table, same intent.
        try:
            res = (
                client.table("knowledge_chunks")
                .select("id,content")
                .limit(10)
                .text_search("content_tsv", build_fts_query(q), FTS_OPTIONS)
                .execute()
            )
            entry["after_rows"] = len(res.data or [])
        except Exception as exc:  # noqa: BLE001
            entry["after_rows"] = f"{type(exc).__name__}: {str(exc)[:120]}"

        # END TO END through the real entry point, so this proves the shipped
        # path and not just a hand-built query that happens to work.
        try:
            got = retrieve_knowledge_fabric(
                client, q, settings=settings, top_k=8, assigned_pack_ids=["pack.legal"]
            )
            results = got.get("results") or []
            # `build_provenance_envelope` does `envelope.update(extra)`, so the
            # extras are FLATTENED into the envelope, not nested under "extra".
            # Reading p["extra"] returned {} on every row and reported a confident
            # zero -- a broken instrument, caught only because it disagreed with
            # `retrieval_health.co_matched` computed by different code.
            extras = list(got.get("provenance") or [])
            entry["retrieve_health"] = got.get("retrieval_health")
            entry["retrieve_results"] = len(results)
            # The number that actually matters: chunks in the FINAL top-k that the
            # keyword arm had a hand in. `fts=ok` with this at 0 means the arm runs
            # and does not count.
            entry["final_touched_by_fts"] = sum(
                1 for e in extras if "fts" in (e.get("matched_by") or [])
            )
            entry["final_co_matched"] = sum(1 for e in extras if e.get("match") == "hybrid")
            entry["final_fts_only"] = sum(1 for e in extras if e.get("match") == "fts")
        except Exception as exc:  # noqa: BLE001
            entry["retrieve_health"] = f"{type(exc).__name__}: {str(exc)[:160]}"

        # Cross-check the two independently-computed records against each other.
        health = entry.get("retrieve_health")
        if isinstance(health, dict):
            entry["health_agrees_with_provenance"] = (
                entry["final_co_matched"] <= health.get("co_matched", 0)
                and entry["final_fts_only"] <= health.get("fts_only", 0)
            )

        report["queries"].append(entry)

    print(json.dumps(report, indent=2, default=str))
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    ok = all(
        isinstance(e.get("after_rows"), int) and "Error" in str(e.get("before"))
        for e in report["queries"]
    )
    any_hits = any(isinstance(e.get("after_rows"), int) and e["after_rows"] > 0 for e in report["queries"])
    print()
    print(f"  every before-call raised, every after-call succeeded : {ok}")
    print(f"  at least one query now returns keyword hits          : {any_hits}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
