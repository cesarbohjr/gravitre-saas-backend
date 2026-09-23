#!/usr/bin/env python3
"""Independent acceptance probes on live production. Audit only. Isolated org."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location("evc", ROOT / "scripts" / "audit-evidence-closure.py")
evc = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(evc)

OUT = ROOT / "docs" / "audits" / "gravitre-independent-acceptance-d90b2838-live.json"
CANVAS = "cdda7de2-bfbb-4cc7-b490-842fb5e7df84"
CIM = "5f7f9ef6-64d9-4029-ad6c-cfb73f750374"
EXPECT_SHA = "d90b283800c1f446ee4181fd64ed5b8bfbb46030"


def _headers(token: str, iso_org: str) -> dict:
    return {
        **evc.smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": iso_org,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }


def _new_conv(client, headers) -> str:
    last = None
    for attempt in range(5):
        cr = client.post(
            f"{evc.BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"ia-{uuid.uuid4().hex[:6]}"},
        )
        last = cr
        if cr.status_code < 500:
            cr.raise_for_status()
            return str(cr.json()["id"])
        time.sleep(2.0 * (attempt + 1))
    if last is not None:
        last.raise_for_status()
    raise RuntimeError("conversation create failed")


def _chat_turn_retry(client, headers, iso_org, conv, history, prompt: str, attempts: int = 3) -> dict:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return evc.chat_turn(client, headers, iso_org, conv, history, prompt)
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise last or RuntimeError("chat_turn failed")


def _dump(out: dict) -> None:
    OUT.write_text(json.dumps(out, indent=2, default=str)[:200000] + "\n", encoding="utf-8")


def _turn_pack(client, headers, iso_org, sb, prompt: str, *, yes: str | None = None) -> dict:
    conv = _new_conv(client, headers)
    history: list = []
    since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    turn = _chat_turn_retry(client, headers, iso_org, conv, history, prompt)
    yes_turn = None
    if yes:
        time.sleep(0.6)
        try:
            yes_turn = _chat_turn_retry(client, headers, iso_org, conv, history, yes)
        except Exception as exc:  # noqa: BLE001
            yes_turn = {"assistant_excerpt": "", "error": f"{type(exc).__name__}: {exc}"}
        time.sleep(3.5)
    else:
        time.sleep(0.6)
    audits = evc.audit_since(sb, iso_org, since, 120)
    return {
        "prompt": prompt,
        "conversation_id": conv,
        "http": turn.get("http_status"),
        "first_ms": turn.get("first_useful_text_ms"),
        "completion_ms": turn.get("completion_ms"),
        "excerpt": (turn.get("assistant_excerpt") or "")[:700],
        "yes_excerpt": ((yes_turn or {}).get("assistant_excerpt") or "")[:700] if yes_turn else None,
        "yes_ms": (yes_turn or {}).get("first_useful_text_ms") if yes_turn else None,
        "actions": [a.get("action") for a in audits[:40]],
        "invokes": [
            {
                "action": a.get("action"),
                "created_at": a.get("created_at"),
                "meta": a.get("meta") or {},
            }
            for a in audits
            if a.get("action") in {"tool.invoke.completed", "tool.invoke.failed"}
        ][:8],
        "latency": [
            a
            for a in audits
            if a.get("action") == "runtime.turn_latency.critical_path"
        ][:3],
        "child_obs": [
            {"created_at": a.get("created_at"), "meta": a.get("meta")}
            for a in audits
            if a.get("action") == "workflow.child.observation"
        ][:8],
        "execute_completed": [a.get("created_at") for a in audits if a.get("action") == "workflow.execute.completed"][:3],
        "execute_failed": [a.get("created_at") for a in audits if a.get("action") == "workflow.execute.failed"][:3],
        "pending_approval": [a.get("created_at") for a in audits if a.get("action") == "workflow.execute.pending_approval"][:3],
        "react": [a.get("action") for a in audits if a.get("action") in {"inference.tool_completion", "agent.react.iteration", "unified_turn.live.completed"}],
        "composer": [
            {"created_at": a.get("created_at"), "kind": (a.get("meta") or {}).get("kind")}
            for a in audits
            if a.get("action") == "response.composer.completed"
        ][:6],
    }


def main() -> int:
    env = evc.load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{evc.BASE}/health", timeout=45).json()
    sha = str(health.get("git_sha") or "")
    iso_org, user_id, email = evc.resolve_isolated_conversation_actor(env, sb)
    token = evc.mint(env, user_id, email)
    headers = _headers(token, iso_org)
    canvas = (
        sb.table("workflow_runs")
        .select("id,status,approval_status,trigger_type,created_at")
        .eq("id", CANVAS)
        .limit(1)
        .execute()
        .data
        or []
    )
    cim = (
        sb.table("workflow_runs")
        .select("id,status,approval_status,trigger_type,created_at,error_message")
        .eq("id", CIM)
        .limit(1)
        .execute()
        .data
        or []
    )
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    p6_bias = (
        sb.table("audit_events")
        .select("id,action,created_at")
        .eq("org_id", iso_org)
        .ilike("action", "%business%")
        .gte("created_at", since_7d)
        .limit(20)
        .execute()
        .data
        or []
    )
    out: dict = {
        "audit": "independent-acceptance",
        "expect_sha": EXPECT_SHA,
        "health_sha": sha,
        "sha_match": sha == EXPECT_SHA,
        "health": {
            k: health.get(k)
            for k in (
                "git_sha",
                "timestamp",
                "unified_turn_live_enabled",
                "unified_turn_task_model_tier",
                "convergence_p1_single_selection_v1",
                "environment",
            )
        },
        "org_id": iso_org,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canvas_untouched": canvas[0] if canvas else None,
        "cim_untouched": cim[0] if cim else None,
        "p6_business_audit_sample": p6_bias[:10],
    }
    if sha != EXPECT_SHA:
        OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2)[:4000])
        return 2

    with httpx.Client(timeout=180) as client:
        out["greeting"] = _turn_pack(client, headers, iso_org, sb, "Hi.")
        _dump(out)
        out["deals"] = _turn_pack(client, headers, iso_org, sb, "Show my deals.")
        _dump(out)
        out["ceo_exact"] = _turn_pack(
            client, headers, iso_org, sb, "How is the business doing and what should I worry about?"
        )
        _dump(out)
        out["company"] = _turn_pack(client, headers, iso_org, sb, "How is my company doing?")
        _dump(out)
        out["company_contraction"] = _turn_pack(client, headers, iso_org, sb, "How's the company doing?")
        _dump(out)
        out["snapshot"] = _turn_pack(
            client, headers, iso_org, sb, "Give me a business performance snapshot from connected systems."
        )
        _dump(out)
        out["sarah"] = _turn_pack(client, headers, iso_org, sb, "Send Sarah a summary.")
        _dump(out)
        out["alpha"] = _turn_pack(
            client,
            headers,
            iso_org,
            sb,
            "Run the workflow named Operator Execution Probe Alpha (noop) in this conversation now.",
            yes="yes",
        )
        _dump(out)
        out["beta"] = _turn_pack(
            client,
            headers,
            iso_org,
            sb,
            "Run the workflow named Operator Execution Probe Beta (noop) in this conversation now.",
            yes="yes",
        )
        _dump(out)
        out["canvas"] = _turn_pack(
            client,
            headers,
            iso_org,
            sb,
            "Run the workflow named Canvas Write Governance Probe (no approval node) in this conversation now.",
            yes="yes",
        )
        _dump(out)
        # J008
        conv2 = _new_conv(client, headers)
        history2: list = []
        text_turn = _chat_turn_retry(client, headers, iso_org, conv2, history2, "Hi.")
        talk_headers = {
            **evc.smoke_http_headers(),
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/x-ndjson",
            "x-org-id": iso_org,
            "X-Org-Id": iso_org,
            "X-Environment": "production",
        }
        first_text = None
        first_audio = None
        types = []
        t0 = time.perf_counter()
        with client.stream(
            "POST",
            f"{evc.BASE}/api/voice/session/turn",
            headers=talk_headers,
            json={
                "text": "Continue in this same conversation.",
                "conversation_id": conv2,
                "turn_id": str(uuid.uuid4()),
                "history": [],
            },
            timeout=180,
        ) as vr:
            for line in vr.iter_lines():
                if not line:
                    continue
                ms = int((time.perf_counter() - t0) * 1000)
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                et = str(ev.get("type") or "")
                if len(types) < 12:
                    types.append(et)
                if et in {"voice.text.delta", "text-delta"} and first_text is None:
                    first_text = ms
                if et == "voice.audio.delta" and first_audio is None:
                    first_audio = ms
                if et == "voice.turn.complete":
                    break
        out["j008"] = {
            "conversation_id": conv2,
            "text_hi": text_turn.get("assistant_excerpt"),
            "spoken_first_text_ms": first_text,
            "spoken_first_audio_ms": first_audio,
            "spoken_types": types,
        }

    OUT.write_text(json.dumps(out, indent=2, default=str)[:200000] + "\n", encoding="utf-8")
    print(json.dumps({k: out.get(k) for k in ("health_sha", "sha_match", "org_id")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
