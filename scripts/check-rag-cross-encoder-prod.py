"""RAG cross-encoder ops check — prod probe + Railway log scan.

Validates that hybrid RAG reranking is healthy in production:
- Live probe: POST /api/test-rag → metrics.rerank_method
- Log scan (when RAILWAY_TOKEN set): cross_encoder_* warning patterns

Usage:
  npm run rag:cross-encoder:check
  python scripts/check-rag-cross-encoder-prod.py --json docs/delivery/rag-cross-encoder-prod-latest.json
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
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://api.gravitre.app",
).rstrip("/")
ENV_NAME = "production"
RAILWAY_SERVICE = os.environ.get("RAILWAY_SERVICE", "gravitre-saas-backend")
LOG_LINE_LIMIT = int(os.environ.get("RAG_CROSS_ENCODER_LOG_LINES", "1500"))

LOG_PATTERNS: dict[str, re.Pattern[str]] = {
    "cross_encoder_load_failed": re.compile(r"cross_encoder_load_failed"),
    "cross_encoder_predict_failed": re.compile(r"cross_encoder_predict_failed"),
    "cross_encoder_unavailable": re.compile(r"sentence_transformers unavailable"),
    "cross_encoder_loading": re.compile(r"rag_cross_encoder_loading"),
    "rag_rerank_method": re.compile(r"rag_rerank org_id=.* method="),
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


def _probe_rag(token: str, org_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "endpoint": "/api/rag-enhanced/query",
        "query": "workflow failure predictions and overdue invoices",
    }
    try:
        payload = _request_json(
            "POST",
            "/api/rag-enhanced/query",
            token,
            org_id,
            {
                "query": result["query"],
                "top_k": 5,
                "scope": "organization",
                "include_sources": True,
            },
            timeout=120,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        result["error"] = f"HTTP {exc.code}: {body or exc.reason}"
        return result

    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    chunks = payload.get("chunks") or []
    result.update(
        {
            "answerPresent": bool(str(payload.get("answer") or "").strip()),
            "chunkCount": len(chunks),
            "metrics": metrics,
            "rerankMethod": metrics.get("rerank_method"),
            "crossEncoderEnabled": metrics.get("cross_encoder_enabled"),
            "embeddingMethod": metrics.get("embedding_method"),
        }
    )
    return result


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
        return {
            "available": False,
            "reason": "RAILWAY_TOKEN not set; skipped log scan",
        }

    railway_bin = _railway_executable()
    if not railway_bin:
        return {"available": False, "reason": "railway CLI not installed"}

    env_copy = os.environ.copy()
    env_copy["RAILWAY_TOKEN"] = token
    try:
        proc = subprocess.run(
            [
                railway_bin,
                "logs",
                "--service",
                RAILWAY_SERVICE,
                "--lines",
                str(LOG_LINE_LIMIT),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            env=env_copy,
            check=False,
        )
    except FileNotFoundError:
        return {"available": False, "reason": f"railway CLI not found at {railway_bin}"}
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

    failure_hits = (
        hits["cross_encoder_load_failed"]
        + hits["cross_encoder_predict_failed"]
        + hits["cross_encoder_unavailable"]
    )
    return {
        "available": True,
        "service": RAILWAY_SERVICE,
        "linesScanned": len(lines),
        "counts": {name: len(values) for name, values in hits.items()},
        "recentFailures": failure_hits[-5:],
        "recentLoads": hits["cross_encoder_loading"][-3:],
        "recentRerankInfo": hits["rag_rerank_method"][-5:],
    }


def _evaluate(probe: dict[str, Any], logs: dict[str, Any]) -> tuple[str, list[str]]:
    notes: list[str] = []
    if probe.get("error"):
        return "fail", [str(probe["error"])]

    rerank_method = probe.get("rerankMethod")
    chunk_count = int(probe.get("chunkCount") or 0)
    if rerank_method == "cross_encoder":
        notes.append(f"live probe rerank_method=cross_encoder chunks={chunk_count}")
    elif chunk_count == 0:
        notes.append("no indexed chunks; rerank path not exercised (probe still reachable)")
    elif rerank_method == "lexical_overlap":
        notes.append("rerank fell back to lexical_overlap")
    elif rerank_method:
        notes.append(f"unexpected rerank_method={rerank_method}")
    else:
        notes.append("metrics.rerank_method missing from probe response")

    if logs.get("available"):
        failure_count = sum(
            logs.get("counts", {}).get(key, 0)
            for key in (
                "cross_encoder_load_failed",
                "cross_encoder_predict_failed",
                "cross_encoder_unavailable",
            )
        )
        load_count = logs.get("counts", {}).get("cross_encoder_loading", 0)
        if failure_count:
            notes.append(f"log scan: {failure_count} cross-encoder failure line(s) in last {logs.get('linesScanned')} lines")
            return "warn", notes
        if load_count:
            notes.append(f"log scan: {load_count} successful model load(s) seen")
        else:
            notes.append("log scan: no cross-encoder activity in recent window (cold or no RAG traffic)")
    else:
        notes.append(str(logs.get("reason") or "log scan skipped"))

    if rerank_method == "cross_encoder" or chunk_count == 0:
        return "pass", notes
    if rerank_method == "lexical_overlap":
        return "warn", notes
    return "pass", notes


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG cross-encoder production ops check")
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write structured report JSON to this path",
    )
    args = parser.parse_args()

    env = _load_env()
    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)

    started = datetime.now(timezone.utc).isoformat()
    print(f"target={API_BASE}")
    print(f"org_id={org_id}")

    print("step: rag_probe")
    probe = _probe_rag(token, org_id)
    if probe.get("error"):
        print(f"  FAIL: {probe['error']}")
    else:
        print(
            f"  rerank_method={probe.get('rerankMethod')} "
            f"chunks={probe.get('chunkCount')} "
            f"cross_encoder_enabled={probe.get('crossEncoderEnabled')}"
        )

    print("step: railway_log_scan")
    logs = _scan_railway_logs(env)
    if logs.get("available"):
        print(
            f"  lines={logs.get('linesScanned')} "
            f"failures={logs.get('counts', {}).get('cross_encoder_load_failed', 0)}"
        )
    else:
        print(f"  skipped: {logs.get('reason')}")

    status, notes = _evaluate(probe, logs)
    finished = datetime.now(timezone.utc).isoformat()
    report = {
        "target": API_BASE,
        "orgId": org_id,
        "startedAt": started,
        "finishedAt": finished,
        "status": status,
        "notes": notes,
        "probe": probe,
        "logs": logs,
    }

    if args.json:
        out_path = Path(args.json)
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
