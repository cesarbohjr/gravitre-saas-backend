#!/usr/bin/env python3
"""Live tip: CF soft-rank gate + heuristics HTTP on smoke org.

Writes docs/delivery/phase5-cf-soft-rank-live.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "phase5-cf-soft-rank-live.json"
EXPECTED_SHA_PREFIX = os.environ.get("CF_TIP_SHA_PREFIX", "").strip()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def mint_token() -> str:
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    email = client.auth.admin.get_user_by_id(ACTOR).user.email
    url = os.environ["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def wait_for_deploy(sha_prefix: str, *, timeout_s: int = 900) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        try:
            health = httpx.get(f"{BASE}/health", timeout=30.0).json()
            last = health if isinstance(health, dict) else {"raw": health}
            tip = str(health.get("git_sha") or "")
            if not sha_prefix:
                return {"ok": True, "git_sha": tip, "matched": "any", "health": last}
            if tip.startswith(sha_prefix) or sha_prefix[:7] in tip:
                return {"ok": True, "git_sha": tip, "matched": "sha", "health": last}
        except Exception as exc:  # noqa: BLE001
            last = {"error": exc.__class__.__name__}
        time.sleep(15)
    return {"ok": False, "git_sha": (last or {}).get("git_sha"), "health": last}


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.ml.cf_interaction_ingest import training_gate_status
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    deploy = wait_for_deploy(
        EXPECTED_SHA_PREFIX,
        timeout_s=int(os.environ.get("CF_DEPLOY_WAIT_S", "120")),
    )
    tip_sha = str(deploy.get("git_sha") or "unknown")
    gate = training_gate_status(client, ORG)

    tok = mint_token()
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.get(
            f"{BASE}/api/intelligence/recommendations/heuristics",
            headers=hdr,
            timeout=60.0,
        )
        body = r.json() if r.content else {}
        cards = body.get("recommendations") or []
        advisory = {
            "status_code": r.status_code,
            "card_count": len(cards),
            "cfRanked": body.get("cfRanked"),
            "cfGate": body.get("cfGate"),
            "outcomeRanked": body.get("outcomeRanked"),
            "advisory_only": body.get("advisoryOnly"),
            "sample_ids": [c.get("id") for c in cards[:5]],
            "executable_any": any(
                bool(c.get("executable") or c.get("toolName") or c.get("arguments"))
                for c in cards
            ),
            "error_detail": body.get("detail") if r.status_code >= 400 else None,
        }
    except Exception as exc:  # noqa: BLE001
        advisory = {"status_code": None, "error": exc.__class__.__name__, "card_count": 0}

    http_ok = int(advisory.get("status_code") or 0) == 200
    advisory_ok = (
        http_ok
        and advisory.get("advisory_only") is True
        and advisory.get("executable_any") is not True
    )
    # Cold start is a valid PASS for CF v1 when gate not ready.
    # When gate ready, require cfRanked true.
    if gate.get("ready"):
        cf_ok = advisory.get("cfRanked") is True
        status = "PASS" if (deploy.get("ok") and advisory_ok and cf_ok) else "PARTIAL"
    else:
        cf_ok = advisory.get("cfRanked") is False
        status = "PASS" if (deploy.get("ok") and advisory_ok and cf_ok) else "PARTIAL"
        if status == "PASS":
            status = "PASS_COLD_START"

    artifact = {
        "pass": status.startswith("PASS"),
        "status": status,
        "ran_at": utcnow(),
        "prod_git_sha": tip_sha,
        "org_id": ORG,
        "base_url": BASE,
        "deploy": deploy,
        "gate": gate,
        "advisory": advisory,
        "governance": {
            "advisory_only": True,
            "auto_execute": False,
            "placement": "heuristics → CF soft-rank → dismiss → outcome rank",
            "volume_gate": "≥50 scored interactions / org / 30d",
        },
        "note": (
            "CF v1 soft-rank tip: cold start when gate fails; "
            "cfRanked when ≥50 interactions/30d."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": artifact["pass"],
                "status": status,
                "out": str(OUT),
                "tip": tip_sha,
                "gate_ready": gate.get("ready"),
                "cfRanked": advisory.get("cfRanked"),
                "advisory_status": advisory.get("status_code"),
            },
            indent=2,
        )
    )
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
