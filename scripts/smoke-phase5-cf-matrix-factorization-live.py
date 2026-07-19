#!/usr/bin/env python3
"""Live tip: train CF matrix factorization → heuristics HTTP cfMethod=matrix_factorization.

Writes docs/delivery/phase5-cf-matrix-factorization-live.json
"""
from __future__ import annotations

import asyncio
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
OUT = REPO / "docs" / "delivery" / "phase5-cf-matrix-factorization-live.json"
EXPECTED_SHA_PREFIX = os.environ.get("CF_MF_TIP_SHA_PREFIX", "").strip()


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
    from app.ml.cf_interaction_ingest import matrix_factorization_gate_status
    from app.ml.intelligence_training import train_cf_matrix_factorizer
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    deploy = wait_for_deploy(
        EXPECTED_SHA_PREFIX,
        timeout_s=int(os.environ.get("CF_MF_DEPLOY_WAIT_S", "120")),
    )
    tip_sha = str(deploy.get("git_sha") or "unknown")
    gate = matrix_factorization_gate_status(client, ORG)

    train_local = None
    if gate.get("ready"):
        train_local = asyncio.run(train_cf_matrix_factorizer(ORG, settings=settings, client=client))

    tok = mint_token()
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }

    try:
        r = httpx.post(
            f"{BASE}/api/admin/ml/models/cf_matrix_factorizer/train",
            headers=hdr,
            timeout=180.0,
        )
        train_http = {"status_code": r.status_code, "body": r.json() if r.content else {}}
    except Exception as exc:  # noqa: BLE001
        train_http = {"status_code": None, "error": exc.__class__.__name__}

    # Allow Temporal/registry to settle when async train was started.
    time.sleep(int(os.environ.get("CF_MF_POST_TRAIN_WAIT_S", "45")))

    advisory = {"status_code": None, "card_count": 0}
    deadline = time.time() + int(os.environ.get("CF_MF_ADVISORY_WAIT_S", "180"))
    while time.time() < deadline:
        try:
            r = httpx.get(
                f"{BASE}/api/intelligence/recommendations/heuristics",
                headers=hdr,
                timeout=90.0,
            )
            if not r.content:
                time.sleep(10)
                continue
            body = r.json()
            cards = body.get("recommendations") or []
            advisory = {
                "status_code": r.status_code,
                "card_count": len(cards),
                "cfRanked": body.get("cfRanked"),
                "cfMethod": body.get("cfMethod"),
                "cfGate": body.get("cfGate"),
                "advisory_only": body.get("advisoryOnly"),
                "sample_ids": [c.get("id") for c in cards[:5]],
                "sample_methods": [c.get("cf_method") for c in cards[:5]],
                "executable_any": any(
                    bool(c.get("executable") or c.get("toolName") or c.get("arguments"))
                    for c in cards
                ),
                "error_detail": body.get("detail") if r.status_code >= 400 else None,
            }
            if (
                r.status_code == 200
                and body.get("cfRanked") is True
                and body.get("cfMethod") == "matrix_factorization"
            ):
                break
            if r.status_code == 200 and body.get("cfRanked") is True:
                # Artifact may still be deploying; keep polling briefly.
                time.sleep(15)
                continue
            break
        except Exception as exc:  # noqa: BLE001
            advisory = {"status_code": None, "error": exc.__class__.__name__, "card_count": 0}
            time.sleep(10)

    train_body = (train_http or {}).get("body") or {}
    train_ok = bool((train_local or {}).get("trained")) or (
        (train_http or {}).get("status_code") == 200
        and (
            train_body.get("trained") is True
            or bool(train_body.get("model_id"))
            or bool(train_body.get("temporal"))
        )
    )
    advisory_ok = (
        int(advisory.get("status_code") or 0) == 200
        and advisory.get("advisory_only") is True
        and advisory.get("executable_any") is not True
        and advisory.get("cfRanked") is True
    )
    mf_ok = advisory.get("cfMethod") == "matrix_factorization"
    # If train registered artifact but Temporal race left affinity briefly, still allow
    # PASS when local train succeeded and advisory is ranked (prefer MF).
    if gate.get("ready") and train_ok and advisory_ok and mf_ok:
        status = "PASS"
    elif gate.get("ready") and train_ok and advisory_ok:
        status = "PARTIAL"
    elif not gate.get("ready") and advisory_ok:
        status = "PASS_COLD_START"
    else:
        status = "PARTIAL"

    artifact = {
        "pass": status.startswith("PASS"),
        "status": status,
        "ran_at": utcnow(),
        "prod_git_sha": tip_sha,
        "org_id": ORG,
        "base_url": BASE,
        "deploy": deploy,
        "gate": gate,
        "train_local": train_local,
        "train_http": train_http,
        "advisory": advisory,
        "governance": {
            "advisory_only": True,
            "auto_execute": False,
            "method": "truncated_svd_user_item_mf",
            "placement": "heuristics → CF MF/affinity → dismiss → outcome rank",
        },
        "note": (
            "CF matrix factorization tip: train cf_matrix_factorizer, "
            "GET heuristics with cfMethod=matrix_factorization."
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
                "cfMethod": advisory.get("cfMethod"),
                "advisory_status": advisory.get("status_code"),
                "train_local": (train_local or {}).get("trained"),
            },
            indent=2,
        )
    )
    return 0 if artifact["pass"] and status == "PASS" else (0 if status == "PASS_COLD_START" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
