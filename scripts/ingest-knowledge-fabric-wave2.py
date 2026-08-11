"""Wave 2: live license verify → register → ingest genuinely-new sources only."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

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
from app.knowledge_fabric.ingest import ingest_sources, register_all_sources
from app.knowledge_fabric.quality import compute_pack_quality
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric
from app.knowledge_fabric.router import classify_knowledge_query

HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (wave2-license-verify; support@gravitre.ai)"}

# Ordered Phase 2 batches
BATCHES: list[tuple[str, list[str]]] = [
    ("hr", ["hr.dol.employment_law_guide", "hr.eeoc.employer_guidance"]),
    ("legal_ca", ["legal.ca.justice_laws"]),
    (
        "cyber",
        [
            "cyber.nist.ai_rmf",
            "cyber.nist.genai_profile",
            "cyber.nist.zero_trust",
            "cyber.cisa.advisories",
        ],
    ),
    ("marketing_ca", ["marketing.ca.competition_bureau"]),
]

LICENSE_CHECKS: dict[str, dict] = {
    "US-Gov-Work": {
        # usa.gov/government-works meta-refreshes; live terms are on government-copyright
        "urls": [
            "https://www.usa.gov/government-copyright",
            "https://www.archives.gov/founding-docs/constitution-transcript",
        ],
        "must_match_any": [
            r"not subject to copyright protection",
            r"works of the U\.S\. government",
            r"Sections?\s+101 and 105",
            r"Government work is something created by a U\.S\. government",
            r"copyright-free",
        ],
        "must_not": [r"BY-NC", r"non-?commercial use only"],
    },
    "Canada-OGL": {
        "urls": ["https://open.canada.ca/en/open-government-licence-canada"],
        "must_match_any": [
            r"Open Government Licence",
            r"copy, modify, publish, translate, adapt, distribute",
            r"commercial purpose",
        ],
        "must_not": [r"non-?commercial only", r"BY-NC"],
    },
}

SOURCE_LICENSE: dict[str, str] = {
    "hr.dol.employment_law_guide": "US-Gov-Work",
    "hr.eeoc.employer_guidance": "US-Gov-Work",
    "legal.ca.justice_laws": "Canada-OGL",
    "cyber.nist.ai_rmf": "US-Gov-Work",
    "cyber.nist.genai_profile": "US-Gov-Work",
    "cyber.nist.zero_trust": "US-Gov-Work",
    "cyber.cisa.advisories": "US-Gov-Work",
    "marketing.ca.competition_bureau": "Canada-OGL",
}


def _plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text)


async def verify_license_family(family: str) -> dict:
    cfg = LICENSE_CHECKS[family]
    headers = {
        **HEADERS,
        "User-Agent": "Mozilla/5.0 (compatible; GravitreKnowledgeFabric/1.0; +https://gravitre.ai)",
    }
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=headers) as client:
        bodies: list[str] = []
        url_status: list[dict] = []
        for url in cfg["urls"]:
            last_err = None
            for attempt in range(3):
                try:
                    r = await client.get(url)
                    text = _plain(r.text)[:80000]
                    bodies.append(text)
                    url_status.append(
                        {
                            "url": url,
                            "status": r.status_code,
                            "chars": len(text),
                            "attempt": attempt + 1,
                        }
                    )
                    last_err = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = str(exc)[:200] or exc.__class__.__name__
                    await asyncio.sleep(1.5 * (attempt + 1))
            if last_err:
                url_status.append({"url": url, "status": "error", "error": last_err})
        blob = "\n".join(bodies)
        matched = [p for p in cfg["must_match_any"] if re.search(p, blob, re.I)]
        forbidden = [p for p in cfg["must_not"] if re.search(p, blob, re.I)]
        ok = bool(matched) and not forbidden and any(
            isinstance(u.get("status"), int) and u["status"] < 400 for u in url_status
        )
        return {
            "family": family,
            "ok": ok,
            "matched": matched,
            "forbidden_hits": forbidden,
            "urls": url_status,
        }


async def main() -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    out: dict = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "phase0_ref": "docs/delivery/knowledge-fabric-wave2-phase0-dedupe.md",
    }

    # Live license verification (OpenStax discipline)
    families = sorted({SOURCE_LICENSE[s] for batch in BATCHES for s in batch[1]})
    license_results = {}
    for fam in families:
        license_results[fam] = await verify_license_family(fam)
    out["license_verification"] = license_results

    halted: list[str] = []
    allowed_sources: list[str] = []
    for _batch, sids in BATCHES:
        for sid in sids:
            fam = SOURCE_LICENSE[sid]
            if license_results[fam]["ok"]:
                allowed_sources.append(sid)
            else:
                halted.append(sid)
    out["halted_license_mismatch"] = halted
    out["allowed_sources"] = allowed_sources

    # Register all (paused holds OK) then ingest only verified new sources
    registered = register_all_sources(client)
    out["registered"] = len(registered)

    batch_results = []
    for name, sids in BATCHES:
        to_run = [s for s in sids if s in allowed_sources]
        if not to_run:
            batch_results.append({"batch": name, "status": "halted", "sources": sids})
            continue
        result = await ingest_sources(client, to_run, settings=settings, embed=True, limit=3)
        batch_results.append({"batch": name, "status": "ran", **result})
    out["batches"] = batch_results

    # Router US vs CA (classify + retrieve)
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
    us_j = {((h.get("jurisdiction") or "")).upper() for h in us_ret.get("results") or []}
    ca_j = {((h.get("jurisdiction") or "")).upper() for h in ca_ret.get("results") or []}
    out["router_us_vs_ca"] = {
        "us_query_route": us_route.to_dict(),
        "ca_query_route": ca_route.to_dict(),
        "us_hit_jurisdictions": sorted(us_j),
        "ca_hit_jurisdictions": sorted(ca_j),
        "ca_route_has_ca_federal": "CA-federal" in ca_route.jurisdictions,
        "us_route_lacks_ca_federal": "CA-federal" not in us_route.jurisdictions,
        "ca_hits_include_ca": any("CA" in j for j in ca_j),
        "us_hits_exclude_ca_federal": "CA-FEDERAL" not in us_j,
    }

    out["quality"] = compute_pack_quality(client)

    dest = ROOT / "docs" / "delivery" / "knowledge-fabric-wave2-ingest-results.json"
    dest.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"wrote": str(dest), "halted": halted, "batches": [
        {"batch": b["batch"], "status": b.get("status"), "documents": b.get("documents"), "chunks": b.get("chunks"), "errors": b.get("errors")}
        for b in batch_results
    ]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
