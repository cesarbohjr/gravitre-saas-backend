#!/usr/bin/env python3
"""Bounded, isolated HTTP synthesis compatibility probe; not realtime certification."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
PHRASE = "Here is a short voice compatibility check."
MAX_VOICES = 12

def candidates(raw):
    ids = list(dict.fromkeys(v.strip() for v in raw.split(",") if v.strip()))
    if not ids or len(ids) > MAX_VOICES or any(not re.fullmatch(r"[A-Za-z0-9]{16,64}", v) for v in ids):
        raise ValueError("Configure one to twelve valid candidate voice IDs")
    return ids

def probe(env, transport=None):
    if not env.get("ELEVENLABS_API_KEY") or not env.get("VOICE_3_APPROVED_VOICE_IDS"):
        return {"status": "NOT RUN", "rows": [], "reason": "missing acceptance key or candidate IDs"}
    try:
        ids = candidates(env["VOICE_3_APPROVED_VOICE_IDS"])
    except ValueError:
        return {"status": "FAIL", "rows": [], "reason": "invalid candidate configuration"}
    import httpx
    from app.services.tier1_voice_service import DEFAULT_VOICES, synthesize_speech
    settings = SimpleNamespace(elevenlabs_api_key=env["ELEVENLABS_API_KEY"],
        elevenlabs_default_voice="sarah", elevenlabs_tts_model="eleven_flash_v2_5",
        **{f"elevenlabs_voice_{k}": "" for k in DEFAULT_VOICES})
    rows = []
    with httpx.Client(timeout=15, follow_redirects=False, transport=transport) as client:
        for voice_id in ids:
            started = time.monotonic()
            row = {"voice_id": voice_id, "model": "eleven_flash_v2_5", "passed": False}
            try:
                audio, content_type, meta = synthesize_speech(settings, text=PHRASE,
                    voice_key=voice_id, model_id=row["model"], http_client=client)
                row["passed"] = (meta["voice_id"] == voice_id and meta["model"] == row["model"]
                    and content_type == "audio/mpeg" and 100 <= len(audio) <= 5000000
                    and (audio.startswith(b"ID3") or (audio[0] == 255 and audio[1] & 224 == 224)))
                row["bytes"] = len(audio)
            except Exception as exc:
                row["error_type"] = type(exc).__name__
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            rows.append(row)
    return {"status": "PASS" if all(r["passed"] for r in rows) else "FAIL",
            "scope": "HTTP Flash synthesis only; no realtime or physical certification",
            "source_sha": env.get("GITHUB_SHA", ""), "rows": rows}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe(os.environ)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"])
    return 0 if result["status"] == "PASS" else 2 if result["status"] == "NOT RUN" else 1

if __name__ == "__main__":
    raise SystemExit(main())
