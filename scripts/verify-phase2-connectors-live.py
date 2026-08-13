#!/usr/bin/env python3
"""Live proof: Phase 2 six-vendor connector wiring + read invoke when connected.

Primary path (deployed tip): POST /api/internal/ops/phase2-connector-smoke
Writes docs/delivery/phase2-connectors-live.json with git_sha from /health.

Usage:
  python scripts/verify-phase2-connectors-live.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "phase2-connectors-live.json"
DEFAULT_ORG = os.environ.get("OAUTH_SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")

PHASE2_CATALOG_ACTIONS = (
    "linear.issues.list",
    "gitlab.projects.list",
    "shopify.products.list",
    "paypal.payments.list",
    "brevo.contacts.list",
    "meta_marketing.campaigns.list",
)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _local_git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            text=True,
            timeout=10,
        ).strip()
    except Exception:  # noqa: BLE001
        return None


def _health() -> dict:
    try:
        return httpx.get(f"{BASE}/health", timeout=60.0).json()
    except Exception as exc:  # noqa: BLE001
        return {"git_sha": None, "error": f"{exc.__class__.__name__}:{exc}"}


def _sha_prefix_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return a.startswith(b[:12]) or b.startswith(a[:12])


def _resolve_actor(env: dict[str, str], org_id: str) -> str:
    actor = (env.get("OAUTH_SMOKE_ACTOR_ID") or env.get("SMOKE_ACTOR_ID") or "").strip()
    if actor:
        return actor
    try:
        from app.config import get_settings
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(get_settings())
        rows = (
            client.table("organization_members")
            .select("user_id,role")
            .eq("org_id", org_id)
            .limit(20)
            .execute()
            .data
            or []
        )
        admin = next((r for r in rows if str(r.get("role") or "").lower() in {"admin", "owner"}), None)
        return str((admin or (rows[0] if rows else {})).get("user_id") or "")
    except Exception:  # noqa: BLE001
        return ""


def _probe_deployed(*, org_id: str, actor_id: str, secret: str, environment_name: str) -> tuple[dict | None, str | None]:
    try:
        resp = httpx.post(
            f"{BASE}/api/internal/ops/phase2-connector-smoke",
            headers={"X-Internal-Secret": secret},
            json={
                "org_id": org_id,
                "actor_id": actor_id,
                "environment_name": environment_name,
                "invoke_reads": True,
            },
            timeout=180.0,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"http_error:{exc.__class__.__name__}"

    if resp.status_code == 404:
        return None, "endpoint_not_deployed"
    if resp.status_code == 401:
        return None, "invalid_internal_secret"
    if resp.status_code == 503:
        return None, "internal_secret_not_configured"
    if resp.status_code >= 400:
        return None, f"http_{resp.status_code}:{resp.text[:200]}"

    try:
        return resp.json(), None
    except Exception as exc:  # noqa: BLE001
        return None, f"invalid_json:{exc.__class__.__name__}"


def _recent_audit_hits(env: dict[str, str], org_id: str, since_iso: str) -> list[dict]:
    try:
        from app.config import get_settings
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(get_settings())
        rows = (
            client.table("audit_events")
            .select("id,created_at,action,resource_type,resource_id,metadata")
            .eq("org_id", org_id)
            .eq("action", "tool.invoke.completed")
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
            .data
            or []
        )
        phase2_prefixes = {v for v in ("linear", "gitlab", "shopify", "paypal", "brevo", "meta_marketing")}
        hits = []
        for row in rows:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            action = str(meta.get("action") or meta.get("tool") or row.get("resource_id") or "")
            integration = str(meta.get("integration") or "")
            if integration in phase2_prefixes or any(action.startswith(f"{p}.") for p in phase2_prefixes):
                hits.append(
                    {
                        "id": row.get("id"),
                        "created_at": row.get("created_at"),
                        "action": action,
                        "integration": integration or None,
                    }
                )
        return hits
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{exc.__class__.__name__}:{exc}"}]


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    org_id = (env.get("OAUTH_SMOKE_ORG_ID") or DEFAULT_ORG).strip()
    actor_id = _resolve_actor(env, org_id)
    secret = (env.get("INTERNAL_API_SECRET") or "").strip()
    environment_name = (env.get("OAUTH_SMOKE_ENVIRONMENT") or "production").strip()
    started = datetime.now(timezone.utc)

    health = _health()
    deploy_sha = str(health.get("git_sha") or "")
    local_sha = _local_git_sha()
    sha_match = _sha_prefix_match(deploy_sha, local_sha)

    probe: dict | None = None
    probe_error: str | None = None
    mode = "not_run"

    if secret and actor_id:
        probe, probe_error = _probe_deployed(
            org_id=org_id,
            actor_id=actor_id,
            secret=secret,
            environment_name=environment_name,
        )
        mode = "deployed_http" if probe else f"deployed_http_failed:{probe_error}"
    elif not secret:
        mode = "missing_internal_secret"
    else:
        mode = "missing_actor_id"

    audit_hits = _recent_audit_hits(env, org_id, started.isoformat())

    verdict = "NOT RUN"
    if probe:
        verdict = str(probe.get("verdict") or ("PASS" if probe.get("pass") else "FAIL"))
    elif probe_error == "endpoint_not_deployed":
        verdict = "NOT RUN — endpoint not on deployed tip"

    artifact = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "actor_id": actor_id or None,
        "base_url": BASE,
        "mode": mode,
        "deploy_sha": deploy_sha,
        "local_git_sha": local_sha,
        "deploy_sha_match": sha_match,
        "probe_error": probe_error,
        "probe": probe,
        "audit_tool_invoke_completed_since_probe": audit_hits,
        "verdict": verdict,
        "claim": probe.get("claim") if probe else f"NOT RUN — {mode}",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "mode": mode, "out": str(OUT), "deploy_sha": deploy_sha[:12]}, indent=2))

    if verdict.startswith("PASS"):
        return 0
    if verdict.startswith("PARTIAL"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
