"""Is the classical retrieval-and-answer region actually reached by real traffic?

Two instruments inside that region (the grounding validator and the query
rewriter) both recorded zero events, which suggested the region might be dead.
Zero events from instruments sitting *inside* a region cannot distinguish "never
entered" from "entered, but that specific branch skipped" — and both instruments
went live only recently, so they carry no history.

conversation_messages does not persist the terminal `model` label, so turns
cannot be attributed retroactively that way. What does have 30 days of history is
agent.react.iteration, and it carries a clean discriminator:

  - agent_intelligence.py:3221 (ReActEngine.run_streaming) is the ONLY caller of
    run_streaming, sits at :3221 — well past the region entry at :2608 — and
    passes audit_resource_type="assistant".
  - agent_intelligence.py:1293 (ReActEngine.run) is in the separate non-streaming
    execute_task, and passes "workflow_run" or "agent_job".

So agent.react.iteration rows with resource_type="assistant" are proof the
classical region was entered, on real traffic, historically. Counting them by
resource_type answers the dead-path question directly.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "classical-region-reach.json"

# resource_type values passed by each ReAct call site.
STREAMING_RESOURCE_TYPE = "assistant"  # agent_intelligence.py:3230 -> post-region
NONSTREAMING_RESOURCE_TYPES = {"workflow_run", "agent_job"}  # :1302 -> other entry point


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
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    return merged


def fetch_all(sb, action: str, since: str, select: str) -> list[dict]:
    rows: list[dict] = []
    page = 0
    while True:
        chunk = (
            sb.table("audit_events")
            .select(select)
            .eq("action", action)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .range(page * 1000, page * 1000 + 999)
            .execute()
            .data
            or []
        )
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        page += 1
        if page > 20:
            break
    return rows


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    iters = fetch_all(sb, "agent.react.iteration", since, "created_at,resource_type,resource_id,metadata")
    by_rt = Counter(str(r.get("resource_type") or "(none)") for r in iters)

    print(f"agent.react.iteration events in 30d: {len(iters)}\n")
    print("=== by resource_type (the call-site discriminator) ===")
    for rt, n in by_rt.most_common():
        if rt == STREAMING_RESOURCE_TYPE:
            tag = "POST-REGION (execute_task_streaming :3221)"
        elif rt in NONSTREAMING_RESOURCE_TYPES:
            tag = "other entry point (execute_task :1293)"
        else:
            tag = "unattributed"
        print(f"  {n:6d}  {rt:16s}  {tag}")

    streaming = [r for r in iters if str(r.get("resource_type") or "") == STREAMING_RESOURCE_TYPE]

    # Distinct turns, not raw iterations: one turn emits several iteration rows.
    turns: set[tuple[str, str]] = set()
    for r in streaming:
        md = r.get("metadata") or {}
        turns.add((str(md.get("taskId") or ""), str(r.get("resource_id") or "")))

    # Daily spread, to confirm this is ongoing traffic and not one old burst.
    per_day = Counter(str(r.get("created_at") or "")[:10] for r in streaming)

    print(f"\ndistinct post-region turns (by taskId): {len(turns)}")
    print("\n=== post-region react activity per day ===")
    for day in sorted(per_day):
        print(f"  {day}  {per_day[day]:5d}")

    fts = fetch_all(sb, "unified_turn.live.fallthrough", since, "created_at,metadata")
    reasons = Counter(
        str((r.get("metadata") or {}).get("fallthroughReason")
            or (r.get("metadata") or {}).get("fallthrough_reason")
            or "(none)")
        for r in fts
    )
    print(f"\n=== fallthrough reasons (n={len(fts)}) ===")
    for reason, n in reasons.most_common():
        print(f"  {n:6d}  {reason}")

    verdict = (
        "REGION ALIVE — real traffic reaches the classical region"
        if len(streaming) > 0
        else "REGION UNREACHED in this window"
    )
    print(f"\nVERDICT: {verdict}")

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window_days": 30,
        "react_iterations_total": len(iters),
        "react_iterations_by_resource_type": dict(by_rt),
        "post_region_iterations": len(streaming),
        "post_region_distinct_turns": len(turns),
        "post_region_per_day": dict(sorted(per_day.items())),
        "fallthrough_total": len(fts),
        "fallthrough_reasons": dict(reasons.most_common()),
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
