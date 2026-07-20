#!/usr/bin/env python3
"""Live verify post-action experience build items on deployed tip.

Evidence: conversation IDs, quoted completion cards, preview, swarm breakdown,
recommendation-on-completion, failure bridge. Suggest-only recs (no new writes).
"""
from __future__ import annotations

import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gravitree_test_client import (  # noqa: E402
    get_service_client,
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = "https://api.gravitre.app"
ENV = "production"
SWARM_ID = "c54ddbe8-ec0b-4f0f-bebc-d6d4389c4c65"
OUT = ROOT / "docs" / "delivery" / "post-action-experience-verify-live.json"


def mint(env, user_id, email):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def req(method, path, token, org_id, body=None, timeout=180):
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("X-Org-Id", org_id)
    r.add_header("X-Environment", ENV)
    for k, v in smoke_http_headers().items():
        r.add_header(k, v)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            try:
                return resp.status, resp.read().decode(errors="replace")
            except Exception as exc:  # IncompleteRead / truncated SSE
                partial = getattr(exc, "partial", b"") or b""
                if isinstance(partial, bytes) and partial:
                    return resp.status, partial.decode(errors="replace")
                raise
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")
    except Exception as exc:
        # Last-resort: bubble IncompleteRead with any partial bytes if present.
        partial = getattr(exc, "partial", None)
        if isinstance(partial, (bytes, bytearray)) and partial:
            return 200, bytes(partial).decode(errors="replace")
        raise


def parse_sse(raw: str):
    texts = []
    er = None
    suggestions = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if not p or p == "[DONE]":
            continue
        try:
            o = json.loads(p)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "text-delta":
            texts.append(o.get("delta") or "")
        if o.get("type") == "data-intelligence":
            d = o.get("data") or {}
            if d.get("executionResult"):
                er = d["executionResult"]
            for s in d.get("proactiveSuggestions") or []:
                if isinstance(s, str):
                    suggestions.append(s)
    return "".join(texts), er, suggestions


def chat(token, org_id, cid, messages):
    _, raw = req(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": messages,
            "org_id": org_id,
            "mode": "agent",
            "conversation_id": cid,
            "tools": ["connector_status"],
        },
    )
    return parse_sse(raw)


def new_conv(token, org_id, title):
    _, raw = req("POST", "/api/conversations", token, org_id, {"org_id": org_id, "title": title})
    return json.loads(raw)["id"]


def health_sha():
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=30) as resp:
            return (json.loads(resp.read().decode()).get("git_sha") or "")[:12]
    except Exception:
        return ""


def main() -> int:
    env = load_env()
    org, uid, email = resolve_test_actor(env)
    org = require_isolated_org(org)
    get_service_client(env)
    token = mint(env, uid, email)
    tip = health_sha()
    report: dict = {
        "probe": "post_action_experience_verify",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": tip,
        "base": BASE,
        "org_id": org,
        "user_id": uid,
        "items": {},
    }

    # --- 1. Verifiable completion card + recommendation ---
    name = f"PostAction-Verify-{uuid.uuid4().hex[:8]}"
    cid = new_conv(token, org, f"post-action card {name}")
    prompt = f"Create a new Apollo contact list named '{name}'. Do not add contacts."
    t1, _, _ = chat(token, org, cid, [{"role": "user", "parts": [{"type": "text", "text": prompt}]}])
    t2, er2 = "", None
    for _attempt in range(2):
        t2, er2, _ = chat(
            token,
            org,
            cid,
            [
                {"role": "user", "parts": [{"type": "text", "text": prompt}]},
                {"role": "assistant", "parts": [{"type": "text", "text": t1}]},
                {"role": "user", "parts": [{"type": "text", "text": "yes"}]},
            ],
        )
        if t2.strip() and (er2 or {}).get("success") is not None:
            break
        time.sleep(2)
    structured = (er2 or {}).get("structured") or {}
    card = structured.get("completionCard") or {}
    rec = (er2 or {}).get("recommendation") or structured.get("recommendation")
    means = (er2 or {}).get("what_this_means") or structured.get("whatThisMeans") or ""
    vendor = (er2 or {}).get("external_url") or card.get("vendorUrl") or ""
    item1 = {
        "conversation_id": cid,
        "list_name": name,
        "assistant_quote": t2[:900],
        "has_what_this_means": bool(means) or "what this means" in t2.lower(),
        "has_vendor_http_link": "https://app.apollo.io" in t2 or str(vendor).startswith("http"),
        "vendor_url": vendor,
        "has_recommendation": bool(rec) or "look at next" in t2.lower(),
        "recommendation": rec,
        "completion_card": card,
        "execution_success": (er2 or {}).get("success"),
    }
    item1["verdict"] = (
        "PASS"
        if item1["has_what_this_means"]
        and item1["has_vendor_http_link"]
        and item1["has_recommendation"]
        and item1["execution_success"]
        else "FAIL"
    )
    report["items"]["completion_card_and_recommendation"] = item1

    # --- 2. Inline preview ---
    t3, er3, _ = chat(
        token,
        org,
        cid,
        [
            {"role": "user", "parts": [{"type": "text", "text": prompt}]},
            {"role": "assistant", "parts": [{"type": "text", "text": t1}]},
            {"role": "user", "parts": [{"type": "text", "text": "yes"}]},
            {"role": "assistant", "parts": [{"type": "text", "text": t2}]},
            {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "Show me the live Apollo list you just created — name, id, and contact count.",
                    }
                ],
            },
        ],
    )
    preview_ok = (
        "live apollo preview" in t3.lower()
        or "contact count" in t3.lower()
        or bool(((er3 or {}).get("structured") or {}).get("inlinePreview"))
    ) and name.lower() in t3.lower()
    item2 = {
        "conversation_id": cid,
        "assistant_quote": t3[:900],
        "inline_preview": bool(((er3 or {}).get("structured") or {}).get("inlinePreview")),
        "mentions_list_name": name.lower() in t3.lower(),
        "verdict": "PASS" if preview_ok else "FAIL",
    }
    report["items"]["inline_preview"] = item2

    # --- 3. Swarm step transparency ---
    scid = new_conv(token, org, "post-action swarm transparency")
    swarm_prompt = (
        f"Summarize swarm run {SWARM_ID} with step-level breakdown — "
        "what Sales found vs what Marketing found, with evidence for each agent."
    )
    st, ser, _ = chat(
        token,
        org,
        scid,
        [{"role": "user", "parts": [{"type": "text", "text": swarm_prompt}]}],
    )
    swarm_ok = (
        "sales" in st.lower()
        and "marketing" in st.lower()
        and ("step-level" in st.lower() or "each agent" in st.lower() or "###" in st)
    )
    item3 = {
        "conversation_id": scid,
        "swarm_id": SWARM_ID,
        "assistant_quote": st[:1200],
        "shows_sales_and_marketing": "sales" in st.lower() and "marketing" in st.lower(),
        "execution_entity": (ser or {}).get("entity_type"),
        "verdict": "PASS" if swarm_ok else "FAIL",
    }
    report["items"]["swarm_step_transparency"] = item3

    # --- 4. Failure-to-action bridge ---
    fcid = new_conv(token, org, "post-action failure bridge")
    fail_prompt = "Create a Zendesk ticket titled 'Post-action failure bridge probe' with body 'test'."
    ft, fer, _ = chat(
        token,
        org,
        fcid,
        [{"role": "user", "parts": [{"type": "text", "text": fail_prompt}]}],
    )
    bridge = (fer or {}).get("failure_bridge") or ((fer or {}).get("structured") or {}).get(
        "failureBridge"
    )
    fail_ok = (
        "zendesk" in ft.lower()
        and ("/connectors" in ft.lower() or "connect" in ft.lower())
        and ("yes" in ft.lower() or bool(bridge))
    )
    item4 = {
        "conversation_id": fcid,
        "assistant_quote": ft[:700],
        "failure_bridge": bridge,
        "verdict": "PASS" if fail_ok else "FAIL",
    }
    report["items"]["failure_bridge"] = item4

    # Confirm no executable surface in recommendation
    if rec:
        banned = {"toolName", "tool_name", "arguments", "approvalId", "executeUrl", "invoke_tool"}
        report["items"]["recommendation_suggest_only"] = {
            "advisoryOnly": bool(rec.get("advisoryOnly")),
            "has_banned_keys": bool(banned.intersection(rec.keys())),
            "verdict": (
                "PASS"
                if rec.get("advisoryOnly") and not banned.intersection(rec.keys())
                else "FAIL"
            ),
        }

    verdicts = {k: v.get("verdict") for k, v in report["items"].items()}
    report["verdicts"] = verdicts
    report["overall"] = (
        "PASS" if all(v == "PASS" for v in verdicts.values()) else "FAIL"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "verdicts": verdicts, "git_sha": tip, "out": str(OUT)}, indent=2))
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
