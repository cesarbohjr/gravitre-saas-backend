"""Register + ingest Sales/Marketing open/gov sources; prove NC gate."""
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
from app.knowledge_fabric.ingest import ingest_pack, register_all_sources, replace_document_chunks
from app.knowledge_fabric.license_types import assert_ingest_allowed
from app.knowledge_fabric.registry import get_spec
from app.knowledge_fabric.router import classify_knowledge_query
from app.knowledge_fabric.sources.google_trends import trends_access_status
from app.knowledge_fabric.sources.openstax import deliberate_nc_ingest_attempt
from app.knowledge_fabric.sources.saylor import provenance_report_all


async def main() -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    out: dict = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "git_sha_env": os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("GIT_SHA"),
    }

    # Phase 0/4 — NC hard gate disposable attempt
    nc_row = {
        "license_type": "A",
        "ingestion_method": "bulk",
        "crawl_allowed": True,
        "commercial_use_allowed": False,
        "source_id": "marketing.openstax.principles",
    }
    out["nc_gate_unit"] = deliberate_nc_ingest_attempt(nc_row)
    try:
        openstax = get_spec("marketing.openstax.principles")
        assert openstax is not None
        source_row = openstax.to_row()
        # force an ingest attempt path
        replace_document_chunks(
            client,
            source_row={
                **source_row,
                "id": "00000000-0000-0000-0000-000000000099",
                "commercial_use_allowed": False,
                "license_type": "A",
            },
            external_id="openstax-nc-should-fail",
            title="OpenStax NC probe",
            content="should not ingest",
            citation="probe",
            jurisdiction=None,
            topics=["marketing"],
            embed=False,
        )
        out["nc_gate_ingest"] = {"rejected": False, "error": None}
    except Exception as exc:  # noqa: BLE001
        out["nc_gate_ingest"] = {"rejected": True, "error": str(exc)[:300]}

    # HubSpot / Trends refuse permanent ingest
    for sid in ("marketing.hubspot.research_live", "marketing.google_trends.live"):
        spec = get_spec(sid)
        try:
            assert_ingest_allowed(
                spec.license_type,
                ingestion_method=spec.ingestion_method,
                crawl_allowed=spec.crawl_allowed,
                commercial_use_allowed=spec.commercial_use_allowed,
            )
            out[f"refuse_{sid}"] = {"rejected": False}
        except ValueError as exc:
            out[f"refuse_{sid}"] = {"rejected": True, "error": str(exc)[:200]}

    out["google_trends_access"] = trends_access_status()
    out["saylor_provenance"] = provenance_report_all()

    registered = register_all_sources(client)
    out["registered"] = [
        {
            "source_id": r.get("source_id"),
            "license_type": r.get("license_type"),
            "commercial_use_allowed": r.get("commercial_use_allowed"),
            "legal_review_status": r.get("legal_review_status"),
            "status": r.get("status"),
        }
        for r in registered
        if (r.get("source_id") or "").startswith(("sales.", "marketing."))
        or (r.get("department") in {"sales", "marketing"})
    ]

    # Prefer department from registry row metadata
    out["registered"] = [
        r
        for r in registered
        if str(r.get("source_id", "")).startswith(("sales.", "marketing."))
    ]

    marketing = await ingest_pack(client, "pack.marketing", settings=settings, embed=True, limit=4)
    sales = await ingest_pack(client, "pack.sales", settings=settings, embed=True, limit=4)
    out["ingest_marketing"] = {
        "documents": marketing.get("documents"),
        "chunks": marketing.get("chunks"),
        "errors": marketing.get("errors"),
    }
    out["ingest_sales"] = {
        "documents": sales.get("documents"),
        "chunks": sales.get("chunks"),
        "errors": sales.get("errors"),
    }

    # Router live classify
    q = "What does the FTC CAN-SPAM rule require for email marketing?"
    route = classify_knowledge_query(
        q, assigned_pack_ids=["pack.marketing", "pack.legal", "pack.sales"]
    )
    out["router_compliance"] = route.to_dict()

    path = ROOT / "docs/delivery/sales-marketing-packs-ingest-live.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "saylor_provenance"}, indent=2, default=str)[:5000])
    print("wrote", path)


if __name__ == "__main__":
    asyncio.run(main())
