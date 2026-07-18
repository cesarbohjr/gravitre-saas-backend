#!/usr/bin/env python3
"""Live tip: seed ≥30 churn labels → train → advisory HTTP on smoke org.

Writes docs/delivery/phase5-churn-ml-live.json
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
OUT = REPO / "docs" / "delivery" / "phase5-churn-ml-live.json"
N_LABELS = 32
EXPECTED_SHA_PREFIX = os.environ.get("CHURN_TIP_SHA_PREFIX", "").strip()


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
            if sha_prefix and (tip.startswith(sha_prefix) or sha_prefix[:7] in tip):
                return {"ok": True, "git_sha": tip, "matched": "sha", "health": last}
            probe = httpx.get(f"{BASE}/api/intelligence/churn-risk/advisory", timeout=30.0)
            if probe.status_code != 404:
                if not sha_prefix:
                    return {
                        "ok": True,
                        "git_sha": tip,
                        "matched": "route",
                        "probe_status": probe.status_code,
                        "health": last,
                    }
                # When pinning SHA, keep waiting until SHA matches (route may be old).
                if tip.startswith(sha_prefix) or (sha_prefix[:7] and sha_prefix[:7] in tip):
                    return {
                        "ok": True,
                        "git_sha": tip,
                        "matched": "sha+route",
                        "probe_status": probe.status_code,
                        "health": last,
                    }
        except Exception as exc:  # noqa: BLE001
            last = {"error": exc.__class__.__name__}
        time.sleep(15)
    return {"ok": False, "git_sha": (last or {}).get("git_sha"), "health": last}


def seed_labels(client) -> dict:
    from app.ml.churn_feature_ingest import (
        count_labeled_churn_examples,
        upsert_churn_training_example,
    )

    before = count_labeled_churn_examples(client, ORG)
    upserted = 0
    for i in range(N_LABELS):
        churned = i % 3 != 0
        features = {
            "days_since_last_activity": float(10 + (i * 7) % 120),
            "open_support_tickets": float(i % 6),
            "failed_payments_30d": float(1 if churned and i % 2 == 0 else 0),
            "deal_stage_regressions": float(i % 4),
            "email_engagement_score": float(max(0.05, 0.9 - (0.02 * i))),
        }
        upsert_churn_training_example(
            client,
            org_id=ORG,
            customer_id=f"smoke-churn-acct-{i:03d}",
            features=features,
            churned=churned,
            label_reason="closed_lost" if churned else "retained",
            agent_id=ACTOR,
        )
        upserted += 1
    after = count_labeled_churn_examples(client, ORG)
    return {"before": before, "upserted": upserted, "after": after, "gate_ready": after >= 30}


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.ml.churn_feature_ingest import training_gate_status
    from app.ml.intelligence_training import train_churn_risk_scorer
    from app.services.churn_advisory_service import build_churn_advisory_cards
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    wait_s = int(os.environ.get("CHURN_DEPLOY_WAIT_S", "900"))
    deploy = wait_for_deploy(EXPECTED_SHA_PREFIX, timeout_s=wait_s)
    tip_sha = str(deploy.get("git_sha") or "unknown")

    seed = seed_labels(client)
    gate = training_gate_status(client, ORG)

    train_local = None
    if gate.get("ready"):
        train_local = asyncio.run(train_churn_risk_scorer(ORG, settings=settings, client=client))

    tok = mint_token()
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }

    try:
        r = httpx.post(
            f"{BASE}/api/admin/ml/models/churn_risk_scorer/train",
            headers=hdr,
            timeout=120.0,
        )
        train_http = {"status_code": r.status_code, "body": r.json() if r.content else {}}
    except Exception as exc:  # noqa: BLE001
        train_http = {"status_code": None, "error": exc.__class__.__name__}

    try:
        r = httpx.get(
            f"{BASE}/api/intelligence/churn-risk/advisory?limit=10",
            headers=hdr,
            timeout=60.0,
        )
        body = r.json() if r.content else {}
        cards = body.get("recommendations") or []
        advisory = {
            "status_code": r.status_code,
            "card_count": len(cards),
            "trained": body.get("trained"),
            "gate": body.get("gate"),
            "advisory_only": body.get("advisory_only"),
            "auto_contact": body.get("auto_contact"),
            "sample_ids": [c.get("id") for c in cards[:5]],
            "executable_any": any(bool(c.get("executable")) for c in cards),
            "error_detail": body.get("detail") if r.status_code >= 400 else None,
        }
    except Exception as exc:  # noqa: BLE001
        advisory = {"status_code": None, "error": exc.__class__.__name__, "card_count": 0}

    advisory_local = asyncio.run(build_churn_advisory_cards(ORG, settings=settings, client=client, limit=10))

    train_ok = bool((train_local or {}).get("trained"))
    body = (train_http or {}).get("body") or {}
    train_http_started = (train_http or {}).get("status_code") == 200 and (
        body.get("trained") is True or bool(body.get("model_id")) or bool(body.get("temporal"))
    )
    train_ok = train_ok or train_http_started

    advisory_ok = (
        int(advisory.get("status_code") or 0) == 200
        and int(advisory.get("card_count") or 0) >= 1
        and advisory.get("advisory_only") is True
        and advisory.get("executable_any") is not True
    )
    seed_ok = bool(seed.get("gate_ready"))
    deploy_ok = bool(deploy.get("ok"))
    passed = deploy_ok and seed_ok and train_ok and advisory_ok

    artifact = {
        "pass": passed,
        "status": "PASS" if passed else "PARTIAL",
        "ran_at": utcnow(),
        "prod_git_sha": tip_sha,
        "org_id": ORG,
        "base_url": BASE,
        "deploy": deploy,
        "seed": seed,
        "gate": gate,
        "train_local": train_local,
        "train_http": train_http,
        "advisory": advisory,
        "advisory_local": {
            "card_count": len(advisory_local.get("recommendations") or []),
            "trained": advisory_local.get("trained"),
            "advisory_only": advisory_local.get("advisory_only"),
            "gate": advisory_local.get("gate"),
        },
        "governance": {
            "advisory_only": True,
            "auto_contact": False,
            "min_labeled_examples": 30,
            "storage": "confidence_note JSON + metric_value_after label",
        },
        "note": (
            "Churn ML live tip: ≥30 labeled churn_customer_signal rows, train churn_risk_scorer, "
            "GET /api/intelligence/churn-risk/advisory suggest-only."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": passed,
                "out": str(OUT),
                "tip": tip_sha,
                "seed_after": seed.get("after"),
                "advisory_status": advisory.get("status_code"),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
