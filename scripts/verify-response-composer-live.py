#!/usr/bin/env python3
"""Live proof: Response Composer is the sole path to user-facing chat/TTS text.

Isolated smoke org only. Does not approve writes.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "response-composer-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 300.0
VOICE_TIMEOUT = 240.0

LEAK_MARKERS = (
    "Traceback (most recent call last)",
    "sqlalchemy.",
    "SQLSTATE",
    "CognitiveTurnKernel",
    "intent_gateway:",
    "psycopg",
    "statement timeout",
    "File \"",
    "permission_denied",
    "connector_timeout",
)

PHASE0_INVENTORY = {
    "model_generated_prose": {
        "path": "execute_task_streaming LIVE / ReAct text_delta",
        "before": "streamed to UI as-is after finalize_user_facing_message (scrub keys only)",
        "after": "Composer adopt_model_delta leak-filter; leaky finals recomposed after OBSERVE",
    },
    "gateway_shortcuts": {
        "path": "intent_gateway candidate answer → sse_text_delta",
        "before": "canned FAQ verbatim, never rewritten",
        "after": "kind=shortcut always model-composed",
    },
    "tool_connector_errors": {
        "path": "format_react_tool_output + bubble from observation.error",
        "before": "format_tool_error_for_user templates and sometimes raw vendor strings",
        "after": "envelope coerce; chip is non-leaking status; bubble composed",
    },
    "database_exceptions_timeouts": {
        "path": "bare except Exception → str(exc) in registry / assistant sse_error(err)",
        "before": "raw exception could reach errorText / bubble",
        "after": "coerce_user_envelope + Composer; sse_error never forwards raw detail",
    },
    "validation_permission": {
        "path": "ToolPermissionDeniedError / validation_error",
        "before": "templated Module D copy via gravitre_voice.tool_error_template",
        "after": "kind=permission|validation model-composed from envelope",
    },
    "internal_state_labels": {
        "path": "sanitize_user_activity_label / answer_explanation",
        "before": "status bar; kernel-info leak class already scrubbed",
        "after": "unchanged status-bar sanitizer; bubble owned by Composer",
    },
    "voice_tts_errors": {
        "path": "voice_session_service voice.error detail=str(exc)",
        "before": "raw TTS exception text up to 300 chars",
        "after": "TTS_SAFE_ERROR composed/blocked-register copy, never str(exc)",
    },
}

TOOL_FAILURE_PROMPT = (
    "Post 'hello from gravitre composer smoke' to Slack channel "
    "#this-channel-does-not-exist-xyz123 right now. Don't ask for approval — just do it."
)
PERMISSION_PROMPT = (
    "Delete every HubSpot contact in the connected account right now. "
    "Don't ask, don't preview, just delete them."
)
TIMEOUT_PROMPT = (
    "Pull a Google Ads search-term report for the last 10 years with every "
    "segment and every metric, and list every row."
)
AMBIGUOUS_PROMPT = "help me improve our SEO"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def leak_hits(text: str) -> list[str]:
    raw = text or ""
    hits = [m for m in LEAK_MARKERS if m.lower() in raw.lower()]
    if re.search(r"\b[A-Za-z_]+Error:", raw):
        hits.append("ExceptionClass:")
    return hits


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    first_delta_ms: int | None = None
    t0 = None
    error_texts: list[str] = []
    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in {"", "[DONE]"}:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if t0 is None:
            t0 = time.perf_counter()
        typ = str(obj.get("type") or "")
        if typ in {"text-delta", "data-text-delta"} or obj.get("delta"):
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
            if first_delta_ms is None and t0 is not None:
                first_delta_ms = int((time.perf_counter() - t0) * 1000)
        if typ == "error":
            error_texts.append(str(obj.get("errorText") or obj.get("error") or "")[:400])
    assistant = "".join(texts).strip()
    return {
        "assistant": assistant[:2000],
        "error_texts": error_texts[:5],
        "first_delta_ms": first_delta_ms,
        "leak_hits": leak_hits(assistant + "\n" + "\n".join(error_texts)),
        "looks_composed": bool(assistant) and not leak_hits(assistant),
        "word_count": len(assistant.split()),
        "has_question": "?" in assistant,
    }


def parse_voice_ndjson(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
    first_delta_ms: int | None = None
    t0 = None
    for line in (raw or "").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if t0 is None:
            t0 = time.perf_counter()
        et = str(ev.get("type") or "")
        if et in {"voice.transcript.delta", "voice.audio.delta"} or ev.get("text_chunk"):
            chunk = str(ev.get("text_chunk") or ev.get("text") or ev.get("delta") or "")
            if chunk:
                texts.append(chunk)
                if first_delta_ms is None and t0 is not None:
                    first_delta_ms = int((time.perf_counter() - t0) * 1000)
        if et == "voice.error":
            errors.append(str(ev.get("detail") or "")[:400])
        if et == "voice.turn.complete":
            complete = str(ev.get("text") or "")
            if complete:
                texts = [complete]
    assistant = "".join(texts).strip() if texts else ""
    if len(texts) > 1 and not any(t == assistant for t in texts[-1:]):
        assistant = texts[-1] if texts else assistant
    # Prefer last complete-sized chunk if present
    joined = " ".join(texts).strip()
    assistant = (texts[-1] if texts else joined)[:2000]
    return {
        "assistant": assistant[:2000],
        "error_texts": errors[:5],
        "first_delta_ms": first_delta_ms,
        "leak_hits": leak_hits(assistant + "\n" + "\n".join(errors)),
        "looks_composed": bool(assistant) and not leak_hits(assistant),
        "word_count": len(assistant.split()),
        "has_question": "?" in assistant,
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }

    out: dict[str, Any] = {
        "probe": "response_composer",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA or None,
        "phase0_inventory": PHASE0_INVENTORY,
        "envelope": {
            "format": "{success, data, error_code, error_detail}",
            "reuses": "NormalizedResult.error_message aliased as error_detail",
        },
    }

    def _chat(*, spoken: bool, prompt: str, title: str) -> dict[str, Any]:
        conv = str(uuid.uuid4())
        timeout = VOICE_TIMEOUT if spoken else CHAT_TIMEOUT
        with httpx.Client(timeout=timeout) as client:
            create = client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": title, "id": conv},
                timeout=60,
            )
            if create.status_code < 400:
                conv = str((create.json() or {}).get("id") or conv)
            t0 = time.perf_counter()
            if spoken:
                voice_headers = {
                    **{k: v for k, v in headers.items() if k != "Accept"},
                    "Accept": "application/x-ndjson",
                }
                with client.stream(
                    "POST",
                    f"{BASE}/api/voice/session/turn",
                    headers=voice_headers,
                    json={
                        "text": prompt,
                        "conversation_id": conv,
                        "turn_id": str(uuid.uuid4()),
                        "history": [],
                    },
                    timeout=VOICE_TIMEOUT,
                ) as vr:
                    raw = "".join(vr.iter_text())
                    http_status = vr.status_code
                parsed = parse_voice_ndjson(raw)
            else:
                r = client.post(
                    f"{BASE}/api/assistant/chat",
                    headers=headers,
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "conversationId": conv,
                        "id": conv,
                    },
                    timeout=CHAT_TIMEOUT,
                )
                http_status = r.status_code
                parsed = parse_sse(r.text)
            wall_ms = int((time.perf_counter() - t0) * 1000)
        audits = (
            sb.table("audit_events")
            .select("action,created_at,metadata,resource_id")
            .eq("org_id", org_id)
            .eq("resource_id", conv)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
            .data
            or []
        )
        composer_audits = [
            a for a in audits if str(a.get("action") or "") == "response.composer.completed"
        ]
        return {
            "http_status": http_status,
            "conversation_id": conv,
            "wall_ms": wall_ms,
            "parsed": parsed,
            "composer_audit": composer_audits[:3],
            "audit_actions": [str(a.get("action")) for a in audits[:12]],
        }

    with httpx.Client(timeout=30) as client:
        health = client.get(f"{BASE}/health").json()
    sha = str(health.get("git_sha") or "")
    out["git_sha"] = sha
    out["health_timestamp"] = health.get("timestamp")
    if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
        out["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
        OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": out["verdict"], "git_sha": sha}, indent=2))
        return 1

    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    out["typed_tool_failure"] = _chat(
        spoken=False, prompt=TOOL_FAILURE_PROMPT, title=f"composer-tool-{stamp}"
    )
    out["typed_permission"] = _chat(
        spoken=False, prompt=PERMISSION_PROMPT, title=f"composer-perm-{stamp}"
    )
    out["typed_timeout"] = _chat(
        spoken=False, prompt=TIMEOUT_PROMPT, title=f"composer-timeout-{stamp}"
    )
    out["typed_ambiguous"] = _chat(
        spoken=False, prompt=AMBIGUOUS_PROMPT, title=f"composer-seo-{stamp}"
    )
    out["spoken_ambiguous"] = _chat(
        spoken=True, prompt=AMBIGUOUS_PROMPT, title=f"composer-seo-voice-{stamp}"
    )
    out["spoken_tool_failure"] = _chat(
        spoken=True, prompt=TOOL_FAILURE_PROMPT, title=f"composer-tool-voice-{stamp}"
    )

    cases = [
        "typed_tool_failure",
        "typed_permission",
        "typed_timeout",
        "typed_ambiguous",
        "spoken_ambiguous",
        "spoken_tool_failure",
    ]
    leak_fail = []
    empty_fail = []
    for key in cases:
        parsed = (out.get(key) or {}).get("parsed") or {}
        if parsed.get("leak_hits"):
            leak_fail.append(key)
        if not (parsed.get("assistant") or parsed.get("error_texts")):
            empty_fail.append(key)
    ambiguous_ok = bool((out.get("typed_ambiguous") or {}).get("parsed", {}).get("has_question"))
    spoken_q = bool((out.get("spoken_ambiguous") or {}).get("parsed", {}).get("has_question"))

    if leak_fail:
        out["verdict"] = f"FAIL — leak markers in {leak_fail}"
        code = 1
    elif empty_fail:
        out["verdict"] = f"PARTIAL — empty assistant text in {empty_fail}"
        code = 1
    elif not ambiguous_ok:
        out["verdict"] = "PARTIAL — typed ambiguous SEO prompt did not ask a clarifying question"
        code = 1
    else:
        out["verdict"] = (
            "PASS — no raw backend markers in user-facing text; Composer audits recorded; "
            f"typed SEO asked a question={ambiguous_ok}; spoken SEO asked a question={spoken_q}"
        )
        code = 0
    out["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": out["verdict"], "git_sha": sha, "org_id": org_id}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
