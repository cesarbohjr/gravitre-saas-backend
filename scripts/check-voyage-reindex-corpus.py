"""Corpus stats + Voyage reindex dry-run (STA-279).

Loads backend/.env and backend/.env.operator.local without printing secrets.
Usage:
  python scripts/check-voyage-reindex-corpus.py
  python scripts/check-voyage-reindex-corpus.py --dry-run --batch-size 10
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
ENV_PATHS = (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env")


def load_operator_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in ENV_PATHS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value:
                env[key.strip()] = value
    return env


def corpus_stats(env: dict[str, str]) -> dict[str, int | None]:
    if not env.get("SUPABASE_URL") or not env.get("SUPABASE_SERVICE_ROLE_KEY"):
        return {"error": -1}  # type: ignore[return-value]

    sys.path.insert(0, str(BACKEND))
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    stats: dict[str, int | None] = {}
    for table, col in (
        ("rag_sources", "id"),
        ("rag_documents", "id"),
        ("rag_chunks", "id"),
        ("rag_embeddings", "chunk_id"),
    ):
        resp = client.table(table).select(col, count="exact").limit(1).execute()
        stats[f"{table}_count"] = int(getattr(resp, "count", 0) or 0)
    pending = (
        client.table("rag_embeddings")
        .select("chunk_id", count="exact")
        .is_("embedding_voyage", "null")
        .limit(1)
        .execute()
    )
    stats["pending_voyage_count"] = int(getattr(pending, "count", 0) or 0)
    stats["voyage_complete_count"] = max(
        0,
        int(stats.get("rag_embeddings_count") or 0) - int(stats.get("pending_voyage_count") or 0),
    )
    return stats


def resolve_python() -> str:
    for candidate in (
        REPO / ".venv" / "Scripts" / "python.exe",
        REPO / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description="Voyage reindex corpus check")
    parser.add_argument("--dry-run", action="store_true", help="Run reindex script in dry-run mode")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-batches", type=int, default=1, help="Limit dry-run batches (API cost guard)")
    args = parser.parse_args()

    env = load_operator_env()
    merged = os.environ.copy()
    merged.update(env)

    stats = corpus_stats(env)
    if stats.get("error") == -1:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in backend/.env or .env.operator.local")
        return 1

    print("=== RAG corpus (Supabase) ===")
    for key in sorted(k for k in stats if k.endswith("_count")):
        print(f"{key}: {stats[key]}")

    voyage_configured = bool((env.get("VOYAGE_API_KEY") or "").strip())
    print(f"voyage_api_key_configured: {voyage_configured}")
    print(f"voyage_embedding_enabled: {(env.get('VOYAGE_EMBEDDING_ENABLED') or 'false').strip().lower()}")

    pending = int(stats.get("pending_voyage_count") or 0)
    if pending == 0:
        print("\nNo embeddings pending Voyage re-index. Dry-run would process 0 rows.")
        if not args.dry_run:
            print("Re-index is a no-op until rag_embeddings rows exist with embedding_voyage IS NULL.")
        return 0

    if not args.dry_run:
        print(f"\n{pending} embedding(s) pending Voyage vectors. Re-run with --dry-run to probe Voyage API.")
        return 0

    if not voyage_configured:
        print("\nCannot dry-run: VOYAGE_API_KEY is not set in backend/.env or .env.operator.local")
        print("Railway gravitre-saas-backend has no VOYAGE_API_KEY yet.")
        print("Set locally: $env:VOYAGE_API_KEY=\"<key>\"; npm run ai:fill-voyage-env")
        print("Then: npm run rag:voyage:dry-run")
        return 1

    print(f"\n=== Voyage reindex dry-run (batch_size={args.batch_size}, max_batches={args.max_batches}) ===")
    cmd = [
        resolve_python(),
        str(BACKEND / "scripts" / "reindex_with_voyage.py"),
        "--dry-run",
        f"--batch-size={args.batch_size}",
        f"--max-batches={args.max_batches}",
    ]
    proc = subprocess.run(cmd, cwd=str(BACKEND), env=merged, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
