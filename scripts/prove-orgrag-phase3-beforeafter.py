#!/usr/bin/env python3
"""Phase 3 before/after: contextual enrichment, and the keyword arm's reach.

HONEST SCOPE, stated first because the prompt asked for "real, honest before/
after retrieval-quality numbers on the same real test set" and that specific
thing is not obtainable today:

  docs/delivery/orgrag-keyword-reach.json records ONE chunk platform-wide. There
  is no real test set. A retrieval-quality comparison over a single chunk is
  arithmetic on n=1, and reporting it as a quality measurement would be exactly
  the kind of confident-but-empty number this program has spent weeks removing.

So this measures two different things by two different methods, and labels which
is which:

  PART A -- contextual enrichment, on a SYNTHETIC corpus, with REAL embeddings.
    The corpus is constructed; the embeddings, the cosine ranking and the
    resulting numbers are real. This is a genuine measurement of a real
    mechanism on invented data. It is not evidence about Gravitre's production
    corpus, because Gravitre does not have one yet.

  PART B -- the keyword arm's reach, DETERMINISTIC, no model at all.
    This one needs no corpus and no embeddings, because the defect was
    structural: the old fetch was query-blind and capped, so a matching chunk
    beyond the cap could not be retrieved at any temperature. Demonstrated by
    construction rather than by sampling.

Read-only with respect to the database: writes nothing, reads nothing. Part A
calls the OpenAI embeddings API.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "orgrag-phase3-beforeafter.json"


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
            print(f"  WARNING: {path.name} unreadable in every attempted encoding")
            continue
        for key, value in (loaded or {}).items():
            if value and not os.environ.get(key):
                os.environ[key] = value


# --------------------------------------------------------------------------
# The synthetic corpus.
#
# Every document is written so that its later chunks lose their referents when
# cut out -- which is not a trick to make enrichment look good, it is the single
# failure mode Anthropic's Contextual Retrieval addresses, and it is what real
# documents do. "Revenue grew 3%" genuinely does not say whose revenue.
# --------------------------------------------------------------------------

DOCS: list[dict[str, Any]] = [
    {
        "title": "ACME Corp Q2 2026 Quarterly Report",
        "synopsis": "ACME Corp's Q2 2026 quarterly financial report, covering revenue, margin and headcount.",
        "chunks": [
            "ACME Corp filed this quarterly report for the three months ending June 2026.",
            "Revenue grew 3% over the prior quarter, driven mainly by renewals.",
            "Gross margin was flat at 71%, with no change in the cost of delivery.",
            "Headcount was unchanged at 240, and no reductions are planned.",
        ],
    },
    {
        "title": "Northwind Ltd FY2025 Annual Report",
        "synopsis": "Northwind Ltd's FY2025 annual report, covering revenue, margin and headcount.",
        "chunks": [
            "Northwind Ltd presents its annual report for the financial year ending December 2025.",
            "Revenue declined 8% year over year following the loss of two large accounts.",
            "Gross margin improved to 64% after the logistics contract was renegotiated.",
            "Headcount fell to 1,150 following a restructuring completed in November.",
        ],
    },
    {
        "title": "Ontario Personal Health Information Breach Notification Guidance",
        "synopsis": "Guidance on breach notification obligations for personal health information in Ontario, Canada.",
        "chunks": [
            "This guidance concerns personal health information custodians in Ontario, Canada.",
            "Notification must be given at the first reasonable opportunity after the custodian becomes aware.",
            "The Commissioner must also be notified where the circumstances meet the prescribed thresholds.",
            "Records of every notification decision must be retained for audit.",
        ],
    },
    {
        "title": "California Consumer Data Breach Notification Guidance",
        "synopsis": "Guidance on consumer data breach notification obligations under California law.",
        "chunks": [
            "This guidance concerns businesses handling consumer personal information in California.",
            "Notification must be made in the most expedient time possible and without unreasonable delay.",
            "The Attorney General must be notified where a single breach affects more than 500 residents.",
            "Substitute notice is permitted where the cost of direct notice would be excessive.",
        ],
    },
]

# Each query names a document that only the enrichment can identify, because the
# gold chunk itself does not contain the distinguishing terms.
QUERIES: list[dict[str, Any]] = [
    {
        "query": "How much did ACME Corp's revenue change in Q2 2026?",
        "gold": (0, 1),
    },
    {
        "query": "What happened to Northwind Ltd's revenue in FY2025?",
        "gold": (1, 1),
    },
    {
        "query": "What was ACME Corp's headcount in Q2 2026?",
        "gold": (0, 3),
    },
    {
        "query": "What was Northwind Ltd's gross margin in FY2025?",
        "gold": (1, 2),
    },
    {
        "query": "When must an Ontario health information custodian notify a breach?",
        "gold": (2, 1),
    },
    {
        "query": "What is the threshold for notifying the California Attorney General?",
        "gold": (3, 2),
    },
    {
        "query": "How long must Ontario notification decisions be retained?",
        "gold": (2, 3),
    },
    {
        "query": "When is substitute notice allowed in California?",
        "gold": (3, 3),
    },
]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def part_a() -> dict[str, Any]:
    """Contextual enrichment, synthetic corpus, real embeddings."""
    from app.config import get_settings
    from app.rag.contextual_enrichment import build_chunk_context, text_for_embedding
    from app.rag.embedding import get_embedding

    settings = get_settings()
    if not (settings.openai_api_key or "").startswith("sk-"):
        return {"status": "NOT MEASURED", "reason": "no usable OPENAI_API_KEY"}

    flat: list[dict[str, Any]] = []
    for d_idx, doc in enumerate(DOCS):
        for c_idx, chunk in enumerate(doc["chunks"]):
            context = build_chunk_context(
                chunk_index=c_idx,
                chunks=doc["chunks"],
                title=doc["title"],
                synopsis=doc["synopsis"],
            )
            flat.append(
                {
                    "doc": d_idx,
                    "idx": c_idx,
                    "content": chunk,
                    "enriched": text_for_embedding(content=chunk, context=context),
                }
            )

    print(f"  embedding {len(flat)} chunks twice (bare + enriched)...")
    for row in flat:
        row["vec_bare"] = get_embedding(row["content"], settings)
        row["vec_rich"] = get_embedding(row["enriched"], settings)

    print(f"  embedding {len(QUERIES)} queries...")
    results = []
    hits_bare = {1: 0, 3: 0}
    hits_rich = {1: 0, 3: 0}
    mrr_bare = 0.0
    mrr_rich = 0.0

    for spec in QUERIES:
        qvec = get_embedding(spec["query"], settings)
        gold = tuple(spec["gold"])

        def _rank(field: str) -> int:
            scored = sorted(
                flat, key=lambda r: _cosine(qvec, r[field]), reverse=True
            )
            for pos, row in enumerate(scored, start=1):
                if (row["doc"], row["idx"]) == gold:
                    return pos
            return len(scored) + 1

        r_bare = _rank("vec_bare")
        r_rich = _rank("vec_rich")
        mrr_bare += 1.0 / r_bare
        mrr_rich += 1.0 / r_rich
        for k in (1, 3):
            if r_bare <= k:
                hits_bare[k] += 1
            if r_rich <= k:
                hits_rich[k] += 1
        results.append(
            {"query": spec["query"], "rank_bare": r_bare, "rank_enriched": r_rich}
        )
        print(f"    rank {r_bare:>3} -> {r_rich:>3}   {spec['query'][:62]}")

    n = len(QUERIES)
    failures_bare = n - hits_bare[1]
    failures_rich = n - hits_rich[1]
    reduction = (
        round(100.0 * (failures_bare - failures_rich) / failures_bare, 1)
        if failures_bare
        else None
    )
    return {
        "status": "MEASURED (synthetic corpus, real embeddings)",
        "corpus_chunks": len(flat),
        "queries": n,
        "recall_at_1": {"bare": hits_bare[1], "enriched": hits_rich[1]},
        "recall_at_3": {"bare": hits_bare[3], "enriched": hits_rich[3]},
        "mrr": {
            "bare": round(mrr_bare / n, 4),
            "enriched": round(mrr_rich / n, 4),
        },
        "top1_failure_reduction_pct": reduction,
        "per_query": results,
        "caveat": (
            "Synthetic corpus. The embeddings, ranking and numbers are real; the "
            "documents are invented, because the production corpus is one chunk. "
            "Not evidence about real customer retrieval quality."
        ),
    }


def part_b() -> dict[str, Any]:
    """The keyword arm's reach. Deterministic; no embeddings, no model."""
    from types import SimpleNamespace

    from app.rag import retrieval as rr

    CORPUS = 2000
    CAP = 500
    GOLD_AT = 1500

    rows = [
        {
            "id": f"c{i}",
            "content": (
                "The statutory breach notification deadline is seventy-two hours."
                if i == GOLD_AT
                else f"unrelated filler passage number {i}"
            ),
            "document_id": "doc-1",
            "source_id": "s1",
        }
        for i in range(CORPUS)
    ]

    class _Builder:
        """Stands in for postgrest, honouring limit and (optionally) text_search."""

        def __init__(self, data, name):
            self._data = data
            self._name = name
            self._limit = None
            self._terms: list[str] | None = None

        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def in_(self, *a, **k):
            return self

        def limit(self, n, *a, **k):
            self._limit = n
            return self

        def text_search(self, column, query, options):
            self._terms = [t.strip('"').lower() for t in query.split(" OR ")]
            return self

        def execute(self):
            if self._name == "rag_documents":
                return SimpleNamespace(data=[{"id": "doc-1", "title": "Guidance"}])
            data = self._data
            if self._terms is not None:
                data = [
                    r
                    for r in data
                    if any(t in r["content"].lower() for t in self._terms)
                ]
            if self._limit is not None:
                data = data[: self._limit]
            return SimpleNamespace(data=list(data))

    client = SimpleNamespace(table=lambda n: _Builder(rows, n))
    settings = SimpleNamespace(
        supabase_url="https://x.supabase.co", supabase_service_role_key="k"
    )

    saved_create = rr.create_client
    saved_scope = rr._resolve_source_ids_for_scope
    rr.create_client = lambda *a, **k: client
    rr._resolve_source_ids_for_scope = lambda *a, **k: None
    try:
        query = "statutory breach notification deadline"

        # AFTER: the shipped code path.
        after_rows, after_reach = rr.fetch_bm25_corpus(
            settings, "org-1", query_text=query, limit=CAP
        )
        after_found = any(r["id"] == f"c{GOLD_AT}" for r in after_rows)

        # BEFORE: the same fetch with the query withheld, which is exactly what
        # the old signature could do -- it had no query parameter to pass.
        before_rows, before_reach = rr.fetch_bm25_corpus(
            settings, "org-1", query_text="", limit=CAP
        )
        before_found = any(r["id"] == f"c{GOLD_AT}" for r in before_rows)
    finally:
        rr.create_client = saved_create
        rr._resolve_source_ids_for_scope = saved_scope

    print(f"    corpus {CORPUS} chunks, cap {CAP}, matching chunk at index {GOLD_AT}")
    print(
        f"    BEFORE (query-blind): {len(before_rows):>4} fetched, "
        f"reach={before_reach}, matching chunk reachable={before_found}"
    )
    print(
        f"    AFTER  (keyword arm): {len(after_rows):>4} fetched, "
        f"reach={after_reach}, matching chunk reachable={after_found}"
    )

    return {
        "status": "MEASURED (deterministic, no model)",
        "corpus_chunks": CORPUS,
        "cap": CAP,
        "matching_chunk_index": GOLD_AT,
        "before": {
            "fetched": len(before_rows),
            "reach": before_reach,
            "gold_reachable": before_found,
        },
        "after": {
            "fetched": len(after_rows),
            "reach": after_reach,
            "gold_reachable": after_found,
        },
        "note": (
            "BEFORE is the old behaviour reproduced by withholding the query, "
            "which is what the previous signature forced -- it had no query "
            "parameter. The matching chunk sits beyond the cap, so no amount of "
            "BM25 tuning could retrieve it: the row never left Postgres."
        ),
        "reachability": (
            "Not a live defect today. orgrag-keyword-reach.json: 1 chunk "
            "platform-wide, 0 scopes over the 500 cap. This is a latent trap "
            "that fires silently on the first real corpus."
        ),
    }


def main() -> int:
    _load_env()
    report: dict[str, Any] = {}

    print("PART B — keyword arm reach (deterministic)")
    report["part_b_keyword_reach"] = part_b()
    print()

    print("PART A — contextual enrichment (synthetic corpus, real embeddings)")
    try:
        report["part_a_contextual_enrichment"] = part_a()
    except Exception as exc:  # noqa: BLE001
        print(f"  NOT MEASURED: {type(exc).__name__}: {exc}")
        report["part_a_contextual_enrichment"] = {
            "status": "NOT MEASURED",
            "error": f"{type(exc).__name__}: {exc}"[:400],
        }

    a = report["part_a_contextual_enrichment"]
    if a.get("status", "").startswith("MEASURED"):
        print()
        print(
            f"  recall@1  {a['recall_at_1']['bare']}/{a['queries']} -> "
            f"{a['recall_at_1']['enriched']}/{a['queries']}"
        )
        print(
            f"  recall@3  {a['recall_at_3']['bare']}/{a['queries']} -> "
            f"{a['recall_at_3']['enriched']}/{a['queries']}"
        )
        print(f"  MRR       {a['mrr']['bare']} -> {a['mrr']['enriched']}")
        print(f"  top-1 failure reduction: {a['top1_failure_reduction_pct']}%")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print()
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
