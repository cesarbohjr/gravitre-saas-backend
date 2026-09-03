#!/usr/bin/env python3
"""Mutation proof for the Phase 3 guards.

Run because of a specific precedent. When the Knowledge Fabric's keyword arm was
fixed, the first mutation run showed that the ONE defect which had actually
shipped -- `text_search(..., config="english")` raising TypeError into a bare
except -- left the whole suite green, because every test checked behaviour
through a mock and none checked the call site. The guards covered everything
except the thing that broke.

The org RAG arm has the same shape, so the same check is warranted before
claiming it is held.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
RETRIEVAL = BACKEND / "app" / "rag" / "retrieval.py"
INGEST = BACKEND / "app" / "rag" / "ingest.py"
ENRICH = BACKEND / "app" / "rag" / "contextual_enrichment.py"
SERVICE = BACKEND / "app" / "services" / "rag_service.py"
TESTS = "tests/rag tests/services/test_rag_service.py"

sys.stdout.reconfigure(encoding="utf-8")

MUTATIONS: list[tuple[str, Path, str, str]] = [
    (
        "reinstate the config= kwarg that killed the Fabric arm",
        RETRIEVAL,
        'response = _base().text_search("content_tsv", fts_query, FTS_OPTIONS).execute()',
        'response = _base().text_search("content_tsv", fts_query, config="english").execute()',
    ),
    (
        "drop the keyword filter entirely (back to a query-blind slice)",
        RETRIEVAL,
        "    if fts_query:\n        try:",
        "    if False:\n        try:",
    ),
    (
        "report truncation as an exact scan",
        RETRIEVAL,
        "        reach = REACH_TRUNCATED if len(rows) >= capped else (",
        "        reach = REACH_EXACT if len(rows) >= capped else (",
    ),
    (
        "collapse no-keyword-match into empty corpus",
        RETRIEVAL,
        "        if reach == REACH_FTS:\n            return [], REACH_FTS_NO_MATCH",
        "        pass",
    ),
    (
        "log the FTS failure at info with the cause hidden in extra=",
        RETRIEVAL,
        '            logger.warning(\n                "rag_bm25_fts_unavailable org_id=%s falling back to unfiltered slice: %s",\n                org_id,\n                exc,\n            )',
        '            logger.info("rag_bm25_fts_unavailable", extra={"error": str(exc)})',
    ),
    (
        "stop threading the query from the call site",
        SERVICE,
        "            query_text=query,",
        "",
    ),
    (
        "drop keyword_reach from the metrics",
        SERVICE,
        '            "keyword_reach": keyword_reach,',
        "",
    ),
    (
        "embed the bare chunk while still storing a context prefix",
        INGEST,
        "        embed_text = (\n            text_for_embedding(content=content, context=contexts[idx])\n            if enrich\n            else content\n        )",
        "        embed_text = content",
    ),
    (
        "stop persisting the context prefix",
        INGEST,
        '        if enrich:\n            row["context_prefix"] = contexts[i]',
        "        pass",
    ),
    (
        "bill the bare chunk instead of what was embedded",
        INGEST,
        "    total_tokens = sum(_estimate_tokens(c) for c in embedded_texts)",
        "    total_tokens = sum(_estimate_tokens(c) for c in chunks)",
    ),
    (
        "enrich by default",
        BACKEND / "app" / "config.py",
        "    rag_contextual_enrichment_enabled: bool = False",
        "    rag_contextual_enrichment_enabled: bool = True",
    ),
    (
        "let the context displace the chunk it describes",
        ENRICH,
        '    return f"{context}\\n\\n{content}"',
        '    return f"{context}\\n\\n{content}"[:200]',
    ),
    (
        "report a model failure as merely disabled",
        ENRICH,
        "        return \"\", ENRICH_FAILED",
        "        return \"\", ENRICH_DISABLED",
    ),
    (
        "drop the neighbouring-passage context",
        ENRICH,
        "    if chunk_index > 0:",
        "    if False:",
    ),
    (
        "round partial enrichment up to fully enriched",
        ENRICH,
        '        "fully_enriched": bool(states) and counts.get(ENRICH_OK, 0) == len(states),',
        '        "fully_enriched": bool(states),',
    ),
]


def run_tests() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS.split(), "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    files = {RETRIEVAL, INGEST, ENRICH, SERVICE, BACKEND / "app" / "config.py"}
    originals = {p: p.read_text(encoding="utf-8") for p in files}
    backups = {}
    for p in files:
        b = p.with_suffix(".py.mutbak")
        shutil.copy2(p, b)
        backups[p] = b

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_tests():
        print("FAIL — suite is red before mutating")
        for p, b in backups.items():
            shutil.move(b, p)
        return 2
    print("green")
    print()

    caught = 0
    escaped: list[str] = []
    try:
        for label, target, find, replace in MUTATIONS:
            src = originals[target]
            if find not in src:
                print(f"  [SKIP] {label} — anchor not found, mutation is stale")
                escaped.append(f"{label} (stale anchor)")
                continue
            target.write_text(src.replace(find, replace, 1), encoding="utf-8")
            red = not run_tests()
            target.write_text(src, encoding="utf-8")
            print(f"  [{'caught' if red else 'ESCAPED'}] {label}")
            if red:
                caught += 1
            else:
                escaped.append(label)
    finally:
        for p, b in backups.items():
            shutil.move(b, p)

    print()
    print(f"  {caught}/{len(MUTATIONS)} mutations caught")
    for item in escaped:
        print(f"  ESCAPED: {item}")
    print(f"  restored; suite green again: {run_tests()}")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
