"""Register + ingest Gravitre-authored tool expertise; compose HubSpot retrieve test."""
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
from app.connectors.action_catalog.integration_taxonomy import classify_wave1_report
from app.connectors.action_catalog.registry import get_vendor_spec
from app.knowledge_fabric.ingest import ingest_sources, register_all_sources
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric
from app.knowledge_fabric.tool_knowledge import (
    tool_knowledge_vendors,
    tool_packs_for_connected_vendors,
)


async def main() -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    registered = register_all_sources(client)
    vendors = list(tool_knowledge_vendors())
    source_ids = [f"tool.{v}.expertise" for v in vendors]
    ingested = await ingest_sources(
        client, source_ids, settings=settings, embed=True, limit=4
    )

    # Compose test: HubSpot actions exist + tool knowledge retrieves together
    hubspot_spec = get_vendor_spec("hubspot")
    hubspot_actions = [a.id for a in (hubspot_spec.all_actions() if hubspot_spec else [])[:5]]
    packs = tool_packs_for_connected_vendors(["hubspot", "slack"])
    fabric = retrieve_knowledge_fabric(
        client,
        "How should I update a HubSpot deal stage and avoid INVALID_PROPERTY errors?",
        assigned_pack_ids=packs,
        agent_department="sales",
        top_k=6,
        settings=settings,
    )
    hits = fabric.get("results") or []
    hubspot_knowledge_hits = [
        h
        for h in hits
        if "hubspot" in str(h.get("source_id") or "").lower()
        or "hubspot" in str(h.get("citation") or "").lower()
    ]

    per = ingested.get("per_source") or []
    out = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "phase0_ref": "docs/delivery/tool-knowledge-phase0-reconciliation.md",
        "registered_sources": len(registered),
        "tool_vendors_ingested": vendors,
        "ingest_per_source": per,
        "license_posture": "Gravitre-Original — commercial_use=true, licence_verified=true; vendor docs NOT bulk-ingested",
        "integration_class_sample": classify_wave1_report()[:8],
        "compose_test": {
            "connected_vendors": ["hubspot", "slack"],
            "tool_packs": packs,
            "hubspot_catalog_actions_sample": hubspot_actions,
            "fabric_hit_count": len(hits),
            "hubspot_knowledge_hits": len(hubspot_knowledge_hits),
            "compose_pass": bool(hubspot_actions) and bool(hubspot_knowledge_hits),
            "sample_citations": [h.get("citation") for h in hubspot_knowledge_hits[:3]],
        },
        "cross_department": {
            "note": "Single pack.tool.hubspot row; Sales and Marketing agents both receive it when hubspot is connected",
            "packs_for_hubspot_only": tool_packs_for_connected_vendors(["hubspot"]),
        },
        "blocked_or_deferred": [
            {
                "vendor": v,
                "reason": "No ActionSpec connector — tool knowledge deferred",
            }
            for v in (
                "gitlab",
                "trello",
                "linear",
                "paypal",
                "shopify",
                "woocommerce",
                "wordpress",
                "brevo",
                "meta_marketing",
                "cloudflare",
                "azure",
                "google_cloud",
            )
        ],
    }
    dest = ROOT / "docs" / "delivery" / "tool-knowledge-wave1-ingest-results.json"
    dest.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(dest),
                "compose_pass": out["compose_test"]["compose_pass"],
                "vendors": vendors,
                "chunks": ingested.get("chunks"),
                "errors": ingested.get("errors"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
