"""Real, current latency of the grounding validator on the deployed tip.

Cesar's decision was to include agent mode, with the latency measured before
making it final. ai_pipeline_latency held exactly one `validation` row in 30
days, at 0ms, so there was no history to read: the mode gate had made the
validator unreachable for every connector-connected org.

This reads `answer.grounding.validated` after live turns have been driven
through the classical answer path, and reports both branches:

  skipped=True  -> mode gate passed but the turn had no retrieved context, so
                   there is nothing to ground against and no model call is paid
                   for. This is the has_context guard, and its rate is the real
                   answer to "how often does including agent mode cost anything".
  skipped absent -> the validator genuinely ran; durationMs is the added latency.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

from supabase import create_client  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "grounding-validator-latency.json"


def _pct(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * q), len(ordered) - 1)]


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()

    rows = (
        sb.table("audit_events")
        .select("created_at,metadata")
        .eq("action", "answer.grounding.validated")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )

    ran: list[dict] = []
    skipped: list[dict] = []
    for r in rows:
        md = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        (skipped if md.get("skipped") else ran).append({**md, "created_at": r.get("created_at")})

    durations = [int(e["durationMs"]) for e in ran if isinstance(e.get("durationMs"), (int, float))]

    print(f"=== answer.grounding.validated (last 3h, tip 1e94e644) ===")
    print(f"total events           : {len(rows)}")
    print(f"  validator ran        : {len(ran)}")
    print(f"  skipped (no context) : {len(skipped)}")

    if durations:
        print("\nlatency of the validator itself, on the real path:")
        print(f"  n    = {len(durations)}")
        print(f"  p50  = {_pct(durations, 0.50)} ms")
        print(f"  p95  = {_pct(durations, 0.95)} ms")
        print(f"  max  = {max(durations)} ms")
        print(f"  mean = {round(sum(durations) / len(durations))} ms")

    if ran:
        print("\nper-run detail:")
        for e in ran[:12]:
            print(
                f"  {e.get('created_at','')[:19]}  mode={e.get('modeKey'):<9} "
                f"{e.get('durationMs')}ms  valid={e.get('isValid')} "
                f"assessorRan={e.get('assessorRan')} sources={e.get('ragSourceCount')} "
                f"replaced={e.get('answerReplaced')} issues={e.get('issues')}"
            )

    if skipped:
        print("\nskipped detail (mode gate passed, no retrieved context):")
        for e in skipped[:8]:
            print(f"  {e.get('created_at','')[:19]}  mode={e.get('modeKey')}  reason={e.get('skipReason')}")

    replaced = [e for e in ran if e.get("answerReplaced")]
    print(f"\nanswers replaced by the validator: {len(replaced)} of {len(ran)}")
    if replaced:
        print("  ^ user-visible behaviour change; review before leaving enabled")

    verdict = "NO EVENTS"
    if ran:
        verdict = f"MEASURED p50={_pct(durations,0.50)}ms p95={_pct(durations,0.95)}ms over n={len(durations)}"
    elif skipped:
        verdict = (
            f"MODE GATE OPEN, {len(skipped)} turn(s) skipped for no retrieved context "
            "— agent mode now enters the validator but pays nothing without RAG sources"
        )
    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "tip": "1e94e644",
                "window_hours": 3,
                "events_total": len(rows),
                "validator_ran": len(ran),
                "skipped_no_context": len(skipped),
                "durations_ms": durations,
                "p50_ms": _pct(durations, 0.50),
                "p95_ms": _pct(durations, 0.95),
                "answers_replaced": len(replaced),
                "ran_detail": ran[:20],
                "skipped_detail": skipped[:20],
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
