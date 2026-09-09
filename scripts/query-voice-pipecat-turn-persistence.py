#!/usr/bin/env python3
"""Check whether Pipecat voice turns persist the user's utterance.

Context: the live probe (scripts/verify-voice-phase5-live.py) found that the
client never receives a ``{"type": "transcript", "final": true}`` message on the
Pipecat path, so the frontend's ``onUserFinal`` never fires. That leaves an open
question with real blast radius: is the user's spoken message still written to
``conversation_messages`` server-side, or is the turn stored assistant-only?

This reads back the probe's conversation ids and reports the role sequence.

Credentials from the environment only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

Usage:
  python scripts/query-voice-pipecat-turn-persistence.py [probe_json_path]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PROBE = REPO / "docs" / "delivery" / "voice-phase5-live-verification-2026-09-08.json"


def _ascii(text: str, limit: int = 80) -> str:
    return text[:limit].encode("ascii", "replace").decode("ascii")


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    probe_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PROBE
    rows = json.loads(probe_path.read_text(encoding="utf-8"))
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    verdicts: list[str] = []
    for row in rows:
        cid = row.get("conversation_id") or ""
        label = row.get("label") or "?"
        resp = httpx.get(
            f"{url}/rest/v1/conversation_messages",
            params={
                "conversation_id": f"eq.{cid}",
                "select": "role,content,created_at",
                "order": "created_at.asc",
            },
            headers=headers,
            timeout=30.0,
        )
        print(f"--- {label}  conversation_id={cid}  http={resp.status_code}", flush=True)
        if resp.status_code != 200:
            print(f"    error: {_ascii(resp.text, 200)}", flush=True)
            verdicts.append(f"{label}=http_{resp.status_code}")
            continue
        msgs = resp.json()
        roles = [str(m.get("role") or "") for m in msgs]
        print(f"    n_msgs={len(msgs)} roles={roles}", flush=True)
        for m in msgs:
            content = str(m.get("content") or "")
            print(
                f"      {m.get('role')} | {len(content)} chars | {_ascii(content)}",
                flush=True,
            )
        verdicts.append(f"{label}={'user_present' if 'user' in roles else 'NO_USER_ROW'}")

    print("\nVERDICT: " + "; ".join(verdicts), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
