"""How often does the conversational turn gate actually defer to its model?

Site 8 (conversational_turn_gate.py:240) is dormant, but unlike the earlier
sites its model only runs when heuristic_turn_shape returns None. So the honest
severity depends entirely on how much REAL traffic the heuristic declines to
classify — a question answerable offline, against real production messages,
before changing any code.

This runs the real heuristic (no model, no network) over real user messages and
reports the deferral rate plus the shapes the heuristic does assign. The
deferred bucket is exactly the set of turns whose classification has been
decided by the dormant call's fail-closed default (task_shaped) rather than by
the model that was supposed to decide it.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "turn-gate-reach.json"
DAYS = 30
SAMPLE_LIMIT = 4000


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if p.exists():
            merged.update({k: v for k, v in dotenv_values(p).items() if v})
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if merged.get(key):
            os.environ.setdefault(key, merged[key])
    return merged


def main() -> int:
    env = load_env()
    sys.path.insert(0, str(ROOT / "backend"))
    for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        if env.get(key):
            os.environ.setdefault(key, env[key])

    from supabase import create_client

    from app.services.conversational_turn_gate import heuristic_turn_shape

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).isoformat()

    rows = (
        sb.table("conversation_messages")
        .select("content,created_at")
        .eq("role", "user")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(SAMPLE_LIMIT)
        .execute()
        .data
        or []
    )

    reasons: Counter[str] = Counter()
    shapes: Counter[str] = Counter()
    deferred: list[str] = []
    considered = 0

    for row in rows:
        text = (row.get("content") or "").strip()
        if not text:
            continue
        considered += 1
        decision = heuristic_turn_shape(text)
        if decision is None:
            reasons["DEFERRED_TO_MODEL"] += 1
            if len(deferred) < 40:
                deferred.append(text[:180])
            continue
        reasons[decision.reason] += 1
        shapes[decision.shape] += 1

    deferrals = reasons["DEFERRED_TO_MODEL"]
    rate = (deferrals / considered * 100) if considered else 0.0

    payload = {
        "window_days": DAYS,
        "user_messages_considered": considered,
        "deferred_to_model": deferrals,
        "deferral_rate_pct": round(rate, 2),
        "heuristic_reasons": dict(reasons.most_common()),
        "heuristic_shapes": dict(shapes.most_common()),
        "heuristic_mixed_count": shapes.get("mixed", 0),
        "deferred_examples": deferred,
        "note": (
            "Deferred turns are the ones the dormant model call decided by its "
            "fail-closed default (task_shaped). heuristic_mixed_count is how "
            "often the mixed social-ack path fires WITHOUT needing the model."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"user messages considered : {considered}")
    print(f"deferred to model        : {deferrals} ({rate:.2f}%)")
    print(f"heuristic mixed          : {shapes.get('mixed', 0)}")
    print("top heuristic reasons:")
    for reason, count in reasons.most_common(10):
        print(f"   {count:6d}  {reason}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
