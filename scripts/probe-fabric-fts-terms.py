#!/usr/bin/env python3
"""Is the keyword arm useful once it runs, or just no longer raising?

`websearch_to_tsquery` ANDs every term, so a full natural-language question only
matches a chunk containing all of them. Removing the exception without checking
this would report the keyword half "restored" while it still contributes zero
rows -- the one-layer-too-low mistake, Class A.

Read-only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

STOP = {
    "what", "are", "the", "is", "of", "under", "and", "for", "to", "in", "on",
    "a", "an", "how", "do", "does", "with", "by", "our", "we", "i", "my",
    "requirements", "current",
}

QUERIES = [
    "What are the statutory breach notification deadlines under Ontario privacy law?",
    "data retention requirements",
    "employee privacy obligations",
    "cybersecurity incident response",
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


def _terms(q: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", q.lower())
    return [w for w in words if w not in STOP][:8]


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())

    total = client.table("knowledge_chunks").select("id", count="exact").limit(1).execute()
    out: dict[str, Any] = {"corpus_chunks": total.count, "queries": []}

    def run(q: str) -> Any:
        try:
            res = (
                client.table("knowledge_chunks")
                .select("id")
                .limit(20)
                .text_search("content_tsv", q, {"type": "web_search", "config": "english"})
                .execute()
            )
            return len(res.data or [])
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {str(exc)[:100]}"

    for q in QUERIES:
        terms = _terms(q)
        out["queries"].append(
            {
                "query": q,
                "terms": terms,
                "whole_sentence_AND": run(q),
                "terms_AND": run(" ".join(terms)) if terms else None,
                "terms_OR": run(" OR ".join(terms)) if terms else None,
            }
        )

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
