"""Restore research_lookups allotment/overage keys on live billing_plans.

Mirrors supabase/migrations/20260811120000_restore_billing_plans_research_lookups.sql
for environments where `supabase db push` is not available in this shell.
"""
from __future__ import annotations

import json
from pathlib import Path

from supabase import create_client


def load_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return out
    text = p.read_bytes().decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


UPDATES: list[tuple[list[str], int]] = [
    (["node", "starter", "free"], 10),
    (["control", "growth"], 60),
    (["command", "scale", "enterprise"], 200),
]


def main() -> None:
    env: dict[str, str] = {}
    for path in ("backend/.env", "backend/.env.operator.local"):
        env.update(load_env(path))
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    before = (
        sb.table("billing_plans")
        .select("code,features,overage_rates")
        .in_("code", ["node", "control", "command", "enterprise"])
        .execute()
        .data
        or []
    )
    print("BEFORE", json.dumps([
        {
            "code": r["code"],
            "research_lookups_per_month": (r.get("features") or {}).get("research_lookups_per_month"),
            "research_lookup": (r.get("overage_rates") or {}).get("research_lookup"),
        }
        for r in before
    ], indent=2))

    for codes, included in UPDATES:
        rows = (
            sb.table("billing_plans")
            .select("code,features,overage_rates")
            .in_("code", codes)
            .execute()
            .data
            or []
        )
        for row in rows:
            features = dict(row.get("features") or {})
            rates = dict(row.get("overage_rates") or {})
            features["research_lookups_per_month"] = included
            rates["research_lookup"] = 0.35
            sb.table("billing_plans").update(
                {"features": features, "overage_rates": rates}
            ).eq("code", row["code"]).execute()
            print(f"UPDATED {row['code']} research_lookups_per_month={included} research_lookup=0.35")

    after = (
        sb.table("billing_plans")
        .select("code,features,overage_rates")
        .in_("code", ["node", "control", "command", "enterprise"])
        .execute()
        .data
        or []
    )
    print("AFTER", json.dumps([
        {
            "code": r["code"],
            "research_lookups_per_month": (r.get("features") or {}).get("research_lookups_per_month"),
            "voice_minutes_per_month": (r.get("features") or {}).get("voice_minutes_per_month"),
            "research_lookup": (r.get("overage_rates") or {}).get("research_lookup"),
            "voice_minute": (r.get("overage_rates") or {}).get("voice_minute"),
        }
        for r in sorted(after, key=lambda x: x["code"])
    ], indent=2))

    expected = {"node": 10, "control": 60, "command": 200, "enterprise": 200}
    bad = []
    for r in after:
        f = r.get("features") or {}
        o = r.get("overage_rates") or {}
        code = r["code"]
        if f.get("research_lookups_per_month") != expected[code]:
            bad.append((code, "research_lookups_per_month", f.get("research_lookups_per_month")))
        if float(o.get("research_lookup") or 0) != 0.35:
            bad.append((code, "research_lookup", o.get("research_lookup")))
        if f.get("voice_minutes_per_month") is None:
            bad.append((code, "voice_minutes_wiped", None))
    if bad:
        raise SystemExit(f"VERIFY_FAIL {bad}")
    print("VERIFY_PASS research keys restored; voice keys intact")


if __name__ == "__main__":
    main()
