"""Voyage RAG quality spot-check (runbook Step 4) + metrics baseline (Step 6).

Probes production /api/rag/query and /api/rag-enhanced/query with representative
queries, records embedding_method and retrieval quality, and snapshots RAG metrics.

Usage:
  npm run rag:voyage:quality-check
  python scripts/check-voyage-rag-quality-prod.py --json docs/delivery/voyage-rag-quality-prod-latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
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
ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
RAILWAY_SERVICE = os.environ.get("RAILWAY_SERVICE", "gravitre-saas-backend")
SAMPLE_DOC_MARKERS = ("hybrid search", "pipeline hygiene", "connector knowledge", "pagerduty", "quickbooks")
LOG_LINE_LIMIT = int(os.environ.get("RAG_VOYAGE_LOG_LINES", "2000"))

SPOT_QUERIES: list[tuple[str, str]] = [
    ("hybrid_search", "How does hybrid search combine vector similarity and BM25 keyword ranking?"),
    ("pipeline_hygiene", "Review stale opportunities weekly with no activity in fourteen days"),
    ("connector_sync", "Connector knowledge sync ingests Notion Confluence HubSpot Zendesk"),
    ("incident_response", "When PagerDuty alerts fire summarize severity and customer impact"),
    ("finance_pilot", "QuickBooks and NetSuite read-only connectors during pilots"),
]

LOG_PATTERNS: dict[str, re.Pattern[str]] = {
    "embedding_voyage_failed": re.compile(r"embedding voyage failed|voyage failed", re.I),
    "embedding_openai_failed": re.compile(r"embedding openai failed", re.I),
    "dimension_mismatch": re.compile(r"dimension mismatch|voyage_dimension_mismatch", re.I),
    "keyword_fallback": re.compile(r"keyword_fallback|embedding unavailable", re.I),
    "rag_embedding_method": re.compile(r"rag embedding org_id=.* method="),
}


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_FILE):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _with_environment(path: str) -> str:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    return path


def _request_json(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    path = _with_environment(path)
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or ""
    supabase_url = (env.get("SUPABASE_URL") or "").rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required in backend/.env.operator.local")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    url = env.get("SUPABASE_URL") or ""
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)
    members = (
        client.table("organization_members")
        .select("org_id, user_id, role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit("No admin organization_members row found")
    row = members.data[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, email


def _top_snippet(payload: dict[str, Any], *, enhanced: bool) -> str:
    if enhanced:
        chunks = payload.get("chunks") or []
        if chunks and isinstance(chunks[0], dict):
            return str(chunks[0].get("content") or "")[:240]
        return ""
    results = payload.get("results") or []
    if results and isinstance(results[0], dict):
        return str(results[0].get("chunkText") or "")[:240]
    return ""


def _spot_check_query(token: str, org_id: str, name: str, query: str) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "query": query}
    try:
        query_payload = _request_json(
            "POST",
            "/api/rag/query",
            token,
            org_id,
            {"query": query, "top_k": 5},
        )
        results = query_payload.get("results") or []
        row["queryEndpoint"] = {
            "resultCount": len(results),
            "topScore": float(results[0].get("score") or 0.0) if results else 0.0,
            "topSnippet": _top_snippet(query_payload, enhanced=False),
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        row["queryEndpoint"] = {"error": f"HTTP {exc.code}: {body or exc.reason}"}

    try:
        enhanced_payload = _request_json(
            "POST",
            "/api/rag-enhanced/query",
            token,
            org_id,
            {
                "query": query,
                "top_k": 5,
                "scope": "organization",
                "include_sources": True,
                "filters": {"environment": ENV_NAME},
            },
        )
        metrics = enhanced_payload.get("metrics") if isinstance(enhanced_payload.get("metrics"), dict) else {}
        chunks = enhanced_payload.get("chunks") or []
        snippet = _top_snippet(enhanced_payload, enhanced=True).lower()
        row["enhancedEndpoint"] = {
            "chunkCount": len(chunks),
            "embeddingMethod": metrics.get("embedding_method"),
            "rerankMethod": metrics.get("rerank_method"),
            "fallback": metrics.get("fallback"),
            "topScore": float(chunks[0].score) if chunks and hasattr(chunks[0], "score") else (
                float(chunks[0].get("score") or 0.0) if chunks and isinstance(chunks[0], dict) else 0.0
            ),
            "topSnippet": _top_snippet(enhanced_payload, enhanced=True),
            "sampleCorpusHit": any(marker in snippet for marker in SAMPLE_DOC_MARKERS),
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        row["enhancedEndpoint"] = {"error": f"HTTP {exc.code}: {body or exc.reason}"}

    return row


def _fetch_embedding_status(token: str, org_id: str) -> dict[str, Any]:
    try:
        return _request_json("GET", "/api/rag/embedding-status", token, org_id)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return {"error": f"HTTP {exc.code}: {body or exc.reason}"}


def _fetch_rag_metrics(token: str, org_id: str, *, range_str: str) -> dict[str, Any]:
    try:
        return _request_json("GET", f"/api/metrics/rag?range={range_str}", token, org_id)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return {"error": f"HTTP {exc.code}: {body or exc.reason}"}


def _railway_executable() -> str | None:
    for candidate in ("railway", "railway.cmd"):
        path = shutil.which(candidate)
        if path:
            return path
    npm_bin = Path.home() / "AppData" / "Roaming" / "npm" / "railway.cmd"
    if npm_bin.is_file():
        return str(npm_bin)
    return None


def _scan_railway_logs(env: dict[str, str]) -> dict[str, Any]:
    token = (env.get("RAILWAY_TOKEN") or "").strip()
    if not token:
        return {"available": False, "reason": "RAILWAY_TOKEN not set; skipped log scan"}
    railway_bin = _railway_executable()
    if not railway_bin:
        return {"available": False, "reason": "railway CLI not installed"}
    env_copy = os.environ.copy()
    env_copy["RAILWAY_TOKEN"] = token
    try:
        proc = subprocess.run(
            [railway_bin, "logs", "--service", RAILWAY_SERVICE, "--lines", str(LOG_LINE_LIMIT)],
            capture_output=True,
            text=True,
            timeout=90,
            env=env_copy,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "railway logs timed out"}
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:400]
        return {"available": False, "reason": f"railway logs failed: {err}"}
    lines = (proc.stdout or "").splitlines()
    hits: dict[str, list[str]] = {name: [] for name in LOG_PATTERNS}
    for line in lines:
        for name, pattern in LOG_PATTERNS.items():
            if pattern.search(line):
                hits[name].append(line.strip()[:240])
    return {
        "available": True,
        "service": RAILWAY_SERVICE,
        "linesScanned": len(lines),
        "counts": {name: len(values) for name, values in hits.items()},
        "recentEmbeddingMethods": hits["rag_embedding_method"][-8:],
        "recentFailures": (
            hits["embedding_voyage_failed"]
            + hits["embedding_openai_failed"]
            + hits["dimension_mismatch"]
        )[-8:],
        "recentFallbacks": hits["keyword_fallback"][-8:],
    }


def _evaluate(spot_checks: list[dict[str, Any]], embedding_status: dict[str, Any], logs: dict[str, Any]) -> tuple[str, list[str]]:
    notes: list[str] = []
    errors = 0
    sample_hits = 0
    methods: set[str] = set()

    for check in spot_checks:
        enhanced = check.get("enhancedEndpoint") or {}
        if enhanced.get("error"):
            errors += 1
            notes.append(f"{check['name']}: enhanced error")
            continue
        method = str(enhanced.get("embeddingMethod") or "")
        if method:
            methods.add(method)
        if enhanced.get("sampleCorpusHit"):
            sample_hits += 1
        if method.startswith("keyword_fallback"):
            notes.append(f"{check['name']}: degraded embedding_method={method}")

    if errors:
        return "fail", notes + [f"{errors} spot-check(s) returned HTTP errors"]

    if embedding_status.get("error"):
        notes.append(f"embedding-status error: {embedding_status['error']}")
    else:
        voyage_on = embedding_status.get("voyage_enabled")
        pending = (embedding_status.get("voyage_reindex") or {}).get("pending_embeddings")
        notes.append(f"prod voyage_enabled={voyage_on} pending_voyage={pending}")
        if voyage_on and pending not in (0, None):
            notes.append("Voyage enabled but re-index still has pending rows")

    notes.append(f"sample corpus hits: {sample_hits}/{len(spot_checks)}")
    notes.append(f"embedding methods seen: {', '.join(sorted(methods)) or 'none'}")

    if logs.get("available"):
        failure_count = len(logs.get("recentFailures") or [])
        fallback_count = logs.get("counts", {}).get("keyword_fallback", 0)
        notes.append(f"log scan: failures={failure_count} keyword_fallback_lines={fallback_count}")
        if failure_count:
            return "warn", notes

    if sample_hits >= 3 and not any(m.startswith("keyword_fallback") for m in methods):
        return "pass", notes
    if sample_hits >= 1:
        return "warn", notes + ["retrieval quality lower than expected on sample corpus"]
    return "warn", notes + ["sample playbook content not retrieved; check ingest/environment=production"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Voyage RAG quality spot-check + metrics baseline")
    parser.add_argument("--json", metavar="PATH", help="Write structured report JSON")
    parser.add_argument("--metrics-range", default="7d", help="Range for /api/metrics/rag (7d, 30d, 90d)")
    args = parser.parse_args()

    env = _load_env()
    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    started = datetime.now(timezone.utc).isoformat()

    print(f"target={API_BASE}")
    print(f"org_id={org_id}")

    print("step: embedding_status")
    embedding_status = _fetch_embedding_status(token, org_id)
    if embedding_status.get("error"):
        print(f"  error: {embedding_status['error']}")
    else:
        reindex = embedding_status.get("voyage_reindex") or {}
        print(
            f"  voyage_enabled={embedding_status.get('voyage_enabled')} "
            f"pending={reindex.get('pending_embeddings')} complete={reindex.get('complete')}"
        )

    print("step: spot_checks (/api/rag/query + /api/rag-enhanced/query)")
    spot_checks = []
    for name, query in SPOT_QUERIES:
        result = _spot_check_query(token, org_id, name, query)
        spot_checks.append(result)
        enhanced = result.get("enhancedEndpoint") or {}
        if enhanced.get("error"):
            print(f"  {name}: FAIL {enhanced['error']}")
        else:
            print(
                f"  {name}: method={enhanced.get('embeddingMethod')} "
                f"chunks={enhanced.get('chunkCount')} sample_hit={enhanced.get('sampleCorpusHit')}"
            )

    print(f"step: rag_metrics range={args.metrics_range}")
    rag_metrics = _fetch_rag_metrics(token, org_id, range_str=args.metrics_range)
    if rag_metrics.get("error"):
        print(f"  error: {rag_metrics['error']}")
    else:
        retrieval = rag_metrics.get("retrieval") or {}
        print(
            f"  total={retrieval.get('total')} "
            f"avg_latency_ms={retrieval.get('avg_latency_ms')} "
            f"zero_result_rate={retrieval.get('zero_result_rate')}"
        )

    print("step: railway_log_scan")
    logs = _scan_railway_logs(env)
    if logs.get("available"):
        print(f"  lines={logs.get('linesScanned')} failures={len(logs.get('recentFailures') or [])}")
    else:
        print(f"  skipped: {logs.get('reason')}")

    status, notes = _evaluate(spot_checks, embedding_status, logs)
    finished = datetime.now(timezone.utc).isoformat()
    report = {
        "target": API_BASE,
        "orgId": org_id,
        "startedAt": started,
        "finishedAt": finished,
        "status": status,
        "notes": notes,
        "runbookSteps": {"step4_spot_check": spot_checks, "step6_metrics_baseline": rag_metrics},
        "embeddingStatus": embedding_status,
        "logs": logs,
        "monitoring": {
            "window": args.metrics_range,
            "rerunCommand": "npm run rag:voyage:quality-check",
            "watchFor24h": [
                "embedding_method in /api/rag-enhanced/query metrics (openai or voyage, not keyword_fallback)",
                "zero_result_rate in /api/metrics/rag?range=7d (re-run daily for 24h window)",
                "Railway logs: embedding voyage failed, dimension mismatch, keyword_fallback",
            ],
        },
    }

    default_json = REPO / "docs" / "delivery" / "voyage-rag-quality-prod-latest.json"
    out_path = Path(args.json) if args.json else default_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report: {out_path}")

    for note in notes:
        print(f"note: {note}")

    if status == "fail":
        raise SystemExit(1)
    if status == "warn":
        print("WARN")
        return
    print("OK")


if __name__ == "__main__":
    main()
