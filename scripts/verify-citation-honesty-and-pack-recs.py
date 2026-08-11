"""Live verify CISA content_mode in provenance + department pack recommendations."""
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
from app.knowledge_fabric.registry import list_platform_packs
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric
from app.knowledge_fabric.router import recommended_pack_ids_for_department


def main() -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    cisa_q = "What does CISA StopRansomware recommend for ransomware prevention?"
    fabric = retrieve_knowledge_fabric(
        client,
        cisa_q,
        assigned_pack_ids=["pack.cybersecurity"],
        agent_department="cybersecurity",
        top_k=5,
        settings=settings,
    )
    cisa_hits = [
        r
        for r in (fabric.get("results") or [])
        if "cisa" in str(r.get("source_id") or "").lower()
        or "cisa" in str(r.get("citation") or "").lower()
    ]
    cisa_prov = [
        p
        for p in (fabric.get("provenance") or [])
        if "cisa" in str(p.get("source_id") or "").lower()
        or "cisa" in str(p.get("citation") or "").lower()
        or p.get("content_mode")
    ]
    sales = list_platform_packs(agent_department="Sales")
    legal = list_platform_packs(agent_department="Legal")
    out = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "cisa_query": cisa_q,
        "cisa_results": [
            {
                "source_id": r.get("source_id"),
                "citation": r.get("citation"),
                "content_mode": r.get("content_mode"),
                "fetch_status_html_blocked": (r.get("fetch_status") or {}).get("html_blocked")
                if isinstance(r.get("fetch_status"), dict)
                else None,
            }
            for r in cisa_hits
        ],
        "cisa_provenance": [
            {
                "citation": p.get("citation"),
                "content_mode": p.get("content_mode"),
                "fetch_status": p.get("fetch_status"),
                "authority_score": p.get("authority_score"),
            }
            for p in cisa_prov
        ],
        "honesty_pass": any(
            (p.get("content_mode") == "curated_summary_live_html_blocked") for p in cisa_prov
        ),
        "sales_recommended": recommended_pack_ids_for_department("Sales"),
        "legal_recommended": recommended_pack_ids_for_department("Legal"),
        "sales_ui_order": [
            {"pack_id": p["pack_id"], "recommended": p.get("recommended")} for p in sales
        ],
        "legal_ui_order": [
            {"pack_id": p["pack_id"], "recommended": p.get("recommended")} for p in legal
        ],
        "recs_differ": recommended_pack_ids_for_department("Sales")
        != recommended_pack_ids_for_department("Legal"),
    }
    dest = ROOT / "docs" / "delivery" / "knowledge-fabric-honesty-pack-recs-verify.json"
    dest.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    # Static HTML for screenshot verification (matches citation + pack badge copy)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>Wave2 honesty verify</title>
<style>
body{{font-family:ui-sans-serif,system-ui;background:#0b0f14;color:#e7ecf3;padding:24px}}
.card{{border:1px solid rgba(245,158,11,.4);background:rgba(245,158,11,.05);border-radius:12px;padding:12px;margin:12px 0;max-width:560px}}
.badge{{display:inline-block;border:1px solid rgba(245,158,11,.3);background:rgba(245,158,11,.05);color:#fbbf24;border-radius:999px;padding:2px 10px;font-size:12px;margin-top:8px}}
.pack{{border:1px solid rgba(16,185,129,.4);background:rgba(16,185,129,.05);border-radius:8px;padding:10px;margin:6px 0}}
.pack .rec{{display:inline-block;border:1px solid rgba(16,185,129,.3);background:rgba(16,185,129,.1);color:#6ee7b7;border-radius:999px;padding:2px 8px;font-size:11px;margin-left:8px}}
h2{{font-size:14px;margin-top:28px}}
.meta{{color:#9aa4b2;font-size:12px}}
</style></head><body>
<h1>Knowledge Fabric honesty + pack recommendations</h1>
<p class="meta">as of {out['ran_at']} · honesty_pass={out['honesty_pass']}</p>
<h2>CISA citation card (live provenance)</h2>
"""
    for p in cisa_prov[:3]:
        mode = p.get("content_mode") or ""
        label = (
            "Curated summary — live source fetch was blocked"
            if mode == "curated_summary_live_html_blocked"
            else mode
        )
        html += f"""<div class="card" id="cisa-cite">
  <div><strong>{p.get('citation') or 'CISA'}</strong></div>
  <span class="badge">{label}</span>
  <div class="meta">authority={p.get('authority_score')} · content_mode={mode}</div>
</div>"""
    html += "<h2>Sales department — recommended packs</h2><div id='sales-packs'>"
    for p in sales:
        if p.get("recommended"):
            html += f"<div class='pack'>{p['label']}<span class='rec'>Recommended for Sales</span></div>"
    html += "</div><h2>Legal department — recommended packs</h2><div id='legal-packs'>"
    for p in legal:
        if p.get("recommended"):
            html += f"<div class='pack'>{p['label']}<span class='rec'>Recommended for Legal</span></div>"
    html += "</div></body></html>"
    html_path = ROOT / "docs" / "delivery" / "knowledge-fabric-honesty-pack-recs-verify.html"
    html_path.write_text(html, encoding="utf-8")
    print(json.dumps({"wrote": str(dest), "html": str(html_path), **{k: out[k] for k in ("honesty_pass", "recs_differ", "sales_recommended", "legal_recommended")}}, indent=2))


if __name__ == "__main__":
    main()
