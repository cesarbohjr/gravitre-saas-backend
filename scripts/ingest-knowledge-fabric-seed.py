#!/usr/bin/env python3
"""Register + ingest licensed knowledge fabric packs (Legal, Finance, Cyber, HR)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from supabase import create_client  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.knowledge_fabric.ingest import ingest_pack, register_all_sources  # noqa: E402


async def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    registered = register_all_sources(client)
    packs = ["pack.cybersecurity", "pack.finance", "pack.legal", "pack.hr"]
    embed = os.environ.get("KNOWLEDGE_FABRIC_EMBED", "1") != "0"
    results = {"registered": len(registered), "packs": {}}
    for pack_id in packs:
        results["packs"][pack_id] = await ingest_pack(
            client, pack_id, settings=settings, embed=embed, limit=int(os.environ.get("KF_LIMIT", "4"))
        )
    out = ROOT / "docs" / "delivery" / "knowledge-fabric-ingest-live.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
