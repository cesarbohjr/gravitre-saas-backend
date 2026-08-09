#!/usr/bin/env python3
"""Lightweight leak monitor: conversation creates last 24h by credential type.

Prints JSON suitable for a single query / internal dashboard tile.
Flags any non-isolated org row created by the conversation smoke SA (or smoke-titled).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from gravitre_test_client import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    ISOLATED_ORG_ID,
    ISOLATED_USER_ID,
    get_service_client,
    load_env,
)

OUT = REPO / "docs" / "delivery" / "conversation-write-leak-24h.json"


def main() -> int:
    env = load_env()
    client = get_service_client(env)
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    resp = (
        client.table("conversations")
        .select("id, org_id, user_id, title, message_count, created_at, deleted_at")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    rows = resp.data or []

    by_org: dict[str, int] = {}
    by_user: dict[str, int] = {}
    leaks: list[dict] = []
    for row in rows:
        oid = str(row.get("org_id") or "")
        uid = str(row.get("user_id") or "")
        by_org[oid] = by_org.get(oid, 0) + 1
        by_user[uid] = by_user.get(uid, 0) + 1
        if oid.lower() != ISOLATED_ORG_ID.lower() and (
            uid.lower() == ISOLATED_USER_ID.lower()
            or oid.lower() == FORBIDDEN_OPERATOR_ORG_ID.lower()
            and any(
                token in str(row.get("title") or "").lower()
                for token in ("perf-audit", "retrieval-ab", "wave67", "smoke", "gravitre-", "sta-307")
            )
        ):
            if row.get("deleted_at") is None:
                leaks.append(
                    {
                        "id": row.get("id"),
                        "org_id": oid,
                        "user_id": uid,
                        "title": row.get("title"),
                        "created_at": row.get("created_at"),
                    }
                )

    report = {
        "probe": "conversation_write_leak_24h",
        "since": since,
        "total_creates": len(rows),
        "by_org": by_org,
        "by_user": by_user,
        "isolated_org_id": ISOLATED_ORG_ID,
        "isolated_user_id": ISOLATED_USER_ID,
        "active_leak_candidates": leaks,
        "pass": len(leaks) == 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
