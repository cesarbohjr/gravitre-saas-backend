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
            try:
                audio, content_type, tts_meta = synthesize_speech(settings, text=phrase, voice_key=env.get("ELEVENLABS_VOICE_ID"), http_client=client)
            except Exception as exc:
                exc.acceptance_stage = "elevenlabs_tts"
                raise
            if not audio or len(audio) > 5_000_000:
                raise ValueError("Provider returned empty or oversized audio")
            try:
                transcript, stt_meta = transcribe_audio(settings, audio_bytes=audio, content_type=content_type, filename="synthetic-acceptance.mp3", http_client=client)
            except Exception as exc:
                exc.acceptance_stage = "deepgram_stt"
                raise
            from app.services.spoken_write_approval import classify_spoken_write_approval
            decision = classify_spoken_write_approval(transcript)
            passed = asyncio.run(prove_commit_block(transcript))
            # No raw transcript, transcript hashes or free-text provider metadata.
            rows.append({"case": case, "passed": passed,
                "stt_diagnostics": {
                    "transcript_present": bool(transcript and transcript.strip()),
                    "decision": decision.decision,
                    "reason": decision.reason if decision.reason in {
                        "yes_wait_hold_commit", "spoken_reject",
                        "ambiguous_spoken_confirm", "no_spoken_write_match",
                        "empty_message", "no_pending_confirmation",
                    } else "other",
                    "invoke_allowed": decision.invoke_allowed,
                },
                "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "request_id": stt_meta.get("request_id"), "tts_request_id": tts_meta.get("request_id"),
                "roundtrip_ms": round((time.monotonic() - started) * 1000), "business_write_executors_called": 0})
    return {"status": "PASS" if rows and all(row["passed"] for row in rows) else "FAIL", "cases": rows,
            "physical_acceptance": "NOT RUN", "scope": "synthetic prerecorded provider roundtrip and local final commit gate"}


def sanitized_failure(exc):
    """Emit fixed diagnostic categories, never provider response bodies."""
    import httpx
    info = {"error_type": type(exc).__name__}
    from app.services.tier1_voice_service import VoiceProviderError
    if isinstance(exc, VoiceProviderError):
        info["provider"] = (exc.provider or "unknown").lower()
        info["upstream_error_class"] = exc.error_class
        # Provider detail is untrusted and may contain secrets. Extract only a
        # tightly allowlisted machine-readable status, never the raw message.
        try:
            detail = json.loads(exc.provider_detail or "{}")
            payload = detail.get("detail", detail)
            if isinstance(payload, dict):
                candidates = (payload.get("status"), payload.get("code"))
                allowed = {
                    "invalid_api_key", "invalid_api_key_prefix", "voice_not_found",
                    "model_not_found", "quota_exceeded", "max_character_limit_exceeded",
                    "invalid_output_format", "insufficient_permissions",
                    "voice_limit_reached", "subscription_required",
                }
                info["provider_reason"] = next(
                    (value for value in candidates if isinstance(value, str) and value in allowed),
                    "unclassified",
                )
        except (ValueError, TypeError, AttributeError):
            info["provider_reason"] = "unclassified"
    stage = getattr(exc, "acceptance_stage", None)
    if stage in ("elevenlabs_tts", "deepgram_stt"):
        info["stage"] = stage
    status = getattr(exc, "upstream_status", None)
    if not isinstance(status, int):
        status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if not isinstance(status, int):
        status = getattr(response, "status_code", None)
    if isinstance(status, int) and 100 <= status <= 599:
        info["http_status"] = status
        info["error_category"] = ("authentication" if status in (401, 403) else
                                  "rate_limit" if status == 429 else
                                  "invalid_request" if status in (400, 404, 422) else
                                  "provider_server" if status >= 500 else "http_error")
    elif isinstance(exc, httpx.TimeoutException):
        info["error_category"] = "timeout"
    elif isinstance(exc, httpx.TransportError):
        info["error_category"] = "transport"
    else:
        info["error_category"] = "provider_error_unclassified"
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_provider_checks(os.environ)
    except Exception as exc:
        # Do not serialize exception URLs/headers; they may contain credentials.
        result = {"status": "FAIL", **sanitized_failure(exc), "physical_acceptance": "NOT RUN"}
    result["commit_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result["worktree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "provider", "stage", "provider_reason", "error_type", "error_category", "http_status") if key in result}))
    return 0 if result["status"] == "PASS" else 2 if result["status"] == "NOT RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
