"""Live retrieve smoke for Sales/Marketing packs after ingest."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _load_env() -> None:
    for path in (ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

from supabase import create_client

from app.config import get_settings
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric
from app.knowledge_fabric.router import classify_knowledge_query


def main() -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    queries = [
        (
            "What does the FTC CAN-SPAM rule require for email marketing?",
            ["pack.marketing", "pack.legal"],
        ),
        (
            "How should a small business do market research and competitive analysis?",
            ["pack.marketing", "pack.sales"],
        ),
        (
            "What dimensions does the Census Bureau API cover for establishments and population?",
            ["pack.sales", "pack.marketing"],
        ),
    ]
    out = {"ran_at": datetime.now(timezone.utc).isoformat(), "queries": []}
    for q, packs in queries:
        route = classify_knowledge_query(q, assigned_pack_ids=packs)
        result = retrieve_knowledge_fabric(
            client,
            q,
            assigned_pack_ids=packs,
            top_k=5,
            settings=settings,
        )
        rows = result.get("results") or []
        out["queries"].append(
            {
                "query": q,
                "route": route.to_dict(),
                "hit_count": len(rows),
                "citations": [
                    {
                        "citation": r.get("citation"),
                        "authority_score": r.get("authority_score"),
                        "score": r.get("score"),
                        "source_id": (r.get("metadata") or {}).get("external_id"),
                    }
                    for r in rows[:5]
                ],
            }
        )
    path = ROOT / "docs/delivery/sales-marketing-retrieve-live.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:4000])
    print("wrote", path)


if __name__ == "__main__":
    main()
