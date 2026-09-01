"""Is the HubSpot deals-search validation error intermittent, or input-shaped?

Observed once during unrelated verification: the same read query that normally
returns a deals table instead returned "Invalid parameters for this Hubspot
action (Search deals via hubspot API)". One failure in four looks like a race or
a flaky upstream, but limited sampling is exactly how an input-correlated bug
disguises itself as intermittent.

This reads the recorded tool invocations rather than guessing: if the failures
carry different arguments than the successes, it is input-shaped; if the
arguments are identical across both, it is genuinely non-deterministic.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "hubspot-deals-search-validation-probe.json"


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    return merged


def fetch(sb, action: str, since: str) -> list[dict]:
    rows: list[dict] = []
    off = 0
    while True:
        page = (
            sb.table("audit_events")
            .select("created_at,action,metadata")
            .eq("action", action)
            .gte("created_at", since)
            .range(off, off + 999)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < 1000:
            return rows
        off += 1000


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

    # Find which invoke actions exist at all, so this does not assume a name.
    actions = Counter()
    for act in (
        "tool.invoke.completed",
        "tool.invoke.failed",
        "tool.invoke.error",
        "tool.invoke.started",
    ):
        rows = fetch(sb, act, since)
        actions[act] = len(rows)
    print("tool invoke audit volume (3d):", dict(actions))

    deals: list[dict] = []
    for act in ("tool.invoke.completed", "tool.invoke.failed", "tool.invoke.error"):
        for row in fetch(sb, act, since):
            meta = row.get("metadata") or {}
            blob = json.dumps(meta).lower()
            if "deal" not in blob or "hubspot" not in blob:
                continue
            deals.append({"audit_action": act, "created_at": row["created_at"], "metadata": meta})

    print(f"\nhubspot deal-related tool invocations (3d): {len(deals)}")
    if not deals:
        print("  none recorded — the tool layer may not audit this path")

    ok: list[dict] = []
    bad: list[dict] = []
    for d in deals:
        meta = d["metadata"]
        blob = json.dumps(meta).lower()
        failed = (
            d["audit_action"] != "tool.invoke.completed"
            or "invalid parameter" in blob
            or "validation" in blob
            or str(meta.get("status") or "").lower() in {"error", "failed"}
        )
        (bad if failed else ok).append(d)

    print(f"  succeeded: {len(ok)}   failed: {len(bad)}")

    def arg_shapes(rows: list[dict]) -> Counter:
        shapes: Counter = Counter()
        for r in rows:
            meta = r["metadata"]
            args = (
                meta.get("arguments")
                or meta.get("args")
                or meta.get("tool_arguments")
                or meta.get("parameters")
                or {}
            )
            if isinstance(args, dict):
                shapes[tuple(sorted(args.keys())) or ("<empty>",)] += 1
            else:
                shapes[("<non-dict>",)] += 1
        return shapes

    print("\nargument key shapes — SUCCESS:")
    for shape, n in arg_shapes(ok).most_common(10):
        print(f"  {n:4}  {list(shape)}")
    print("argument key shapes — FAILURE:")
    for shape, n in arg_shapes(bad).most_common(10):
        print(f"  {n:4}  {list(shape)}")

    print("\nfailure samples:")
    for d in bad[:4]:
        meta = d["metadata"]
        args = meta.get("arguments") or meta.get("args") or meta.get("tool_arguments") or {}
        print(f"  {d['created_at']} tool={meta.get('tool_name') or meta.get('tool')}")
        print(f"    args={json.dumps(args)[:300]}")
        print(f"    error={str(meta.get('error') or meta.get('message') or '')[:200]}")

    print("\nsuccess samples:")
    for d in ok[:3]:
        meta = d["metadata"]
        args = meta.get("arguments") or meta.get("args") or meta.get("tool_arguments") or {}
        print(f"  {d['created_at']} tool={meta.get('tool_name') or meta.get('tool')}")
        print(f"    args={json.dumps(args)[:300]}")

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window_days": 3,
        "audit_volume": dict(actions),
        "deal_invocations": len(deals),
        "succeeded": len(ok),
        "failed": len(bad),
        "success_arg_shapes": {str(list(k)): v for k, v in arg_shapes(ok).items()},
        "failure_arg_shapes": {str(list(k)): v for k, v in arg_shapes(bad).items()},
        "failures": bad[:20],
        "successes": ok[:10],
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
