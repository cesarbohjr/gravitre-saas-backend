#!/usr/bin/env python3
"""Is the org RAG keyword arm's 500-row ceiling reachable today?

Phase 3 was scoped on the premise that org RAG "has no persisted keyword index
(no tsvector+GIN), unlike the Knowledge Fabric which already has one" and needs
bringing "up to the same real, hybrid standard". The first half is true. The
second is not: org RAG is already hybrid, and in one respect better than the
Fabric -- it runs BM25, which produces a real relevance ORDER, where the
Fabric's FTS arm cannot order by ts_rank at all.

What org RAG actually has is a different defect, in `fetch_bm25_corpus`
(backend/app/rag/retrieval.py L104-117):

    client.table("rag_chunks").select(...).eq("org_id", ...).limit(500)

No query terms, no ORDER BY. So the keyword arm ranks an ARBITRARY 500-chunk
slice of the org's corpus. Under 500 chunks it is exact and looks perfect. Over
500 it silently drops to sampling, and nothing anywhere reports which regime a
given org is in -- Class C, the sixth-plus instance in this program.

Lesson 4 says measure real reachability with real production data before
investing a fix-and-prove cycle. So: how many orgs are actually over the line
today, and how close is the largest corpus to it.

Read-only. Counts rows. No writes.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "orgrag-keyword-reach.json"
PAGE = 1000
BM25_CEILING = 500


def _load_env() -> None:
    """Load .env with an explicit encoding ladder.

    The silent-swallow version of this cost real time once already: the operator
    env file is cp1252, `dotenv_values` raised UnicodeDecodeError, the except
    hid it, and the probe reported a missing API key.
    """
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
            print(f"  WARNING: {path.name} unreadable in every attempted encoding")
            continue
        for key, value in (loaded or {}).items():
            if value and not os.environ.get(key):
                os.environ[key] = value


def _fetch_all(client: Any, table: str, columns: str) -> tuple[list[dict], str | None]:
    """Page through a table. Returns (rows, error) -- never a sentinel row.

    Returning an error marker inside the row list produced a false "1
    organization" reading on the memory probe. An unavailable table has to be
    reportable as UNAVAILABLE, not silently counted.
    """
    rows: list[dict] = []
    start = 0
    while True:
        try:
            resp = (
                client.table(table)
                .select(columns)
                .range(start, start + PAGE - 1)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            return rows, f"{type(exc).__name__}: {exc}"[:300]
        batch = list(resp.data or [])
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows, None
        start += PAGE


def main() -> int:
    _load_env()
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("MISSING SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
        return 2
    client = create_client(url, key)

    report: dict[str, Any] = {"ceiling": BM25_CEILING}

    chunks, err = _fetch_all(client, "rag_chunks", "id,org_id,environment,document_id")
    if err:
        report["rag_chunks"] = "UNAVAILABLE"
        report["rag_chunks_error"] = err
        print(f"rag_chunks: UNAVAILABLE ({err})")
    else:
        per_org: Counter[str] = Counter()
        per_org_env: Counter[tuple[str, str]] = Counter()
        for row in chunks:
            org = str(row.get("org_id") or "?")
            env = str(row.get("environment") or "default")
            per_org[org] += 1
            per_org_env[(org, env)] += 1

        over = {o: n for o, n in per_org.items() if n > BM25_CEILING}
        # The scope actually used at query time is (org, environment), not org,
        # so that is the number that decides whether truncation bites.
        over_scoped = {f"{o}/{e}": n for (o, e), n in per_org_env.items() if n > BM25_CEILING}

        report["total_chunks"] = len(chunks)
        report["orgs_with_any_chunks"] = len(per_org)
        report["largest_org_corpus"] = max(per_org.values()) if per_org else 0
        report["orgs_over_ceiling"] = len(over)
        report["scopes_over_ceiling"] = over_scoped
        report["distribution"] = dict(
            sorted(per_org.items(), key=lambda kv: -kv[1])[:20]
        )

        print(f"total rag_chunks rows      : {len(chunks)}")
        print(f"orgs with any chunks       : {len(per_org)}")
        print(f"largest single-org corpus  : {report['largest_org_corpus']}")
        print(f"orgs over the {BM25_CEILING}-row ceiling: {len(over)}")
        print()
        if over_scoped:
            print("SCOPES CURRENTLY TRUNCATED (keyword arm sees an arbitrary slice):")
            for scope, n in sorted(over_scoped.items(), key=lambda kv: -kv[1]):
                print(f"  {scope}: {n} chunks")
        else:
            print(
                f"NOT REACHABLE TODAY: no (org, environment) scope exceeds "
                f"{BM25_CEILING} chunks, so the ceiling is a latent trap rather "
                "than a live defect. It fires silently the first time a customer "
                "uploads a real corpus."
            )

    docs, derr = _fetch_all(client, "rag_documents", "id,org_id,is_active")
    if derr:
        report["rag_documents"] = "UNAVAILABLE"
        report["rag_documents_error"] = derr
    else:
        report["total_documents"] = len(docs)
        report["active_documents"] = sum(1 for d in docs if d.get("is_active"))
        print()
        print(f"rag_documents rows         : {len(docs)}")
        print(f"  active                   : {report['active_documents']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print()
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
