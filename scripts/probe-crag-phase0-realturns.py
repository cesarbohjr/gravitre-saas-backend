#!/usr/bin/env python3
"""What do the REAL (non-probe) unified turns actually ask for?

Phase 0d found the sufficiency loop ran 256 times, all in the smoke probe org,
and zero times in the only real human org. Those 34 real turns carried no
`evidenceSufficiency` block at all, which means the knowledge builder returned
before the loop. The reason matters:

  * `not_informational` -> real traffic is action/tool shaped, not
    knowledge-retrieval shaped. A retrieval-correction loop is then solving a
    problem real users are not hitting.
  * `no_hits`           -> real traffic IS knowledge shaped but retrieval finds
    nothing, which would be a live retrieval gap worth closing.

These point at opposite work, so the distinction decides whether the CRAG
program is aimed at real demand.

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

OUT = REPO / "docs" / "delivery" / "crag-phase0-realturns.json"
PROBE_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
LOOKBACK_DAYS = 30


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

    rows: list[dict[str, Any]] = []
    for action in ("unified_turn.live.completed", "unified_turn.live.fallthrough"):
        data = (
            client.table("audit_events")
            .select("org_id,action,created_at,metadata")
            .eq("action", action)
            .neq("org_id", PROBE_ORG)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(300)
            .execute()
            .data
            or []
        )
        rows.extend(data)

    know_skipped = Counter()
    outcomes = Counter()
    depths = Counter()
    has_know = 0
    detail: list[dict[str, Any]] = []

    for row in rows:
        meta = _meta(row.get("metadata"))
        know = _find(meta, "unifiedTurnKnowledge")
        if isinstance(know, dict):
            has_know += 1
            know_skipped[str(know.get("skipped"))] += 1
        else:
            know_skipped["<no knowledge block at all>"] += 1
        outcomes[str(_find(meta, "outcome_kind") or _find(meta, "outcomeKind"))] += 1
        depths[str(_find(meta, "reasoning_depth") or _find(meta, "reasoningDepth"))] += 1
        if len(detail) < 12:
            detail.append(
                {
                    "created_at": row.get("created_at"),
                    "action": row.get("action"),
                    "outcome_kind": _find(meta, "outcome_kind"),
                    "reasoning_depth": _find(meta, "reasoning_depth"),
                    "knowledge_skipped": (know or {}).get("skipped")
                    if isinstance(know, dict)
                    else "<absent>",
                    "org_rag_chunk_count": (know or {}).get("org_rag_chunk_count")
                    if isinstance(know, dict)
                    else None,
                    "route_reason": (know or {}).get("route_reason")
                    if isinstance(know, dict)
                    else None,
                }
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "real_turns_examined": len(rows),
        "with_knowledge_block": has_know,
        "knowledge_skipped_reason": dict(know_skipped.most_common()),
        "outcome_kind": dict(outcomes.most_common()),
        "reasoning_depth": dict(depths.most_common()),
        "detail": detail,
    }
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("=" * 70)
    print("PHASE 0e - what do REAL (non-probe) turns look like?")
    print("=" * 70)
    print(f"real turns examined      : {report['real_turns_examined']}")
    print(f"with knowledge block     : {report['with_knowledge_block']}")
    print()
    print("knowledge builder skipped reason:")
    for k, v in report["knowledge_skipped_reason"].items():
        print(f"  {k:34s} {v}")
    print()
    print("outcome_kind:")
    for k, v in report["outcome_kind"].items():
        print(f"  {k:34s} {v}")
    print()
    print("reasoning_depth:")
    for k, v in report["reasoning_depth"].items():
        print(f"  {k:34s} {v}")
    print()
    for d in report["detail"][:10]:
        print(
            f"  {d['created_at'][:19]} {str(d['outcome_kind'])[:26]:26s} "
            f"depth={str(d['reasoning_depth'])[:14]:14s} know_skipped={d['knowledge_skipped']}"
        )
    print()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
