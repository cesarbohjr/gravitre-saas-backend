"""Re-ingest CISA curated summaries + live US/CA jurisdiction reverify."""
from __future__ import annotations

import asyncio
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
from app.knowledge_fabric.ingest import ingest_sources
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric
from app.knowledge_fabric.router import classify_knowledge_query


async def main() -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    cisa = await ingest_sources(
        client, ["cyber.cisa.advisories"], settings=settings, embed=True, limit=3
    )
    us_q = "What does the U.S. Constitution say about equal protection?"
    ca_q = "What does PIPEDA require under Justice Laws Canada for personal information?"
    us_route = classify_knowledge_query(us_q, assigned_pack_ids=["pack.legal"])
    ca_route = classify_knowledge_query(ca_q, assigned_pack_ids=["pack.legal"])
    us_ret = retrieve_knowledge_fabric(
        client, us_q, assigned_pack_ids=["pack.legal"], top_k=5, settings=settings
    )
    ca_ret = retrieve_knowledge_fabric(
        client, ca_q, assigned_pack_ids=["pack.legal"], top_k=5, settings=settings
    )
    us_j = sorted({(h.get("jurisdiction") or "").upper() for h in us_ret.get("results") or []})
    ca_j = sorted({(h.get("jurisdiction") or "").upper() for h in ca_ret.get("results") or []})
    out = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "cisa": cisa.get("per_source"),
        "router": {
            "us_route": us_route.to_dict(),
            "ca_route": ca_route.to_dict(),
            "us_hit_jurisdictions": us_j,
            "ca_hit_jurisdictions": ca_j,
            "us_excludes_ca": "CA-FEDERAL" not in us_j,
            "ca_includes_ca": any("CA" in j for j in ca_j),
            "ca_excludes_us_federal": "US-FEDERAL" not in ca_j,
            "us_sources": [h.get("source_id") for h in us_ret.get("results") or []],
            "ca_sources": [h.get("source_id") for h in ca_ret.get("results") or []],
        },
    }
    dest = ROOT / "docs" / "delivery" / "knowledge-fabric-wave2-router-reverify.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
