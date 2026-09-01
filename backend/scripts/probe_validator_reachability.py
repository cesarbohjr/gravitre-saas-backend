"""Phase B — how often does a turn actually reach the grounding validator?

Two separate questions, and conflating them is what made the earlier reading
wrong:

  1. How much traffic takes the ReAct fallthrough path at all?
  2. Of the turns that take it, how many emit `answer.grounding.validated`?

A low answer to (1) would mean the validator is niche. A healthy (1) with a zero
(2) means something downstream of the fallthrough is stopping the turn before
finalize, which is a different and more interesting problem.
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
OUT = ROOT / "docs" / "delivery" / "validator-reachability.json"

FALLTHROUGH = "unified_turn.live.fallthrough"
COMPLETED = "unified_turn.live.completed"
GROUNDING = "answer.grounding.validated"


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


def count_all(sb, action: str, since: str) -> list[dict]:
    rows: list[dict] = []
    off = 0
    while True:
        page = (
            sb.table("audit_events")
            .select("created_at,metadata")
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

    windows: dict[str, dict] = {}
    for label, delta in (
        ("6h", timedelta(hours=6)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
    ):
        since = (datetime.now(timezone.utc) - delta).isoformat()
        fall = count_all(sb, FALLTHROUGH, since)
        comp = count_all(sb, COMPLETED, since)
        ground = count_all(sb, GROUNDING, since)
        total = len(fall) + len(comp)
        windows[label] = {
            "fallthrough": len(fall),
            "completed": len(comp),
            "total_turns": total,
            "fallthrough_rate_pct": round(100.0 * len(fall) / total, 1) if total else None,
            "grounding_audits": len(ground),
            "grounding_per_fallthrough_pct": (
                round(100.0 * len(ground) / len(fall), 1) if fall else None
            ),
        }
        print(
            f"{label:>4}: fallthrough={len(fall):<5} completed={len(comp):<5} "
            f"rate={windows[label]['fallthrough_rate_pct']}%  "
            f"grounding_audits={len(ground)}"
        )

    since30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    reasons: Counter = Counter()
    keys: Counter = Counter()
    for row in count_all(sb, FALLTHROUGH, since30):
        meta = row.get("metadata") or {}
        for k in meta:
            keys[k] += 1
        reasons[
            str(
                meta.get("reason")
                or meta.get("fallthroughReason")
                or meta.get("fallthrough_reason")
                or "<no reason field>"
            )
        ] += 1

    print("\nfallthrough metadata keys (30d):", dict(keys.most_common(12)))
    print("fallthrough reasons (30d):", dict(reasons.most_common(10)))

    ground30 = count_all(sb, GROUNDING, since30)
    src: Counter = Counter()
    for row in ground30:
        src[str((row.get("metadata") or {}).get("confidenceSource") or "?")] += 1
    print("grounding confidenceSource (30d):", dict(src))

    result = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "windows": windows,
        "fallthrough_metadata_keys_30d": dict(keys.most_common(20)),
        "fallthrough_reasons_30d": dict(reasons.most_common(20)),
        "grounding_confidence_source_30d": dict(src),
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
