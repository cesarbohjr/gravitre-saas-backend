#!/usr/bin/env python3
"""EV-J-007 / EV-J-008 live probes on isolated org. Not a new master audit."""
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

spec = importlib.util.spec_from_file_location(
    "evc", ROOT / "scripts" / "audit-evidence-closure.py"
)
evc = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(evc)

ORG = evc.ORG
BASE = evc.BASE


def main() -> int:
    env = evc.load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{BASE}/health", timeout=45).json()
    iso_org, user_id, email = evc.resolve_isolated_conversation_actor(env, sb)
    token = evc.mint(env, user_id, email)
    headers = {
        **evc.smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": iso_org,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    out: dict = {"health_sha": health.get("git_sha"), "org_id": iso_org}

    wfs = (
        sb.table("workflows")
        .select("id,name")
        .eq("org_id", iso_org)
        .limit(8)
        .execute()
        .data
        or []
    )
    out["workflows"] = [{"id": w.get("id"), "name": w.get("name")} for w in wfs]
    canvas = next(
        (w for w in wfs if "canvas write" in str(w.get("name") or "").lower()),
        None,
    )
    pick = canvas or (wfs[0] if wfs else {})
    name = str(pick.get("name") or "").strip()

    with httpx.Client(timeout=180) as client:
        cr = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"gap-j007-{uuid.uuid4().hex[:6]}"},
        )
        cr.raise_for_status()
        conv = str(cr.json()["id"])
        history: list = []
        prompt = (
            f"Run the workflow named {name} in this conversation now."
            if name
            else "Start a workflow from chat for this conversation."
        )
        since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        turn = evc.chat_turn(client, headers, iso_org, conv, history, prompt)
        time.sleep(0.8)
        yes = evc.chat_turn(client, headers, iso_org, conv, history, "yes")
        time.sleep(1.5)
        audits = evc.audit_since(sb, iso_org, since, 120)
        child = [a for a in audits if a.get("action") == "workflow.child.observation"]
        composer = [
            a
            for a in audits
            if a.get("action") == "response.composer.completed"
            and (a.get("meta") or {}).get("kind") == "workflow_waiting"
        ]
        invoke = [
            a
            for a in audits
            if a.get("action") in {"tool.invoke.completed", "assistant.execute_workflow"}
        ]
        out["j007"] = {
            "conversation_id": conv,
            "prompt": prompt,
            "assistant": turn.get("assistant_excerpt"),
            "yes_assistant": yes.get("assistant_excerpt"),
            "first_ms": turn.get("first_useful_text_ms"),
            "yes_ms": yes.get("first_useful_text_ms"),
            "child_obs": child[:4],
            "workflow_waiting": composer[:3],
            "invokes": invoke[:6],
            "audit_head": [a.get("action") for a in audits[:30]],
        }

        cr2 = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"gap-j008-{uuid.uuid4().hex[:6]}"},
        )
        cr2.raise_for_status()
        conv2 = str(cr2.json()["id"])
        history2: list = []
        text_turn = evc.chat_turn(client, headers, iso_org, conv2, history2, "Hi.")
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
            f"{BASE}/api/voice/session/turn",
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

    path = ROOT / "docs" / "audits" / "gravitre-gap-j007-j008-live.json"
    path.write_text(json.dumps(out, indent=2, default=str)[:80000] + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
