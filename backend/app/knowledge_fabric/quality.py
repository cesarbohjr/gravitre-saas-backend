"""Knowledge Fabric quality metrics — honest per-pack coverage (Module C style)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Topic taxonomy per pack — coverage % is hits against this list (never invented).
PACK_TOPIC_TAXONOMY: dict[str, tuple[str, ...]] = {
    "pack.legal": (
        "constitution",
        "case_law",
        "statutes",
        "regulations",
        "employment_law",
        "privacy",
        "pipeda",
        "competition",
        "canada_federal",
        "ftc",
        "can_spam",
    ),
    "pack.finance": (
        "filings",
        "xbrl",
        "corporate_disclosure",
        "edgar",
    ),
    "pack.cybersecurity": (
        "csf2",
        "sp800-53",
        "ai_rmf",
        "genai",
        "zero_trust",
        "cisa",
        "ransomware",
        "msp",
        "advisories",
    ),
    "pack.hr": (
        "employment_law",
        "wage_hour",
        "flsa",
        "fmla",
        "eeoc",
        "occupations",
        "leave",
    ),
    "pack.sales": (
        "sales_management",
        "pipeline",
        "census",
        "establishments",
        "personal_selling",
    ),
    "pack.marketing": (
        "advertising",
        "consumer_behavior",
        "market_research",
        "influencer_marketing",
        "deceptive_marketing",
        "segmentation",
        "can_spam",
        "competition_bureau",
    ),
}

# Tool expertise packs share a small taxonomy (vendor + practice topics).
_TOOL_TOPIC_TAXONOMY: tuple[str, ...] = (
    "tool_expertise",
    "connector",
    "best_practices",
)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _days_since(ts: datetime | None, *, now: datetime) -> float | None:
    if ts is None:
        return None
    return max(0.0, (now - ts).total_seconds() / 86400.0)


def compute_pack_quality(
    client: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return honest per-pack quality metrics from live knowledge_* tables."""
    now = now or datetime.now(timezone.utc)
    sources = (
        client.table("knowledge_sources")
        .select(
            "id,source_id,department,license_type,licence_verified,commercial_use_allowed,"
            "authority_score,quality_score,jurisdictions,topics,last_refreshed_at,"
            "license_verified_at,legal_review_status,status,metadata,citation_required"
        )
        .eq("namespace", "platform_shared")
        .execute()
    )
    source_rows = list(sources.data or [])
    source_by_id = {r["id"]: r for r in source_rows if r.get("id")}

    docs = (
        client.table("knowledge_documents")
        .select("id,source_id,jurisdiction,citation,topics,metadata")
        .execute()
    )
    doc_rows = list(docs.data or [])

    chunks = (
        client.table("knowledge_chunks")
        .select("id,document_id,source_id,citation,jurisdiction,authority_score,topics")
        .execute()
    )
    chunk_rows = list(chunks.data or [])

    # Map source uuid → pack_id from metadata
    def pack_for_source(row: dict[str, Any]) -> str:
        meta = row.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("pack_id"):
            return str(meta["pack_id"])
        dept = (row.get("department") or "").strip().lower()
        return {
            "legal": "pack.legal",
            "finance": "pack.finance",
            "cybersecurity": "pack.cybersecurity",
            "hr": "pack.hr",
            "sales": "pack.sales",
            "marketing": "pack.marketing",
        }.get(dept, f"pack.{dept or 'unknown'}")

    packs: dict[str, dict[str, Any]] = {}
    taxonomy_map = dict(PACK_TOPIC_TAXONOMY)
    # Discover tool packs from live sources (already loaded)
    for row in source_rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        pid = str(meta.get("pack_id") or "")
        if pid.startswith("pack.tool.") and pid not in taxonomy_map:
            taxonomy_map[pid] = _TOOL_TOPIC_TAXONOMY
        if (row.get("department") or "") == "tool_expertise" and pid.startswith("pack.tool."):
            taxonomy_map.setdefault(pid, _TOOL_TOPIC_TAXONOMY)

    for sid, taxonomy in taxonomy_map.items():
        packs[sid] = {
            "pack_id": sid,
            "source_count": 0,
            "active_source_count": 0,
            "document_count": 0,
            "chunk_count": 0,
            "authoritative_source_count": 0,  # authority_score >= 0.9
            "primary_source_count": 0,  # license_type A/B government/api
            "avg_authority_score": None,
            "avg_freshness_days": None,
            "jurisdictions_covered": [],
            "live_data_provider_count": 0,  # type B api / live_only D
            "citation_coverage_pct": None,
            "license_verified_pct": None,
            "topic_coverage_pct": None,
            "topics_covered": [],
            "topics_missing": list(taxonomy),
            "gaps": [],
            "honesty": "exact_counts_from_live_tables",
        }

    # Aggregate sources
    auth_sums: dict[str, list[float]] = {}
    fresh_sums: dict[str, list[float]] = {}
    lic_verified: dict[str, list[bool]] = {}
    jurisdictions: dict[str, set[str]] = {}
    topics_hit: dict[str, set[str]] = {}

    for row in source_rows:
        pid = pack_for_source(row)
        if pid not in packs:
            packs[pid] = {
                "pack_id": pid,
                "source_count": 0,
                "active_source_count": 0,
                "document_count": 0,
                "chunk_count": 0,
                "authoritative_source_count": 0,
                "primary_source_count": 0,
                "avg_authority_score": None,
                "avg_freshness_days": None,
                "jurisdictions_covered": [],
                "live_data_provider_count": 0,
                "citation_coverage_pct": None,
                "license_verified_pct": None,
                "topic_coverage_pct": None,
                "topics_covered": [],
                "topics_missing": list(PACK_TOPIC_TAXONOMY.get(pid, ())),
                "gaps": [],
                "honesty": "exact_counts_from_live_tables",
            }
        p = packs[pid]
        p["source_count"] += 1
        if row.get("status") == "active":
            p["active_source_count"] += 1
        auth = float(row.get("authority_score") or 0)
        auth_sums.setdefault(pid, []).append(auth)
        if auth >= 0.9:
            p["authoritative_source_count"] += 1
        if str(row.get("license_type") or "") in {"A", "B"}:
            p["primary_source_count"] += 1
        if str(row.get("license_type") or "") in {"B", "D"}:
            p["live_data_provider_count"] += 1
        days = _days_since(
            _parse_ts(row.get("license_verified_at") or row.get("last_refreshed_at")),
            now=now,
        )
        if days is not None:
            fresh_sums.setdefault(pid, []).append(days)
        lic_verified.setdefault(pid, []).append(bool(row.get("licence_verified")))
        for j in row.get("jurisdictions") or []:
            jurisdictions.setdefault(pid, set()).add(str(j))
        for t in row.get("topics") or []:
            topics_hit.setdefault(pid, set()).add(str(t).lower())

    # Docs / chunks keyed by source uuid → pack
    doc_pack: dict[str, str] = {}
    for d in doc_rows:
        src = source_by_id.get(d.get("source_id"))
        if not src:
            continue
        pid = pack_for_source(src)
        packs[pid]["document_count"] += 1
        doc_pack[d["id"]] = pid
        if d.get("jurisdiction"):
            jurisdictions.setdefault(pid, set()).add(str(d["jurisdiction"]))
        for t in d.get("topics") or []:
            topics_hit.setdefault(pid, set()).add(str(t).lower())

    cited = {pid: [0, 0] for pid in packs}  # [with_citation, total]
    for c in chunk_rows:
        src = source_by_id.get(c.get("source_id"))
        pid = pack_for_source(src) if src else doc_pack.get(c.get("document_id") or "")
        if not pid or pid not in packs:
            continue
        packs[pid]["chunk_count"] += 1
        cited.setdefault(pid, [0, 0])
        cited[pid][1] += 1
        if (c.get("citation") or "").strip():
            cited[pid][0] += 1
        for t in c.get("topics") or []:
            topics_hit.setdefault(pid, set()).add(str(t).lower())

    for pid, p in packs.items():
        if auth_sums.get(pid):
            vals = auth_sums[pid]
            p["avg_authority_score"] = round(sum(vals) / len(vals), 4)
        if fresh_sums.get(pid):
            vals = fresh_sums[pid]
            p["avg_freshness_days"] = round(sum(vals) / len(vals), 2)
        if lic_verified.get(pid):
            vals = lic_verified[pid]
            p["license_verified_pct"] = round(100.0 * sum(1 for v in vals if v) / len(vals), 2)
        if cited.get(pid) and cited[pid][1]:
            p["citation_coverage_pct"] = round(100.0 * cited[pid][0] / cited[pid][1], 2)
        elif p["chunk_count"] == 0:
            p["citation_coverage_pct"] = None  # withhold — no evidence
        p["jurisdictions_covered"] = sorted(jurisdictions.get(pid, set()))
        taxonomy = [t.lower() for t in taxonomy_map.get(pid, ())]
        hit = topics_hit.get(pid, set())
        covered = [t for t in taxonomy if t in hit or any(t in h or h in t for h in hit)]
        missing = [t for t in taxonomy if t not in covered]
        p["topics_covered"] = covered
        p["topics_missing"] = missing
        if taxonomy:
            p["topic_coverage_pct"] = round(100.0 * len(covered) / len(taxonomy), 2)
        else:
            p["topic_coverage_pct"] = None
        # Specific gaps (Module C honesty — name the weak area)
        if missing:
            weak = ", ".join(missing[:4])
            p["gaps"].append(f"{pid}: coverage weak on {weak}")
        if p["chunk_count"] == 0 and p["active_source_count"] > 0:
            p["gaps"].append(f"{pid}: active sources registered but zero chunks ingested")
        if p.get("license_verified_pct") is not None and p["license_verified_pct"] < 100:
            p["gaps"].append(
                f"{pid}: license-verified {p['license_verified_pct']}% (not all sources verified)"
            )

    return {
        "as_of": now.isoformat(),
        "honesty": "exact_live_counts_no_rounding_up",
        "packs": sorted(packs.values(), key=lambda x: x["pack_id"]),
    }
