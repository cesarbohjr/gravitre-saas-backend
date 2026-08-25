"""Live proof: Phase 3 capability recipe list + org-connected resolve."""
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
OUT = REPO / "docs" / "delivery" / "capability-recipes-live.json"
BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
DEFAULT_ORG = os.environ.get("OAUTH_SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if path.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(path).items() if v})
            except UnicodeDecodeError:
                pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _local_git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO), text=True, timeout=10
        ).strip()
    except Exception:  # noqa: BLE001
        return None


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


def main() -> int:
    env = _load_env()
    org_id = (env.get("OAUTH_SMOKE_ORG_ID") or DEFAULT_ORG).strip()
    actor_id = _resolve_actor(env, org_id)
    secret = (env.get("INTERNAL_API_SECRET") or "").strip()
    health = httpx.get(f"{BASE}/health", timeout=60.0).json()
    deploy_sha = str(health.get("git_sha") or "")
    probe = None
    probe_error = None
    mode = "not_run"
    if secret and actor_id:
        try:
            resp = httpx.post(
                f"{BASE}/api/internal/ops/capability-recipes-smoke",
                headers={"X-Internal-Secret": secret},
                json={
                    "org_id": org_id,
                    "actor_id": actor_id,
                    "environment_name": env.get("OAUTH_SMOKE_ENVIRONMENT") or "production",
                },
                timeout=120.0,
            )
            if resp.status_code == 404:
                probe_error = "endpoint_not_deployed"
            elif resp.status_code >= 400:
                probe_error = f"http_{resp.status_code}:{resp.text[:200]}"
            else:
                probe = resp.json()
                mode = "deployed_http"
        except Exception as exc:  # noqa: BLE001
            probe_error = f"{exc.__class__.__name__}:{exc}"
    elif not secret:
        mode = "missing_internal_secret"
    else:
        mode = "missing_actor_id"

    verdict = str(probe.get("verdict") or "NOT RUN") if probe else f"NOT RUN — {mode}"
    artifact = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "org_id": org_id,
        "deploy_sha": deploy_sha,
        "local_git_sha": _local_git_sha(),
        "mode": mode,
        "probe_error": probe_error,
        "probe": probe,
        "verdict": verdict,
        "claim": probe.get("claim") if probe else f"NOT RUN — {mode}",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "out": str(OUT)}, indent=2))
    return 0 if str(verdict).startswith(("PASS", "PARTIAL")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
