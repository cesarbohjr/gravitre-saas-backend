"""Minimal regression smoke tests (no external deps)."""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from pathlib import Path
import urllib.request
from urllib.error import HTTPError, URLError

# Allow running from repo root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


FORBIDDEN_KEY_SUBSTRINGS = [
    "recipient",
    "email_address",
    "payload",
    "body",
    "subject",
    "query",
    "content",
    "token",
    "secret",
    "url",
    "message",
]


def http_get(url: str, token: str | None = None) -> dict:
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8") or "{}"
        return json.loads(body)


def scan_forbidden(obj, path="") -> list[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            for f in FORBIDDEN_KEY_SUBSTRINGS:
                if f in key:
                    hits.append(f"{path}.{k}".lstrip("."))
            hits.extend(scan_forbidden(v, f"{path}.{k}".lstrip(".")))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(scan_forbidden(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if "@" in obj:
            hits.append(f"{path}:contains_email")
        if "http://" in obj or "https://" in obj:
            hits.append(f"{path}:contains_url")
    return hits


def test_metrics(base_url: str, token: str) -> None:
    endpoints = [
        "/api/metrics/overview?range=7d",
        "/api/metrics/workflows?range=7d",
        "/api/metrics/rag?range=7d",
        "/api/metrics/connectors?range=7d",
        "/api/metrics/timeseries?range=30d&metric=exec_runs_total",
    ]
    for ep in endpoints:
        data = http_get(base_url + ep, token)
        hits = scan_forbidden(data)
        if hits:
            raise SystemExit(f"Forbidden fields detected in {ep}: {hits}")


def test_webhook_ssrf_static() -> None:
    from app.connectors import webhook as wh

    # Static checks to avoid outbound network
    src = inspect.getsource(wh.send_webhook)
    if "connect_ip" not in inspect.signature(wh.send_webhook).parameters:
        raise SystemExit("send_webhook missing connect_ip parameter (pinned IP required)")
    if "_PinnedHTTPSConnection" not in src:
        raise SystemExit("send_webhook does not use pinned HTTPS connection")
    src_resolve = inspect.getsource(wh.resolve_and_validate_host)
    if "return ips" not in src_resolve:
        raise SystemExit("resolve_and_validate_host does not return IP candidates")


def test_approval_floor_static() -> None:
    from app.routers import workflows as wf

    src = inspect.getsource(wf.execute_workflow)
    required = {"slack_post_message", "email_send", "webhook_post"}
    if not all(t in src for t in required):
        raise SystemExit("approval floor check missing external step types")
    if "required_approvals < 1" not in src and "required_approvals<1" not in src:
        raise SystemExit("approval floor enforcement not detected")
    if "policy.override.approval_floor_applied" not in src:
        raise SystemExit("approval floor audit event missing")


def test_ingest_atomicity_db() -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        print("Skipping DB checks (SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing).")
        return
    from supabase import create_client

    client = create_client(supabase_url, service_key)
    docs = (
        client.table("rag_documents")
        .select("id, source_id, external_id, is_active")
        .not_.is_("external_id", "null")
        .execute()
    )
    rows = list(docs.data or [])
    if not rows:
        print("No documents with external_id found; DB checks skipped.")
        return
    # Map (source_id, external_id) -> active count, ids
    counts: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (str(row["source_id"]), str(row["external_id"]))
        counts.setdefault(key, []).append(row)
    for key, items in counts.items():
        active = [i for i in items if i.get("is_active") is True]
        if len(active) != 1:
            raise SystemExit(f"Ingest atomicity violation for {key}: active_count={len(active)}")
    # Optional: active docs should have >=1 chunk (best-effort)
    active_ids = [str(i["id"]) for items in counts.values() for i in items if i.get("is_active") is True]
    if active_ids:
        if len(active_ids) <= 500:
            chunks = (
                client.table("rag_chunks")
                .select("document_id")
                .in_("document_id", active_ids)
                .execute()
            )
            chunk_docs = {str(c["document_id"]) for c in (chunks.data or [])}
            for doc_id in active_ids:
                if doc_id not in chunk_docs:
                    raise SystemExit(f"Active document has no chunks: {doc_id}")
        else:
            print("Skipping chunk presence check (too many active docs).")

    # Best-effort ingest job consistency
    jobs = client.table("rag_ingest_jobs").select("id, document_id, status").execute()
    for job in (jobs.data or []):
        if job.get("status") == "completed" and job.get("document_id"):
            if str(job["document_id"]) not in active_ids:
                raise SystemExit(f"Ingest job completed but document not active: {job['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal smoke tests")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=None, help="JWT token for auth endpoints")
    args = parser.parse_args()

    # Static approval floor and SSRF checks (no network)
    test_approval_floor_static()
    test_webhook_ssrf_static()

    # Health (only if backend is reachable)
    backend_ok = False
    try:
        _ = http_get(args.base_url + "/health")
        backend_ok = True
    except HTTPError as exc:
        raise SystemExit(f"/health returned {exc.code}") from exc
    except URLError:
        print("Backend not running; skipping HTTP checks.")

    # Auth/me if token provided
    if backend_ok and args.token:
        _ = http_get(args.base_url + "/api/auth/me", args.token)
        test_metrics(args.base_url, args.token)

    # DB checks for ingest atomicity (env gated)
    test_ingest_atomicity_db()

    print("Smoke tests passed.")


if __name__ == "__main__":
    sys.exit(main())
