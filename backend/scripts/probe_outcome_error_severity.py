"""Severity split for outcome_error: real customer traffic vs the audit's own probes.

The first trace found 140 of 142 events in org f07e57c0, which is the isolated
conversation org this audit's own verification scripts use. That would make most
of the "28% of fallthroughs failing" self-inflicted, so it has to be separated
before the finding is given a severity.

Also resolves whether the 6 turns that got no assistant reply were real users.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

from supabase import create_client  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "outcome-error-severity.json"

PROBE_ORG_PREFIXES = ("f07e57c0", "00000000")


def error_class(err: str) -> str:
    e = (err or "").strip()
    if "unnarrowed_tool_attach_blocked" in e:
        return "unnarrowed_tool_attach_blocked (internal invariant guard)"
    if "tool_choice" in e:
        return "400 invalid tool_choice (API contract bug)"
    if "Error code: 429" in e or "Rate limit" in e:
        return "429 provider rate limit (environmental)"
    if "Error code: 404" in e:
        return "404 provider"
    if "Error code: 400" in e:
        return "400 other"
    return e[:70] or "(empty)"


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    rows = (
        sb.table("audit_events")
        .select("created_at,org_id,metadata,resource_id")
        .eq("action", "unified_turn.live.fallthrough")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(4000)
        .execute()
        .data
        or []
    )
    errs = [
        {
            "created_at": str(r.get("created_at") or ""),
            "org_id": str(r.get("org_id") or ""),
            "conversation_id": r.get("resource_id"),
            "error": str((r.get("metadata") or {}).get("error") or ""),
        }
        for r in rows
        if str((r.get("metadata") or {}).get("fallthrough_reason") or "") == "outcome_error"
    ]

    def is_probe(org: str) -> bool:
        return org.startswith(PROBE_ORG_PREFIXES)

    real = [e for e in errs if not is_probe(e["org_id"])]
    probe = [e for e in errs if is_probe(e["org_id"])]

    print(f"=== outcome_error, 30d (n={len(errs)}) ===")
    print(f"  audit's own probe orgs : {len(probe)}")
    print(f"  REAL customer orgs     : {len(real)}")

    print("\n=== error class x traffic source ===")
    grid: dict[str, Counter[str]] = defaultdict(Counter)
    for e in errs:
        grid[error_class(e["error"])]["probe" if is_probe(e["org_id"]) else "real"] += 1
    print(f"  {'class':58s} {'probe':>6s} {'real':>6s}")
    for cls, c in sorted(grid.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"  {cls:58s} {c['probe']:6d} {c['real']:6d}")

    print("\n=== real-customer events in full ===")
    for e in real:
        print(f"  {e['created_at'][:19]}  org={e['org_id'][:8]}  conv={str(e['conversation_id'])[:8]}")
        print(f"     {e['error'][:150]}")

    print("\n=== date distribution (is this ongoing or historical?) ===")
    by_day: dict[str, Counter[str]] = defaultdict(Counter)
    for e in errs:
        by_day[e["created_at"][:10]][error_class(e["error"])] += 1
    for day in sorted(by_day, reverse=True):
        total = sum(by_day[day].values())
        top = by_day[day].most_common(1)[0]
        print(f"  {day}  n={total:4d}  top={top[1]:4d} {top[0][:52]}")

    # Is the dominant internal guard still firing recently?
    guard = [e for e in errs if "unnarrowed_tool_attach_blocked" in e["error"]]
    guard_days = sorted({e["created_at"][:10] for e in guard})
    tool_choice = [e for e in errs if "tool_choice" in e["error"]]
    tc_days = sorted({e["created_at"][:10] for e in tool_choice})
    print(f"\nunnarrowed_tool_attach_blocked: n={len(guard)}  days={guard_days[:3]}..{guard_days[-3:]}")
    print(f"400 invalid tool_choice       : n={len(tool_choice)}  days={tc_days}")

    # The unanswered turns: real users or probes?
    print("\n=== turns with no assistant reply: whose? ===")
    unanswered: list[dict[str, Any]] = []
    for e in errs[:120]:
        if not e["conversation_id"]:
            continue
        try:
            msgs = (
                sb.table("conversation_messages")
                .select("role")
                .eq("conversation_id", e["conversation_id"])
                .gte("created_at", e["created_at"])
                .limit(6)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            break
        if not [m for m in msgs if str(m.get("role")) == "assistant"]:
            unanswered.append(e)
    u_real = [e for e in unanswered if not is_probe(e["org_id"])]
    print(f"  unanswered sampled : {len(unanswered)}")
    print(f"    of probe orgs    : {len(unanswered) - len(u_real)}")
    print(f"    of REAL orgs     : {len(u_real)}")
    for e in u_real[:10]:
        print(f"      {e['created_at'][:19]} org={e['org_id'][:8]} {e['error'][:90]}")

    verdict = (
        f"{len(errs)} outcome_error turns in 30d, of which {len(real)} are from real "
        f"customer orgs and {len(probe)} from this audit's own probe orgs. "
        f"{len(u_real)} real-customer turns had no assistant reply."
    )
    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "outcome_error_total": len(errs),
                "probe_org_events": len(probe),
                "real_org_events": len(real),
                "class_by_source": {k: dict(v) for k, v in grid.items()},
                "real_events": real,
                "guard_days": guard_days,
                "tool_choice_days": tc_days,
                "unanswered_sampled": len(unanswered),
                "unanswered_real": u_real,
                "by_day": {k: dict(v) for k, v in by_day.items()},
                "verdict": verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
