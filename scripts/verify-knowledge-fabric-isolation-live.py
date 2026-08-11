#!/usr/bin/env python3
"""Live isolation proof: knowledge_* platform shared vs org-scoped rag_*.

Matches program standard in verify-phase0-rls-cross-org-live.py:
disposable isolated org JWT, PostgREST probes, foreign-org seed + leak check,
write attempts on protected tables, API path with X-Org-Id.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

OUT = ROOT / "docs" / "delivery" / "knowledge-fabric-isolation-live.json"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
FOREIGN_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
KNOWLEDGE_TABLES = ["knowledge_sources", "knowledge_documents", "knowledge_chunks"]
RAG_TABLES = ["rag_sources", "rag_chunks"]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
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
    return merged


def mint_jwt(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
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


def rest_probe(
    *,
    url: str,
    table: str,
    headers: dict[str, str],
    method: str = "GET",
    params: dict[str, str] | None = None,
    json_body: dict | None = None,
) -> dict:
    req_headers = {**headers, "Prefer": "return=representation"}
    r = httpx.request(
        method,
        f"{url}/rest/v1/{table}",
        headers=req_headers,
        params=params,
        json=json_body,
        timeout=60,
    )
    try:
        data = r.json()
    except Exception:
        data = r.text[:500]
    return {
        "table": table,
        "method": method,
        "http": r.status_code,
        "row_count": len(data) if isinstance(data, list) else None,
        "error": data if not isinstance(data, list) else None,
        "sample_ids": [row.get("id") for row in data[:3]] if isinstance(data, list) else None,
    }


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    assert org_id.lower() != FOREIGN_ORG.lower()

    tok = mint_jwt(env, user_id, email)
    url = env["SUPABASE_URL"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {tok}",
        "apikey": env["SUPABASE_ANON_KEY"],
        "Content-Type": "application/json",
    }

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "isolated_org_id": org_id,
        "isolated_user_id": user_id,
        "foreign_org_id": FOREIGN_ORG,
        "prior_verify_isolation_was": "schema/service-role only (not live JWT/API)",
        "probes": {},
    }

    # Schema presence (service role — setup only, not the isolation pass)
    schema: dict[str, object] = {}
    for table in KNOWLEDGE_TABLES + RAG_TABLES:
        try:
            rows = sb.table(table).select("id").limit(1).execute()
            schema[table] = {"exists": True, "sample_count": len(rows.data or [])}
        except Exception as exc:  # noqa: BLE001
            schema[table] = {"exists": False, "error": str(exc)[:300]}
    report["schema_presence"] = schema

    knowledge_tables_live = all(schema.get(t, {}).get("exists") for t in KNOWLEDGE_TABLES)

    # Seed foreign-org rag marker (service role)
    foreign_rag_id = str(uuid.uuid4())
    foreign_title = f"KF-ISOLATION-PROBE-{foreign_rag_id[:8]}"
    seed_ok = False
    seed_error = None
    try:
        sb.table("rag_sources").insert(
            {
                "id": foreign_rag_id,
                "org_id": FOREIGN_ORG,
                "title": foreign_title,
                "type": "document",
                "status": "active",
                "metadata": {"kf_isolation_probe": True},
            }
        ).execute()
        seed_ok = True
    except Exception as exc:  # noqa: BLE001
        seed_error = str(exc)[:400]

    cross_org_rag: list[dict] = []
    for table in RAG_TABLES:
        params: dict[str, str] = {"select": "id,org_id", "limit": "10"}
        if table == "rag_sources":
            params["org_id"] = f"eq.{FOREIGN_ORG}"
            params["title"] = f"ilike.*{foreign_title}*"
        elif table == "rag_chunks":
            params["org_id"] = f"eq.{FOREIGN_ORG}"
        r = rest_probe(url=url, table=table, headers=headers, params=params)
        leaked = isinstance(r.get("sample_ids"), list) and len(r["sample_ids"]) > 0
        r["blocked"] = (r["http"] in {200, 206} and not leaked) or r["http"] in {401, 403}
        r["leaked"] = leaked
        r["seed"] = foreign_rag_id if seed_ok else seed_error
        cross_org_rag.append(r)

    report["probes"]["cross_org_rag"] = cross_org_rag

    # knowledge_* authenticated writes must fail
    write_probes: list[dict] = []
    fake_source_id = str(uuid.uuid4())
    write_attempts = [
        (
            "knowledge_sources",
            {
                "id": fake_source_id,
                "source_id": f"probe.{fake_source_id[:8]}",
                "publisher": "probe",
                "url": "https://example.invalid/probe",
                "source_type": "probe",
                "department": "legal",
                "ingestion_method": "manual",
                "license_type": "A",
                "refresh_frequency": "never",
                "namespace": "platform_shared",
            },
        ),
        (
            "knowledge_chunks",
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "source_id": fake_source_id,
                "chunk_index": 0,
                "content": "probe must not persist",
            },
        ),
    ]
    for table, body in write_attempts:
        r = rest_probe(url=url, table=table, headers=headers, method="POST", json_body=body)
        blocked = r["http"] in {401, 403, 404, 405} or (
            r["http"] in {200, 201} and (r.get("row_count") or 0) == 0
        )
        # PostgREST often returns 403/new row violates row-level security
        if isinstance(r.get("error"), dict):
            msg = json.dumps(r["error"])
            blocked = blocked or "row-level security" in msg.lower() or "permission denied" in msg.lower()
        r["blocked"] = blocked
        r["leaked"] = r["http"] in {200, 201} and (r.get("row_count") or 0) > 0
        write_probes.append(r)
    report["probes"]["knowledge_write_blocked"] = write_probes

    # knowledge_* read: allowed for platform shared (if tables exist)
    read_probes: list[dict] = []
    for table in KNOWLEDGE_TABLES:
        r = rest_probe(
            url=url,
            table=table,
            headers=headers,
            params={"select": "id", "limit": "3"},
        )
        if not knowledge_tables_live:
            r["note"] = "table missing — migration not applied"
            r["expected_read"] = "n/a"
        else:
            r["expected_read"] = "allowed (platform_shared SELECT policy)"
        read_probes.append(r)
    report["probes"]["knowledge_read"] = read_probes

    # API retrieve must not touch customer rag
    api_headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "Content-Type": "application/json",
    }
    api_probe: dict = {"http": None, "blocked_foreign_rag_in_results": True}
    try:
        r = httpx.post(
            f"{BASE}/api/knowledge-fabric/retrieve",
            headers=api_headers,
            json={
                "query": "NIST CSF Govern function",
                "assigned_pack_ids": ["pack.cybersecurity"],
                "top_k": 3,
            },
            timeout=120,
        )
        api_probe["http"] = r.status_code
        if r.status_code == 200:
            body = r.json()
            api_probe["isolation"] = body.get("isolation")
            api_probe["result_count"] = len(body.get("results") or [])
            titles = json.dumps(body)
            api_probe["blocked_foreign_rag_in_results"] = foreign_title not in titles
            api_probe["customer_rag_tables_touched"] = (
                body.get("isolation") or {}
            ).get("customer_rag_tables_touched")
        else:
            api_probe["body"] = r.text[:500]
    except Exception as exc:  # noqa: BLE001
        api_probe["error"] = str(exc)[:400]
    report["probes"]["api_retrieve"] = api_probe

    # Cleanup foreign seed
    if seed_ok:
        try:
            sb.table("rag_sources").delete().eq("id", foreign_rag_id).execute()
            report["cleanup"] = {"foreign_rag_seed_deleted": True}
        except Exception as exc:  # noqa: BLE001
            report["cleanup"] = {"foreign_rag_seed_deleted": False, "error": str(exc)[:200]}

    cross_org_pass = all(p.get("blocked") and not p.get("leaked") for p in cross_org_rag)
    write_pass = all(p.get("blocked") and not p.get("leaked") for p in write_probes)
    api_pass = (
        api_probe.get("http") == 200
        and api_probe.get("customer_rag_tables_touched") is False
        and api_probe.get("blocked_foreign_rag_in_results") is True
    )
    schema_note = (
        "knowledge_* tables absent in prod — structural isolation unproven live; "
        "do not apply migration until drift sign-off"
        if not knowledge_tables_live
        else None
    )

    report["pass"] = cross_org_pass and write_pass and (api_pass if knowledge_tables_live else False)
    report["partial"] = knowledge_tables_live is False
    report["schema_note"] = schema_note
    report["verdict"] = (
        "PASS — live JWT/API isolation probes"
        if report["pass"]
        else (
            "PARTIAL — rag cross-org/write probes only; knowledge_* tables not in prod"
            if not knowledge_tables_live and cross_org_pass and write_pass
            else "FAIL — see probes"
        )
    )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("wrote", OUT)
    if report["pass"]:
        return 0
    if report.get("partial"):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
