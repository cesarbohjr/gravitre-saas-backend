#!/usr/bin/env python3
"""Prod smoke: assign expert pack → refresh → persists; remove from second agent → KB remains."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = (os.environ.get("GRAVITRE_PROD_WEB_URL") or os.environ.get("PLAYWRIGHT_BASE_URL") or "").rstrip("/")
TOKEN = (os.environ.get("GRAVITRE_PROD_BEARER") or os.environ.get("SMOKE_BEARER") or "").strip()
AGENT_A = (os.environ.get("SMOKE_AGENT_A_ID") or "").strip()
AGENT_B = (os.environ.get("SMOKE_AGENT_B_ID") or "").strip()
PACK_ID = (os.environ.get("SMOKE_EXPERT_PACK_ID") or "pack.sales-playbook").strip()
SOURCE_ID = (os.environ.get("SMOKE_RAG_SOURCE_ID") or "").strip()


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {"error": exc.reason}
        except json.JSONDecodeError:
            payload = {"error": raw or exc.reason}
        return exc.code, payload


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    if not BASE or not TOKEN or not AGENT_A:
        print(
            "NOT RUN — set GRAVITRE_PROD_WEB_URL, GRAVITRE_PROD_BEARER, SMOKE_AGENT_A_ID "
            "(optional SMOKE_AGENT_B_ID, SMOKE_RAG_SOURCE_ID, SMOKE_EXPERT_PACK_ID)",
            file=sys.stderr,
        )
        return 2

    print(f"[{_stamp()}] Agent knowledge prod verify against {BASE}")

    status, listed = _request("GET", f"/api/agents/{AGENT_A}/knowledge-assignments")
    if status >= 400:
        print(f"FAIL list assignments HTTP {status}: {listed}", file=sys.stderr)
        return 1

    before_ids = {str(a.get("sourceId")) for a in listed.get("assignments") or []}

    status, created = _request(
        "POST",
        f"/api/agents/{AGENT_A}/knowledge-assignments",
        {
            "sourceType": "knowledge_pack",
            "sourceId": PACK_ID,
            "label": f"Smoke pack {PACK_ID}",
            "enabled": True,
            "metadata": {"fabric_pack": True},
        },
    )
    if status >= 400 and PACK_ID not in before_ids:
        print(f"FAIL assign pack HTTP {status}: {created}", file=sys.stderr)
        return 1

    status, after_assign = _request("GET", f"/api/agents/{AGENT_A}/knowledge-assignments")
    after_ids = {str(a.get("sourceId")) for a in after_assign.get("assignments") or []}
    if PACK_ID not in after_ids:
        print("FAIL pack missing after assign + refresh", file=sys.stderr)
        return 1
    print(f"PASS — pack {PACK_ID} assigned @ {_stamp()}")

    assignment_id = next(
        (str(a.get("id")) for a in after_assign.get("assignments") or [] if str(a.get("sourceId")) == PACK_ID),
        "",
    )

    if AGENT_B and SOURCE_ID:
        status, _ = _request(
            "POST",
            f"/api/agents/{AGENT_B}/knowledge-assignments",
            {
                "sourceType": "rag_source",
                "sourceId": SOURCE_ID,
                "label": "Smoke org KB",
                "enabled": True,
            },
        )
        if status >= 400:
            print(f"FAIL assign org source to agent B HTTP {status}", file=sys.stderr)
            return 1

        _, b_assignments = _request("GET", f"/api/agents/{AGENT_B}/knowledge-assignments")
        b_row = next(
            (a for a in b_assignments.get("assignments") or [] if str(a.get("sourceId")) == SOURCE_ID),
            None,
        )
        if not b_row or not b_row.get("id"):
            print("FAIL agent B assignment missing", file=sys.stderr)
            return 1

        status, _ = _request("DELETE", f"/api/agents/{AGENT_B}/knowledge-assignments/{b_row['id']}")
        if status >= 400:
            print(f"FAIL remove from agent B HTTP {status}", file=sys.stderr)
            return 1

        status, source_check = _request("GET", f"/api/sources/{SOURCE_ID}")
        if status >= 400:
            print(f"FAIL org source deleted after unassign HTTP {status}", file=sys.stderr)
            return 1
        print(f"PASS — rag_source {SOURCE_ID} still present after agent B unassign @ {_stamp()}")

    if assignment_id:
        status, _ = _request("DELETE", f"/api/agents/{AGENT_A}/knowledge-assignments/{assignment_id}")
        if status >= 400:
            print(f"WARN cleanup delete failed HTTP {status}", file=sys.stderr)

    print(f"PASS — agent knowledge assign/remove prod verify @ {_stamp()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
