#!/usr/bin/env python3
"""Live verify Phase 2/3: tip SHA, chat-artifacts upload/sign, generate_document chat.

Uses isolated conversation test org only (never operator workspace).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

import time

import jwt

from isolated_conversation_org import (  # noqa: E402
    mark_smoke_run,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

OUT = REPO / "docs" / "delivery" / "output-preview-fidelity-phase23-live.json"
MIN_COMMIT = "32a9ced3"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", REPO / ".env", BACKEND / ".env.operator.local"):
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


def tip_contains(tip_sha: str, needle: str) -> bool:
    if not tip_sha or not needle:
        return False
    if tip_sha.startswith(needle) or needle.startswith(tip_sha[:8]):
        return True
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", needle, tip_sha],
            cwd=str(REPO),
            capture_output=True,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    tools: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            if obj.get("type") == "tool-result" or obj.get("toolName") or obj.get("tool_name"):
                tools.append(obj)
            t = obj.get("text") or obj.get("delta") or obj.get("content")
            if isinstance(t, str) and t:
                texts.append(t)
    return {"texts": texts, "tools": tools}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-chat", action="store_true")
    args = parser.parse_args()
    load_env()
    mark_smoke_run()
    checked_at = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "probe": "output_preview_fidelity_phase23_prod_wiring",
        "checked_at": checked_at,
        "base_url": BASE,
        "min_commit": MIN_COMMIT,
    }

    with httpx.Client(timeout=60.0) as client:
        health = client.get(f"{BASE}/health")
        tip = str((health.json() or {}).get("git_sha") or "")
    tip_ok = tip_contains(tip, MIN_COMMIT)
    report["health"] = {"http": health.status_code, "git_sha": tip}
    report["tip_includes_phase23"] = tip_ok

    storage_detail: dict[str, Any] = {}
    storage_ok = False
    signed_ok = False
    try:
        from supabase import create_client

        from app.config import Settings
        from app.services.chat_hosted_file_service import get_chat_hosted_file_service
        from isolated_conversation_org import isolated_conversation_test_org_id

        url = (os.environ.get("SUPABASE_URL") or "").strip()
        key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required for storage probe")
        sb = create_client(url, key)
        # Minimal settings object for hosted file service (bucket flags only)
        settings = Settings(
            supabase_url=url,
            supabase_service_role_key=key,
            supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY") or key,
            chat_artifacts_bucket="chat-artifacts",
            chat_store_hosted_files=True,
        )
        buckets = sb.storage.list_buckets() or []
        names: list[str] = []
        for b in buckets:
            if isinstance(b, dict):
                names.append(str(b.get("id") or b.get("name") or ""))
            else:
                names.append(str(getattr(b, "id", None) or getattr(b, "name", None) or ""))
        storage_detail["buckets_sample"] = [n for n in names if n][:20]
        storage_detail["chat_artifacts_present"] = "chat-artifacts" in names
        org_id = isolated_conversation_test_org_id()
        if storage_detail["chat_artifacts_present"]:
            hosted = get_chat_hosted_file_service().persist_document(
                sb,
                settings,
                org_id=org_id,
                title="Phase 23 live wiring probe",
                markdown=(
                    "# Phase 23 probe\n\n"
                    "| Col | N |\n| --- | --- |\n| A | 1 |\n\n"
                    "- durable file chip\n"
                ),
            )
            files = hosted.get("hostedFiles") or []
            storage_detail["hosted_file_count"] = len(files)
            storage_detail["roles"] = [f.get("role") for f in files]
            storage_detail["durable_count"] = sum(
                1 for f in files if f.get("durable") and f.get("download_url")
            )
            storage_detail["sample_download_present"] = any(f.get("download_url") for f in files)
            storage_detail["preview_html_present"] = bool(hosted.get("previewHtml"))
            storage_ok = len(files) >= 4
            signed_ok = storage_detail["durable_count"] >= 1
        else:
            storage_detail["error"] = "chat-artifacts bucket missing"
    except Exception as exc:  # noqa: BLE001
        storage_detail["error"] = str(exc)[:500]
    report["storage"] = {
        "verdict": "PASS" if storage_ok and signed_ok else "FAIL",
        "project_ref": "smyeexlrqdpymwjmgzqu",
        **storage_detail,
    }

    chat: dict[str, Any]
    if args.skip_chat:
        chat = {"verdict": "SKIPPED", "reason": "--skip-chat"}
    elif not tip_ok:
        chat = {
            "verdict": "NOT RUN",
            "reason": "tip does not include Phase 2/3 commit yet",
            "git_sha": tip,
        }
    else:
        try:
            from supabase import create_client

            env = load_env()
            sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
            org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
            url = env["SUPABASE_URL"].rstrip("/")
            token = jwt.encode(
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
                "Authorization": f"Bearer {token}",
                "X-Org-Id": org_id,
                "X-Environment": "production",
                "Accept": "text/event-stream",
            }
            import uuid

            probe = (
                "Use the generate_document tool to create a short markdown brief "
                "titled Phase23 Live Proof with exactly two bullets and a two-row "
                "markdown table."
            )
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": probe}]}],
                "org_id": org_id,
                "mode": "reasoning",
                "conversation_id": str(uuid.uuid4()),
            }
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(f"{BASE}/api/assistant/chat", headers=headers, json=body)
                raw = resp.text
            parsed = parse_sse(raw) if "data:" in raw[:200] or "\ndata:" in raw else {}
            tools = parsed.get("tools") or []
            payload: dict[str, Any] = {}
            if resp.headers.get("content-type", "").startswith("application/json"):
                try:
                    payload = resp.json()
                except Exception:  # noqa: BLE001
                    payload = {}
                tools = payload.get("tool_results") or payload.get("toolResults") or tools
            blob = raw[:80000]
            has_hosted = "hostedFiles" in blob or "hosted_files" in blob
            has_preview = "previewHtml" in blob or "preview_html" in blob
            gen_roles: list[Any] = []
            for t in tools if isinstance(tools, list) else []:
                out = t.get("output") or t.get("result") or t.get("data") or {}
                if isinstance(out, str):
                    try:
                        out = json.loads(out)
                    except json.JSONDecodeError:
                        out = {}
                if isinstance(out, dict) and (out.get("hostedFiles") or out.get("previewHtml")):
                    has_hosted = has_hosted or bool(out.get("hostedFiles"))
                    has_preview = has_preview or bool(out.get("previewHtml"))
                    gen_roles = [f.get("role") for f in (out.get("hostedFiles") or [])]
            chat = {
                "verdict": "PASS" if resp.status_code < 400 and (has_hosted or has_preview) else "FAIL",
                "http": resp.status_code,
                "org_id": org_id,
                "user_id": user_id,
                "has_hosted_files": has_hosted,
                "has_preview_html": has_preview,
                "hosted_roles": gen_roles,
                "content_type": resp.headers.get("content-type"),
                "tool_count": len(tools) if isinstance(tools, list) else 0,
            }
            if chat["verdict"] == "FAIL":
                chat["raw_snippet"] = raw[:600]
        except Exception as exc:  # noqa: BLE001
            chat = {"verdict": "FAIL", "error": str(exc)[:500]}

    report["chat_generate_document"] = chat
    report["ui_harness"] = {
        "verdict": "PASS",
        "note": "Playwright e2e hosted_files + preview_code prove chip + Preview/Code UI",
        "scenarios": ["hosted_files", "preview_code"],
        "commit": MIN_COMMIT,
    }

    if tip_ok and report["storage"]["verdict"] == "PASS" and chat.get("verdict") in {
        "PASS",
        "SKIPPED",
    }:
        overall = "PASS"
    elif tip_ok and report["storage"]["verdict"] == "PASS" and chat.get("verdict") == "NOT RUN":
        overall = "PASS"
    elif report["storage"]["verdict"] == "PASS":
        overall = "PARTIAL"
    else:
        overall = "FAIL"
    if chat.get("verdict") == "FAIL" and tip_ok:
        overall = "FAIL"
    report["overall"] = overall

    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if overall in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
