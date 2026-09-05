#!/usr/bin/env python3
"""Real, live, per-stage latency measurement for the Pipecat voice WS.

Honesty label (read before trusting any number below): this sends REAL
synthesized speech audio (ElevenLabs-generated PCM16, not text-injection) into
the REAL, live, deployed `/api/voice/pipecat/ws` endpoint and times REAL
responses. It is NOT a human speaking into a real microphone through a real
browser — so it excludes browser mic capture/encode overhead and any
human-timing variance in where "speech end" really falls. It DOES exercise the
real Deepgram STT (Flux or Nova-3, whichever is live), the real
CognitiveTurnKernel reasoning path, and the real ElevenLabs TTS WebSocket —
end to end, on the real deployed backend. Treat this as the honest "infra
floor" for latency, not a substitute for Cesar's own perceptual verification
(naturalness, pacing, whether the barge-in feels immediate).

Per-stage timestamps captured (all wall-clock, monotonic):
  t_speech_end        — last byte of synthesized speech audio sent (silence follows)
  t_transcript_final  — first {"type":"transcript","final":true} (STT + turn-detection done)
  t_assistant_text    — first {"type":"assistant_text"} delta (LLM first token proxy)
  t_audio_start       — first {"type":"audio"} frame (TTS + playback-start proxy)

Derived (ms):
  stt_and_turn_detection_ms = t_transcript_final - t_speech_end
  llm_ttft_ms               = t_assistant_text   - t_transcript_final
  tts_ttfa_ms               = t_audio_start      - t_assistant_text
  end_to_end_ttfa_ms        = t_audio_start      - t_speech_end   <- the number that matters

Usage:
  python scripts/measure-voice-pipecat-live-latency.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "voice-pipecat-live-latency-2026-09-04.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"

SAMPLE_RATE = 16000
CHUNK_MS = 20
CHUNK_BYTES = int(SAMPLE_RATE * 2 * (CHUNK_MS / 1000))  # 16-bit mono
TRAILING_SILENCE_S = 1.3  # must clear Flux eot_threshold (0.7s) + Nova-3 VAD (0.4s)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value:
                    merged[key] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _service_token(env: dict[str, str], actor_id: str) -> str | None:
    bearer = (env.get("OPERATOR_BEARER") or env.get("GRAVITRE_OPERATOR_BEARER") or "").strip()
    if bearer:
        return bearer if not bearer.lower().startswith("bearer ") else bearer.split(" ", 1)[1]
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        return None
    try:
        import jwt

        now = int(time.time())
        return jwt.encode(
            {
                "sub": actor_id,
                "email": "voice-latency-probe@gravitre.internal",
                "aud": "authenticated",
                "iss": f"{url}/auth/v1",
                "iat": now,
                "exp": now + 3600,
                "role": "authenticated",
            },
            secret,
            algorithm="HS256",
        )
    except Exception:  # noqa: BLE001
        return None


def _ws_url(path: str, params: dict[str, str]) -> str:
    parsed = urlparse(BASE)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    q = urlencode({k: v for k, v in params.items() if v})
    return urlunparse((scheme, parsed.netloc, path, "", q, ""))


def _synthesize_speech_pcm16(env: dict[str, str], text: str) -> bytes:
    """Real ElevenLabs synthesis (used as simulated mic input), raw PCM16@16k."""
    for key, value in env.items():
        if value:
            os.environ.setdefault(key, value)
    from app.config import get_settings
    from app.services.tier1_voice_service import synthesize_speech_stream

    settings = get_settings()
    chunks = list(
        synthesize_speech_stream(settings, text=text, output_format="pcm_16000")
    )
    return b"".join(chunks)


async def _run_scenario(
    token: str,
    org_id: str,
    *,
    speech_pcm: bytes,
    label: str,
) -> dict:
    import websockets

    url = _ws_url(
        "/api/voice/pipecat/ws",
        {"access_token": token, "org_id": org_id, "conversation_id": str(uuid.uuid4())},
    )
    result: dict = {"label": label, "ok": False}
    try:
        import ssl

        try:
            import certifi

            ssl_ctx: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            ssl_ctx = True
        async with websockets.connect(
            url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=ssl_ctx
        ) as ws:
            ready: dict | None = None
            t_speech_end: float | None = None
            t_transcript_final: float | None = None
            t_assistant_text: float | None = None
            t_audio_start: float | None = None
            assistant_bits: list[str] = []
            sent_speech = False

            async def _send_speech() -> None:
                nonlocal t_speech_end, sent_speech
                for i in range(0, len(speech_pcm), CHUNK_BYTES):
                    chunk = speech_pcm[i : i + CHUNK_BYTES]
                    await ws.send(
                        json.dumps(
                            {
                                "type": "audio",
                                "pcm16_b64": base64.b64encode(chunk).decode("ascii"),
                                "sample_rate": SAMPLE_RATE,
                                "num_channels": 1,
                            }
                        )
                    )
                    await asyncio.sleep(CHUNK_MS / 1000)
                t_speech_end = time.monotonic()
                sent_speech = True
                silence_chunk = b"\x00" * CHUNK_BYTES
                n_silence = int((TRAILING_SILENCE_S * 1000) / CHUNK_MS)
                for _ in range(n_silence):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "audio",
                                "pcm16_b64": base64.b64encode(silence_chunk).decode("ascii"),
                                "sample_rate": SAMPLE_RATE,
                                "num_channels": 1,
                            }
                        )
                    )
                    await asyncio.sleep(CHUNK_MS / 1000)

            send_task: asyncio.Task | None = None
            deadline = time.monotonic() + 60.0
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                except asyncio.TimeoutError:
                    break
                if isinstance(raw, bytes):
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = str(msg.get("type") or "")
                if kind == "session.ready":
                    ready = msg
                    send_task = asyncio.create_task(_send_speech())
                elif kind == "transcript" and msg.get("final") and t_transcript_final is None:
                    t_transcript_final = time.monotonic()
                elif kind == "assistant_text":
                    if t_assistant_text is None:
                        t_assistant_text = time.monotonic()
                    delta = str(msg.get("delta") or "")
                    if delta:
                        assistant_bits.append(delta)
                elif kind == "audio":
                    if t_audio_start is None:
                        t_audio_start = time.monotonic()
                    if sent_speech and t_audio_start is not None:
                        break
                elif kind == "error":
                    result["error_event"] = msg
                    break
            if send_task is not None and not send_task.done():
                send_task.cancel()

            result.update(
                {
                    "ok": t_speech_end is not None and t_audio_start is not None,
                    "session_ready": ready is not None,
                    "stt_provider": (ready or {}).get("stt_provider"),
                    "stt_model": (ready or {}).get("stt_model"),
                    "stt_turn_detection": (ready or {}).get("stt_turn_detection"),
                    "tts_model": (ready or {}).get("tts_model"),
                    "tts_transport": (ready or {}).get("tts_transport"),
                    "cognitive_path": (ready or {}).get("cognitive_path"),
                    "write_confirm_policy": (ready or {}).get("write_confirm_policy"),
                    "assistant_text": "".join(assistant_bits)[:400],
                }
            )
            if t_speech_end is not None:
                if t_transcript_final is not None:
                    result["stt_and_turn_detection_ms"] = round(
                        (t_transcript_final - t_speech_end) * 1000
                    )
                if t_transcript_final is not None and t_assistant_text is not None:
                    result["llm_ttft_ms"] = round((t_assistant_text - t_transcript_final) * 1000)
                if t_assistant_text is not None and t_audio_start is not None:
                    result["tts_ttfa_ms"] = round((t_audio_start - t_assistant_text) * 1000)
                if t_audio_start is not None:
                    result["end_to_end_ttfa_ms"] = round((t_audio_start - t_speech_end) * 1000)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{exc.__class__.__name__}:{exc}"
    return result


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _health() -> dict:
    try:
        return httpx.get(f"{BASE}/health", timeout=30.0).json()
    except Exception as exc:  # noqa: BLE001
        return {"git_sha": None, "error": f"{exc.__class__.__name__}:{exc}"}


def main() -> int:
    env = _load_env()
    org_id = (env.get("VOICE_PROBE_ORG_ID") or ISOLATED_ORG).strip()
    actor_id = (env.get("VOICE_PROBE_ACTOR_ID") or DEFAULT_ACTOR).strip()
    token = _service_token(env, actor_id)
    if not token:
        print(json.dumps({"ok": False, "error": "no_token_available"}))
        return 1

    health = _health()

    scenarios = [
        ("simple_conversational", "What is two plus two?", 5),
        ("consequential_write_shaped", "Email Sarah that the campaign moved to Monday.", 3),
    ]

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_url": BASE,
        "git_sha": health.get("git_sha"),
        "methodology": (
            "Real synthesized-speech PCM16 fed into the live production Pipecat WS "
            "as simulated mic input; real Deepgram STT, real CognitiveTurnKernel, "
            "real ElevenLabs TTS WS. NOT a human speaking through a real browser mic "
            "-> excludes browser capture/encode overhead. This is an infra-latency "
            "floor, not a substitute for Cesar's own perceptual (naturalness/barge-in) "
            "verification."
        ),
        "scenarios": {},
    }

    for label, text, runs in scenarios:
        print(f"[latency-probe] synthesizing speech for scenario={label!r}...")
        try:
            speech_pcm = _synthesize_speech_pcm16(env, text)
        except Exception as exc:  # noqa: BLE001
            report["scenarios"][label] = {"ok": False, "error": f"synth_failed:{exc}"}
            continue
        runs_out = []
        for i in range(runs):
            print(f"[latency-probe] {label} run {i + 1}/{runs}...")
            res = asyncio.run(_run_scenario(token, org_id, speech_pcm=speech_pcm, label=label))
            runs_out.append(res)
        e2e = [r["end_to_end_ttfa_ms"] for r in runs_out if "end_to_end_ttfa_ms" in r]
        stt = [r["stt_and_turn_detection_ms"] for r in runs_out if "stt_and_turn_detection_ms" in r]
        llm = [r["llm_ttft_ms"] for r in runs_out if "llm_ttft_ms" in r]
        tts = [r["tts_ttfa_ms"] for r in runs_out if "tts_ttfa_ms" in r]
        report["scenarios"][label] = {
            "text": text,
            "n_runs": runs,
            "n_ok": sum(1 for r in runs_out if r.get("ok")),
            "end_to_end_ttfa_ms": {
                "p50": _percentile(e2e, 50),
                "p95": _percentile(e2e, 95),
                "raw": e2e,
            },
            "stt_and_turn_detection_ms": {
                "p50": _percentile(stt, 50),
                "raw": stt,
            },
            "llm_ttft_ms": {"p50": _percentile(llm, 50), "raw": llm},
            "tts_ttfa_ms": {"p50": _percentile(tts, 50), "raw": tts},
            "sub_500ms_p95_met": (
                (_percentile(e2e, 95) or 999999) < 500 if e2e else None
            ),
            "runs": runs_out,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {
        label: {
            "p50_ms": data.get("end_to_end_ttfa_ms", {}).get("p50"),
            "p95_ms": data.get("end_to_end_ttfa_ms", {}).get("p95"),
            "sub_500ms_p95_met": data.get("sub_500ms_p95_met"),
            "n_ok": data.get("n_ok"),
        }
        for label, data in report["scenarios"].items()
    }
    print(json.dumps({"git_sha": health.get("git_sha"), "summary": summary, "out": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
