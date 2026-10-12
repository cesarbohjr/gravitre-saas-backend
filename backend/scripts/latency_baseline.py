"""Capture or check the chat and voice latency baseline (read-only).

Capture a fresh baseline from the last N days of production turn traces:

    python scripts/latency_baseline.py capture --days 7 --out baseline.json

Gate a change (for example after switching on the indexing pilot) against it;
exits 1 when p50 or p95 of either surface regressed by more than --max-pct:

    python scripts/latency_baseline.py check --baseline baseline.json --days 1

``--input traces.jsonl`` reads payloads from a file instead of the database.
Only SELECTs ``audit_events``.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.latency_baseline import compare, summarize
from app.services.turn_latency_trace import AUDIT_ACTION

PAGE_SIZE = 1000


def fetch(client: Any, *, start: datetime, end: datetime, org_id: str | None, limit: int = 50_000) -> list[dict]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while len(rows) < limit:
        q = (
            client.table("audit_events")
            .select("metadata,created_at")
            .eq("action", AUDIT_ACTION)
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
        )
        if org_id:
            q = q.eq("org_id", org_id)
        page = q.order("created_at").range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(r.get("metadata") or {} for r in page if isinstance(r, dict))
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows[:limit]


def _payloads(args: argparse.Namespace) -> tuple[list[dict], dict[str, str]]:
    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()], {"source": args.input}
    from supabase import create_client

    from app.config import get_settings
    from app.core.db import shared_service_client

    end = datetime.now(UTC)
    start = end - timedelta(days=float(args.days))
    client = shared_service_client(get_settings(), create_client)
    return fetch(client, start=start, end=end, org_id=args.org), {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "org": args.org or "all",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("capture", "check"):
        p = sub.add_parser(name)
        p.add_argument("--days", default="7")
        p.add_argument("--org")
        p.add_argument("--input")
        if name == "capture":
            p.add_argument("--out", required=True)
        else:
            p.add_argument("--baseline", required=True)
            p.add_argument("--max-pct", type=float, default=10.0)
    args = parser.parse_args(argv)

    payloads, window = _payloads(args)
    summary = summarize(payloads)
    if args.cmd == "capture":
        Path(args.out).write_text(json.dumps({"window": window, **summary}, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0
    baseline = json.loads(Path(args.baseline).read_text())
    rows = compare(summary, baseline, max_regression_pct=args.max_pct)
    for r in rows:
        print(
            f"{r['surface']:<6} {r['pct']:<4} baseline={r.get('baseline')} current={r.get('current')} "
            f"change={r.get('change_pct', '-')}% {r['verdict']}"
        )
    return 1 if any(r["verdict"] == "regressed" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
