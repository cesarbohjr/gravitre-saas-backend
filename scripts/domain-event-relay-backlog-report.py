#!/usr/bin/env python3
"""Read-only report of domain_event_outbox backlog and registered handlers.

Does not enable the relay or mutate rows. Requires Supabase service credentials.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))


def main() -> int:
    from app.config import get_settings
    from app.services.domain_events import domain_event_outbox_stats, handled_event_types
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    stats = domain_event_outbox_stats(client)
    pending = (
        client.table("domain_event_outbox")
        .select("event_type, attempts, created_at, event_id")
        .eq("status", "pending")
        .order("created_at")
        .limit(500)
        .execute()
        .data
        or []
    )
    report = {
        "handled_event_types": handled_event_types(),
        "stats": stats,
        "pending_sample": pending,
        "pending_count_listed": len(pending),
    }
    out = Path(__file__).resolve().parent.parent / "docs/delivery/domain-event-relay-backlog-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "pending_listed": len(pending)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
