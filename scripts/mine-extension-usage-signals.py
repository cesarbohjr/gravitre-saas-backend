#!/usr/bin/env python3
"""Mine prod audit_events for extension.usage_signal — v6 surface candidates.

Writes docs/delivery/browser-extension-v6-usage-signals.json
Does NOT implement agentic DOM. Classification only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OUT = ROOT / "docs" / "delivery" / "browser-extension-v6-usage-signals.json"
TIP_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
PAGE_SIZE = 1000
MAX_ROWS = int(os.environ.get("EXT_USAGE_SIGNAL_MAX_ROWS", "5000"))

# Hosts already covered by MV3 content scripts / allowlist — not v6.
ALLOWLISTED_HOST_MARKERS = (
    "linkedin.com",
    "mail.google.com",
    "outlook.office.com",
    "outlook.live.com",
    "outlook.office365.com",
    "lightning.force.com",
    "salesforce.com",
    "force.com",
    "app.slack.com",
)

# Smoke / test noise — not operator demand.
NOISE_HOST_MARKERS = (
    "example.com",
    "localhost",
    "127.0.0.1",
    "gravitre.app",
    "vercel.app",
)
# Reserved / fixture domains used by tip smokes (RFC 2606-style + acme fixtures).
NOISE_HOST_RE = re.compile(
    r"(^|\.)example$|(^|\.)test$|(^|\.)invalid$|(^|\.)localhost$|"
    r"acme-example\.|example\.com$|\.example$",
    re.I,
)
NOISE_NOTE_RE = re.compile(
    r"(v5-parity|v2_smoke|v2_tip|v1_smoke|v3_smoke|v4_|ext.?v5|smoke|parity-edge-brave)",
    re.I,
)
NOISE_PATH_RE = re.compile(r"(v5-parity|parity-edge-brave|/not-allowlisted)", re.I)

# Hosts where a governed catalog/connector path already exists or is the right backlog.
# These are NOT v6 agentic-DOM candidates.
CATALOG_HOST_HINTS: dict[str, str] = {
    "app.hubspot.com": "hubspot catalog actions already on extension allowlist",
    "hubspot.com": "hubspot catalog / connector",
    "app.apollo.io": "apollo catalog actions already on extension allowlist",
    "apollo.io": "apollo catalog / connector",
    "ads.google.com": "google_ads connector / catalog path",
    "analytics.google.com": "google_analytics connector path",
    "business.facebook.com": "meta ads — catalog/connector backlog, not DOM",
    "ads.twitter.com": "x ads — catalog backlog if needed",
    "app.clay.com": "clay — prefer API/connector if productized",
    "clay.com": "clay — prefer API/connector if productized",
    "app.attio.com": "attio — connector/catalog backlog",
    "attio.com": "attio — connector/catalog backlog",
    "app.close.com": "close CRM — connector/catalog backlog",
    "app.salesloft.com": "salesloft — connector/catalog backlog",
    "app.outreach.io": "outreach — connector/catalog backlog",
    "app.gong.io": "gong — connector/catalog backlog",
    "calendar.google.com": "google calendar — connector path",
    "drive.google.com": "google drive — connector path",
    "docs.google.com": "google docs — connector path",
    "sheets.google.com": "google sheets — connector path",
    "notion.so": "notion — connector/catalog backlog",
    "www.notion.so": "notion — connector/catalog backlog",
    "app.asana.com": "asana — connector/catalog backlog",
    "app.monday.com": "monday — connector/catalog backlog",
    "linear.app": "linear — connector/catalog backlog",
    "github.com": "github — connector/catalog backlog",
    "gitlab.com": "gitlab — connector/catalog backlog",
    "app.zendesk.com": "zendesk — Tier 1 connector path",
    "atlassian.net": "jira/confluence — Tier 1 connector path",
    "app.intercom.com": "intercom — connector/catalog backlog",
}


def load_env() -> None:
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        for k, v in loaded.items():
            if v:
                os.environ.setdefault(k, v)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _host(page_url: str | None) -> str:
    text = str(page_url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text if "://" in text else f"https://{text}")
        return (parsed.hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _is_allowlisted_host(host: str) -> bool:
    if not host:
        return False
    return any(host == m or host.endswith("." + m) for m in ALLOWLISTED_HOST_MARKERS)


def _catalog_reason(host: str) -> str | None:
    if not host:
        return None
    if host in CATALOG_HOST_HINTS:
        return CATALOG_HOST_HINTS[host]
    for marker, reason in CATALOG_HOST_HINTS.items():
        if host == marker or host.endswith("." + marker):
            return reason
    return None


def _is_noise(host: str, page_url: str, note: str | None, surface: str | None) -> bool:
    if not host:
        return True
    if any(host == m or host.endswith("." + m) for m in NOISE_HOST_MARKERS):
        return True
    if NOISE_HOST_RE.search(host):
        return True
    if NOISE_NOTE_RE.search(note or ""):
        return True
    if NOISE_PATH_RE.search(page_url or ""):
        return True
    if (surface or "") == "outside_allowlist" and "example.com" in (page_url or ""):
        return True
    return False


def classify(
    host: str,
    *,
    page_url: str,
    note: str | None,
    surface: str | None,
    host_allowlisted: bool | None,
) -> tuple[str, str]:
    """Return (bucket, reason). bucket: noise | allowlisted | catalog | possible_dom_forcing."""
    if _is_noise(host, page_url, note, surface):
        return "noise", "smoke/test/internal host or note"
    if host_allowlisted or _is_allowlisted_host(host):
        return "allowlisted", "already on extension host allowlist / content scripts"
    catalog = _catalog_reason(host)
    if catalog:
        return "catalog", catalog
    return (
        "possible_dom_forcing",
        "non-allowlisted host with no known catalog/connector mapping — needs human review "
        "(only promotes to v6 if no API exists and multi-step form need is real)",
    )


def fetch_signals(client: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch tip-org first, then recent global if tip is sparse."""
    scope: dict[str, Any] = {"tip_org": TIP_ORG, "tip_count": 0, "global_count": 0, "mode": "tip_only"}
    tip_rows: list[dict[str, Any]] = []
    offset = 0
    while len(tip_rows) < MAX_ROWS:
        batch = (
            client.table("audit_events")
            .select("id,org_id,action,resource_type,resource_id,metadata,created_at,actor_id")
            .eq("action", "extension.usage_signal")
            .eq("org_id", TIP_ORG)
            .order("created_at", desc=True)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        if not batch:
            break
        tip_rows.extend(batch)
        offset += len(batch)
        if len(batch) < PAGE_SIZE:
            break
    scope["tip_count"] = len(tip_rows)

    rows = list(tip_rows)
    if len(tip_rows) < 25:
        scope["mode"] = "tip_plus_global"
        global_rows: list[dict[str, Any]] = []
        offset = 0
        seen_ids = {r.get("id") for r in tip_rows}
        while len(global_rows) + len(tip_rows) < MAX_ROWS:
            batch = (
                client.table("audit_events")
                .select("id,org_id,action,resource_type,resource_id,metadata,created_at,actor_id")
                .eq("action", "extension.usage_signal")
                .order("created_at", desc=True)
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
                .data
                or []
            )
            if not batch:
                break
            for r in batch:
                if r.get("id") in seen_ids:
                    continue
                global_rows.append(r)
                seen_ids.add(r.get("id"))
            offset += len(batch)
            if len(batch) < PAGE_SIZE:
                break
        scope["global_count"] = len(global_rows)
        rows = tip_rows + global_rows
    return rows, scope


def main() -> int:
    load_env()
    from app.config import get_settings
    from supabase import create_client

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows, scope = fetch_signals(client)

    host_stats: dict[str, dict[str, Any]] = {}
    bucket_counts: Counter[str] = Counter()
    by_bucket_hosts: dict[str, list[str]] = defaultdict(list)

    for row in rows:
        meta = _meta(row)
        page_url = str(meta.get("page_url") or meta.get("pageUrl") or "")[:2000]
        host = _host(page_url)
        note = meta.get("note")
        surface = meta.get("surface") or meta.get("surface_requested")
        host_allowlisted = meta.get("host_allowlisted")
        if isinstance(host_allowlisted, str):
            host_allowlisted = host_allowlisted.lower() in {"true", "1", "yes"}
        bucket, reason = classify(
            host,
            page_url=page_url,
            note=str(note) if note else None,
            surface=str(surface) if surface else None,
            host_allowlisted=bool(host_allowlisted) if host_allowlisted is not None else None,
        )
        bucket_counts[bucket] += 1
        key = host or "(empty)"
        if key not in host_stats:
            host_stats[key] = {
                "host": key,
                "count": 0,
                "bucket": bucket,
                "reason": reason,
                "surfaces": Counter(),
                "notes": Counter(),
                "org_ids": set(),
                "sample_urls": [],
                "latest_at": row.get("created_at"),
            }
        st = host_stats[key]
        st["count"] += 1
        # Prefer non-noise bucket if host appears in mixed classifications
        priority = {
            "possible_dom_forcing": 3,
            "catalog": 2,
            "allowlisted": 1,
            "noise": 0,
        }
        if priority.get(bucket, 0) >= priority.get(st["bucket"], 0):
            st["bucket"] = bucket
            st["reason"] = reason
        st["surfaces"][str(surface or "")] += 1
        if note:
            st["notes"][str(note)[:120]] += 1
        st["org_ids"].add(str(row.get("org_id") or ""))
        if len(st["sample_urls"]) < 5 and page_url:
            st["sample_urls"].append(page_url[:300])
        if row.get("created_at") and (
            not st["latest_at"] or str(row.get("created_at")) > str(st["latest_at"])
        ):
            st["latest_at"] = row.get("created_at")

    hosts_out = []
    for st in sorted(host_stats.values(), key=lambda x: (-x["count"], x["host"])):
        bucket = st["bucket"]
        by_bucket_hosts[bucket].append(st["host"])
        hosts_out.append(
            {
                "host": st["host"],
                "count": st["count"],
                "bucket": bucket,
                "reason": st["reason"],
                "surfaces": dict(st["surfaces"]),
                "topNotes": dict(st["notes"].most_common(5)),
                "orgCount": len([o for o in st["org_ids"] if o]),
                "sampleUrls": st["sample_urls"],
                "latestAt": st["latest_at"],
            }
        )

    possible = [h for h in hosts_out if h["bucket"] == "possible_dom_forcing"]
    catalog = [h for h in hosts_out if h["bucket"] == "catalog"]

    evidence = {
        "probe": "extension_v6_usage_signal_mine",
        "verified_at": utcnow(),
        "scope": scope,
        "totalRows": len(rows),
        "bucketCounts": dict(bucket_counts),
        "uniqueHosts": len(hosts_out),
        "possibleDomForcingHosts": possible,
        "catalogBacklogHosts": catalog,
        "hosts": hosts_out,
        "gateNote": (
            "possible_dom_forcing hosts are candidates for human pick only. "
            "Zero such hosts ⇒ v6 gate remains closed. "
            "No agentic DOM code ships from this probe."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "overall": "PASS",
                "totalRows": len(rows),
                "scope": scope,
                "bucketCounts": dict(bucket_counts),
                "possibleDomForcing": len(possible),
                "catalogBacklog": len(catalog),
                "artifact": str(OUT.relative_to(ROOT)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
