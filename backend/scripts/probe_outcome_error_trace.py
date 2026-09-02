"""Real trace of the `outcome_error` fallthrough branch (142 of 512 turns / 30d).

Recorded as "~28% of fallthrough turns failing outright". That framing needs
checking before it is treated as a quality incident, because of where the reason
is emitted (unified_turn_reasoning_service.py:1667):

    if result.outcome_kind in {"skipped", "error"}:
        _mark_live_fallthrough(result, f"outcome_{result.outcome_kind}")

A fallthrough CONTINUES to the classical path. So `outcome_error` means the LIVE
reasoning attempt errored and classical took over — which is a real defect in
the LIVE path either way, but only a user-visible failure if the classical path
then also failed to answer.

This probe answers three separate questions, deliberately not conflated:

  1. WHAT is erroring — group the real `error` strings into classes.
  2. Did the USER still get an answer — join to conversation_messages on the
     conversation and window, and check for an assistant reply after the event.
  3. What did it COST — latency on turns that burned a failed LIVE attempt
     before starting over on classical.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

from supabase import create_client  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "outcome-error-trace.json"

# Collapse volatile detail (ids, numbers, quoted values) so real classes group.
_NOISE = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<uuid>"),
    (re.compile(r"\b\d{4,}\b"), "<num>"),
    (re.compile(r"'[^']{1,80}'"), "'<v>'"),
    (re.compile(r'"[^"]{1,80}"'), '"<v>"'),
    (re.compile(r"\s+"), " "),
]


def classify(error: str) -> str:
    text = (error or "").strip() or "(empty error field)"
    for pattern, repl in _NOISE:
        text = pattern.sub(repl, text)
    return text[:180]


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

    errs: list[dict[str, Any]] = []
    all_reasons: Counter[str] = Counter()
    for r in rows:
        md = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        reason = str(md.get("fallthrough_reason") or "")
        all_reasons[reason] += 1
        if reason == "outcome_error":
            errs.append(
                {
                    "created_at": r.get("created_at"),
                    "org_id": r.get("org_id"),
                    "conversation_id": r.get("resource_id"),
                    "error": str(md.get("error") or ""),
                    "model": md.get("model"),
                    "latency_ms": md.get("latency_ms"),
                    "outcome_kind": md.get("outcome_kind"),
                    "streamed": md.get("streamed"),
                    "user_message": str(md.get("user_message") or "")[:120],
                }
            )

    print(f"=== unified_turn.live.fallthrough, 30d (n={len(rows)}) ===")
    for reason, n in all_reasons.most_common():
        share = 100.0 * n / max(len(rows), 1)
        print(f"  {reason or '(none)':38s} {n:5d}  {share:5.1f}%")

    print(f"\n=== outcome_error detail (n={len(errs)}) ===")
    if not errs:
        print("  none in window")
        return 0

    # 1. What is erroring.
    classes: Counter[str] = Counter(classify(e["error"]) for e in errs)
    print("\nerror classes:")
    for cls, n in classes.most_common(12):
        print(f"  {n:5d}  {cls}")

    empty = [e for e in errs if not e["error"].strip()]
    print(f"\nevents with an EMPTY error field: {len(empty)} of {len(errs)}")
    if empty:
        print("  ^ the branch fired but recorded no reason; unfixable as logged")

    # 3. Cost of the wasted LIVE attempt.
    lat = [int(e["latency_ms"]) for e in errs if isinstance(e.get("latency_ms"), (int, float))]
    if lat:
        lat.sort()
        print(f"\nlatency burned before falling through (n={len(lat)}):")
        print(f"  p50={lat[len(lat)//2]}ms  p95={lat[min(int(len(lat)*0.95), len(lat)-1)]}ms  max={lat[-1]}ms")

    by_model = Counter(str(e.get("model") or "(none)") for e in errs)
    print("\nby model:")
    for m, n in by_model.most_common(8):
        print(f"  {n:5d}  {m}")

    by_org = Counter(str(e.get("org_id") or "")[:8] for e in errs)
    print(f"\ndistinct orgs affected: {len(by_org)}")
    for o, n in by_org.most_common(6):
        print(f"  {n:5d}  {o}")

    # 2. Did the user still get an answer?
    print("\n=== did the user still get an answer? ===")
    convs = [e for e in errs if e.get("conversation_id")]
    checked = 0
    answered = 0
    unanswered: list[dict[str, Any]] = []
    for e in convs[:60]:
        try:
            msgs = (
                sb.table("conversation_messages")
                .select("role,created_at,content")
                .eq("conversation_id", e["conversation_id"])
                .gte("created_at", e["created_at"])
                .order("created_at")
                .limit(6)
                .execute()
                .data
                or []
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  lookup failed: {str(exc)[:80]}")
            break
        checked += 1
        assistant = [m for m in msgs if str(m.get("role")) == "assistant"]
        if assistant:
            answered += 1
        else:
            unanswered.append({**e, "messages_after": len(msgs)})

    print(f"  conversations checked            : {checked}")
    print(f"  got an assistant reply afterwards: {answered}")
    print(f"  no assistant reply found         : {len(unanswered)}")
    if unanswered:
        print("\n  turns with no recorded assistant reply:")
        for u in unanswered[:8]:
            print(f"    {u['created_at'][:19]}  conv={str(u['conversation_id'])[:8]}  err={u['error'][:70]!r}")

    recovery = (100.0 * answered / checked) if checked else 0.0
    verdict = (
        f"{len(errs)} outcome_error turns in 30d ({100.0*len(errs)/max(len(rows),1):.1f}% of "
        f"fallthroughs). Of {checked} sampled, {answered} received an assistant reply "
        f"afterwards ({recovery:.0f}% recovery via the classical path)."
    )
    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "window_days": 30,
                "fallthrough_total": len(rows),
                "reason_split": dict(all_reasons),
                "outcome_error_count": len(errs),
                "error_classes": dict(classes.most_common(25)),
                "empty_error_field": len(empty),
                "latency_p50_ms": lat[len(lat) // 2] if lat else None,
                "latency_p95_ms": lat[min(int(len(lat) * 0.95), len(lat) - 1)] if lat else None,
                "by_model": dict(by_model),
                "distinct_orgs": len(by_org),
                "conversations_checked": checked,
                "answered_afterwards": answered,
                "unanswered": unanswered[:20],
                "samples": errs[:25],
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
