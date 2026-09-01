"""Why did the rewriter record zero if the classical region runs every day?

probe_classical_region_reach proved the region IS entered on real traffic (606
post-region ReAct iterations in 30 days, including today). Reaching the ReAct
call at agent_intelligence.py:3221 requires executing the region entry at :2608,
and both sit inside execute_task_streaming (1382-3844) with no function boundary
between them.

So the rewriter's zero events have only two possible explanations left:
  (a) deploy timing — no real post-region turn happened after the instrument
      went live, or
  (b) mode_key == "fast" on those turns, which skips the rewriter while still
      entering the region.

These are distinguishable right now from existing data: compare the timestamps
of post-region ReAct activity against when the instrument went live.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import fetch_all, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "rewriter-zero-explained.json"
REWRITER_COMMIT = "f8fb93d6"


def commit_time(sha: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "show", "-s", "--format=%cI", sha],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    ct = commit_time(REWRITER_COMMIT)
    print(f"rewriter instrument commit {REWRITER_COMMIT} authored/committed: {ct}")

    iters = fetch_all(sb, "agent.react.iteration", since, "created_at,resource_type,metadata")
    streaming = [r for r in iters if str(r.get("resource_type") or "") == "assistant"]
    streaming.sort(key=lambda r: str(r.get("created_at") or ""))

    after = [r for r in streaming if ct and str(r.get("created_at") or "") >= ct]
    print(f"\npost-region ReAct iterations total (30d): {len(streaming)}")
    print(f"post-region ReAct iterations AFTER instrument went live: {len(after)}")
    if streaming:
        print(f"  earliest: {streaming[0].get('created_at')}")
        print(f"  latest:   {streaming[-1].get('created_at')}")

    # Did either instrument ever fire?
    rew = fetch_all(sb, "retrieval.query.rewritten", since, "created_at,metadata")
    reached = fetch_all(sb, "classical.answer_path.reached", since, "created_at,metadata")
    ground = fetch_all(sb, "answer.grounding.validated", since, "created_at,metadata")
    print(f"\nretrieval.query.rewritten events:      {len(rew)}")
    print(f"classical.answer_path.reached events:  {len(reached)}  (not deployed yet)")
    print(f"answer.grounding.validated events:     {len(ground)}")

    if after and not rew:
        verdict = (
            "mode_key=='fast' (or equivalent skip) — the region ran after the "
            "instrument went live, yet the rewriter branch never did"
        )
    elif not after:
        verdict = (
            "deploy timing — no real post-region turn occurred after the "
            "instrument went live, so zero events proves nothing yet"
        )
    else:
        verdict = "rewriter fired; earlier UNREACHED reading was incomplete"

    print(f"\nVERDICT: {verdict}")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "instrument_commit": REWRITER_COMMIT,
                "instrument_commit_time": ct,
                "post_region_iterations_30d": len(streaming),
                "post_region_iterations_after_instrument": len(after),
                "earliest": streaming[0].get("created_at") if streaming else None,
                "latest": streaming[-1].get("created_at") if streaming else None,
                "retrieval_query_rewritten": len(rew),
                "classical_answer_path_reached": len(reached),
                "answer_grounding_validated": len(ground),
                "verdict": verdict,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
