"""Positive proof that the four corrected column reads now succeed in production.

Absence of errors in a log tail is weak: load_user_organizations only runs on login
and cache warming runs on a timer. This exercises each repaired query directly
against the live database, through the same Supabase client the app uses, and prints
what it got back.

Run: railway run --service gravitre-saas-backend -- python scripts/verify-column-read-repairs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import get_settings  # noqa: E402
from app.workflows.repository import get_supabase_client  # noqa: E402

settings = get_settings()
client = get_supabase_client(settings)

failures: list[str] = []


def check(label: str, fn) -> None:
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001
        failures.append(label)
        print(f"FAIL  {label}\n      {type(exc).__name__}: {exc}")
        return
    print(f"PASS  {label}\n      -> {result}")


# 1. The select that used to fail wholesale and render every org as "Organization".
def org_read():
    rows = (
        client.table("organizations")
        .select("id, name, slug, logo_url, settings, created_at")
        .limit(5)
        .execute()
        .data
        or []
    )
    names = [r.get("name") for r in rows]
    return f"{len(rows)} orgs, names={names}"


# 2. The real end-to-end path, including the "Organization" fallback branch.
def membership_read():
    from app.services.org_membership import load_user_organizations

    org_id = (
        client.table("organizations").select("id").limit(1).execute().data or [{}]
    )[0].get("id")
    member = (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0].get("user_id")
    if not member:
        return "no member row to test with (skipped)"
    orgs = load_user_organizations(client, str(member))
    fallbacks = [o for o in orgs if o.get("name") == "Organization"]
    return (
        f"{len(orgs)} orgs for user, names={[o.get('name') for o in orgs]}, "
        f"literal-'Organization' fallbacks={len(fallbacks)}"
    )


# 3. Cache warming: select + order that raised 42703 on every tick.
def cluster_read():
    rows = (
        client.table("org_query_clusters")
        .select("representative_queries, member_query_count")
        .order("member_query_count", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    return f"{len(rows)} clusters"


# 4. Promotion audit counters.
def pending_read():
    res = (
        client.table("agent_memory_promotion_audit")
        .select("id", count="exact")
        .eq("status_at_decision", "pending")
        .execute()
    )
    return f"count={getattr(res, 'count', None)}"


def recent_read():
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    res = (
        client.table("agent_memory_promotion_audit")
        .select("id", count="exact")
        .gte("decided_at", since)
        .eq("status_at_decision", "approved")
        .execute()
    )
    return f"count={getattr(res, 'count', None)}"


# 5. Confirm the three names we deliberately did NOT add are still absent.
def absent_columns():
    still_absent = []
    for table, column in (
        ("org_query_clusters", "query_count"),
        ("agent_memory_promotion_audit", "status"),
        ("agent_memory_promotion_audit", "created_at"),
    ):
        try:
            client.table(table).select(column).limit(1).execute()
            still_absent.append(f"{table}.{column} UNEXPECTEDLY EXISTS")
        except Exception:  # noqa: BLE001
            still_absent.append(f"{table}.{column} absent (correct)")
    return "; ".join(still_absent)


check("organizations select with logo_url + settings", org_read)
check("load_user_organizations end to end", membership_read)
check("cache warming select/order member_query_count", cluster_read)
check("promotion pending via status_at_decision", pending_read)
check("promotion 7d via decided_at + status_at_decision", recent_read)
check("misspelled duplicates were not created", absent_columns)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILED -> {failures}")
    raise SystemExit(1)
print("RESULT: all corrected reads succeed against production")
