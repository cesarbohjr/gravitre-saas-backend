#!/usr/bin/env python3
"""Seed safe-org entity relationship edges for Module C live labeling checks.

Writes ONLY into the isolated conversation test org (never operator/customer orgs).
Then probes /api/admin/intelligence/relationships and a clarify-path ask for entities.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "module-c-inconclusive-surfaces-live.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
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


def main() -> int:
    sys.path.insert(0, str(REPO / "backend"))
    sys.path.insert(0, str(REPO / "scripts"))
    from isolated_conversation_org import (  # type: ignore
        DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        ensure_isolated_conversation_test_org,
        isolated_conversation_test_org_id,
    )
    from supabase import create_client

    from app.services.confidence_honesty import (
        CONFIDENCE_SOURCE_EDGE_HEURISTIC,
        estimated_confidence,
    )
    from app.services.entity_relationship_builder import (
        ENTITY_DEPARTMENT,
        ENTITY_GLOSSARY,
        _upsert_relationship,
    )

    env = _load_env()
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id = ensure_isolated_conversation_test_org(client)
    assert org_id == isolated_conversation_test_org_id(), "refusing non-isolated org"
    user_id = user_id or DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID

    # Seed glossary + edge with labeled heuristic confidence (DB stores float only).
    now = datetime.now(timezone.utc).isoformat()
    gloss = (
        client.table("org_glossary_terms")
        .select("id,term")
        .eq("org_id", org_id)
        .eq("term", "module-c-acme")
        .limit(1)
        .execute()
        .data
        or []
    )
    if gloss:
        gloss_id = str(gloss[0]["id"])
    else:
        inserted = (
            client.table("org_glossary_terms")
            .insert(
                {
                    "org_id": org_id,
                    "term": "module-c-acme",
                    "definition": "Safe Module C probe entity (isolated org only)",
                    "associated_department": "sales",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            .execute()
            .data
            or []
        )
        gloss_id = str(inserted[0]["id"]) if inserted else "module-c-acme"

    edge_conf = float(estimated_confidence(0.72, source=CONFIDENCE_SOURCE_EDGE_HEURISTIC)["confidence"])
    _upsert_relationship(
        client,
        org_id=org_id,
        source_entity_type=ENTITY_GLOSSARY,
        source_entity_id=gloss_id,
        relationship_type="associated_with",
        target_entity_type=ENTITY_DEPARTMENT,
        target_entity_id="sales",
        confidence=edge_conf,
        evidence_count=2,
    )

    users = client.auth.admin.get_user_by_id(user_id)
    email = getattr(getattr(users, "user", None), "email", None) or f"{user_id}@smoke.local"
    token = _mint(env, user_id, str(email))

    with urllib.request.urlopen(f"{API_BASE}/health", timeout=30) as resp:
        health = json.loads(resp.read().decode())

    code_rel, body_rel = _req(
        "GET",
        f"/api/admin/intelligence/relationships?entityType={ENTITY_GLOSSARY}&entityId={gloss_id}",
        token,
        org_id,
    )
    rel0 = {}
    if isinstance(body_rel, dict):
        rows = body_rel.get("relationships") or []
        rel0 = rows[0] if rows else {}

    code_ask, body_ask = _req(
        "POST",
        "/api/intelligence/ask",
        token,
        org_id,
        {"question": 'Clarify: what is "module-c-acme" in sales?', "mode": "standard"},
    )
    entities = []
    if isinstance(body_ask, dict):
        entities = body_ask.get("entities") or []
        if not entities:
            enrich = ((body_ask.get("enrichments") or {}).get("contextual") or {}).get("entities")
            if isinstance(enrich, list):
                entities = enrich

    report = {
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": health.get("git_sha"),
        "org_id": org_id,
        "seeded_glossary_id": gloss_id,
        "seeded_edge_confidence": edge_conf,
        "6_entity_relationships": {
            "http": code_rel,
            "total": (body_rel.get("total") if isinstance(body_rel, dict) else None),
            "relationship0": {
                "confidence": rel0.get("confidence"),
                "confidence_is_estimate": rel0.get("confidence_is_estimate")
                or rel0.get("confidenceIsEstimate"),
                "confidence_source": rel0.get("confidence_source") or rel0.get("confidenceSource"),
            },
            "keys": sorted(rel0.keys())[:40] if isinstance(rel0, dict) else [],
        },
        "7_contextual_entities": {
            "http": code_ask,
            "entity0": {
                "confidence": (entities[0] or {}).get("confidence") if entities else None,
                "confidence_is_estimate": (entities[0] or {}).get("confidence_is_estimate")
                or (entities[0] or {}).get("confidenceIsEstimate")
                if entities
                else None,
                "confidence_source": (entities[0] or {}).get("confidence_source")
                or (entities[0] or {}).get("confidenceSource")
                if entities
                else None,
                "text": (entities[0] or {}).get("text") or (entities[0] or {}).get("name")
                if entities
                else None,
            },
            "entity_count": len(entities),
            "answer_keys": sorted(body_ask.keys())[:50] if isinstance(body_ask, dict) else [],
            "error": body_ask if code_ask >= 400 else None,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {OUT}")

    rel_ok = (
        code_rel < 400
        and rel0.get("confidence") is not None
        and bool(rel0.get("confidence_is_estimate") or rel0.get("confidenceIsEstimate"))
        and (rel0.get("confidence_source") or rel0.get("confidenceSource"))
        == CONFIDENCE_SOURCE_EDGE_HEURISTIC
    )
    return 0 if rel_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
