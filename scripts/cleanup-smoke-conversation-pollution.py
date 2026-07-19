#!/usr/bin/env python3
"""Soft-delete smoke/probe conversation pollution in real (non-isolated) orgs.

Criteria (OR):
  1) message_count=0 AND zero conversation_messages rows
  2) title matches known probe/smoke/CI patterns

Never touches the isolated conversation test org.
Soft-delete only (deleted_at). Writes an audit JSON before mutate.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
)

OUT = REPO / "docs" / "delivery" / "smoke-conversation-pollution-cleanup.json"
BATCH_TAG = f"smoke_conv_cleanup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

TITLE_SQL = """(
  c.title ILIKE '%STA-307%'
  OR c.title ILIKE '%perf-audit%'
  OR c.title ILIKE 'Gravitre Workflow E2E%'
  OR c.title ILIKE '%retrieval-ab%'
  OR c.title ILIKE '%wave67%'
  OR c.title ILIKE 'gravitre-%'
  OR c.title ILIKE 'CanvasGovProbe%'
  OR c.title ILIKE 'PartD-%'
  OR c.title ILIKE '%spotcheck%'
  OR c.title ILIKE 'STA322%'
  OR c.title ILIKE 'STA305%'
  OR c.title ILIKE '%High-intent execution-link%'
  OR c.title ILIKE '%Routing Wave Live%'
  OR c.title ILIKE '%Isolated guard verify%'
  OR c.title ~* '(perf-audit|retrieval-ab|wave67|STA-307|Workflow E2E|gravitre-(react|wave67|flake|planforce|retrieval)|claim[34]|spotcheck)'
)"""


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
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
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _fetch_candidates(client) -> list[dict]:
    """Page through non-deleted conversations and filter in Python for clarity."""
    isolated = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID.lower()
    rows: list[dict] = []
    offset = 0
    page = 1000
    while True:
        resp = (
            client.table("conversations")
            .select("id, org_id, user_id, title, message_count, created_at, deleted_at, task_state")
            .is_("deleted_at", "null")
            .order("created_at", desc=False)
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page

    # Message presence: batch query conversation_messages for candidate empty shells
    empty_ids = [
        str(r["id"])
        for r in rows
        if str(r.get("org_id") or "").lower() != isolated and int(r.get("message_count") or 0) == 0
    ]
    has_msgs: set[str] = set()
    for i in range(0, len(empty_ids), 200):
        chunk = empty_ids[i : i + 200]
        if not chunk:
            continue
        msg = (
            client.table("conversation_messages")
            .select("conversation_id")
            .in_("conversation_id", chunk)
            .execute()
        )
        for m in msg.data or []:
            has_msgs.add(str(m["conversation_id"]))

    import re

    title_re = re.compile(
        r"(perf-audit|retrieval-ab|wave67|STA-307|Workflow E2E|"
        r"gravitre-(react|wave67|flake|planforce|retrieval)|claim[34]|spotcheck|"
        r"CanvasGovProbe|High-intent execution-link|Routing Wave Live|"
        r"Isolated guard verify|PartD-|STA322|STA305)",
        re.I,
    )

    out: list[dict] = []
    for r in rows:
        org = str(r.get("org_id") or "")
        if org.lower() == isolated:
            continue
        cid = str(r["id"])
        title = str(r.get("title") or "")
        msg_count = int(r.get("message_count") or 0)
        empty = msg_count == 0 and cid not in has_msgs
        patterned = bool(title_re.search(title))
        if not empty and not patterned:
            continue
        reason = "title_pattern" if patterned else "empty_shell"
        if empty and patterned:
            reason = "empty_shell+title_pattern"
        out.append(
            {
                "id": cid,
                "org_id": org,
                "user_id": str(r.get("user_id") or ""),
                "title": title[:200],
                "message_count": msg_count,
                "has_messages": cid in has_msgs,
                "created_at": r.get("created_at"),
                "match_reason": reason,
            }
        )
    return out


def main() -> int:
    env = _load_env()
    client = _client(env)
    apply = "--apply" in sys.argv
    candidates = _fetch_candidates(client)
    now = datetime.now(timezone.utc).isoformat()

    by_org: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for c in candidates:
        by_org[c["org_id"]] = by_org.get(c["org_id"], 0) + 1
        by_reason[c["match_reason"]] = by_reason.get(c["match_reason"], 0) + 1

    report: dict = {
        "probe": "smoke_conversation_pollution_cleanup",
        "batch_tag": BATCH_TAG,
        "started_at": now,
        "isolated_org_excluded": DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
        "operator_org": FORBIDDEN_OPERATOR_ORG_ID,
        "mode": "apply" if apply else "dry_run",
        "candidate_count": len(candidates),
        "by_org": by_org,
        "by_reason": by_reason,
        "candidates": candidates,
        "soft_deleted_ids": [],
        "verify": {},
    }

    if not apply:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"DRY_RUN candidates={len(candidates)} by_org={by_org} by_reason={by_reason}")
        print(f"Wrote {OUT}")
        print("Re-run with --apply to soft-delete (set deleted_at).")
        return 0

    # Persist audit BEFORE mutate
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    deleted_ids: list[str] = []
    for i in range(0, len(candidates), 100):
        chunk = candidates[i : i + 100]
        ids = [c["id"] for c in chunk]
        # Stamp reason into task_state for forensic trail, then soft-delete.
        for c in chunk:
            prev = {}
            # best-effort merge marker
            try:
                row = (
                    client.table("conversations")
                    .select("task_state")
                    .eq("id", c["id"])
                    .limit(1)
                    .execute()
                )
                if row.data and isinstance(row.data[0].get("task_state"), dict):
                    prev = dict(row.data[0]["task_state"])
            except Exception:
                prev = {}
            prev["_smoke_pollution_cleanup"] = {
                "batch_tag": BATCH_TAG,
                "match_reason": c["match_reason"],
                "soft_deleted_at": now,
                "why": "smoke/probe/CI conversation pollution cleanup — soft-delete only",
            }
            client.table("conversations").update(
                {
                    "task_state": prev,
                    "deleted_at": now,
                    "updated_at": now,
                }
            ).eq("id", c["id"]).is_("deleted_at", "null").execute()
            deleted_ids.append(c["id"])
        print(f"soft_deleted batch {i // 100 + 1}: {len(ids)}")

    # Verify: remaining visible for Cesar org
    still = (
        client.table("conversations")
        .select("id, title, message_count")
        .eq("org_id", FORBIDDEN_OPERATOR_ORG_ID)
        .is_("deleted_at", "null")
        .execute()
    )
    remaining = still.data or []
    # Pattern / empty check on remaining
    import re

    title_re = re.compile(
        r"(perf-audit|retrieval-ab|wave67|STA-307|Workflow E2E|gravitre-|spotcheck|claim[34])",
        re.I,
    )
    residual_pattern = [r for r in remaining if title_re.search(str(r.get("title") or ""))]
    empty_remaining = [
        r for r in remaining if int(r.get("message_count") or 0) == 0
    ]
    # Confirm empty remaining truly have no messages
    empty_residual: list[dict] = []
    for r in empty_remaining:
        msgs = (
            client.table("conversation_messages")
            .select("id")
            .eq("conversation_id", r["id"])
            .limit(1)
            .execute()
        )
        if not msgs.data:
            empty_residual.append({"id": r["id"], "title": r.get("title")})

    report["soft_deleted_ids"] = deleted_ids
    report["soft_deleted_count"] = len(deleted_ids)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["verify"] = {
        "cesar_org_visible_total": len(remaining),
        "cesar_org_residual_title_pattern": len(residual_pattern),
        "cesar_org_residual_empty_shells": len(empty_residual),
        "residual_pattern_sample": residual_pattern[:10],
        "residual_empty_sample": empty_residual[:10],
        "history_panel_clean": len(residual_pattern) == 0 and len(empty_residual) == 0,
    }
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        f"APPLIED soft_deleted={len(deleted_ids)} "
        f"cesar_visible={len(remaining)} "
        f"residual_pattern={len(residual_pattern)} "
        f"residual_empty={len(empty_residual)}"
    )
    print(f"Wrote {OUT}")
    return 0 if report["verify"]["history_panel_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
