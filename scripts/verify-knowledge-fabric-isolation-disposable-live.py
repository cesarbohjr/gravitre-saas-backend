#!/usr/bin/env python3
"""Part A — disposable-org live isolation proof for knowledge fabric.

Creates a real disposable org+user, probes every exposed API path + PostgREST
read/write on knowledge_*, then deletes the disposable org/user.
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
OUT = ROOT / "docs" / "delivery" / "knowledge-fabric-isolation-disposable-live.json"
API_BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
FOREIGN_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
KNOWLEDGE_TABLES = ["knowledge_sources", "knowledge_documents", "knowledge_chunks"]


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
            "exp": int(time.time()) + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def create_disposable(env: dict[str, str]) -> tuple[str, str, str, str]:
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    ts = int(time.time())
    email = f"kf-isolation+{ts}@gravitre.app"
    password = f"KfIso!{ts}Xx"
    created = client.auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": "KF Isolation Disposable",
                "company_name": f"KF Isolation Disposable {ts}",
            },
        }
    )
    user_id = str(created.user.id)
    org_id = None
    for _ in range(20):
        members = (
            client.table("organization_members")
            .select("org_id,role")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if members.data:
            org_id = str(members.data[0]["org_id"])
            break
        time.sleep(0.5)
    if not org_id:
        raise SystemExit(f"handle_new_user did not provision org for {user_id}")
    # Mark disposable for cleanup auditing
    client.table("organizations").update(
        {
            "settings": {
                "disposable_isolation_probe": True,
                "purpose": "knowledge_fabric_isolation_2026_08_11",
                "never_customer_visible": True,
            }
        }
    ).eq("id", org_id).execute()
    return org_id, user_id, email, password


def cleanup_disposable(env: dict[str, str], org_id: str, user_id: str) -> dict:
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    notes: list[str] = []
    for table in (
        "organization_members",
        "org_billing",
        "subscriptions",
        "agents",
        "rag_sources",
    ):
        try:
            client.table(table).delete().eq("org_id", org_id).execute()
            notes.append(f"deleted:{table}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"warn:{table}:{str(exc)[:80]}")
    try:
        client.table("organizations").delete().eq("id", org_id).execute()
        notes.append("deleted:organizations")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"warn:organizations:{str(exc)[:80]}")
    try:
        client.auth.admin.delete_user(user_id)
        notes.append("deleted:auth_user")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"warn:auth_user:{str(exc)[:80]}")
    # Confirm gone
    still = client.table("organizations").select("id").eq("id", org_id).limit(1).execute()
    return {
        "notes": notes,
        "org_still_exists": bool(still.data),
        "cleaned": not bool(still.data),
    }


def rest(
    *,
    url: str,
    table: str,
    headers: dict[str, str],
    method: str = "GET",
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    r = httpx.request(
        method,
        f"{url}/rest/v1/{table}",
        headers={**headers, "Prefer": "return=representation"},
        params=params,
        json=json_body,
        timeout=60,
    )
    try:
        data = r.json()
    except Exception:
        data = r.text[:800]
    return {
        "table": table,
        "method": method,
        "http": r.status_code,
        "body": data if not isinstance(data, list) else {"row_count": len(data), "sample_ids": [x.get("id") for x in data[:3]]},
    }


def api(
    method: str,
    path: str,
    *,
    token: str,
    org_id: str,
    body: dict | None = None,
) -> dict:
    r = httpx.request(
        method,
        f"{API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": org_id,
            "X-Environment": "production",
            "Content-Type": "application/json",
            "X-Gravitre-Smoke": "1",
        },
        json=body,
        timeout=120,
    )
    try:
        data = r.json()
    except Exception:
        data = r.text[:800]
    return {"path": path, "method": method, "http": r.status_code, "body": data}


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "part_a1_honest_prior_status": (
            "The verify-knowledge-fabric-live.json isolation check was SCHEMA/SERVICE-ROLE only "
            "(namespace + table presence). It was NOT a disposable-org JWT/API attempt."
        ),
        "api_base": API_BASE,
        "foreign_org_id": FOREIGN_ORG,
        "probes": {},
    }

    org_id, user_id, email, _pw = create_disposable(env)
    report["disposable_org_id"] = org_id
    report["disposable_user_id"] = user_id
    report["disposable_email"] = email
    assert org_id.lower() != FOREIGN_ORG.lower()

    tok = mint_jwt(env, user_id, email)
    url = env["SUPABASE_URL"].rstrip("/")
    rest_headers = {
        "Authorization": f"Bearer {tok}",
        "apikey": env["SUPABASE_ANON_KEY"],
        "Content-Type": "application/json",
    }

    # Seed foreign rag marker
    foreign_rag_id = str(uuid.uuid4())
    foreign_title = f"KF-DISP-ISO-{foreign_rag_id[:8]}"
    sb.table("rag_sources").insert(
        {
            "id": foreign_rag_id,
            "org_id": FOREIGN_ORG,
            "title": foreign_title,
            "type": "document",
            "metadata": {"kf_disposable_isolation": True},
        }
    ).execute()

    # PostgREST knowledge writes
    write_probes = []
    fake_id = str(uuid.uuid4())
    for table, body in [
        (
            "knowledge_sources",
            {
                "id": fake_id,
                "source_id": f"probe.{fake_id[:8]}",
                "publisher": "probe",
                "url": "https://example.invalid/probe",
                "source_type": "probe",
                "department": "legal",
                "ingestion_method": "manual",
                "license_type": "A",
                "refresh_frequency": "manual",
                "namespace": "platform_shared",
            },
        ),
        (
            "knowledge_documents",
            {
                "id": str(uuid.uuid4()),
                "source_id": fake_id,
                "external_id": "probe-doc",
                "title": "must not persist",
            },
        ),
        (
            "knowledge_chunks",
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "source_id": fake_id,
                "chunk_index": 0,
                "content": "must not persist",
            },
        ),
    ]:
        r = rest(url=url, table=table, headers=rest_headers, method="POST", json_body=body)
        msg = json.dumps(r.get("body"))
        blocked = r["http"] in {401, 403, 404, 405} or "row-level security" in msg.lower()
        r["blocked"] = blocked
        r["leaked"] = r["http"] in {200, 201} and "row-level security" not in msg.lower()
        write_probes.append(r)
    report["probes"]["postgrest_knowledge_write"] = write_probes

    # PostgREST knowledge DELETE (must fail)
    delete_probes = []
    for table in KNOWLEDGE_TABLES:
        r = rest(
            url=url,
            table=table,
            headers=rest_headers,
            method="DELETE",
            params={"id": "eq.00000000-0000-0000-0000-000000000001"},
        )
        msg = json.dumps(r.get("body"))
        r["blocked"] = r["http"] in {401, 403, 404, 405, 204, 200} and "row-level security" in msg.lower() or r["http"] in {401, 403, 405}
        # 204 with 0 rows also OK (no matching rows + no write policy)
        if r["http"] in {200, 204} and (isinstance(r.get("body"), dict) and r["body"].get("row_count") in (None, 0)):
            r["blocked"] = True
            r["note"] = "no rows deleted / empty success without write policy"
        delete_probes.append(r)
    report["probes"]["postgrest_knowledge_delete"] = delete_probes

    # PostgREST knowledge read (shared SELECT allowed)
    read_probes = []
    for table in KNOWLEDGE_TABLES:
        r = rest(url=url, table=table, headers=rest_headers, params={"select": "id", "limit": "2"})
        r["read_ok"] = r["http"] in {200, 206}
        read_probes.append(r)
    report["probes"]["postgrest_knowledge_read"] = read_probes

    # Foreign rag must not leak via JWT
    rag_leak = rest(
        url=url,
        table="rag_sources",
        headers=rest_headers,
        params={"select": "id,org_id,title", "org_id": f"eq.{FOREIGN_ORG}", "title": f"eq.{foreign_title}"},
    )
    leaked = (
        isinstance(rag_leak.get("body"), dict)
        and (rag_leak["body"].get("row_count") or 0) > 0
    )
    rag_leak["blocked"] = not leaked
    rag_leak["leaked"] = leaked
    report["probes"]["postgrest_foreign_rag"] = rag_leak

    # Exposed FastAPI paths
    api_probes = {}
    api_probes["GET /packs"] = api("GET", "/api/knowledge-fabric/packs", token=tok, org_id=org_id)
    api_probes["POST /classify"] = api(
        "POST",
        "/api/knowledge-fabric/classify",
        token=tok,
        org_id=org_id,
        body={"query": "NIST CSF Govern", "assigned_pack_ids": ["pack.cybersecurity"]},
    )
    api_probes["POST /retrieve"] = api(
        "POST",
        "/api/knowledge-fabric/retrieve",
        token=tok,
        org_id=org_id,
        body={"query": "NIST CSF Govern function", "assigned_pack_ids": ["pack.cybersecurity"], "top_k": 3},
    )
    # Org admin of disposable org must NOT mutate shared corpus (platform-admin gate)
    api_probes["POST /admin/register-sources"] = api(
        "POST",
        "/api/knowledge-fabric/admin/register-sources",
        token=tok,
        org_id=org_id,
    )
    api_probes["POST /admin/ingest"] = api(
        "POST",
        "/api/knowledge-fabric/admin/ingest",
        token=tok,
        org_id=org_id,
        body={"pack_id": "pack.cybersecurity", "limit": 1, "embed": False},
    )
    # Internal refresh without secret
    r = httpx.post(
        f"{API_BASE}/api/internal/knowledge-fabric/refresh-due",
        json={"force": True, "pack_ids": ["pack.finance"], "limit": 1, "embed": False},
        timeout=60,
    )
    try:
        body = r.json()
    except Exception:
        body = r.text[:400]
    api_probes["POST /internal/refresh-due (no secret)"] = {
        "path": "/api/internal/knowledge-fabric/refresh-due",
        "method": "POST",
        "http": r.status_code,
        "body": body,
    }

    # Annotate expected outcomes
    retrieve = api_probes["POST /retrieve"]
    if retrieve["http"] == 200 and isinstance(retrieve.get("body"), dict):
        titles = json.dumps(retrieve["body"])
        retrieve["foreign_rag_title_absent"] = foreign_title not in titles
        retrieve["customer_rag_tables_touched"] = (
            retrieve["body"].get("isolation") or {}
        ).get("customer_rag_tables_touched")
        retrieve["result_count"] = len(retrieve["body"].get("results") or [])

    for key in ("POST /admin/register-sources", "POST /admin/ingest"):
        p = api_probes[key]
        p["expected"] = "403 Platform admin required (org admin of disposable org blocked)"
        p["blocked"] = p["http"] in {401, 403}
    api_probes["POST /internal/refresh-due (no secret)"]["blocked"] = api_probes[
        "POST /internal/refresh-due (no secret)"
    ]["http"] in {401, 403}
    api_probes["POST /internal/refresh-due (no secret)"]["expected"] = "401 without INTERNAL_API_SECRET"

    report["probes"]["api"] = api_probes

    # Cleanup foreign seed + disposable
    try:
        sb.table("rag_sources").delete().eq("id", foreign_rag_id).execute()
        foreign_cleaned = True
    except Exception as exc:  # noqa: BLE001
        foreign_cleaned = False
        report["foreign_seed_cleanup_error"] = str(exc)[:200]

    report["cleanup"] = cleanup_disposable(env, org_id, user_id)
    report["cleanup"]["foreign_rag_seed_deleted"] = foreign_cleaned

    write_ok = all(p.get("blocked") and not p.get("leaked") for p in write_probes)
    rag_ok = rag_leak.get("blocked") and not rag_leak.get("leaked")
    admin_ok = all(api_probes[k].get("blocked") for k in ("POST /admin/register-sources", "POST /admin/ingest"))
    internal_ok = api_probes["POST /internal/refresh-due (no secret)"].get("blocked")
    retrieve_ok = (
        retrieve.get("http") == 200
        and retrieve.get("customer_rag_tables_touched") is False
        and retrieve.get("foreign_rag_title_absent") is True
    )
    read_ok = all(p.get("read_ok") for p in read_probes)
    cleanup_ok = report["cleanup"].get("cleaned") is True

    report["pass"] = all([write_ok, rag_ok, admin_ok, internal_ok, retrieve_ok, read_ok, cleanup_ok])
    report["assertions"] = {
        "postgrest_writes_blocked": write_ok,
        "foreign_rag_not_readable": rag_ok,
        "org_admin_cannot_mutate_shared_corpus": admin_ok,
        "internal_refresh_requires_secret": internal_ok,
        "retrieve_ok_no_foreign_rag": retrieve_ok,
        "shared_read_allowed": read_ok,
        "disposable_cleaned": cleanup_ok,
    }
    report["verdict"] = (
        "PASS — disposable org live isolation"
        if report["pass"]
        else "FAIL — see probes/assertions"
    )

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print("wrote", OUT)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
