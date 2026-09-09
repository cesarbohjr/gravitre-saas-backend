#!/usr/bin/env python3
"""How much silence does tool narration actually cover on a voice turn?

Narration ("Let me check your knowledge base. Found 5.") costs four sentences of
mechanics before the answer on a tool-using turn. Whether that is worth keeping
depends on a number nobody had measured: how long the user would otherwise wait
in silence while the tools run.

This timestamps every ``assistant_text`` delta on a real production turn and
reports the gap between the narration sentences and the first word of the actual
answer. That gap is the dead air narration exists to fill.

For latency work use ``measure-voice-latency-harness.py`` instead -- it reports a
noise floor, which this script does not, and single samples here have ranged over
25x.

Honesty label: real ElevenLabs-synthesized speech into the real deployed
``/api/voice/pipecat/ws``. NOT a human at a browser mic.

Credentials from the environment only: SUPABASE_URL, SUPABASE_JWT_SECRET,
ELEVENLABS_API_KEY.

Usage:
  python scripts/measure-voice-narration-dead-air.py [runs]
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _voice_probe_lib import REPO, drive_turn, service_token, synthesize  # noqa: E402

# A question that reliably drives real tool calls.
UTTERANCE = "Did the HubSpot sync finish today?"


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    token = service_token()
    print(f"[dead-air] synthesizing {UTTERANCE!r}...", flush=True)
    speech = synthesize(UTTERANCE)

    results = []
    for i in range(runs):
        print(f"[dead-air] run {i + 1}/{runs}...", flush=True)
        res = asyncio.run(drive_turn(token, speech))
        res["utterance"] = UTTERANCE
        results.append(res)
        print(
            f"  first_delta={res.get('first_delta_ms')}ms "
            f"first_answer={res.get('first_answer_ms')}ms "
            f"dead_air_covered={res.get('dead_air_covered_ms')}ms "
            f"max_gap={res.get('max_gap_ms')}ms "
            f"narration_words={res.get('narration_word_count')}",
            flush=True,
        )

    ok = [r for r in results if r.get("ok")]
    summary = {
        "runs": runs,
        "n_ok": len(ok),
        "dead_air_covered_ms": sorted(
            r["dead_air_covered_ms"] for r in ok if r.get("dead_air_covered_ms") is not None
        ),
        "first_answer_ms": sorted(
            r["first_answer_ms"] for r in ok if r.get("first_answer_ms") is not None
        ),
        "narration_word_counts": [r.get("narration_word_count") for r in ok],
    }
    out_path = REPO / "docs" / "delivery" / "voice-narration-dead-air-2026-09-08.json"
    out_path.write_text(
        json.dumps({"summary": summary, "runs": results}, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print("\n" + json.dumps(summary, indent=2), flush=True)
    print(f"wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
