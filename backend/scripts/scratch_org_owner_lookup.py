"""Find a real, named fallback actor for org-scoped background audit events.

connectors.created_by covers only 6 of 19 status-changeable connectors, so the
health sweep needs a second real actor rather than actor_id=None. An org owner
or admin is the honest choice: a connector auth failure is that person's to act
on. This inspects what owner/admin concept actually exists in the schema.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

from supabase import create_client  # noqa: E402

ORGS_WITH_CONNECTORS = [
    "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea",
    "28d91c1f-63e6-4c62-9eb7-519212635b64",
    "00000000-0000-0000-0000-000000000001",
]


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    for table in ("organizations", "orgs"):
        try:
            row = sb.table(table).select("*").limit(1).execute().data or []
            if row:
                print(f"=== {table} columns ===")
                for k, v in sorted(row[0].items()):
                    print(f"   {k:24s} {type(v).__name__:9s} {str(v)[:44]}")
                break
        except Exception as exc:  # noqa: BLE001
            print(f"{table}: {str(exc)[:90]}")

    for table in ("org_members", "organization_members", "memberships", "user_orgs"):
        try:
            rows = sb.table(table).select("*").limit(3).execute().data or []
            print(f"\n=== {table} ({len(rows)} sample rows) ===")
            if rows:
                for k, v in sorted(rows[0].items()):
                    print(f"   {k:24s} {type(v).__name__:9s} {str(v)[:44]}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"{table}: {str(exc)[:90]}")

    print("\n=== owner resolvable per org that actually has connectors ===")
    for org in ORGS_WITH_CONNECTORS:
        found = None
        for table, col in (
            ("org_members", "role"),
            ("organization_members", "role"),
        ):
            try:
                rows = (
                    sb.table(table)
                    .select("user_id,role")
                    .eq("org_id", org)
                    .limit(20)
                    .execute()
                    .data
                    or []
                )
                if rows:
                    ranked = sorted(
                        rows,
                        key=lambda r: {"owner": 0, "admin": 1}.get(
                            str(r.get("role") or "").lower(), 2
                        ),
                    )
                    found = (table, ranked[0])
                    break
            except Exception:  # noqa: BLE001
                continue
        print(f"  {org} -> {found}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
