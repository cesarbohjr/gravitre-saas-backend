"""Can connector health events be attributed to a real, named actor?

The health sweep runs with no user, so both of its audit writes passed
actor_id=None and were silently dropped by write_audit_event. `created_by` on
the connector row is the person who connected it, which is a real named actor
and semantically the right one to attribute "your connector's auth failed" to.
This measures whether that column is actually populated before relying on it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

from supabase import create_client  # noqa: E402


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    rows = (
        sb.table("connectors")
        .select("id,created_by,status,deleted_at,type,org_id")
        .limit(5000)
        .execute()
        .data
        or []
    )
    live = [r for r in rows if not r.get("deleted_at")]
    with_actor = [r for r in live if r.get("created_by")]
    without = [r for r in live if not r.get("created_by")]

    print(f"connectors total          : {len(rows)}")
    print(f"live (not soft-deleted)   : {len(live)}")
    print(f"  live with created_by    : {len(with_actor)}")
    print(f"  live missing created_by : {len(without)}")
    if without:
        print("\nmissing created_by (need a fallback actor):")
        for r in without[:15]:
            print(f"   {r.get('id')}  type={r.get('type')}  org={r.get('org_id')}")

    # Would the fallback ever be needed for the events that actually fire? Those
    # only fire on a status CHANGE, so restrict to connectors that can change.
    changeable = [r for r in live if str(r.get("status") or "") in
                  {"active", "healthy", "error", "pending_auth", "connected"}]
    ch_missing = [r for r in changeable if not r.get("created_by")]
    print(f"\nstatus-changeable live connectors : {len(changeable)}")
    print(f"  of those missing created_by      : {len(ch_missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
