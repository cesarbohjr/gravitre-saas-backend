#!/usr/bin/env python3
"""Master-audit evidence closure — isolated org only. No secrets in output."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT_DIR = ROOT / "docs" / "audits"
CHAT_TIMEOUT = 180.0
ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    types: list[str] = []
    tools: list[str] = []
    errors: list[str] = []
    first_text_offset: int | None = None
    for i, block in enumerate(re.split(r"\n\n+", raw)):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            types.append(payload or "empty")
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        et = str(o.get("type") or "")
        types.append(et)
        if et == "text-delta":
            d = str(o.get("delta") or "")
            if d and first_text_offset is None:
                first_text_offset = i
            texts.append(d)
        if et in {"error", "data-error"}:
            errors.append(str(o.get("errorText") or et)[:200])
        name = o.get("toolName") or o.get("name")
        if name and et.startswith("tool"):
            tools.append(str(name))
    return {
        "assistant": "".join(texts).strip()[:2000],
        "event_types": types[:80],
        "tools": tools[:16],
        "errors": errors[:8],
        "text_delta_count": sum(1 for t in types if t == "text-delta"),
    }


def slim_meta(meta: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "action",
        "tool",
        "action_key",
        "fallthrough_reason",
        "fallthroughReason",
        "kind",
        "model",
        "model_id",
        "tier",
        "task_model_tier",
        "provider",
        "latency_breakdown",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "cached_prompt_tokens",
        "input_tokens",
        "output_tokens",
        "ttft_ms",
        "composer_kind",
        "spoken_mode",
        "provider_invoked",
        "plan_id",
        "step_id",
        "success",
        "result_count",
        "retrieval_method",
        "visible_tools",
        "git_sha",
        "outcome_kind",
        "unified_live",
        "path",
    )
    out: dict[str, Any] = {}
    for k in keep:
        if k in meta and meta[k] is not None:
            v = meta[k]
            if k == "latency_breakdown" and isinstance(v, dict):
                compact = {}
                for bk, bv in v.items():
                    if isinstance(bv, (int, float, str, bool)) or bv is None:
                        compact[bk] = bv
                    elif isinstance(bv, dict) and bk == "context_size_breakdown":
                        compact[bk] = {
                            sk: sv
                            for sk, sv in list(bv.items())[:24]
                            if isinstance(sv, (int, float, str, bool))
                        }
                out[k] = compact
            else:
                out[k] = v
    return out


def audit_since(sb: Any, org_id: str, since: str, limit: int = 80) -> list[dict[str, Any]]:
    res = (
        sb.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    rows = []
    for row in res.data or []:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        rows.append(
            {
                "id": str(row.get("id") or "")[:12],
                "action": row.get("action"),
                "created_at": row.get("created_at"),
                "meta": slim_meta(meta),
            }
        )
    return rows


def chat_turn(
    client: httpx.Client,
    headers: dict[str, str],
    org_id: str,
    conv_id: str,
    history: list[dict[str, Any]],
    prompt: str,
) -> dict[str, Any]:
    history.append({"role": "user", "parts": [{"type": "text", "text": prompt}]})
    t0 = time.perf_counter()
    first_text_ms: int | None = None
    buf: list[str] = []
    http_status = 0
    with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers=headers,
        json={
            "messages": history,
            "org_id": org_id,
            "mode": "fast",
            "conversation_id": conv_id,
        },
    ) as resp:
        http_status = resp.status_code
        for piece in resp.iter_text():
            if first_text_ms is None and "text-delta" in piece:
                first_text_ms = int((time.perf_counter() - t0) * 1000)
            buf.append(piece)
    wall_ms = int((time.perf_counter() - t0) * 1000)
    parsed = parse_sse("".join(buf))
    if parsed.get("assistant"):
        history.append(
            {"role": "assistant", "parts": [{"type": "text", "text": parsed["assistant"]}]}
        )
    return {
        "prompt": prompt,
        "http_status": http_status,
        "first_useful_text_ms": first_text_ms,
        "completion_ms": wall_ms,
        "assistant_excerpt": (parsed.get("assistant") or "")[:500],
        "tools": parsed.get("tools"),
        "errors": parsed.get("errors"),
        "text_delta_count": parsed.get("text_delta_count"),
        "event_types_head": (parsed.get("event_types") or [])[:20],
    }


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
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


def count_action(sb: Any, action: str, since: str, org_id: str | None = None) -> int:
    q = sb.table("audit_events").select("id", count="exact").eq("action", action).gte("created_at", since)
    if org_id:
        q = q.eq("org_id", org_id)
    res = q.limit(1).execute()
    return int(getattr(res, "count", 0) or 0)


def fallthrough_sample(sb: Any, since: str, org_id: str) -> dict[str, Any]:
    rows = (
        sb.table("audit_events")
        .select("created_at,metadata,org_id")
        .eq("action", "unified_turn.live.fallthrough")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(400)
        .execute()
        .data
        or []
    )
    reasons = Counter()
    for r in rows:
        md = r.get("metadata") or {}
        reasons[str(md.get("fallthroughReason") or md.get("fallthrough_reason") or "(none)")] += 1
    return {"n": len(rows), "reasons": dict(reasons.most_common(20))}


def outcome_sample(sb: Any, org_id: str, since: str) -> dict[str, Any]:
    try:
        rows = (
            sb.table("intelligence_outcome_events")
            .select("outcome_event,created_at,department")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__, "n": 0}
    c = Counter(str(r.get("outcome_event") or "") for r in rows)
    return {
        "n": len(rows),
        "events": dict(c),
        "latest": [
            {
                "outcome_event": r.get("outcome_event"),
                "created_at": r.get("created_at"),
                "department": r.get("department"),
            }
            for r in rows[:8]
        ],
    }


def connectors(sb: Any, org_id: str) -> list[dict[str, Any]]:
    from app.connectors.repository import list_connectors

    rows = []
    for row in list_connectors(sb, org_id, "production"):
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        err = str(cfg.get("last_error") or cfg.get("error") or "")[:80]
        rows.append(
            {
                "type": row.get("type"),
                "status": row.get("status"),
                "error_class": (
                    "invalid_grant"
                    if "invalid_grant" in err.lower()
                    else ("present" if err else None)
                ),
            }
        )
    return rows


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{BASE}/health", timeout=45).json()
    iso_org, user_id, email = resolve_isolated_conversation_actor(env, sb)
    if iso_org == FORBIDDEN_OPERATOR_ORG_ID or iso_org != ORG:
        raise SystemExit(f"refusing org {iso_org}")

    token = mint(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": iso_org,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    report: dict[str, Any] = {
        "probe": "master_audit_evidence_closure",
        "started_at": utcnow(),
        "health": health,
        "org_id": iso_org,
        "isolated_connectors": connectors(sb, iso_org),
        "fallthrough_24h_isolated": fallthrough_sample(sb, since_24h, iso_org),
        "fallthrough_7d_isolated": fallthrough_sample(sb, since_7d, iso_org),
        "audit_counts_24h_isolated": {
            "unified_turn.live.fallthrough": count_action(
                sb, "unified_turn.live.fallthrough", since_24h, iso_org
            ),
            "classical.answer_path.reached": count_action(
                sb, "classical.answer_path.reached", since_24h, iso_org
            ),
            "tool.invoke.completed": count_action(sb, "tool.invoke.completed", since_24h, iso_org),
            "response.composer.completed": count_action(
                sb, "response.composer.completed", since_24h, iso_org
            ),
        },
        "outcomes_7d_isolated": outcome_sample(sb, iso_org, since_7d),
        "turns": [],
    }

    scenarios = [
        ("cold_greeting", "Hi.", True),
        ("warm_greeting", "Hello again.", False),
        ("general_conversation", "What can you help me with in one sentence?", True),
        ("hubspot_read", "Show my deals.", True),
        ("hubspot_followup", "Only the large ones.", False),
        ("ambiguous", "What should we do about it?", True),
        ("safe_write_clarify", "Send Sarah a summary.", True),
        ("multi_source", "How is the business doing and what should I worry about?", True),
    ]

    with httpx.Client(timeout=CHAT_TIMEOUT) as client:
        conv_id: str | None = None
        history: list[dict[str, Any]] = []
        for i, (sid, prompt, new_conv) in enumerate(scenarios):
            if new_conv or conv_id is None:
                cr = client.post(
                    f"{BASE}/api/conversations",
                    headers={k: v for k, v in headers.items() if k != "Accept"},
                    json={"title": f"audit-closure-{sid}-{uuid.uuid4().hex[:6]}"},
                )
                cr.raise_for_status()
                conv_id = str(cr.json()["id"])
                history = []
            since = (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat()
            turn = chat_turn(client, headers, iso_org, conv_id, history, prompt)
            time.sleep(0.8)
            audits = audit_since(sb, iso_org, since, 60)
            actions = [a.get("action") for a in audits]
            composer = [a for a in audits if a.get("action") == "response.composer.completed"]
            live_ft = [a for a in audits if a.get("action") == "unified_turn.live.fallthrough"]
            classic = [a for a in audits if a.get("action") == "classical.answer_path.reached"]
            invoke = [a for a in audits if a.get("action") == "tool.invoke.completed"]
            lat = [a for a in audits if a.get("action") == "runtime.turn_latency.critical_path"]
            turn.update(
                {
                    "id": sid,
                    "conversation_id": conv_id,
                    "cohort": "cold" if i == 0 or new_conv else "warm_followup",
                    "audit_actions": actions[:30],
                    "fallthrough": [a.get("meta") for a in live_ft[:4]],
                    "classical_reached": bool(classic),
                    "composer": [a.get("meta") for a in composer[:3]],
                    "invokes": [a.get("meta") for a in invoke[:6]],
                    "latency_audit": [a.get("meta") for a in lat[:2]],
                }
            )
            report["turns"].append(turn)

    talk_headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
        "x-org-id": iso_org,
        "X-Org-Id": iso_org,
        "X-Environment": "production",
    }

    def voice_http_turn(client: httpx.Client, prompt: str, conv: str) -> dict[str, Any]:
        first_text = None
        first_audio = None
        complete_ms = None
        types: list[str] = []
        t0 = time.perf_counter()
        status = None
        err = None
        try:
            with client.stream(
                "POST",
                f"{BASE}/api/voice/session/turn",
                headers=talk_headers,
                json={
                    "text": prompt,
                    "conversation_id": conv,
                    "turn_id": str(uuid.uuid4()),
                    "history": [],
                },
                timeout=180,
            ) as vr:
                status = vr.status_code
                for line in vr.iter_lines():
                    if not line:
                        continue
                    ms = int((time.perf_counter() - t0) * 1000)
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    et = str(ev.get("type") or "")
                    if len(types) < 16:
                        types.append(et)
                    if et in {"voice.text.delta", "text-delta"} and first_text is None:
                        first_text = ms
                    if et == "voice.audio.delta" and first_audio is None:
                        first_audio = ms
                    if et == "voice.turn.complete" and complete_ms is None:
                        complete_ms = ms
                        break
        except Exception as exc:  # noqa: BLE001
            err = type(exc).__name__
        return {
            "http_status": status,
            "conversation_id": conv,
            "first_useful_text_ms": first_text,
            "first_audio_ms": first_audio,
            "completion_ms": complete_ms or int((time.perf_counter() - t0) * 1000),
            "event_types_head": types,
            "error": err,
            "proof_class": "HTTP_TALK_NOT_PHYSICAL_MIC",
        }

    with httpx.Client(timeout=CHAT_TIMEOUT) as client:
        cr = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in talk_headers.items() if k != "Accept"},
            json={"title": f"audit-voice-http-{uuid.uuid4().hex[:6]}"},
        )
        cr.raise_for_status()
        vid = str(cr.json()["id"])
        report["voice_http_greeting"] = voice_http_turn(client, "Hi.", vid)
        report["voice_http_tool"] = voice_http_turn(client, "Show my deals.", vid)

    report["finished_at"] = utcnow()
    path = OUT_DIR / "gravitre-evidence-closure-live.json"
    path.write_text(json.dumps(report, indent=2, default=str)[:400000] + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(path),
                "health_sha": health.get("git_sha"),
                "turns": [
                    {
                        "id": t.get("id"),
                        "first_ms": t.get("first_useful_text_ms"),
                        "done_ms": t.get("completion_ms"),
                        "classical": t.get("classical_reached"),
                        "tools": t.get("tools"),
                        "fallthrough": t.get("fallthrough"),
                    }
                    for t in report["turns"]
                ],
                "fallthrough_24h": report["fallthrough_24h_isolated"],
                "outcomes_7d_n": report["outcomes_7d_isolated"].get("n"),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
