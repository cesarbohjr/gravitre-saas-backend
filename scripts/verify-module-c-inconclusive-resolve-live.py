#!/usr/bin/env python3
"""Phase 0.3 — resolve Module C surfaces 6/7 from LIVE INCONCLUSIVE → PASS|FAIL.

Re-seeds organic glossary+edge in the isolated org (fresh term each run), then
probes admin relationships + ask entities. PASS requires labeled confidence on
both surfaces (confidence + source + is_estimate).

Writes docs/delivery/module-c-inconclusive-resolve-live.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "module-c-inconclusive-resolve-live.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def _req(method: str, path: str, token: str, org_id: str, body: dict | None = None) -> tuple[int, Any]:
    import urllib.error
    import urllib.request

    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    req.add_header("X-Gravitree-Smoke-Run", "1")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {"detail": raw}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:400]}
        return exc.code, parsed


def _labeled(obj: dict | None) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("confidence") is None:
        return False
    src = obj.get("confidence_source") or obj.get("confidenceSource")
    est = obj.get("confidence_is_estimate")
    if est is None:
        est = obj.get("confidenceIsEstimate")
    return bool(src) and est is not None


def main() -> int:
    sys.path.insert(0, str(REPO / "backend"))
    sys.path.insert(0, str(REPO / "scripts"))
    from isolated_conversation_org import (
        DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        ensure_isolated_conversation_test_org,
        isolated_conversation_test_org_id,
    )
    from supabase import create_client

    from app.services.confidence_honesty import estimated_confidence
    from app.services.entity_relationship_builder import (
        ENTITY_DEPARTMENT,
        ENTITY_GLOSSARY,
        _upsert_relationship,
    )

    env = _load_env()
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id = ensure_isolated_conversation_test_org(client)
    assert org_id == isolated_conversation_test_org_id()
    user_id = user_id or DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
    email = "conversation-smoke-sa@gravitre.app"

    import httpx

    tip = httpx.get(f"{API_BASE}/health", timeout=30.0).json()
    git_sha = str(tip.get("git_sha") or "")

    now = datetime.now(timezone.utc).isoformat()
    term = f"Phase0Resolve-{uuid.uuid4().hex[:8]}"
    gloss = (
        client.table("org_glossary_terms")
        .insert(
            {
                "org_id": org_id,
                "term": term,
                "definition": f"{term} is an organic Module C resolve fixture.",
                "created_at": now,
                "updated_at": now,
            }
        )
        .execute()
    )
    gloss_id = str((gloss.data or [{}])[0].get("id") or "")
    dept = (
        client.table("departments")
        .select("id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not dept:
        d = (
            client.table("departments")
            .insert({"org_id": org_id, "name": "Phase0 Sales", "slug": f"phase0-{uuid.uuid4().hex[:6]}"})
            .execute()
        )
        dept_id = str((d.data or [{}])[0].get("id") or "")
    else:
        dept_id = str(dept[0]["id"])

    from app.services.confidence_honesty import CONFIDENCE_SOURCE_EDGE_HEURISTIC

    labeled = estimated_confidence(0.73, source=CONFIDENCE_SOURCE_EDGE_HEURISTIC)
    edge_ok = _upsert_relationship(
        client,
        org_id=org_id,
        source_entity_type=ENTITY_GLOSSARY,
        source_entity_id=gloss_id,
        relationship_type="associated_with",
        target_entity_type=ENTITY_DEPARTMENT,
        target_entity_id="sales",
        confidence=float(labeled["confidence"]),
        evidence_count=1,
    )

    token = _mint(env, user_id, email)
    # Prefer admin intelligence relationships (same as prior Module C live)
    http6, body6 = _req("GET", "/api/admin/intelligence/relationships?limit=20", token, org_id)
    rels = []
    if isinstance(body6, dict):
        rels = body6.get("relationships") or body6.get("items") or body6.get("edges") or []
    elif isinstance(body6, list):
        rels = body6
    rel0 = next(
        (
            r
            for r in rels
            if isinstance(r, dict) and str(r.get("source_entity_id") or "") == gloss_id
        ),
        rels[0] if rels else None,
    )
    # entity-scoped
    http6b, _ = _req(
        "GET",
        f"/api/admin/intelligence/relationships?entity_type=glossary_term&entity_id={gloss_id}&limit=20",
        token,
        org_id,
    )

    http7, body7 = _req(
        "POST",
        "/api/intelligence/ask",
        token,
        org_id,
        {"question": f"Tell me about {term} and related entities in our org.", "org_id": org_id},
    )
    entities: list = []
    if isinstance(body7, dict):
        und = body7.get("understanding") if isinstance(body7.get("understanding"), dict) else {}
        entities = list(und.get("entities") or body7.get("entities") or [])
        # some envelopes nest under answer
        if not entities and isinstance(body7.get("enrichments"), dict):
            entities = list(body7["enrichments"].get("entities") or [])
    entity0 = entities[0] if entities else None
    envelope_labeled = _labeled(body7 if isinstance(body7, dict) else None)

    s6_pass = http6 == 200 and _labeled(rel0 if isinstance(rel0, dict) else None)
    s7_pass = http7 == 200 and (_labeled(entity0 if isinstance(entity0, dict) else None) or envelope_labeled)

    report = {
        "probe": "module_c_inconclusive_resolve",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "org_id": org_id,
        "organic_term": term,
        "glossary_id": gloss_id,
        "department_id": dept_id,
        "edge_upsert_ok": bool(edge_ok),
        "seeded_edge_confidence": labeled,
        "6_entity_relationships": {
            "prior": "LIVE INCONCLUSIVE — no edges in prod",
            "http": http6,
            "entity_scoped_http": http6b,
            "total": len(rels),
            "relationship0": {
                "confidence": (rel0 or {}).get("confidence") if isinstance(rel0, dict) else None,
                "confidence_is_estimate": (rel0 or {}).get("confidence_is_estimate")
                or (rel0 or {}).get("confidenceIsEstimate")
                if isinstance(rel0, dict)
                else None,
                "confidence_source": (rel0 or {}).get("confidence_source")
                or (rel0 or {}).get("confidenceSource")
                if isinstance(rel0, dict)
                else None,
            },
            "resolved": "PASS" if s6_pass else "FAIL",
            "pass": s6_pass,
        },
        "7_contextual_entities": {
            "prior": "LIVE INCONCLUSIVE — NO_PUBLIC_JSON / ask 500",
            "http": http7,
            "envelope_labeled": envelope_labeled,
            "entity_count": len(entities),
            "entity0": {
                "confidence": (entity0 or {}).get("confidence") if isinstance(entity0, dict) else None,
                "confidence_is_estimate": (entity0 or {}).get("confidence_is_estimate")
                or (entity0 or {}).get("confidenceIsEstimate")
                if isinstance(entity0, dict)
                else None,
                "confidence_source": (entity0 or {}).get("confidence_source")
                or (entity0 or {}).get("confidenceSource")
                if isinstance(entity0, dict)
                else None,
                "text": (entity0 or {}).get("text")
                or (entity0 or {}).get("name")
                or (entity0 or {}).get("value")
                if isinstance(entity0, dict)
                else None,
            },
            "resolved": "PASS" if s7_pass else "FAIL",
            "pass": s7_pass,
        },
        "passed": bool(s6_pass and s7_pass),
        "note": (
            "Organic glossary+department edge in isolated org; labeling contract verified live. "
            "Not permanently untestable."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "s6": report["6_entity_relationships"]["resolved"],
                "s7": report["7_contextual_entities"]["resolved"],
                "git_sha": git_sha,
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
