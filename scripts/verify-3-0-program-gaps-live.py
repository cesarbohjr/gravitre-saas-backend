#!/usr/bin/env python3
"""Live inventory for remaining 3.0 program gaps (isolated org only).

Does not print secrets. Does not complete third-party OAuth consent.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID  # noqa: E402

ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
LIVE_API = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-3.0-program-gaps-live.json"
VENDORS = (
    "google_analytics",
    "google_search_console",
    "gmail",
    "quickbooks",
    "zendesk",
)


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for key, value in os.environ.items():
        if value and key not in merged:
            merged[key] = value
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_JWT_SECRET",
    ):
        if merged.get(key):
            os.environ[key] = merged[key]
    return merged


def main() -> int:
    env = load_env()
    if ORG != DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID:
        raise SystemExit("refused unexpected org")
    health = httpx.get(f"{LIVE_API}/health", timeout=60.0).json()
    from app.config import get_settings
    from app.connectors.connector_availability_service import list_connector_availability
    from app.connectors.google_oauth_common import google_oauth_configured
    from app.connectors.quickbooks_oauth import quickbooks_oauth_configured
    from app.services.website_source_status import website_source_readiness
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    rows = list_connector_availability(
        client,
        ORG,
        settings,
        environment_name="production",
        force_live=True,
    )
    wanted: dict[str, list[dict]] = {v: [] for v in VENDORS}
    for row in rows:
        vendor = str(row.get("vendor") or "").strip().lower()
        if vendor not in wanted:
            continue
        wanted[vendor].append(
            {
                "connector_id": row.get("connector_id"),
                "present": True,
                "configured": row.get("configured"),
                "authenticated": row.get("authenticated"),
                "execution_available": row.get("execution_available"),
                "auth_status": row.get("auth_status"),
                "blocking_reason": row.get("blocking_reason"),
                "display_status": row.get("display_status"),
                "raw_status": row.get("raw_status"),
            }
        )
    readiness = website_source_readiness(client, ORG, settings)
    server = {
        "google_oauth_configured": google_oauth_configured(settings),
        "quickbooks_oauth_configured": quickbooks_oauth_configured(settings),
        "zendesk_client_id_present": bool(getattr(settings, "zendesk_client_id", None) or getattr(settings, "ZENDESK_CLIENT_ID", None)),
    }
    # Zendesk/Gmail often share Google or generic OAuth — surface presence only.
    for attr in (
        "zendesk_oauth_client_id",
        "gmail_client_id",
        "google_client_id",
        "google_oauth_client_id",
    ):
        if hasattr(settings, attr):
            server[f"{attr}_present"] = bool(getattr(settings, attr))

    from isolated_conversation_org import smoke_http_headers
    from smoke_auth import resolve_smoke_actor_and_email
    import jwt
    import time as _time

    actor, email = resolve_smoke_actor_and_email(client, org_id=ORG, env=env)
    now = int(_time.time())
    token = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        **smoke_http_headers(),
    }
    prod_list = httpx.get(f"{LIVE_API}/api/connectors?live=true", headers=headers, timeout=60.0)
    prod_connectors = {
        "http": prod_list.status_code,
        "body_head": (prod_list.text or "")[:800],
    }
    oauth_starts: dict[str, dict] = {}
    for provider, name, cid in (
        ("google_analytics", "Gravitre isolated GA4", "10b20a26-5de9-4d72-a84b-9d3f84ab38ab"),
        ("google_search_console", "Gravitre isolated GSC", "4d7fcc34-83a4-40c4-af31-97f5b1576163"),
        ("gmail", "Gravitre isolated Gmail", None),
        ("quickbooks", "Gravitre isolated QBO", None),
        ("zendesk", "Gravitre isolated Zendesk", None),
    ):
        payload: dict = {"name": name}
        if cid:
            payload["connectorId"] = cid
        resp = httpx.post(
            f"{LIVE_API}/api/connectors/oauth/{provider}/start",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
        oauth_starts[provider] = {
            "http": resp.status_code,
            "has_authorization_url": "authorizationUrl" in (resp.text or "")
            or "authorization_url" in (resp.text or ""),
            "detail": (resp.text or "")[:400],
        }

    token_presence: dict[str, bool] = {}
    for cid, label in (
        ("10b20a26-5de9-4d72-a84b-9d3f84ab38ab", "google_analytics"),
        ("4d7fcc34-83a4-40c4-af31-97f5b1576163", "google_search_console"),
    ):
        found = False
        for table in ("connector_oauth_tokens", "connector_secrets", "oauth_tokens"):
            try:
                data = (
                    client.table(table)
                    .select("id")
                    .eq("connector_id", cid)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if data:
                    found = True
                    break
            except Exception:
                continue
        token_presence[label] = found

    pcm: dict = {"attempted": False}

    def _sapi_pcm16(text: str) -> bytes:
        import subprocess
        import tempfile
        import wave
        import array

        wav_path = Path(tempfile.gettempdir()) / "gravitre-3-0-voice-c.wav"
        spoken = text.replace("'", "")
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.SetOutputToWaveFile('{wav_path}'); "
            f"$s.Speak('{spoken}'); "
            "$s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=60)
        with wave.open(str(wav_path), "rb") as handle:
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            frames = handle.readframes(handle.getnframes())
        if width != 2:
            raise RuntimeError(f"unexpected sample width {width}")
        samples = array.array("h")
        samples.frombytes(frames)
        if channels == 2:
            samples = array.array("h", [samples[i] for i in range(0, len(samples), 2)])
        if rate != 16000:
            ratio = rate / 16000.0
            out = array.array("h")
            n = int(len(samples) / ratio)
            for i in range(n):
                src = min(int(i * ratio), len(samples) - 1)
                out.append(samples[src])
            samples = out
        return samples.tobytes()

    try:
        from _voice_probe_lib import drive_turn, service_token, synthesize

        try:
            speech = synthesize("Is Apollo connected? Do not execute anything.")
            pcm_source = "elevenlabs"
        except Exception:
            speech = _sapi_pcm16("Is Apollo connected? Do not execute anything.")
            pcm_source = "windows_sapi"
        pcm_result = __import__("asyncio").run(drive_turn(service_token(), speech, deadline_s=70.0))
        pcm = {
            "attempted": True,
            "ok": bool(pcm_result.get("ok")),
            "proof_class": "SYNTHESIZED_PCM_INTO_PIPECAT_WS",
            "pcm_source": pcm_source,
            "pcm_bytes": len(speech),
            "first_delta_ms": pcm_result.get("first_delta_ms"),
            "first_answer_ms": pcm_result.get("first_answer_ms"),
            "physical_mic": False,
            "lane_b_webrtc": False,
        }
    except Exception as exc:  # noqa: BLE001
        pcm = {
            "attempted": True,
            "ok": False,
            "error": f"{exc.__class__.__name__}:{exc}",
            "proof_class": "SYNTHESIZED_PCM_INTO_PIPECAT_WS",
            "physical_mic": False,
        }

    report = {
        "probe": "3.0_program_gaps_live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "org_id": ORG,
        "health": {"git_sha": health.get("git_sha"), "timestamp": health.get("timestamp")},
        "local_settings_oauth_configured": server,
        "local_settings_availability": wanted,
        "production_connectors_http": prod_connectors,
        "production_oauth_start": oauth_starts,
        "oauth_token_row_present": token_presence,
        "website_source_readiness": {
            vendor: {
                "present": row.get("present"),
                "executable": row.get("executable"),
                "auth_status": row.get("auth_status"),
                "blocking_reason": row.get("blocking_reason"),
            }
            for vendor, row in (readiness or {}).items()
        },
        "pcm_voice": pcm,
        "lane_b": {
            "production_allows_webrtc": False,
            "reason": "voice_webrtc_eval.production_allows_webrtc_media is false; spec forbids serving production audio on lane B",
        },
    }
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
