#!/usr/bin/env python3
"""Live proof on one real voice session: composed failure text + real socket facts.

Two open items share a prerequisite -- an actual authenticated voice session
against the deployed tip -- so they run in one pass rather than two:

  1. The cognitive_llm fix (3e621c07). The voice path used to push
     str(exc)[:500] into an ErrorFrame, so a Python exception could be read
     aloud. Confirm nothing user-facing on the voice path is raw backend text.

  2. Phase B. The earlier toast investigation could not be closed because the
     REAL WebSocket URL and close code at the moment of failure were never
     captured -- only inferred from code review. Record both as facts.

The access token rides in the WS query string, so the raw URL is a live
credential. It is redacted here the same way apps/web/lib/voice-socket-
diagnostics.ts redacts it: origin and path kept, every value dropped.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import ssl
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"
WS_PATH = "/api/voice/pipecat/ws"
OUT = ROOT / "docs" / "delivery" / "voice-composer-and-socket-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

SAMPLE_RATE = 16000
CHUNK_MS = 20
CHUNK_BYTES = int(SAMPLE_RATE * 2 * (CHUNK_MS / 1000))
TRAILING_SILENCE_S = 1.5

# The utterance is a real operator-shaped request, not "hello". A trivial turn
# can be answered by a fast path and would never exercise the cognitive turn
# whose failure handler is under test.
UTTERANCE = os.environ.get(
    "VOICE_PROBE_UTTERANCE",
    "Pull my connected HubSpot contacts and tell me which accounts went quiet this month.",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    from dotenv import dotenv_values

    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in (dotenv_values(p, encoding=enc) or {}).items():
                    if v and not os.environ.get(k):
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue


def redact_ws_url(raw: str) -> str:
    """Same contract as redactVoiceWsUrl in the web client."""
    try:
        u = urlparse(raw)
        from urllib.parse import parse_qs

        keys = list(parse_qs(u.query).keys())
        shown = "?" + "&".join(f"{k}=<redacted>" for k in keys) if keys else ""
        return f"{u.scheme}://{u.netloc}{u.path}{shown}"
    except Exception:  # noqa: BLE001
        return "(unparseable)"


def service_token(actor_id: str = DEFAULT_ACTOR) -> str:
    import jwt

    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    secret = (os.environ.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        raise SystemExit("SUPABASE_URL and SUPABASE_JWT_SECRET required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": actor_id,
            "email": "voice-composer-probe@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def ssl_ctx() -> Any:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return True


def synthesize(text: str) -> bytes:
    from app.config import get_settings
    from app.services.tier1_voice_service import synthesize_speech_stream

    return b"".join(
        synthesize_speech_stream(get_settings(), text=text, output_format="pcm_16000")
    )


async def run_session(
    token: str,
    speech: bytes,
    *,
    conversation_id: str | None = None,
    deadline_s: float = 120.0,
) -> dict[str, Any]:
    import websockets

    url = urlunparse(
        (
            "wss" if urlparse(BASE).scheme == "https" else "ws",
            urlparse(BASE).netloc,
            WS_PATH,
            "",
            urlencode(
                {
                    "access_token": token,
                    "org_id": ISOLATED_ORG,
                    "conversation_id": conversation_id or str(uuid.uuid4()),
                }
            ),
            "",
        )
    )

    result: dict[str, Any] = {
        "ws_url_redacted": redact_ws_url(url),
        "ws_path": WS_PATH,
        "token_in_query": "access_token" in url,
        "opened": False,
        "session_ready": False,
        "close_code": None,
        "close_reason": None,
        "was_clean": None,
        "connect_error": None,
        "events": [],
        "assistant_text": "",
        "server_errors": [],
        "raw_messages": [],
        "audio_frames": 0,
        "audio_bytes": 0,
    }

    deltas: list[str] = []
    try:
        async with websockets.connect(
            url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=ssl_ctx()
        ) as ws:
            result["opened"] = True

            async def send_audio() -> None:
                for i in range(0, len(speech), CHUNK_BYTES):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "audio",
                                "pcm16_b64": base64.b64encode(
                                    speech[i : i + CHUNK_BYTES]
                                ).decode("ascii"),
                                "sample_rate": SAMPLE_RATE,
                                "num_channels": 1,
                            }
                        )
                    )
                    await asyncio.sleep(CHUNK_MS / 1000)
                silence = base64.b64encode(b"\x00" * CHUNK_BYTES).decode("ascii")
                for _ in range(int((TRAILING_SILENCE_S * 1000) / CHUNK_MS)):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "audio",
                                "pcm16_b64": silence,
                                "sample_rate": SAMPLE_RATE,
                                "num_channels": 1,
                            }
                        )
                    )
                    await asyncio.sleep(CHUNK_MS / 1000)

            send_task: asyncio.Task | None = None
            last_text_at: float | None = None
            deadline = time.monotonic() + deadline_s
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=25.0)
                except asyncio.TimeoutError:
                    result["events"].append({"type": "_recv_timeout"})
                    break
                except Exception as exc:  # noqa: BLE001
                    result["events"].append(
                        {"type": "_recv_closed", "detail": type(exc).__name__}
                    )
                    break
                if isinstance(raw, bytes):
                    # Binary frames are synthesized speech. Counting them matters:
                    # if the composed line is spoken but never mirrored as text,
                    # a text-only capture would wrongly report silence.
                    result["audio_frames"] = int(result.get("audio_frames") or 0) + 1
                    result["audio_bytes"] = int(result.get("audio_bytes") or 0) + len(raw)
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = str(msg.get("type") or "")
                if kind == "session.ready":
                    result["session_ready"] = True
                    send_task = asyncio.create_task(send_audio())
                elif kind == "assistant_text":
                    delta = str(msg.get("delta") or "")
                    if delta.strip():
                        deltas.append(delta)
                        last_text_at = time.monotonic()
                elif kind == "error":
                    # Record the WHOLE payload. Reading a guessed key is how a
                    # capture reports "empty" when the text is sitting in a field
                    # the reader never looked at.
                    result["server_errors"].append(json.loads(json.dumps(msg))) 
                if kind not in {"audio"}:
                    result["events"].append({"type": kind or "(untyped)"})
                    # Keep full payloads for anything that is not a bulk transcript
                    # delta, so the rendered surface can be reconstructed later.
                    if kind != "assistant_text" and len(result["raw_messages"]) < 60:
                        result["raw_messages"].append(json.loads(json.dumps(msg)))
                if last_text_at is not None and time.monotonic() - last_text_at > 5.0:
                    break

            if send_task is not None and not send_task.done():
                send_task.cancel()

        # websockets exposes the handshake/close facts on the closed connection.
        result["close_code"] = getattr(ws, "close_code", None)
        result["close_reason"] = getattr(ws, "close_reason", None)
        result["was_clean"] = result["close_code"] in (1000, 1001)
    except Exception as exc:  # noqa: BLE001
        result["connect_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        for attr in ("code", "reason"):
            val = getattr(exc, attr, None)
            if val is not None:
                result[f"close_{'code' if attr == 'code' else 'reason'}"] = val

    result["assistant_text"] = "".join(deltas).strip()[:3000]
    return result


def main() -> int:
    load_env()
    import httpx

    out: dict[str, Any] = {
        "probe": "voice_composer_and_socket",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": ISOLATED_ORG,
        "utterance": UTTERANCE,
        "covers": [
            "cognitive_llm raw-exception leak on the voice path (3e621c07)",
            "Phase B real WS URL + close code",
        ],
    }

    with httpx.Client(timeout=45) as c:
        health = c.get(f"{BASE}/health").json()
    sha = str(health.get("git_sha") or "")
    out["git_sha"] = sha
    out["health_timestamp"] = health.get("timestamp")
    if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
        out["verdict"] = f"NOT RUN - tip mismatch got={sha} expect={EXPECT_SHA}"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": out["verdict"]}, indent=2))
        return 1

    try:
        speech = synthesize(UTTERANCE)
        out["speech_bytes"] = len(speech)
    except Exception as exc:  # noqa: BLE001
        out["verdict"] = f"NOT RUN - synthesis unavailable: {type(exc).__name__}: {exc}"[:300]
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": out["verdict"]}, indent=2))
        return 1

    from app.services.composer_failure_triggers import (
        VOICE_TURN_FAILURE_CONVERSATION_ID,
        VOICE_TURN_FAILURE_MESSAGE,
    )

    # Leak scan uses the Composer's own detector rather than a second list, so
    # this cannot drift from what the Composer actually considers a leak.
    from app.services.response_composer import TTS_SAFE_ERROR, looks_like_raw_backend

    def user_facing(session: dict[str, Any]) -> list[str]:
        """Every string the server sent that a user could end up reading or hearing.

        Pulls all string values out of error payloads rather than one guessed
        key, because the field carrying the message is exactly the thing not to
        assume.
        """
        def strings(node: Any) -> list[str]:
            # Recurses, because the live payload nests the message at data.error
            # rather than at the top level. A flat read of the same event returned
            # empty and would have been reported as "no user-facing text".
            if isinstance(node, str):
                return [node]
            if isinstance(node, dict):
                return [s for v in node.values() for s in strings(v)]
            if isinstance(node, list):
                return [s for v in node for s in strings(v)]
            return []

        return [session.get("assistant_text") or ""] + strings(
            session.get("server_errors") or []
        )

    # A healthy turn first: establishes the socket's normal close code, which is
    # the baseline Phase B needs in order to call any other code abnormal. A
    # fresh token and a real gap per session, because the first back-to-back
    # attempt degraded both runs -- two sessions in quick succession on one token
    # closed 1006 with no text, where a single session closed 1000 with text.
    healthy = asyncio.run(run_session(service_token(), speech))
    out["healthy_session"] = healthy
    time.sleep(float(os.environ.get("VOICE_PROBE_GAP_S", "20")))

    # Then the deliberate cognitive-turn failure. The happy path never enters the
    # except-handler, so without this the fix is untested however green the
    # healthy run looks.
    failed = asyncio.run(
        run_session(
            service_token(),
            speech,
            conversation_id=VOICE_TURN_FAILURE_CONVERSATION_ID,
        )
    )
    out["induced_failure_session"] = failed

    fail_texts = user_facing(failed)
    leaks = [t[:300] for t in fail_texts if t and looks_like_raw_backend(t)]
    out["tts_safe_error_expected"] = TTS_SAFE_ERROR
    out["probe_message_that_must_not_appear"] = VOICE_TURN_FAILURE_MESSAGE
    out["leaks"] = leaks
    out["raw_probe_text_verbatim"] = [
        t[:300] for t in fail_texts if VOICE_TURN_FAILURE_MESSAGE in (t or "")
    ]
    out["composed_safe_line_present"] = any(
        TTS_SAFE_ERROR in (t or "") for t in fail_texts
    )

    # If the control turn did not itself produce text, this run cannot tell the
    # difference between "the failure path stayed silent" and "the harness got
    # nothing either way". That is INCONCLUSIVE, not PASS and not FAIL.
    control_ok = bool(
        healthy.get("opened")
        and healthy.get("session_ready")
        and (healthy.get("assistant_text") or "").strip()
    )
    out["control_ok"] = control_ok
    if not control_ok:
        out["verdict"] = (
            "INCONCLUSIVE - control turn produced no text "
            f"(opened={healthy.get('opened')} ready={healthy.get('session_ready')} "
            f"close={healthy.get('close_code')}); cannot attribute the failure "
            "turn's silence to the code under test"
        )
        out["finished_at"] = utcnow()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "verdict": out["verdict"],
                    "git_sha": sha,
                    "healthy_close_code": healthy.get("close_code"),
                    "failure_close_code": failed.get("close_code"),
                    "healthy_events": [e.get("type") for e in healthy.get("events") or []],
                },
                indent=2,
                default=str,
            )
        )
        return 2

    fails: list[str] = []
    if not failed.get("opened"):
        fails.append(f"failure_session_never_opened({failed.get('connect_error')})")
    if out["raw_probe_text_verbatim"]:
        fails.append("RAW EXCEPTION REACHED THE USER verbatim")
    if leaks:
        fails.append(f"raw_backend_text_user_facing={leaks}")
    if not any(t.strip() for t in fail_texts):
        # Silence is not a pass. If the turn failed and the user got nothing at
        # all, the Composer is not the sole path to output -- it is absent.
        fails.append("induced_failure_produced_no_user_facing_text")
    elif not out["composed_safe_line_present"]:
        fails.append(
            f"composed_safe_line_absent; got={[t[:200] for t in fail_texts if t.strip()]}"
        )

    out["fails"] = fails
    session = failed
    if fails:
        out["verdict"] = "FAIL - " + "; ".join(fails)
        code = 1
    else:
        out["verdict"] = (
            f"PASS - on {sha[:8]}: induced cognitive-turn failure on a live voice "
            f"session produced the composed safe line, not the raw exception; "
            f"healthy close_code={healthy.get('close_code')} "
            f"failure close_code={session.get('close_code')} "
            f"url={session.get('ws_url_redacted')}"
        )
        code = 0
    out["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": out["verdict"],
                "git_sha": sha,
                "ws_url_redacted": session.get("ws_url_redacted"),
                "close_code": session.get("close_code"),
                "was_clean": session.get("was_clean"),
                "server_errors": session.get("server_errors"),
                "raw_messages": session.get("raw_messages"),
                "audio_frames": session.get("audio_frames"),
                "audio_bytes": session.get("audio_bytes"),
                "healthy_audio_frames": healthy.get("audio_frames"),
                "assistant_text": (session.get("assistant_text") or "")[:400],
            },
            indent=2,
            default=str,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
