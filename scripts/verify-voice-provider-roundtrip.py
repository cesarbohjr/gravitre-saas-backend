#!/usr/bin/env python3
"""Bounded ElevenLabs -> Deepgram -> canonical confirmation/commit-gate acceptance.

Only fixed synthetic phrases are generated. No business write executor is called.
This is provider audio roundtrip evidence, NOT physical microphone/speaker or
full duplex latency acceptance. Missing credentials exits 2 (NOT RUN), never PASS.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
CASES = (("yes_wait", "Yes, wait. Hold on."), ("cancel", "Cancel it. Do not send anything."))


async def prove_commit_block(transcript):
    from app.services import voice_pause_gate
    from app.services.spoken_write_approval import classify_spoken_write_approval
    from app.services.tool_types import ToolValidationError
    from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
    from app.services.voice_barge_in_write import begin_write_effect
    decision = classify_spoken_write_approval(transcript)
    if decision.invoke_allowed or decision.decision not in {"hold_commit", "reject"}:
        return False
    ctx = SimpleNamespace(org_id=str(uuid4()), conversation_id=str(uuid4()), settings=SimpleNamespace())
    cancellation = TurnCancellation()
    cancellation.cancel("provider_acceptance_hold")
    voice_pause_gate.pause(ctx.org_id, ctx.conversation_id)
    try:
        with bound_turn_cancellation(cancellation):
            try:
                begin_write_effect(ctx, "gmail.send")
            except ToolValidationError:
                return True
            return False
    finally:
        voice_pause_gate.end_pause(ctx.org_id, ctx.conversation_id)


def run_provider_checks(env, transport=None):
    required = ("DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY")
    missing = [name for name in required if not env.get(name)]
    if missing:
        return {"status": "NOT RUN", "blockers": ["missing:" + name for name in missing], "cases": [], "physical_acceptance": "NOT RUN"}
    import httpx
    from app.services.tier1_voice_service import synthesize_speech, transcribe_audio
    settings = SimpleNamespace(elevenlabs_api_key=env["ELEVENLABS_API_KEY"], deepgram_api_key=env["DEEPGRAM_API_KEY"],
        elevenlabs_default_voice=env.get("ELEVENLABS_DEFAULT_VOICE", "sarah"),
        elevenlabs_tts_model=env.get("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"), deepgram_stt_model=env.get("DEEPGRAM_STT_MODEL", "nova-3"),
        **{"elevenlabs_voice_" + key: env.get("ELEVENLABS_VOICE_" + key.upper(), "") for key in ("sarah", "rachel", "adam", "josh", "eric")})
    rows = []
    with httpx.Client(timeout=30, follow_redirects=False, transport=transport) as client:
        for case, phrase in CASES:
            started = time.monotonic()
            audio, content_type, tts_meta = synthesize_speech(settings, text=phrase, voice_key=env.get("ELEVENLABS_VOICE_ID"), http_client=client)
            if not audio or len(audio) > 5_000_000:
                raise ValueError("Provider returned empty or oversized audio")
            transcript, stt_meta = transcribe_audio(settings, audio_bytes=audio, content_type=content_type, filename="synthetic-acceptance.mp3", http_client=client)
            passed = asyncio.run(prove_commit_block(transcript))
            rows.append({"case": case, "passed": passed, "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "request_id": stt_meta.get("request_id"), "tts_request_id": tts_meta.get("request_id"),
                "roundtrip_ms": round((time.monotonic() - started) * 1000), "business_write_executors_called": 0})
    return {"status": "PASS" if rows and all(row["passed"] for row in rows) else "FAIL", "cases": rows,
            "physical_acceptance": "NOT RUN", "scope": "synthetic prerecorded provider roundtrip and local final commit gate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_provider_checks(os.environ)
    except Exception as exc:
        # Do not serialize exception URLs/headers; they may contain credentials.
        result = {"status": "FAIL", "error_type": type(exc).__name__, "physical_acceptance": "NOT RUN"}
    result["commit_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result["worktree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0 if result["status"] == "PASS" else 2 if result["status"] == "NOT RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
