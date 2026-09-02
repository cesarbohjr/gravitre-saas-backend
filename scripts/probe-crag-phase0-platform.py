#!/usr/bin/env python3
"""Platform-wide corpus and real-traffic census, to size the CRAG work honestly.

Phase 0c found all 256 sufficiency-loop turns came from one empty probe org.
Before concluding "there is no corpus to correct retrieval over", confirm the
scope properly rather than from one org's view:

  * how many orgs exist, and how many have any RAG corpus at all
  * where the single platform-wide rag_chunk actually lives, and in which
    `environment` (retrieval filters on it, so a chunk in the wrong environment
    is invisible even though it exists)
  * which orgs produced unified-turn traffic, separating probe from real
  * whether any REAL org turn ever ran the loop

Read-only.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "crag-phase0-platform.json"
LOOKBACK_DAYS = 30
PAGE = 500


def _load_env() -> None:
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded is None:
            continue
        for k, v in loaded.items():
            if v and k not in os.environ:
                os.environ[k] = v


def _find(node: Any, target: str, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if isinstance(node, dict):
        if target in node:
            return node[target]
        for v in node.values():
            got = _find(v, target, depth + 1)
            if got is not None:
                return got
    elif isinstance(node, list):
        for item in node[:20]:
            got = _find(item, target, depth + 1)
            if got is not None:
                return got
    return None


def _meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    report: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat()}

    # orgs
    orgs = (
        client.table("organizations").select("id,name,created_at").limit(500).execute().data
        or []
    )
    report["org_count"] = len(orgs)
    by_id = {str(o["id"]): o for o in orgs}

    # the whole corpus, all orgs
    chunks = (
        client.table("rag_chunks")
        .select("id,org_id,document_id,environment,created_at")
        .limit(500)
        .execute()
        .data
        or []
    )
    docs = (
        client.table("rag_documents")
        .select("id,org_id,title,environment,created_at")
        .limit(500)
        .execute()
        .data
        or []
    )
    report["rag_chunks_total"] = len(chunks)
    report["rag_documents_total"] = len(docs)
    report["rag_chunks_detail"] = [
        {
            "org_id": c.get("org_id"),
            "org_name": (by_id.get(str(c.get("org_id"))) or {}).get("name"),
            "environment": c.get("environment"),
            "created_at": c.get("created_at"),
        }
        for c in chunks
    ]
    report["rag_documents_detail"] = [
        {
            "org_id": d.get("org_id"),
            "org_name": (by_id.get(str(d.get("org_id"))) or {}).get("name"),
            "title": d.get("title"),
            "environment": d.get("environment"),
            "created_at": d.get("created_at"),
        }
        for d in docs
    ]
    report["orgs_with_corpus"] = sorted(
        {str(c.get("org_id")) for c in chunks} | {str(d.get("org_id")) for d in docs}
    )

    # unified-turn traffic by org, and did the loop ever run for each
    traffic: dict[str, Counter] = {}
    for action in (
        "unified_turn.live.completed",
        "unified_turn.live.fallthrough",
    ):
        offset = 0
        while True:
            batch = (
                client.table("audit_events")
                .select("org_id,metadata")
                .eq("action", action)
                .gte("created_at", since)
                .order("created_at", desc=True)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            data = batch.data or []
            for row in data:
                org = str(row.get("org_id"))
                traffic.setdefault(org, Counter())
                traffic[org][action] += 1
                meta = _meta(row.get("metadata"))
                suff = _find(meta, "evidenceSufficiency")
                if isinstance(suff, dict):
                    if suff.get("skipped"):
                        traffic[org][f"loop_skipped:{suff.get('skipped')}"] += 1
                    else:
                        traffic[org]["loop_RAN"] += 1
                else:
                    traffic[org]["no_sufficiency_block"] += 1
            if len(data) < PAGE:
                break
            offset += PAGE

    report["traffic_by_org"] = {
        org: {
            "org_name": (by_id.get(org) or {}).get("name", "<unknown org>"),
            **dict(counts),
        }
        for org, counts in sorted(traffic.items(), key=lambda kv: -sum(kv[1].values()))
    }

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("=" * 72)
    print("PHASE 0d - platform census")
    print("=" * 72)
    print(f"organizations               : {report['org_count']}")
    print(f"rag_documents (ALL orgs)    : {report['rag_documents_total']}")
    print(f"rag_chunks    (ALL orgs)    : {report['rag_chunks_total']}")
    print(f"orgs with any corpus        : {report['orgs_with_corpus']}")
    print()
    print("corpus detail:")
    for d in report["rag_documents_detail"]:
        print(f"  doc   org={d['org_name']!r} env={d['environment']} title={str(d['title'])[:40]!r}")
    for c in report["rag_chunks_detail"]:
        print(f"  chunk org={c['org_name']!r} env={c['environment']} created={c['created_at']}")
    print()
    print("unified-turn traffic by org (30d):")
    for org, info in report["traffic_by_org"].items():
        print(f"  {info.get('org_name')!r}  [{org}]")
        for k, v in info.items():
            if k == "org_name":
                continue
            print(f"      {k:44s} {v}")
    print()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
